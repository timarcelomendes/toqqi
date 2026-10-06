<script setup lang="ts">
// Pesquisa que o cliente responde. É o MESMO componente da página pública (/r e /f)
// e da pré-visualização do editor. Não importa Pinia, router nem ícones externos.
// Etapa 5l (docs/api-etapa-5l.md §5.2): a navegação segue o caminho da lógica (mostrar se, pular), recalculado a cada
// resposta; o bloco de conteúdo é um passo próprio; títulos citam respostas ({{id}}); o final pode vir da lógica.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { API_URL } from '@/api/cliente'
import BlocoHtml from './BlocoHtml.vue'
import CampoPergunta from './CampoPergunta.vue'
import CartaoDepoimento from './CartaoDepoimento.vue'
import CartaoIndicacao from './CartaoIndicacao.vue'
import { corDoTexto, corValida } from './cor'
import { carregarLimpador, textoDoHtml } from './html'
import { lerConviteIndicacao, lerDepoimento, notaDaDireitoAIndicacao } from './indicacao'
import {
  citarComValores,
  escolherFinal,
  faixa,
  indexar,
  paginasDoCaminho,
  percorrer,
  perguntaPrincipal,
  respondivel,
  respostasParaEnvio,
} from './logica'
import { renderizarVariaveis, renderizarVariaveisHtml } from './variaveis'
import { validarPerguntas, validarResposta } from './validacao'
import {
  FOCO_FINAL_PADRAO,
  TEMA_PADRAO,
  type BotaoFinal,
  type ConviteIndicacao,
  type DadosIndicacao,
  type Final,
  type FormularioPublico,
  type Pergunta,
  type Respostas,
  type TelaFinal,
  type TelaFinalDepoimento,
  type ValorResposta,
  type Variaveis,
} from './tipos'

/** Erro que `enviar` pode lançar: mensagem para mostrar e, se houver, erros por pergunta. */
export interface ErroEnvio {
  mensagem?: string
  campos?: Record<string, string>
}

const props = withDefaults(
  defineProps<{
    formulario: FormularioPublico
    variaveis?: Partial<Variaveis>
    /** ?nota=N: já marca a nota principal e começa depois dela (ou na 1ª obrigatória antes dela). */
    notaInicial?: number | null
    /** Envia as respostas. Devolve a tela final, ou null se quem chamou assumiu (ex.: "já respondido"). Sem ela: pré-visualização. */
    enviar?: (respostas: Respostas) => Promise<TelaFinal | null>
    /** Dentro de iframe (embed=1): sem margens de fora. */
    compacto?: boolean
    /** Pré-visualização do editor: mostra aviso e botão de recomeçar. */
    previa?: boolean
    /** Etapa 5c: envia uma indicação (convite individual) e devolve a mensagem de obrigado. Sem ela, o cartão é exemplo. */
    indicar?: (dados: DadosIndicacao) => Promise<string | void>
    /** Melhoria 5: autoriza publicar o comentário como depoimento (convite individual). */
    autorizarDepoimento?: () => Promise<string | void>
    /**
     * Etapa 5c, pré-visualização: o convite de exemplo, pedido quando a pesquisa termina com nota de promotor (NPS 9–10
     * ou CSAT 5); null não mostra o cartão (ex.: indicações desligadas na conta).
     */
    indicacaoExemplo?: () => Promise<ConviteIndicacao | null>
    /** Etapa 5l, prévia: os finais por condição (o final sai de `escolherFinal`; nenhum vale = final padrão do tema). */
    finais?: Final[]
    /** Etapa 5l, prévia: abre direto neste item (ou final; `FOCO_FINAL_PADRAO` para o padrão), mesmo fora do caminho. */
    focoId?: string | null
    /** Etapa 5l, prévia: a condição do item em foco, já em frase ("NPS é detrator ou neutro"). */
    motivoFoco?: string | null
    /** Prévia: o botão "Reiniciar prévia" embaixo da pesquisa (a prévia do editor tem o dela, na barra). */
    reiniciavel?: boolean
  }>(),
  {
    variaveis: () => ({}),
    notaInicial: null,
    compacto: false,
    previa: false,
    indicar: undefined,
    indicacaoExemplo: undefined,
    autorizarDepoimento: undefined,
    finais: () => [],
    focoId: null,
    motivoFoco: null,
    reiniciavel: true,
  },
)

