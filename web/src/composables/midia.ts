import { onBeforeUnmount, ref, type Ref } from 'vue'

/**
 * Acompanha uma media query (ex.: '(min-width: 1280px)'). Sem `matchMedia` (testes), fica em `padrao`.
 * Use dentro de `setup` (para de ouvir ao desmontar).
 */
export function useMidia(consulta: string, padrao = true): Ref<boolean> {
  const casa = ref(padrao)
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return casa
  const mq = window.matchMedia(consulta)
  casa.value = mq.matches
  const ouvir = (e: MediaQueryListEvent) => (casa.value = e.matches)
  mq.addEventListener?.('change', ouvir)
  onBeforeUnmount(() => mq.removeEventListener?.('change', ouvir))
  return casa
}
