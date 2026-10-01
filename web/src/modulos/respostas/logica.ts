// Regras puras da tela de Respostas (sem Vue): categorias, filtros ↔ endereço (URL),
// validação do registro à mão, o que mudou na análise e o texto da exclusão.
import type {
  CanalManual,
  DadosAnaliseResposta,
  FiltrosRespostas,
  GrupoNota,
  Id,
  OrigemResposta,
  RespostaItem,
  TemaResposta,
  TipoNota,
} from '@/api/tipos'
import { formatarData, formatarDataHora, hojeIso } from '@/utils/datas'
import { dataIsoValida, ehPreset, intervaloDoPeriodo, type PresetPeriodo } from '@/utils/periodo'
import type { Tom } from '@/utils/rotulos'

// ── Categorias (grupo da nota) ──────────────────────────────────────────────

export const CATEGORIAS: Record<GrupoNota, { rotulo: string; plural: string; notas: string; tom: Tom }> = {
  detrator: { rotulo: 'Detrator', plural: 'Detratores', notas: 'notas 0 a 6', tom: 'erro' },
  neutro: { rotulo: 'Neutro', plural: 'Neutros', notas: 'notas 7 e 8 (no CSAT, 3)', tom: 'atencao' },
  promotor: { rotulo: 'Promotor', plural: 'Promotores', notas: 'notas 9 e 10', tom: 'sucesso' },
  insatisfeito: { rotulo: 'Insatisfeito', plural: 'Insatisfeitos', notas: 'notas 1 e 2 (CSAT)', tom: 'erro' },
  satisfeito: { rotulo: 'Satisfeito', plural: 'Satisfeitos', notas: 'notas 4 e 5 (CSAT)', tom: 'sucesso' },
}

/** Categoria de uma nota: NPS 0–6 detrator, 7–8 neutro, 9–10 promotor; CSAT 1–2 insatisfeito, 3 neutro, 4–5 satisfeito. */
export function categoriaDaNota(tipo: TipoNota, nota: number): GrupoNota {
  if (tipo === 'csat') return nota <= 2 ? 'insatisfeito' : nota === 3 ? 'neutro' : 'satisfeito'
  return nota <= 6 ? 'detrator' : nota <= 8 ? 'neutro' : 'promotor'
}

/** Quais notas formam a categoria, no tipo dado ("notas 0 a 6", "nota 3"...). */
export function notasDaCategoria(tipo: TipoNota, g: GrupoNota): string {
  if (tipo === 'csat') return g === 'neutro' ? 'nota 3' : g === 'satisfeito' || g === 'promotor' ? 'notas 4 e 5' : 'notas 1 e 2'
  return g === 'neutro' ? 'notas 7 e 8' : g === 'promotor' || g === 'satisfeito' ? 'notas 9 e 10' : 'notas 0 a 6'
}

/** Categorias que fazem sentido para o tipo escolhido (sem tipo: todas). */
export function categoriasDoTipo(tipo: TipoNota | ''): GrupoNota[] {
  if (tipo === 'nps') return ['detrator', 'neutro', 'promotor']
  if (tipo === 'csat') return ['insatisfeito', 'neutro', 'satisfeito']
  return ['detrator', 'neutro', 'promotor', 'insatisfeito', 'satisfeito']
}

function ehCategoria(g: string | null | undefined): g is GrupoNota {
  return !!g && Object.hasOwn(CATEGORIAS, g)
}

export function rotuloCategoria(g: string | null | undefined): string {
  return ehCategoria(g) ? CATEGORIAS[g].rotulo : g || '—'
}

export function tomCategoria(g: string | null | undefined, nota?: number | null, tipo?: TipoNota | null): Tom {
  if (ehCategoria(g)) return CATEGORIAS[g].tom
  if (typeof nota !== 'number') return 'neutro'
  if (tipo === 'csat') return nota <= 2 ? 'erro' : nota === 3 ? 'atencao' : 'sucesso'
  return nota <= 6 ? 'erro' : nota <= 8 ? 'atencao' : 'sucesso'
}

