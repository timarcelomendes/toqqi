// Gráficos dos relatórios: o que o clique, o toque e o foco pelo teclado mostram (ou abrem).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import type { PontoMatriz, PrioridadeTema, SemanaTemas } from '@/api/tipos'
import GraficoPrioridades from '@/modulos/relatorios/GraficoPrioridades.vue'
import GraficoSemanal from '@/modulos/relatorios/GraficoSemanal.vue'
import MatrizNpsValor from '@/modulos/relatorios/MatrizNpsValor.vue'

// No jsdom nada tem tamanho: o <svg> passa a medir o que diz nos atributos (1 unidade = 1 px na tela).
const medidaOriginal = Element.prototype.getBoundingClientRect
beforeEach(() => {
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    if (this.tagName.toLowerCase() !== 'svg') return medidaOriginal.call(this)
    const w = Number(this.getAttribute('width'))
    const h = Number(this.getAttribute('height'))
    return { x: 0, y: 0, left: 0, top: 0, width: w, height: h, right: w, bottom: h, toJSON: () => ({}) } as DOMRect
  })
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

/** Evento de ponteiro na posição (mouse ou toque); o jsdom pode não ter PointerEvent. */
function ponteiro(el: Element, tipo: string, x: number, y: number, pointerType: 'mouse' | 'touch' = 'mouse') {
  const Ev = typeof PointerEvent === 'function' ? PointerEvent : MouseEvent
  const e = new Ev(tipo, { clientX: x, clientY: y, bubbles: tipo !== 'pointerleave', cancelable: true })
  Object.defineProperty(e, 'pointerType', { value: pointerType })
  el.dispatchEvent(e)
}
/** Foco pelo teclado, como o Tab: o navegador (e o jsdom) só marca :focus-visible depois de uma tecla. */
async function focarPeloTeclado(el: Element) {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
  ;(el as HTMLElement).focus()
  await nextTick()
}
function clique(el: Element, x: number, y: number) {
  el.dispatchEvent(new MouseEvent('click', { clientX: x, clientY: y, bubbles: true, cancelable: true }))
}

/**
 * Um clique ou toque como o navegador faz: pointerdown (no gráfico) → foco no contêiner (se ainda não tinha) →
 * [toque: pointerleave antes do clique] → click.
 */
async function tocar(w: VueWrapper, x: number, y: number, tipo: 'mouse' | 'touch' = 'mouse') {
  const svg = w.get('svg').element
  const grupo = w.get('[role="group"]').element as HTMLElement
  ponteiro(svg, 'pointerdown', x, y, tipo)
  if (document.activeElement !== grupo) grupo.focus()
  ponteiro(svg, 'pointerup', x, y, tipo)
  if (tipo === 'touch') ponteiro(svg, 'pointerleave', x, y, tipo)
  clique(svg, x, y)
  await nextTick()
}

const centro = (w: VueWrapper, seletor: string) => {
  const c = w.get(seletor)
  return [Number(c.attributes('cx')), Number(c.attributes('cy'))] as const
}

// ── Matriz NPS × valor ──────────────────────────────────────────────────────

const PONTOS: PontoMatriz[] = [
  { empresa: { id: 1, nome: 'Barata' }, nps: 50, valor_mensal: '1000.00', respostas: 3, quadrante: 'crescer' },
  { empresa: { id: 2, nome: 'Média' }, nps: -20, valor_mensal: '8000.00', respostas: 5, quadrante: 'corrigir' },
  { empresa: { id: 3, nome: 'Cara' }, nps: -60, valor_mensal: '90000.00', respostas: 9, quadrante: 'proteger' },
]
const matriz = () => mount(MatrizNpsValor, { props: { pontos: PONTOS, mediana: 8000 }, attachTo: document.body })

