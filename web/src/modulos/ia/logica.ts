// Regras puras da IA sob demanda (etapa 5d, docs/api-etapa-5d.md §6): a chave dos filtros, a contagem até poder gerar
// de novo, os textos dos botões e do rodapé, o que fazer com cada erro e a leitura do que vem da API (sempre como texto).
import { ApiError, MENSAGEM_INESPERADA } from '@/api/erros'
import type { ConteudoParecerIa, ConteudoResumoIa, CotaIa, FiltrosGeracaoIa, Id, SituacaoPassosIa } from '@/api/tipos'
import { formatarDataHora } from '@/utils/datas'

/** A cota esgotada sem a mensagem da API (no GET só vem o motivo) e o "Restam X de Y": os mesmos do assistente. */
export { MENSAGEM_COTA_ESGOTADA, textoCota } from '@/modulos/assistente/logica'

// ── Textos ──────────────────────────────────────────────────────────────────

export interface TextosGeracaoIa {
  /** Sem nada salvo para os filtros. */
  vazio: string
  /** O botão sem nada salvo ("Gerar resumo"). */
  gerar: string
  /** Conta pausada (assinatura atrasada): no lugar do botão. */
  pausada: string
  /** Para leitores de tela, antes do texto gerado. */
  gerado: string
  /** A geração terminou depois de a pessoa trocar os filtros: ficou salva para os anteriores. */
  prontoAnterior: string
}

export const TEXTOS_RESUMO: TextosGeracaoIa = {
  vazio: 'Três frases sobre o período: o que precisa melhorar, o que está funcionando e o próximo passo. Usa 1 análise de IA.',
  gerar: 'Gerar resumo',
  pausada: 'O resumo volta quando a assinatura estiver em dia.',
  gerado: 'Resumo gerado.',
  prontoAnterior: 'O resumo pedido ficou pronto para os filtros anteriores. Volte a eles para ver.',
}

export const TEXTOS_PARECER: TextosGeracaoIa = {
  vazio: 'Um resumo do período e até 3 recomendações para esta semana, com os filtros da tela. Usa 1 análise de IA.',
  gerar: 'Gerar parecer',
  pausada: 'O parecer volta quando a assinatura estiver em dia.',
  gerado: 'Parecer gerado.',
  prontoAnterior: 'O parecer pedido ficou pronto para os filtros anteriores. Volte a eles para ver.',
}

export const TEXTO_GERANDO = 'Lendo os números do período…'
/** Motivo que a tela não conhece: sem botão. */
export const MENSAGEM_IA_INDISPONIVEL = 'A IA não está disponível no momento.'
export const TEXTO_PODE_GERAR = 'Já dá para gerar de novo.'

/** Rótulos das três frases do resumo do painel, na ordem. */
export const PARTES_RESUMO: { chave: keyof ConteudoResumoIa; rotulo: string }[] = [
  { chave: 'melhorar', rotulo: 'Precisa melhorar' },
  { chave: 'funciona', rotulo: 'Está funcionando' },
  { chave: 'proximo_passo', rotulo: 'Próximo passo' },
]

// ── Filtros ─────────────────────────────────────────────────────────────────

/**
 * Chave canônica dos filtros, como a API guarda (`de` e `ate` ISO ou vazio, o grupo ou vazio, só ativas 1/0 com vazio =
 * 1): `de=2026-07-01|ate=2026-09-30|grupo=|ativos=1`. Filtros iguais, mesma chave: a tela só relê quando ela muda.
 */
export function chaveFiltros(f: FiltrosGeracaoIa): string {
  const g = f.grupo_id
  const grupo = g === undefined || g === null || g === '' ? '' : String(g)
  return `de=${f.de ?? ''}|ate=${f.ate ?? ''}|grupo=${grupo}|ativos=${f.so_ativos === false ? 0 : 1}`
}