/** Faixa de nota editável conforme o tipo (NPS 0–10, CSAT 1–5); sem tipo, não há nota. */
export function faixaDaNota(tipo: TipoNota | null | undefined): { min: number; max: number } | null {
  if (tipo === 'nps') return { min: 0, max: 10 }
  if (tipo === 'csat') return { min: 1, max: 5 }
  return null
}

export const CANAIS_REGISTRO: { valor: CanalManual; rotulo: string }[] = [
  { valor: 'manual', rotulo: 'Anotação manual' },
  { valor: 'telefone', rotulo: 'Telefone' },
  { valor: 'whatsapp', rotulo: 'WhatsApp' },
  { valor: 'email', rotulo: 'E-mail' },
  { valor: 'reuniao', rotulo: 'Reunião' },
]

export const ORIGENS_RESPOSTA: Record<OrigemResposta, string> = {
  pesquisa: 'Respondida pelo cliente na pesquisa',
  manual: 'Registrada à mão pela equipe',
  importacao: 'Importada de uma planilha',
}

/** Selo curto para as respostas que não vieram da pesquisa (listas e histórico). */
export function seloOrigem(origem: OrigemResposta | string | null | undefined): string | null {
  return origem === 'manual' ? 'Registrada à mão' : origem === 'importacao' ? 'Importada' : null
}

/**
 * Quando foi a resposta, para mostrar. Usa `data` (a data da resposta) e, se não vier, `criada_em`.
 * A hora só aparece quando é a hora de verdade: com data informada (à mão ou importada), o servidor
 * guarda o dia ao meio-dia, então mostramos só o dia. Sem `respondida_em` no formato, vale a origem.
 */
export function quandoFoiResposta(r: {
  data?: string | null
  criada_em?: string | null
  origem?: OrigemResposta | string | null
  respondida_em?: string | null
}): string {
  const d = r.data ?? r.criada_em
  if (!d) return '—'
  const soDia = r.respondida_em !== undefined ? !!r.respondida_em : !!r.origem && r.origem !== 'pesquisa'
  return soDia ? formatarData(d) : formatarDataHora(d)
}

/** Os 6 temas do contrato, na ordem; usados se a lista da API não vier. */
export const TEMAS_PADRAO: TemaResposta[] = [
  { chave: 'prazo_entrega', rotulo: 'Prazo e entrega' },
  { chave: 'produto_avarias', rotulo: 'Produto e avarias' },
  { chave: 'atendimento', rotulo: 'Atendimento' },
  { chave: 'preco_condicoes', rotulo: 'Preço e condições' },
  { chave: 'comunicacao', rotulo: 'Comunicação' },
  { chave: 'sistema_pedidos', rotulo: 'Sistema e pedidos' },
]

export function rotuloTema(chave: string, temas: TemaResposta[] = TEMAS_PADRAO): string {
  return temas.find((t) => t.chave === chave)?.rotulo ?? TEMAS_PADRAO.find((t) => t.chave === chave)?.rotulo ?? chave
}

// ── Filtros ↔ endereço ──────────────────────────────────────────────────────

/** A API aceita buscas de até 100 caracteres (o campo também corta; um texto colado maior seria recusado). */
export const LIMITE_BUSCA = 100

export type Arquivadas = 'false' | 'true' | 'todas'

export interface FiltrosTela {
  busca: string
  periodo: PresetPeriodo
  de: string
  ate: string
  data_por: 'resposta' | 'entrada'
  categoria: GrupoNota | ''
  tipo_nota: TipoNota | ''
  grupo_id: Id | ''
  empresa_id: Id | ''
  tema: string
  perfil_id: Id | ''
  arquivadas: Arquivadas
  /** Só respostas de empresas ativas (as sem empresa continuam), como o "Só empresas ativas" do painel. */
  so_ativos: boolean
  contato_id: Id | ''
  pagina: number
}

export const FILTROS_PADRAO: Readonly<FiltrosTela> = Object.freeze<FiltrosTela>({
  busca: '',
  periodo: 'tudo',
  de: '',
  ate: '',
  data_por: 'resposta',
  categoria: '',
  tipo_nota: '',
  grupo_id: '',
  empresa_id: '',
  tema: '',
  perfil_id: '',
  arquivadas: 'false',
  so_ativos: false,
  contato_id: '',
  pagina: 1,
})

