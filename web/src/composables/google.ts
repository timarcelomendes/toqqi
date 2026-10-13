// Entrar com o Google (docs/api-login-google.md). O ID do cliente vem da API (GET /auth/google/config, uma vez por carga
// do site) e o script oficial do Google (Google Identity Services) só é carregado nas telas de entrar e de cadastro,
// quando há ID. Falhou (sem ID, bloqueador, sem internet): null, e a tela segue só com e-mail e senha.
// Desde 13/10/2026 o botão é do Toqqi e usa o modelo de token do Google (`google.accounts.oauth2.initTokenClient`): a
// janela do Google devolve um token de acesso, que a API confere com o próprio Google.
import { authApi } from '@/api'

/** O que a janela do Google devolve: o token de acesso ou, se a pessoa recusou, o erro (ex.: "access_denied"). */
export interface RespostaTokenGoogle {
  access_token?: string
  expires_in?: number | string
  scope?: string
  error?: string
  error_description?: string
}

/** A janela do Google não abriu (bloqueador de janelas), foi fechada antes do fim ou outro erro. */
export interface ErroJanelaGoogle {
  type: 'popup_failed_to_open' | 'popup_closed' | 'unknown' | string
}

export interface ClienteTokenGoogle {
  /** Abre a janela do Google. Precisa ser chamado direto no clique (senão o navegador bloqueia a janela). */
  requestAccessToken(opcoes?: { prompt?: string }): void
}

/** O pedaço do Google Identity Services que o Toqqi usa: o modelo de token. */
export interface GoogleOauth2 {
  initTokenClient(opcoes: {
    client_id: string
    scope: string
    callback: (resposta: RespostaTokenGoogle) => void
    error_callback?: (erro: ErroJanelaGoogle) => void
    prompt?: string
  }): ClienteTokenGoogle
}

declare global {
  interface Window {
    google?: { accounts?: { oauth2?: GoogleOauth2 } }
  }
}

export const URL_SCRIPT_GOOGLE = 'https://accounts.google.com/gsi/client'
/** O "G" oficial do Google, servido pelo Google (as regras de marca pedem o logotipo original no botão). */
export const URL_LOGO_GOOGLE = 'https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg'
/** Nome, e-mail e o identificador da conta: nada de Gmail, Drive, agenda ou contatos. */
export const ESCOPOS_GOOGLE = 'openid email profile'
const ESPERA_MAXIMA = 10_000

let idCliente: Promise<string | null> | null = null
let script: Promise<GoogleOauth2 | null> | null = null

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
export function carregarGoogle(): Promise<GoogleOauth2 | null> {
  const pronto = window.google?.accounts?.oauth2
  if (pronto) return Promise.resolve(pronto)
  script ??= new Promise<GoogleOauth2 | null>((resolve) => {
    const el = document.createElement('script')
    el.src = URL_SCRIPT_GOOGLE
    el.async = true
    el.defer = true
    const desistir = setTimeout(() => terminar(null), ESPERA_MAXIMA)
    function terminar(g: GoogleOauth2 | null) {
      clearTimeout(desistir)
      if (!g) script = null // a próxima tela tenta de novo
      resolve(g)
    }
    el.onload = () => terminar(window.google?.accounts?.oauth2 ?? null)
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
