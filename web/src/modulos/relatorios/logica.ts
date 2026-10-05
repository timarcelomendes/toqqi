// Regras puras dos Relatórios (sem Vue): abas, filtros ↔ endereço (os comuns e os de cada aba), o que vai para a API,
// quadrantes da matriz NPS × valor, faixas de valor e de tempo como cliente, escalas e dados dos gráficos.
import type {
  DimensaoEntrega,
  FaixaValor,
  FiltrosRelatorio,
  FiltrosRelatorioEmpresas,
  FiltrosRelatorioEntregas,
  FiltrosRelatorioGrupos,
  Id,
  OrdemEmpresas,
  OrdemEntregas,
  Quadrante,
  SemanaTemas,
  TempoCliente,
  ValorDecimal,
} from '@/api/tipos'
import { FUSO, formatarData, formatarDiaMes, hojeIso } from '@/utils/datas'
import { dataIsoValida, ehPreset, intervaloDoPeriodo, type PresetPeriodo } from '@/utils/periodo'
import type { Tom } from '@/utils/rotulos'

// ── Abas ────────────────────────────────────────────────────────────────────

export type AbaRelatorio = 'empresas' | 'grupos' | 'temas' | 'entregas' | 'responsaveis' | 'operacao' | 'desfecho' | 'historico'

export const ABAS_RELATORIO: { valor: AbaRelatorio; rotulo: string; descricao: string }[] = [
  { valor: 'empresas', rotulo: 'Empresas', descricao: 'NPS, cobertura e receita em risco de cada empresa, com a matriz NPS × valor.' },
  { valor: 'grupos', rotulo: 'Grupos de clientes', descricao: 'NPS por segmento, grupo, tempo como cliente e valor do contrato, e o que resolver primeiro.' },
  { valor: 'temas', rotulo: 'Temas', descricao: 'Do que os clientes falam, as reclamações e os elogios, semana a semana.' },
  { valor: 'entregas', rotulo: 'Entregas', descricao: 'NPS, CSAT e reclamações por motorista, rota, filial e transportadora.' },
  { valor: 'responsaveis', rotulo: 'Responsáveis', descricao: 'A carteira de cada responsável: NPS, receita em risco e ações.' },
  { valor: 'operacao', rotulo: 'Operação', descricao: 'Taxa de resposta, convites por canal, ações concluídas e quem ainda não respondeu.' },
  { valor: 'desfecho', rotulo: 'Desfecho', descricao: 'Quem saiu, por quê, o que dizia antes de sair e quanto da receita ficou.' },
  { valor: 'historico', rotulo: 'Histórico de uma empresa', descricao: 'Tudo o que uma empresa respondeu, mês a mês, com as ações.' },
]

export const ABA_PADRAO: AbaRelatorio = 'empresas'

export function ehAba(v: unknown): v is AbaRelatorio {
  return typeof v === 'string' && ABAS_RELATORIO.some((a) => a.valor === v)
}

export function rotuloAba(aba: AbaRelatorio): string {
  return ABAS_RELATORIO.find((a) => a.valor === aba)?.rotulo ?? aba
}

// ── Rótulos ─────────────────────────────────────────────────────────────────

export const FAIXAS_VALOR: { valor: FaixaValor; rotulo: string }[] = [
  { valor: 'ate_2k', rotulo: 'Menos de R$ 2 mil' },
  { valor: '2k_10k', rotulo: 'R$ 2 mil a 10 mil' },
  { valor: '10k_50k', rotulo: 'R$ 10 mil a 50 mil' },
  { valor: 'acima_50k', rotulo: 'R$ 50 mil ou mais' },
  { valor: 'sem_valor', rotulo: 'Sem valor' },
]

export const FAIXAS_TEMPO: { valor: TempoCliente; rotulo: string }[] = [
  { valor: 'ate_3m', rotulo: 'Até 3 meses' },
  { valor: '3_6m', rotulo: '3 a 6 meses' },
  { valor: '6_12m', rotulo: '6 a 12 meses' },
  { valor: 'mais_1a', rotulo: 'Mais de 1 ano' },
  { valor: 'sem_data', rotulo: 'Sem data de início' },
]

export const DIMENSOES: { valor: DimensaoEntrega; rotulo: string; plural: string }[] = [
  { valor: 'motorista', rotulo: 'Motorista', plural: 'motoristas' },
  { valor: 'rota', rotulo: 'Rota', plural: 'rotas' },
  { valor: 'filial', rotulo: 'Filial', plural: 'filiais' },
  { valor: 'transportadora', rotulo: 'Transportadora', plural: 'transportadoras' },
]

