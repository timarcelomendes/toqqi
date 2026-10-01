// Regras puras da página /sair/:token (sem Vue). Fica fora do componente para testar e manter leve.

export const MOTIVOS_RAPIDOS = ['Recebo pesquisas demais', 'Não sou cliente', 'Não quero informar'] as const
export type MotivoRapido = (typeof MOTIVOS_RAPIDOS)[number]
export const LIMITE_MOTIVO = 300

/** Token do caminho /sair/{token}; null se o endereço não tiver um. */
export function tokenDoCaminho(caminho: string): string | null {
  const m = caminho.match(/^\/sair\/([^/?#]+)/)
  if (!m) return null
  try {
    return decodeURIComponent(m[1]!)
  } catch {
    return null
  }
}

/**
 * Motivo enviado à API (até 300 caracteres), juntando o motivo rápido e o texto livre.
 * "Não quero informar" sem texto não manda motivo.
 */
export function montarMotivo(rapido: MotivoRapido | null, texto: string): string | undefined {
  const livre = texto.trim().replace(/\s+/g, ' ')
  const escolhido = rapido && rapido !== 'Não quero informar' ? rapido : ''
  const motivo = escolhido && livre ? `${escolhido}: ${livre}` : escolhido || livre
  return motivo ? motivo.slice(0, LIMITE_MOTIVO) : undefined
}
