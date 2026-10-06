/**
 * Entrada dos guias do site (reduzir-churn.html, clientes-insatisfeitos.html, customer-success.html). O texto já está
 * pronto no HTML; aqui só entram a fonte, o visual, a origem da visita (para o cadastro) e o "Abrir o Toqqi" para quem já
 * entrou. Nenhuma requisição: nem à API do Toqqi.
 */
import '@fontsource/plus-jakarta-sans/latin-400.css'
import '@fontsource/plus-jakarta-sans/latin-600.css'
import '@fontsource/plus-jakarta-sans/latin-700.css'
import '@fontsource/plus-jakarta-sans/latin-800.css'
import './site.css'
import './guia.css'
import { temSessao } from './logica'
import { guardarOrigem } from './origem'

function lerSessao(): string | null {
  for (const nome of ['localStorage', 'sessionStorage'] as const) {
    try {
      const v = window[nome].getItem('toqqi.sessao')
      if (v) return v
    } catch {
      /* armazenamento bloqueado: segue como visitante */
    }
  }
  return null
}

export function iniciarGuia(): void {
  guardarOrigem() // a origem do anúncio (utm_*) vale mais que a dos botões do guia
  if (!temSessao(lerSessao())) return
  const entrar = document.querySelector<HTMLAnchorElement>('[data-entrar]')
  if (entrar) {
    entrar.textContent = 'Abrir o Toqqi'
    entrar.href = '/inicio'
  }
}

iniciarGuia()
