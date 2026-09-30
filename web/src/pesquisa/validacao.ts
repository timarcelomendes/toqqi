import { faixa } from './logica'
import type { Pergunta, ValorResposta } from './tipos'

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

export function dataValida(v: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return false
  const [a, m, d] = v.split('-').map(Number) as [number, number, number]
  const dt = new Date(Date.UTC(a, m - 1, d))
  return dt.getUTCFullYear() === a && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d
}

/**
 * Valida uma resposta como o servidor valida: obrigatória, faixa das notas,
 * formatos (e-mail, número, telefone com 8+ dígitos, data AAAA-MM-DD) e opções existentes.
 * Devolve a mensagem para mostrar ou null.
 */
export function validarResposta(p: Pergunta, v: ValorResposta | null | undefined): string | null {
  if (p.tipo === 'quebra_pagina') return null
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
      if (p.formato === 'numero' && !/^-?\d+([.,]\d+)?$/.test(t)) return 'Digite só números.'
      if (p.formato === 'telefone' && t.replace(/\D/g, '').length < 8) return 'Confira o telefone: faltam números.'
      return null
    }
    case 'comentario':
      return String(v).length > LIMITE_COMENTARIO ? `Use no máximo ${LIMITE_COMENTARIO} caracteres.` : null
    case 'escolha_unica':
      return typeof v === 'string' && (p.opcoes ?? []).includes(v) ? null : 'Escolha uma das opções.'
    case 'escolha_multipla':
      return Array.isArray(v) && v.every((x) => (p.opcoes ?? []).includes(x)) ? null : 'Escolha entre as opções da lista.'
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