describe('Matriz NPS × valor', () => {
  it('clique num espaço vazio (o primeiro, que também dá o foco) não abre nada nem mostra dica', async () => {
    const w = matriz()
    await tocar(w, 330, 20)
    expect(w.emitted('abrir')).toBeUndefined()
    expect(w.text()).not.toContain('Clique para ver o histórico')
  })

  it('clique no ponto abre a empresa daquele ponto (nunca a de menor valor)', async () => {
    const w = matriz()
    const [x, y] = centro(w, 'circle[data-empresa="3"]')
    await tocar(w, x + 6, y - 5)
    expect(w.emitted('abrir')).toEqual([[3, 'Cara']])
    // Um segundo clique, em outro ponto, abre esse outro.
    const [x2, y2] = centro(w, 'circle[data-empresa="2"]')
    await tocar(w, x2, y2)
    expect(w.emitted('abrir')).toEqual([
      [3, 'Cara'],
      [2, 'Média'],
    ])
  })

  it('toque: abre o ponto tocado, também nos toques seguintes', async () => {
    const w = matriz()
    const [x, y] = centro(w, 'circle[data-empresa="2"]')
    await tocar(w, x, y, 'touch')
    const [x3, y3] = centro(w, 'circle[data-empresa="3"]')
    await tocar(w, x3, y3, 'touch')
    expect(w.emitted('abrir')).toEqual([
      [2, 'Média'],
      [3, 'Cara'],
    ])
  })

  it('mouse por cima mostra a dica; sair com o mouse esconde', async () => {
    const w = matriz()
    const [x, y] = centro(w, 'circle[data-empresa="1"]')
    ponteiro(w.get('svg').element, 'pointermove', x, y)
    await nextTick()
    expect(w.text()).toContain('Barata')
    ponteiro(w.get('svg').element, 'pointerleave', x, y)
    await nextTick()
    expect(w.text()).not.toContain('Clique para ver o histórico')
  })

  it('teclado: o foco (Tab) mostra a primeira empresa, as setas andam e Enter abre a escolhida', async () => {
    const w = matriz()
    const grupo = w.get('[role="group"]')
    await focarPeloTeclado(grupo.element)
    expect(w.text()).toContain('Barata')
    expect(w.get('[aria-live="polite"]').text()).toContain('Barata: NPS 50')
    await grupo.trigger('keydown', { key: 'ArrowRight' })
    expect(w.get('[aria-live="polite"]').text()).toContain('Média')
    await grupo.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('abrir')).toEqual([[2, 'Média']])
    // Sair do gráfico esconde a dica.
    ;(grupo.element as HTMLElement).blur()
    await nextTick()
    expect(w.text()).not.toContain('Clique para ver o histórico')
  })

  it('depois de um clique sem foco novo, o próximo Tab ainda escolhe a primeira empresa', async () => {
    const w = matriz()
    const grupo = w.get('[role="group"]').element as HTMLElement
    await tocar(w, 330, 20)
    // Clique de novo no gráfico já focado (não há foco novo), depois sai e volta pelo teclado.
    ponteiro(w.get('svg').element, 'pointerdown', 330, 20)
    grupo.blur()
    await focarPeloTeclado(grupo)
    expect(w.text()).toContain('Barata')
  })
})

// ── O que resolver primeiro ─────────────────────────────────────────────────

const PRIORIDADES: PrioridadeTema[] = [
  { tema: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 38, nota_media: 5.9, reclamacoes: 21 },
  { tema: 'atendimento', rotulo: 'Atendimento', mencoes: 12, nota_media: 8.8, reclamacoes: 2 },
]

describe('O que resolver primeiro', () => {
  const grafico = () => mount(GraficoPrioridades, { props: { prioridades: PRIORIDADES }, attachTo: document.body })
  const dica = (w: VueWrapper) => w.find('.pointer-events-none.absolute')

  it('clique num espaço vazio não mostra o primeiro tema', async () => {
    const w = grafico()
    await tocar(w, 300, 250)
    expect(dica(w).exists()).toBe(false)
  })

  it('toque num tema mostra a dica, que continua depois de levantar o dedo', async () => {
    const w = grafico()
    const [x, y] = centro(w, 'circle[data-tema="atendimento"]')
    await tocar(w, x, y, 'touch')
    expect(dica(w).text()).toContain('Atendimento')
    expect(dica(w).text()).toContain('12 menções')
  })

  it('o foco pelo teclado mostra o primeiro tema (o mais urgente)', async () => {
    const w = grafico()
    await focarPeloTeclado(w.get('[role="group"]').element)
    expect(dica(w).text()).toContain('Prazo e entrega')
  })
})

// ── Semana a semana ─────────────────────────────────────────────────────────

const SEMANAS: SemanaTemas[] = [
  { inicio: '2026-09-07', fim: '2026-09-13', respostas: 5, temas: { prazo_entrega: { mencoes: 1, reclamacoes: 1 } } },
  { inicio: '2026-09-14', fim: '2026-09-20', respostas: 6, temas: { prazo_entrega: { mencoes: 2, reclamacoes: 1 } } },
  { inicio: '2026-09-21', fim: '2026-09-27', respostas: 7, temas: { prazo_entrega: { mencoes: 4, reclamacoes: 3 } } },
]

describe('Temas semana a semana', () => {
  const grafico = () =>
    mount(GraficoSemanal, {
      props: { semanas: SEMANAS, medida: 'mencoes', temas: [{ tema: 'prazo_entrega', rotulo: 'Prazo e entrega' }] },
      attachTo: document.body,
    })
  const dica = (w: VueWrapper) => w.find('.pointer-events-none.absolute')
  // Primeira semana no começo da área do gráfico (margem esquerda de 36 px).
  const xSemana = (i: number) => 36 + (i * (640 - 36 - 16)) / 2

  it('clique numa semana mostra aquela semana (não a última)', async () => {
    const w = grafico()
    await tocar(w, xSemana(0), 120)
    expect(dica(w).text()).toContain('Semana de 07/09 a 13/09')
  })

  it('toque mostra a semana tocada e a dica fica depois de levantar o dedo; o mouse saindo esconde', async () => {
    const w = grafico()
    await tocar(w, xSemana(1), 120, 'touch')
    expect(dica(w).text()).toContain('Semana de 14/09 a 20/09')
    ponteiro(w.get('svg').element, 'pointerleave', 0, 0, 'mouse')
    await nextTick()
    expect(dica(w).exists()).toBe(false)
  })

  it('o foco pelo teclado mostra a última semana', async () => {
    const w = grafico()
    await focarPeloTeclado(w.get('[role="group"]').element)
    expect(dica(w).text()).toContain('Semana de 21/09 a 27/09')
  })
})