const tema = computed(() => ({ ...TEMA_PADRAO, ...(props.formulario.tema ?? {}) }))
const cor = computed(() => corValida(tema.value.cor))
const estiloCor = computed(() => ({
  '--cor': cor.value,
  '--cor-texto': corDoTexto(cor.value),
  '--cor-suave': `color-mix(in srgb, ${cor.value} 10%, white)`,
}))
const itens = computed<Pergunta[]>(() => props.formulario.perguntas ?? [])
const porId = computed(() => indexar(itens.value))
const principal = computed(() => perguntaPrincipal(itens.value))
const umaPorVez = computed(() => tema.value.modo !== 'paginas')
const v = (t: string | null | undefined) => renderizarVariaveis(t, props.variaveis)
/** Só as imagens da plataforma entram no HTML (§3.1). Sem o prefixo no payload (API antiga), o da API daqui. */
const prefixoImagens = computed(() => props.formulario.prefixo_imagens || `${API_URL}/publico/imagens/`)

const respostas = reactive<Respostas>({})
const erros = reactive<Record<string, string>>({})
// Etapa 5h: não há mais a tela "Começar"; a abertura vai no alto da primeira pergunta.
const etapa = ref<'perguntas' | 'final'>('perguntas')
/** Uma por vez: o item da tela. Páginas: o número da página da tela (`PaginaDoCaminho.numero`). */
const atualId = ref<string | null>(null)
const paginaAtual = ref<number | null>(null)
/** Prévia: item em foco que, com as respostas da prévia, não está no caminho (aparece mesmo assim, com a faixa). */
const forcado = ref<string | null>(null)
const enviando = ref(false)
const erroEnvio = ref<string | null>(null)
const telaFinal = ref<TelaFinal | null>(null)
/** As respostas enviadas (as citações do final usam estas). */
const enviadas = ref<Respostas>({})
/** Prévia: final em foco (o editor selecionou um final); a faixa diz quando ele aparece. */
const finalEmFoco = ref<string | null>(null)
/** Etapa 5c: o convite de indicação da tela final (da API ou, na pré-visualização, o de exemplo). */
const indicacao = ref<ConviteIndicacao | null>(null)
/** Melhoria 5: o pedido de depoimento e o link de avaliação da tela final. */
const depoimento = ref<TelaFinalDepoimento | null>(null)
let pedidoExemplo = 0
const raiz = ref<HTMLElement | null>(null)
const anuncio = ref('')
let temporizador: ReturnType<typeof setTimeout> | null = null

/** O caminho com as respostas de agora (recalculado a cada resposta). */
const percurso = computed(() => percorrer(itens.value, respostas))
const caminhoIds = computed(() => percurso.value.ids)
/** Os passos da tela: o caminho e, na prévia, o item em foco na posição dele. */
const passos = computed<string[]>(() => {
  const ids = caminhoIds.value
  const f = forcado.value
  if (!f || ids.includes(f) || !porId.value.has(f)) return ids
  const posicao = (id: string) => itens.value.findIndex((p) => p.id === id)
  const pf = posicao(f)
  const i = ids.findIndex((id) => posicao(id) > pf)
  return i < 0 ? [...ids, f] : [...ids.slice(0, i), f, ...ids.slice(i)]
})
const paginas = computed(() => paginasDoCaminho(itens.value, passos.value))
const indice = computed(() => {
  if (umaPorVez.value) return Math.max(0, atualId.value ? passos.value.indexOf(atualId.value) : 0)
  return Math.max(0, paginas.value.findIndex((pg) => pg.numero === paginaAtual.value))
})
const total = computed(() => (umaPorVez.value ? passos.value.length : paginas.value.length))
const atuais = computed<Pergunta[]>(() => {
  if (umaPorVez.value) {
    const p = atualId.value ? porId.value.get(atualId.value) : undefined
    return p && passos.value.includes(p.id) ? [p] : []
  }
  return paginas.value[indice.value]?.itens ?? []
})
const ultima = computed(() => indice.value >= total.value - 1)
const progresso = computed(() => (total.value ? Math.round(((indice.value + (etapa.value === 'final' ? 1 : 0)) / total.value) * 100) : 0))
/** "Pergunta N de M" conta só perguntas (o bloco de conteúdo é passo, mas não é pergunta). */
const perguntasDoCaminho = computed(() => passos.value.filter((id) => respondivel(porId.value.get(id)?.tipo)))
const numeroPergunta = computed(() => {
  const id = atuais.value[0]?.id
  return id && umaPorVez.value ? perguntasDoCaminho.value.indexOf(id) + 1 : 0
})
// Abertura (título e texto de boas-vindas): no alto da primeira pergunta (ou da primeira página), na mesma tela.
// Sem título de abertura, só o texto (o nome do formulário é interno: não vira título).
const tituloAbertura = computed(() => v(tema.value.titulo_abertura))
const textoAbertura = computed(() => v(tema.value.texto_abertura))
const mostrarAbertura = computed(() => indice.value === 0 && !forcado.value && !!(tituloAbertura.value || textoAbertura.value))

