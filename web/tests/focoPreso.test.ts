import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { useFocoPreso } from '@/composables/focoPreso'
import { liberarRolagem, travarRolagem } from '@/composables/rolagem'

enableAutoUnmount(afterEach)

afterEach(() => {
  document.body.innerHTML = ''
  document.body.style.overflow = ''
})

function janela(aoEsc: () => void) {
  return defineComponent({
    props: { aberta: Boolean },
    setup(props) {
      const raiz = ref<HTMLElement | null>(null)
      const ativo = ref(props.aberta)
      useFocoPreso(raiz, ativo, aoEsc)
      return { raiz, ativo }
    },
    render() {
      return h('div', { ref: 'raiz' }, [h('button', 'Um'), h('button', 'Dois')])
    },
  })
}

describe('janelas umas sobre as outras', () => {
  it('Esc fecha só a de cima (ex.: confirmação aberta por cima do painel lateral)', async () => {
    const escPainel = vi.fn()
    const escConfirmacao = vi.fn()
    const painel = mount(janela(escPainel), { attachTo: document.body })
    const confirmacao = mount(janela(escConfirmacao), { attachTo: document.body })
    ;(painel.vm as unknown as { ativo: boolean }).ativo = true
    await nextTick()
    ;(confirmacao.vm as unknown as { ativo: boolean }).ativo = true
    await nextTick()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(escConfirmacao).toHaveBeenCalledTimes(1)
    expect(escPainel).not.toHaveBeenCalled()

    // Fechou a confirmação: o Esc volta a ser do painel.
    ;(confirmacao.vm as unknown as { ativo: boolean }).ativo = false
    await nextTick()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(escPainel).toHaveBeenCalledTimes(1)
    expect(escConfirmacao).toHaveBeenCalledTimes(1)
  })

  it('Esc dentro de uma lista aberta (busca com sugestões, menu) fecha só a lista, não a janela', async () => {
    const escPainel = vi.fn()
    const Janela = defineComponent({
      setup() {
        const raiz = ref<HTMLElement | null>(null)
        useFocoPreso(raiz, ref(true), escPainel)
        return { raiz }
      },
      render() {
        return h('div', { ref: 'raiz' }, [
          h('input', { id: 'busca', role: 'combobox', 'aria-expanded': 'true' }),
          h('div', { role: 'menu' }, [h('button', { id: 'item', role: 'menuitem' }, 'Mover')]),
          h('button', { id: 'gatilho', 'aria-haspopup': 'menu', 'aria-expanded': 'true' }, 'Mais'),
          h('button', { id: 'filtros', 'aria-expanded': 'true' }, 'Filtros'),
          h('input', { id: 'nome' }),
        ])
      },
    })
    mount(Janela, { attachTo: document.body })
    await nextTick()
    const esc = (id: string) => {
      const ev = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
      document.getElementById(id)!.dispatchEvent(ev)
    }
    // A lista recebe o Esc (o evento chega até ela) e a janela fica aberta.
    const doCampo = vi.fn()
    document.getElementById('busca')!.addEventListener('keydown', doCampo)
    esc('busca')
    expect(doCampo).toHaveBeenCalledTimes(1)
    esc('item')
    esc('gatilho')
    expect(escPainel).not.toHaveBeenCalled()

    // Lista fechada, botão de mostrar/esconder ou campo comum: o Esc fecha a janela.
    document.getElementById('busca')!.setAttribute('aria-expanded', 'false')
    esc('busca')
    esc('filtros')
    esc('nome')
    expect(escPainel).toHaveBeenCalledTimes(3)
  })

  it('a rolagem da página só volta quando a última janela fecha', () => {
    travarRolagem()
    travarRolagem()
    liberarRolagem()
    expect(document.body.style.overflow).toBe('hidden')
    liberarRolagem()
    expect(document.body.style.overflow).toBe('')
    liberarRolagem() // a mais não deixa o contador negativo
    travarRolagem()
    expect(document.body.style.overflow).toBe('hidden')
    liberarRolagem()
  })
})
