// Rolagem ao navegar (filtros e página no endereço não jogam a tela para o topo; voltar devolve a posição, mesmo
// com os dados chegando depois), paginação que leva ao começo da lista e os botões segmentados (rádios nativos).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import { quandoCouber, rolagemAoNavegar } from '@/router'

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('rolagem ao navegar', () => {
  const rota = (path: string, name: string, meta: Record<string, unknown> = {}) => ({ path, name, meta })

  it('voltar e avançar devolvem a posição salva', () => {
    expect(rolagemAoNavegar(rota('/respostas', 'respostas'), rota('/inicio', 'inicio'), { left: 0, top: 640 })).toEqual({ left: 0, top: 640 })
  })

  it('mudar só a query (filtros, página, painel "Analisar") não rola', () => {
    expect(rolagemAoNavegar(rota('/relatorios/empresas', 'relatorios'), rota('/relatorios/empresas', 'relatorios'), null)).toBe(false)
    expect(rolagemAoNavegar(rota('/respostas', 'respostas'), rota('/respostas', 'respostas'), null)).toBe(false)
  })

  it('outra página (ou outra aba dos relatórios) vai para o topo', () => {
    expect(rolagemAoNavegar(rota('/relatorios/historico', 'relatorios'), rota('/relatorios/empresas', 'relatorios'), null)).toEqual({ top: 0 })
    expect(rolagemAoNavegar(rota('/contatos', 'contatos'), rota('/respostas', 'respostas'), null)).toEqual({ top: 0 })
  })

  it('abrir e fechar o painel de uma ação (rota com manterRolagem) não rola', () => {
    const meta = { manterRolagem: true }
    expect(rolagemAoNavegar(rota('/planos-de-acao/12', 'planos-de-acao', meta), rota('/planos-de-acao', 'planos-de-acao'), null)).toBe(false)
    expect(rolagemAoNavegar(rota('/planos-de-acao/12', 'planos-de-acao', meta), rota('/inicio', 'inicio'), null)).toEqual({ top: 0 })
  })
})

describe('voltar: espera a página crescer até caber a posição salva', () => {
  let altura = 0
  beforeEach(() => {
    vi.useFakeTimers()
    altura = 900 // a tela recém-montada, ainda sem os dados
    Object.defineProperty(document.documentElement, 'scrollHeight', { configurable: true, get: () => altura })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
  })
  afterEach(() => {
    vi.useRealTimers()
    Reflect.deleteProperty(document.documentElement, 'scrollHeight')
  })
  const resolvido = (p: Promise<unknown>) => {
    const estado = { pronto: false, valor: undefined as unknown }
    void p.then((v) => Object.assign(estado, { pronto: true, valor: v }))
    return estado
  }

  it('devolve a posição quando os dados chegam e a página cresce', async () => {
    const r = resolvido(quandoCouber({ left: 0, top: 1300 }))
    await vi.advanceTimersByTimeAsync(300)
    expect(r.pronto).toBe(false)
    altura = 2600
    await vi.advanceTimersByTimeAsync(60)
    expect(r).toEqual({ pronto: true, valor: { left: 0, top: 1300 } })
  })

  it('com a página já alta, devolve na hora', async () => {
    altura = 3000
    const r = resolvido(quandoCouber({ left: 0, top: 1300 }))
    await vi.advanceTimersByTimeAsync(0)
    expect(r.valor).toEqual({ left: 0, top: 1300 })
  })

  it('se a pessoa rolar enquanto espera, não mexe mais na rolagem', async () => {
    const r = resolvido(quandoCouber({ left: 0, top: 1300 }))
    window.dispatchEvent(new Event('wheel'))
    altura = 2600
    await vi.advanceTimersByTimeAsync(60)
    expect(r).toEqual({ pronto: true, valor: false })
  })

  it('desiste de esperar depois do limite e devolve a posição (o navegador corta no fim da página)', async () => {
    const r = resolvido(quandoCouber({ left: 0, top: 1300 }, 2000))
    await vi.advanceTimersByTimeAsync(1900)
    expect(r.pronto).toBe(false)
    await vi.advanceTimersByTimeAsync(200)
    expect(r.valor).toEqual({ left: 0, top: 1300 })
  })
})

