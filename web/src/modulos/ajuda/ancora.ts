// Âncoras da Ajuda (docs/api-etapa-5b.md §6.1 e docs/ajuda-jornadas.md §3): levar a seção de um tópico, ou o cartão de
// uma jornada, para a vista e pôr o foco no título dele. Os dois usam os mesmos ids: `ajuda-<id>` e `t-ajuda-<id>`.
import { nextTick } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { semMovimento } from '@/modulos/assistente/logica'
import { ID_JORNADAS } from './logica'

export const comportamento = (): ScrollBehavior => (semMovimento() ? 'auto' : 'smooth')

/** Leva a seção (ou o cartão da jornada) da âncora para a vista e põe o foco no título dela (leitores de tela começam ali). */
export function irParaSecao(ancora: string) {
  let id = ancora.replace(/^#/, '')
  try {
    id = decodeURIComponent(id)
  } catch {
    /* âncora malformada: usa como veio */
  }
  if (!id) return
  const secao = document.getElementById(`ajuda-${id}`)
  if (!secao) return
  secao.scrollIntoView?.({ block: 'start', behavior: comportamento() })
  document.getElementById(`t-ajuda-${id}`)?.focus({ preventScroll: true })
}

/** O cartão de uma jornada: /ajuda/jornadas#<id>. */
export const destinoJornada = (id: string): RouteLocationRaw => ({ path: `/ajuda/${ID_JORNADAS}`, hash: `#${encodeURIComponent(id)}` })

/** A seção de um tópico: /ajuda/<topico>#<secao>. */
export const destinoSecao = (topico: string, secao: string): RouteLocationRaw => ({
  path: `/ajuda/${encodeURIComponent(topico)}`,
  hash: `#${encodeURIComponent(secao)}`,
})

export type Navegar = (e?: MouseEvent) => Promise<unknown>

/**
 * Clique num link para uma âncora da Ajuda: navega e leva ao destino, também quando o endereço já é esse (aí o router
 * não muda nada e a tela não rolaria sozinha). Ctrl+clique e afins ficam com o navegador (outra aba).
 */
export async function abrirAncora(navegar: Navegar, e: MouseEvent, id: string) {
  await navegar(e)
  if (!e.defaultPrevented) return
  await nextTick()
  irParaSecao(id)
}
