// Regras puras de Auditoria › E-mails enviados (docs/api-etapa-5e.md §5 e §6.3): período (padrão 30 dias, até 90),
// filtros, "Ver só as falhas" e os textos. Sem Vue, para testar com facilidade.
import type { FiltrosEmailsEnviados, SituacaoEmailEnviado, TipoEmailEnviado } from '@/api/tipos'
import { hojeIso } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import { dataIsoValida, erroPeriodoEscolhido, somarDias } from '@/utils/periodo'
import type { Tom } from '@/utils/rotulos'

/** O registro guarda os últimos 90 dias (a limpeza apaga o resto). */
export const DIAS_GUARDADOS = 90

// ── Abas da Auditoria ───────────────────────────────────────────────────────

export type AbaAuditoria = 'atividades' | 'emails'

export const ABAS_AUDITORIA: { valor: AbaAuditoria; rotulo: string }[] = [
  { valor: 'atividades', rotulo: 'Atividades' },
  { valor: 'emails', rotulo: 'E-mails enviados' },
]

/**
 * A aba que o endereço pede: /auditoria/emails ou /auditoria?aba=emails abrem "E-mails enviados"; o resto (inclusive
 * /auditoria/atividades), "Atividades".
 */
export function abaAuditoriaDaRota(param: unknown, query: unknown): AbaAuditoria {
  const primeiro = (v: unknown) => (Array.isArray(v) ? v[0] : v)
  return primeiro(param) === 'emails' || primeiro(query) === 'emails' ? 'emails' : 'atividades'
}

export type PeriodoEmails = '7' | '30' | '90' | 'personalizado'

export const PERIODOS_EMAILS: { valor: PeriodoEmails; rotulo: string }[] = [
  { valor: '7', rotulo: 'Últimos 7 dias' },
  { valor: '30', rotulo: 'Últimos 30 dias' },
  { valor: '90', rotulo: 'Últimos 90 dias' },
  { valor: 'personalizado', rotulo: 'Escolher as datas' },
]

/** Os tipos na ordem do filtro, com os mesmos rótulos da API (`tipo_rotulo`). Boas-vindas e Cobrança existem na API,
 *  mas hoje nenhum e-mail sai com eles (usuário criado pela equipe e assinatura não mandam e-mail): ficam fora do filtro
 *  para não oferecer uma opção sempre vazia; uma linha com eles ainda aparece com o rótulo da API. */
export const TIPOS_EMAIL: { valor: TipoEmailEnviado; rotulo: string }[] = [
  { valor: 'convite', rotulo: 'Convite de pesquisa' },
  { valor: 'lembrete', rotulo: 'Lembrete' },
  { valor: 'agradecimento', rotulo: 'Agradecimento' },
  { valor: 'teste', rotulo: 'E-mail de teste' },
  { valor: 'confirmacao', rotulo: 'Confirmação de e-mail' },
  { valor: 'senha', rotulo: 'Redefinição de senha' },
  { valor: 'alerta_risco', rotulo: 'Alerta de risco' },
  { valor: 'resumo_semanal', rotulo: 'Resumo semanal' },
  { valor: 'pico', rotulo: 'Pico de reclamações' },
  { valor: 'indicacao', rotulo: 'Nova indicação' },
  { valor: 'aviso', rotulo: 'Aviso aos administradores' },
]

export const SITUACOES_EMAIL: Record<SituacaoEmailEnviado, { rotulo: string; tom: Tom }> = {
  enviado: { rotulo: 'Enviado', tom: 'sucesso' },
  falhou: { rotulo: 'Falhou', tom: 'erro' },
}

/** Situação com rótulo e tom (uma desconhecida aparece como veio). */
export function situacaoEmail(s: string | null | undefined): { rotulo: string; tom: Tom } {
  if (s === 'enviado' || s === 'falhou') return SITUACOES_EMAIL[s]
  return { rotulo: s ? s.charAt(0).toUpperCase() + s.slice(1) : '—', tom: 'neutro' }
}

