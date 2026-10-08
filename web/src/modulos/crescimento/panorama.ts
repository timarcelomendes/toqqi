// Regras puras do topo da tela de Crescimento (docs/api-crescimento-panorama.md): o período, a receita e a comparação
// com o período anterior, as duas trilhas (do promotor ao cliente e as ofertas), os próximos passos e quem mais indica.
// Sem Vue, para testar.
import type { PanoramaCrescimento, ValorDecimal } from '@/api/tipos'
import { formatarMoeda, formatarNumero, plural } from '@/utils/formatos'
import { intervaloDoPeriodo } from '@/utils/periodo'
import { formatarMoedaCurta, partesMoedaCurta } from '@/modulos/relatorios/logica'
import { numeroDecimal, taxa } from './logica'

// ── Período ─────────────────────────────────────────────────────────────────

export type PeriodoPanorama = '30' | '90' | '365'
export const PERIODO_PANORAMA_PADRAO: PeriodoPanorama = '90'
export const PERIODOS_PANORAMA: readonly { valor: PeriodoPanorama; rotulo: string }[] = [
  { valor: '30', rotulo: '30 dias' },
  { valor: '90', rotulo: '90 dias' },
  { valor: '365', rotulo: '12 meses' },
]

export function ehPeriodoPanorama(v: unknown): v is PeriodoPanorama {
  return v === '30' || v === '90' || v === '365'
}

/** As datas do período, terminando hoje (12 meses = 365 dias, como o "Últimos 12 meses" das outras telas). */
export function intervaloPanorama(p: PeriodoPanorama, hoje: string): { de: string; ate: string } {
  const r = intervaloDoPeriodo(p, {}, hoje)
  return { de: r.de!, ate: r.ate! }
}

/** "nos 90 dias anteriores", "nos 12 meses anteriores". */
export function periodoAnterior(p: PeriodoPanorama): string {
  return p === '365' ? 'nos 12 meses anteriores' : `nos ${p} dias anteriores`
}

/** "nos últimos 90 dias", "nos últimos 12 meses". */
export function periodoAtual(p: PeriodoPanorama): string {
  return p === '365' ? 'nos últimos 12 meses' : `nos últimos ${p} dias`
}

// ── Receita ─────────────────────────────────────────────────────────────────

/** R$ 12,4 mil → { numero: '12,4', sufixo: 'mil' } (o número grande do topo). */
export function partesReceita(v: ValorDecimal | null | undefined): { numero: string; sufixo: string } {
  const p = partesMoedaCurta(numeroDecimal(v) ?? 0)
  return { numero: p?.numero ?? '0', sufixo: p?.sufixo ?? '' }
}

/** "R$ 3,1 mil", "R$ 850" (o formato curto dos Relatórios e do Início). */
export function moedaCurta(v: number): string {
  return formatarMoedaCurta(v, 'R$ 0')
}

/** O valor inteiro, para leitores de tela e para a dica ao passar o mouse: "R$ 12.400,00". */
export function moedaInteira(v: ValorDecimal | null | undefined): string {
  return formatarMoeda(numeroDecimal(v) ?? 0)
}

export interface Variacao {
  texto: string
  sentido: 'subiu' | 'caiu' | 'igual'
}

/** A receita do período contra a do anterior, de mesmo tamanho; null sem o anterior ou com os dois zerados. */
export function variacaoReceita(p: PanoramaCrescimento, periodo: PeriodoPanorama): Variacao | null {
  const atual = numeroDecimal(p.receita.total) ?? 0
  const antes = numeroDecimal(p.receita.anterior)
  if (antes === null || (atual === 0 && antes === 0)) return null
  const diferenca = atual - antes
  if (Math.abs(diferenca) < 0.005) return { texto: `O mesmo que ${periodoAnterior(periodo)}`, sentido: 'igual' }
  return diferenca > 0
    ? { texto: `${moedaCurta(diferenca)} a mais que ${periodoAnterior(periodo)}`, sentido: 'subiu' }
    : { texto: `${moedaCurta(-diferenca)} a menos que ${periodoAnterior(periodo)}`, sentido: 'caiu' }
}

