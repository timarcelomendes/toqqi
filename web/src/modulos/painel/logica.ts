// Regras puras do Painel (sem Vue): faixas e cores do NPS, números com sinal, meses,
// primeiros passos (com "ocultar" guardado no navegador) e a escala do gráfico de evolução.
import type { FaixaNps, Painel, Permissao, Pico } from '@/api/tipos'
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
}

/** Os 4 passos reais vindos da API, com o atalho certo para o perfil de quem vê. */
export function montarPassos(pp: Partial<Painel['primeiros_passos']> | null | undefined, pode: (p: Permissao) => boolean): PassoInicial[] {
  const feito = (k: ChavePasso) => !!pp?.[k]
  return [
    {
      chave: 'contatos',
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
      titulo: 'Ligar os envios',
      descricao: 'Confira o texto do convite e ligue o envio das pesquisas.',
      feito: feito('envios_ligados'),
      ...(pode('envios.ver') ? { para: '/configuracoes/envios', acao: 'Configurar os envios' } : {}),
    },
    {
      chave: 'primeiro_envio',
      titulo: 'Enviar a primeira pesquisa',
      descricao: 'Mande por e-mail ou WhatsApp para alguns clientes.',
      feito: feito('primeiro_envio'),
      ...(pode('envios.ver') ? { para: '/envios', acao: 'Ir para Envios' } : {}),
    },
    {
      chave: 'primeira_resposta',
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

/** As duas partes do aviso de pico: "Pico de reclamações em Prazo e entrega" e "7 nos últimos 7 dias; a média era 1,5 por semana". */
export function partesPico(p: Pick<Pico, 'rotulo' | 'reclamacoes' | 'media_anterior'>): { titulo: string; detalhe: string } {
  const media = Number(p.media_anterior)
  const antes = Number.isFinite(media) && media > 0 ? `a média era ${fmtMediaPico.format(media)} por semana` : 'antes, não havia nenhuma'
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
