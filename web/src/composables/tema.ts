import { ref } from 'vue'

export type Tema = 'claro' | 'escuro'
const CHAVE = 'toqqi.tema'

function temaInicial(): Tema {
  if (typeof document === 'undefined') return 'claro'
  return document.documentElement.classList.contains('dark') ? 'escuro' : 'claro'
}

const tema = ref<Tema>(temaInicial())

export function useTema() {
  function definir(novo: Tema) {
    tema.value = novo
    document.documentElement.classList.toggle('dark', novo === 'escuro')
    try {
      localStorage.setItem(CHAVE, novo)
    } catch {
      /* navegador sem armazenamento: só não lembra */
    }
  }
  function alternar() {
    definir(tema.value === 'escuro' ? 'claro' : 'escuro')
  }
  return { tema, definir, alternar }
}
