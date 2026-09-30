import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, authApi, euApi } from '@/api'
import type { Conta, DadosSessao, Permissao, Sessao, Usuario } from '@/api'

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

  function aplicarDados(d: DadosSessao) {
    usuario.value = d.usuario
    conta.value = d.conta
    permissoes.value = Array.isArray(d.permissoes) ? d.permissoes : []
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
  }

  function atualizarUsuario(u: Usuario) {
    usuario.value = u
    persistir()
  }

  /** Busca /eu para ter dados e permissões atualizados. */
  async function recarregar() {
    const d = await euApi.obter()
    aplicarDados(d)
    persistir()
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
    pode,
    definirSessao,
    limpar,
    atualizarUsuario,
    recarregar,
    inicializar,
    entrar,
    sair,
  }
})
