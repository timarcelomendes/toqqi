import { apenasDigitos, formatarTelefone, normalizarDocumento } from './validacao'

const fmtMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const fmtDecimal = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtNumero = new Intl.NumberFormat('pt-BR')

/** R$ 1.250,00 (aceita número ou texto decimal "1250.00"). */
export function formatarMoeda(v: number | string | null | undefined, vazio = '—'): string {
  if (v === null || v === undefined || v === '') return vazio
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? fmtMoeda.format(n) : vazio
}

/** 1.250,00 (para o campo, sem "R$"). */
export function formatarDecimal(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === '') return ''
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? fmtDecimal.format(n) : ''
}

/** Lê o que a pessoa digitou ("1.250,50", "1250.5", "R$ 30") e devolve número ou null. */
export function lerMoeda(texto: string): number | null {
  let t = texto.replace(/[^\d,.-]/g, '')
  if (!t) return null
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.')
  else if ((t.match(/\./g) ?? []).length > 1) t = t.replace(/\./g, '')
  const n = Number(t)
  return Number.isFinite(n) ? Math.round(n * 100) / 100 : null
}

export function formatarNumero(n: number | null | undefined): string {
  return typeof n === 'number' ? fmtNumero.format(n) : '—'
}

/**
 * CPF (11 dígitos) ou CNPJ (14) com pontuação, enquanto digita. O CNPJ pode ter letras nos 12 primeiros caracteres
 * (CNPJ alfanumérico, desde 07/2026); os 2 últimos são sempre dígitos. Letras vão para maiúsculas; CPF é só número.
 */
export function formatarDocumento(v: string | null | undefined): string {
  let base = ''
  let dv = ''
  for (const ch of normalizarDocumento(v)) {
    if (base.length < 12) base += ch
    else if (dv.length < 2 && ch >= '0' && ch <= '9') dv += ch
  }
  const d = base + dv
  if (d.length <= 11 && /^\d*$/.test(d)) {
    return d
      .replace(/^(\d{3})(\d)/, '$1.$2')
      .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
      .replace(/\.(\d{3})(\d{1,2})$/, '.$1-$2')
  }
  return d
    .replace(/^([0-9A-Z]{2})([0-9A-Z])/, '$1.$2')
    .replace(/^([0-9A-Z]{2})\.([0-9A-Z]{3})([0-9A-Z])/, '$1.$2.$3')
    .replace(/\.([0-9A-Z]{3})([0-9A-Z])/, '.$1/$2')
    .replace(/([0-9A-Z]{4})([0-9]{1,2})$/, '$1-$2')
}

/** Telefone guardado só com dígitos e DDI 55 → "(11) 91234-5678". Outros países: +DDI e número. */
export function exibirTelefone(v: string | null | undefined): string {
  const d = apenasDigitos(v ?? '')
  if (!d) return ''
  if (d.startsWith('55') && (d.length === 12 || d.length === 13)) return formatarTelefone(d.slice(2))
  if (d.length === 10 || d.length === 11) return formatarTelefone(d)
  return `+${d}`
}

/** Telefone para o campo de edição (sem o 55). */
export function telefoneParaCampo(v: string | null | undefined): string {
  const d = apenasDigitos(v ?? '')
  if (d.startsWith('55') && (d.length === 12 || d.length === 13)) return formatarTelefone(d.slice(2))
  return formatarTelefone(d)
}

/** Número para o link do WhatsApp (wa.me): sempre com DDI. */
export function telefoneWhatsapp(v: string | null | undefined): string | null {
  const d = apenasDigitos(v ?? '')
  if (d.length < 10) return null
  return d.length === 10 || d.length === 11 ? `55${d}` : d
}

export function plural(n: number, um: string, varios: string): string {
  return `${formatarNumero(n)} ${n === 1 ? um : varios}`
}
