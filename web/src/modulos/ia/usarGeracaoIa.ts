// Resumo do painel e parecer dos relatórios (etapa 5d, docs/api-etapa-5d.md §6.1 e §6.2): lê o que está salvo para os
// filtros da tela (de novo a cada troca de filtro), gera (o custo do nível da conta: 1 análise da cota, ou 2 no Mais
// detalhado), conta até poder gerar de novo e diz o que mostrar em cada caso. O cartão do painel e o painel lateral dos
// relatórios só desenham o que vem daqui.
import { computed, onBeforeUnmount, onMounted, ref, useId, watch, type Ref } from 'vue'
import { mensagemDoErro, type CotaIa, type EstadoGeracaoIa, type FiltrosGeracaoIa, type ResultadoGeracaoIa } from '@/api'
import { MENSAGEM_INESPERADA } from '@/api/erros'
import { useAssistenteStore } from '@/stores/assistente'
import {
  MENSAGEM_COTA_ESGOTADA,
  MENSAGEM_IA_INDISPONIVEL,
  TEXTO_PODE_GERAR,
  chaveFiltros,
  instante,
  lerCota,
  lerCusto,
  lerErroGeracao,
  mensagemCotaInsuficiente,
  normalizarItem,
  prazoLocal,
  rotuloBotaoGerar,
  segundosAte,
  textoVazio,
  type ErroGeracao,
  type ItemIa,
  type TextosGeracaoIa,
} from './logica'

export interface OpcoesGeracaoIa<C> {
  obter: (f: FiltrosGeracaoIa, sinal: AbortSignal) => Promise<EstadoGeracaoIa<unknown>>
  gerar: (f: FiltrosGeracaoIa) => Promise<ResultadoGeracaoIa<unknown>>
  /** Lê o conteúdo que veio da API (null = inválido: como se não houvesse nada salvo). */
  conteudo: (c: unknown) => C | null
  /** Os filtros da tela; null enquanto não dá para buscar (datas escolhidas incompletas). */
  filtros: () => FiltrosGeracaoIa | null
  /**
   * Só lê de novo a cada troca de filtro enquanto for verdadeiro (o parecer, com o painel aberto). A primeira leitura, ao
   * montar, acontece sempre; enquanto nenhuma leitura deu certo (falhou ou as datas estavam incompletas), troca de filtro
   * também lê, senão o botão do parecer não apareceria mais.
   */
  ativo?: () => boolean
  textos: TextosGeracaoIa
  /** O conteúdo em texto corrido, para leitores de tela. */
  falar: (c: C) => string
}

/** O estado que as telas desenham (tudo só leitura, menos as duas ações). */
export interface GeracaoIa<C> {
  /** Já leu uma vez e a IA existe na plataforma (sem IA, nada aparece). */
  readonly visivel: boolean
  /** O que está na tela é dos filtros atuais. */
  readonly atual: boolean
  readonly lendo: boolean
  /** A leitura falhou (com algo já lido antes): aviso com "Tentar de novo". */
  readonly erroLeitura: string | null
  readonly disponivel: boolean
  readonly item: ItemIa<C> | null
  /** Análises que uma geração gasta no nível da conta (1, ou 2 no Mais detalhado). */
  readonly custo: number
  /** O texto de quando não há nada salvo, com o custo ("Usa 2 análises de IA."). */
  readonly textoVazio: string
  /** Por que não dá para gerar (conta pausada, cota esgotada ou insuficiente…), no lugar do botão; null quando dá. */
  readonly bloqueio: string | null
  readonly cotaEsgotada: boolean
  /** Restam análises, mas menos que o custo do nível (ex.: 1 no Mais detalhado). */
  readonly cotaInsuficiente: boolean
  /** Gerando para os filtros da tela (uma geração pedida com os filtros anteriores não ocupa a tela dos novos). */
  readonly gerando: boolean
  readonly erro: ErroGeracao | null
  /** A geração pedida terminou depois de a pessoa trocar os filtros (ficou salva para os anteriores). */
  readonly prontoAnterior: string | null
  /** Segundos até poder gerar de novo (0 = pode). */
  readonly segundos: number
  readonly mostrarBotao: boolean
  readonly podeGerar: boolean
  /** O nome do botão ("Gerar resumo", "Gerar de novo"): fixo; a contagem aparece à parte, fora do nome acessível. */
  readonly rotuloBotao: string
  /** id do botão de gerar: o foco volta para ele quando um aviso com "Tentar de novo" some. */
  readonly idBotao: string
  /** Depois de gerar: a cota do mês ("Restam X de Y"). */
  readonly cota: CotaIa | null
  /** Para a região aria-live: o texto gerado e o fim da espera (os avisos já são regiões vivas). */
  readonly anuncio: string
  readonly textos: TextosGeracaoIa
  ler(): Promise<void>
  gerar(): Promise<void>
}

