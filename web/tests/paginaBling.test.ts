// Página do aplicativo do Toqqi na loja do Bling (toqqi.com/bling): página inicial e manual de uso sem login, como o
// Bling pede. Título e descrição para a busca, um h1, a marca do canonical, a entrada leve dos guias, o índice apontando
// para seções que existem (com o #manual que vai no cadastro do aplicativo), links internos conhecidos e o cadastro com
// a origem.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { INTEGRACOES, PAGINAS, paginaDoEndereco, sitemap } from '@/site/guias'

const html = readFileSync(resolve(__dirname, '../bling.html'), 'utf8')
const corpo = html.slice(html.indexOf('<body>'))

describe('toqqi.com/bling', () => {
  it('é página de conteúdo própria (no sitemap e no render.yaml), fora do índice de guias', () => {
    expect(INTEGRACOES.map((p) => p.caminho)).toEqual(['bling'])
    expect(paginaDoEndereco('/bling')?.caminho).toBe('bling')
    expect(sitemap('https://toqqi.com', '2026-11-10')).toContain('<loc>https://toqqi.com/bling</loc>')
    const guias = readFileSync(resolve(__dirname, '../guias.html'), 'utf8')
    expect(guias).not.toContain('href="/bling"')
    expect(PAGINAS.some((p) => p.caminho === 'bling')).toBe(true)
  })

  it('título, descrição de tamanho bom, um só h1, canonical e só a entrada leve', () => {
    const titulo = /<title>([^<]+)<\/title>/.exec(html)![1]!
    const descricao = /<meta name="description" content="([^"]+)"/.exec(html)![1]!
    expect(titulo.length).toBeLessThanOrEqual(70)
    expect(descricao.length).toBeGreaterThan(110)
    expect(descricao.length).toBeLessThanOrEqual(160)
    expect(corpo.match(/<h1[\s>]/g)).toHaveLength(1)
    expect(html).toContain('<!-- canonical -->')
    expect([...html.matchAll(/<script[^>]*src="([^"]+)"/g)].map((m) => m[1])).toEqual(['/src/site/guia.ts'])
    expect(html).not.toMatch(/https?:\/\/(?!toqqi\.com)[a-z0-9.-]+\.[a-z]{2,}\/[^"]*\.(js|css)/)
  })

  it('o manual tem as seções que o Bling pede, e o índice só aponta para o que existe', () => {
    for (const id of ['o-que-faz', 'manual', 'requisitos', 'instalar', 'configurar', 'sincronizar', 'desinstalar', 'dados', 'duvidas', 'suporte']) {
      expect(corpo, id).toContain(`id="${id}"`)
    }
    for (const [, ancora] of corpo.matchAll(/href="#([^"]+)"/g)) expect(corpo, ancora).toContain(`id="${ancora}"`)
  })

  it('links internos vão a páginas conhecidas e o cadastro leva a origem da integração', () => {
    const conhecidos = new Set(['/', '/entrar', '/termos', '/privacidade', '/sair', '/cadastro', ...PAGINAS.map((g) => `/${g.caminho}`)])
    for (const [, href] of corpo.matchAll(/href="(\/[^"#?]*)/g)) {
      if (href!.startsWith('/marca/')) continue
      expect(conhecidos.has(href!), href).toBe(true)
    }
    const cadastros = [...corpo.matchAll(/href="(\/cadastro[^"]*)"/g)].map((m) => m[1])
    expect(cadastros.length).toBeGreaterThanOrEqual(3)
    for (const c of cadastros) expect(c).toBe('/cadastro?utm_source=toqqi&amp;utm_medium=integracao&amp;utm_campaign=bling')
  })

  it('não escreve preço (os preços mudam em Parâmetros) e diz que só lê o Bling', () => {
    expect(corpo).not.toMatch(/R\$\s*\d/)
    expect(corpo).toContain('não cria, não altera e não apaga nada no Bling')
  })
})
