import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/**
 * Barras de salvar presas ao rodapé da tela (marcadas com `data-barra-fixa`, como a de Configurações › Empresa): quanto
 * o botão e o painel do assistente sobem para não cobrir os botões delas. Só conta a barra encostada no rodapé; a que
 * está no meio do conteúdo (página curta, ou rolada até o fim) não cobre o canto.
 */
export function useFolgaDasBarras(): Ref<number> {
  const folga = ref(0)
  let quadro: number | null = null
  let observador: MutationObserver | null = null

  const proximoQuadro = (f: () => void): number =>
    typeof window.requestAnimationFrame === 'function' ? window.requestAnimationFrame(f) : window.setTimeout(f, 16)

  function medir() {
    quadro = null
    const altura = window.innerHeight
    let maior = 0
    for (const el of document.querySelectorAll<HTMLElement>('[data-barra-fixa]')) {
      const r = el.getBoundingClientRect()
      if (r.height > 0 && r.top < altura && r.bottom >= altura - 48) maior = Math.max(maior, Math.ceil(altura - r.top))
    }
    if (maior !== folga.value) folga.value = maior
  }
  function agendar() {
    if (quadro === null) quadro = proximoQuadro(medir)
  }

  onMounted(() => {
    agendar()
    window.addEventListener('scroll', agendar, { passive: true })
    window.addEventListener('resize', agendar)
    // A barra entra com uma transição (de baixo para cima): mede de novo quando ela termina.
    document.addEventListener('transitionend', agendar, true)
    if (typeof MutationObserver === 'function') {
      observador = new MutationObserver(agendar)
      observador.observe(document.getElementById('conteudo') ?? document.body, { childList: true, subtree: true })
    }
  })
  onBeforeUnmount(() => {
    window.removeEventListener('scroll', agendar)
    window.removeEventListener('resize', agendar)
    document.removeEventListener('transitionend', agendar, true)
    observador?.disconnect()
    if (quadro !== null) {
      if (typeof window.cancelAnimationFrame === 'function') window.cancelAnimationFrame(quadro)
      window.clearTimeout(quadro)
    }
  })

  return folga
}