export function usarGeracaoIa<C>(opcoes: OpcoesGeracaoIa<C>): GeracaoIa<C> {
  const assistente = useAssistenteStore()
  const idBotao = `gerar-ia-${useId()}`
  const ativo = () => opcoes.ativo?.() ?? true
  const chave = computed(() => {
    const f = opcoes.filtros()
    return f ? chaveFiltros(f) : null
  })

  // ── O que a última leitura disse ──────────────────────────────────────────
  const lido = ref(false)
  const lendo = ref(false)
  const erroLeitura = ref<string | null>(null)
  const chaveLida = ref<string | null>(null)
  const disponivel = ref(false)
  const motivo = ref<string | null>(null)
  const item = ref(null) as Ref<ItemIa<C> | null>
  /** Análises que uma geração gasta no nível da conta (do GET; a resposta da geração também traz). */
  const custo = ref(1)
  /** A cota mais nova que esta tela recebeu (do GET ou da geração): o que resta, na frase da cota insuficiente. */
  const ultimaCota = ref<CotaIa | null>(null)
  /**
   * Mensagem do 409 `cota_esgotada` ou `cota_insuficiente` do POST, com o motivo dela (no GET só vem o motivo: a tela usa
   * a frase padrão ou a monta com o que resta e o custo).
   */
  const mensagemCota = ref<{ motivo: string; texto: string } | null>(null)

  // ── Geração ───────────────────────────────────────────────────────────────
  /** A chave dos filtros da geração em andamento (null sem nenhuma). */
  const chaveGerando = ref<string | null>(null)
  const erro = ref<ErroGeracao | null>(null)
  const prontoAnterior = ref<string | null>(null)
  const cotaGerada = ref<CotaIa | null>(null)
  const anuncio = ref('')

  // ── Espera de 30 s (vale para a conta toda, qualquer filtro) ─────────────
  /** Até quando esperar, no relógio do aparelho (ms). */
  const podeGerarEm = ref<number | null>(null)
  const agora = ref(Date.now())
  let relogio: ReturnType<typeof setInterval> | undefined
  /** A espera começou por uma geração (ou 429) desta tela: ao acabar, avisa o leitor de tela. */
  let avisarFim = false
  /** A tela saiu: uma geração que volta depois não liga mais a contagem. */
  let montado = true
  /** O último `pode_gerar_em` da API (hora do servidor, ms): a mesma espera lida de novo não recomeça a contagem. */
  let ultimoDaApi: number | null = null

  const visivel = computed(() => lido.value && motivo.value !== 'ia_indisponivel')
  const atual = computed(() => chave.value !== null && chave.value === chaveLida.value)
  const gerando = computed(() => chaveGerando.value !== null && chaveGerando.value === chave.value)
  const segundos = computed(() => segundosAte(podeGerarEm.value, agora.value))
  const cotaEsgotada = computed(() => !disponivel.value && motivo.value === 'cota_esgotada')
  const cotaInsuficiente = computed(() => !disponivel.value && motivo.value === 'cota_insuficiente')
  const bloqueio = computed<string | null>(() => {
    if (disponivel.value) return null
    if (motivo.value === 'conta_pausada') return opcoes.textos.pausada
    const daApi = mensagemCota.value?.motivo === motivo.value ? mensagemCota.value.texto : null
    if (motivo.value === 'cota_esgotada') return daApi ?? MENSAGEM_COTA_ESGOTADA
    if (motivo.value === 'cota_insuficiente') return daApi ?? mensagemCotaInsuficiente(ultimaCota.value?.restantes ?? 1, custo.value)
    return MENSAGEM_IA_INDISPONIVEL
  })
  const mostrarBotao = computed(() => visivel.value && disponivel.value && !erroLeitura.value)
  // Uma geração de cada vez, com qualquer filtro (a API responderia 429).
  const podeGerar = computed(() => mostrarBotao.value && atual.value && chaveGerando.value === null && segundos.value === 0)
  const rotuloBotao = computed(() => rotuloBotaoGerar(opcoes.textos.gerar, !!item.value))
  /** A cota mais nova: a desta geração ou, no mesmo mês, a do assistente (que muda a cada pergunta). */
  const cota = computed<CotaIa | null>(() => {
    const c = cotaGerada.value
    const a = assistente.cota
    return c && a && a.mes === c.mes ? a : c
  })

  function pararRelogio() {
    if (relogio !== undefined) clearInterval(relogio)
    relogio = undefined
  }

  /** Guarda até quando esperar (o prazo mais distante que a tela conhece, no relógio do aparelho) e liga a contagem. */
  function esperarAte(prazo: number | null, avisar = false) {
    if (prazo === null || !montado) return
    if (podeGerarEm.value === null || prazo > podeGerarEm.value) podeGerarEm.value = prazo
    agora.value = Date.now()
    if (segundos.value === 0) return
    if (avisar) avisarFim = true
    if (relogio !== undefined) return
    relogio = setInterval(() => {
      agora.value = Date.now()
      if (segundos.value > 0) return
      pararRelogio()
      // O aviso do 429 ("Aguarde 12 s para gerar de novo.") era desta espera: o botão voltou, o aviso sai.
      if (erro.value?.esperar) erro.value = null
      if (avisarFim && mostrarBotao.value) anuncio.value = TEXTO_PODE_GERAR
      avisarFim = false
    }, 1000)
  }

  /**
   * O `pode_gerar_em` da API (hora do servidor) vira um prazo no relógio do aparelho na hora em que chega: um aparelho
   * adiantado ou atrasado não muda a espera, que nunca passa de 30 s.
   */
  function esperarPelaApi(iso: string | null | undefined, avisar = false) {
    const t = instante(iso)
    if (t === null || t === ultimoDaApi) return
    ultimoDaApi = t
    esperarAte(prazoLocal(t, Date.now()), avisar)
  }

  // ── Leitura ───────────────────────────────────────────────────────────────
  let controle: AbortController | null = null
  let pedido = 0

  /** A leitura em andamento deixa de valer (o que ela trouxer é descartado). */
  function cancelarLeitura() {
    pedido++
    controle?.abort()
    controle = null
    lendo.value = false
  }

  function aplicarEstado(r: EstadoGeracaoIa<unknown>, k: string) {
    disponivel.value = r.disponivel === true
    motivo.value = disponivel.value ? null : typeof r.motivo === 'string' && r.motivo ? r.motivo : null
    if (mensagemCota.value?.motivo !== motivo.value) mensagemCota.value = null
    custo.value = lerCusto(r.custo)
    ultimaCota.value = lerCota(r.cota)
    item.value = normalizarItem(r.item, opcoes.conteudo)
    chaveLida.value = k
    erroLeitura.value = null
    lido.value = true
    esperarPelaApi(r.pode_gerar_em)
  }

  async function ler(): Promise<void> {
    const f = opcoes.filtros()
    if (!f) return
    const k = chaveFiltros(f)
    controle?.abort()
    controle = new AbortController()
    const meu = ++pedido
    lendo.value = true
    try {
      const r = await opcoes.obter(f, controle.signal)
      if (meu !== pedido) return
      if (!r || typeof r !== 'object') throw new Error('resposta inválida')
      aplicarEstado(r, k)
    } catch (e) {
      if (meu !== pedido || (e instanceof DOMException && e.name === 'AbortError')) return
      // Sem nada lido ainda, o cartão (ou o botão do parecer) não aparece; com algo na tela, avisa e deixa tentar de novo.
      erroLeitura.value = e instanceof Error && e.message === 'resposta inválida' ? MENSAGEM_INESPERADA : mensagemDoErro(e)
    } finally {
      if (meu === pedido) lendo.value = false
    }
  }

  // Filtros novos: o aviso, o "Restam" e o anúncio eram dos anteriores.
  watch(chave, () => {
    erro.value = null
    prontoAnterior.value = null
    cotaGerada.value = null
    anuncio.value = ''
  })
  // Lê de novo a cada troca de filtro: o parecer, só com o painel aberto ou enquanto nenhuma leitura deu certo.
  watch([chave, ativo], ([k, a]) => {
    if (k !== null && (a || !lido.value)) void ler()
  })

  // ── Geração ───────────────────────────────────────────────────────────────
  async function gerar(): Promise<void> {
    const f = opcoes.filtros()
    if (!f || !podeGerar.value) return
    const k = chaveFiltros(f)
    chaveGerando.value = k
    erro.value = null
    prontoAnterior.value = null
    anuncio.value = ''
    try {
      const r = await opcoes.gerar(f)
      esperarPelaApi(r?.pode_gerar_em, true)
      const c = lerCota(r?.cota)
      // O custo desta geração (o do nível da conta); sem ele na resposta, fica o do GET.
      const novoCusto = typeof r?.custo === 'number' ? lerCusto(r.custo) : undefined
      if (novoCusto !== undefined) custo.value = novoCusto
      if (c) {
        ultimaCota.value = c
        assistente.receberCota(c, novoCusto)
      }
      // A geração que deixou menos análises que o custo já tira o botão (a próxima daria 409), com qualquer filtro na
      // tela: sem nenhuma, "cota esgotada"; com alguma (1 no Mais detalhado), "cota insuficiente".
      if (c && c.restantes < custo.value) {
        disponivel.value = false
        motivo.value = c.restantes <= 0 ? 'cota_esgotada' : 'cota_insuficiente'
        mensagemCota.value = null
      }
      // Os filtros mudaram enquanto gerava: a tela é dos novos; o pedido ficou salvo para os anteriores.
      if (k !== chave.value) {
        prontoAnterior.value = opcoes.textos.prontoAnterior
        return
      }
      const novo = normalizarItem(r?.item, opcoes.conteudo)
      if (novo) {
        // Uma leitura destes filtros que ainda está indo traria o item de antes por cima do novo.
        cancelarLeitura()
        item.value = novo
        chaveLida.value = k
        erroLeitura.value = null
      }
      cotaGerada.value = c
      anuncio.value = novo ? `${opcoes.textos.gerado} ${opcoes.falar(novo.conteudo)}` : opcoes.textos.gerado
    } catch (e) {
      const er = lerErroGeracao(e)
      if (er.bloqueio) {
        disponivel.value = false
        motivo.value = er.bloqueio
        if (er.bloqueio === 'cota_esgotada' || er.bloqueio === 'cota_insuficiente') {
          mensagemCota.value = { motivo: er.bloqueio, texto: er.mensagem }
          // A cota e o nível são da conta: o assistente também para.
          assistente.marcarSemCota(er.bloqueio)
        }
      } else if (k === chave.value) {
        erro.value = er
      }
      if (er.esperar) esperarAte(Date.now() + er.esperar * 1000, true)
      // Sem anúncio à parte: o aviso (Alerta) já é uma região viva, e o leitor de tela ouviria o erro duas vezes.
    } finally {
      chaveGerando.value = null
    }
  }

  onMounted(() => void ler())
  onBeforeUnmount(() => {
    montado = false
    cancelarLeitura()
    pararRelogio()
  })

  // Getters: cada campo lê o ref na hora (a tela acompanha as mudanças) e o compilador confere os tipos de GeracaoIa.
  return {
    get visivel() {
      return visivel.value
    },
    get atual() {
      return atual.value
    },
    get lendo() {
      return lendo.value
    },
    get erroLeitura() {
      return erroLeitura.value
    },
    get disponivel() {
      return disponivel.value
    },
    get item() {
      return item.value
    },
    get custo() {
      return custo.value
    },
    get textoVazio() {
      return textoVazio(opcoes.textos, custo.value)
    },
    get bloqueio() {
      return bloqueio.value
    },
    get cotaEsgotada() {
      return cotaEsgotada.value
    },
    get cotaInsuficiente() {
      return cotaInsuficiente.value
    },
    get gerando() {
      return gerando.value
    },
    get erro() {
      return erro.value
    },
    get prontoAnterior() {
      return prontoAnterior.value
    },
    get segundos() {
      return segundos.value
    },
    get mostrarBotao() {
      return mostrarBotao.value
    },
    get podeGerar() {
      return podeGerar.value
    },
    get rotuloBotao() {
      return rotuloBotao.value
    },
    idBotao,
    get cota() {
      return cota.value
    },
    get anuncio() {
      return anuncio.value
    },
    textos: opcoes.textos,
    ler,
    gerar,
  }
}
