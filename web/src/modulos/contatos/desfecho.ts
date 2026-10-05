// Etapa 5i: motivos da perda (as chaves e os rótulos da API, `empresas/desfecho.py`) e o selo da situação.
import type { Empresa, MarcoEmpresa, MotivoPerda, SituacaoEmpresa } from '@/api'
import { formatarData } from '@/utils/datas'
import { formatarMoeda } from '@/utils/formatos'

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

/** Etapa 5i: o texto de um marco da linha do tempo da empresa. */
export function textoMarco(m: MarcoEmpresa): { titulo: string; detalhe: string; tom: 'sucesso' | 'neutro' | 'erro' | 'atencao' } {
  const quem = [m.usuario?.nome, m.origem_rotulo].filter(Boolean).join(', ')
  if (m.tipo === 'entrada') {
    const valor = m.valor_depois !== null ? ` com ${formatarMoeda(m.valor_depois)} por mês` : ''
    return { titulo: `Virou cliente${valor}`, detalhe: quem, tom: 'sucesso' }
  }
  if (m.tipo === 'valor') {
    const sobe = Number(m.valor_depois ?? 0) > Number(m.valor_antes ?? 0)
    return {
      titulo: `Valor mensal: ${formatarMoeda(m.valor_antes)} → ${formatarMoeda(m.valor_depois)}`,
      detalhe: quem,
      tom: sobe ? 'sucesso' : 'atencao',
    }
  }
  if (m.tipo === 'perdida') {
    const motivo = [m.motivo_rotulo, m.motivo_detalhe].filter(Boolean).join(': ')
    const contatos = m.contatos ? `${m.contatos} ${m.contatos === 1 ? 'contato desativado' : 'contatos desativados'}` : ''
    return { titulo: `Perdida${motivo ? ` (${motivo})` : ''}`, detalhe: [contatos, quem].filter(Boolean).join(' · '), tom: 'erro' }
  }
  return { titulo: 'Voltou a ser cliente', detalhe: quem, tom: 'sucesso' }
}
