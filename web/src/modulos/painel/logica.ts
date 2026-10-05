// Regras puras do Painel (sem Vue): faixas e cores do NPS, números com sinal, meses, primeiros passos (com "ocultar"
// guardado no navegador), as escalas dos gráficos (evolução, medidor, régua, barras divergentes) e a manchete "O que mudou".
import type { FaixaNps, Id, Painel, Permissao, Pico, ResultadoDetratores, TomComentarios } from '@/api/tipos'
import { dataIsoValida, ehPreset, type PresetPeriodo } from '@/utils/periodo'
import type { Tom } from '@/utils/rotulos'

// ── NPS ─────────────────────────────────────────────────────────────────────

export const FAIXAS_NPS: Record<FaixaNps, { rotulo: string; tom: Tom; explicacao: string }> = {
  excelente: { rotulo: 'Excelente', tom: 'sucesso', explicacao: 'NPS de 75 a 100.' },
  muito_bom: { rotulo: 'Muito bom', tom: 'sucesso', explicacao: 'NPS de 50 a 74.' },
  pode_melhorar: { rotulo: 'Pode melhorar', tom: 'atencao', explicacao: 'NPS de 0 a 49.' },
  critico: { rotulo: 'Crítico', tom: 'erro', explicacao: 'NPS abaixo de 0: há mais detratores que promotores.' },
}

/** Faixa pelo valor: ≥ 75 excelente, ≥ 50 muito bom, ≥ 0 pode melhorar, < 0 crítico. */
export function faixaDoNps(valor: number | null | undefined): FaixaNps | null {
  if (typeof valor !== 'number' || !Number.isFinite(valor)) return null
  if (valor >= 75) return 'excelente'
  if (valor >= 50) return 'muito_bom'
  if (valor >= 0) return 'pode_melhorar'
  return 'critico'
}

/** Rótulo e cor da faixa. Usa a faixa que a API mandou; sem ela, calcula pelo valor. */
export function faixaNps(
  faixa: FaixaNps | string | null | undefined,
  valor?: number | null,
): { chave: FaixaNps; rotulo: string; tom: Tom } | null {
  const chave = faixa && Object.hasOwn(FAIXAS_NPS, faixa) ? (faixa as FaixaNps) : faixaDoNps(valor)
  return chave ? { chave, rotulo: FAIXAS_NPS[chave].rotulo, tom: FAIXAS_NPS[chave].tom } : null
}

/** Cor de um NPS: verde ≥ 50, âmbar de 0 a 49, vermelho < 0. */
export function tomNps(valor: number | null | undefined): Tom {
  if (typeof valor !== 'number') return 'neutro'
  return valor >= 50 ? 'sucesso' : valor >= 0 ? 'atencao' : 'erro'
}

/** Nota média (0 a 10): abaixo de 7 vermelho, abaixo de 9 âmbar, 9 ou mais verde (mesmos grupos do NPS). */
export function tomNotaMedia(media: number | string | null | undefined): Tom {
  const n = typeof media === 'string' ? Number(media) : media
  if (typeof n !== 'number' || !Number.isFinite(n)) return 'neutro'
  return n < 7 ? 'erro' : n < 9 ? 'atencao' : 'sucesso'
}

/** CSAT: verde ≥ 80%, âmbar ≥ 60%, vermelho abaixo. */
export function tomCsat(percentual: number | null | undefined): Tom {
  if (typeof percentual !== 'number') return 'neutro'
  return percentual >= 80 ? 'sucesso' : percentual >= 60 ? 'atencao' : 'erro'
}

const MENOS = '−' // sinal de menos tipográfico

/** "45", "−12" ou "—". */
export function formatarNps(v: number | null | undefined, vazio = '—'): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return vazio
  const n = Math.round(v)
  return n < 0 ? `${MENOS}${Math.abs(n)}` : String(n)
}

/** Diferença com sinal: "+8", "−5", "0". */
export function formatarVariacao(v: number): string {
  const n = Math.round(v)
  if (n > 0) return `+${n}`
  if (n < 0) return `${MENOS}${Math.abs(n)}`
  return '0'
}

/** Variação em palavras: "subiu 8 pontos", "caiu 5 pontos", "ficou igual". */
export function descreverVariacao(v: number): string {
  const n = Math.round(v)
  if (n === 0) return 'ficou igual'
  const pontos = Math.abs(n) === 1 ? 'ponto' : 'pontos'
  return n > 0 ? `subiu ${n} ${pontos}` : `caiu ${Math.abs(n)} ${pontos}`
}

const fmtDecimal1 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const fmtDecimal2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** 6,4 (uma casa) ou "—". */
export function formatarMedia1(v: number | string | null | undefined): string {
  const n = typeof v === 'string' ? Number(v) : v
  return typeof n === 'number' && Number.isFinite(n) ? fmtDecimal1.format(n) : '—'
}

/** 4,32 (duas casas) ou "—". */
export function formatarMedia2(v: number | string | null | undefined): string {
  const n = typeof v === 'string' ? Number(v) : v
  return typeof n === 'number' && Number.isFinite(n) ? fmtDecimal2.format(n) : '—'
}

/** Porcentagem com no máximo uma casa: 33,3% / 50%. */
export function formatarPct(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return `${v.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`
}

// ── Meses ───────────────────────────────────────────────────────────────────

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

