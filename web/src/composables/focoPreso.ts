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
 * Pilha das janelas abertas: só a de cima (a última aberta) responde ao Tab e ao Esc.
 * Assim uma confirmação aberta por cima de um painel não briga com ele pelo foco.
 */
const pilha: symbol[] = []

function tirarDaPilha(eu: symbol) {
  const i = pilha.lastIndexOf(eu)
  if (i >= 0) pilha.splice(i, 1)
}

/**
 * O Esc saiu de dentro de uma lista aberta (busca com sugestões, menu)? Então é dela: fecha a lista e a
 * janela fica (senão o que foi digitado se perde). Botões de mostrar/esconder, como "Filtros", também têm
 * aria-expanded, mas não abrem lista: nesses o Esc continua fechando a janela.
 */
export function escPertenceALista(alvo: EventTarget | null): boolean {
  if (!(alvo instanceof Element)) return false
  if (alvo.closest('[role="menu"], [role="listbox"]')) return true
  const expandido = alvo.closest('[aria-expanded="true"]')
  if (!expandido) return false
  const popup = expandido.getAttribute('aria-haspopup')
  return expandido.getAttribute('role') === 'combobox' || (popup !== null && popup !== 'false')
}

/** Devolve o foco a quem abriu a janela. Se foi um item de menu (que já fechou), volta para o botão do menu. */
function devolverFoco(el: HTMLElement | null) {
  if (!el || !el.isConnected) return
  const menu = el.closest<HTMLElement>('[role="menu"]')
  const gatilho = menu?.id
    ? Array.from(document.querySelectorAll<HTMLElement>('[aria-controls]')).find((g) => g.getAttribute('aria-controls') === menu.id)
    : undefined
  ;(gatilho ?? el).focus?.()
}

/**
 * Mantém o foco do teclado dentro de `raiz` enquanto `ativo` for true,
 * chama `aoEsc` com a tecla Esc e devolve o foco ao elemento anterior ao fechar.
 */
export function useFocoPreso(raiz: Ref<HTMLElement | null>, ativo: Ref<boolean>, aoEsc: () => void) {
  let anterior: HTMLElement | null = null
  const eu = Symbol('foco-preso')

  function aoTeclar(e: KeyboardEvent) {
    if (!ativo.value || !raiz.value) return
    if (pilha[pilha.length - 1] !== eu) return
    if (e.key === 'Escape') {
      if (escPertenceALista(e.target)) return
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
        tirarDaPilha(eu)
        pilha.push(eu)
        document.addEventListener('keydown', aoTeclar, true)
        await nextTick()
        if (!raiz.value) return
        const auto = raiz.value.querySelector<HTMLElement>('[autofocus],[data-autofoco]')
        ;(auto ?? focaveis(raiz.value)[0] ?? raiz.value).focus()
      } else {
        tirarDaPilha(eu)
        document.removeEventListener('keydown', aoTeclar, true)
        devolverFoco(anterior)
        anterior = null
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    tirarDaPilha(eu)
    document.removeEventListener('keydown', aoTeclar, true)
  })
}
