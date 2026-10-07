// Regras puras das páginas /sair/:token e /sair (sem Vue). Ficam fora dos componentes para testar e manter leve.

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

/** A página /sair sem token (pedir o link por e-mail): "/sair" ou "/sair/". */
export function ehPedirLink(caminho: string): boolean {
  return /^\/sair\/?$/.test(caminho)
}

/** O que falta no e-mail digitado na página /sair, ou null se dá para pedir o link (a API confere de verdade). */
export function conferirEmail(email: string): string | null {
  const e = email.trim()
  if (!e) return 'Digite o seu e-mail.'
  if (e.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return 'Confira o e-mail: ele precisa ser como nome@empresa.com.br.'
  return null
}
