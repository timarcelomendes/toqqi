// Etapa 5l (docs/api-etapa-5l.md §3): o HTML dos blocos de conteúdo e dos finais passa pela lista permitida antes de
// ir para a tela (`limparHtml`, com DOMPurify) e só o BlocoHtml.vue usa v-html.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { avisoRemocao, imagemDaPlataforma, limparHtml, limparHtmlComRelatorio, REL_LINK } from '@/pesquisa/html'
import BlocoHtml from '@/pesquisa/BlocoHtml.vue'

const PREFIXO = 'https://api.toqqi.com/api/v1/publico/imagens/'
const limpar = (html: string) => limparHtml(html, PREFIXO)
const relatorio = (html: string) => limparHtmlComRelatorio(html, PREFIXO)

describe('limparHtml: o que fica', () => {
  it('a lista permitida passa inteira (texto, listas, títulos, tabela, código)', async () => {
    const html =
      '<h2>Título</h2><h3>Sub</h3><h4>Menor</h4><p><strong>a</strong> <b>b</b> <em>c</em> <i>d</i> <u>e</u> <s>f</s> <small>g</small> <sub>h</sub><sup>i</sup> <code>j</code><br></p>' +
      '<ul><li>um</li></ul><ol><li>dois</li></ol><blockquote>cit</blockquote><hr><pre>pre</pre><span>sp</span><div>dv</div>' +
      '<figure><figcaption>leg</figcaption></figure><table><caption>cap</caption><thead><tr><th colspan="2">A</th></tr></thead><tbody><tr><td rowspan="2">1</td></tr></tbody></table>'
    expect(await limpar(html)).toBe(html)
  })

  it('links: só https, http, mailto e tel, sempre em nova aba e com rel forçado (title fica)', async () => {
    expect(await limpar('<a href="https://x.com" title="t" target="_self" rel="opener">x</a>')).toBe(
      `<a href="https://x.com" title="t" target="_blank" rel="${REL_LINK}">x</a>`,
    )
    expect(await limpar('<a href="mailto:a@b.com">m</a>')).toContain('href="mailto:a@b.com"')
    expect(await limpar('<a href="tel:+5511999990000">t</a>')).toContain('href="tel:+5511999990000"')
    expect(await limpar('<a href="http://x.com">h</a>')).toContain('href="http://x.com"')
  })

  it('imagem da plataforma fica, com alt e tamanho (1 a 2000)', async () => {
    const img = `<img src="${PREFIXO}Ab12_cd-3" alt="Logo" width="300" height="120">`
    expect(await limpar(img)).toBe(img)
    expect(imagemDaPlataforma(`${PREFIXO}Ab12`, PREFIXO)).toBe(true)
    expect(imagemDaPlataforma(`${PREFIXO}../x`, PREFIXO)).toBe(false)
    const r = await relatorio(`<img src="${PREFIXO}Ab12" width="9999" height="0">`)
    expect(r.html).toBe(`<img src="${PREFIXO}Ab12">`)
  })

  it('text-align fica (p, títulos, div, td, th); cor e outras propriedades caem', async () => {
    const r = await relatorio('<p style="color: red; text-align: center; background: url(https://x.com/a.png)">oi</p>')
    expect(r.html).toBe('<p style="text-align: center">oi</p>')
    expect(r.removido).toEqual(expect.arrayContaining(['estilo (color)', 'estilo (background)']))
    expect(await limpar('<h3 style="text-align:right">t</h3><td style="text-align: justify">c</td>')).toContain('<h3 style="text-align: right">t</h3>')
    expect(await limpar('<p style="text-align: center !important">x</p>')).toBe('<p>x</p>')
    expect(await limpar('<span style="text-align: center">x</span>')).toBe('<span>x</span>')
  })
})

