// Entrar com o Google (docs/api-login-google.md). O ID do cliente vem da API (GET /auth/google/config, uma vez por carga
// do site) e o script oficial do Google (Google Identity Services) só é carregado nas telas de entrar e de cadastro,
// quando há ID. Falhou (sem ID, bloqueador, sem internet): null, e a tela segue só com e-mail e senha.
import { authApi } from '@/api'

/** O pedaço do Google Identity Services que o Toqqi usa (o botão oficial e o retorno com o token). */
export interface GoogleId {
  initialize(opcoes: {
    client_id: string
    callback: (resposta: { credential?: string }) => void
    ux_mode?: 'popup'
    auto_select?: boolean
    context?: 'signin' | 'signup' | 'use'
    itp_support?: boolean
  }): void
  renderButton(
    alvo: HTMLElement,
    opcoes: {
      type?: 'standard'
      theme?: 'outline' | 'filled_blue' | 'filled_black'
      size?: 'large' | 'medium' | 'small'
      text?: 'signin_with' | 'signup_with' | 'continue_with'
      shape?: 'rectangular' | 'pill'
      logo_alignment?: 'left' | 'center'
      width?: number
      locale?: string
    },
  ): void
}

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleId } }
  }
}

export const URL_SCRIPT_GOOGLE = 'https://accounts.google.com/gsi/client'
const ESPERA_MAXIMA = 10_000

let idCliente: Promise<string | null> | null = null
let script: Promise<GoogleId | null> | null = null

/** O ID do cliente do Google (null = sem o botão). Uma chamada por carga do site; falhou, tenta de novo na próxima. */
export function idClienteGoogle(): Promise<string | null> {
  idCliente ??= authApi
    .googleConfig()
    .then((r) => r?.client_id || null)
    .catch(() => {
      idCliente = null
      return null
    })
  return idCliente
}

/** O script do Google, uma vez só; null se não carregar em 10 s. */
export function carregarGoogle(): Promise<GoogleId | null> {
  const pronto = window.google?.accounts?.id
  if (pronto) return Promise.resolve(pronto)
  script ??= new Promise<GoogleId | null>((resolve) => {
    const el = document.createElement('script')
    el.src = URL_SCRIPT_GOOGLE
    el.async = true
    el.defer = true
    const desistir = setTimeout(() => terminar(null), ESPERA_MAXIMA)
    function terminar(gid: GoogleId | null) {
      clearTimeout(desistir)
      if (!gid) script = null // a próxima tela tenta de novo
      resolve(gid)
    }
    el.onload = () => terminar(window.google?.accounts?.id ?? null)
    el.onerror = () => {
      el.remove()
      terminar(null)
    }
    document.head.appendChild(el)
  })
  return script
}

/** Testes: esquece o ID e o script. */
export function esquecerGoogle() {
  idCliente = null
  script = null
}