export function rotuloDimensao(d: DimensaoEntrega): string {
  return DIMENSOES.find((x) => x.valor === d)?.rotulo ?? d
}

export const ORDENS_EMPRESAS: { valor: OrdemEmpresas; rotulo: string }[] = [
  { valor: 'prioridade', rotulo: 'Em risco primeiro' },
  { valor: 'nps', rotulo: 'Menor NPS' },
  { valor: 'valor', rotulo: 'Maior valor' },
  { valor: 'cobertura', rotulo: 'Menor cobertura' },
  { valor: 'respostas', rotulo: 'Mais respostas' },
  { valor: 'nome', rotulo: 'Nome (A a Z)' },
]

export const ORDENS_ENTREGAS: { valor: OrdemEntregas; rotulo: string }[] = [
  { valor: 'respostas', rotulo: 'Mais respostas' },
  { valor: 'nps', rotulo: 'Menor NPS' },
  { valor: 'csat', rotulo: 'Menor CSAT' },
  { valor: 'reclamacoes', rotulo: 'Mais reclamações' },
  { valor: 'valor', rotulo: 'Nome (A a Z)' },
]

// ── Quadrantes da matriz NPS × valor ────────────────────────────────────────

export const ORDEM_QUADRANTES: Quadrante[] = ['proteger', 'manter', 'corrigir', 'crescer']

/**
 * Os 4 quadrantes. A cor reforça o que a posição já diz (valor acima ou abaixo da mediana, NPS abaixo de 0 ou não):
 * o nome do quadrante está sempre escrito no gráfico e na contagem.
 */
export const QUADRANTES: Record<Quadrante, { rotulo: string; descricao: string; tom: Tom; ponto: string; fundo: string }> = {
  proteger: {
    rotulo: 'Proteger já',
    descricao: 'Valor acima da mediana e NPS negativo: receita grande em risco.',
    tom: 'erro',
    ponto: 'fill-grafico-detrator',
    fundo: 'bg-grafico-detrator',
  },
  manter: {
    rotulo: 'Manter de perto',
    descricao: 'Valor acima da mediana e NPS de 0 para cima.',
    tom: 'sucesso',
    ponto: 'fill-grafico-promotor',
    fundo: 'bg-grafico-promotor',
  },
  corrigir: {
    rotulo: 'Corrigir',
    descricao: 'Valor abaixo da mediana e NPS negativo.',
    tom: 'atencao',
    ponto: 'fill-grafico-neutro',
    fundo: 'bg-grafico-neutro',
  },
  crescer: {
    rotulo: 'Pode crescer',
    descricao: 'Valor abaixo da mediana e NPS de 0 para cima: espaço para vender mais.',
    tom: 'info',
    ponto: 'fill-grafico-serie',
    fundo: 'bg-grafico-serie',
  },
}

export function ehQuadrante(v: unknown): v is Quadrante {
  return typeof v === 'string' && Object.hasOwn(QUADRANTES, v)
}

// ── Números da API ──────────────────────────────────────────────────────────

/** Decimal da API (número ou texto "1250.00") → número; vazio ou inválido → null. */
export function numero(v: ValorDecimal | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

/** Meses completos de `desde` até `hoje` (AAAA-MM-DD), como o age() do banco; negativo se `desde` é futura. */
export function mesesCompletos(desde: string, hoje: string): number {
  const [a1, m1, d1] = desde.split('-').map(Number) as [number, number, number]
  const [a2, m2, d2] = hoje.split('-').map(Number) as [number, number, number]
  const meses = (a2 - a1) * 12 + (m2 - m1)
  return d2 < d1 ? meses - 1 : meses
}

const fmtCurto = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
const fmtInteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })

/** Dinheiro em pouco espaço: "R$ 850", "R$ 2,5 mil", "R$ 1,2 mi". */
export function formatarMoedaCurta(v: ValorDecimal | null | undefined, vazio = '—'): string {
  const n = numero(v)
  if (n === null) return vazio
  const abs = Math.abs(n)
  const sinal = n < 0 ? '−' : ''
  if (abs >= 1_000_000) return `${sinal}R$ ${fmtCurto.format(abs / 1_000_000)} mi`
  if (abs >= 1_000) return `${sinal}R$ ${fmtCurto.format(abs / 1_000)} mil`
  return `${sinal}R$ ${fmtInteiro.format(abs)}`
}