/** "Últimos 90 dias · Todos os grupos · Só empresas ativas" (o que o parecer leva em conta). */
export function descreverFiltrosIa(periodo: string, grupo: string | null, soAtivos: boolean): string {
  return [periodo, grupo ? `Grupo ${grupo}` : 'Todos os grupos', soAtivos ? 'Só empresas ativas' : 'Empresas ativas e inativas'].filter(Boolean).join(' · ')
}

// ── Espera de 30 s ──────────────────────────────────────────────────────────

/** A API trava 30 s depois de cada geração: a contagem nunca passa disso (relógio do aparelho adiantado ou atrasado). */
export const ESPERA_MAXIMA = 30

/** Segundos inteiros (arredondados para cima) até `alvo` (ms), de 0 a 30. */
export function segundosAte(alvo: number | null | undefined, agora: number, maximo = ESPERA_MAXIMA): number {
  if (alvo === null || alvo === undefined || !Number.isFinite(alvo)) return 0
  return Math.min(maximo, Math.max(0, Math.ceil((alvo - agora) / 1000)))
}

/** `pode_gerar_em` da API em ms (null se vier vazio ou inválido). */
export function instante(iso: string | null | undefined): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isFinite(t) ? t : null
}

/**
 * Até quando esperar no relógio do aparelho: o que falta para `alvo` (o `pode_gerar_em` da API, na hora do servidor) no
 * momento em que a resposta chega, de 0 a 30 s; daí em diante a contagem segue só o relógio do aparelho. Comparar a hora
 * do servidor com a do aparelho a cada segundo faria um aparelho atrasado 1 min esperar 1 min e meio.
 */
export function prazoLocal(alvo: number | null, agora: number): number | null {
  if (alvo === null || !Number.isFinite(alvo)) return null
  return agora + Math.min(ESPERA_MAXIMA * 1000, Math.max(0, alvo - agora))
}

/** O nome do botão ("Gerar resumo" ou, com algo salvo, "Gerar de novo"): não muda com a contagem. */
export function rotuloBotaoGerar(rotulo: string, temItem: boolean): string {
  return temItem ? 'Gerar de novo' : rotulo
}

/** "Gerar resumo", "Gerar de novo" ou com a contagem ("Gerar de novo em 25 s"): o que aparece escrito no botão. */
export function textoBotaoGerar(rotulo: string, temItem: boolean, segundos: number): string {
  const base = rotuloBotaoGerar(rotulo, temItem)
  return segundos > 0 ? `${base} em ${segundos} s` : base
}

// ── Rodapé ──────────────────────────────────────────────────────────────────

/** "Gerado em 02/10/2026 às 14:30 por Ana Paula · Equilibrado" (sem quem gerou, se o usuário foi removido). */
export function textoGerado(item: { gerado_em: string | null; gerado_por: string | null; modelo_rotulo: string }): string {
  let t = item.gerado_em ? `Gerado em ${formatarDataHora(item.gerado_em)}` : 'Gerado'
  if (item.gerado_por) t += ` por ${item.gerado_por}`
  return item.modelo_rotulo ? `${t} · ${item.modelo_rotulo}` : t
}

// ── Erros da geração ────────────────────────────────────────────────────────

export type BloqueioGeracao = 'conta_pausada' | 'cota_esgotada'

export interface ErroGeracao {
  mensagem: string
  /** Tom do aviso: sem dados é informação; 429 pede para esperar; o resto é erro. */
  tom: 'info' | 'atencao' | 'erro'
  /** "Tentar de novo": só no 503 (a IA falhou e a análise voltou para a cota). */
  repetir: boolean
  /** 409 de conta pausada ou cota esgotada: o botão some e fica a explicação. */
  bloqueio: BloqueioGeracao | null
  /** 429 `aguarde` com os segundos na mensagem: o botão mostra a contagem. */
  esperar: number | null
}

