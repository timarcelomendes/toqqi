import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { GUIAS, INDICE, PAGINAS, guiaDoEndereco, paginaDoEndereco, robots, sitemap, urlDoSite } from '@/site/guias'
import { ehSite } from '@/site/rota'

const ler = (arquivo: string) => readFileSync(resolve(__dirname, '..', arquivo), 'utf8')
const corpoDe = (html: string) => html.slice(html.indexOf('<body>') + 6, html.indexOf('</body>'))
const semTags = (html: string) =>
  html
    .replace(/<script[\s\S]*?<\/script>/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')

describe('lista dos guias', () => {
  it('reconhece o endereço com e sem barra, com .html e com busca; o resto não é guia', () => {
    expect(guiaDoEndereco('/reduzir-churn')?.caminho).toBe('reduzir-churn')
    expect(guiaDoEndereco('/reduzir-churn/')?.caminho).toBe('reduzir-churn')
    expect(guiaDoEndereco('/reduzir-churn.html?utm_source=google')?.caminho).toBe('reduzir-churn')
    expect(guiaDoEndereco('/customer-success#planos')?.caminho).toBe('customer-success')
    for (const u of ['/', '/entrar', '/reduzir', '/r/reduzir-churn', '/reduzir-churn/x']) {
      expect(guiaDoEndereco(u)).toBeNull()
    }
  })
  it('o índice /guias é página de conteúdo, mas não é um guia', () => {
    expect(paginaDoEndereco('/guias')?.caminho).toBe('guias')
    expect(paginaDoEndereco('/guias/?x=1')?.caminho).toBe('guias')
    expect(paginaDoEndereco('/reduzir-churn')?.caminho).toBe('reduzir-churn')
    expect(guiaDoEndereco('/guias')).toBeNull()
    expect(paginaDoEndereco('/entrar')).toBeNull()
    expect(ehSite('/guias')).toBe(false)
  })
  it('os guias não são a raiz do site (o app nunca carrega a página da raiz neles)', () => {
    for (const g of GUIAS) expect(ehSite(`/${g.caminho}`)).toBe(false)
  })
  it('endereço do site: SITE_URL vale mais que o do Render; só https', () => {
    expect(urlDoSite({ SITE_URL: 'https://toqqi.com/', RENDER_EXTERNAL_URL: 'https://toqqi-web.onrender.com' })).toBe(
      'https://toqqi.com',
    )
    expect(urlDoSite({ RENDER_EXTERNAL_URL: 'https://toqqi-web.onrender.com' })).toBe('https://toqqi-web.onrender.com')
    expect(urlDoSite({})).toBeNull()
    expect(urlDoSite({ SITE_URL: 'http://toqqi.com' })).toBeNull()
    expect(urlDoSite({ SITE_URL: 'https://toqqi.com/"><script>' })).toBeNull()
  })
  it('sitemap com a raiz e cada guia; robots esconde pesquisa e descadastro', () => {
    const xml = sitemap('https://toqqi.com', '2026-10-05')
    expect(xml).toContain('<loc>https://toqqi.com/</loc>')
    for (const g of PAGINAS) expect(xml).toContain(`<loc>https://toqqi.com/${g.caminho}</loc>`)
    const txt = robots('https://toqqi.com')
    for (const p of ['/r/', '/f/', '/sair/']) expect(txt).toContain(`Disallow: ${p}`)
    expect(txt).toContain('Sitemap: https://toqqi.com/sitemap.xml')
    expect(robots(null)).not.toContain('Sitemap')
  })
})

describe('servidor e build', () => {
  it('render.yaml manda cada guia ao seu HTML antes da regra geral do app', () => {
    const yaml = ler('../render.yaml')
    const geral = yaml.indexOf('source: /*\n        destination: /index.html')
    expect(geral).toBeGreaterThan(0)
    for (const g of PAGINAS) {
      const regra = yaml.indexOf(`source: /${g.caminho}\n        destination: /${g.caminho}.html`)
      expect(regra, g.caminho).toBeGreaterThan(0)
      expect(regra, g.caminho).toBeLessThan(geral)
    }
  })
  it('a página da raiz leva ao índice no menu e a cada guia no rodapé', () => {
    const raiz = ler('index.html')
    const menu = raiz.slice(raiz.indexOf('<nav class="nav"'), raiz.indexOf('</nav>', raiz.indexOf('<nav class="nav"')))
    expect(menu).toContain('<a href="/guias">Guias</a>')
    for (const g of GUIAS) expect(raiz).toContain(`href="/${g.caminho}"`)
  })
})

describe('índice /guias', () => {
  const html = ler(`${INDICE.caminho}.html`)
  const corpo = corpoDe(html)
  it('lista cada guia, com o menu marcando Guias e a mesma entrada leve, sem nada de fora', () => {
    for (const g of GUIAS) expect(corpo).toContain(`<a href="/${g.caminho}" class="guia-cartao cartao">`)
    expect(corpo).toContain('<a href="/guias" aria-current="page">Guias</a>')
    expect(corpo.match(/<h1[\s>]/g)).toHaveLength(1)
    expect(html).toMatch(/<title>[^<]+· Toqqi<\/title>/)
    expect(html).toContain('<!-- canonical -->')
    expect(html).toContain('<script type="module" src="/src/site/guia.ts"></script>')
    expect(html).not.toMatch(/(src|href)="(https?:)?\/\//)
  })
})

describe.each(GUIAS.map((g) => [g.caminho]))('guia %s', (caminho) => {
  const html = ler(`${caminho}.html`)
  const corpo = corpoDe(html)
  const texto = semTags(corpo)

  it('tem título, descrição de tamanho bom para a busca, um só h1 e a marca do canonical', () => {
    const titulo = /<title>([^<]+)<\/title>/.exec(html)?.[1] ?? ''
    const descricao = /<meta name="description" content="([^"]+)"/.exec(html)?.[1] ?? ''
    expect(titulo).toMatch(/· Toqqi$/)
    expect(titulo.length).toBeLessThanOrEqual(80)
    expect(descricao.length).toBeGreaterThanOrEqual(110)
    expect(descricao.length).toBeLessThanOrEqual(180)
    expect(corpo.match(/<h1[\s>]/g)).toHaveLength(1)
    expect(html).toContain('<!-- canonical -->')
    expect(html).toContain('<html lang="pt-BR">')
  })

  it('carrega só a entrada leve dos guias, sem o app nem nada de fora', () => {
    expect(html).toContain('<script type="module" src="/src/site/guia.ts"></script>')
    expect(html).not.toContain('entrada.ts')
    expect(html).not.toMatch(/(src|href)="(https?:)?\/\//)
    expect(html).not.toMatch(/fonts\.googleapis|googletagmanager|gtag\(/)
  })

  it('os botões de teste levam ao cadastro com a origem do guia', () => {
    const links = [...corpo.matchAll(/href="(\/cadastro[^"]*)"/g)].map((m) => m[1])
    expect(links.length).toBeGreaterThanOrEqual(3)
    for (const l of links) {
      expect(l).toBe(`/cadastro?utm_source=toqqi&amp;utm_medium=guia&amp;utm_campaign=${caminho}`)
    }
  })

  it('o índice aponta para seções que existem, e os links internos vão a páginas conhecidas', () => {
    const ancoras = [...corpo.matchAll(/<li><a href="#([^"]+)">/g)].map((m) => m[1])
    expect(ancoras.length).toBeGreaterThanOrEqual(4)
    for (const a of ancoras) expect(corpo).toContain(`<section id="${a}"`)
    const conhecidos = new Set(['/', '/entrar', '/termos', '/privacidade', ...PAGINAS.map((g) => `/${g.caminho}`)])
    for (const [, href] of corpo.matchAll(/href="(\/[^"#?]*)/g)) {
      if (href === '/cadastro') continue
      expect(conhecidos.has(href as string), href).toBe(true)
    }
    for (const g of GUIAS.filter((x) => x.caminho !== caminho)) expect(corpo).toContain(`href="/${g.caminho}"`)
    expect(corpo).toContain('<li><a href="/guias">Guias</a></li>')
    expect(corpo).toContain('<a href="/guias">Guias</a>\n</nav>')
  })

  it('não promete o que o produto não tem nem preço escrito (preços e limites mudam em Parâmetros)', () => {
    expect(texto).not.toMatch(/R\$\s?(149|349|799)\b/)
    expect(texto).not.toMatch(/\b(14|7) dias grátis/)
    expect(texto).not.toMatch(/\[a confirmar|lorem ipsum/i)
    expect(texto).not.toMatch(/\bTODO\b/)
    // 5k: o WhatsApp automático não tem franquia em nenhum plano.
    expect(texto).not.toMatch(/franquia mensal|mensagens automáticas por mês|quantidade de mensagens/)
    for (const proibido of ['Teams', 'Fillout', 'Google Analytics', 'cookies de terceiros']) {
      expect(texto).not.toContain(proibido)
    }
  })

  it('número de exemplo vem marcado como exemplo', () => {
    if (/R\$ 262\.399,99|R\$ 100\.000/.test(texto)) expect(texto).toContain('Exemplo')
  })
})
