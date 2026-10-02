// Lógica dos documentos legais (docs/api-aceite-lgpd.md §3): tipo de link e âncora vinda do endereço.

export type TipoLink = 'interno' | 'email' | 'externo' | 'invalido'

/**
 * Como desenhar um link do texto: caminho do próprio site ("/..." sem "//") vira RouterLink; "mailto:" e "https://"
 * viram <a>. Qualquer outra coisa (ex.: "javascript:") não vira link, só texto.
 */
export function tipoDeLink(href: string): TipoLink {
  if (href.startsWith('/') && !href.startsWith('//') && !href.includes('\\')) return 'interno'
  if (/^mailto:[^\s]+$/i.test(href)) return 'email'
  if (/^https:\/\/[^\s]+$/i.test(href)) return 'externo'
  return 'invalido'
}

/** "#cookies" → "cookies" (decodificado; vazio se não houver). */
export function idDaAncora(hash: string | null | undefined): string {
  let id = (hash ?? '').replace(/^#/, '')
  try {
    id = decodeURIComponent(id)
  } catch {
    /* âncora malformada: usa como veio */
  }
  return id
}
