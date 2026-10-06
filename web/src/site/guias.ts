/**
 * Guias do site (páginas de conteúdo para a busca e para os anúncios). Cada guia é um HTML pronto na raiz de `web/`
 * (`<caminho>.html`), servido em `/<caminho>` pela regra do `render.yaml` (e pelo Vite em dev e preview). Esta lista é
 * a fonte para as entradas do build, o redirecionamento, o `sitemap.xml` e os testes. Sem dependências: o
 * `vite.config.ts` importa este arquivo.
 */
export interface Guia {
  /** Endereço sem a barra: `/reduzir-churn`. Também é o nome do HTML e o `utm_campaign` dos botões. */
  caminho: string
  /** Texto do link nos rodapés. */
  rotulo: string
}

export const GUIAS: readonly Guia[] = [
  { caminho: 'reduzir-churn', rotulo: 'Como reduzir o churn' },
  { caminho: 'clientes-insatisfeitos', rotulo: 'Clientes insatisfeitos e receita em risco' },
  { caminho: 'customer-success', rotulo: 'Software de customer success' },
]

/** A página que lista os guias (`/guias`, link "Guias" no menu do site). */
export const INDICE: Guia = { caminho: 'guias', rotulo: 'Guias' }

/** Todas as páginas de conteúdo servidas como HTML próprio: o índice e cada guia. */
export const PAGINAS: readonly Guia[] = [INDICE, ...GUIAS]

/** O guia de um endereço (`/reduzir-churn`, `/reduzir-churn/` ou `/reduzir-churn.html`), ou null. */
export function guiaDoEndereco(url: string): Guia | null {
  const caminho = (url.split(/[?#]/)[0] ?? '').replace(/^\/+/, '').replace(/\/+$/, '').replace(/\.html$/, '')
  return GUIAS.find((g) => g.caminho === caminho) ?? null
}

/** A página de conteúdo (índice ou guia) de um endereço, ou null. */
export function paginaDoEndereco(url: string): Guia | null {
  const caminho = (url.split(/[?#]/)[0] ?? '').replace(/^\/+/, '').replace(/\/+$/, '').replace(/\.html$/, '')
  return PAGINAS.find((g) => g.caminho === caminho) ?? null
}

/** Endereço público do site, sem barra no fim, ou null quando não se sabe (build local). */
export function urlDoSite(env: Record<string, string | undefined>): string | null {
  const bruto = (env.SITE_URL || env.RENDER_EXTERNAL_URL || '').trim().replace(/\/+$/, '')
  return /^https:\/\/[a-z0-9.-]+$/i.test(bruto) ? bruto : null
}

/** `sitemap.xml` com a raiz, o índice e os guias. */
export function sitemap(site: string, hoje: string): string {
  const urls = ['/', ...PAGINAS.map((g) => `/${g.caminho}`)]
  const itens = urls.map((u) => `  <url><loc>${site}${u}</loc><lastmod>${hoje}</lastmod></url>`).join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${itens}\n</urlset>\n`
}

/** `robots.txt`: tudo liberado, menos as páginas de pesquisa e descadastro (têm token no endereço). */
export function robots(site: string | null): string {
  const linhas = ['User-agent: *', 'Disallow: /r/', 'Disallow: /f/', 'Disallow: /sair/', 'Allow: /']
  if (site) linhas.push('', `Sitemap: ${site}/sitemap.xml`)
  return linhas.join('\n') + '\n'
}
