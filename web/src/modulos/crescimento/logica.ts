// Regras puras do módulo Crescimento (etapa 5c), sem Vue: abas, filtros ↔ endereço ↔ API, rótulos das situações e dos
// resultados, quem indicou, links de WhatsApp e e-mail, o texto da oferta e a edição de uma indicação.
import type {
  CanalOferta,
  DadosEdicaoIndicacao,
  FiltrosIndicacoes,
  FiltrosOportunidades,
  Id,
  Indicacao,
  ListaOportunidade,
  Oportunidade,
  ResultadoOferta,
  SituacaoIndicacao,
  ValorDecimal,
} from '@/api/tipos'
import { hojeIso } from '@/utils/datas'
import { formatarDecimal, lerMoeda, telefoneWhatsapp } from '@/utils/formatos'
import { dataIsoValida, ehPreset, intervaloDoPeriodo, type PresetPeriodo } from '@/utils/periodo'
import type { Tom } from '@/utils/rotulos'
import { renderizarMensagem } from '@/modulos/configuracoes/mensagens'

// ── Abas ────────────────────────────────────────────────────────────────────

export type AbaCrescimento = 'indicacoes' | 'oportunidades'

export const ABAS_CRESCIMENTO: { valor: AbaCrescimento; rotulo: string }[] = [
  { valor: 'indicacoes', rotulo: 'Indicações' },
  { valor: 'oportunidades', rotulo: 'Oportunidades' },
]

export const ABA_PADRAO: AbaCrescimento = 'indicacoes'

export function ehAbaCrescimento(v: unknown): v is AbaCrescimento {
  return v === 'indicacoes' || v === 'oportunidades'
}

export function rotuloAbaCrescimento(a: AbaCrescimento): string {
  return ABAS_CRESCIMENTO.find((x) => x.valor === a)?.rotulo ?? a
}

// ── Rótulos ─────────────────────────────────────────────────────────────────

export const ORDEM_SITUACOES: SituacaoIndicacao[] = ['nova', 'em_contato', 'cliente', 'nao_avancou']

/** `rotulo`: o selo de uma indicação; `filtro`: o botão da lista (no plural). */
export const SITUACOES_INDICACAO: Record<SituacaoIndicacao, { rotulo: string; filtro: string; tom: Tom }> = {
  nova: { rotulo: 'Nova', filtro: 'Novas', tom: 'info' },
  em_contato: { rotulo: 'Em contato', filtro: 'Em contato', tom: 'atencao' },
  cliente: { rotulo: 'Virou cliente', filtro: 'Viraram cliente', tom: 'sucesso' },
  nao_avancou: { rotulo: 'Não avançou', filtro: 'Não avançaram', tom: 'neutro' },
}

export function ehSituacaoIndicacao(v: unknown): v is SituacaoIndicacao {
  return typeof v === 'string' && (ORDEM_SITUACOES as string[]).includes(v)
}

export function situacaoIndicacao(v: string | null | undefined): { rotulo: string; tom: Tom } {
  return ehSituacaoIndicacao(v) ? SITUACOES_INDICACAO[v] : { rotulo: v || '—', tom: 'neutro' }
}

export const ORDEM_LISTAS: ListaOportunidade[] = ['pode_crescer', 'promotores']

/** As duas listas de Oportunidades, com a frase do critério de cada uma. */
export const LISTAS_OPORTUNIDADE: Record<ListaOportunidade, { rotulo: string; criterio: string }> = {
  pode_crescer: {
    rotulo: 'Pode crescer',
    criterio:
      'Empresas com NPS de 0 para cima e valor mensal abaixo da mediana nos últimos 90 dias: o quadrante “Pode crescer” de Relatórios › Empresas. Maior NPS primeiro e, no empate, o menor valor.',
  },
  promotores: {
    rotulo: 'Promotores recentes',
    criterio: 'Empresas com uma nota 9 ou 10 nos últimos 30 dias, com o promotor mais recente primeiro.',
  },
}

export const REGRA_DE_OURO =
  'Regra de ouro: nunca entram empresas inativas, com detrator (nota 0 a 6) nos últimos 90 dias, com plano de ação aberto ou com a saúde da conta em Risco, nem contatos que saíram da lista.'

export function ehListaOportunidade(v: unknown): v is ListaOportunidade {
  return v === 'pode_crescer' || v === 'promotores'
}