/** Citações com as respostas do caminho (texto puro e HTML escapado). */
const citarTexto = (t: string) => citarComValores(t, porId.value, percurso.value.valores)
/** HTML de um bloco de conteúdo: variáveis (na prévia; na página pública a API já trocou), citações escapadas. */
function htmlConteudo(p: Pergunta): string {
  const html = props.previa ? renderizarVariaveisHtml(p.html, props.variaveis) : (p.html ?? '')
  return citarComValores(html, porId.value, percurso.value.valores, true)
}

// Embaralhar (aleatorizar): uma vez por visita, guardado aqui (voltar e avançar não reembaralha).
const ordens = new Map<string, string[]>()
function ordemOpcoes(p: Pergunta): string[] | undefined {
  const opcoes = p.opcoes ?? []
  if (!p.aleatorizar || opcoes.length < 2) return undefined
  const chave = `${p.id}\u0000${opcoes.join('\u0000')}`
  let ordem = ordens.get(chave)
  if (!ordem) {
    ordem = [...opcoes]
    for (let i = ordem.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[ordem[i], ordem[j]] = [ordem[j]!, ordem[i]!]
    }
    ordens.set(chave, ordem)
  }
  return ordem
}

function limparObjeto(o: Record<string, unknown>) {
  for (const k of Object.keys(o)) delete o[k]
}

function primeiroPasso() {
  atualId.value = passos.value[0] ?? null
  paginaAtual.value = paginas.value[0]?.numero ?? null
}

function irPara(id: string) {
  if (umaPorVez.value) atualId.value = id
  else paginaAtual.value = paginas.value.find((pg) => pg.itens.some((p) => p.id === id))?.numero ?? paginaAtual.value
}

function iniciar() {
  cancelarAvanco()
  limparObjeto(respostas)
  limparObjeto(erros)
  erroEnvio.value = null
  telaFinal.value = null
  enviadas.value = {}
  indicacao.value = null
  depoimento.value = null
  forcado.value = null
  finalEmFoco.value = null
  pedidoExemplo++
  etapa.value = 'perguntas'
  anuncio.value = ''
  primeiroPasso()
  const p = principal.value
  const n = props.notaInicial
  if (p && typeof n === 'number') {
    const { min, max } = faixa(p)
    if (Number.isInteger(n) && n >= min && n <= max) {
      respostas[p.id] = n
      // ?nota=: começa no item do caminho depois da nota; havendo obrigatória antes dela, começa pela primeira (com a
      // nota já marcada), para ela não ficar sem resposta.
      const ids = caminhoIds.value
      const ip = ids.indexOf(p.id)
      if (ip >= 0) {
        const obrigatoria = ids.slice(0, ip).find((id) => {
          const q = porId.value.get(id)
          return !!q && respondivel(q.tipo) && q.obrigatoria
        })
        irPara(obrigatoria ?? ids[ip + 1] ?? ids[ip]!)
      }
    }
  }
}

