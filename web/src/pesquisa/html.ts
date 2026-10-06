// HTML dos blocos de conteúdo e dos finais (docs/api-etapa-5l.md §3): a mesma lista permitida da API (nh3), aqui com
// o DOMPurify. A página da pesquisa fica no mesmo endereço do app (onde está a sessão de quem usa o app): todo HTML
// passa por `limparHtml` antes de ir para a tela, e só o BlocoHtml.vue desenha HTML (v-html).
// O DOMPurify entra por import dinâmico: só quem tem conteúdo ou final com HTML baixa o limpador.
import type { DOMPurify } from 'dompurify'

/** Tags permitidas (§3.1). */
export const TAGS_PERMITIDAS = [
  'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'a', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'blockquote', 'hr', 'img',
  'span', 'div', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'caption', 'small', 'sub', 'sup', 'code', 'pre', 'figure',
  'figcaption',
] as const

/** Atributos permitidos, por tag (§3.1). O resto cai: class, id, on*, data-*, aria-*... */
export const ATRIBUTOS_PERMITIDOS: Readonly<Record<string, readonly string[]>> = {
  a: ['href', 'title', 'target', 'rel'],
  img: ['src', 'alt', 'width', 'height'],
  td: ['colspan', 'rowspan', 'style'],
  th: ['colspan', 'rowspan', 'style'],
  p: ['style'],
  h2: ['style'],
  h3: ['style'],
  h4: ['style'],
  div: ['style'],
}

/** Forçados em todo link: abre em nova aba, sem levar quem abriu nem passar reputação. */
export const REL_LINK = 'noopener noreferrer nofollow ugc'

const ALINHAMENTOS = ['left', 'center', 'right', 'justify']
const RE_INTEIRO = /^\d{1,4}$/

export interface ResultadoLimpeza {
  html: string
  /** O que saiu, sem repetir, na ordem em que apareceu: "script", "onclick", "iframe", "imagem de outro site"... */
  removido: string[]
}

/** O que a limpeza da vez precisa saber (os ganchos do DOMPurify são do objeto todo; a limpeza é síncrona). */
let contexto: { prefixo: string | null; removido: string[] } | null = null

function registrar(o: string) {
  if (contexto && !contexto.removido.includes(o)) contexto.removido.push(o)
}

/** A imagem é da plataforma? `prefixo` + chave (letras, números, "_" e "-"). */
export function imagemDaPlataforma(src: string | null | undefined, prefixo: string | null | undefined): boolean {
  if (!src || !prefixo) return false
  const s = src.trim()
  if (!s.startsWith(prefixo)) return false
  return /^[A-Za-z0-9_-]+$/.test(s.slice(prefixo.length))
}

/** `text-align` válido de um `style` (e as outras propriedades, que caem). */
function lerEstilo(estilo: string): { alinhamento: string | null; outras: string[] } {
  let alinhamento: string | null = null
  const outras: string[] = []
  for (const declaracao of estilo.split(';')) {
    const i = declaracao.indexOf(':')
    const prop = (i >= 0 ? declaracao.slice(0, i) : declaracao).trim().toLowerCase()
    if (!prop) continue
    const valor = i >= 0 ? declaracao.slice(i + 1).trim().toLowerCase() : ''
    if (prop === 'text-align' && ALINHAMENTOS.includes(valor)) alinhamento = valor
    else outras.push(prop)
  }
  return { alinhamento, outras }
}

function configurar(purify: DOMPurify): DOMPurify {
  purify.addHook('uponSanitizeElement', (no, dados) => {
    // Imagem que não é da plataforma sai inteira (a página da pesquisa não chama outros sites).
    if (dados.tagName !== 'img' || !(no instanceof Element)) return
    if (!imagemDaPlataforma(no.getAttribute('src'), contexto?.prefixo)) {
      registrar('imagem de outro site')
      no.remove()
    }
  })
  purify.addHook('uponSanitizeAttribute', (no, dados) => {
    const tag = no.nodeName.toLowerCase()
    const nome = dados.attrName
    if (!(ATRIBUTOS_PERMITIDOS[tag] ?? []).includes(nome)) {
      dados.keepAttr = false
      return
    }
    const valor = dados.attrValue
    if (nome === 'style') {
      const { alinhamento, outras } = lerEstilo(valor)
      for (const o of outras) registrar(`estilo (${o})`)
      if (alinhamento) dados.attrValue = `text-align: ${alinhamento}`
      else dados.keepAttr = false
    } else if (nome === 'width' || nome === 'height') {
      const n = Number(valor)
      if (!RE_INTEIRO.test(valor.trim()) || n < 1 || n > 2000) dados.keepAttr = false
    } else if (nome === 'colspan' || nome === 'rowspan') {
      const n = Number(valor)
      if (!RE_INTEIRO.test(valor.trim()) || n < 1 || n > 20) dados.keepAttr = false
    }
  })
  purify.addHook('afterSanitizeAttributes', (no) => {
    if (no.nodeName.toLowerCase() === 'a' && no instanceof Element) {
      no.setAttribute('target', '_blank')
      no.setAttribute('rel', REL_LINK)
    }
  })
  return purify
}

