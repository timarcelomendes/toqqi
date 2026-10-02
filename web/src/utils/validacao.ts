export function emailValido(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())
}

/**
 * Aceita só caminhos internos nos parâmetros de retorno ("voltar" de Entrar, "de" do aceite), para não redirecionar
 * para outro site: começa com "/", sem "//" nem "\\" em lugar nenhum e sem caracteres de controle. O resto vira `padrao`.
 */
export function destinoSeguro(v: unknown, padrao = '/inicio'): string {
  if (typeof v !== 'string' || !v.startsWith('/')) return padrao
  if (v.includes('//') || v.includes('\\') || /[\u0000-\u001f\u007f]/.test(v)) return padrao
  return v
}

/** Remove tudo que não é dígito. */
export function apenasDigitos(v: string): string {
  return v.replace(/\D/g, '')
}

/**
 * CPF ou CNPJ sem pontuação, em maiúsculas (o CNPJ pode ter letras desde 07/2026: 12.ABC.345/01DE-35 → 12ABC34501DE35).
 */
export function normalizarDocumento(v: string | null | undefined): string {
  return (v ?? '').toUpperCase().replace(/[^0-9A-Z]/g, '')
}

/**
 * Formata telefone brasileiro enquanto digita: (11) 91234-5678. Colado com o código do país ("+55 11 98765-4321",
 * "5511987654321"), fica só o número nacional; o que vem da própria máscara (começa com "(") não perde o 55, que
 * também é DDD.
 */
export function formatarTelefone(v: string): string {
  let d = apenasDigitos(v)
  if (d.length > 11 && d.startsWith('55') && !v.trimStart().startsWith('(')) d = d.slice(2)
  d = d.slice(0, 11)
  if (d.length <= 2) return d ? `(${d}` : ''
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
}
