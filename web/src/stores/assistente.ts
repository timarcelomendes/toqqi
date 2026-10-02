// Assistente (etapa 5b, docs/api-etapa-5b.md §6.2): o estado de GET /assistente (o botão só aparece com a IA ligada na
// plataforma), o painel aberto, a conversa (guardada no navegador por conta e usuário; sair apaga) e as perguntas.
// Usado pelo botão flutuante do AppLayout e pela Ajuda ("Pergunte ao assistente").
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { assistenteApi, type CotaIa, type EstadoAssistente, type MensagemHistorico } from '@/api'
import { apagarConversa, chaveConversa, guardarConversa, lerConversa, type MensagemGuardada } from '@/modulos/assistente/historico'
import {
  esperaDaTentativa,
  historicoParaApi,
  LIMITE_PERGUNTA,
  lerErroPergunta,
  MENSAGENS_GUARDADAS,
  type MotivoBloqueio,
} from '@/modulos/assistente/logica'
import { useSessaoStore } from './sessao'

export interface MensagemConversa extends MensagemGuardada {
  id: number
  /** Pergunta que ficou sem resposta: não vai no histórico nem fica guardada. */
  falhou?: boolean
  /** O erro dela, mostrado na conversa logo abaixo. */
  erro?: { mensagem: string; repetir: boolean }
  /** Resposta que acabou de chegar: a tela a revela aos poucos (não é guardado). */
  nova?: boolean
}