/** "2026-05" → "mai/26" (curto) ou "maio de 2026" (longo). Texto inválido volta como veio. */
export function formatarMes(mes: string, formato: 'curto' | 'longo' = 'curto'): string {
  const m = /^(\d{4})-(\d{2})$/.exec(mes)
  const i = m ? Number(m[2]) - 1 : -1
  if (!m || i < 0 || i > 11) return mes
  const nome = MESES[i]!
  return formato === 'longo' ? `${nome} de ${m[1]}` : `${nome.slice(0, 3)}/${m[1]!.slice(2)}`
}

/**
 * A API manda só os meses com dados. Para o gráfico mostrar o buraco (e não ligar meses distantes como se
 * fossem vizinhos), completa os meses que faltam entre o primeiro e o último com NPS vazio.
 * Fica em ordem cronológica; meses repetidos ou inválidos são ignorados; no máximo 120 meses.
 */
export function completarMeses<T extends { mes: string; nps: number | null; total: number }>(pontos: T[]): (T | { mes: string; nps: null; total: number })[] {
  const validos = new Map<string, T>()
  for (const p of pontos) if (/^\d{4}-(0[1-9]|1[0-2])$/.test(p.mes) && !validos.has(p.mes)) validos.set(p.mes, p)
  const meses = [...validos.keys()].sort()
  if (meses.length < 2) return meses.map((m) => validos.get(m)!)
  const [a1, m1] = meses[0]!.split('-').map(Number) as [number, number]
  const [a2, m2] = meses[meses.length - 1]!.split('-').map(Number) as [number, number]
  const resultado: (T | { mes: string; nps: null; total: number })[] = []
  for (let a = a1, m = m1; (a < a2 || (a === a2 && m <= m2)) && resultado.length < 120; m === 12 ? ((m = 1), a++) : m++) {
    const chave = `${a}-${String(m).padStart(2, '0')}`
    resultado.push(validos.get(chave) ?? { mes: chave, nps: null, total: 0 })
  }
  return resultado
}

// ── Escala do gráfico de evolução ───────────────────────────────────────────

/**
 * Eixo Y do NPS: passo de 10, 25 ou 50 conforme a amplitude dos dados, limitado a −100…100.
 * Valores todos iguais ganham uma folga de um passo para cima e para baixo.
 */
export function dominioNps(valores: number[]): { min: number; max: number; passo: number; ticks: number[] } {
  const v = valores.filter((x) => Number.isFinite(x))
  if (!v.length) return { min: 0, max: 100, passo: 50, ticks: [0, 50, 100] }
  const menor = Math.min(...v)
  const maior = Math.max(...v)
  const amplitude = maior - menor
  const passo = amplitude <= 40 ? 10 : amplitude <= 100 ? 25 : 50
  let min = Math.floor(menor / passo) * passo
  let max = Math.ceil(maior / passo) * passo
  if (min === max) {
    min -= passo
    max += passo
  }
  if (min < -100) min = -100
  if (max > 100) max = 100
  if (min === max) min = max - passo
  const ticks: number[] = []
  for (let t = min; t <= max + 1e-9; t += passo) ticks.push(Math.round(t))
  return { min, max, passo, ticks }
}

/** Converte um valor do domínio para a posição na tela (linear). */
export function escala(dominio: [number, number], faixa: [number, number]): (v: number) => number {
  const [d0, d1] = dominio
  const [f0, f1] = faixa
  const span = d1 - d0 || 1
  return (v: number) => f0 + ((v - d0) / span) * (f1 - f0)
}

// ── Primeiros passos ────────────────────────────────────────────────────────

export type ChavePasso = keyof Painel['primeiros_passos']

export interface PassoInicial {
  chave: ChavePasso
  titulo: string
  descricao: string
  feito: boolean
  /** Para onde levar quem ainda não fez (só se o perfil puder abrir). */
  para?: string
  acao?: string
  /** "Próximo: …" da linha de primeiros passos. */
  proximo: string
}

/** Os 4 passos reais vindos da API, com o atalho certo para o perfil de quem vê. */
export function montarPassos(pp: Partial<Painel['primeiros_passos']> | null | undefined, pode: (p: Permissao) => boolean): PassoInicial[] {
  const feito = (k: ChavePasso) => !!pp?.[k]
  return [
    {
      chave: 'contatos',
      proximo: 'traga sua lista de clientes de uma planilha ou cadastre um por um.',
      titulo: 'Cadastrar seus clientes',
      descricao: 'Traga sua lista de uma planilha ou cadastre um por um.',
      feito: feito('contatos'),
      ...(pode('importacao.usar')
        ? { para: '/contatos/importar', acao: 'Importar planilha' }
        : pode('contatos.ver')
          ? { para: '/contatos', acao: 'Ir para Contatos' }
          : {}),
    },
    {
      chave: 'envios_ligados',
      proximo: 'ligue os envios para as pesquisas saírem sozinhas.',
      titulo: 'Ligar os envios',
      descricao: 'Confira o texto do convite e ligue o envio das pesquisas.',
      feito: feito('envios_ligados'),
      ...(pode('envios.ver') ? { para: '/configuracoes/envios', acao: 'Configurar os envios' } : {}),
    },
    {
      chave: 'primeiro_envio',
      proximo: 'mande a primeira pesquisa por e-mail ou WhatsApp.',
      titulo: 'Enviar a primeira pesquisa',
      descricao: 'Mande por e-mail ou WhatsApp para alguns clientes.',
      feito: feito('primeiro_envio'),
      ...(pode('envios.ver') ? { para: '/envios', acao: 'Ir para Envios' } : {}),
    },
    {
      chave: 'primeira_resposta',
      proximo: 'quando alguém responder, a nota e o comentário aparecem aqui.',
      titulo: 'Receber a primeira resposta',
      descricao: 'Quando alguém responder, a nota e o comentário aparecem aqui.',
      feito: feito('primeira_resposta'),
      ...(pode('respostas.ver') ? { para: '/respostas', acao: 'Ver respostas' } : {}),
    },
  ]
}

