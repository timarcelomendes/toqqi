// Atalhos da nota principal (docs/api-etapa-5l.md §5.3): "Criar acompanhamento por segmento" e "Criar finais por
// segmento", nos textos do modelo `nps_segmentos` (ou no equivalente de CSAT).
import type { Final, Pergunta } from '@/api/tipos'
import { criarFinal, novoIdPergunta } from '../tiposPergunta'

const grupo = (fonte: string, ...grupos: string[]) => ({ juncao: 'todas' as const, condicoes: [{ fonte, op: 'grupo_e' as const, valor: grupos }] })

/** As perguntas de acompanhamento, logo depois da nota principal: uma para quem não gostou, outra para quem gostou. */
export function perguntasPorSegmento(principal: Pergunta, existentes: { id: string }[]): Pergunta[] {
  const nps = principal.tipo === 'nps'
  const ids = [...existentes]
  const nova = (titulo: string, grupos: string[]): Pergunta => {
    const p: Pergunta = { id: novoIdPergunta(ids), tipo: 'comentario', titulo, obrigatoria: false, logica: { mostrar_se: grupo(principal.id, ...grupos) } }
    ids.push(p)
    return p
  }
  return nps
    ? [nova('O que podemos melhorar?', ['detrator', 'neutro']), nova('O que você mais valoriza na {empresa}?', ['promotor'])]
    : [nova('O que podemos melhorar?', ['insatisfeito', 'neutro']), nova('O que você mais gostou?', ['satisfeito'])]
}

/** Os finais por segmento: Promotores e Detratores (ou Satisfeitos e Insatisfeitos). */
export function finaisPorSegmento(principal: Pergunta, existentes: Final[]): Final[] {
  const nps = principal.tipo === 'nps'
  const lista = [...existentes]
  const novo = (f: Partial<Final>) => {
    const final = criarFinal(lista, f)
    lista.push(final)
    return final
  }
  return nps
    ? [
        novo({
          nome: 'Promotores',
          titulo: 'Obrigado por recomendar a {empresa}!',
          html: '<p>Que bom saber que você recomenda a gente. A sua opinião ajuda a {empresa} a continuar acertando.</p>',
          mostrar_se: grupo(principal.id, 'promotor'),
        }),
        novo({ nome: 'Detratores', titulo: 'Obrigado pela sinceridade', html: '<p>Vamos usar o que você contou para melhorar.</p>', mostrar_se: grupo(principal.id, 'detrator') }),
      ]
    : [
        novo({ nome: 'Satisfeitos', titulo: 'Que bom que gostou!', html: '<p>Obrigado por avaliar a {empresa}. A sua opinião ajuda a gente a continuar acertando.</p>', mostrar_se: grupo(principal.id, 'satisfeito') }),
        novo({ nome: 'Insatisfeitos', titulo: 'Obrigado pela sinceridade', html: '<p>Vamos usar o que você contou para melhorar.</p>', mostrar_se: grupo(principal.id, 'insatisfeito') }),
      ]
}

/** Onde os finais novos entram: antes do 1º final sem condição (que pega o resto), senão no fim. */
export function posicaoParaFinalComCondicao(finais: readonly Final[]): number {
  const i = finais.findIndex((f) => !f.mostrar_se?.condicoes?.length)
  return i >= 0 ? i : finais.length
}
