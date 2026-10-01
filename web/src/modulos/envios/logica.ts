// Regras puras da tela de Envios (sem Vue): rótulos, seleção com limite e atualização automática.
import type { CanalEnvio, ContatoEnvio, Id, OrigemEnvio, SituacaoEnvio, TipoEnvio } from '@/api/tipos'
import type { Tom } from '@/utils/rotulos'

/** Máximo de contatos por envio manual (limite do contrato). */
export const LIMITE_SELECAO = 500

/** Intervalo da atualização automática enquanto há pesquisas saindo. */
export const INTERVALO_ATUALIZACAO_MS = 3000

export const SITUACOES_ENVIO: Record<SituacaoEnvio, { rotulo: string; tom: Tom }> = {
  pendente: { rotulo: 'Enviando...', tom: 'marca' },
  enviado: { rotulo: 'Enviado', tom: 'sucesso' },
  erro: { rotulo: 'Não saiu', tom: 'erro' },
  aberto_no_whatsapp: { rotulo: 'Aberto no WhatsApp', tom: 'info' },
}

export const TIPOS_ENVIO: Record<TipoEnvio, string> = {
  convite: 'Pesquisa',
  lembrete: 'Lembrete',
  agradecimento: 'Agradecimento',
}

export const CANAIS_ENVIO: Record<CanalEnvio, string> = {
  email: 'E-mail',
  whatsapp: 'WhatsApp',
}

export const ORIGENS_ENVIO: Record<OrigemEnvio, string> = {
  manual: 'Enviado por alguém da equipe',
  automatico: 'Envio automático',
  lembrete: 'Lembrete automático',
  resposta: 'Depois da resposta',
}

export const ORIGENS_DESCADASTRO: Record<string, string> = {
  link: 'Pelo link do e-mail',
  um_clique: 'Pelo botão do programa de e-mail',
  manual: 'Registrado pela equipe',
}

export function rotuloDe<T extends string>(mapa: Record<T, string>, v: string | null | undefined): string {
  return (v && mapa[v as T]) || v || '—'
}

export function situacaoEnvio(v: string | null | undefined): { rotulo: string; tom: Tom } {
  return (v && SITUACOES_ENVIO[v as SituacaoEnvio]) || { rotulo: v || '—', tom: 'neutro' }
}

/** Há alguma linha saindo agora? Enquanto houver, a tela recarrega a cada 3 s. */
export function temEnviando(linhas: Pick<ContatoEnvio, 'enviando' | 'situacao'>[]): boolean {
  return linhas.some((c) => c.enviando || c.situacao === 'enviando')
}

/** Quem pode receber pelo botão "Enviar agora" (e-mail): ativo, com e-mail e na lista. */
export function podeEnviarEmail(c: Pick<ContatoEnvio, 'ativo' | 'email' | 'situacao' | 'enviando'>): boolean {
  return c.ativo && !!c.email && c.situacao !== 'saiu_da_lista' && c.situacao !== 'inativo' && !c.enviando && c.situacao !== 'enviando'
}

/** Quem pode receber pelo WhatsApp: ativo, com telefone e na lista. */
export function podeEnviarWhatsapp(c: Pick<ContatoEnvio, 'ativo' | 'telefone' | 'situacao'>): boolean {
  return c.ativo && !!c.telefone && c.situacao !== 'saiu_da_lista' && c.situacao !== 'inativo'
}

// ── Seleção (mantida entre páginas, com limite) ─────────────────────────────

export type Selecao = Map<string, { id: Id; nome: string }>

export type ResultadoAlternar = 'adicionado' | 'removido' | 'limite'

/** Marca ou desmarca um contato. Não passa do limite. */
export function alternarSelecao(sel: Selecao, c: { id: Id; nome: string }, limite = LIMITE_SELECAO): ResultadoAlternar {
  const k = String(c.id)
  if (sel.has(k)) {
    sel.delete(k)
    return 'removido'
  }
  if (sel.size >= limite) return 'limite'
  sel.set(k, { id: c.id, nome: c.nome })
  return 'adicionado'
}

/**
 * Marca todos da página (ou desmarca, se todos já estavam marcados).
 * Devolve quantos entraram e quantos ficaram de fora pelo limite.
 */
export function alternarPagina(
  sel: Selecao,
  itens: { id: Id; nome: string }[],
  limite = LIMITE_SELECAO,
): { adicionados: number; removidos: number; foraDoLimite: number } {
  const todos = itens.length > 0 && itens.every((c) => sel.has(String(c.id)))
  if (todos) {
    for (const c of itens) sel.delete(String(c.id))
    return { adicionados: 0, removidos: itens.length, foraDoLimite: 0 }
  }
  let adicionados = 0
  let foraDoLimite = 0
  for (const c of itens) {
    const k = String(c.id)
    if (sel.has(k)) continue
    if (sel.size >= limite) {
      foraDoLimite++
      continue
    }
    sel.set(k, { id: c.id, nome: c.nome })
    adicionados++
  }
  return { adicionados, removidos: 0, foraDoLimite }
}

/** Estado da caixa "marcar todos da página": 'todos' | 'alguns' | 'nenhum'. */
export function estadoPagina(sel: Selecao, itens: { id: Id }[]): 'todos' | 'alguns' | 'nenhum' {
  const n = itens.filter((c) => sel.has(String(c.id))).length
  if (!n) return 'nenhum'
  return n === itens.length ? 'todos' : 'alguns'
}

/** "1 contato" / "12 contatos". */
export function contatos(n: number): string {
  return `${n.toLocaleString('pt-BR')} ${n === 1 ? 'contato' : 'contatos'}`
}