/** "Aguarde 12 s para gerar de novo." → 12 (null sem número). */
export function segundosDaMensagem(mensagem: string): number | null {
  const m = /(\d{1,3})\s*s\b/.exec(mensagem)
  if (!m) return null
  const n = Number(m[1])
  return n >= 1 ? Math.min(n, ESPERA_MAXIMA) : null
}

/**
 * O que a tela faz com o erro do POST: 409 `cota_esgotada` e `conta_pausada` mudam o estado (sem botão, com a mensagem);
 * 409 `sem_dados`, 429 e 503 aparecem num aviso (só o 503 com "Tentar de novo"); o resto, a mensagem.
 */
export function lerErroGeracao(e: unknown): ErroGeracao {
  if (!(e instanceof ApiError)) return { mensagem: MENSAGEM_INESPERADA, tom: 'erro', repetir: false, bloqueio: null, esperar: null }
  if (e.status === 409 && (e.codigo === 'cota_esgotada' || e.codigo === 'conta_pausada')) {
    return { mensagem: e.mensagem, tom: 'atencao', repetir: false, bloqueio: e.codigo, esperar: null }
  }
  if (e.status === 429) {
    const esperar = e.codigo === 'aguarde' ? segundosDaMensagem(e.mensagem) : null
    return { mensagem: e.mensagem, tom: 'atencao', repetir: false, bloqueio: null, esperar }
  }
  const tom = e.status === 409 && e.codigo === 'sem_dados' ? 'info' : 'erro'
  return { mensagem: e.mensagem, tom, repetir: e.status === 503, bloqueio: null, esperar: null }
}

// ── Leitura do que vem da API ───────────────────────────────────────────────

