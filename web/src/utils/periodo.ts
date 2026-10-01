// Período dos filtros (painel, respostas e planos de ação): presets e datas em AAAA-MM-DD,
// sempre em dias de São Paulo e com o primeiro e o último dia incluídos.
import { formatarData, hojeIso } from './datas'

export type PresetPeriodo = '7' | '30' | '90' | '365' | 'tudo' | 'personalizado'

export const PERIODOS: { valor: PresetPeriodo; rotulo: string }[] = [
  { valor: '7', rotulo: 'Últimos 7 dias' },
  { valor: '30', rotulo: 'Últimos 30 dias' },
  { valor: '90', rotulo: 'Últimos 90 dias' },
  { valor: '365', rotulo: 'Últimos 12 meses' },
  { valor: 'tudo', rotulo: 'Todo o período' },
  { valor: 'personalizado', rotulo: 'Escolher as datas' },
]

const ISO = /^\d{4}-\d{2}-\d{2}$/

export function dataIsoValida(v: unknown): v is string {
  if (typeof v !== 'string' || !ISO.test(v)) return false
  const d = new Date(`${v}T00:00:00Z`)
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v
}

/** Soma (ou subtrai) dias de uma data AAAA-MM-DD, sem depender do fuso do aparelho. */
export function somarDias(iso: string, dias: number): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + dias)
  return d.toISOString().slice(0, 10)
}

export function ehPreset(v: unknown): v is PresetPeriodo {
  return PERIODOS.some((p) => p.valor === v)
}

/**
 * Intervalo de um preset: "últimos 7 dias" vai de hoje − 6 até hoje (7 dias contando hoje).
 * "tudo" não manda datas. "personalizado" usa as datas escolhidas (só as válidas).
 */
export function intervaloDoPeriodo(
  preset: PresetPeriodo,
  escolhido: { de?: string; ate?: string } = {},
  hoje: string = hojeIso(),
): { de?: string; ate?: string } {
  if (preset === 'tudo') return {}
  if (preset === 'personalizado') {
    const r: { de?: string; ate?: string } = {}
    if (dataIsoValida(escolhido.de)) r.de = escolhido.de
    if (dataIsoValida(escolhido.ate)) r.ate = escolhido.ate
    return r
  }
  const dias = Number(preset)
  return { de: somarDias(hoje, -(dias - 1)), ate: hoje }
}

/** Erro das datas escolhidas à mão (ou null). */
export function erroIntervalo(de: string, ate: string): string | null {
  if (de && !dataIsoValida(de)) return 'Confira a data inicial.'
  if (ate && !dataIsoValida(ate)) return 'Confira a data final.'
  if (de && ate && de > ate) return 'A data inicial precisa ser antes da final.'
  return null
}

/**
 * Erro do período "Escolher as datas" (ou null): as duas datas preenchidas, válidas e a inicial antes da final.
 * Enquanto houver erro, a tela avisa no campo e não busca de novo (nem mostra o período nos títulos).
 */
export function erroPeriodoEscolhido(de: string, ate: string): string | null {
  const e = erroIntervalo(de, ate)
  if (e) return e
  if (!de && !ate) return 'Escolha a data inicial e a final.'
  if (!de) return 'Escolha a data inicial.'
  if (!ate) return 'Escolha a data final.'
  return null
}

/** "de 01/07/2026 a 29/09/2026", "desde 01/07/2026", "até 29/09/2026" ou "desde o começo". */
export function descreverIntervalo(de?: string | null, ate?: string | null): string {
  if (de && ate) return de === ate ? `em ${formatarData(de)}` : `de ${formatarData(de)} a ${formatarData(ate)}`
  if (de) return `desde ${formatarData(de)}`
  if (ate) return `até ${formatarData(ate)}`
  return 'desde o começo'
}

/** Texto curto do período escolhido, para títulos de cartão ("Últimos 90 dias", "De 01/07 a 29/09/2026"). */
export function rotuloPeriodo(preset: PresetPeriodo, escolhido: { de?: string; ate?: string } = {}): string {
  if (preset !== 'personalizado') return PERIODOS.find((p) => p.valor === preset)?.rotulo ?? ''
  const t = descreverIntervalo(escolhido.de || null, escolhido.ate || null)
  return t.charAt(0).toUpperCase() + t.slice(1)
}