describe('limparHtml: cada ataque sai (§3.1)', () => {
  const casos: [string, string, string, string][] = [
    ['script', '<p>oi</p><script>fetch("/api")</script>', '<p>oi</p>', 'script'],
    ['on*', '<p onclick="roubar()" onmouseover="x()">oi</p>', '<p>oi</p>', 'onclick'],
    ['javascript:', '<a href="javascript:alert(1)">x</a>', `<a target="_blank" rel="${REL_LINK}">x</a>`, 'href (javascript:)'],
    ['javascript: com espaços e maiúsculas', '<a href=" JaVaScRiPt:alert(1)">x</a>', `<a target="_blank" rel="${REL_LINK}">x</a>`, 'href (javascript:)'],
    ['data: em link', '<a href="data:text/html,<script>alert(1)</script>">x</a>', `<a target="_blank" rel="${REL_LINK}">x</a>`, 'href (data:)'],
    ['data: em imagem', '<img src="data:image/png;base64,iVBORw0KGgo=">', '', 'imagem de outro site'],
    ['imagem externa', '<p><img src="https://rastreador.com/pixel.png" alt="x"></p>', '<p></p>', 'imagem de outro site'],
    ['imagem sem src', '<img alt="x">', '', 'imagem de outro site'],
    ['onerror em imagem da plataforma', `<img src="${PREFIXO}abc" onerror="alert(1)">`, `<img src="${PREFIXO}abc">`, 'onerror'],
    ['iframe', '<iframe src="https://x.com"></iframe><p>a</p>', '<p>a</p>', 'iframe'],
    ['svg', '<svg><script>alert(1)</script><circle r="1"/></svg><p>a</p>', '<p>a</p>', 'svg'],
    ['math', '<math><mi>x</mi></math><p>a</p>', '<p>a</p>', 'math'],
    ['style (tag)', '<style>body{display:none}</style><p>a</p>', '<p>a</p>', 'style'],
    ['object e embed', '<object data="x.swf"></object><embed src="x.swf"><p>a</p>', '<p>a</p>', 'object'],
    ['form, input e button', '<form action="https://x.com"><input name="senha"><button>ok</button></form>', 'ok', 'form'],
    ['video e audio', '<video src="https://x.com/v.mp4"></video><audio src="https://x.com/a.mp3"></audio><p>a</p>', '<p>a</p>', 'video'],
    ['meta, link e base', '<meta http-equiv="refresh" content="0;url=https://x.com"><link rel="stylesheet" href="https://x.com/a.css"><base href="https://x.com"><p>a</p>', '<p>a</p>', 'meta'],
    ['class e id', '<p class="x" id="y" data-z="1" aria-label="w">a</p>', '<p>a</p>', 'class'],
    ['comentário', '<!-- segredo --><p>a</p>', '<p>a</p>', 'comentário'],
    ['tag desconhecida mantém o texto', '<font color="red">texto</font>', 'texto', 'font'],
  ]

  it.each(casos)('%s', async (_nome, entrada, saida, removido) => {
    const r = await relatorio(entrada)
    expect(r.html).toBe(saida)
    expect(r.removido).toContain(removido)
  })

  it('o aviso do editor lista o que saiu', async () => {
    const r = await relatorio('<script>x</script><p onclick="y">a</p><iframe></iframe>')
    expect(avisoRemocao(r.removido)).toBe('Removemos por segurança: script, onclick, iframe.')
    expect(avisoRemocao([])).toBe('')
  })

  it('sem prefixo de imagens, nenhuma imagem passa', async () => {
    expect(await limparHtml(`<img src="${PREFIXO}abc">`, null)).toBe('')
  })

  it('HTML vazio continua vazio (sem carregar nada)', async () => {
    expect(await limpar('')).toBe('')
  })
})

describe('BlocoHtml', () => {
  it('desenha só o HTML limpo e avisa o que saiu', async () => {
    const w = mount(BlocoHtml, { props: { html: '<p onclick="x()">Olá <strong>Ana</strong></p><script>alert(1)</script>', prefixoImagens: PREFIXO } })
    await flushPromises()
    await new Promise((r) => setTimeout(r, 0))
    await flushPromises()
    expect(w.get('[data-bloco-html]').element.innerHTML).toBe('<p>Olá <strong>Ana</strong></p>')
    expect(w.emitted('limpo')?.at(-1)?.[0]).toEqual({ html: '<p>Olá <strong>Ana</strong></p>', removido: ['onclick', 'script'] })
    await w.setProps({ html: '<p>Outro</p>' })
    await flushPromises()
    await new Promise((r) => setTimeout(r, 0))
    expect(w.get('[data-bloco-html]').text()).toBe('Outro')
  })
})

// ── Varredor: v-html só no BlocoHtml.vue (§3.3) ──────────────────────────────

function arquivosVue(pasta: string): string[] {
  const saida: string[] = []
  for (const nome of readdirSync(pasta)) {
    const caminho = join(pasta, nome)
    if (statSync(caminho).isDirectory()) saida.push(...arquivosVue(caminho))
    else if (nome.endsWith('.vue')) saida.push(caminho)
  }
  return saida
}

describe('varredor de v-html', () => {
  it('nenhum v-html em web/src fora do src/pesquisa/BlocoHtml.vue', () => {
    const raiz = resolve(__dirname, '../src')
    const usam = arquivosVue(raiz)
      .filter((arquivo) => /\bv-html\s*=/.test(readFileSync(arquivo, 'utf8')))
      .map((arquivo) => relative(raiz, arquivo).split('\\').join('/'))
    expect(usam).toEqual(['pesquisa/BlocoHtml.vue'])
  })

  it('o BlocoHtml.vue passa tudo pelo limparHtml', () => {
    const fonte = readFileSync(resolve(__dirname, '../src/pesquisa/BlocoHtml.vue'), 'utf8')
    expect(fonte).toMatch(/limparHtml/)
    expect(fonte.match(/\bv-html\s*=\s*"([^"]+)"/)?.[1]).toBe('limpo')
  })
})
