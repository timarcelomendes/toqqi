import { reactive } from 'vue'

/** Pedaço de um parágrafo extra do diálogo: texto, ou link interno do site (fecha o diálogo ao clicar). */
export type PedacoConfirmacao = string | { texto: string; para: string }

export interface OpcoesConfirmacao {
  titulo: string
  mensagem?: string
  /** Parágrafo extra, abaixo da mensagem, que pode ter links internos (texto puro, sem HTML). */
  complemento?: PedacoConfirmacao[]
  confirmar?: string
  cancelar?: string
  perigo?: boolean
}

interface EstadoConfirmacao extends OpcoesConfirmacao {
  aberto: boolean
  resolver: ((ok: boolean) => void) | null
}

export const estadoConfirmacao = reactive<EstadoConfirmacao>({
  aberto: false,
  titulo: '',
  resolver: null,
})

/** Abre o diálogo de confirmação e resolve com true (confirmou) ou false. */
export function confirmar(opcoes: OpcoesConfirmacao): Promise<boolean> {
  estadoConfirmacao.resolver?.(false)
  return new Promise((resolve) => {
    Object.assign(estadoConfirmacao, {
      confirmar: undefined,
      cancelar: undefined,
      mensagem: undefined,
      complemento: undefined,
      perigo: false,
      ...opcoes,
      aberto: true,
      resolver: resolve,
    })
  })
}

export function responderConfirmacao(ok: boolean): void {
  const r = estadoConfirmacao.resolver
  estadoConfirmacao.resolver = null
  estadoConfirmacao.aberto = false
  r?.(ok)
}
