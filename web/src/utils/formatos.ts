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

/** Milhar com ponto: "1.250", "12.500", "1.250.000" (1 a 3 dígitos sem zero na frente, depois grupos de 3). */
const MILHAR_COM_PONTO = /^-?[1-9]\d{0,2}(?:\.\d{3})+$/

/**
 * Lê o que a pessoa digitou e devolve o número (arredondado aos centavos) ou null. A vírgula é sempre a decimal
 * ("1.250,50", "1250,5", "12,5"). Sem vírgula, ponto seguido de exatamente 3 dígitos é milhar ("1.250" = 1250,
 * "1.250.000") e os outros pontos são decimais ("1.25", "1250.5", "0.500"). Pontos que não formam milhar junto da
 * vírgula ("1.25,50") ou soltos ("1.2.3") não viram número: a tela pede para conferir em vez de gravar um valor errado.
 */
export function lerMoeda(texto: string): number | null {
  let t = texto.replace(/[^\d,.-]/g, '')
  if (!t) return null
  if (t.includes(',')) {
    const [inteiro = '', ...decimais] = t.split(',')
    if (decimais.length !== 1 || (inteiro.includes('.') && !MILHAR_COM_PONTO.test(inteiro))) return null
    t = `${inteiro.replace(/\./g, '')}.${decimais[0]}`
  } else if (MILHAR_COM_PONTO.test(t)) t = t.replace(/\./g, '')
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

/**
 * E-mail em pedaços que terminam no "@" e em cada ponto ("sonia@", "padariaprado.", "com.", "br"): a tela põe um
 * <wbr> entre eles, para a linha quebrar nesses pontos e não no meio de uma palavra.
 */
export function partesEmail(email: string | null | undefined): string[] {
  return (email ?? '').split(/(?<=[@.])/).filter(Boolean)
}

export function plural(n: number, um: string, varios: string): string {
  return `${formatarNumero(n)} ${n === 1 ? um : varios}`
}

const fmtTamanho = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })

/** Tamanho de arquivo como nas outras telas (1 KB = 1.024 bytes): "512 bytes", "850,4 KB", "1,7 MB". */
export function formatarTamanho(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return plural(Math.round(bytes), 'byte', 'bytes')
  const unidades = ['KB', 'MB', 'GB', 'TB']
  let valor = bytes / 1024
  let i = 0
  // Sobe de unidade também quando o arredondamento chegaria a 1.024 ("1.024 KB" vira "1 MB").
  while (i < unidades.length - 1 && Math.round(valor * 10) / 10 >= 1024) {
    valor /= 1024
    i++
  }
  return `${fmtTamanho.format(valor)} ${unidades[i]}`
}
