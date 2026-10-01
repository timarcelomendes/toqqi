// Regras puras dos Planos de ação (sem Vue): colunas, selo de prazo, ordem do quadro,
// o que falta para concluir e como o quadro muda ao mover, salvar ou excluir uma ação.
import type {
  Acao,
  DadosEdicaoAcao,
  FiltrosAcoes,
  GrupoNota,
  Id,
  PrioridadeAcao,
  QuadroAcoes,
  Referencia,
  SeloPrazo,
  SituacaoAcao,
  TipoNota,
  TotaisQuadro,
} from '@/api/tipos'
import { formatarData, hojeIso } from '@/utils/datas'
import { dataIsoValida, ehPreset, intervaloDoPeriodo, type PresetPeriodo } from '@/utils/periodo'
import type { Tom } from '@/utils/rotulos'
import { LIMITE_BUSCA } from '@/modulos/respostas/logica'

export { LIMITE_BUSCA }

export const COLUNAS: { situacao: SituacaoAcao; titulo: string; vazio: string }[] = [
  { situacao: 'a_fazer', titulo: 'A fazer', vazio: 'Nada para começar agora.' },
  { situacao: 'em_andamento', titulo: 'Em andamento', vazio: 'Nenhuma ação em andamento.' },
  { situacao: 'concluida', titulo: 'Concluído', vazio: 'Nenhuma ação concluída ainda.' },
]

export const SITUACOES_ACAO: Record<SituacaoAcao, { rotulo: string; tom: Tom }> = {
  a_fazer: { rotulo: 'A fazer', tom: 'neutro' },
  em_andamento: { rotulo: 'Em andamento', tom: 'info' },
  concluida: { rotulo: 'Concluída', tom: 'sucesso' },
}

export const PRIORIDADES: Record<PrioridadeAcao, { rotulo: string; tom: Tom; ordem: number }> = {
  alta: { rotulo: 'Alta', tom: 'erro', ordem: 0 },
  media: { rotulo: 'Média', tom: 'atencao', ordem: 1 },
  baixa: { rotulo: 'Baixa', tom: 'neutro', ordem: 2 },
}

/** O quadro mostra só as 15 concluídas mais recentes; o resto fica em "Ver todas". */
export const LIMITE_CONCLUIDAS = 15

/** Mesmas mensagens do servidor (422 ao concluir). */
export const MENSAGENS_CONCLUIR = {
  responsavel_id: 'Escolha o responsável antes de concluir.',
  resolucao: 'Conte o que foi feito para concluir.',
} as const

export function ehSituacao(v: unknown): v is SituacaoAcao {
  return v === 'a_fazer' || v === 'em_andamento' || v === 'concluida'
}

// ── Selo de prazo ───────────────────────────────────────────────────────────

/** Regra do contrato: só para ação não concluída com prazo; vencido se prazo < hoje, hoje, amanhã; senão null. */
export function calcularSeloPrazo(prazo: string | null | undefined, situacao: SituacaoAcao, hoje: string = hojeIso()): SeloPrazo | null {
  if (!prazo || situacao === 'concluida') return null
  const dia = prazo.slice(0, 10)
  if (dia < hoje) return 'vencido'
  if (dia === hoje) return 'hoje'
  if (dia === amanhaDe(hoje)) return 'amanha'
  return null
}