/** Mesmo formato do `route.query` do Vue Router. */
export type Consulta = Record<string, string | null | (string | null)[] | undefined>

function um(q: Consulta, k: string): string {
  const v = q[k]
  const s = Array.isArray(v) ? v[0] : v
  return typeof s === 'string' ? s.trim() : ''
}

/** Identificador vindo do endereço: texto curto, sem espaços. */
function id(v: string): Id | '' {
  return /^[\w-]{1,40}$/.test(v) ? v : ''
}

/** Lê os filtros do endereço (`/respostas?categoria=detrator&periodo=30`), ignorando o que não vale. */
export function filtrosDaQuery(q: Consulta): FiltrosTela {
  const de = um(q, 'de')
  const ate = um(q, 'ate')
  const temData = dataIsoValida(de) || dataIsoValida(ate)
  const periodo = um(q, 'periodo')
  const categoria = um(q, 'categoria')
  const tipo = um(q, 'tipo_nota')
  const arquivadas = um(q, 'arquivadas')
  const pagina = Number.parseInt(um(q, 'pagina'), 10)
  return {
    busca: um(q, 'busca').slice(0, LIMITE_BUSCA),
    // "personalizado" sem datas também volta (a pessoa apagou as datas): fica sem filtro de data até escolher.
    periodo: temData ? 'personalizado' : ehPreset(periodo) ? periodo : FILTROS_PADRAO.periodo,
    de: dataIsoValida(de) ? de : '',
    ate: dataIsoValida(ate) ? ate : '',
    data_por: um(q, 'data_por') === 'entrada' ? 'entrada' : 'resposta',
    categoria: Object.hasOwn(CATEGORIAS, categoria) ? (categoria as GrupoNota) : '',
    tipo_nota: tipo === 'nps' || tipo === 'csat' ? tipo : '',
    grupo_id: id(um(q, 'grupo_id')),
    empresa_id: id(um(q, 'empresa_id')),
    tema: /^[a-z_]{1,40}$/.test(um(q, 'tema')) ? um(q, 'tema') : '',
    perfil_id: id(um(q, 'perfil_id')),
    arquivadas: arquivadas === 'true' || arquivadas === 'todas' ? arquivadas : 'false',
    so_ativos: um(q, 'so_ativos') === 'true',
    contato_id: id(um(q, 'contato_id')),
    pagina: Number.isFinite(pagina) && pagina > 1 ? pagina : 1,
  }
}

/** Escreve os filtros no endereço, só com o que foge do padrão (endereço curto e fácil de compartilhar). */
export function queryDosFiltros(f: FiltrosTela): Record<string, string> {
  const q: Record<string, string> = {}
  if (f.busca.trim()) q.busca = f.busca.trim()
  if (f.periodo === 'personalizado') {
    if (dataIsoValida(f.de)) q.de = f.de
    if (dataIsoValida(f.ate)) q.ate = f.ate
    if (!q.de && !q.ate) q.periodo = 'personalizado'
  } else if (f.periodo !== FILTROS_PADRAO.periodo) q.periodo = f.periodo
  if (f.data_por === 'entrada') q.data_por = 'entrada'
  if (f.categoria) q.categoria = f.categoria
  if (f.tipo_nota) q.tipo_nota = f.tipo_nota
  if (f.grupo_id !== '') q.grupo_id = String(f.grupo_id)
  if (f.empresa_id !== '') q.empresa_id = String(f.empresa_id)
  if (f.tema) q.tema = f.tema
  if (f.perfil_id !== '') q.perfil_id = String(f.perfil_id)
  if (f.arquivadas !== 'false') q.arquivadas = f.arquivadas
  if (f.so_ativos) q.so_ativos = 'true'
  if (f.contato_id !== '') q.contato_id = String(f.contato_id)
  if (f.pagina > 1) q.pagina = String(f.pagina)
  return q
}

