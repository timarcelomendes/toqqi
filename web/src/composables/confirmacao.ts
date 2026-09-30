import { reactive } from 'vue'

export interface OpcoesConfirmacao {
  titulo: string
  mensagem?: string
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
