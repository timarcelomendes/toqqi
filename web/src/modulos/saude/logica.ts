// Etapa 5i: rótulos, tons e ícones da saúde da conta (o texto e o ícone sempre junto da cor).
import type { FaixaSaude } from '@/api'

export const FAIXAS_SAUDE: { valor: FaixaSaude; rotulo: string; tom: 'sucesso' | 'atencao' | 'erro' | 'neutro' }[] = [
  { valor: 'risco', rotulo: 'Risco', tom: 'erro' },
  { valor: 'atencao', rotulo: 'Atenção', tom: 'atencao' },
  { valor: 'saudavel', rotulo: 'Saudável', tom: 'sucesso' },
  { valor: 'sem_dados', rotulo: 'Sem dados', tom: 'neutro' },
]

export const infoFaixa = (f: FaixaSaude) => FAIXAS_SAUDE.find((x) => x.valor === f)!

/** "Renova em 12 dias" / "Renova hoje" / "Renova amanhã". */
export function textoRenova(dias: number): string {
  if (dias === 0) return 'Renova hoje'
  if (dias === 1) return 'Renova amanhã'
  return `Renova em ${dias} dias`
}
