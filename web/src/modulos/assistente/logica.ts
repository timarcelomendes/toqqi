// Regras puras do assistente (sem Vue): a resposta em parágrafos e listas (sempre como texto, nunca HTML), o histórico
// que vai em cada pergunta, a frase da cota e o que a tela faz com cada erro (docs/api-etapa-5b.md §4 e §6.2).
import { ApiError, MENSAGEM_INESPERADA } from '@/api/erros'
import type { CotaIa, MensagemHistorico, PapelMensagem } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'

/** Tamanho máximo da pergunta (a API conta depois de tirar os espaços das pontas). */
export const LIMITE_PERGUNTA = 1000
/** Quantas mensagens da conversa vão junto com cada pergunta. */
export const HISTORICO_API = 8
/** Quantas mensagens ficam guardadas no navegador. */
export const MENSAGENS_GUARDADAS = 20
/** Tamanho máximo de cada texto do histórico na API. */
const TEXTO_HISTORICO = 4000

/**
 * Telas com espaço para o painel preso ao canto: largas **e** altas. Abaixo disso (celular, celular deitado, zoom de
 * 200%) o painel ocupa a tela toda, como modal. É a mesma consulta da variante `painel:` do Tailwind (src/styles/main.css).
 */
export const MIDIA_PAINEL = '(min-width: 640px) and (min-height: 560px)'

/** Sem o estado do assistente (a busca falhou), tenta de novo depois de 5 s, 15 s e 60 s; depois, a cada 5 minutos. */
export const ESPERAS_ESTADO = [5_000, 15_000, 60_000, 300_000] as const

/** Quanto esperar antes da tentativa `n` (0 = a primeira depois da falha). */
export function esperaDaTentativa(n: number): number {
  return ESPERAS_ESTADO[Math.min(Math.max(0, n), ESPERAS_ESTADO.length - 1)]!
}

export const MENSAGEM_LIMITE_PERGUNTAS = 'Muitas perguntas em pouco tempo. Aguarde um minuto e tente de novo.'
export const MENSAGEM_COTA_ESGOTADA = 'O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º.'
export const MENSAGEM_CONTA_PAUSADA = 'O ToqqiAI volta quando a assinatura estiver em dia.'
export const MENSAGEM_INDISPONIVEL = 'O ToqqiAI está indisponível no momento. Tente de novo em instantes.'

export type BlocoTexto = { tipo: 'paragrafo'; linhas: string[] } | { tipo: 'lista'; itens: string[] }

/**
 * Divide a resposta em blocos para montar com nós de texto: linhas que começam com "- " viram itens de lista; as outras
 * formam parágrafos (as quebras de linha dentro deles continuam); linha em branco separa parágrafos.
 */
export function blocosDoTexto(texto: string): BlocoTexto[] {
  const blocos: BlocoTexto[] = []
  let lista: string[] | null = null
  let paragrafo: string[] | null = null
  for (const bruta of texto.replace(/\r\n?/g, '\n').split('\n')) {
    const item = /^\s*-\s+(.*\S)\s*$/.exec(bruta)
    if (item) {
      paragrafo = null
      if (!lista) blocos.push({ tipo: 'lista', itens: (lista = []) })
      lista.push(item[1]!)
    } else if (!bruta.trim()) {
      lista = null
      paragrafo = null
    } else {
      lista = null
      if (!paragrafo) blocos.push({ tipo: 'paragrafo', linhas: (paragrafo = []) })
      paragrafo.push(bruta.trim())
    }
  }
  return blocos
}

/** Uma mensagem da conversa como a tela guarda (as perguntas que falharam não vão para a API). */
export interface MensagemBase {
  papel: PapelMensagem
  texto: string
  falhou?: boolean
}

/** As últimas 8 mensagens que tiveram resposta (sem a pergunta que está sendo feita), no formato da API. */
export function historicoParaApi(mensagens: readonly MensagemBase[]): MensagemHistorico[] {
  return mensagens
    .filter((m) => !m.falhou && m.texto.trim())
    .slice(-HISTORICO_API)
    .map((m) => ({ papel: m.papel, texto: m.texto.trim().slice(0, TEXTO_HISTORICO) }))
}

/** "Restam 488 de 500 análises este mês" (no singular, "Resta 1 de …"). */
export function textoCota(cota: CotaIa): string {
  const restantes = Math.max(0, cota.restantes)
  return `${restantes === 1 ? 'Resta' : 'Restam'} ${formatarNumero(restantes)} de ${formatarNumero(cota.limite)} análises este mês`
}

export type MotivoBloqueio = 'cota_esgotada' | 'conta_pausada'

export interface ErroPergunta {
  mensagem: string
  /** Mostra "Tentar de novo": só 503 `ia_indisponivel`, 429 (limite por minuto) e sem conexão. */
  repetir: boolean
  /** Cota esgotada ou conta pausada: a caixa de texto desliga e explica. */
  bloqueio: MotivoBloqueio | null
}

/**
 * O que fazer com o erro de uma pergunta: a mensagem da API vai para a conversa. "Tentar de novo" só onde repetir é
 * seguro: 503 `ia_indisponivel` (a análise volta), 429 (barrado antes de reservar a análise) e sem conexão. Nos outros
 * (um 500 pode vir depois de a análise ser gasta, um erro inesperado também), só a mensagem.
 */
export function lerErroPergunta(e: unknown): ErroPergunta {
  if (!(e instanceof ApiError)) return { mensagem: MENSAGEM_INESPERADA, repetir: false, bloqueio: null }
  if (e.status === 409 && (e.codigo === 'cota_esgotada' || e.codigo === 'conta_pausada')) {
    return { mensagem: e.mensagem, repetir: false, bloqueio: e.codigo }
  }
  // O cliente troca o texto de todo 429 por um genérico; aqui vale o do contrato.
  if (e.status === 429) return { mensagem: MENSAGEM_LIMITE_PERGUNTAS, repetir: true, bloqueio: null }
  const repetir = e.status === 0 || (e.status === 503 && e.codigo === 'ia_indisponivel')
  return { mensagem: e.mensagem, repetir, bloqueio: null }
}

/** Por que a caixa de texto está desligada (null quando o assistente está disponível). */
export function explicacaoIndisponivel(disponivel: boolean, motivo: string | null | undefined): string | null {
  if (disponivel) return null
  if (motivo === 'cota_esgotada') return MENSAGEM_COTA_ESGOTADA
  if (motivo === 'conta_pausada') return MENSAGEM_CONTA_PAUSADA
  return MENSAGEM_INDISPONIVEL
}

/** Quem pede menos movimento no sistema: sem efeito de digitação nem rolagem animada. */
export function semMovimento(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
