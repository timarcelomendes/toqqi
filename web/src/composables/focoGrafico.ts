// Foco nos gráficos de SVG (evolução do NPS, matriz NPS × valor, prioridades, temas semana a semana): o contêiner do
// gráfico é focável para quem usa o teclado (as setas mostram cada ponto). Só o foco que veio do teclado escolhe um
// ponto sozinho; com mouse ou toque, vale o que está embaixo do ponteiro (senão um clique num espaço vazio mostraria —
// ou abriria — o primeiro ponto).

export interface FocoGrafico {
  /** No `pointerdown` do contêiner focável (antes do foco que o clique ou o toque provocam). */
  aoApertar: () => void
  /** No `blur`: um clique que não trouxe foco novo não deixa a marca para o próximo Tab. */
  aoSair: () => void
  /** No `focus`: verdadeiro quando o foco veio do teclado. */
  veioDoTeclado: (e: FocusEvent) => boolean
}

export function usarFocoGrafico(): FocoGrafico {
  let ponteiro = false
  return {
    aoApertar: () => {
      ponteiro = true
    },
    aoSair: () => {
      ponteiro = false
    },
    veioDoTeclado: (e) => {
      if (ponteiro) {
        ponteiro = false
        return false
      }
      // Voltar para a janela devolve o foco ao gráfico: :focus-visible diz se o foco era do teclado.
      const el = e.currentTarget
      if (!(el instanceof Element)) return true
      try {
        return el.matches(':focus-visible')
      } catch {
        return true
      }
    },
  }
}

/** Toque não tem "passar por cima": ao levantar o dedo, a dica do ponto tocado continua na tela. */
export function saiuComMouse(e: PointerEvent): boolean {
  return e.pointerType !== 'touch'
}
