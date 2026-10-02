import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, authApi, euApi } from '@/api'
import type { Conta, DadosSessao, Permissao, Sessao, Usuario } from '@/api'
import { apagarConversas } from '@/modulos/assistente/historico'

const CHAVE = 'toqqi.sessao'

interface SessaoGuardada extends DadosSessao {
  token: string
  expira_em: string | null
}

function armazenamento(lembrar: boolean): Storage | null {
  try {
    return lembrar ? window.localStorage : window.sessionStorage
  } catch {
    return null
  }
}

function lerGuardada(): { dados: SessaoGuardada; lembrar: boolean } | null {
  for (const lembrar of [true, false]) {
    try {
      const bruto = armazenamento(lembrar)?.getItem(CHAVE)
      if (!bruto) continue
      const dados = JSON.parse(bruto) as SessaoGuardada
      if (dados && typeof dados.token === 'string' && dados.token) return { dados, lembrar }
    } catch {
      /* ignora dado corrompido */
    }
  }
  return null
}

export const useSessaoStore = defineStore('sessao', () => {
  const token = ref<string | null>(null)
  const expiraEm = ref<string | null>(null)
  const usuario = ref<Usuario | null>(null)
  const conta = ref<Conta | null>(null)
  const permissoes = ref<Permissao[]>([])
  const lembrar = ref(false)
  const inicializada = ref(false)
  /** Mensagem para mostrar na tela de entrar (ex.: "sua sessão terminou"). */
  const avisoEntrar = ref<string | null>(null)

  const logado = computed(() => !!token.value && !!usuario.value)
  const superadmin = computed(() => !!usuario.value?.superadmin)
  /** Perfil administrador da conta (algumas telas e ações são só dele). */
  const admin = computed(() => usuario.value?.perfil === 'admin')

  function pode(permissao: Permissao): boolean {
    return permissoes.value.includes(permissao)
  }

  function persistir() {
    // Limpa os dois lugares e grava só no escolhido.
    armazenamento(true)?.removeItem(CHAVE)
    armazenamento(false)?.removeItem(CHAVE)
    if (!token.value || !usuario.value || !conta.value) return
    const dados: SessaoGuardada = {
      token: token.value,
      expira_em: expiraEm.value,
      usuario: usuario.value,
      conta: conta.value,
      permissoes: permissoes.value,
    }
    try {
      armazenamento(lembrar.value)?.setItem(CHAVE, JSON.stringify(dados))
    } catch {
      /* armazenamento cheio/indisponível: a sessão vale só nesta aba */
    }
  }

  /** Quando a sessão veio da API pela última vez (ms). */
  let atualizadaEm = 0

  function aplicarDados(d: DadosSessao) {
    usuario.value = d.usuario
    conta.value = d.conta
    permissoes.value = Array.isArray(d.permissoes) ? d.permissoes : []
    atualizadaEm = Date.now()
  }

  function definirSessao(s: Sessao, lembrarDeMim: boolean) {
    token.value = s.token
    expiraEm.value = s.expira_em ?? null
    lembrar.value = lembrarDeMim
    aplicarDados(s)
    avisoEntrar.value = null
    persistir()
  }

  function limpar(aviso?: string | null) {
    token.value = null
    expiraEm.value = null
    usuario.value = null
    conta.value = null
    permissoes.value = []
    if (aviso !== undefined) avisoEntrar.value = aviso
    persistir()
    // Etapa 5b: a conversa com o assistente fica só nesta sessão do navegador; ao sair, some.
    apagarConversas()
  }

  function atualizarUsuario(u: Usuario) {
    usuario.value = u
    persistir()
  }

  /** Atualiza dados da conta já na sessão (ex.: nome e logo salvos em Configurações › Empresa): o topo muda na hora. */
  function atualizarConta(parcial: Partial<Conta>) {
    if (!conta.value) return
    conta.value = { ...conta.value, ...parcial }
    persistir()
  }

  /** Busca /eu para ter dados e permissões atualizados. */
  async function recarregar() {
    const d = await euApi.obter()
    aplicarDados(d)
    persistir()
  }

  /**
   * Busca /eu de novo se a última busca foi há mais de `ms` (a aba voltou a ficar visível): quem pagou pelo e-mail do
   * Asaas ou noutro aparelho vê o aviso do topo e os envios certos sem recarregar a página.
   */
  async function recarregarSeAntiga(ms = 180_000) {
    if (!token.value || Date.now() - atualizadaEm < ms) return
    atualizadaEm = Date.now() // duas voltas seguidas não fazem duas buscas
    try {
      await recarregar()
    } catch {
      /* sem conexão: fica a sessão que está; 401 já é tratado pelo cliente */
    }
  }

  /** Chamado uma vez pelo router antes da primeira navegação. */
  async function inicializar() {
    if (inicializada.value) return
    inicializada.value = true
    const guardada = lerGuardada()
    if (!guardada) return
    const { dados } = guardada
    // Não expiramos pelo relógio local: quem decide é a API (401 sessao_invalida em /eu).
    token.value = dados.token
    expiraEm.value = dados.expira_em
    lembrar.value = guardada.lembrar
    if (dados.usuario && dados.conta) aplicarDados(dados)
    try {
      await recarregar()
    } catch (e) {
      // Sessão inválida: o cliente já avisou via gancho; aqui só garantimos a limpeza.
      if (e instanceof ApiError && e.status === 401) limpar()
      // Sem conexão: seguimos com os dados guardados.
      else if (!usuario.value) limpar()
    }
  }

  async function entrar(email: string, senha: string, lembrarDeMim: boolean) {
    const s = await authApi.entrar({ email, senha, lembrar: lembrarDeMim })
    definirSessao(s, lembrarDeMim)
    // A resposta do login não traz o logo da conta (só GET /eu traz): busca em segundo plano, sem segurar a entrada.
    if (s.conta && !('logo_url' in s.conta)) recarregar().catch(() => {})
  }

  async function sair() {
    try {
      if (token.value) await authApi.sair()
    } catch {
      /* mesmo com erro, saímos localmente */
    } finally {
      limpar(null)
    }
  }

  return {
    token,
    expiraEm,
    usuario,
    conta,
    permissoes,
    lembrar,
    inicializada,
    avisoEntrar,
    logado,
    superadmin,
    admin,
    pode,
    definirSessao,
    limpar,
    atualizarUsuario,
    atualizarConta,
    recarregar,
    recarregarSeAntiga,
    inicializar,
    entrar,
    sair,
  }
})
