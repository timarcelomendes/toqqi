import { computed, ref } from 'vue'

/** Menu lateral recolhido (só ícones) no computador. A escolha fica guardada neste navegador. */
export const CHAVE_MENU_RECOLHIDO = 'toqqi.menu-recolhido'

function lerPreferencia(): boolean {
  try {
    return window.localStorage.getItem(CHAVE_MENU_RECOLHIDO) === '1'
  } catch {
    return false // navegador sem armazenamento: começa aberto
  }
}

const preferencia = ref(lerPreferencia())
/**
 * Etapa 5l: uma tela larga (o editor de formulário, com 3 colunas) pede o menu recolhido enquanto está aberta. Não
 * muda a preferência guardada; expandir pelo botão vale só para esta visita à tela.
 */
const recolhidoNaTela = ref(false)
const recolhido = computed(() => preferencia.value || recolhidoNaTela.value)

export function useMenuLateral() {
  function definir(valor: boolean) {
    preferencia.value = valor
    if (!valor) recolhidoNaTela.value = false
    try {
      if (valor) window.localStorage.setItem(CHAVE_MENU_RECOLHIDO, '1')
      else window.localStorage.removeItem(CHAVE_MENU_RECOLHIDO)
    } catch {
      /* navegador sem armazenamento: só não lembra */
    }
  }
  function alternar() {
    // Recolhido só por causa da tela: expandir não mexe na preferência guardada.
    if (recolhidoNaTela.value && !preferencia.value) {
      recolhidoNaTela.value = false
      return
    }
    definir(!preferencia.value)
  }
  /** A tela pede (ou devolve) o menu recolhido enquanto ela está aberta. */
  function recolherNaTela(valor: boolean) {
    recolhidoNaTela.value = valor
  }
  return { recolhido, definir, alternar, recolherNaTela }
}

/** Relê a preferência guardada (usado nos testes). */
export function recarregarMenuLateral() {
  preferencia.value = lerPreferencia()
  recolhidoNaTela.value = false
}
