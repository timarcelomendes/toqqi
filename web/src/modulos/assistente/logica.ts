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

/**
 * O `custo` que veio da API (análises que uma pergunta, um resumo ou um parecer gasta no nível da conta: 1, ou 2 no Mais
 * detalhado). Sem ele (API anterior a 03/10, ou sem IA na plataforma), 1.
 */
export function lerCusto(v: unknown): number {
  return typeof v === 'number' && Number.isInteger(v) && v >= 1 ? v : 1
}

/**
 * Restam análises, mas menos que o custo do nível. Só quando a API não mandou a frase dela (que já sugere o nível mais
 * barato que cabe no que resta): como as análises de cada nível mudam em Plataforma › Parâmetros, o texto não cita nível
 * nenhum. "O nível escolhido gasta 3 análises e restam 2. Troque o nível em Configurações › IA ou aguarde o próximo mês."
 * ("e resta 1" no singular). O custo nunca fica igual ou abaixo do que resta (a frase se contradiria).
 */
export function mensagemCotaInsuficiente(restantes: number, custo: number): string {
  const resta = Math.max(1, Math.floor(restantes))
  const gasta = Math.max(lerCusto(custo), resta + 1)
  const sobra = resta === 1 ? 'resta 1' : `restam ${formatarNumero(resta)}`
  return `O nível escolhido gasta ${formatarNumero(gasta)} análises e ${sobra}. Troque o nível em Configurações › IA ou aguarde o próximo mês.`
}

/** Por que a caixa (ou o botão de gerar) desliga: a cota acabou, não dá para o custo do nível ou a conta está pausada. */
export type MotivoBloqueio = 'cota_esgotada' | 'cota_insuficiente' | 'conta_pausada'

const BLOQUEIOS: readonly MotivoBloqueio[] = ['cota_esgotada', 'cota_insuficiente', 'conta_pausada']

/** O 409 que desliga a caixa (ou o botão): cota esgotada, cota insuficiente para o nível ou conta pausada. */
export function ehBloqueio(codigo: string): codigo is MotivoBloqueio {
  return (BLOQUEIOS as readonly string[]).includes(codigo)
}

export interface ErroPergunta {
  mensagem: string
  /** Mostra "Tentar de novo": só 503 `ia_indisponivel`, 429 (limite por minuto) e sem conexão. */
  repetir: boolean
  /** Cota esgotada, cota insuficiente para o nível ou conta pausada: a caixa de texto desliga e explica. */
  bloqueio: MotivoBloqueio | null
}

/**
 * O que fazer com o erro de uma pergunta: a mensagem da API vai para a conversa. "Tentar de novo" só onde repetir é
 * seguro: 503 `ia_indisponivel` (a análise volta), 429 (barrado antes de reservar a análise) e sem conexão. Nos outros
 * (um 500 pode vir depois de a análise ser gasta, um erro inesperado também), só a mensagem.
 */
export function lerErroPergunta(e: unknown): ErroPergunta {
  if (!(e instanceof ApiError)) return { mensagem: MENSAGEM_INESPERADA, repetir: false, bloqueio: null }
  if (e.status === 409 && ehBloqueio(e.codigo)) {
    return { mensagem: e.mensagem, repetir: false, bloqueio: e.codigo }
  }
  // O cliente troca o texto de todo 429 por um genérico; aqui vale o do contrato.
  if (e.status === 429) return { mensagem: MENSAGEM_LIMITE_PERGUNTAS, repetir: true, bloqueio: null }
  const repetir = e.status === 0 || (e.status === 503 && e.codigo === 'ia_indisponivel')
  return { mensagem: e.mensagem, repetir, bloqueio: null }
}

/** O que a explicação da cota insuficiente usa: a mensagem do 409, se veio, ou a montada com o que resta e o custo. */
export interface DetalheCota {
  /** A mensagem do 409 `cota_insuficiente` (null quando o bloqueio veio do GET ou da conta local). */
  mensagem?: string | null
  restantes?: number | null
  custo?: number | null
}

/** Por que a caixa de texto está desligada (null quando o assistente está disponível). */
export function explicacaoIndisponivel(disponivel: boolean, motivo: string | null | undefined, cota: DetalheCota = {}): string | null {
  if (disponivel) return null
  if (motivo === 'cota_esgotada') return MENSAGEM_COTA_ESGOTADA
  if (motivo === 'cota_insuficiente') return cota.mensagem || mensagemCotaInsuficiente(cota.restantes ?? 1, cota.custo ?? 1)
  if (motivo === 'conta_pausada') return MENSAGEM_CONTA_PAUSADA
  return MENSAGEM_INDISPONIVEL
}

/** Quem pede menos movimento no sistema: sem efeito de digitação nem rolagem animada. */
export function semMovimento(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