/** As partes do valor curto, para o número grande dos cartões: "572,7" e "mil" (o "R$" fica pequeno, antes). */
export function partesMoedaCurta(v: ValorDecimal | null | undefined): { numero: string; sufixo: '' | 'mil' | 'mi'; negativo: boolean } | null {
  const n = numero(v)
  if (n === null) return null
  const abs = Math.abs(n)
  const negativo = n < 0
  if (abs >= 1_000_000) return { numero: fmtCurto.format(abs / 1_000_000), sufixo: 'mi', negativo }
  if (abs >= 1_000) return { numero: fmtCurto.format(abs / 1_000), sufixo: 'mil', negativo }
  return { numero: fmtInteiro.format(abs), sufixo: '', negativo }
}

// ── Filtros ↔ endereço ──────────────────────────────────────────────────────

/** A API aceita buscas de até 100 caracteres. */
export const LIMITE_BUSCA = 100
export const POR_PAGINA = 50

export interface FiltrosRelatorioTela {
  // Comuns (valem para todas as abas; o histórico usa só o período)
  periodo: PresetPeriodo
  de: string
  ate: string
  grupo_id: Id | ''
  /** Só empresas ativas (padrão ligado). */
  so_ativos: boolean
  // Empresas e grupos de clientes
  segmento_id: Id | ''
  /** Só empresas: 0 = sem responsável. */
  responsavel_id: Id | ''
  faixa_valor: FaixaValor | ''
  tempo_cliente: TempoCliente | ''
  // Empresas e entregas
  busca: string
  respostas: 'com' | 'sem' | ''
  quadrante: Quadrante | ''
  ordem: string
  pagina: number
  // Entregas
  dimensao: DimensaoEntrega
  // Histórico
  empresa_id: Id | ''
}

type Campo = keyof FiltrosRelatorioTela

/** Os filtros próprios de cada aba (os outros não entram no endereço dela). */
export const CAMPOS_DA_ABA: Record<AbaRelatorio, Campo[]> = {
  empresas: ['segmento_id', 'responsavel_id', 'faixa_valor', 'tempo_cliente', 'busca', 'respostas', 'quadrante', 'ordem', 'pagina'],
  grupos: ['segmento_id', 'faixa_valor', 'tempo_cliente'],
  temas: [],
  entregas: ['dimensao', 'busca', 'ordem', 'pagina'],
  responsaveis: [],
  operacao: [],
  desfecho: [],
  historico: ['empresa_id'],
}

/** Período padrão: 90 dias; no Desfecho, 12 meses; no histórico de uma empresa, todo o período. */
export function periodoPadrao(aba: AbaRelatorio): PresetPeriodo {
  return aba === 'historico' ? 'tudo' : aba === 'desfecho' ? '365' : '90'
}

export function ordemPadrao(aba: AbaRelatorio): string {
  return aba === 'entregas' ? 'respostas' : aba === 'empresas' ? 'prioridade' : ''
}

export function filtrosPadrao(aba: AbaRelatorio): FiltrosRelatorioTela {
  return {
    periodo: periodoPadrao(aba),
    de: '',
    ate: '',
    grupo_id: '',
    so_ativos: true,
    segmento_id: '',
    responsavel_id: '',
    faixa_valor: '',
    tempo_cliente: '',
    busca: '',
    respostas: '',
    quadrante: '',
    ordem: ordemPadrao(aba),
    pagina: 1,
    dimensao: 'motorista',
    empresa_id: '',
  }
}

/** Mesmo formato do `route.query` do Vue Router. */
export type Consulta = Record<string, string | null | (string | null)[] | undefined>

function um(q: Consulta, k: string): string {
  const v = q[k]
  const s = Array.isArray(v) ? v[0] : v
  return typeof s === 'string' ? s.trim() : ''
}

/** Identificador vindo do endereço: texto curto, sem espaços (0 = "sem segmento"/"sem responsável"). */
function id(v: string): Id | '' {
  return /^[\w-]{1,40}$/.test(v) ? v : ''
}

function validaOrdem(aba: AbaRelatorio, v: string): string {
  const lista = aba === 'empresas' ? ORDENS_EMPRESAS : aba === 'entregas' ? ORDENS_ENTREGAS : []
  return lista.some((o) => o.valor === v) ? v : ordemPadrao(aba)
}

