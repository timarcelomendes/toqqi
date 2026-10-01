import { ref } from 'vue'

/** Menu lateral recolhido (só ícones) no computador. A escolha fica guardada neste navegador. */
export const CHAVE_MENU_RECOLHIDO = 'toqqi.menu-recolhido'

function lerPreferencia(): boolean {
  try {
    return window.localStorage.getItem(CHAVE_MENU_RECOLHIDO) === '1'
  } catch {
    return false // navegador sem armazenamento: começa aberto
  }
}

const recolhido = ref(lerPreferencia())

export function useMenuLateral() {
  function definir(valor: boolean) {
    recolhido.value = valor
    try {
      if (valor) window.localStorage.setItem(CHAVE_MENU_RECOLHIDO, '1')
      else window.localStorage.removeItem(CHAVE_MENU_RECOLHIDO)
    } catch {
      /* navegador sem armazenamento: só não lembra */
    }
  }
  function alternar() {
    definir(!recolhido.value)
  }
  return { recolhido, definir, alternar }
}

/** Relê a preferência guardada (usado nos testes). */
export function recarregarMenuLateral() {
  recolhido.value = lerPreferencia()
}
