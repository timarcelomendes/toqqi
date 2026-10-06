// Textos curtos do editor de formulário: "há 5 minutos", a hora do conflito e as teclas dos atalhos (⌘ no Mac).
import { formatarData, FUSO } from '@/utils/datas'

/** "agora há pouco", "há 5 minutos", "há 2 horas", "há 3 dias"; mais de 30 dias: a data. */
export function haQuanto(valor: string | null | undefined, agora = Date.now()): string {
  if (!valor) return ''
  const t = new Date(valor).getTime()
  if (Number.isNaN(t)) return ''
  const s = Math.max(0, Math.round((agora - t) / 1000))
  if (s < 60) return 'agora há pouco'
  const m = Math.round(s / 60)
  if (m < 60) return `há ${m} ${m === 1 ? 'minuto' : 'minutos'}`
  const h = Math.round(m / 60)
  if (h < 24) return `há ${h} ${h === 1 ? 'hora' : 'horas'}`
  const d = Math.round(h / 24)
  if (d <= 30) return `há ${d} ${d === 1 ? 'dia' : 'dias'}`
  return `em ${formatarData(valor)}`
}

const fmtHora = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit' })

/** HH:MM no horário de Brasília. */
export function hora(valor: string | null | undefined): string {
  if (!valor) return ''
  const d = new Date(valor)
  return Number.isNaN(d.getTime()) ? '' : fmtHora.format(d)
}

/** Mac usa ⌘; os outros, Ctrl. */
export function ehMac(): boolean {
  try {
    return /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
  } catch {
    return false
  }
}

/** "Ctrl+Z" ou "⌘Z". */
export function tecla(combinacao: string): string {
  if (!ehMac()) return combinacao
  return combinacao.replace(/Ctrl\+/g, '⌘').replace(/Alt\+/g, '⌥').replace(/Shift\+/g, '⇧')
}

/** O elemento é um campo onde se digita (lá, "/" e "?" são texto, não atalho). */
export function emCampoDeTexto(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  if (el.isContentEditable) return true
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) return true
  return el instanceof HTMLInputElement && !['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color', 'file'].includes(el.type)
}