/** Lê os filtros do endereço para a aba, ignorando o que não vale (e os filtros das outras abas). */
export function filtrosDaQuery(aba: AbaRelatorio, q: Consulta): FiltrosRelatorioTela {
  const f = filtrosPadrao(aba)
  const de = um(q, 'de')
  const ate = um(q, 'ate')
  const temData = dataIsoValida(de) || dataIsoValida(ate)
  const periodo = um(q, 'periodo')
  f.periodo = temData ? 'personalizado' : ehPreset(periodo) ? periodo : periodoPadrao(aba)
  f.de = dataIsoValida(de) ? de : ''
  f.ate = dataIsoValida(ate) ? ate : ''
  f.grupo_id = id(um(q, 'grupo_id'))
  f.so_ativos = um(q, 'so_ativos') !== 'false'
  const campos = CAMPOS_DA_ABA[aba]
  if (campos.includes('segmento_id')) f.segmento_id = id(um(q, 'segmento_id'))
  if (campos.includes('responsavel_id')) f.responsavel_id = id(um(q, 'responsavel_id'))
  if (campos.includes('faixa_valor')) {
    const v = um(q, 'faixa_valor')
    f.faixa_valor = FAIXAS_VALOR.some((x) => x.valor === v) ? (v as FaixaValor) : ''
  }
  if (campos.includes('tempo_cliente')) {
    const v = um(q, 'tempo_cliente')
    f.tempo_cliente = FAIXAS_TEMPO.some((x) => x.valor === v) ? (v as TempoCliente) : ''
  }
  if (campos.includes('busca')) f.busca = um(q, 'busca').slice(0, LIMITE_BUSCA)
  if (campos.includes('respostas')) {
    const v = um(q, 'respostas')
    f.respostas = v === 'com' || v === 'sem' ? v : ''
  }
  if (campos.includes('quadrante')) {
    const v = um(q, 'quadrante')
    f.quadrante = ehQuadrante(v) ? v : ''
  }
  if (campos.includes('ordem')) f.ordem = validaOrdem(aba, um(q, 'ordem'))
  if (campos.includes('pagina')) {
    const p = Number.parseInt(um(q, 'pagina'), 10)
    f.pagina = Number.isFinite(p) && p > 1 ? p : 1
  }
  if (campos.includes('dimensao')) {
    const v = um(q, 'dimensao')
    f.dimensao = DIMENSOES.some((d) => d.valor === v) ? (v as DimensaoEntrega) : 'motorista'
  }
  if (campos.includes('empresa_id')) f.empresa_id = id(um(q, 'empresa_id'))
  return f
}

/** Escreve no endereço só o que foge do padrão da aba (endereço curto e fácil de compartilhar). */
export function queryDosFiltros(aba: AbaRelatorio, f: FiltrosRelatorioTela): Record<string, string> {
  const q: Record<string, string> = {}
  const padrao = filtrosPadrao(aba)
  if (f.periodo === 'personalizado') {
    if (dataIsoValida(f.de)) q.de = f.de
    if (dataIsoValida(f.ate)) q.ate = f.ate
    if (!q.de && !q.ate) q.periodo = 'personalizado'
  } else if (f.periodo !== padrao.periodo) q.periodo = f.periodo
  if (f.grupo_id !== '') q.grupo_id = String(f.grupo_id)
  if (!f.so_ativos) q.so_ativos = 'false'
  for (const c of CAMPOS_DA_ABA[aba]) {
    const v = f[c]
    if (c === 'pagina') {
      if (f.pagina > 1) q.pagina = String(f.pagina)
    } else if (c === 'busca') {
      if (f.busca.trim()) q.busca = f.busca.trim().slice(0, LIMITE_BUSCA)
    } else if (v !== '' && v !== padrao[c]) q[c] = String(v)
  }
  return q
}

/** Os mesmos filtros (como ficam no endereço da aba). */
export function mesmosFiltros(aba: AbaRelatorio, a: FiltrosRelatorioTela, b: FiltrosRelatorioTela): boolean {
  return JSON.stringify(queryDosFiltros(aba, a)) === JSON.stringify(queryDosFiltros(aba, b))
}

/** Mesma busca, ignorando a página: serve para voltar à página 1 quando um filtro muda. */
export function mesmaBusca(aba: AbaRelatorio, a: FiltrosRelatorioTela, b: FiltrosRelatorioTela): boolean {
  return mesmosFiltros(aba, { ...a, pagina: 1 }, { ...b, pagina: 1 })
}