const PREFIXO_PASSOS = 'toqqi.painel.passos-ocultos'

export function chavePassosOcultos(contaId: string | number | null | undefined): string {
  return `${PREFIXO_PASSOS}.${contaId ?? 'conta'}`
}

/** A pessoa escondeu "Primeiros passos" neste navegador? Sem armazenamento disponível, mostra. */
export function passosOcultos(contaId: string | number | null | undefined): boolean {
  try {
    return window.localStorage.getItem(chavePassosOcultos(contaId)) === '1'
  } catch {
    return false
  }
}

/** Guarda (ou desfaz) a escolha de esconder. Devolve false se o navegador não deixou guardar. */
export function ocultarPassos(contaId: string | number | null | undefined, ocultar = true): boolean {
  try {
    if (ocultar) window.localStorage.setItem(chavePassosOcultos(contaId), '1')
    else window.localStorage.removeItem(chavePassosOcultos(contaId))
    return true
  } catch {
    return false
  }
}

/** Mostra o bloco enquanto falta algum passo e a pessoa não escondeu. */
export function mostrarPassos(passos: PassoInicial[], ocultos: boolean): boolean {
  return !ocultos && passos.some((p) => !p.feito)
}

// ── Picos de reclamação (etapa 4b) ──────────────────────────────────────────

const fmtMediaPico = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })

/** A média anterior do pico vale ser escrita? Abaixo de 0,05 ela apareceria como "0" (dizemos que não havia nenhuma). */
function temMediaPico(media: number): boolean {
  return Number.isFinite(media) && media >= 0.05
}

/** As duas partes do aviso de pico: "Pico de reclamações em Prazo e entrega" e "7 nos últimos 7 dias; a média era 1,5 por semana". */
export function partesPico(p: Pick<Pico, 'rotulo' | 'reclamacoes' | 'media_anterior'>): { titulo: string; detalhe: string } {
  const media = Number(p.media_anterior)
  const antes = temMediaPico(media) ? `a média era ${fmtMediaPico.format(media)} por semana` : 'antes, não havia nenhuma'
  return { titulo: `Pico de reclamações em ${p.rotulo}`, detalhe: `${p.reclamacoes} nos últimos 7 dias; ${antes}` }
}

/** "Pico de reclamações em Prazo e entrega: 7 nos últimos 7 dias; a média era 1,5 por semana". */
export function textoPico(p: Pick<Pico, 'rotulo' | 'reclamacoes' | 'media_anterior'>): string {
  const { titulo, detalhe } = partesPico(p)
  return `${titulo}: ${detalhe}`
}

/** Respostas do pico: as reclamações do tema nos 7 dias, de empresas ativas (como no e-mail de alerta). */
export function consultaPico(p: Pick<Pico, 'tema' | 'de' | 'ate'>): Record<string, string> {
  return { tema: p.tema, reclamacao: 'true', so_ativos: 'true', ...(p.de ? { de: p.de } : {}), ...(p.ate ? { ate: p.ate } : {}) }
}

/** Variação das menções de um tema contra o período anterior: "+3", "−2", "0" e a frase para leitor de tela. */
export function variacaoMencoes(v: number | null | undefined): { texto: string; direcao: 'sobe' | 'desce' | 'igual'; descricao: string } | null {
  if (typeof v !== 'number' || !Number.isFinite(v)) return null
  const n = Math.round(v)
  const qtd = Math.abs(n) === 1 ? 'menção' : 'menções'
  if (n > 0) return { texto: formatarVariacao(n), direcao: 'sobe', descricao: `${n} ${qtd} a mais que no período anterior` }
  if (n < 0) return { texto: formatarVariacao(n), direcao: 'desce', descricao: `${Math.abs(n)} ${qtd} a menos que no período anterior` }
  return { texto: '0', direcao: 'igual', descricao: 'o mesmo número de menções do período anterior' }
}

// ── Painel v2 (docs/painel-v2.md) ───────────────────────────────────────────

const DIAS_SEMANA = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

/** "2026-10-02" → "Sexta, 2 de outubro" (data de calendário, sem fuso). Texto inválido volta vazio. */
export function dataPorExtenso(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return ''
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  if (Number.isNaN(d.getTime()) || d.getUTCMonth() !== Number(m[2]) - 1) return ''
  return `${DIAS_SEMANA[d.getUTCDay()]}, ${d.getUTCDate()} de ${MESES[d.getUTCMonth()]}`
}

/** Dias de um intervalo AAAA-MM-DD, contando o primeiro e o último (null se faltar data ou estiver trocado). */
export function diasNoIntervalo(de: string | null | undefined, ate: string | null | undefined): number | null {
  if (!de || !ate) return null
  const a = Date.parse(`${de}T00:00:00Z`)
  const b = Date.parse(`${ate}T00:00:00Z`)
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return null
  return Math.round((b - a) / 86_400_000) + 1
}

/** Título do medidor: "NPS dos últimos 90 dias", "NPS dos últimos 12 meses", "NPS de todo o período", "NPS · De 01/07/2026 a …". */
export function tituloNps(preset: string, rotulo: string): string {
  if (preset === '365') return 'NPS dos últimos 12 meses'
  if (preset === 'tudo') return 'NPS de todo o período'
  if (/^\d+$/.test(preset)) return `NPS dos últimos ${preset} dias`
  return rotulo ? `NPS · ${rotulo}` : 'NPS'
}

