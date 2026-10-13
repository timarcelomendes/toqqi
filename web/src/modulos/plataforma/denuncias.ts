// Plataforma › Feedback › Denúncias (Plano Grátis, docs/api-plano-gratis.md), sem Vue: os rótulos da situação, do
// motivo e de por onde a pessoa abriu a pesquisa, e o endereço da conta denunciada em Plataforma › Contas.
import type { DenunciaPlataforma, SituacaoDenuncia } from '@/api/tipos'
import { MOTIVOS_DENUNCIA } from '@/api/publico'
import type { Tom } from '@/utils/rotulos'

export type FiltroDenuncias = 'abertas' | 'todas'

export const FILTROS_DENUNCIAS: { valor: FiltroDenuncias; rotulo: string }[] = [
  { valor: 'abertas', rotulo: 'Abertas' },
  { valor: 'todas', rotulo: 'Todas' },
]

export const SITUACOES_DENUNCIA: Record<SituacaoDenuncia, { rotulo: string; tom: Tom }> = {
  aberta: { rotulo: 'Aberta', tom: 'atencao' },
  procedente: { rotulo: 'Procedente', tom: 'erro' },
  descartada: { rotulo: 'Descartada', tom: 'neutro' },
}

export function infoSituacaoDenuncia(s: string): { rotulo: string; tom: Tom } {
  return SITUACOES_DENUNCIA[s as SituacaoDenuncia] ?? { rotulo: s, tom: 'neutro' }
}

/** O motivo como a pessoa escolheu ("Pede senha, cartão ou dados bancários"). */
export function rotuloMotivo(m: string): string {
  return MOTIVOS_DENUNCIA.find((x) => x.valor === m)?.rotulo ?? m
}

export function rotuloOrigem(o: string): string {
  return o === 'convite' ? 'Pelo convite' : o === 'link_publico' ? 'Pelo link público' : o
}

/** O que a equipe lê ao mudar a situação. */
export function mensagemSituacao(s: SituacaoDenuncia): string {
  if (s === 'procedente') return 'Denúncia marcada como procedente.'
  if (s === 'descartada') return 'Denúncia descartada: ela não pesa mais na nota de risco da conta.'
  return 'Denúncia reaberta.'
}

/** "1 denúncia aberta" / "3 denúncias abertas" / "Nenhuma denúncia aberta". */
export function textoAbertas(n: number): string {
  if (n <= 0) return 'Nenhuma denúncia aberta'
  return n === 1 ? '1 denúncia aberta' : `${n} denúncias abertas`
}

/** A conta denunciada em Plataforma › Contas (a busca pelo nome); null se a conta foi excluída. */
export function linkDaConta(d: Pick<DenunciaPlataforma, 'conta'>): string | null {
  return d.conta.nome ? `/plataforma/contas?busca=${encodeURIComponent(d.conta.nome)}` : null
}
