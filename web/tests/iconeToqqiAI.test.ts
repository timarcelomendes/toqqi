// Ícone do ToqqiAI (design-system/README.md §1): o símbolo da marca com a geometria oficial, nas variantes `simbolo`
// (traço em currentColor) e `selo` (quadrado coral com o símbolo branco); decorativo por padrão, role="img" com rótulo.
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import IconeToqqiAI from '@/components/app/IconeToqqiAI.vue'

/** As formas do símbolo, iguais às de design-system/marca/toqqi-simbolo.svg e de Marca.vue. */
function formas(svg: Element) {
  return {
    circulos: [...svg.querySelectorAll('circle')].map((c) => [c.getAttribute('cx'), c.getAttribute('cy'), c.getAttribute('r')]),
    tracos: [...svg.querySelectorAll('path')].map((p) => p.getAttribute('d')),
  }
}

const SIMBOLO = {
  circulos: [
    ['33', '33', '24.5'],
    ['109', '33', '24.5'],
  ],
  tracos: ['M57.5 33 V92', 'M133.5 33 V92', 'M18 112 Q70 140 122 112'],
}

describe('IconeToqqiAI', () => {
  it('simbolo (padrão): só o traço, em currentColor, com a geometria oficial e enquadrado sem cortar', () => {
    const w = mount(IconeToqqiAI, { attrs: { class: 'size-4' } })
    const svg = w.get('svg')
    expect(svg.attributes('data-icone-toqqiai')).toBe('simbolo')
    expect(svg.attributes('stroke')).toBe('currentColor')
    expect(svg.attributes('fill')).toBe('none')
    expect(svg.classes()).toEqual(expect.arrayContaining(['size-4', 'shrink-0']))
    expect(formas(svg.element)).toEqual(SIMBOLO)
    expect(svg.find('rect').exists()).toBe(false)
    // Hastes retas (só "V", nada de curva) e o sorriso de ponta redonda, solto abaixo das hastes (que terminam em y=92).
    const [h1, h2, sorriso] = svg.findAll('path')
    expect(h1!.attributes('d')).toMatch(/^M[\d.]+ \d+ V\d+$/)
    expect(h2!.attributes('d')).toMatch(/^M[\d.]+ \d+ V\d+$/)
    expect(sorriso!.attributes('stroke-linecap')).toBe('round')
    // Traço um pouco mais grosso que o oficial (20/17) para ler bem a 16 px.
    expect(svg.findAll('circle').map((c) => Number(c.attributes('stroke-width')))).toEqual([22, 22])
    expect(Number(sorriso!.attributes('stroke-width'))).toBe(19)
    // viewBox: o símbolo (x 8,5–133,5+traço; y 8,5–~126+traço) inteiro, com a metade do traço de folga.
    const [x, y, larg, alt] = svg.attributes('viewBox')!.split(' ').map(Number)
    expect(x).toBeLessThanOrEqual(8.5 - 11)
    expect(x! + larg!).toBeGreaterThanOrEqual(133.5 + 11)
    expect(y).toBeLessThanOrEqual(8.5 - 11)
    expect(y! + alt!).toBeGreaterThanOrEqual(126 + 9.5)
  })

  it('selo: quadrado arredondado coral da marca com o símbolo branco (o ícone do app)', () => {
    const w = mount(IconeToqqiAI, { props: { variante: 'selo' }, attrs: { class: 'size-8' } })
    const svg = w.get('svg')
    expect(svg.attributes('data-icone-toqqiai')).toBe('selo')
    expect(svg.attributes('viewBox')).toBe('0 0 48 48')
    const fundo = svg.get('rect')
    expect([fundo.attributes('width'), fundo.attributes('height'), fundo.attributes('rx'), fundo.attributes('fill')]).toEqual(['48', '48', '11', '#FF5A36'])
    const g = svg.get('g')
    expect(g.attributes('stroke')).toBe('#FFFFFF')
    expect(g.attributes('transform')).toBe('translate(9.1 9.7) scale(0.21)')
    expect(formas(svg.element)).toEqual(SIMBOLO)
    expect(svg.classes()).toContain('size-8')
  })

  it('decorativo por padrão; com rótulo, vira imagem com nome', () => {
    for (const variante of ['simbolo', 'selo'] as const) {
      const decorativo = mount(IconeToqqiAI, { props: { variante } }).get('svg')
      expect(decorativo.attributes('aria-hidden')).toBe('true')
      expect(decorativo.attributes('role')).toBeUndefined()
      expect(decorativo.attributes('aria-label')).toBeUndefined()
      expect(decorativo.attributes('focusable')).toBe('false')

      const comNome = mount(IconeToqqiAI, { props: { variante, rotulo: 'ToqqiAI' } }).get('svg')
      expect(comNome.attributes('role')).toBe('img')
      expect(comNome.attributes('aria-label')).toBe('ToqqiAI')
      expect(comNome.attributes('aria-hidden')).toBeUndefined()
    }
  })
})