/** Prévia: vai para o item (ou final) em foco; fora do caminho, ele aparece mesmo assim. */
function irParaFoco(id: string | null | undefined) {
  if (!props.previa || !id) return
  cancelarAvanco()
  if (id === FOCO_FINAL_PADRAO || props.finais.some((f) => f.id === id)) {
    finalEmFoco.value = id
    mostrarFinal(telaDoFinal(id === FOCO_FINAL_PADRAO ? null : id), false)
    return
  }
  const item = porId.value.get(id)
  if (!item || item.tipo === 'quebra_pagina') return
  finalEmFoco.value = null
  telaFinal.value = null
  etapa.value = 'perguntas'
  limparObjeto(erros)
  forcado.value = caminhoIds.value.includes(id) ? null : id
  irPara(id)
}

// Os passos mudaram (resposta, ou o editor mexeu nos itens): a tela fica num passo que existe.
watch(passos, (lista, antes) => {
  if (forcado.value && caminhoIds.value.includes(forcado.value)) forcado.value = null
  if (umaPorVez.value) {
    if (atualId.value && lista.includes(atualId.value)) return
    const i = atualId.value && antes ? antes.indexOf(atualId.value) : 0
    atualId.value = lista[Math.min(Math.max(i, 0), lista.length - 1)] ?? null
  } else if (!paginas.value.some((pg) => pg.numero === paginaAtual.value)) {
    const depois = paginas.value.find((pg) => pg.numero > (paginaAtual.value ?? -1)) ?? paginas.value[paginas.value.length - 1]
    paginaAtual.value = depois?.numero ?? null
  }
})
// Fontes separadas: só reinicia quando a nota inicial ou o modo mudam de fato.
watch([() => props.notaInicial, () => tema.value.modo], () => {
  iniciar()
  irParaFoco(props.focoId)
})
watch(() => props.focoId, (id) => irParaFoco(id))

function atualizar(p: Pergunta, valor: ValorResposta | undefined) {
  if (valor === undefined) delete respostas[p.id]
  else respostas[p.id] = valor
  if (erros[p.id]) delete erros[p.id]
}

async function focarTopo(idPergunta?: string) {
  await nextTick()
  // A pergunta antes do título da tela: na primeira pergunta, o título da abertura fica acima dela.
  const alvo = idPergunta
    ? raiz.value?.querySelector<HTMLElement>(`[data-pergunta="${idPergunta}"] [data-titulo-pergunta]`)
    : (raiz.value?.querySelector<HTMLElement>('[data-titulo-pergunta]') ?? raiz.value?.querySelector<HTMLElement>('[data-titulo-tela]'))
  alvo?.focus({ preventScroll: true })
  if (!props.previa) (alvo ?? raiz.value)?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
}

/** O que o leitor de tela ouve ao trocar de passo: "Pergunta N de M"; no conteúdo, o começo do texto. */
function anunciarPasso() {
  if (!umaPorVez.value) {
    anuncio.value = `Página ${indice.value + 1} de ${total.value}`
    return
  }
  const p = atuais.value[0]
  if (p?.tipo === 'conteudo') {
    const texto = textoDoHtml(htmlConteudo(p))
    anuncio.value = texto.length > 160 ? `${texto.slice(0, 160)}…` : texto
  } else {
    anuncio.value = `Pergunta ${numeroPergunta.value} de ${perguntasDoCaminho.value.length}`
  }
}

function validarAtuais(): boolean {
  const e = validarPerguntas(atuais.value, respostas)
  limparObjeto(erros)
  Object.assign(erros, e)
  const primeira = atuais.value.find((p) => e[p.id])
  if (primeira) {
    anuncio.value = e[primeira.id]!
    focarTopo(primeira.id)
    return false
  }
  return true
}

function cancelarAvanco() {
  if (temporizador) clearTimeout(temporizador)
  temporizador = null
}

async function avancar() {
  cancelarAvanco()
  if (enviando.value || !validarAtuais()) return
  if (ultima.value) return enviarTudo()
  if (umaPorVez.value) atualId.value = passos.value[indice.value + 1] ?? atualId.value
  else paginaAtual.value = paginas.value[indice.value + 1]?.numero ?? paginaAtual.value
  anunciarPasso()
  focarTopo()
}