/**
 * Endereço de outra aba, levando os filtros comuns. O período só vai junto se a pessoa escolheu um (no padrão da aba
 * de origem, a aba nova usa o padrão dela: o histórico abre com todo o período). `extra` = filtros da aba nova.
 */
export function consultaDaAba(
  para: AbaRelatorio,
  deAba: AbaRelatorio,
  f: FiltrosRelatorioTela,
  extra: Partial<FiltrosRelatorioTela> = {},
): Record<string, string> {
  const escolhido = f.periodo !== periodoPadrao(deAba)
  const base: FiltrosRelatorioTela = {
    ...filtrosPadrao(para),
    periodo: escolhido ? f.periodo : periodoPadrao(para),
    de: escolhido ? f.de : '',
    ate: escolhido ? f.ate : '',
    grupo_id: f.grupo_id,
    so_ativos: f.so_ativos,
    ...extra,
  }
  return queryDosFiltros(para, base)
}

/** Quantos filtros próprios da aba estão ligados (os que ficam na área "Filtros"). */
export function contarFiltrosDaAba(aba: AbaRelatorio, f: FiltrosRelatorioTela): number {
  const campos = CAMPOS_DA_ABA[aba].filter((c) => ['segmento_id', 'responsavel_id', 'faixa_valor', 'tempo_cliente', 'respostas', 'quadrante'].includes(c))
  return campos.filter((c) => f[c] !== '').length
}

// ── O que vai para a API ────────────────────────────────────────────────────

/** Filtros comuns: o período em datas de São Paulo, o grupo e "só ativas" (sempre explícito: o padrão da API é true). */
export function comunsParaApi(f: FiltrosRelatorioTela, hoje: string = hojeIso()): FiltrosRelatorio {
  const r: FiltrosRelatorio = { ...intervaloDoPeriodo(f.periodo, { de: f.de, ate: f.ate }, hoje), so_ativos: f.so_ativos }
  if (f.grupo_id !== '') r.grupo_id = f.grupo_id
  return r
}

export function empresasParaApi(f: FiltrosRelatorioTela, hoje: string = hojeIso()): FiltrosRelatorioEmpresas {
  const r: FiltrosRelatorioEmpresas = { ...comunsParaApi(f, hoje), ordem: (f.ordem || 'prioridade') as OrdemEmpresas, pagina: f.pagina, por_pagina: POR_PAGINA }
  if (f.segmento_id !== '') r.segmento_id = f.segmento_id
  if (f.responsavel_id !== '') r.responsavel_id = f.responsavel_id
  if (f.faixa_valor) r.faixa_valor = f.faixa_valor
  if (f.tempo_cliente) r.tempo_cliente = f.tempo_cliente
  if (f.busca.trim()) r.busca = f.busca.trim().slice(0, LIMITE_BUSCA)
  if (f.respostas) r.respostas = f.respostas
  if (f.quadrante) r.quadrante = f.quadrante
  return r
}

/** Etapa 5i: Relatórios › Desfecho (os filtros de empresa; as perdidas são inativas, então sem "só ativas"). */
export function desfechoParaApi(f: FiltrosRelatorioTela, hoje: string = hojeIso()): FiltrosRelatorioGrupos & { responsavel_id?: Id } {
  const { so_ativos: _ignorado, ...r }: FiltrosRelatorioGrupos & { responsavel_id?: Id } = gruposParaApi(f, hoje)
  if (f.responsavel_id !== '') r.responsavel_id = f.responsavel_id
  return r
}

export function gruposParaApi(f: FiltrosRelatorioTela, hoje: string = hojeIso()): FiltrosRelatorioGrupos {
  const r: FiltrosRelatorioGrupos = comunsParaApi(f, hoje)
  if (f.segmento_id !== '') r.segmento_id = f.segmento_id
  if (f.faixa_valor) r.faixa_valor = f.faixa_valor
  if (f.tempo_cliente) r.tempo_cliente = f.tempo_cliente
  return r
}

export function entregasParaApi(f: FiltrosRelatorioTela, hoje: string = hojeIso()): FiltrosRelatorioEntregas {
  const r: FiltrosRelatorioEntregas = {
    ...comunsParaApi(f, hoje),
    dimensao: f.dimensao,
    ordem: (f.ordem || 'respostas') as OrdemEntregas,
    pagina: f.pagina,
    por_pagina: POR_PAGINA,
  }
  if (f.busca.trim()) r.busca = f.busca.trim().slice(0, LIMITE_BUSCA)
  return r
}