const fmtCurto = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
const fmtInteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })

/** Moeda curta: "R$ 850", "R$ 48 mil", "R$ 265,2 mil", "R$ 1,2 mi". Aceita texto decimal ("1250.00"). */
export function formatarMoedaCurta(v: number | string | null | undefined, vazio = '—'): string {
  const n = typeof v === 'string' ? Number(v) : v
  if (typeof n !== 'number' || !Number.isFinite(n)) return vazio
  const sinal = n < 0 ? MENOS : ''
  const a = Math.abs(n)
  // Arredonda antes de comparar: 999,6 vira "R$ 1 mil" (e não "R$ 1.000"); 999.950 vira "R$ 1 mi".
  if (Math.round(a) < 1000) return `${sinal}R$ ${fmtInteiro.format(Math.round(a))}`
  const mil = Math.round((a / 1000) * 10) / 10
  if (mil < 1000) return `${sinal}R$ ${fmtCurto.format(mil)} mil`
  return `${sinal}R$ ${fmtCurto.format(Math.round((a / 1_000_000) * 10) / 10)} mi`
}

function numero(v: number | string | null | undefined): number {
  const n = typeof v === 'string' ? Number(v) : v
  return typeof n === 'number' && Number.isFinite(n) ? n : 0
}

function pontos(n: number): string {
  return n === 1 ? 'ponto' : 'pontos'
}

// ── Medidor semicircular e régua (escala −100 a 100) ────────────────────────

/** Ponto do arco do medidor para um NPS: −100 à esquerda, 0 no topo, 100 à direita (limitado à escala). */
export function pontoNoArco(valor: number, cx: number, cy: number, r: number): { x: number; y: number } {
  const v = Math.min(100, Math.max(-100, Number.isFinite(valor) ? valor : 0))
  const angulo = Math.PI * (1 - (v + 100) / 200)
  return { x: Math.round((cx + r * Math.cos(angulo)) * 100) / 100, y: Math.round((cy - r * Math.sin(angulo)) * 100) / 100 }
}

/** Caminho SVG do trecho do arco entre dois valores (no sentido horário, da esquerda para a direita). */
export function arcoNps(de: number, ate: number, cx: number, cy: number, r: number): string {
  const a = pontoNoArco(de, cx, cy, r)
  const b = pontoNoArco(ate, cx, cy, r)
  return `M${a.x},${a.y} A${r},${r} 0 0 1 ${b.x},${b.y}`
}

/** As três faixas do medidor: detrator (< 0), neutro (0 a 49), promotor (≥ 50). */
export const FAIXAS_MEDIDOR = [
  { de: -100, ate: 0, cor: 'stroke-grafico-detrator' },
  { de: 0, ate: 50, cor: 'stroke-grafico-neutro' },
  { de: 50, ate: 100, cor: 'stroke-grafico-promotor' },
] as const

/** Régua −100 a 100 com o zero no meio: a barra vai do zero até o valor (em % da largura). */
export function reguaNps(valor: number | null | undefined): { inicio: number; largura: number; sinal: 'negativo' | 'zero' | 'positivo' } {
  const v = typeof valor === 'number' && Number.isFinite(valor) ? Math.min(100, Math.max(-100, valor)) : 0
  if (v < 0) return { inicio: 50 + v / 2, largura: -v / 2, sinal: 'negativo' }
  if (v > 0) return { inicio: 50, largura: v / 2, sinal: 'positivo' }
  return { inicio: 50, largura: 0, sinal: 'zero' }
}

// ── Evolução de 12 meses ────────────────────────────────────────────────────

/** Menor e maior mês com NPS (empate: o mais recente). Sem dois valores diferentes, não marca nenhum. */
export function extremosSerie(serie: { nps: number | null }[]): { menor: number | null; maior: number | null } {
  let menor: number | null = null
  let maior: number | null = null
  serie.forEach((p, i) => {
    if (typeof p.nps !== 'number') return
    if (menor === null || p.nps <= (serie[menor]!.nps as number)) menor = i
    if (maior === null || p.nps >= (serie[maior]!.nps as number)) maior = i
  })
  if (menor === null || maior === null || serie[menor]!.nps === serie[maior]!.nps) return { menor: null, maior: null }
  return { menor, maior }
}

// ── Temas: barras divergentes ───────────────────────────────────────────────

export interface BarraTema {
  chave: string
  rotulo: string
  mencoes: number
  reclamacoes: number
  outras: number
  /** Frações da escala comum (0 a 1): reclamações à esquerda, demais menções à direita. */
  esquerda: number
  direita: number
}

/** Reclamações à esquerda, demais menções à direita, na mesma escala (o maior lado de todos os temas = 1). */
export function barrasDivergentes(temas: Pick<Painel['temas'][number], 'chave' | 'rotulo' | 'mencoes' | 'reclamacoes'>[]): BarraTema[] {
  const linhas = temas.map((t) => {
    const mencoes = Math.max(0, numero(t.mencoes))
    const reclamacoes = Math.min(mencoes, Math.max(0, numero(t.reclamacoes)))
    return { chave: t.chave, rotulo: t.rotulo, mencoes, reclamacoes, outras: mencoes - reclamacoes }
  })
  const maior = Math.max(1, ...linhas.map((l) => Math.max(l.reclamacoes, l.outras)))
  return linhas.map((l) => ({ ...l, esquerda: l.reclamacoes / maior, direita: l.outras / maior }))
}

