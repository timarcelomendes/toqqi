// Regras puras do topo de Planos de ação (docs/api-acoes-panorama.md): a frase dos prazos, a barra das abertas por
// prazo, a carga por responsável e as concluídas nos últimos 30 dias. Sem Vue, para testar.
import type { ConcluidasAcoes, Id, PanoramaAcoes } from '@/api/tipos'
import { formatarNumero, plural } from '@/utils/formatos'

export interface Manchete {
  titulo: string
  texto: string | null
  tom: 'erro' | 'atencao' | 'sucesso' | 'neutro'
}

/** Como estão os prazos, em uma frase. */
export function manchete(p: PanoramaAcoes['prazos']): Manchete {
  if (!p.abertas) return { titulo: 'Nenhuma ação aberta', texto: 'Quando um cliente der nota baixa, a ação aparece aqui, com responsável e prazo.', tom: 'neutro' }
  if (p.vencidas)
    return {
      titulo: `${formatarNumero(p.vencidas)} de ${plural(p.abertas, 'ação aberta', 'ações abertas')} ${p.vencidas === 1 ? 'está vencida' : 'estão vencidas'}`,
      texto: p.hoje ? `E ${plural(p.hoje, 'vence', 'vencem')} hoje.` : null,
      tom: 'erro',
    }
  if (p.hoje)
    return { titulo: `Nenhuma vencida, mas ${plural(p.hoje, 'vence', 'vencem')} hoje`, texto: `${plural(p.abertas, 'ação aberta', 'ações abertas')} ao todo.`, tom: 'atencao' }
  return {
    titulo: p.abertas === 1 ? 'A ação aberta está em dia' : `As ${formatarNumero(p.abertas)} ações abertas estão em dia`,
    texto: p.sem_prazo ? `${plural(p.sem_prazo, 'está', 'estão')} sem prazo.` : null,
    tom: 'sucesso',
  }
}

export interface SegmentoPrazo {
  chave: 'vencidas' | 'hoje' | 'em_dia' | 'sem_prazo'
  valor: number
  rotulo: string
  /** Largura na barra, em % das abertas (com valor, nunca menos de 3%). */
  largura: number
  /** Classe da cor da barra (as de situação: vencida em vermelho, hoje em âmbar). */
  cor: string
}

const CORES: Record<SegmentoPrazo['chave'], string> = {
  vencidas: 'bg-grafico-detrator',
  hoje: 'bg-grafico-neutro',
  em_dia: 'bg-grafico-cinza',
  sem_prazo: 'bg-borda-forte',
}

/** As abertas por prazo, só as partes com valor: vencidas, vencem hoje, em dia e sem prazo. */
export function segmentosPrazo(p: PanoramaAcoes['prazos']): SegmentoPrazo[] {
  const emDia = p.proximos_7_dias + p.depois
  const partes: [SegmentoPrazo['chave'], number, string][] = [
    ['vencidas', p.vencidas, p.vencidas === 1 ? 'vencida' : 'vencidas'],
    ['hoje', p.hoje, p.hoje === 1 ? 'vence hoje' : 'vencem hoje'],
    ['em_dia', emDia, 'em dia'],
    ['sem_prazo', p.sem_prazo, 'sem prazo'],
  ]
  return partes
    .filter(([, v]) => v > 0)
    .map(([chave, valor, rotulo]) => ({ chave, valor, rotulo, largura: p.abertas ? Math.max(3, Math.round((valor / p.abertas) * 100)) : 0, cor: CORES[chave] }))
}

export interface Pessoa {
  /** Valor do filtro "Responsável": o id, ou "0" para sem responsável. */
  filtro: Id
  nome: string
  abertas: number
  vencidas: number
  /** "3 abertas, 2 vencidas"; "1 aberta". */
  detalhe: string
  /** Largura da barra em % de quem tem mais abertas; parte vencida em % da própria barra. */
  largura: number
  parteVencida: number
}

export function carga(p: PanoramaAcoes): Pessoa[] {
  const maior = Math.max(0, ...p.responsaveis.map((r) => r.abertas))
  return p.responsaveis.map((r) => ({
    filtro: r.responsavel ? r.responsavel.id : '0',
    nome: r.responsavel?.nome ?? 'Sem responsável',
    abertas: r.abertas,
    vencidas: r.vencidas,
    detalhe: `${plural(r.abertas, 'aberta', 'abertas')}${r.vencidas ? `, ${plural(r.vencidas, 'vencida', 'vencidas')}` : ''}`,
    largura: maior > 0 ? Math.max(6, Math.round((r.abertas / maior) * 100)) : 0,
    parteVencida: r.abertas ? Math.min(100, Math.round((r.vencidas / r.abertas) * 100)) : 0,
  }))
}

/** "Metade em até 4 dias", "Metade no mesmo dia"; null sem concluídas. */
export function tempoConclusao(c: ConcluidasAcoes): string | null {
  if (c.mediana_dias === null) return null
  if (c.mediana_dias < 1) return 'Metade concluída no mesmo dia'
  return `Metade concluída em até ${plural(Math.round(c.mediana_dias), 'dia', 'dias')}`
}

/** "2 com retorno ao cliente" (o e-mail "Avisar o cliente"); "Nenhuma com retorno ao cliente". */
export function retorno(c: ConcluidasAcoes): string | null {
  if (!c.total) return null
  return c.com_retorno ? `${formatarNumero(c.com_retorno)} de ${formatarNumero(c.total)} com retorno ao cliente` : 'Nenhuma com retorno ao cliente ainda'
}

export interface Comparacao {
  texto: string
  sentido: 'subiu' | 'caiu' | 'igual'
}

/** As concluídas contra as dos 30 dias anteriores; null quando as duas são zero. */
export function comparacaoConcluidas(c: PanoramaAcoes['concluidas']): Comparacao | null {
  const antes = c.anterior.total
  if (!c.total && !antes) return null
  const d = c.total - antes
  if (!d) return { texto: 'O mesmo que nos 30 dias anteriores', sentido: 'igual' }
  return d > 0 ? { texto: `${formatarNumero(d)} a mais que nos 30 dias anteriores`, sentido: 'subiu' } : { texto: `${formatarNumero(-d)} a menos que nos 30 dias anteriores`, sentido: 'caiu' }
}
