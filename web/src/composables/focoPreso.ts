import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const SELETOR_FOCAVEL = [
  'a[href]',
  'area[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

export function focaveis(raiz: HTMLElement): HTMLElement[] {
  return Array.from(raiz.querySelectorAll<HTMLElement>(SELETOR_FOCAVEL)).filter(
    (el) => !el.hasAttribute('inert') && el.getAttribute('aria-hidden') !== 'true' && el.offsetParent !== null,
  )
}

/**
 * Mantém o foco do teclado dentro de `raiz` enquanto `ativo` for true,
 * chama `aoEsc` com a tecla Esc e devolve o foco ao elemento anterior ao fechar.
 */
export function useFocoPreso(raiz: Ref<HTMLElement | null>, ativo: Ref<boolean>, aoEsc: () => void) {
  let anterior: HTMLElement | null = null

  function aoTeclar(e: KeyboardEvent) {
    if (!ativo.value || !raiz.value) return
    if (e.key === 'Escape') {
      e.stopPropagation()
      aoEsc()
      return
    }
    if (e.key !== 'Tab') return
    const lista = focaveis(raiz.value)
    if (!lista.length) {
      e.preventDefault()
      raiz.value.focus()
      return
    }
    const primeiro = lista[0]!
    const ultimo = lista[lista.length - 1]!
    const atual = document.activeElement
    if (e.shiftKey && (atual === primeiro || !raiz.value.contains(atual))) {
      e.preventDefault()
      ultimo.focus()
    } else if (!e.shiftKey && (atual === ultimo || !raiz.value.contains(atual))) {
      e.preventDefault()
      primeiro.focus()
    }
  }

  watch(
    ativo,
    async (aberto) => {
      if (aberto) {
        anterior = document.activeElement instanceof HTMLElement ? document.activeElement : null
        document.addEventListener('keydown', aoTeclar, true)
        await nextTick()
        if (!raiz.value) return
        const auto = raiz.value.querySelector<HTMLElement>('[autofocus],[data-autofoco]')
        ;(auto ?? focaveis(raiz.value)[0] ?? raiz.value).focus()
      } else {
        document.removeEventListener('keydown', aoTeclar, true)
        anterior?.focus?.()
        anterior = null
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => document.removeEventListener('keydown', aoTeclar, true))
}