let carregando: Promise<DOMPurify> | null = null

/** Carrega o DOMPurify (uma vez). Chame cedo quando souber que vai precisar (ex.: o formulário tem conteúdo). */
export function carregarLimpador(): Promise<DOMPurify> {
  carregando ??= import('dompurify')
    .then((m) => configurar(m.default))
    .catch((e: unknown) => {
      carregando = null
      throw e
    })
  return carregando
}

/** O nome do que o DOMPurify tirou (tag, atributo ou comentário). */
function nomeRemovido(item: unknown): string | null {
  const r = item as { element?: Node; attribute?: Attr | null; from?: Node }
  if (r.attribute) {
    const nome = r.attribute.name.toLowerCase()
    if ((nome === 'href' || nome === 'src') && r.attribute.value) {
      const esquema = /^\s*([a-z][a-z0-9+.-]*):/i.exec(r.attribute.value)?.[1]
      return esquema ? `${nome} (${esquema.toLowerCase()}:)` : nome
    }
    return nome
  }
  if (r.element) {
    if (r.element.nodeType === 8) return 'comentário'
    if (r.element.nodeType !== 1) return null
    const nome = r.element.nodeName.toLowerCase()
    // `body` e `remove` são do próprio DOMPurify (o documento em que ele limpa), não do HTML de quem escreveu.
    return nome === 'body' || nome === 'remove' ? null : nome
  }
  return null
}

const CONFIG = {
  ALLOWED_TAGS: [...TAGS_PERMITIDAS],
  ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'src', 'alt', 'width', 'height', 'colspan', 'rowspan', 'style'],
  // Links e imagens: só https, http, mailto e tel (sem javascript:, data: nem endereço relativo).
  ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):)/i,
  // Atributos que não são endereço (o DOMPurify testaria a regra acima neles); o valor é conferido nos ganchos.
  ADD_URI_SAFE_ATTR: ['width', 'height', 'colspan', 'rowspan', 'target', 'rel'],
  ALLOW_DATA_ATTR: false,
  ALLOW_ARIA_ATTR: false,
  ALLOW_UNKNOWN_PROTOCOLS: false,
  KEEP_CONTENT: true,
  // Tudo no <body>: sem isso, um <script>, <meta> ou comentário no começo vai para o <head> e sai sem aparecer no aviso.
  FORCE_BODY: true,
}

/** Limpa com o DOMPurify já carregado (síncrono). */
export function limparComPurificador(purify: DOMPurify, html: string, prefixoImagens: string | null | undefined): ResultadoLimpeza {
  if (!html) return { html: '', removido: [] }
  contexto = { prefixo: prefixoImagens?.trim() || null, removido: [] }
  try {
    const limpo = purify.sanitize(html, CONFIG) as unknown as string
    for (const item of purify.removed) {
      const nome = nomeRemovido(item)
      if (nome) registrar(nome)
    }
    return { html: limpo, removido: contexto.removido }
  } finally {
    contexto = null
  }
}

/**
 * Limpa o HTML pela lista permitida (§3.1): só as tags e atributos da lista, `style` só com `text-align`, imagem só da
 * plataforma (`prefixoImagens`), link só https/http/mailto/tel e sempre com `target="_blank"` e `rel` forçado. Devolve
 * também o que foi removido (o editor mostra "Removemos por segurança: …").
 */
export async function limparHtmlComRelatorio(html: string, prefixoImagens: string | null | undefined): Promise<ResultadoLimpeza> {
  if (!html) return { html: '', removido: [] }
  return limparComPurificador(await carregarLimpador(), html, prefixoImagens)
}

/** Limpa o HTML pela lista permitida (§3.1). Use sempre antes de mostrar HTML (o BlocoHtml.vue já faz isso). */
export async function limparHtml(html: string, prefixoImagens: string | null | undefined): Promise<string> {
  return (await limparHtmlComRelatorio(html, prefixoImagens)).html
}

/** "Removemos por segurança: script, onclick, iframe." (vazio quando nada saiu). */
export function avisoRemocao(removido: readonly string[]): string {
  return removido.length ? `Removemos por segurança: ${removido.join(', ')}.` : ''
}

/** O texto do HTML, sem tags (para anunciar o começo de um bloco e para o caso de o limpador não carregar). */
export function textoDoHtml(html: string | null | undefined): string {
  if (!html) return ''
  try {
    // Documento inerte: nada roda nem carrega (sem script, sem imagem).
    const doc = new DOMParser().parseFromString(html, 'text/html')
    doc.querySelectorAll('script, style, template, noscript').forEach((e) => e.remove())
    return (doc.body.textContent ?? '').replace(/\s+/g, ' ').trim()
  } catch {
    return ''
  }
}
