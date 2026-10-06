import { dataValida, faixa, numeroDoTexto, respondivel } from './logica'
import type { Pergunta, ValorResposta } from './tipos'

export { dataValida }

export const LIMITE_TEXTO_CURTO = 300
export const LIMITE_COMENTARIO = 4000

export function respostaVazia(v: ValorResposta | null | undefined): boolean {
  if (v === undefined || v === null) return true
  if (typeof v === 'string') return !v.trim()
  if (Array.isArray(v)) return v.length === 0
  return false
}

export function emailValido(v: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim())
}

/** Número como a API lê (docs/api-etapa-5l.md §2.1): "1.250,5", "12,5", "-3" e "12.5" valem. */
export function numeroValido(v: string): boolean {
  const n = numeroDoTexto(v)
  return n !== null && Number.isFinite(n)
}

/**
 * Valida uma resposta como o servidor valida: obrigatória, faixa das notas,
 * formatos (e-mail, número, telefone com 8+ dígitos, data AAAA-MM-DD), opções existentes e o máximo de opções.
 * Devolve a mensagem para mostrar ou null. Conteúdo e quebra de página não têm resposta.
 */
export function validarResposta(p: Pergunta, v: ValorResposta | null | undefined): string | null {
  if (!respondivel(p.tipo)) return null
  if (respostaVazia(v)) {
    if (!p.obrigatoria) return null
    if (p.tipo === 'escolha_multipla') return 'Escolha pelo menos uma opção.'
    if (['nps', 'csat', 'estrelas', 'escala', 'escolha_unica', 'sim_nao'].includes(p.tipo)) return 'Escolha uma opção para continuar.'
    return 'Responda esta pergunta para continuar.'
  }
  switch (p.tipo) {
    case 'nps':
    case 'csat':
    case 'estrelas':
    case 'escala': {
      const { min, max } = faixa(p)
      if (typeof v !== 'number' || !Number.isInteger(v) || v < min || v > max) return `Escolha uma nota de ${min} a ${max}.`
      return null
    }
    case 'texto_curto': {
      const t = String(v).trim()
      if (t.length > LIMITE_TEXTO_CURTO) return `Use no máximo ${LIMITE_TEXTO_CURTO} caracteres.`
      if (p.formato === 'email' && !emailValido(t)) return 'Confira o e-mail: parece que falta alguma parte.'
      if (p.formato === 'numero' && !numeroValido(t)) return 'Digite só números.'
      if (p.formato === 'telefone' && t.replace(/\D/g, '').length < 8) return 'Confira o telefone: faltam números.'
      return null
    }
    case 'comentario':
      return String(v).length > LIMITE_COMENTARIO ? `Use no máximo ${LIMITE_COMENTARIO} caracteres.` : null
    case 'escolha_unica':
      return typeof v === 'string' && (p.opcoes ?? []).includes(v) ? null : 'Escolha uma das opções.'
    case 'escolha_multipla': {
      if (!Array.isArray(v) || !v.every((x) => (p.opcoes ?? []).includes(x))) return 'Escolha entre as opções da lista.'
      const max = p.max_selecoes
      return typeof max === 'number' && max > 0 && v.length > max ? `Escolha no máximo ${max} opções.` : null
    }
    case 'sim_nao':
      return typeof v === 'boolean' ? null : 'Escolha sim ou não.'
    case 'data':
      return typeof v === 'string' && dataValida(v) ? null : 'Confira a data.'
    default:
      return null
  }
}

/** Valida uma lista de perguntas; devolve {id: mensagem} só das que têm erro. */
export function validarPerguntas(perguntas: Pergunta[], respostas: Record<string, ValorResposta>): Record<string, string> {
  const erros: Record<string, string> = {}
  for (const p of perguntas) {
    const e = validarResposta(p, respostas[p.id])
    if (e) erros[p.id] = e
  }
  return erros
}