function ehObjeto(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** Texto numa linha só, sem espaços nas pontas ('' se não for texto). */
function texto(v: unknown): string {
  return typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : ''
}

/** Lista de textos: só os não vazios, sem repetidos, até `maximo`. */
export function listaDeTextos(v: unknown, maximo = 3): string[] {
  if (!Array.isArray(v)) return []
  const r: string[] = []
  for (const x of v) {
    const t = texto(x)
    if (t && !r.includes(t)) r.push(t)
    if (r.length >= maximo) break
  }
  return r
}

/** As três frases do resumo do painel (null se não vier nenhuma). */
export function normalizarResumo(c: unknown): ConteudoResumoIa | null {
  if (!ehObjeto(c)) return null
  const r = { melhorar: texto(c.melhorar), funciona: texto(c.funciona), proximo_passo: texto(c.proximo_passo) }
  return r.melhorar || r.funciona || r.proximo_passo ? r : null
}

/** O resumo e as recomendações do parecer (null se não vier nada). */
export function normalizarParecer(c: unknown): ConteudoParecerIa | null {
  if (!ehObjeto(c)) return null
  const r = { resumo: texto(c.resumo), recomendacoes: listaDeTextos(c.recomendacoes) }
  return r.resumo || r.recomendacoes.length ? r : null
}

/** O item salvo, já lido: o conteúdo, quando e por quem foi gerado e o nome do modelo. */
export interface ItemIa<C> {
  conteudo: C
  gerado_em: string | null
  /** Nome de quem gerou (null se o usuário foi removido). */
  gerado_por: string | null
  modelo_rotulo: string
}

/** O resumo em texto corrido, para leitores de tela ("Precisa melhorar: … Está funcionando: … Próximo passo: …"). */
export function falarResumo(c: ConteudoResumoIa): string {
  return PARTES_RESUMO.filter((p) => c[p.chave])
    .map((p) => `${p.rotulo}: ${c[p.chave]}`)
    .join(' ')
}

/** O parecer em texto corrido, para leitores de tela. */
export function falarParecer(c: ConteudoParecerIa): string {
  const partes: string[] = []
  if (c.resumo) partes.push(`Resumo: ${c.resumo}`)
  if (c.recomendacoes.length) partes.push(`Recomendações da semana: ${textoPassos(c.recomendacoes).replace(/\n/g, ' ')}`)
  return partes.join(' ')
}

/** A cota que veio da API, se estiver no formato (senão null). */
export function lerCota(v: unknown): CotaIa | null {
  if (!ehObjeto(v)) return null
  const { usadas, limite, restantes, mes } = v
  if (typeof usadas !== 'number' || typeof limite !== 'number' || typeof restantes !== 'number' || typeof mes !== 'string') return null
  return { usadas, limite, restantes, mes }
}

export function normalizarItem<C>(i: unknown, conteudo: (c: unknown) => C | null): ItemIa<C> | null {
  if (!ehObjeto(i)) return null
  const c = conteudo(i.conteudo)
  if (!c) return null
  const autor = ehObjeto(i.gerado_por) ? texto(i.gerado_por.nome) : ''
  return { conteudo: c, gerado_em: texto(i.gerado_em) || null, gerado_por: autor || null, modelo_rotulo: texto(i.modelo_rotulo) }
}

// ── Configurações › IA: como a IA escreve (§6.4) ────────────────────────────

export type CampoEscritaIa = 'modelo' | 'estilo' | 'passos_acoes'

/** O rótulo de uma opção da lista da API (o próprio valor, se não estiver na lista). */
export function rotuloOpcao(opcoes: readonly { valor: string; rotulo: string }[] | null | undefined, valor: string): string {
  return opcoes?.find((o) => o.valor === valor)?.rotulo ?? valor
}

/** O aviso depois de salvar um campo de "Como a IA escreve". */
export function textoEscritaSalva(
  campo: CampoEscritaIa,
  d: { modelo?: string; estilo?: string; passos_acoes?: boolean; modelos?: readonly { valor: string; rotulo: string }[]; estilos?: readonly { valor: string; rotulo: string }[] },
): string {
  if (campo === 'modelo') return `Modelo salvo: ${rotuloOpcao(d.modelos, d.modelo ?? '')}.`
  if (campo === 'estilo') return `Estilo salvo: ${rotuloOpcao(d.estilos, d.estilo ?? '')}.`
  return d.passos_acoes
    ? 'Sugestão de passos ligada. Vale para as próximas ações criadas a partir de uma resposta.'
    : 'Sugestão de passos desligada. As próximas ações ficam só com o comentário do cliente.'
}

// ── Passos das ações (§6.3) ─────────────────────────────────────────────────

export const TEXTOS_PASSOS = {
  titulo: 'Passos sugeridos pela IA',
  pendente: 'A IA está sugerindo os passos…',
  /** Depois das releituras, ainda pendente (a tarefa da IA pode terminar depois). */
  demorando: 'Os passos aparecem aqui quando ficarem prontos. Abra a ação de novo daqui a pouco.',
  falhou: 'A IA não conseguiu sugerir passos para esta ação.',
  limite: 'O limite mensal de análises automáticas foi atingido.',
  nota: 'Sugestão da IA. Confira antes de seguir.',
} as const

/** Enquanto pendente, relê a ação a cada 5 s, até 6 vezes. */
export const INTERVALO_PASSOS = 5000
export const RELEITURAS_PASSOS = 6

const SITUACOES_PASSOS: readonly SituacaoPassosIa[] = ['pendente', 'pronta', 'falhou', 'limite']

/** A situação dos passos (null = nada aparece, inclusive uma situação que a tela não conhece). */
export function situacaoPassos(v: unknown): SituacaoPassosIa | null {
  return SITUACOES_PASSOS.includes(v as SituacaoPassosIa) ? (v as SituacaoPassosIa) : null
}

/** O que o painel da ação avisa à tela quando, ao reler a ação, os passos mudaram. */
export interface PassosAtualizados {
  id: Id
  ia_passos: string[] | null
  ia_passos_situacao: SituacaoPassosIa | null
}

/** "1. Ligar para o cliente\n2. …" (para copiar). */
export function textoPassos(passos: readonly string[]): string {
  return passos.map((p, i) => `${i + 1}. ${p}`).join('\n')
}