/** De onde veio a receita: "8 indicações viraram cliente e 3 ofertas foram aceitas". */
export function origemReceita(p: PanoramaCrescimento): string {
  const partes: string[] = []
  if (p.indicacoes.clientes) partes.push(`${plural(p.indicacoes.clientes, 'indicação virou', 'indicações viraram')} cliente`)
  if (p.ofertas.aceitas) partes.push(plural(p.ofertas.aceitas, 'oferta foi aceita', 'ofertas foram aceitas'))
  if (!partes.length) return 'Nenhuma indicação virou cliente e nenhuma oferta foi aceita no período.'
  return partes.length === 2 ? `${partes[0]} e ${partes[1]}.` : `${partes[0]}.`
}

// ── Mês a mês ───────────────────────────────────────────────────────────────

const MESES_CURTOS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const MESES_LONGOS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

/** "2026-10" → "out/26". */
export function mesCurto(mes: string): string {
  const [a, m] = mes.split('-')
  return `${MESES_CURTOS[Number(m) - 1] ?? m}/${(a ?? '').slice(2)}`
}

/** "2026-10" → "outubro de 2026". */
export function mesLongo(mes: string): string {
  const [a, m] = mes.split('-')
  return `${MESES_LONGOS[Number(m) - 1] ?? m} de ${a}`
}

export interface BarraMes {
  mes: string
  valor: number
  indicacoes: number
  ofertas: number
  /** Altura da barra, em % do maior mês (com valor, nunca menos de 3%). */
  altura: number
  /** O mês tem dias no período escolhido (a barra em destaque). */
  noPeriodo: boolean
  /** O mês de hoje (ainda não acabou). */
  atual: boolean
}

/** As barras dos 12 meses: em destaque, os meses que entram no período escolhido (terminando hoje). */
export function barrasMeses(p: PanoramaCrescimento, periodo: PeriodoPanorama, hoje: string): BarraMes[] {
  const inicio = intervaloPanorama(periodo, hoje).de.slice(0, 7)
  const valores = p.meses.map((m) => numeroDecimal(m.total) ?? 0)
  const maior = Math.max(0, ...valores)
  return p.meses.map((m, i) => {
    const valor = valores[i] ?? 0
    return {
      mes: m.mes,
      valor,
      indicacoes: numeroDecimal(m.indicacoes) ?? 0,
      ofertas: numeroDecimal(m.ofertas) ?? 0,
      altura: maior > 0 && valor > 0 ? Math.max(3, Math.round((valor / maior) * 100)) : 0,
      noPeriodo: m.mes >= inicio,
      atual: m.mes === hoje.slice(0, 7),
    }
  })
}

/** De onde veio a receita do mês, com os valores inteiros (que somam o total): "R$ 3.200,00 de indicações e R$ 900,00 de ofertas". */
export function detalheMes(b: BarraMes): string {
  const partes: string[] = []
  if (b.indicacoes > 0) partes.push(`${moedaInteira(b.indicacoes)} de indicações`)
  if (b.ofertas > 0) partes.push(`${moedaInteira(b.ofertas)} de ofertas`)
  return partes.join(' e ')
}

// ── As trilhas ──────────────────────────────────────────────────────────────

/** Para onde leva um número: uma aba do Crescimento (com os filtros que dão a mesma conta) ou outra tela. */
export type Destino = { aba: 'indicacoes' | 'oportunidades' | 'depoimentos'; query?: Record<string, string> } | { caminho: string }

/** O endereço do destino, no formato do roteador. */
export function enderecoDoDestino(d: Destino): string | { name: 'crescimento'; params: { aba: string }; query: Record<string, string> } {
  return 'caminho' in d ? d.caminho : { name: 'crescimento', params: { aba: d.aba }, query: d.query ?? {} }
}