/** Frase do tema para leitor de tela: "Prazo e entrega: 13 menções, 8 reclamações, nota média 6,2, 9 menções a mais que no período anterior". */
export function descreverTema(t: Pick<Painel['temas'][number], 'rotulo' | 'mencoes' | 'reclamacoes' | 'nota_media' | 'variacao'>): string {
  const partes = [`${t.mencoes} ${t.mencoes === 1 ? 'menção' : 'menções'}`]
  if (typeof t.reclamacoes === 'number') partes.push(`${t.reclamacoes} ${t.reclamacoes === 1 ? 'reclamação' : 'reclamações'}`)
  if (t.nota_media !== null && t.nota_media !== undefined) partes.push(`nota média ${formatarMedia1(t.nota_media)}`)
  const v = variacaoMencoes(t.variacao)
  if (v) partes.push(v.descricao)
  return `${t.rotulo}: ${partes.join(', ')}`
}

// ── Tom dos comentários ─────────────────────────────────────────────────────

export type ParteTom = 'negativo' | 'misto' | 'neutro' | 'positivo'

export const PARTES_TOM: { chave: ParteTom; rotulo: string; cor: string }[] = [
  { chave: 'negativo', rotulo: 'Negativo', cor: 'bg-grafico-detrator' },
  { chave: 'misto', rotulo: 'Misto', cor: 'bg-grafico-neutro' },
  { chave: 'neutro', rotulo: 'Neutro', cor: 'bg-grafico-cinza' },
  { chave: 'positivo', rotulo: 'Positivo', cor: 'bg-grafico-promotor' },
]

export interface ResumoTom {
  analisados: number
  /** % de negativos entre os analisados (inteiro). */
  pctNegativo: number
  /** % no período anterior (null sem anterior ou sem análises nele). */
  pctNegativoAnterior: number | null
  /** Diferença em pontos percentuais (null sem anterior). */
  variacao: number | null
  partes: { chave: ParteTom; rotulo: string; cor: string; qtd: number; fracao: number }[]
  comComentario: number
  totalRespostas: number
  /** % das respostas com comentário (null sem respostas). */
  pctComentario: number | null
}

export function resumoTom(tom: TomComentarios | null | undefined): ResumoTom | null {
  if (!tom || typeof tom !== 'object') return null
  const qtd = (k: ParteTom) => Math.max(0, numero(tom[k]))
  const soma = PARTES_TOM.reduce((a, p) => a + qtd(p.chave), 0)
  const analisados = Math.max(numero(tom.analisados), soma)
  const pct = (a: number, b: number) => Math.round((a / b) * 100)
  const pctNegativo = analisados ? pct(qtd('negativo'), analisados) : 0
  const ant = tom.anterior
  const pctNegativoAnterior = ant && numero(ant.analisados) > 0 ? pct(Math.max(0, numero(ant.negativo)), numero(ant.analisados)) : null
  const comComentario = Math.max(0, numero(tom.com_comentario))
  const totalRespostas = Math.max(0, numero(tom.total_respostas))
  return {
    analisados,
    pctNegativo,
    pctNegativoAnterior,
    variacao: pctNegativoAnterior === null || !analisados ? null : pctNegativo - pctNegativoAnterior,
    partes: PARTES_TOM.map((p) => ({ ...p, qtd: qtd(p.chave), fracao: soma ? qtd(p.chave) / soma : 0 })),
    comComentario,
    totalRespostas,
    pctComentario: totalRespostas ? pct(comComentario, totalRespostas) : null,
  }
}

export type EstadoTom = 'dados' | 'sem_comentarios' | 'analisando' | 'nao_lidos' | 'curtos' | 'ligar'

/**
 * O que o bloco mostra, só pelo que o painel devolveu para os filtros: os números ('dados'); sem comentários no período
 * ('sem_comentarios'); nada analisado mas comentários na fila da IA ('analisando', `pendentes` > 0); ou nada analisado
 * nem na fila. Aí, etapa 5h: com a IA ligada (`ia_ligada`), 'nao_lidos' quando há comentários que a IA ainda não leu
 * (`sem_analise` > 0: "Analisar agora") ou 'curtos' quando os que há são curtos demais para ela; desligada (ou servidor
 * sem o campo), 'ligar'.
 */
export function estadoTom(
  tom: Pick<TomComentarios, 'analisados' | 'com_comentario'> & {
    pendentes?: number | null
    ia_ligada?: boolean | null
    sem_analise?: number | null
  },
): EstadoTom {
  if (numero(tom.analisados) > 0) return 'dados'
  if (numero(tom.com_comentario) <= 0) return 'sem_comentarios'
  if (numero(tom.pendentes) > 0) return 'analisando'
  if (tom.ia_ligada === true) return numero(tom.sem_analise) > 0 ? 'nao_lidos' : 'curtos'
  return 'ligar'
}

// ── Nuvem de palavras ───────────────────────────────────────────────────────

export interface PalavraNuvem {
  palavra: string
  total: number
  /** 4 = a mais citada; 1 = as menos citadas. */
  nivel: 1 | 2 | 3 | 4
  /** Classe da cor: pelo tom da palavra quando a API diz; senão, pelo tamanho. */
  cor: string
}