function voltar() {
  cancelarAvanco()
  if (indice.value > 0) {
    if (umaPorVez.value) atualId.value = passos.value[indice.value - 1] ?? atualId.value
    else paginaAtual.value = paginas.value[indice.value - 1]?.numero ?? paginaAtual.value
    limparObjeto(erros)
    focarTopo()
  }
}

function aoEscolher(p: Pergunta) {
  // Avança sozinho ao tocar numa nota (modo uma por vez), menos na última do caminho.
  if (!umaPorVez.value || ultima.value) return
  if (!['nps', 'csat', 'estrelas', 'escala', 'sim_nao'].includes(p.tipo)) return
  cancelarAvanco()
  temporizador = setTimeout(() => {
    temporizador = null
    if (atuais.value[0]?.id === p.id && !validarResposta(p, respostas[p.id])) avancar()
  }, 320)
}

/** Posiciona na pergunta com erro (vindo do servidor). */
function irParaPergunta(id: string) {
  irPara(id)
  etapa.value = 'perguntas'
  focarTopo(id)
}

/** A API pode mandar `respostas.<id>`, `<id>` ou `respostas.<id>.<algo>`. */
function lerCamposServidor(campos: Record<string, string>): Record<string, string> {
  const ids = new Set(itens.value.map((p) => p.id))
  const saida: Record<string, string> = {}
  for (const [chave, msg] of Object.entries(campos)) {
    const partes = chave.split('.')
    const id = partes.find((x) => ids.has(x))
    if (id && !saida[id]) saida[id] = msg
  }
  return saida
}

/** Prévia: a tela final de um final da lista (ou do padrão, com `null`). */
function telaDoFinal(id: string | null): TelaFinal {
  const f = id ? props.finais.find((x) => x.id === id) : null
  if (!f) return { titulo_final: tema.value.titulo_final, texto_final: tema.value.texto_final, final_id: null }
  return {
    titulo_final: f.titulo || tema.value.titulo_final,
    texto_final: '',
    final_id: f.id,
    html_final: f.html ? renderizarVariaveisHtml(f.html, props.variaveis) : null,
    botao_final: f.botao ?? null,
  }
}

async function enviarTudo() {
  // Confere tudo o que está no caminho (no modo páginas a pessoa pode ter voltado e mudado algo).
  const doCaminho = caminhoIds.value.map((id) => porId.value.get(id)!).filter((p) => respondivel(p.tipo))
  const e = validarPerguntas(doCaminho, respostas)
  if (Object.keys(e).length) {
    limparObjeto(erros)
    Object.assign(erros, e)
    irParaPergunta(doCaminho.find((p) => e[p.id])!.id)
    return
  }
  erroEnvio.value = null
  const corpo = respostasParaEnvio(itens.value, respostas)
  if (!props.enviar) {
    enviadas.value = corpo
    mostrarFinal(telaDoFinal(escolherFinal(props.finais, itens.value, respostas)))
    void mostrarIndicacaoExemplo()
    return
  }
  enviando.value = true
  try {
    const r = await props.enviar(corpo)
    if (r === null) return
    enviadas.value = corpo
    indicacao.value = lerConviteIndicacao(r?.indicacao)
    depoimento.value = lerDepoimento(r?.depoimento)
    mostrarFinal({
      titulo_final: r?.titulo_final || tema.value.titulo_final,
      texto_final: r?.texto_final ?? tema.value.texto_final,
      final_id: r?.final_id ?? null,
      html_final: r?.html_final ?? null,
      botao_final: r?.botao_final ?? null,
    })
  } catch (err) {
    const erro = (err ?? {}) as ErroEnvio
    const porPergunta = erro.campos ? lerCamposServidor(erro.campos) : {}
    const primeira = doCaminho.find((p) => porPergunta[p.id])
    if (primeira) {
      limparObjeto(erros)
      Object.assign(erros, porPergunta)
      irParaPergunta(primeira.id)
    } else {
      erroEnvio.value = erro.mensagem || 'Não conseguimos enviar agora. Confira sua internet e tente de novo.'
    }
  } finally {
    enviando.value = false
  }
}