/** O histórico de uma empresa usa só o período. */
export function periodoParaApi(f: FiltrosRelatorioTela, hoje: string = hojeIso()): { de?: string; ate?: string } {
  return intervaloDoPeriodo(f.periodo, { de: f.de, ate: f.ate }, hoje)
}

/**
 * Os mesmos filtros na tela Respostas (para os links): as datas, o grupo e "só empresas ativas" (lá o padrão é
 * desligado, então vai explícito quando ligado aqui).
 */
export function consultaRespostas(f: FiltrosRelatorioTela, hoje: string = hojeIso()): Record<string, string> {
  const { de, ate } = intervaloDoPeriodo(f.periodo, { de: f.de, ate: f.ate }, hoje)
  const q: Record<string, string> = {}
  if (de) q.de = de
  if (ate) q.ate = ate
  if (f.grupo_id !== '') q.grupo_id = String(f.grupo_id)
  if (f.so_ativos) q.so_ativos = 'true'
  return q
}

// ── Escala logarítmica (valor do contrato na matriz) ────────────────────────

const PASSOS_125 = [1, 2, 5]

function passoAbaixo(v: number): number {
  const base = 10 ** Math.floor(Math.log10(v))
  for (const p of [...PASSOS_125].reverse()) if (p * base <= v * (1 + 1e-9)) return p * base
  return base
}

function passoAcima(v: number): number {
  const base = 10 ** Math.floor(Math.log10(v))
  for (const p of [...PASSOS_125, 10]) if (p * base >= v * (1 - 1e-9)) return p * base
  return 10 * base
}

function passosEntre(lo: number, hi: number): number[] {
  const r: number[] = []
  for (let k = Math.floor(Math.log10(lo)); k <= Math.ceil(Math.log10(hi)); k++) {
    for (const p of PASSOS_125) {
      const v = p * 10 ** k
      if (v >= lo * (1 - 1e-9) && v <= hi * (1 + 1e-9)) r.push(Math.round(v * 1e6) / 1e6)
    }
  }
  return r
}

/**
 * Escala logarítmica de um eixo de valores (reais): começa e termina em 1, 2 ou 5 × 10ⁿ em volta dos dados.
 * Valores ≤ 0 ficam na borda esquerda. `pos` devolve a posição de 0 a 1. Com muitos rótulos, só as potências de 10.
 */
export function escalaLog(valores: number[]): { min: number; max: number; ticks: number[]; pos: (v: number) => number } {
  const positivos = valores.filter((v) => Number.isFinite(v) && v > 0)
  let min = positivos.length ? passoAbaixo(Math.min(...positivos)) : 1000
  let max = positivos.length ? passoAcima(Math.max(...positivos)) : 100_000
  if (min >= max) {
    min = passoAbaixo(min * 0.99)
    max = passoAcima(max * 1.01)
  }
  let ticks = passosEntre(min, max)
  if (ticks.length > 6) {
    const potencias = ticks.filter((t) => Math.abs(Math.log10(t) - Math.round(Math.log10(t))) < 1e-9)
    ticks = potencias.length >= 2 ? potencias : [min, max]
  }
  const l0 = Math.log10(min)
  const l1 = Math.log10(max)
  const pos = (v: number) => {
    const c = Math.min(Math.max(v > 0 ? v : min, min), max)
    return (Math.log10(c) - l0) / (l1 - l0 || 1)
  }
  return { min, max, ticks, pos }
}

/** Eixo de contagens (0 até um pouco acima do máximo): passos de 1, 2, 5, 10, 20, 50… com 3 a 5 marcas. */
export function escalaContagem(maximo: number): { max: number; ticks: number[] } {
  const m = Math.max(0, Math.ceil(maximo))
  if (m <= 4) {
    const max = Math.max(1, m)
    return { max, ticks: Array.from({ length: max + 1 }, (_, i) => i) }
  }
  let passo = 1
  for (const base of [1, 10, 100, 1000, 10000, 100000]) {
    const achado = [1, 2, 5].map((p) => p * base).find((p) => m / p <= 5)
    if (achado) {
      passo = achado
      break
    }
  }
  const max = Math.ceil(m / passo) * passo
  const ticks: number[] = []
  for (let t = 0; t <= max; t += passo) ticks.push(t)
  return { max, ticks }
}