/** Os filtros prontos para GET /respostas (e para o CSV, sem a página). */
export function filtrosParaApi(f: FiltrosTela, hoje: string = hojeIso()): FiltrosRespostas {
  const r: FiltrosRespostas = { arquivadas: f.arquivadas, pagina: f.pagina }
  if (f.busca.trim()) r.busca = f.busca.trim().slice(0, LIMITE_BUSCA)
  const { de, ate } = intervaloDoPeriodo(f.periodo, { de: f.de, ate: f.ate }, hoje)
  if (de) r.de = de
  if (ate) r.ate = ate
  if ((de || ate) && f.data_por === 'entrada') r.data_por = 'entrada'
  if (f.categoria) r.categoria = f.categoria
  if (f.tipo_nota) r.tipo_nota = f.tipo_nota
  if (f.grupo_id !== '') r.grupo_id = f.grupo_id
  if (f.empresa_id !== '') r.empresa_id = f.empresa_id
  if (f.tema) r.tema = f.tema
  if (f.perfil_id !== '') r.perfil_id = f.perfil_id
  if (f.contato_id !== '') r.contato_id = f.contato_id
  if (f.so_ativos) r.so_ativos = true
  return r
}

/** Quantos filtros da área "Filtros" estão ligados (busca, período e contato ficam de fora: aparecem na tela). */
export function contarFiltrosAtivos(f: FiltrosTela): number {
  return (
    [f.categoria, f.tipo_nota, f.grupo_id, f.empresa_id, f.tema, f.perfil_id].filter((v) => v !== '').length +
    (f.arquivadas !== 'false' ? 1 : 0) +
    (f.so_ativos ? 1 : 0)
  )
}

/** Os mesmos filtros (comparando como ficam no endereço, então 1 e "1" são iguais). */
export function mesmosFiltros(a: FiltrosTela, b: FiltrosTela): boolean {
  return JSON.stringify(queryDosFiltros(a)) === JSON.stringify(queryDosFiltros(b))
}

/** Mesma busca, ignorando a página. Útil para saber se só a página mudou. */
export function mesmaBusca(a: FiltrosTela, b: FiltrosTela): boolean {
  return mesmosFiltros({ ...a, pagina: 1 }, { ...b, pagina: 1 })
}

// ── Registrar resposta ──────────────────────────────────────────────────────

export const LIMITE_COMENTARIO = 4000
export const LIMITE_ANALISE = 2000

export interface DadosRegistro {
  contatoId: Id | null
  nota: number | null
  data: string
  comentario: string
}

/** Erros por campo (mesmas chaves da API) antes de enviar. */
export function validarRegistro(d: DadosRegistro, hoje: string = hojeIso()): Record<string, string> {
  const e: Record<string, string> = {}
  if (d.contatoId === null || d.contatoId === '') e.contato_id = 'Escolha o contato que deu a nota.'
  if (d.nota === null || !Number.isInteger(d.nota) || d.nota < 0 || d.nota > 10) e.nota = 'Escolha a nota, de 0 a 10.'
  if (d.data) {
    if (!dataIsoValida(d.data)) e.data = 'Confira a data.'
    else if (d.data > hoje) e.data = 'A data não pode ser depois de hoje.'
    else if (d.data < '2000-01-01') e.data = 'Use uma data a partir de 01/01/2000.'
  }
  if (d.comentario.length > LIMITE_COMENTARIO) e.comentario = 'O comentário passa de 4.000 caracteres. Resuma um pouco.'
  return e
}

// ── Analisar ────────────────────────────────────────────────────────────────

export interface EdicaoAnalise {
  nota: number | null
  comentario: string
  o_que_faltou: string
  o_que_combinamos: string
  temas: string[]
}

export function edicaoInicial(r: Pick<RespostaItem, 'nota' | 'comentario' | 'o_que_faltou' | 'o_que_combinamos' | 'temas'>): EdicaoAnalise {
  return {
    nota: typeof r.nota === 'number' ? r.nota : null,
    comentario: r.comentario ?? '',
    o_que_faltou: r.o_que_faltou ?? '',
    o_que_combinamos: r.o_que_combinamos ?? '',
    temas: [...(r.temas ?? [])],
  }
}