export const useAssistenteStore = defineStore('assistente', () => {
  const sessao = useSessaoStore()
  const estado = ref<EstadoAssistente | null>(null)
  const aberto = ref(false)
  const mensagens = ref<MensagemConversa[]>([])
  /** O que está na caixa de texto (a Ajuda pode deixar o termo procurado aqui). */
  const rascunho = ref('')
  const enviando = ref(false)
  /** Para leitores de tela (região aria-live do painel): "Consultando os dados…", a resposta nova ou o erro. */
  const anuncio = ref('')

  let proximoId = 1
  /** Muda ao trocar de pessoa (ou sair): respostas que chegam depois são ignoradas. */
  let geracao = 0
  let chave: string | null = null

  // Busca do estado: um pedido por vez. Sem estado (a busca falhou), o botão não aparece: enquanto o botão estiver
  // montado (acompanharEstado) e houver sessão, tenta de novo com espera crescente e ao voltar para a aba.
  let pedidoEstado: Promise<void> | null = null
  let tentativas = 0
  let proximaTentativa: ReturnType<typeof setTimeout> | undefined
  let acompanhantes = 0

  /** O botão aparece com o estado carregado e a IA ligada na plataforma. */
  const visivel = computed(() => !!estado.value && estado.value.motivo !== 'ia_indisponivel')
  const disponivel = computed(() => !!estado.value?.disponivel)
  const cota = computed<CotaIa | null>(() => estado.value?.cota ?? null)

  // Cada conta e usuário tem a sua conversa; sem sessão (saiu), tudo volta ao começo e as tentativas param.
  watch(
    () => (sessao.conta && sessao.usuario ? chaveConversa(sessao.conta.id, sessao.usuario.id) : null),
    (nova) => {
      geracao++
      chave = nova
      mensagens.value = nova ? lerConversa(nova).map((m) => ({ ...m, id: proximoId++ })) : []
      rascunho.value = ''
      enviando.value = false
      anuncio.value = ''
      cancelarTentativa()
      tentativas = 0
      pedidoEstado = null
      if (!nova) {
        estado.value = null
        aberto.value = false
      } else if (acompanhantes > 0 && !estado.value) {
        void carregarEstado()
      }
    },
    { immediate: true },
  )

  function guardar() {
    if (!chave) return
    const ok = mensagens.value.filter((m) => !m.falhou)
    guardarConversa(
      chave,
      ok.map((m) => (m.papel === 'assistente' ? { papel: m.papel, texto: m.texto, sugestoes: m.sugestoes ?? [], atalhos: m.atalhos ?? [] } : { papel: m.papel, texto: m.texto })),
    )
  }

  /** A conversa na tela também fica nas últimas 20 mensagens. */
  function aparar() {
    const excesso = mensagens.value.length - MENSAGENS_GUARDADAS
    if (excesso > 0) mensagens.value.splice(0, excesso)
  }

  function cancelarTentativa() {
    if (proximaTentativa !== undefined) clearTimeout(proximaTentativa)
    proximaTentativa = undefined
  }

  /** Ainda sem estado: agenda a próxima busca (5 s, 15 s, 60 s, depois a cada 5 min), só com o botão montado e sessão. */
  function agendarTentativa() {
    cancelarTentativa()
    if (!acompanhantes || !chave || estado.value) return
    proximaTentativa = setTimeout(() => {
      proximaTentativa = undefined
      void carregarEstado()
    }, esperaDaTentativa(tentativas++))
  }

  async function buscarEstado(g: number): Promise<void> {
    try {
      const e = await assistenteApi.estado()
      if (g !== geracao || !e || typeof e !== 'object') return
      estado.value = { ...e, sugestoes: Array.isArray(e.sugestoes) ? e.sugestoes.filter((s) => typeof s === 'string' && s.trim()).slice(0, 3) : [] }
    } catch {
      /* sem conexão ou API sem a rota: fica o que havia (sem nenhum, tenta de novo mais tarde) */
    }
  }

  /**
   * Busca o estado (ao entrar, ao abrir o painel e nas novas tentativas). Um pedido por vez: quem chama durante outro
   * recebe o mesmo. Se falhar, fica o que havia; sem nenhum, o botão não aparece e a busca é repetida mais tarde.
   */
  function carregarEstado(): Promise<void> {
    if (!chave) return Promise.resolve()
    if (!pedidoEstado) {
      cancelarTentativa()
      const g = geracao
      const pedido: Promise<void> = buscarEstado(g).finally(() => {
        if (pedidoEstado === pedido) pedidoEstado = null
        if (g !== geracao) return
        if (estado.value) tentativas = 0
        else agendarTentativa()
      })
      pedidoEstado = pedido
    }
    return pedidoEstado
  }

  function aoVoltarParaAba() {
    if (document.visibilityState === 'visible' && !estado.value) void carregarEstado()
  }

  /** O botão entrou na tela: busca o estado e, enquanto ele não vier, tenta de novo (com espera e ao voltar para a aba). */
  function acompanharEstado(): Promise<void> {
    if (acompanhantes++ === 0) document.addEventListener('visibilitychange', aoVoltarParaAba)
    return carregarEstado()
  }

  /** O botão saiu da tela (saiu da área logada): para as tentativas. */
  function pararDeAcompanhar() {
    if (acompanhantes === 0 || --acompanhantes > 0) return
    document.removeEventListener('visibilitychange', aoVoltarParaAba)
    cancelarTentativa()
  }

  function bloquear(motivo: MotivoBloqueio) {
    const c = estado.value?.cota ?? null
    estado.value = {
      disponivel: false,
      motivo,
      sugestoes: [],
      cota: motivo === 'cota_esgotada' && c ? { ...c, usadas: Math.max(c.usadas, c.limite), restantes: 0 } : c,
    }
  }

  /** A cota volta em cada resposta; a que gastou a última análise já desliga a caixa (a próxima daria 409). */
  function atualizarCota(c: CotaIa) {
    estado.value = { disponivel: true, motivo: null, sugestoes: [], ...estado.value, cota: c }
    if (c.restantes <= 0) bloquear('cota_esgotada')
  }

  /**
   * Etapa 5d: o resumo do painel e o parecer dos relatórios gastam a mesma cota. A tela que gerou manda a cota que veio na
   * resposta, e o assistente (e Configurações › IA, que acompanha esta) mostra o mesmo "Restam X de Y". Sem o estado do
   * assistente (a busca falhou), não há o que atualizar.
   */
  function receberCota(c: CotaIa) {
    if (estado.value) atualizarCota(c)
  }

  /** Etapa 5d: o resumo ou o parecer recebeu 409 `cota_esgotada`: o assistente também para de aceitar perguntas. */
  function marcarCotaEsgotada() {
    if (estado.value && estado.value.motivo !== 'ia_indisponivel') bloquear('cota_esgotada')
  }

  async function enviar(indice: number, historico: MensagemHistorico[]) {
    const msg = mensagens.value[indice]
    if (!msg) return
    const g = geracao
    enviando.value = true
    msg.falhou = false
    msg.erro = undefined
    anuncio.value = 'Consultando os dados…'
    try {
      const r = await assistenteApi.perguntar(msg.texto, historico)
      if (g !== geracao) return
      const texto = typeof r?.resposta === 'string' ? r.resposta : ''
      mensagens.value.push({
        id: proximoId++,
        papel: 'assistente',
        texto,
        sugestoes: (Array.isArray(r.sugestoes) ? r.sugestoes : []).filter((s) => typeof s === 'string' && s.trim()).slice(0, 3),
        atalhos: (Array.isArray(r.atalhos) ? r.atalhos : []).slice(0, 2),
        nova: true,
      })
      aparar()
      if (r.cota) atualizarCota(r.cota)
      anuncio.value = texto
      guardar()
    } catch (e) {
      if (g !== geracao) return
      const erro = lerErroPergunta(e)
      msg.falhou = true
      msg.erro = { mensagem: erro.mensagem, repetir: erro.repetir }
      if (erro.bloqueio) bloquear(erro.bloqueio)
      anuncio.value = erro.mensagem
    } finally {
      if (g === geracao) enviando.value = false
    }
  }

  /** Manda uma pergunta (a pergunta aparece na hora). Ignora vazia, enquanto outra está indo ou sem o assistente. */
  async function perguntar(texto: string): Promise<boolean> {
    const pergunta = texto.trim().slice(0, LIMITE_PERGUNTA).trim()
    if (!pergunta || enviando.value || !disponivel.value) return false
    const historico = historicoParaApi(mensagens.value)
    mensagens.value.push({ id: proximoId++, papel: 'usuario', texto: pergunta })
    aparar()
    await enviar(mensagens.value.length - 1, historico)
    return true
  }

  /** "Tentar de novo": manda outra vez a última pergunta, se ela falhou. */
  async function tentarDeNovo(): Promise<void> {
    const i = mensagens.value.length - 1
    const ultima = mensagens.value[i]
    if (!ultima || ultima.papel !== 'usuario' || !ultima.falhou || enviando.value || !disponivel.value) return
    await enviar(i, historicoParaApi(mensagens.value.slice(0, i)))
  }

  function novaConversa() {
    if (enviando.value) return
    mensagens.value = []
    anuncio.value = ''
    if (chave) apagarConversa(chave)
  }

  /** Abre o painel (com um texto na caixa, se vier) e busca o estado de novo (cota e sugestões). */
  function abrir(texto?: string) {
    if (texto?.trim()) rascunho.value = texto.trim().slice(0, LIMITE_PERGUNTA)
    aberto.value = true
    carregarEstado()
  }

  function fechar() {
    aberto.value = false
    // Reabrir mostra a resposta inteira, sem revelar de novo.
    for (const m of mensagens.value) m.nova = false
  }

  function marcarRevelada(id: number) {
    const m = mensagens.value.find((x) => x.id === id)
    if (m) m.nova = false
  }

  return {
    estado,
    aberto,
    mensagens,
    rascunho,
    enviando,
    anuncio,
    visivel,
    disponivel,
    cota,
    carregarEstado,
    acompanharEstado,
    pararDeAcompanhar,
    perguntar,
    tentarDeNovo,
    novaConversa,
    abrir,
    fechar,
    marcarRevelada,
    receberCota,
    marcarCotaEsgotada,
  }
})