/** Tamanho pela contagem (em relação à mais citada) e cor pelo tom, sem inventar tom que a API não mandou. */
export function nuvemPalavras(palavras: Painel['palavras'], limite = 20): PalavraNuvem[] {
  const validas = (palavras ?? []).filter((p) => p && typeof p.palavra === 'string' && p.palavra.trim() && numero(p.total) > 0).slice(0, limite)
  const maior = Math.max(1, ...validas.map((p) => numero(p.total)))
  return validas.map((p) => {
    const r = numero(p.total) / maior
    const nivel = (r >= 0.75 ? 4 : r >= 0.5 ? 3 : r >= 0.25 ? 2 : 1) as PalavraNuvem['nivel']
    const cor =
      p.tom === 'negativo' ? 'text-marca-texto' : p.tom === 'positivo' ? 'text-sucesso' : p.tom === 'neutro' ? 'text-texto-suave' : nivel >= 3 ? 'text-texto' : 'text-texto-suave'
    return { palavra: p.palavra, total: numero(p.total), nivel, cor }
  })
}

// ── Manchete "O que mudou" (§3) ─────────────────────────────────────────────

export interface ParteTexto {
  texto: string
  /** 'alerta': o pico (vermelho e negrito); 'forte': o valor em risco (negrito). */
  enfase?: 'alerta' | 'forte'
}

export interface EntradaManchete {
  nps: Pick<Painel['nps'], 'total' | 'detratores'>
  variacao: Painel['variacao']
  /** Tamanho do período anterior, em dias ("em relação aos 90 dias antes"); null se não se sabe. */
  diasAnteriores: number | null
  picos: Pico[] | null | undefined
  /**
   * Os picos da API são sempre da conta inteira nos últimos 7 dias: só entram na manchete quando valem para os filtros
   * (o período termina hoje e não há grupo filtrado; veja `picosValemParaFiltros`). Sem o campo, valem.
   */
  picosValem?: boolean
  atencao: Pick<Painel['atencao'], 'acoes_abertas' | 'acoes_vencidas'> & {
    receita_em_risco: Pick<Painel['atencao']['receita_em_risco'], 'valor' | 'empresas'>
    /** Etapa 5h: empresas com detrator e sem plano aberto (o botão "Criar planos"). */
    detratores_sem_plano?: number | null
  }
}

export interface Manchete {
  regra: 1 | 2 | 3 | 4 | 5
  titulo: ParteTexto[]
  apoio: ParteTexto[] | null
  /** O pico da manchete (regra 1). */
  pico: Pico | null
  /** Os outros temas com pico (além do da manchete). */
  outrosPicos: string[]
}

const LIMIAR_VARIACAO = 5

function antes(dias: number | null): string {
  return dias ? `aos ${fmtNumeroInt(dias)} ${dias === 1 ? 'dia' : 'dias'} antes` : 'ao período anterior'
}
function fmtNumeroInt(n: number): string {
  return fmtInteiro.format(n)
}

/**
 * Os picos (conta inteira, últimos 7 dias) valem para o painel filtrado? Só quando o período termina hoje (ou não tem
 * fim, como "Todo o período") e não há grupo filtrado.
 */
export function picosValemParaFiltros(f: { ate?: string | null; grupo_id: Id | '' | null | undefined }, hoje: string): boolean {
  return (!f.ate || f.ate >= hoje) && (f.grupo_id === '' || f.grupo_id === null || f.grupo_id === undefined)
}

/** O pico com mais reclamações (empate: o primeiro da lista). */
function picoPrincipal(picos: Pico[] | null | undefined): Pico | null {
  let melhor: Pico | null = null
  for (const p of picos ?? []) if (!melhor || p.reclamacoes > melhor.reclamacoes) melhor = p
  return melhor
}

/** As regras na ordem de prioridade; cada uma devolve o texto ou null se não vale. */
function regras(e: EntradaManchete): ((comQueda: boolean) => ParteTexto[] | null)[] {
  const v = e.variacao ? Math.round(e.variacao.valor) : null
  const caiu = v !== null && v <= -LIMIAR_VARIACAO
  const subiu = v !== null && v >= LIMIAR_VARIACAO
  const pico = e.picosValem === false ? null : picoPrincipal(e.picos)
  const receita = numero(e.atencao?.receita_em_risco?.valor)
  const empresas = numero(e.atencao?.receita_em_risco?.empresas)
  const abertas = numero(e.atencao?.acoes_abertas)
  const vencidas = numero(e.atencao?.acoes_vencidas)
  return [
    // 1. Pico de reclamações (com a queda do NPS antes, se houver).
    () => {
      if (!pico) return null
      const media = Number(pico.media_anterior)
      const depois =
        temMediaPico(media) ? `, quando a média era ${fmtMediaPico.format(media)} por semana.` : ', quando antes não havia nenhuma.'
      return [
        ...(caiu ? [{ texto: `O NPS caiu ${Math.abs(v!)} ${pontos(Math.abs(v!))}. ` }] : []),
        { texto: `${pico.reclamacoes} ${pico.reclamacoes === 1 ? 'reclamação' : 'reclamações'} de ${pico.rotulo}`, enfase: 'alerta' as const },
        { texto: ` em 7 dias${depois}` },
      ]
    },
    // 2. Queda (não repete a queda que já está na manchete do pico).
    (comQueda) => (caiu && !comQueda ? [{ texto: `O NPS caiu ${Math.abs(v!)} ${pontos(Math.abs(v!))} em relação ${antes(e.diasAnteriores)}.` }] : null),
    // 3. Alta.
    () => (subiu ? [{ texto: `O NPS subiu ${v} ${pontos(v!)} em relação ${antes(e.diasAnteriores)}.` }] : null),
    // 4. Receita em risco.
    () => {
      if (!(receita > 0) || empresas <= 0) return null
      const quem = empresas === 1 ? '1 empresa teve' : `${fmtNumeroInt(empresas)} empresas tiveram`
      const planos =
        abertas === 0
          ? empresas === 1
            ? ' Ela não tem plano de ação aberto.'
            : ' Nenhuma tem plano de ação aberto.'
          : ` ${abertas === 1 ? '1 plano aberto' : `${fmtNumeroInt(abertas)} planos abertos`}, ${
              vencidas === 0 ? 'nenhum vencido' : vencidas === 1 ? '1 vencido' : `${fmtNumeroInt(vencidas)} vencidos`
            }.`
      return [
        { texto: `${quem} detrator no período, somando ` },
        { texto: `${formatarMoedaCurta(receita)} por mês`, enfase: 'forte' as const },
        { texto: ` em contrato.${planos}` },
      ]
    },
    // 5. Nada disso.
    () => {
      if (v !== null) return [{ texto: v === 0 ? 'Tudo estável: o NPS ficou igual.' : `Tudo estável: o NPS variou ${formatarVariacao(v)} ${pontos(Math.abs(v))}.` }]
      const total = numero(e.nps?.total)
      return [{ texto: total ? `${fmtNumeroInt(total)} ${total === 1 ? 'resposta' : 'respostas'} de NPS no período.` : 'Nenhuma resposta de NPS no período.' }]
    },
  ]
}