export interface EtapaTrilha {
  chave: string
  valor: number
  rotulo: string
  /** A taxa sobre a etapa de base, ou uma nota curta; null sem nada a dizer. */
  detalhe: string | null
  /** Largura da barra, em % da maior etapa da trilha (com valor, nunca menos de 2%, para aparecer). */
  largura: number
  /** A etapa que é o resultado (a barra em destaque). */
  resultado: boolean
  /** Só quando a lista de baixo, com os filtros, mostra exatamente esse número. */
  destino: Destino | null
}

function larguras(etapas: Omit<EtapaTrilha, 'largura'>[]): EtapaTrilha[] {
  const maior = Math.max(0, ...etapas.map((e) => e.valor))
  return etapas.map((e) => ({ ...e, largura: maior > 0 && e.valor > 0 ? Math.max(2, Math.round((e.valor / maior) * 100)) : 0 }))
}

const pct = (parte: number, total: number, de: string): string | null => {
  const t = taxa(parte, total)
  return t === null ? null : `${formatarNumero(t)}% ${de}`
}

/** Do promotor ao cliente: promotores → indicações recebidas → abordadas → viraram cliente. */
export function trilhaIndicacoes(p: PanoramaCrescimento, periodo: PeriodoPanorama): EtapaTrilha[] {
  const i = p.indicacoes
  return larguras([
    { chave: 'promotores', valor: i.promotores, rotulo: i.promotores === 1 ? 'Promotor' : 'Promotores', detalhe: 'notas 9 e 10', resultado: false, destino: null },
    {
      chave: 'recebidas',
      valor: i.recebidas,
      rotulo: i.recebidas === 1 ? 'Indicação recebida' : 'Indicações recebidas',
      detalhe: null,
      resultado: false,
      destino: { aba: 'indicacoes', query: { periodo } },
    },
    { chave: 'abordadas', valor: i.abordadas, rotulo: i.abordadas === 1 ? 'Abordada' : 'Abordadas', detalhe: pct(i.abordadas, i.recebidas, 'das indicações'), resultado: false, destino: null },
    {
      chave: 'clientes',
      valor: i.clientes,
      rotulo: 'Viraram cliente',
      detalhe: pct(i.clientes, i.recebidas, 'das indicações'),
      resultado: true,
      destino: { aba: 'indicacoes', query: { periodo, situacao: 'cliente' } },
    },
  ])
}

/** As ofertas do período: feitas → aceitas (a lista de baixo é de empresas, não de ofertas: sem link). */
export function trilhaOfertas(p: PanoramaCrescimento): EtapaTrilha[] {
  const o = p.ofertas
  return larguras([
    {
      chave: 'feitas',
      valor: o.feitas,
      rotulo: o.feitas === 1 ? 'Oferta feita' : 'Ofertas feitas',
      detalhe: o.aguardando ? `${formatarNumero(o.aguardando)} sem resultado` : null,
      resultado: false,
      destino: null,
    },
    { chave: 'aceitas', valor: o.aceitas, rotulo: o.aceitas === 1 ? 'Aceita' : 'Aceitas', detalhe: pct(o.aceitas, o.feitas, 'das feitas'), resultado: true, destino: null },
  ])
}

// ── Próximos passos ─────────────────────────────────────────────────────────

export interface Passo {
  chave: string
  /** O número em destaque (null quando o passo não é uma contagem). */
  quantidade: number | null
  /** O resto da frase, sem o número: "indicações esperando o primeiro contato". */
  texto: string
  acao: string
  destino: Destino
}

/**
 * Até 3, do que trava o resto ao que pode esperar: o convite desligado (sem ele não chegam indicações), gente
 * esperando o primeiro contato, clientes felizes sem oferta e depoimentos para aprovar.
 */