export const ORDEM_RESULTADOS: ResultadoOferta[] = ['aceitou', 'recusou', 'sem_resposta']

export const RESULTADOS_OFERTA: Record<ResultadoOferta, { rotulo: string; tom: Tom }> = {
  aceitou: { rotulo: 'Aceitou', tom: 'sucesso' },
  recusou: { rotulo: 'Recusou', tom: 'neutro' },
  sem_resposta: { rotulo: 'Sem resposta', tom: 'atencao' },
}

export function resultadoOferta(v: string | null | undefined): { rotulo: string; tom: Tom } | null {
  if (!v) return null
  return RESULTADOS_OFERTA[v as ResultadoOferta] ?? { rotulo: v, tom: 'neutro' }
}

// ── Números ─────────────────────────────────────────────────────────────────

/** Decimal da API (número ou texto "1250.00") → número; vazio ou inválido → null. */
export function numeroDecimal(v: ValorDecimal | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

/**
 * Taxa em % inteiro (meio para cima) de `parte` sobre `total`; sem total, null. Calculada das contagens do resumo: o
 * contrato não diz a escala de `taxa` (0–1 ou 0–100), e a conta dá o mesmo número.
 */
export function taxa(parte: number | null | undefined, total: number | null | undefined): number | null {
  if (typeof parte !== 'number' || typeof total !== 'number' || total <= 0) return null
  return Math.round((parte / total) * 100)
}

// ── Pessoas e contato ───────────────────────────────────────────────────────

export function primeiroNome(nome: string | null | undefined): string {
  return (nome ?? '').trim().split(/\s+/)[0] ?? ''
}

export const NAO_QUIS_SE_IDENTIFICAR = 'Não quis se identificar'
export const INDICADOR_NAO_INFORMADO = 'Não informado'
/** Veio pela pesquisa, mas o contato e a empresa de quem indicou foram apagados (a indicação fica). */
export const INDICADOR_EXCLUIDO = 'Não informado (contato excluído)'

/**
 * Quem indicou, como a lista mostra: "Mercado Bom Preço · Ana" ou, quando a pessoa pediu na pesquisa para não ser
 * identificada, "Não quis se identificar". Registro à mão sem indicador: "Não informado"; pela pesquisa, com o contato
 * e a empresa de quem indicou apagados depois: "Não informado (contato excluído)".
 */
export function quemIndicou(i: Pick<Indicacao, 'indicador' | 'pode_identificar' | 'origem'>): string {
  if (i.origem !== 'manual' && !i.pode_identificar) return NAO_QUIS_SE_IDENTIFICAR
  const partes = nomesDoIndicador(i)
  if (partes.length) return partes.join(' · ')
  return i.origem === 'manual' ? INDICADOR_NAO_INFORMADO : INDICADOR_EXCLUIDO
}

/** A lista não mostra o nome de quem indicou (não quis aparecer ou não se sabe): o texto fica mais apagado. */
export function semNomeDoIndicador(i: Pick<Indicacao, 'indicador' | 'pode_identificar' | 'origem'>): boolean {
  return (i.origem !== 'manual' && !i.pode_identificar) || !nomesDoIndicador(i).length
}

/** Empresa e nome de quem indicou (o que a API mandou), para o painel. */
export function nomesDoIndicador(i: Pick<Indicacao, 'indicador'>): string[] {
  return [i.indicador?.empresa?.nome, i.indicador?.contato?.nome].map((s) => (s ?? '').trim()).filter(Boolean)
}

/** Link do WhatsApp (wa.me, número com o 55), com o texto pronto se vier; sem telefone válido, null. */
export function linkWhatsapp(telefone: string | null | undefined, texto?: string | null): string | null {
  const numero = telefoneWhatsapp(telefone)
  if (!numero) return null
  return `https://wa.me/${numero}${texto ? `?text=${encodeURIComponent(texto)}` : ''}`
}

/** Link mailto: com assunto e corpo (codificados à mão: o "+" do URLSearchParams apareceria no e-mail). */
export function linkEmail(email: string | null | undefined, assunto?: string | null, corpo?: string | null): string | null {
  const e = (email ?? '').trim()
  if (!e || !e.includes('@')) return null
  const partes = [assunto ? `subject=${encodeURIComponent(assunto)}` : '', corpo ? `body=${encodeURIComponent(corpo)}` : ''].filter(Boolean)
  return `mailto:${encodeURIComponent(e).replace(/%40/g, '@')}${partes.length ? `?${partes.join('&')}` : ''}`
}

// ── Oferta ──────────────────────────────────────────────────────────────────

export const LIMITE_TEXTO_OFERTA_ENVIO = 2000

export interface ValoresOferta {
  /** Nome do contato (vale o primeiro nome). */
  nome?: string | null
  /** A empresa que usa o Toqqi (a conta). */
  empresa?: string | null
  /** A empresa do cliente. */
  empresa_cliente?: string | null
  /** Quem está oferecendo (vale o primeiro nome). */
  representante?: string | null
}

/** O texto da oferta com as variáveis trocadas: {nome}, {empresa}, {empresa_cliente} e {representante}. */
export function textoOferta(modelo: string | null | undefined, v: ValoresOferta): string {
  const comRepresentante = (modelo ?? '').replace(/\{representante\}/g, primeiroNome(v.representante))
  return renderizarMensagem(comRepresentante, v).slice(0, LIMITE_TEXTO_OFERTA_ENVIO)
}

export function assuntoOferta(empresaCliente: string | null | undefined): string {
  const e = (empresaCliente ?? '').trim()
  return e ? `Uma condição especial para a ${e}` : 'Uma condição especial para você'
}

/** Por onde a oferta sai: WhatsApp quando o contato tem telefone; só e-mail → mailto:; sem contato → null. */
export function linkDaOferta(o: Pick<Oportunidade, 'contato' | 'empresa'>, texto: string): { canal: CanalOferta; href: string } | null {
  const c = o.contato
  if (!c) return null
  const whatsapp = linkWhatsapp(c.telefone, texto)
  if (whatsapp) return { canal: 'whatsapp', href: whatsapp }
  const email = linkEmail(c.email, assuntoOferta(o.empresa.nome), texto)
  return email ? { canal: 'email', href: email } : null
}

// ── Lista ───────────────────────────────────────────────────────────────────

/**
 * Página que veio vazia depois da primeira (a última linha dela saiu, ou o endereço é antigo): a última página que
 * existe, sempre antes da atual (não fica indo e voltando se o total vier estranho).
 */
export function ultimaPaginaQueExiste(pagina: number, total: number, porPagina: number): number {
  const ultima = Math.ceil(Math.max(0, total) / Math.max(1, porPagina))
  return Math.max(1, Math.min(pagina - 1, ultima))
}

/**
 * A linha que recebe o foco quando a linha `id` sai da lista: a seguinte (na ordem de antes) que continua nela; sem
 * ela, a anterior; sem nenhuma das antigas, a primeira da lista nova. Lista vazia: null (o foco vai para o título).
 */
export function linhaVizinha(ordem: readonly string[], id: string, atuais: readonly string[]): string | null {
  const ficou = (x: string) => x !== id && atuais.includes(x)
  const i = ordem.indexOf(id)
  const depois = i >= 0 ? ordem.slice(i + 1).find(ficou) : undefined
  const antes = i >= 0 ? ordem.slice(0, i).reverse().find(ficou) : undefined
  return depois ?? antes ?? atuais.find((x) => x !== id) ?? null
}

// ── Filtros ↔ endereço ↔ API ────────────────────────────────────────────────

export const LIMITE_BUSCA = 100

type Consulta = Record<string, string | null | (string | null)[] | undefined>

function um(q: Consulta, k: string): string {
  const v = q[k]
  const s = Array.isArray(v) ? v[0] : v
  return typeof s === 'string' ? s.trim() : ''
}
const idValido = (v: string): Id | '' => (/^[\w-]{1,40}$/.test(v) ? v : '')
function paginaValida(v: string): number {
  const n = Number(v)
  return Number.isInteger(n) && n > 1 && n < 100_000 ? n : 1
}

export interface FiltrosIndicacoesTela {
  situacao: SituacaoIndicacao | ''
  responsavel_id: Id | ''
  periodo: PresetPeriodo
  de: string
  ate: string
  busca: string
  pagina: number
}

export const FILTROS_INDICACOES_PADRAO: Readonly<FiltrosIndicacoesTela> = Object.freeze<FiltrosIndicacoesTela>({
  situacao: '',
  responsavel_id: '',
  periodo: 'tudo',
  de: '',
  ate: '',
  busca: '',
  pagina: 1,
})

export function filtrosIndicacoesDaQuery(q: Consulta): FiltrosIndicacoesTela {
  const de = um(q, 'de')
  const ate = um(q, 'ate')
  const temData = dataIsoValida(de) || dataIsoValida(ate)
  const periodo = um(q, 'periodo')
  const situacao = um(q, 'situacao')
  return {
    situacao: ehSituacaoIndicacao(situacao) ? situacao : '',
    responsavel_id: idValido(um(q, 'responsavel_id')),
    periodo: temData ? 'personalizado' : ehPreset(periodo) ? periodo : 'tudo',
    de: dataIsoValida(de) ? de : '',
    ate: dataIsoValida(ate) ? ate : '',
    busca: um(q, 'busca').slice(0, LIMITE_BUSCA),
    pagina: paginaValida(um(q, 'pagina')),
  }
}

export function queryDosFiltrosIndicacoes(f: FiltrosIndicacoesTela): Record<string, string> {
  const q: Record<string, string> = {}
  if (f.situacao) q.situacao = f.situacao
  if (f.responsavel_id !== '') q.responsavel_id = String(f.responsavel_id)
  if (f.periodo === 'personalizado') {
    if (dataIsoValida(f.de)) q.de = f.de
    if (dataIsoValida(f.ate)) q.ate = f.ate
    if (!q.de && !q.ate) q.periodo = 'personalizado'
  } else if (f.periodo !== 'tudo') q.periodo = f.periodo
  if (f.busca.trim()) q.busca = f.busca.trim()
  if (f.pagina > 1) q.pagina = String(f.pagina)
  return q
}

export function filtrosIndicacoesParaApi(f: FiltrosIndicacoesTela, hoje: string = hojeIso()): FiltrosIndicacoes {
  const r: FiltrosIndicacoes = {}
  if (f.situacao) r.situacao = f.situacao
  // Ids como texto: o da lista (número) e o do endereço (texto) pedem a mesma coisa (e não buscam duas vezes).
  if (f.responsavel_id !== '') r.responsavel_id = String(f.responsavel_id)
  const { de, ate } = intervaloDoPeriodo(f.periodo, { de: f.de, ate: f.ate }, hoje)
  if (de) r.de = de
  if (ate) r.ate = ate
  if (f.busca.trim()) r.busca = f.busca.trim().slice(0, LIMITE_BUSCA)
  if (f.pagina > 1) r.pagina = f.pagina
  return r
}

/** Filtros da área "Filtros" ligados (a situação e a busca ficam à vista e não contam). */
export function contarFiltrosIndicacoes(f: FiltrosIndicacoesTela): number {
  return (f.responsavel_id !== '' ? 1 : 0) + (f.periodo !== 'tudo' ? 1 : 0)
}

/** Mudou alguma coisa além da página? (aí a lista volta para a página 1). */
export function mesmaBuscaIndicacoes(a: FiltrosIndicacoesTela, b: FiltrosIndicacoesTela): boolean {
  return JSON.stringify({ ...a, pagina: 0 }) === JSON.stringify({ ...b, pagina: 0 })
}

export interface FiltrosOportunidadesTela {
  lista: ListaOportunidade
  grupo_id: Id | ''
  responsavel_id: Id | ''
  pagina: number
}

export const FILTROS_OPORTUNIDADES_PADRAO: Readonly<FiltrosOportunidadesTela> = Object.freeze<FiltrosOportunidadesTela>({
  lista: 'pode_crescer',
  grupo_id: '',
  responsavel_id: '',
  pagina: 1,
})

export function filtrosOportunidadesDaQuery(q: Consulta): FiltrosOportunidadesTela {
  const lista = um(q, 'lista')
  return {
    lista: ehListaOportunidade(lista) ? lista : 'pode_crescer',
    grupo_id: idValido(um(q, 'grupo_id')),
    responsavel_id: idValido(um(q, 'responsavel_id')),
    pagina: paginaValida(um(q, 'pagina')),
  }
}

export function queryDosFiltrosOportunidades(f: FiltrosOportunidadesTela): Record<string, string> {
  const q: Record<string, string> = {}
  if (f.lista !== 'pode_crescer') q.lista = f.lista
  if (f.grupo_id !== '') q.grupo_id = String(f.grupo_id)
  if (f.responsavel_id !== '') q.responsavel_id = String(f.responsavel_id)
  if (f.pagina > 1) q.pagina = String(f.pagina)
  return q
}

export function filtrosOportunidadesParaApi(f: FiltrosOportunidadesTela): FiltrosOportunidades {
  const r: FiltrosOportunidades = { lista: f.lista }
  if (f.grupo_id !== '') r.grupo_id = String(f.grupo_id)
  if (f.responsavel_id !== '') r.responsavel_id = String(f.responsavel_id)
  if (f.pagina > 1) r.pagina = f.pagina
  return r
}

export function mesmaBuscaOportunidades(a: FiltrosOportunidadesTela, b: FiltrosOportunidadesTela): boolean {
  return JSON.stringify({ ...a, pagina: 0 }) === JSON.stringify({ ...b, pagina: 0 })
}

// ── Edição de uma indicação (painel) ────────────────────────────────────────

export const LIMITE_MOTIVO = 300

/** O que o painel edita: o valor é texto ("1.250,00"), como a pessoa digita. */
export interface EdicaoIndicacao {
  situacao: SituacaoIndicacao
  valor_mensal: string
  motivo: string
  responsavel_id: Id | ''
}

export function edicaoDaIndicacao(i: Indicacao): EdicaoIndicacao {
  return {
    situacao: i.situacao,
    valor_mensal: formatarDecimal(i.valor_mensal),
    motivo: i.motivo ?? '',
    responsavel_id: i.responsavel?.id ?? '',
  }
}

/** Erros antes de salvar (mesmas chaves da API): virar cliente pede o valor mensal (pode ser 0). */
export function validarEdicaoIndicacao(e: EdicaoIndicacao): Record<string, string> {
  const erros: Record<string, string> = {}
  if (e.situacao === 'cliente') {
    const v = e.valor_mensal.trim() ? lerMoeda(e.valor_mensal) : null
    if (v === null) erros.valor_mensal = e.valor_mensal.trim() ? 'Digite um valor, ex.: 1.250,00.' : 'Informe o valor mensal do novo cliente (pode ser 0).'
    else if (v < 0) erros.valor_mensal = 'O valor não pode ser negativo.'
  }
  if (e.situacao === 'nao_avancou' && e.motivo.trim().length > LIMITE_MOTIVO) erros.motivo = `Use até ${LIMITE_MOTIVO} caracteres.`
  return erros
}

/**
 * Só o que mudou (PATCH). Virar cliente (ou mudar o valor de quem já é) manda a situação com o valor; o motivo vai com
 * 'nao_avancou'. As outras situações não mandam valor nem motivo (a API limpa o valor).
 */
export function mudancasIndicacao(i: Indicacao, e: EdicaoIndicacao): DadosEdicaoIndicacao {
  const d: DadosEdicaoIndicacao = {}
  const mudouSituacao = e.situacao !== i.situacao
  if (mudouSituacao) d.situacao = e.situacao
  if (e.situacao === 'cliente') {
    const v = e.valor_mensal.trim() ? lerMoeda(e.valor_mensal) : null
    if (mudouSituacao || v !== numeroDecimal(i.valor_mensal)) {
      d.situacao = 'cliente'
      d.valor_mensal = v
    }
  }
  if (e.situacao === 'nao_avancou') {
    const m = e.motivo.trim() || null
    if (mudouSituacao || m !== ((i.motivo ?? '').trim() || null)) {
      d.situacao = 'nao_avancou'
      d.motivo = m
    }
  }
  if (String(e.responsavel_id) !== String(i.responsavel?.id ?? '')) d.responsavel_id = e.responsavel_id === '' ? null : e.responsavel_id
  return d
}

/** A indicação depois do PATCH, quando a API não devolve o corpo: o que mudou por cima da antiga. */
export function aplicarMudancas(i: Indicacao, d: DadosEdicaoIndicacao, responsavel: { id: Id; nome: string } | null): Indicacao {
  const situacao = d.situacao ?? i.situacao
  return {
    ...i,
    situacao,
    valor_mensal: situacao === 'cliente' ? (d.valor_mensal !== undefined ? d.valor_mensal : i.valor_mensal) : null,
    motivo: d.motivo !== undefined ? d.motivo : i.motivo,
    responsavel: d.responsavel_id !== undefined ? (d.responsavel_id === null ? null : responsavel) : i.responsavel,
    atualizada_em: new Date().toISOString(),
  }
}