/** A manchete (a primeira regra que vale) e a linha de apoio (a seguinte que vale, sem o "tudo estável"). */
export function montarManchete(e: EntradaManchete): Manchete {
  const lista = regras(e)
  const v = e.variacao ? Math.round(e.variacao.valor) : null
  let regra = 5
  let titulo: ParteTexto[] = []
  for (let i = 0; i < lista.length; i++) {
    const t = lista[i]!(false)
    if (t) {
      regra = i + 1
      titulo = t
      break
    }
  }
  // A queda já dita junto do pico não volta na linha de apoio.
  const quedaNaManchete = regra === 1 && v !== null && v <= -LIMIAR_VARIACAO
  let apoio: ParteTexto[] | null = null
  for (let i = regra; i < 4 && !apoio; i++) apoio = lista[i]!(quedaNaManchete)
  const pico = regra === 1 ? picoPrincipal(e.picos) : null  // regra 1 só vale com picosValem
  return {
    regra: regra as Manchete['regra'],
    titulo,
    apoio,
    pico,
    outrosPicos: pico ? (e.picos ?? []).filter((p) => p !== pico).map((p) => p.rotulo) : [],
  }
}

export interface AcaoManchete {
  /** 'criar_planos' (etapa 5h): chama POST /acoes/detratores; os outros levam a uma tela ou abrem o ToqqiAI. */
  tipo: 'pico' | 'criar_planos' | 'detratores' | 'planos' | 'toqqiai'
  rotulo: string
  para?: { path: string; query?: Record<string, string> }
}

/** Pergunta que o botão do ToqqiAI deixa na caixa do chat. */
export const PERGUNTA_TOQQIAI = 'O que explica a variação do NPS no período?'

/**
 * Até 3 botões da manchete: as reclamações do pico; "Criar planos para N empresas" (etapa 5h: empresas com detrator
 * e sem plano aberto, para quem trata planos de ação); os detratores (sem plano aberto) ou os planos; e o ToqqiAI.
 * Cada um só para quem pode abrir o destino.
 */
export function acoesManchete(
  e: EntradaManchete,
  m: Pick<Manchete, 'pico'>,
  o: { podeVerRespostas: boolean; podeVerAcoes: boolean; toqqiAI: boolean; consultaNps: Record<string, string>; podeTratarAcoes?: boolean },
): AcaoManchete[] {
  const acoes: AcaoManchete[] = []
  if (m.pico && o.podeVerRespostas) {
    const n = m.pico.reclamacoes
    acoes.push({ tipo: 'pico', rotulo: n === 1 ? 'Ver a reclamação' : `Ver as ${fmtNumeroInt(n)} reclamações`, para: { path: '/respostas', query: consultaPico(m.pico) } })
  }
  const semPlano = numero(e.atencao?.detratores_sem_plano)
  if (semPlano > 0 && o.podeTratarAcoes) acoes.push({ tipo: 'criar_planos', rotulo: rotuloCriarPlanos(semPlano) })
  const comDetrator = numero(e.nps?.detratores) > 0 || numero(e.atencao?.receita_em_risco?.empresas) > 0
  const abertas = numero(e.atencao?.acoes_abertas)
  const vencidas = numero(e.atencao?.acoes_vencidas)
  if (comDetrator && abertas === 0 && o.podeVerRespostas) {
    acoes.push({ tipo: 'detratores', rotulo: 'Ver os detratores', para: { path: '/respostas', query: { ...o.consultaNps, categoria: 'detrator' } } })
  } else if (comDetrator && abertas > 0 && o.podeVerAcoes) {
    acoes.push(
      vencidas > 0
        ? { tipo: 'planos', rotulo: vencidas === 1 ? 'Ver o plano vencido' : `Ver os ${fmtNumeroInt(vencidas)} planos vencidos`, para: { path: '/planos-de-acao', query: { so_vencidas: 'true' } } }
        : { tipo: 'planos', rotulo: 'Ver os planos de ação', para: { path: '/planos-de-acao' } },
    )
  }
  if (o.toqqiAI) acoes.push({ tipo: 'toqqiai', rotulo: 'Perguntar ao ToqqiAI' })
  return acoes.slice(0, 3)
}

