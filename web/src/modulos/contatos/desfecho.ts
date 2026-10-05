// Etapa 5i: motivos da perda (as chaves e os rótulos da API, `empresas/desfecho.py`) e o selo da situação.
import type { Empresa, MotivoPerda, SituacaoEmpresa } from '@/api'
import { formatarData } from '@/utils/datas'

export const MOTIVOS_PERDA: { valor: MotivoPerda; rotulo: string }[] = [
  { valor: 'preco', rotulo: 'Preço' },
  { valor: 'concorrente', rotulo: 'Foi para um concorrente' },
  { valor: 'atendimento', rotulo: 'Atendimento ou qualidade' },
  { valor: 'produto', rotulo: 'O produto não atendeu' },
  { valor: 'encerrou', rotulo: 'Encerrou a atividade' },
  { valor: 'outro', rotulo: 'Outro' },
]

/** A situação (a API manda `situacao`; sem ela, como antes: ativa ou inativa). */
export function situacaoEmpresa(e: Pick<Empresa, 'ativa' | 'situacao' | 'perdida_em'>): SituacaoEmpresa {
  return e.situacao ?? (e.perdida_em ? 'perdida' : e.ativa ? 'ativa' : 'pausada')
}

export function seloSituacao(e: Pick<Empresa, 'ativa' | 'situacao' | 'perdida_em'>): { texto: string; tom: 'sucesso' | 'neutro' | 'erro' } {
  const s = situacaoEmpresa(e)
  if (s === 'perdida') return { texto: e.perdida_em ? `Perdida em ${formatarData(e.perdida_em)}` : 'Perdida', tom: 'erro' }
  return s === 'ativa' ? { texto: 'Ativa', tom: 'sucesso' } : { texto: 'Inativa', tom: 'neutro' }
}