function amanhaDe(hoje: string): string {
  const d = new Date(`${hoje}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}

/**
 * Selo para o cartão: "Prazo vencido", "Vence hoje", "Vence amanhã" ou a data ("Até 12/10/2026").
 * Concluída ou sem prazo: sem selo. Usa o selo da API; o cálculo local só entra quando a API não mandou.
 */
export function seloPrazo(
  a: Pick<Acao, 'prazo' | 'situacao'> & { prazo_selo?: SeloPrazo | null },
  hoje: string = hojeIso(),
): { tipo: SeloPrazo | 'data'; rotulo: string; tom: Tom; descricao: string } | null {
  if (!a.prazo || a.situacao === 'concluida') return null
  const selo = a.prazo_selo === undefined ? calcularSeloPrazo(a.prazo, a.situacao, hoje) : a.prazo_selo
  const data = formatarData(a.prazo)
  if (selo === 'vencido') return { tipo: 'vencido', rotulo: 'Prazo vencido', tom: 'erro', descricao: `O prazo era ${data}.` }
  if (selo === 'hoje') return { tipo: 'hoje', rotulo: 'Vence hoje', tom: 'atencao', descricao: `Prazo: hoje, ${data}.` }
  if (selo === 'amanha') return { tipo: 'amanha', rotulo: 'Vence amanhã', tom: 'atencao', descricao: `Prazo: amanhã, ${data}.` }
  return { tipo: 'data', rotulo: `Até ${data}`, tom: 'neutro', descricao: `Prazo: ${data}.` }
}

function estaVencida(a: Pick<Acao, 'prazo' | 'situacao'>, hoje: string): boolean {
  return calcularSeloPrazo(a.prazo, a.situacao, hoje) === 'vencido'
}

// ── Ordem das colunas ───────────────────────────────────────────────────────

/** Abertas: vencidas primeiro, depois prazo (sem prazo por último), prioridade (alta → baixa) e criação (mais antiga primeiro). */
export function compararAbertas(hoje: string = hojeIso()) {
  return (a: Acao, b: Acao): number => {
    const va = estaVencida(a, hoje) ? 0 : 1
    const vb = estaVencida(b, hoje) ? 0 : 1
    if (va !== vb) return va - vb
    const pa = a.prazo ? a.prazo.slice(0, 10) : '9999-99-99'
    const pb = b.prazo ? b.prazo.slice(0, 10) : '9999-99-99'
    if (pa !== pb) return pa < pb ? -1 : 1
    const prioridade = (PRIORIDADES[a.prioridade]?.ordem ?? 9) - (PRIORIDADES[b.prioridade]?.ordem ?? 9)
    if (prioridade) return prioridade
    if (a.criada_em !== b.criada_em) return a.criada_em < b.criada_em ? -1 : 1
    return String(a.id).localeCompare(String(b.id), 'pt-BR', { numeric: true })
  }
}

/** Concluídas: a concluída mais recentemente primeiro. */
export function compararConcluidas(a: Acao, b: Acao): number {
  const ca = a.concluida_em ?? ''
  const cb = b.concluida_em ?? ''
  if (ca !== cb) return ca > cb ? -1 : 1
  return String(b.id).localeCompare(String(a.id), 'pt-BR', { numeric: true })
}

export function ordenarColuna(situacao: SituacaoAcao, acoes: Acao[], hoje: string = hojeIso()): Acao[] {
  const copia = [...acoes]
  copia.sort(situacao === 'concluida' ? compararConcluidas : compararAbertas(hoje))
  return situacao === 'concluida' ? copia.slice(0, LIMITE_CONCLUIDAS) : copia
}

// ── Concluir ────────────────────────────────────────────────────────────────

/** O que falta para concluir (vazio = pode concluir). Chaves iguais às do 422 da API. */
export function faltasParaConcluir(a: { responsavel_id?: Id | null; responsavel?: { id: Id } | null; resolucao?: string | null }): Partial<
  Record<keyof typeof MENSAGENS_CONCLUIR, string>
> {
  const faltas: Partial<Record<keyof typeof MENSAGENS_CONCLUIR, string>> = {}
  const responsavel = a.responsavel_id !== undefined ? a.responsavel_id : (a.responsavel?.id ?? null)
  if (responsavel === null || responsavel === '') faltas.responsavel_id = MENSAGENS_CONCLUIR.responsavel_id
  if (!(a.resolucao ?? '').trim()) faltas.resolucao = MENSAGENS_CONCLUIR.resolucao
  return faltas
}

/** Pode ir para a coluna? Ir para "Concluído" exige responsável e o que foi feito. */
export function podeMover(a: Acao, para: SituacaoAcao): { ok: true } | { ok: false; faltas: Partial<Record<keyof typeof MENSAGENS_CONCLUIR, string>> } {
  if (para !== 'concluida' || a.situacao === 'concluida') return { ok: true }
  const faltas = faltasParaConcluir(a)
  return Object.keys(faltas).length ? { ok: false, faltas } : { ok: true }
}

/** Destinos do menu "Mover para…" (todas as colunas menos a atual). */
export function destinos(atual: SituacaoAcao): { situacao: SituacaoAcao; rotulo: string }[] {
  return COLUNAS.filter((c) => c.situacao !== atual).map((c) => ({ situacao: c.situacao, rotulo: c.titulo }))
}

// ── Mudanças no quadro (sempre devolvem um quadro novo) ─────────────────────

export function acharNoQuadro(q: QuadroAcoes, id: Id): Acao | null {
  for (const c of COLUNAS) {
    const a = q.colunas[c.situacao]?.find((x) => String(x.id) === String(id))
    if (a) return a
  }
  return null
}

function semAcao(q: QuadroAcoes, id: Id): Record<SituacaoAcao, Acao[]> {
  return {
    a_fazer: (q.colunas.a_fazer ?? []).filter((x) => String(x.id) !== String(id)),
    em_andamento: (q.colunas.em_andamento ?? []).filter((x) => String(x.id) !== String(id)),
    concluida: (q.colunas.concluida ?? []).filter((x) => String(x.id) !== String(id)),
  }
}

/** Ajusta os totais quando uma ação sai de um estado e entra em outro (null = entrou ou saiu do quadro). */
function ajustarTotais(t: TotaisQuadro, antes: Acao | null, depois: Acao | null, hoje: string): TotaisQuadro {
  const novo = { ...t }
  if (antes) {
    novo[antes.situacao] = Math.max(0, novo[antes.situacao] - 1)
    if (estaVencida(antes, hoje)) novo.vencidas = Math.max(0, novo.vencidas - 1)
  }
  if (depois) {
    novo[depois.situacao] += 1
    if (estaVencida(depois, hoje)) novo.vencidas += 1
  }
  return novo
}

/** A ação como fica depois de mudar de situação (como o servidor faz: datas de início e conclusão). */
export function comNovaSituacao(a: Acao, para: SituacaoAcao, agora: string = new Date().toISOString(), hoje: string = hojeIso()): Acao {
  if (a.situacao === para) return a
  const b: Acao = { ...a, situacao: para }
  if (para === 'concluida') b.concluida_em = agora
  else {
    b.concluida_em = null
    b.concluida_por = null
  }
  if (para === 'em_andamento' && !b.iniciada_em) b.iniciada_em = agora
  b.prazo_selo = calcularSeloPrazo(b.prazo, para, hoje)
  return b
}

/** Move uma ação de coluna (atualização otimista; a resposta do servidor entra depois com `colocarNoQuadro`). */
export function moverNoQuadro(q: QuadroAcoes, id: Id, para: SituacaoAcao, agora?: string, hoje: string = hojeIso()): QuadroAcoes {
  const atual = acharNoQuadro(q, id)
  if (!atual || atual.situacao === para) return q
  const movida = comNovaSituacao(atual, para, agora, hoje)
  return colocar(q, atual, movida, hoje)
}

/**
 * Coloca a versão nova de uma ação (salva ou criada) na coluna certa, na ordem certa.
 * `anterior`: como a ação estava antes (para acertar os totais mesmo se ela não estava à vista no quadro,
 * ex.: uma concluída antiga aberta por "Ver todas"). Sem ele, vale a versão do quadro; fora do quadro, conta como nova.
 */
export function colocarNoQuadro(q: QuadroAcoes, acao: Acao, anterior?: Acao | null, hoje: string = hojeIso()): QuadroAcoes {
  const antes = anterior !== undefined ? anterior : acharNoQuadro(q, acao.id)
  return colocar(q, antes, acao, hoje)
}

function colocar(q: QuadroAcoes, antes: Acao | null, depois: Acao, hoje: string): QuadroAcoes {
  const colunas = semAcao(q, depois.id)
  colunas[depois.situacao] = ordenarColuna(depois.situacao, [...colunas[depois.situacao], depois], hoje)
  return { colunas, totais: ajustarTotais(q.totais, antes, depois, hoje) }
}

/** Tira a ação do quadro (excluída). `anterior` serve para acertar os totais de uma ação que não estava à vista. */
export function removerDoQuadro(q: QuadroAcoes, id: Id, anterior?: Acao | null, hoje: string = hojeIso()): QuadroAcoes {
  const antes = anterior !== undefined ? anterior : acharNoQuadro(q, id)
  if (!antes) return q
  return { colunas: semAcao(q, id), totais: ajustarTotais(q.totais, antes, null, hoje) }
}

/** Quadro vazio (antes de carregar). */
export function quadroVazio(): QuadroAcoes {
  return { colunas: { a_fazer: [], em_andamento: [], concluida: [] }, totais: { a_fazer: 0, em_andamento: 0, concluida: 0, vencidas: 0 } }
}

/** Garante as três colunas e os totais, mesmo se a API mandar algo faltando. */
export function normalizarQuadro(q: Partial<QuadroAcoes> | null | undefined, hoje: string = hojeIso()): QuadroAcoes {
  const colunas = {
    a_fazer: ordenarColuna('a_fazer', q?.colunas?.a_fazer ?? [], hoje),
    em_andamento: ordenarColuna('em_andamento', q?.colunas?.em_andamento ?? [], hoje),
    // A API já manda as 15 mais recentes; ordenamos de novo só por segurança.
    concluida: ordenarColuna('concluida', q?.colunas?.concluida ?? [], hoje),
  }
  const t = q?.totais
  return {
    colunas,
    totais: {
      a_fazer: t?.a_fazer ?? colunas.a_fazer.length,
      em_andamento: t?.em_andamento ?? colunas.em_andamento.length,
      concluida: t?.concluida ?? colunas.concluida.length,
      vencidas: t?.vencidas ?? [...colunas.a_fazer, ...colunas.em_andamento].filter((a) => estaVencida(a, hoje)).length,
    },
  }
}

// ── Textos ──────────────────────────────────────────────────────────────────

/** Título sugerido para uma ação criada a partir de uma resposta (mesmo formato da automática). */
export function tituloSugerido(r: { nota: number | null; tipo_nota: 'nps' | 'csat' | null; grupo: string | null; empresa?: { nome: string } | null; contato?: { nome: string } | null }): string {
  const alvo = r.empresa?.nome || r.contato?.nome || 'cliente sem cadastro'
  // CSAT: só nota 1 ou 2 é "cliente insatisfeito"; de 3 a 5, o mesmo "Ação requerida" das outras.
  if (r.tipo_nota === 'csat' && typeof r.nota === 'number') {
    return r.nota <= 2 ? `[CSAT ${r.nota}] Cliente insatisfeito: ${alvo}` : `[CSAT ${r.nota}] Ação requerida: ${alvo}`
  }
  if (r.tipo_nota === 'nps' && typeof r.nota === 'number') {
    const grupo = r.grupo === 'detrator' ? 'Detrator' : r.grupo === 'neutro' ? 'Neutro' : r.grupo === 'promotor' ? 'Promotor' : null
    if (grupo) return `[${grupo} NPS ${r.nota}] Ação requerida: ${alvo}`
  }
  return `Retornar para ${alvo}`
}

/** Prioridade sugerida pela categoria da resposta (igual à ação automática). */
export function prioridadeSugerida(grupo: string | null | undefined): PrioridadeAcao {
  if (grupo === 'detrator' || grupo === 'insatisfeito') return 'alta'
  if (grupo === 'neutro') return 'media'
  return 'baixa'
}

// ── Edição no painel ────────────────────────────────────────────────────────

export const LIMITE_TITULO = 200
export const LIMITE_TEXTO_ACAO = 4000

export interface EdicaoAcao {
  titulo: string
  descricao: string
  resolucao: string
  responsavel_id: Id | ''
  prioridade: PrioridadeAcao
  prazo: string
  situacao: SituacaoAcao
  empresa: Referencia | null
}

export function edicaoDaAcao(a: Acao): EdicaoAcao {
  return {
    titulo: a.titulo ?? '',
    descricao: a.descricao ?? '',
    resolucao: a.resolucao ?? '',
    responsavel_id: a.responsavel?.id ?? '',
    prioridade: a.prioridade,
    prazo: a.prazo ? a.prazo.slice(0, 10) : '',
    situacao: a.situacao,
    empresa: a.empresa ? { id: a.empresa.id, nome: a.empresa.nome } : null,
  }
}

/** Só o que mudou (PATCH parcial); vazio vira null nos opcionais. */
export function mudancasAcao(a: Acao, e: EdicaoAcao): DadosEdicaoAcao {
  const d: DadosEdicaoAcao = {}
  if (e.titulo.trim() !== (a.titulo ?? '').trim()) d.titulo = e.titulo.trim()
  if (e.descricao.trim() !== (a.descricao ?? '').trim()) d.descricao = e.descricao.trim()
  if (e.resolucao.trim() !== (a.resolucao ?? '').trim()) d.resolucao = e.resolucao.trim() || null
  const resp = a.responsavel?.id ?? ''
  if (String(e.responsavel_id) !== String(resp)) d.responsavel_id = e.responsavel_id === '' ? null : e.responsavel_id
  if (e.prioridade !== a.prioridade) d.prioridade = e.prioridade
  const prazo = a.prazo ? a.prazo.slice(0, 10) : ''
  if (e.prazo !== prazo) d.prazo = e.prazo || null
  if (e.situacao !== a.situacao) d.situacao = e.situacao
  if (String(e.empresa?.id ?? '') !== String(a.empresa?.id ?? '')) d.empresa_id = e.empresa ? e.empresa.id : null
  return d
}

/**
 * Erros antes de salvar (mesmas chaves da API). Concluir pede responsável e o que foi feito; numa ação que já
 * estava concluída, a regra só volta a valer se a pessoa mexer no responsável ou no que foi feito.
 */
export function validarEdicaoAcao(e: EdicaoAcao, original?: Acao | null): Record<string, string> {
  const erros: Record<string, string> = {}
  const titulo = e.titulo.trim()
  if (!titulo) erros.titulo = 'Dê um título para a ação.'
  else if (titulo.length > LIMITE_TITULO) erros.titulo = 'Use até 200 caracteres no título.'
  if (e.descricao.length > LIMITE_TEXTO_ACAO) erros.descricao = 'Use até 4.000 caracteres na descrição.'
  if (e.resolucao.length > LIMITE_TEXTO_ACAO) erros.resolucao = 'Use até 4.000 caracteres.'
  const mexeuNoConcluir =
    !original ||
    original.situacao !== 'concluida' ||
    String(original.responsavel?.id ?? '') !== String(e.responsavel_id) ||
    (original.resolucao ?? '').trim() !== e.resolucao.trim()
  if (e.situacao === 'concluida' && mexeuNoConcluir) {
    Object.assign(erros, faltasParaConcluir({ responsavel_id: e.responsavel_id === '' ? null : e.responsavel_id, resolucao: e.resolucao }))
  }
  return erros
}

// ── Filtros do quadro ↔ endereço ────────────────────────────────────────────

export interface FiltrosQuadro {
  busca: string
  categoria: GrupoNota | ''
  tipo_nota: TipoNota | ''
  /** "0" = sem responsável. */
  responsavel_id: Id | ''
  empresa_id: Id | ''
  grupo_id: Id | ''
  periodo: PresetPeriodo
  de: string
  ate: string
  so_vencidas: boolean
}

export const FILTROS_QUADRO_PADRAO: Readonly<FiltrosQuadro> = Object.freeze<FiltrosQuadro>({
  busca: '',
  categoria: '',
  tipo_nota: '',
  responsavel_id: '',
  empresa_id: '',
  grupo_id: '',
  periodo: 'tudo',
  de: '',
  ate: '',
  so_vencidas: false,
})

const CATEGORIAS_VALIDAS: GrupoNota[] = ['detrator', 'neutro', 'promotor', 'insatisfeito', 'satisfeito']

type Consulta = Record<string, string | null | (string | null)[] | undefined>
function um(q: Consulta, k: string): string {
  const v = q[k]
  const s = Array.isArray(v) ? v[0] : v
  return typeof s === 'string' ? s.trim() : ''
}
const idValido = (v: string): Id | '' => (/^[\w-]{1,40}$/.test(v) ? v : '')

export function filtrosQuadroDaQuery(q: Consulta): FiltrosQuadro {
  const de = um(q, 'de')
  const ate = um(q, 'ate')
  const temData = dataIsoValida(de) || dataIsoValida(ate)
  const periodo = um(q, 'periodo')
  const categoria = um(q, 'categoria')
  const tipo = um(q, 'tipo_nota')
  return {
    busca: um(q, 'busca').slice(0, LIMITE_BUSCA),
    categoria: (CATEGORIAS_VALIDAS as string[]).includes(categoria) ? (categoria as GrupoNota) : '',
    tipo_nota: tipo === 'nps' || tipo === 'csat' ? tipo : '',
    responsavel_id: idValido(um(q, 'responsavel_id')),
    empresa_id: idValido(um(q, 'empresa_id')),
    grupo_id: idValido(um(q, 'grupo_id')),
    periodo: temData ? 'personalizado' : ehPreset(periodo) ? periodo : 'tudo',
    de: dataIsoValida(de) ? de : '',
    ate: dataIsoValida(ate) ? ate : '',
    so_vencidas: um(q, 'so_vencidas') === 'true',
  }
}

export function queryDosFiltrosQuadro(f: FiltrosQuadro): Record<string, string> {
  const q: Record<string, string> = {}
  if (f.busca.trim()) q.busca = f.busca.trim()
  if (f.categoria) q.categoria = f.categoria
  if (f.tipo_nota) q.tipo_nota = f.tipo_nota
  if (f.responsavel_id !== '') q.responsavel_id = String(f.responsavel_id)
  if (f.empresa_id !== '') q.empresa_id = String(f.empresa_id)
  if (f.grupo_id !== '') q.grupo_id = String(f.grupo_id)
  if (f.periodo === 'personalizado') {
    if (dataIsoValida(f.de)) q.de = f.de
    if (dataIsoValida(f.ate)) q.ate = f.ate
    if (!q.de && !q.ate) q.periodo = 'personalizado'
  } else if (f.periodo !== 'tudo') q.periodo = f.periodo
  if (f.so_vencidas) q.so_vencidas = 'true'
  return q
}

export function filtrosQuadroParaApi(f: FiltrosQuadro, hoje: string = hojeIso()): FiltrosAcoes {
  const r: FiltrosAcoes = {}
  if (f.busca.trim()) r.busca = f.busca.trim().slice(0, LIMITE_BUSCA)
  if (f.categoria) r.categoria = f.categoria
  if (f.tipo_nota) r.tipo_nota = f.tipo_nota
  if (f.responsavel_id !== '') r.responsavel_id = f.responsavel_id
  if (f.empresa_id !== '') r.empresa_id = f.empresa_id
  if (f.grupo_id !== '') r.grupo_id = f.grupo_id
  const { de, ate } = intervaloDoPeriodo(f.periodo, { de: f.de, ate: f.ate }, hoje)
  if (de) r.de = de
  if (ate) r.ate = ate
  if (f.so_vencidas) r.so_vencidas = true
  return r
}

/** Filtros da área "Filtros" ligados (busca e "só vencidas" ficam à vista e não contam). */
export function contarFiltrosQuadro(f: FiltrosQuadro): number {
  return [f.categoria, f.tipo_nota, f.responsavel_id, f.empresa_id, f.grupo_id].filter((v) => v !== '').length + (f.periodo !== 'tudo' ? 1 : 0)
}