// ── Temas: cores, séries por semana e sentimento ────────────────────────────

/** Cor fixa de cada tema (segue o tema, nunca a posição na lista): traço, fundo de legenda e preenchimento. */
const CORES_TEMA: Record<string, { traco: string; fundo: string; preenchimento: string }> = {
  prazo_entrega: { traco: 'stroke-grafico-tema-1', fundo: 'bg-grafico-tema-1', preenchimento: 'fill-grafico-tema-1' },
  produto_avarias: { traco: 'stroke-grafico-tema-2', fundo: 'bg-grafico-tema-2', preenchimento: 'fill-grafico-tema-2' },
  atendimento: { traco: 'stroke-grafico-tema-3', fundo: 'bg-grafico-tema-3', preenchimento: 'fill-grafico-tema-3' },
  preco_condicoes: { traco: 'stroke-grafico-tema-4', fundo: 'bg-grafico-tema-4', preenchimento: 'fill-grafico-tema-4' },
  comunicacao: { traco: 'stroke-grafico-tema-5', fundo: 'bg-grafico-tema-5', preenchimento: 'fill-grafico-tema-5' },
  sistema_pedidos: { traco: 'stroke-grafico-tema-6', fundo: 'bg-grafico-tema-6', preenchimento: 'fill-grafico-tema-6' },
}
const COR_OUTRO = { traco: 'stroke-texto-fraco', fundo: 'bg-texto-fraco', preenchimento: 'fill-texto-fraco' }

export function corDoTema(chave: string): { traco: string; fundo: string; preenchimento: string } {
  return CORES_TEMA[chave] ?? COR_OUTRO
}

export type MedidaTema = 'mencoes' | 'reclamacoes'

/** Uma série por tema (na ordem dada), com o valor de cada semana e o total do período mostrado. */
export function seriesSemanais(semanas: SemanaTemas[], medida: MedidaTema, temas: readonly string[]): { tema: string; valores: number[]; total: number }[] {
  return temas.map((tema) => {
    const valores = semanas.map((s) => Math.max(0, s.temas?.[tema]?.[medida] ?? 0))
    return { tema, valores, total: valores.reduce((a, b) => a + b, 0) }
  })
}

/** "15/09 a 21/09". */
export function rotuloSemana(s: { inicio: string; fim: string }): string {
  return `${formatarDiaMes(s.inicio, '?')} a ${formatarDiaMes(s.fim, '?')}`
}

export type ParteSentimento = 'positivo' | 'neutro' | 'misto' | 'negativo'

/**
 * Partes da barra de sentimento: positivo, neutro, misto (só quando há algum) e negativo, cada uma com a fração entre
 * as respostas analisadas pela IA. "Sem análise" fica fora da barra (a tela mostra a quantidade em texto).
 */
export function partesSentimento(s: Partial<Record<ParteSentimento, number>>): { chave: ParteSentimento; qtd: number; fracao: number }[] {
  const qtd = (k: ParteSentimento) => Math.max(0, s[k] ?? 0)
  const chaves: ParteSentimento[] = qtd('misto') > 0 ? ['positivo', 'neutro', 'misto', 'negativo'] : ['positivo', 'neutro', 'negativo']
  const total = chaves.reduce((a, k) => a + qtd(k), 0)
  return chaves.map((chave) => ({ chave, qtd: qtd(chave), fracao: total ? qtd(chave) / total : 0 }))
}

// ── Nomes ao lado dos pontos (gráfico "O que resolver primeiro") ────────────

export interface PontoRotulado {
  x: number
  y: number
  texto: string
}

export interface PosicaoRotulo {
  x: number
  y: number
  ancora: 'start' | 'end' | 'middle'
}

interface Caixa {
  x0: number
  x1: number
  y0: number
  y1: number
}

/**
 * Onde escrever o nome de cada ponto sem cobrir os outros nomes nem os pontos: à direita; não cabendo, à esquerda, uma
 * linha abaixo ou acima de cada lado, ou centrado acima ou abaixo (o primeiro lugar livre dentro da área). A largura do
 * texto é estimada pelo número de letras. Sem lugar livre, fica no primeiro que cabe na área.
 */