/** O rótulo que veio da API; sem ele, o da tabela; sem os dois, o próprio tipo. */
export function rotuloTipoEmail(item: { tipo: string; tipo_rotulo?: string | null }): string {
  return item.tipo_rotulo?.trim() || TIPOS_EMAIL.find((t) => t.valor === item.tipo)?.rotulo || item.tipo
}

/** Os filtros como estão na tela (período por preset; datas só em "Escolher as datas"). */
export interface FiltrosEmailsTela {
  periodo: PeriodoEmails
  de: string
  ate: string
  situacao: SituacaoEmailEnviado | ''
  tipo: TipoEmailEnviado | ''
  busca: string
}

export const FILTROS_EMAILS_PADRAO: FiltrosEmailsTela = { periodo: '30', de: '', ate: '', situacao: '', tipo: '', busca: '' }

/** "Ver só as falhas": as falhas dos últimos 7 dias, sem os outros filtros (as mesmas que o aviso conta). */
export function filtrosSoFalhas(): FiltrosEmailsTela {
  return { ...FILTROS_EMAILS_PADRAO, periodo: '7', situacao: 'falhou' }
}

export function ehSoFalhas(f: FiltrosEmailsTela): boolean {
  return f.periodo === '7' && f.situacao === 'falhou' && !f.tipo && !f.busca.trim()
}

/** Algum filtro além do padrão (para o vazio dizer "com esses filtros" e mostrar "Limpar filtros"). */
export function temFiltroEmails(f: FiltrosEmailsTela): boolean {
  return f.periodo !== '30' || !!f.situacao || !!f.tipo || !!f.busca.trim()
}

/** A data mais antiga que ainda está guardada (hoje − 89: 90 dias contando hoje). */
export function primeiroDiaGuardado(hoje: string = hojeIso()): string {
  return somarDias(hoje, -(DIAS_GUARDADOS - 1))
}

/** Erro das datas escolhidas à mão (ou null): as duas datas, a inicial antes da final e dentro dos 90 dias. */
export function erroPeriodoEmails(f: Pick<FiltrosEmailsTela, 'periodo' | 'de' | 'ate'>, hoje: string = hojeIso()): string | null {
  if (f.periodo !== 'personalizado') return null
  const e = erroPeriodoEscolhido(f.de, f.ate)
  if (e) return e
  if (f.ate > hoje) return 'A data final não pode ser depois de hoje.'
  if (f.de < primeiroDiaGuardado(hoje)) return 'Guardamos só os últimos 90 dias. Escolha uma data inicial mais recente.'
  return null
}

/** Os filtros para GET /auditoria/emails (sem os vazios; o período sempre com as duas datas). */
export function filtrosEmailsParaApi(f: FiltrosEmailsTela, pagina = 1, hoje: string = hojeIso()): FiltrosEmailsEnviados {
  let de: string
  let ate: string
  if (f.periodo === 'personalizado' && dataIsoValida(f.de) && dataIsoValida(f.ate)) {
    de = f.de
    ate = f.ate
  } else {
    const dias = f.periodo === 'personalizado' ? 30 : Number(f.periodo)
    de = somarDias(hoje, -(dias - 1))
    ate = hoje
  }
  const q: FiltrosEmailsEnviados = { de, ate, pagina }
  if (f.situacao) q.situacao = f.situacao
  if (f.tipo) q.tipo = f.tipo
  const busca = f.busca.trim()
  if (busca) q.busca = busca
  return q
}

/** "1 e-mail falhou nos últimos 7 dias." / "3 e-mails falharam nos últimos 7 dias." */
export function textoFalhas(n: number): string {
  return n === 1 ? '1 e-mail falhou nos últimos 7 dias.' : `${formatarNumero(n)} e-mails falharam nos últimos 7 dias.`
}

/** "1 e-mail" / "1.234 e-mails". */
export function textoTotalEmails(n: number): string {
  return n === 1 ? '1 e-mail' : `${formatarNumero(n)} e-mails`
}