export function proximosPassos(p: PanoramaCrescimento, o: { conviteDesligado?: boolean; podeConfigurar?: boolean } = {}): Passo[] {
  const passos: Passo[] = []
  const esperando = p.indicacoes.esperando_contato
  const semOferta = p.ofertas.sem_oferta
  const pendentes = p.depoimentos.pendentes
  if (o.conviteDesligado)
    passos.push({
      chave: 'convite',
      quantidade: null,
      texto: 'O convite de indicação está desligado: quem dá nota 9 ou 10 não recebe o pedido para indicar.',
      acao: o.podeConfigurar ? 'Ligar o convite' : 'Ver o convite',
      destino: { caminho: '/configuracoes/crescimento' },
    })
  if (esperando)
    passos.push({
      chave: 'esperando',
      quantidade: esperando,
      texto: `${esperando === 1 ? 'indicação esperando' : 'indicações esperando'} o primeiro contato`,
      acao: esperando === 1 ? 'Ver a indicação' : 'Ver as indicações',
      destino: { aba: 'indicacoes', query: { situacao: 'nova' } },
    })
  if (semOferta)
    passos.push({
      chave: 'sem_oferta',
      quantidade: semOferta,
      texto: `${semOferta === 1 ? 'cliente feliz ainda sem oferta' : 'clientes felizes ainda sem oferta'}`,
      acao: 'Ver as oportunidades',
      destino: { aba: 'oportunidades' },
    })
  if (pendentes)
    passos.push({
      chave: 'depoimentos',
      quantidade: pendentes,
      texto: `${pendentes === 1 ? 'depoimento esperando' : 'depoimentos esperando'} a sua aprovação`,
      acao: pendentes === 1 ? 'Revisar o depoimento' : 'Revisar os depoimentos',
      destino: { aba: 'depoimentos' },
    })
  return passos.slice(0, 3)
}

// ── Quem mais indica ────────────────────────────────────────────────────────

export interface Fa {
  id: PanoramaCrescimento['fas'][number]['empresa']['id']
  nome: string
  indicacoes: number
  clientes: number
  /** "2 viraram cliente, R$ 1,2 mil/mês"; "Nenhuma virou cliente" quando nenhuma virou. */
  detalhe: string
  /** Largura da barra, em % de quem mais indicou (nunca menos de 4%). */
  largura: number
  /** Quanto da barra são as que viraram cliente (em % da própria barra). */
  parteClientes: number
}

export function quemMaisIndica(p: PanoramaCrescimento): Fa[] {
  const maior = Math.max(0, ...p.fas.map((f) => f.indicacoes))
  return p.fas.map((f) => {
    const receita = numeroDecimal(f.receita_mensal) ?? 0
    const detalhe = f.clientes
      ? `${plural(f.clientes, 'virou cliente', 'viraram cliente')}${receita > 0 ? `, ${moedaCurta(receita)}/mês` : ''}`
      : 'Nenhuma virou cliente'
    return {
      id: f.empresa.id,
      nome: f.empresa.nome,
      indicacoes: f.indicacoes,
      clientes: f.clientes,
      detalhe,
      largura: maior > 0 ? Math.max(4, Math.round((f.indicacoes / maior) * 100)) : 0,
      parteClientes: f.indicacoes > 0 ? Math.min(100, Math.round((f.clientes / f.indicacoes) * 100)) : 0,
    }
  })
}

// ── O resto ─────────────────────────────────────────────────────────────────

/** "Nota 10", "Nota 5 de 5" (CSAT). */
export function textoNota(nota: number | null, tipo: string | null): string | null {
  if (nota === null) return null
  return tipo === 'csat' ? `Nota ${nota} de 5` : `Nota ${nota}`
}

/** O período tem algo para as trilhas mostrarem (um promotor, uma indicação ou uma oferta). */
export function temMovimento(p: PanoramaCrescimento): boolean {
  const i = p.indicacoes
  return i.promotores + i.recebidas + p.ofertas.feitas > 0
}
