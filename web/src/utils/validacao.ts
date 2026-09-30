export function emailValido(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())
}

/** Aceita só caminhos internos no parâmetro "voltar" (evita redirecionar para outro site). */
export function destinoSeguro(v: unknown, padrao = '/inicio'): string {
  return typeof v === 'string' && v.startsWith('/') && !v.startsWith('//') ? v : padrao
}

/** Remove tudo que não é dígito. */
export function apenasDigitos(v: string): string {
  return v.replace(/\D/g, '')
}

/** Formata telefone brasileiro enquanto digita: (11) 91234-5678. */
export function formatarTelefone(v: string): string {
  const d = apenasDigitos(v).slice(0, 11)
  if (d.length <= 2) return d ? `(${d}` : ''
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
}