/** Título e HTML da tela final: variáveis, depois citações das respostas enviadas (no HTML, escapadas). */
const valoresEnviados = computed(() => percorrer(itens.value, enviadas.value).valores)
const tituloFinal = computed(() => citarComValores(v(telaFinal.value?.titulo_final), porId.value, valoresEnviados.value))
const htmlFinal = computed(() =>
  telaFinal.value?.html_final ? citarComValores(telaFinal.value.html_final, porId.value, valoresEnviados.value, true) : '',
)
/** O botão do final: só endereço https (o resto não vira link). */
const botaoFinal = computed<BotaoFinal | null>(() => {
  const b = telaFinal.value?.botao_final
  return b && b.texto?.trim() && /^https:\/\//i.test(b.url ?? '') ? b : null
})
/** Prévia, final em foco: quando ele aparece (a faixa); o padrão vale quando nenhum outro vale. */
const faixaFinal = computed(() => {
  if (!props.previa || !finalEmFoco.value || etapa.value !== 'final') return ''
  if (finalEmFoco.value === FOCO_FINAL_PADRAO) return props.finais.length ? 'Este final aparece quando nenhum outro final vale.' : ''
  return props.motivoFoco ? `Este final aparece quando: ${props.motivoFoco}` : ''
})

/** Tela final. Etapa 5h: o leitor de tela anuncia o título dela (antes ficava o "Pergunta N de N" da última troca). */
function mostrarFinal(tela: TelaFinal, focar = true) {
  telaFinal.value = tela
  etapa.value = 'final'
  anuncio.value = tituloFinal.value
  if (focar) focarTopo()
}

/** Pré-visualização: com nota de promotor na pergunta principal, mostra o cartão de indicação de exemplo. */
async function mostrarIndicacaoExemplo() {
  const p = principal.value
  if (!props.indicacaoExemplo || !p || !notaDaDireitoAIndicacao(p.tipo, respostas[p.id])) return
  const meu = ++pedidoExemplo
  try {
    const c = await props.indicacaoExemplo()
    if (meu === pedidoExemplo && etapa.value === 'final') indicacao.value = c
  } catch {
    /* sem o exemplo, a tela final fica como está */
  }
}

/** Reiniciar a prévia: tudo do começo (o foco volta a valer quando o editor selecionar outro item). */
function reiniciar() {
  iniciar()
  focarTopo()
}

// Teclado: 0–9 no NPS (1 e depois 0 rápido = 10); Enter avança.
let digitoPendente: { n: number; ate: number } | null = null
function aoTeclar(e: KeyboardEvent) {
  if (etapa.value !== 'perguntas' || !umaPorVez.value || e.ctrlKey || e.metaKey || e.altKey) return
  const alvo = e.target as HTMLElement | null
  if (alvo && (alvo.tagName === 'TEXTAREA' || alvo.tagName === 'SELECT' || alvo.isContentEditable || (alvo.tagName === 'INPUT' && !['radio', 'checkbox'].includes((alvo as HTMLInputElement).type)))) return
  if (props.previa && raiz.value && !raiz.value.contains(alvo)) return
  const p = atuais.value[0]
  if (!p || p.tipo !== 'nps' || !/^\d$/.test(e.key)) return
  e.preventDefault()
  const n = Number(e.key)
  const agora = Date.now()
  if (n === 0 && digitoPendente?.n === 1 && agora < digitoPendente.ate) {
    digitoPendente = null
    atualizar(p, 10)
  } else {
    digitoPendente = n === 1 ? { n, ate: agora + 700 } : null
    atualizar(p, n)
  }
  anuncio.value = `Nota ${respostas[p.id]}`
  // Espera um pouco para permitir o "10".
  cancelarAvanco()
  if (!ultima.value) {
    temporizador = setTimeout(() => {
      temporizador = null
      avancar()
    }, n === 1 ? 750 : 400)
  }
}

// Já no primeiro desenho: o passo certo (?nota=, foco da prévia) aparece sem esperar a montagem.
iniciar()
irParaFoco(props.focoId)

onMounted(() => {
  document.addEventListener('keydown', aoTeclar)
  // Conteúdo ou final com HTML: o limpador já vem baixando enquanto a pessoa responde.
  const temHtml = itens.value.some((p) => p.tipo === 'conteudo') || props.formulario.tem_finais || props.finais.some((f) => f.html)
  if (temHtml) carregarLimpador().catch(() => {})
})
onBeforeUnmount(() => {
  cancelarAvanco()
  document.removeEventListener('keydown', aoTeclar)
})

