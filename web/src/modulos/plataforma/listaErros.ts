// Regras puras de Plataforma › Erros (etapa 5h, docs/api-etapa-5h.md §4): filtros, rótulos e textos da lista.
import type { ErroPlataforma, OrigemErro, SituacaoErros } from '@/api/tipos'
import { formatarNumero, plural } from '@/utils/formatos'
import type { Tom } from '@/utils/rotulos'

export interface FiltrosErrosTela {
  origem: OrigemErro | ''
  situacao: SituacaoErros
  dias: 7 | 30
}

export const FILTROS_ERROS_PADRAO: FiltrosErrosTela = { origem: '', situacao: 'abertos', dias: 7 }

export const ORIGENS_ERRO: { valor: OrigemErro; rotulo: string }[] = [
  { valor: 'api', rotulo: 'API' },
  { valor: 'site', rotulo: 'Site' },
  { valor: 'tarefa', rotulo: 'Tarefas' },
]

export const SITUACOES_ERRO: { valor: SituacaoErros; rotulo: string }[] = [
  { valor: 'abertos', rotulo: 'Abertos' },
  { valor: 'resolvidos', rotulo: 'Resolvidos' },
  { valor: 'todos', rotulo: 'Todos' },
]

export const PERIODOS_ERRO: { valor: 7 | 30; rotulo: string }[] = [
  { valor: 7, rotulo: 'Últimos 7 dias' },
  { valor: 30, rotulo: 'Últimos 30 dias' },
]

const ORIGENS: Record<string, { rotulo: string; tom: Tom }> = {
  api: { rotulo: 'API', tom: 'info' },
  site: { rotulo: 'Site', tom: 'marca' },
  tarefa: { rotulo: 'Tarefa', tom: 'neutro' },
}

export function rotuloOrigem(origem: string): { rotulo: string; tom: Tom } {
  return ORIGENS[origem] ?? { rotulo: origem, tom: 'neutro' }
}

/** "1 vez" / "1.250 vezes". */
export function textoOcorrencias(n: number): string {
  return n === 1 ? '1 vez' : `${formatarNumero(n)} vezes`
}

/** O aviso da lista vazia (o mesmo título com qualquer filtro). */
export function textoVazio(dias: number): string {
  return `Nenhum erro nos últimos ${dias} dias`
}

export function descricaoVazio(f: FiltrosErrosTela): string {
  const origem = f.origem ? ` (${rotuloOrigem(f.origem).rotulo})` : ''
  if (f.situacao === 'abertos') return `Nada aberto${origem}. Os erros da API, do site e das tarefas aparecem aqui assim que acontecem.`
  if (f.situacao === 'resolvidos') return `Nenhum erro resolvido${origem} nesse período.`
  return `Os erros da API, do site e das tarefas${origem} aparecem aqui assim que acontecem.`
}

/** "3 erros abertos" / "1 erro resolvido" / "12 erros". */
export function textoTotalErros(n: number, situacao: SituacaoErros): string {
  if (situacao === 'abertos') return plural(n, 'erro aberto', 'erros abertos')
  if (situacao === 'resolvidos') return plural(n, 'erro resolvido', 'erros resolvidos')
  return plural(n, 'erro', 'erros')
}

/** A conta do erro: o nome, "Conta 12 (excluída)" sem nome, ou null sem conta. */
export function textoConta(e: Pick<ErroPlataforma, 'conta_id' | 'conta_nome'>): string | null {
  if (e.conta_id === null || e.conta_id === undefined) return null
  return e.conta_nome ?? `Conta ${e.conta_id} (excluída)`
}

export function temFiltroErros(f: FiltrosErrosTela): boolean {
  return f.origem !== FILTROS_ERROS_PADRAO.origem || f.situacao !== FILTROS_ERROS_PADRAO.situacao || f.dias !== FILTROS_ERROS_PADRAO.dias
}