function mesmoTexto(a: string | null | undefined, b: string): boolean {
  return (a ?? '').trim() === b.trim()
}

/** Só o que mudou (PATCH parcial). Temas só vão se mudarem: mandar temas marca a escolha como manual. */
export function mudancasAnalise(
  r: Pick<RespostaItem, 'nota' | 'comentario' | 'o_que_faltou' | 'o_que_combinamos' | 'temas' | 'tipo_nota'>,
  e: EdicaoAnalise,
  ordemTemas: TemaResposta[] = TEMAS_PADRAO,
): DadosAnaliseResposta {
  const d: DadosAnaliseResposta = {}
  if (faixaDaNota(r.tipo_nota) && e.nota !== null && e.nota !== r.nota) d.nota = e.nota
  if (!mesmoTexto(r.comentario, e.comentario)) d.comentario = e.comentario.trim() || null
  if (!mesmoTexto(r.o_que_faltou, e.o_que_faltou)) d.o_que_faltou = e.o_que_faltou.trim() || null
  if (!mesmoTexto(r.o_que_combinamos, e.o_que_combinamos)) d.o_que_combinamos = e.o_que_combinamos.trim() || null
  const antes = [...(r.temas ?? [])].sort().join(',')
  const depois = [...e.temas].sort().join(',')
  if (antes !== depois) {
    const ordem = ordemTemas.map((t) => t.chave)
    d.temas = [...e.temas].sort((a, b) => (ordem.indexOf(a) + 1 || 99) - (ordem.indexOf(b) + 1 || 99))
  }
  return d
}

export function validarAnalise(e: EdicaoAnalise, tipo: TipoNota | null | undefined): Record<string, string> {
  const erros: Record<string, string> = {}
  const faixa = faixaDaNota(tipo)
  if (faixa && (e.nota === null || e.nota < faixa.min || e.nota > faixa.max || !Number.isInteger(e.nota))) {
    erros.nota = `Escolha uma nota de ${faixa.min} a ${faixa.max}.`
  }
  if (e.comentario.length > LIMITE_COMENTARIO) erros.comentario = 'O comentário passa de 4.000 caracteres.'
  if (e.o_que_faltou.length > LIMITE_ANALISE) erros.o_que_faltou = 'Use até 2.000 caracteres.'
  if (e.o_que_combinamos.length > LIMITE_ANALISE) erros.o_que_combinamos = 'Use até 2.000 caracteres.'
  return erros
}

// ── Excluir de vez ──────────────────────────────────────────────────────────

/** Confirmação que diz exatamente o que some (a resposta e quantas ações). */
export function textoExclusao(
  r: Pick<RespostaItem, 'contato' | 'nota' | 'data'>,
  qtdAcoes: number,
): { titulo: string; mensagem: string; confirmar: string } {
  const nome = r.contato?.nome ?? 'cliente sem cadastro'
  const detalhes = [typeof r.nota === 'number' ? `nota ${r.nota}` : '', r.data ? `de ${formatarData(r.data)}` : ''].filter(Boolean).join(', ')
  const resposta = `A resposta${detalhes ? ` (${detalhes})` : ''}`
  const n = Math.max(0, Math.floor(qtdAcoes))
  const oQue =
    n === 0
      ? `${resposta} será apagada de vez. Nenhuma ação está ligada a ela.`
      : n === 1
        ? `${resposta} e a ação ligada a ela serão apagadas de vez.`
        : `${resposta} e as ${n} ações ligadas a ela serão apagadas de vez.`
  // A "última nota" do contato só muda se esta for a resposta mais recente dele (e a tela não sabe): texto condicional.
  const ultimaNota = r.contato ? ' Se esta for a resposta mais recente do contato, a última nota dele passa a ser a da resposta anterior.' : ''
  return {
    titulo: `Excluir a resposta de ${nome}?`,
    mensagem: `${oQue}${ultimaNota} Não dá para desfazer. Se você só quer tirar a resposta dos números, use Arquivar.`,
    confirmar: n ? 'Excluir resposta e ações' : 'Excluir resposta',
  }
}