describe('paginação', () => {
  function montar(topoDaLista: number) {
    const rolar = vi.fn()
    Element.prototype.scrollIntoView = rolar
    const Lista = defineComponent({
      setup() {
        const pagina = ref(1)
        return () =>
          h('section', { id: 'lista' }, [
            h('p', 'itens'),
            h(Paginacao, { modelValue: pagina.value, 'onUpdate:modelValue': (p: number) => (pagina.value = p), total: 120, porPagina: 50 }),
          ])
      },
    })
    const w = mount(Lista, { attachTo: document.body })
    vi.spyOn(w.get('#lista').element, 'getBoundingClientRect').mockReturnValue({ top: topoDaLista } as DOMRect)
    return { w, rolar }
  }

  it('trocar de página leva a tela ao começo da lista quando ele ficou para cima', async () => {
    const { w, rolar } = montar(-900)
    await w.findAll('button').find((b) => b.text().includes('Próxima'))!.trigger('click')
    expect(w.text()).toContain('Página 2 de 3')
    expect(rolar).toHaveBeenCalledTimes(1)
    expect(rolar.mock.instances[0]).toBe(w.get('#lista').element)
    expect(rolar.mock.calls[0]![0]).toMatchObject({ block: 'start' })
  })

  it('com o começo da lista à vista, não rola', async () => {
    const { w, rolar } = montar(120)
    await w.findAll('button').find((b) => b.text().includes('Próxima'))!.trigger('click')
    expect(w.text()).toContain('Página 2 de 3')
    expect(rolar).not.toHaveBeenCalled()
  })

  it('numa caixa com rolagem própria (janela modal), volta a caixa ao começo e não mexe na página', async () => {
    const { w, rolar } = montar(140)
    const caixa = w.get('#lista').element as HTMLElement
    const rolarCaixa = vi.fn()
    Object.defineProperties(caixa, {
      scrollHeight: { value: 2400, configurable: true },
      clientHeight: { value: 600, configurable: true },
      scrollTop: { value: 1800, configurable: true, writable: true },
      scrollTo: { value: rolarCaixa, configurable: true },
    })
    await w.findAll('button').find((b) => b.text().includes('Próxima'))!.trigger('click')
    expect(rolarCaixa).toHaveBeenCalledTimes(1)
    expect(rolarCaixa.mock.calls[0]![0]).toMatchObject({ top: 0 })
    expect(rolar).not.toHaveBeenCalled()
  })
})

describe('botões segmentados', () => {
  it('são rádios nativos do mesmo grupo, com legenda, ligados ao v-model', async () => {
    const valor = ref('b')
    const w = mount(BotoesSegmentados, {
      props: {
        opcoes: [
          { valor: 'a', rotulo: 'Motorista' },
          { valor: 'b', rotulo: 'Rota' },
          { valor: 'c', rotulo: 'Filial' },
        ],
        rotulo: 'Agrupar por',
        modelValue: valor.value,
        'onUpdate:modelValue': (v: string) => {
          valor.value = v
          w.setProps({ modelValue: v })
        },
      },
    })
    expect(w.get('legend').text()).toBe('Agrupar por')
    const radios = w.findAll<HTMLInputElement>('input[type="radio"]')
    expect(radios).toHaveLength(3)
    expect(new Set(radios.map((r) => r.element.name)).size).toBe(1)
    expect(radios.map((r) => r.element.checked)).toEqual([false, true, false])
    // Cada opção tem o nome escrito (é o rótulo do rádio).
    expect(w.findAll('label').map((l) => l.text())).toEqual(['Motorista', 'Rota', 'Filial'])
    await radios[2]!.setValue(true)
    expect(valor.value).toBe('c')
  })
})
