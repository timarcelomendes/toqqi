export const FUSO = 'America/Sao_Paulo'

const fmtData = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit', year: 'numeric' })
const fmtDiaMes = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit' })
const fmtHora = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit' })
const fmtIso = new Intl.DateTimeFormat('en-CA', { timeZone: FUSO, year: 'numeric', month: '2-digit', day: '2-digit' })

function paraData(valor: string | Date | null | undefined): Date | null {
  if (!valor) return null
  // "YYYY-MM-DD" puro é uma data de calendário: ancoramos ao meio-dia de Brasília para não "voltar um dia".
  const d = typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valor) ? new Date(`${valor}T12:00:00-03:00`) : new Date(valor)
  return Number.isNaN(d.getTime()) ? null : d
}

/** dd/mm/aaaa no horário de Brasília. */
export function formatarData(valor: string | Date | null | undefined, vazio = '—'): string {
  const d = paraData(valor)
  return d ? fmtData.format(d) : vazio
}

/** dd/mm no horário de Brasília (ex.: "Próximo envio em 12/03"). */
export function formatarDiaMes(valor: string | Date | null | undefined, vazio = '—'): string {
  const d = paraData(valor)
  return d ? fmtDiaMes.format(d) : vazio
}

/** dd/mm/aaaa às hh:mm no horário de Brasília. */
export function formatarDataHora(valor: string | Date | null | undefined, vazio = '—'): string {
  const d = paraData(valor)
  return d ? `${fmtData.format(d)} às ${fmtHora.format(d)}` : vazio
}

/** Data de hoje (Brasília) em YYYY-MM-DD, com deslocamento opcional em dias. */
export function hojeIso(deslocamentoDias = 0): string {
  const d = new Date(Date.now() + deslocamentoDias * 86_400_000)
  return fmtIso.format(d)
}

/** Dias inteiros que faltam até a data (negativo se já passou). */
export function diasAte(valor: string | null | undefined): number | null {
  const d = paraData(valor)
  if (!d) return null
  const alvo = paraData(fmtIso.format(d))!
  const hoje = paraData(hojeIso())!
  return Math.round((alvo.getTime() - hoje.getTime()) / 86_400_000)
}