/** Etapa 5h (tom): "12 comentários ainda não foram lidos pela IA." */
export function textoNaoLidos(n: number): string {
  return n === 1 ? '1 comentário ainda não foi lido pela IA.' : `${fmtNumeroInt(n)} comentários ainda não foram lidos pela IA.`
}

/** Etapa 5h: "Criar planos para 4 empresas" / "Criar planos para 1 empresa". */
export function rotuloCriarPlanos(n: number): string {
  return `Criar planos para ${n === 1 ? '1 empresa' : `${fmtNumeroInt(n)} empresas`}`
}

/** Etapa 5h: o aviso depois de criar, "4 planos criados." (e quantos ficaram para a próxima, se passou de 100). */
export function textoPlanosCriados(r: Pick<ResultadoDetratores, 'criadas' | 'restantes'>): string {
  if (!r.criadas) return 'Nenhum plano novo: as empresas com detrator já têm plano aberto.'
  const criados = r.criadas === 1 ? '1 plano criado.' : `${fmtNumeroInt(r.criadas)} planos criados.`
  if (!r.restantes) return criados
  const faltam = r.restantes === 1 ? 'Falta 1 empresa' : `Faltam ${fmtNumeroInt(r.restantes)} empresas`
  return `${criados} ${faltam}: use o botão de novo para criar os próximos.`
}

/** Texto corrido de partes (para leitor de tela e testes). */
export function textoDasPartes(partes: ParteTexto[] | null | undefined): string {
  return (partes ?? []).map((p) => p.texto).join('')
}

// ── Filtros no endereço (/inicio?periodo=30&grupo_id=2&so_ativos=false) ─────

export interface FiltrosTela {
  periodo: PresetPeriodo
  de: string
  ate: string
  grupo_id: Id | ''
  so_ativos: boolean
}

export const FILTROS_PADRAO: FiltrosTela = { periodo: '90', de: '', ate: '', grupo_id: '', so_ativos: true }

type ValorConsulta = string | null | (string | null)[] | undefined

function primeiro(v: ValorConsulta): string {
  const x = Array.isArray(v) ? v[0] : v
  return typeof x === 'string' ? x : ''
}

/**
 * Lê os filtros do endereço; o que for inválido fica no padrão (90 dias, todos os grupos, só ativas). "Escolher as
 * datas" só vale com as duas datas válidas e na ordem; senão, volta aos 90 dias (a tela nunca abre sem o que buscar).
 */
export function filtrosDaConsulta(q: Record<string, ValorConsulta>): FiltrosTela {
  const periodo = primeiro(q.periodo)
  const f: FiltrosTela = { ...FILTROS_PADRAO, periodo: ehPreset(periodo) ? periodo : FILTROS_PADRAO.periodo }
  if (f.periodo === 'personalizado') {
    const de = primeiro(q.de)
    const ate = primeiro(q.ate)
    if (dataIsoValida(de) && dataIsoValida(ate) && de <= ate) {
      f.de = de
      f.ate = ate
    } else f.periodo = FILTROS_PADRAO.periodo
  }
  const grupo = primeiro(q.grupo_id)
  if (/^\d+$/.test(grupo)) f.grupo_id = Number(grupo)
  if (primeiro(q.so_ativos) === 'false') f.so_ativos = false
  return f
}

/** O inverso: só o que difere do padrão vai para o endereço (o padrão fica com o endereço limpo). */
export function consultaDosFiltros(f: FiltrosTela): Record<string, string> {
  const q: Record<string, string> = {}
  if (f.periodo !== FILTROS_PADRAO.periodo) q.periodo = f.periodo
  if (f.periodo === 'personalizado') {
    if (f.de) q.de = f.de
    if (f.ate) q.ate = f.ate
  }
  if (f.grupo_id !== '') q.grupo_id = String(f.grupo_id)
  if (!f.so_ativos) q.so_ativos = 'false'
  return q
}

/** Quanto da carteira está em risco, em % inteiro ("48"); null sem carteira ou sem valor em risco. */
export function pctCarteira(valor: number | string | null | undefined, carteira: number | string | null | undefined): number | null {
  const v = numero(valor)
  const c = numero(carteira)
  if (!(c > 0) || !(v > 0)) return null
  const p = Math.round((v / c) * 100)
  return p === 0 ? 1 : Math.min(100, p)
}

/** "Igual aos 90 dias antes" / "Igual ao período anterior" (a partir de `textoPeriodoAnterior`). */
export function igualAo(textoAnterior: string): string {
  if (textoAnterior.startsWith('os ')) return `Igual aos ${textoAnterior.slice(3)}`
  if (textoAnterior.startsWith('o ')) return `Igual ao ${textoAnterior.slice(2)}`
  return `Igual a ${textoAnterior}`
}

/** Título da evolução: "NPS nos últimos 12 meses" ou, se o último mês não é o atual, "NPS em 12 meses até março de 2026". */
export function tituloEvolucao12m(ultimoMes: string | null | undefined, hoje: string): string {
  if (!ultimoMes || ultimoMes === hoje.slice(0, 7)) return 'NPS nos últimos 12 meses'
  return `NPS em 12 meses até ${formatarMes(ultimoMes, 'longo')}`
}

/** "os 90 dias antes" (com o tamanho do período anterior) ou "o período anterior". */
export function textoPeriodoAnterior(anterior: { de: string; ate: string } | null | undefined): string {
  const dias = diasNoIntervalo(anterior?.de, anterior?.ate)
  return dias ? `os ${fmtNumeroInt(dias)} ${dias === 1 ? 'dia' : 'dias'} antes` : 'o período anterior'
}
