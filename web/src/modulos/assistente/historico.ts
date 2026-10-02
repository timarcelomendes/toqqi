// A conversa com o assistente fica só no navegador (docs/api-etapa-5b.md §6.2): sessionStorage, uma por conta e
// usuário, com as últimas 20 mensagens. "Nova conversa" apaga a da pessoa; sair apaga todas.
import type { AtalhoAssistente, PapelMensagem } from '@/api/tipos'
import { MENSAGENS_GUARDADAS } from './logica'

export const PREFIXO_CONVERSA = 'toqqi.assistente.'

export interface MensagemGuardada {
  papel: PapelMensagem
  texto: string
  /** Só nas respostas. */
  sugestoes?: string[]
  atalhos?: AtalhoAssistente[]
}

export function chaveConversa(contaId: number | string, usuarioId: number | string): string {
  return `${PREFIXO_CONVERSA}${contaId}.${usuarioId}`
}

function armazenamento(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

const ehTexto = (v: unknown): v is string => typeof v === 'string'

function lerMensagem(m: unknown): MensagemGuardada | null {
  if (!m || typeof m !== 'object') return null
  const r = m as Record<string, unknown>
  if ((r.papel !== 'usuario' && r.papel !== 'assistente') || !ehTexto(r.texto) || !r.texto.trim()) return null
  const msg: MensagemGuardada = { papel: r.papel, texto: r.texto }
  if (r.papel === 'assistente') {
    msg.sugestoes = Array.isArray(r.sugestoes) ? r.sugestoes.filter(ehTexto).slice(0, 3) : []
    msg.atalhos = Array.isArray(r.atalhos)
      ? r.atalhos.filter((a): a is AtalhoAssistente => !!a && typeof a === 'object' && ehTexto((a as AtalhoAssistente).chave)).slice(0, 2)
      : []
  }
  return msg
}

/** A conversa guardada (vazia se não houver ou se o dado estiver corrompido). */
export function lerConversa(chave: string): MensagemGuardada[] {
  try {
    const bruto = armazenamento()?.getItem(chave)
    const lista = bruto ? (JSON.parse(bruto) as unknown) : []
    return Array.isArray(lista)
      ? lista.map(lerMensagem).filter((m): m is MensagemGuardada => !!m).slice(-MENSAGENS_GUARDADAS)
      : []
  } catch {
    return []
  }
}

export function guardarConversa(chave: string, mensagens: readonly MensagemGuardada[]): void {
  try {
    const ultimas = mensagens.slice(-MENSAGENS_GUARDADAS)
    if (ultimas.length) armazenamento()?.setItem(chave, JSON.stringify(ultimas))
    else armazenamento()?.removeItem(chave)
  } catch {
    /* armazenamento cheio ou bloqueado: a conversa vale só enquanto a tela está aberta */
  }
}

export function apagarConversa(chave: string): void {
  try {
    armazenamento()?.removeItem(chave)
  } catch {
    /* nada guardado */
  }
}

/** Apaga as conversas de todas as contas e usuários deste navegador (ao sair). */
export function apagarConversas(): void {
  try {
    const s = armazenamento()
    if (!s) return
    const chaves: string[] = []
    for (let i = 0; i < s.length; i++) {
      const k = s.key(i)
      if (k?.startsWith(PREFIXO_CONVERSA)) chaves.push(k)
    }
    for (const k of chaves) s.removeItem(k)
  } catch {
    /* nada guardado */
  }
}