defineExpose({ recomecar: iniciar, irParaPergunta })
</script>

<template>
  <!-- @container/pesquisa: a largura de dentro da raiz é a do cartão (a régua de notas muda em menos de 420 px) -->
  <div
    ref="raiz"
    class="pesquisa @container/pesquisa w-full text-slate-900"
    :class="compacto ? '' : 'mx-auto max-w-xl px-4 py-6 sm:py-10'"
    :style="estiloCor"
  >
    <div class="overflow-hidden bg-white" :class="compacto ? '' : 'rounded-2xl border border-slate-200 shadow-sm'">
      <!-- Barra de progresso: posição no caminho (recalculado a cada resposta) -->
      <div
        v-if="umaPorVez && total > 1"
        class="h-1.5 bg-slate-100"
        role="progressbar"
        :aria-valuenow="progresso"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-label="Progresso da pesquisa"
      >
        <div class="h-full bg-[var(--cor)] transition-all duration-300" :style="{ width: `${progresso}%` }" />
      </div>

      <div :class="compacto ? 'p-4 sm:p-6' : 'p-5 sm:p-8'">
        <header v-if="tema.logo_url" class="mb-6 flex">
          <img :src="tema.logo_url" alt="" class="max-h-12 max-w-[60%] object-contain" />
        </header>

        <!-- Final -->
        <section v-if="etapa === 'final'" class="flex flex-col items-center gap-3 py-6 text-center" data-tela-final :data-final="telaFinal?.final_id ?? 'padrao'">
          <p v-if="faixaFinal" class="mb-2 w-full rounded-xl bg-amber-50 px-3.5 py-2.5 text-left text-sm text-amber-900 ring-1 ring-amber-200" data-faixa-foco>
            {{ faixaFinal }}
          </p>
          <span class="flex size-16 items-center justify-center rounded-full bg-[var(--cor-suave)] text-[var(--cor)]" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="size-9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          </span>
          <h1 tabindex="-1" data-titulo-tela class="text-2xl font-extrabold text-slate-900 focus:outline-none">{{ tituloFinal }}</h1>
          <BlocoHtml v-if="htmlFinal" class="w-full max-w-md text-left" :html="htmlFinal" :prefixo-imagens="prefixoImagens" data-html-final />
          <p v-else-if="telaFinal?.texto_final" class="max-w-md whitespace-pre-line text-base text-slate-600">{{ v(telaFinal.texto_final) }}</p>
          <a
            v-if="botaoFinal"
            :href="botaoFinal.url"
            target="_blank"
            rel="noopener noreferrer"
            class="mt-2 inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[var(--cor)] px-6 py-2.5 text-base font-bold text-[var(--cor-texto)] shadow-sm transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
            data-botao-final
          >
            {{ botaoFinal.texto }}
            <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>
            <span class="sr-only">(abre em nova aba)</span>
          </a>
          <CartaoDepoimento v-if="depoimento" class="mt-3" :dados="depoimento" :autorizar="autorizarDepoimento" />
          <CartaoIndicacao v-if="indicacao" class="mt-3" :convite="indicacao" :empresa="variaveis.empresa ?? ''" :enviar="indicar" />
          <button v-if="previa" type="button" class="mt-4 text-sm font-semibold text-slate-600 underline underline-offset-4 hover:text-slate-900" @click="reiniciar">
            Ver de novo
          </button>
        </section>

        <!-- Perguntas -->
        <form v-else novalidate @submit.prevent="avancar">
          <!-- Abertura: no alto da primeira pergunta, na mesma tela (sem a antiga tela "Começar") -->
          <div v-if="mostrarAbertura" class="mb-6 border-b border-slate-100 pb-6" data-abertura>
            <h1 v-if="tituloAbertura" tabindex="-1" data-titulo-tela class="text-2xl font-extrabold leading-tight text-slate-900 focus:outline-none">
              {{ tituloAbertura }}
            </h1>
            <p v-if="textoAbertura" class="whitespace-pre-line text-base text-slate-600" :class="tituloAbertura ? 'mt-2' : ''">{{ textoAbertura }}</p>
          </div>
          <p v-if="!total" class="py-8 text-center text-slate-500">Esta pesquisa ainda não tem perguntas.</p>
          <template v-else>
            <p v-if="umaPorVez && numeroPergunta && perguntasDoCaminho.length > 1" class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500" data-contador>
              Pergunta {{ numeroPergunta }} de {{ perguntasDoCaminho.length }}
            </p>
            <p v-else-if="!umaPorVez && total > 1" class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500" data-contador>
              Página {{ indice + 1 }} de {{ total }}
            </p>
            <div class="flex flex-col gap-8">
              <template v-for="p in atuais" :key="p.id">
                <div v-if="forcado === p.id && previa" class="-mb-4 rounded-xl bg-amber-50 px-3.5 py-2.5 text-sm text-amber-900 ring-1 ring-amber-200" data-faixa-foco>
                  Na pesquisa, este item só aparece quando: {{ motivoFoco || 'a condição dele vale' }}
                </div>
                <!-- Bloco de conteúdo: texto formatado (HTML limpo), sem resposta -->
                <section v-if="p.tipo === 'conteudo'" tabindex="-1" class="focus:outline-none" :data-pergunta="p.id" data-titulo-pergunta data-conteudo>
                  <BlocoHtml :html="htmlConteudo(p)" :prefixo-imagens="prefixoImagens" />
                </section>
                <CampoPergunta
                  v-else
                  :pergunta="p"
                  :model-value="respostas[p.id]"
                  :erro="erros[p.id]"
                  :variaveis="variaveis"
                  :ordem-opcoes="ordemOpcoes(p)"
                  :citar="citarTexto"
                  @update:model-value="(valor) => atualizar(p, valor)"
                  @escolheu="aoEscolher(p)"
                />
              </template>
            </div>

            <div v-if="erroEnvio" role="alert" class="mt-6 rounded-xl border border-red-200 bg-red-50 p-3.5 text-sm text-red-800">
              {{ erroEnvio }}
            </div>

            <div class="mt-8 flex items-center gap-3">
              <button
                v-if="indice > 0"
                type="button"
                class="inline-flex h-12 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-slate-600 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-slate-900"
                :disabled="enviando"
                @click="voltar"
              >
                <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
                Voltar
              </button>
              <button
                type="submit"
                class="ml-auto inline-flex h-12 min-w-32 items-center justify-center gap-2 rounded-xl bg-[var(--cor)] px-6 text-base font-bold text-[var(--cor-texto)] shadow-sm transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:opacity-60"
                :disabled="enviando"
                :aria-busy="enviando || undefined"
                data-avancar
              >
                <svg v-if="enviando" viewBox="0 0 24 24" class="size-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
                <template v-if="erroEnvio && ultima">Tentar de novo</template>
                <template v-else>{{ ultima ? tema.texto_botao || 'Enviar' : 'Continuar' }}</template>
              </button>
            </div>
          </template>
        </form>
      </div>
    </div>
    <!-- Etapa 5i: fora do cartão e longe do botão de enviar; o Referer nunca leva o endereço (tem o token) -->
    <p v-if="formulario.mencao_toqqi" class="text-center text-xs text-slate-600" :class="compacto ? 'mt-3' : 'mt-6'" data-mencao-toqqi>
      <a
        :href="formulario.mencao_toqqi.url"
        target="_blank"
        rel="noopener noreferrer"
        referrerpolicy="no-referrer"
        class="inline-flex min-h-6 items-center rounded hover:underline focus-visible:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
        >{{ formulario.mencao_toqqi.texto }}</a
      >
    </p>
    <p v-if="previa && reiniciavel" class="text-center" :class="compacto ? 'mt-3' : 'mt-4'">
      <button
        type="button"
        class="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 text-xs font-semibold text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline focus-visible:outline-2 focus-visible:outline-slate-500"
        data-reiniciar-previa
        @click="reiniciar"
      >
        <svg viewBox="0 0 24 24" class="size-3.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></svg>
        Reiniciar prévia
      </button>
    </p>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
  </div>
</template>
