// O que o editor visual (TipTap) sabe representar. HTML com outras partes (tabela, div, legenda…) fica na aba HTML,
// para não perder conteúdo (docs/api-etapa-5l.md §5.3). O que a limpeza tira de qualquer jeito (script, iframe…) não
// conta: isso sai nas duas abas, e o aviso "Removemos por segurança" já diz.
import { TAGS_PERMITIDAS } from '@/pesquisa/html'

const PERMITIDAS = new Set<string>(TAGS_PERMITIDAS)

/** Tags que o editor visual representa sem perder nada. */
const SUPORTADAS = new Set(['p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'a', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'blockquote', 'hr', 'img', 'code', 'pre'])

/** As partes do HTML que só a aba HTML edita (ex.: "table", "div"); vazio = o editor visual dá conta. */
export function partesSoNoHtml(html: string | null | undefined): string[] {
  if (!html?.trim() || typeof DOMParser === 'undefined') return []
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const fora = new Set<string>()
  for (const el of Array.from(doc.body.querySelectorAll('*'))) {
    const tag = el.tagName.toLowerCase()
    // <span> não tem atributo permitido: depois da limpeza é só um invólucro, e o texto fica nas duas abas.
    if (tag === 'span') continue
    if (PERMITIDAS.has(tag) && !SUPORTADAS.has(tag)) fora.add(tag)
  }
  return [...fora]
}

/** Endereço de link aceito (o mesmo da limpeza): https, http, mailto e tel. */
export function enderecoDeLinkValido(url: string): boolean {
  return /^(https?:\/\/[^\s]+|mailto:[^\s]+|tel:[+\d][\d\s().-]*)$/i.test(url.trim())
}