export function posicionarRotulos(
  pontos: PontoRotulado[],
  area: { esq: number; dir: number; topo: number; base: number },
  larguraLetra = 6.6,
): PosicaoRotulo[] {
  const ocupados: Caixa[] = pontos.map((p) => ({ x0: p.x - 7, x1: p.x + 7, y0: p.y - 7, y1: p.y + 7 }))
  const dentro = (b: Caixa) => b.x0 >= area.esq && b.x1 <= area.dir && b.y0 >= area.topo && b.y1 <= area.base
  const livre = (b: Caixa) => !ocupados.some((o) => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0)
  return pontos.map((p) => {
    const w = p.texto.length * larguraLetra
    const lado = (ancora: 'start' | 'end', dy: number): PosicaoRotulo & { caixa: Caixa } => {
      const x = ancora === 'start' ? p.x + 10 : p.x - 10
      const x0 = ancora === 'start' ? x : x - w
      return { x, y: p.y + 4 + dy, ancora, caixa: { x0, x1: x0 + w, y0: p.y - 7 + dy, y1: p.y + 7 + dy } }
    }
    // Centrado acima ou abaixo, empurrado para dentro da área se passar da borda.
    const centro = Math.min(Math.max(p.x, area.esq + w / 2), Math.max(area.esq + w / 2, area.dir - w / 2))
    const meio = (dy: number, y0: number): PosicaoRotulo & { caixa: Caixa } => ({
      x: centro,
      y: p.y + dy,
      ancora: 'middle',
      caixa: { x0: centro - w / 2, x1: centro + w / 2, y0: p.y + y0, y1: p.y + y0 + 14 },
    })
    const candidatos = [lado('start', 0), lado('end', 0), lado('start', 14), lado('start', -14), lado('end', 14), lado('end', -14), meio(-12, -23), meio(21, 9)]
    const escolhido = candidatos.find((c) => dentro(c.caixa) && livre(c.caixa)) ?? candidatos.find((c) => dentro(c.caixa)) ?? candidatos[0]!
    ocupados.push(escolhido.caixa)
    return { x: escolhido.x, y: escolhido.y, ancora: escolhido.ancora }
  })
}

// ── Histórico de uma empresa ────────────────────────────────────────────────

/** Tempo como cliente em palavras: "8 meses", "1 ano e 3 meses", "menos de 1 mês"; data futura: "a partir de 10/12/2026". */
export function descreverTempoCliente(desde: string | null | undefined, hoje: string = hojeIso()): string | null {
  if (!desde || !dataIsoValida(desde.slice(0, 10))) return null
  const dia = desde.slice(0, 10)
  if (dia > hoje) return `a partir de ${formatarData(dia)}`
  const meses = mesesCompletos(dia, hoje)
  if (meses < 1) return 'menos de 1 mês'
  if (meses < 12) return `${meses} ${meses === 1 ? 'mês' : 'meses'}`
  const anos = Math.floor(meses / 12)
  const resto = meses % 12
  const parteAnos = `${anos} ${anos === 1 ? 'ano' : 'anos'}`
  return resto ? `${parteAnos} e ${resto} ${resto === 1 ? 'mês' : 'meses'}` : parteAnos
}

const fmtMesSp = new Intl.DateTimeFormat('en-CA', { timeZone: FUSO, year: 'numeric', month: '2-digit' })

/** Mês (AAAA-MM) de uma data ou data e hora, no horário de Brasília; inválida → "". */
export function mesDaData(valor: string | null | undefined): string {
  if (!valor) return ''
  const d = /^\d{4}-\d{2}-\d{2}$/.test(valor) ? new Date(`${valor}T12:00:00-03:00`) : new Date(valor)
  return Number.isNaN(d.getTime()) ? '' : fmtMesSp.format(d).slice(0, 7)
}

/** A linha do tempo em blocos por mês, na ordem em que veio (a API manda a mais recente primeiro). */
export function agruparPorMes<T extends { data: string }>(itens: readonly T[]): { mes: string; itens: T[] }[] {
  const grupos: { mes: string; itens: T[] }[] = []
  for (const x of itens) {
    const mes = mesDaData(x.data)
    const ultimo = grupos[grupos.length - 1]
    if (ultimo && ultimo.mes === mes) ultimo.itens.push(x)
    else grupos.push({ mes, itens: [x] })
  }
  return grupos
}

/** Cargo e perfil do contato vêm como nome (o contrato não fixa; aceitamos também {id, nome}). */
export function nomeDoCampo(v: string | { nome?: string | null } | null | undefined): string {
  if (!v) return ''
  return (typeof v === 'string' ? v : (v.nome ?? '')).trim()
}
