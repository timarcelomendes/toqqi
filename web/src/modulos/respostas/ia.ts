// Análise da IA de cada resposta (etapa 4b): rótulos e cores do sentimento, o que dizer em cada situação da
// análise e quando mostrar os filtros que dependem dela.
import type { AnaliseIa, FiltroSentimento, Sentimento, SentimentoGeral, SituacaoIa } from '@/api/tipos'
import type { Tom } from '@/utils/rotulos'

/**
 * Sentimento geral do comentário, com a mesma cor em todas as telas: positivo verde, neutro cinza, misto âmbar e
 * negativo vermelho (`tom` nos selos, `barra` nos gráficos). A cor acompanha a palavra escrita (nunca fala sozinha).
 */
export const SENTIMENTOS: Record<SentimentoGeral, { rotulo: string; tom: Tom; barra: string }> = {
  positivo: { rotulo: 'Positivo', tom: 'sucesso', barra: 'bg-grafico-promotor' },
  neutro: { rotulo: 'Neutro', tom: 'neutro', barra: 'bg-grafico-cinza' },
  misto: { rotulo: 'Misto', tom: 'atencao', barra: 'bg-grafico-neutro' },
  negativo: { rotulo: 'Negativo', tom: 'erro', barra: 'bg-grafico-detrator' },
}

/** Sentimento sobre um tema (na caixa "Análise da IA"). */
export const SENTIMENTOS_TEMA: Record<Sentimento, { rotulo: string; tom: Tom }> = {
  positivo: { rotulo: 'elogio', tom: 'sucesso' },
  neutro: { rotulo: 'neutro', tom: 'neutro' },
  negativo: { rotulo: 'reclamação', tom: 'erro' },
}

export const OPCOES_SENTIMENTO: { valor: FiltroSentimento; rotulo: string }[] = [
  { valor: 'negativo', rotulo: 'Negativo' },
  { valor: 'misto', rotulo: 'Misto' },
  { valor: 'neutro', rotulo: 'Neutro' },
  { valor: 'positivo', rotulo: 'Positivo' },
  { valor: 'sem_analise', rotulo: 'Ainda sem análise da IA' },
]

export function ehSentimento(v: unknown): v is SentimentoGeral {
  return typeof v === 'string' && Object.hasOwn(SENTIMENTOS, v)
}

export function ehFiltroSentimento(v: unknown): v is FiltroSentimento {
  return v === 'sem_analise' || ehSentimento(v)
}

export function rotuloSentimento(v: string | null | undefined): string {
  return ehSentimento(v) ? SENTIMENTOS[v].rotulo : v || '—'
}

/** O que a caixa "Análise da IA" diz em cada situação que não é "analisada". */
export const SITUACOES_IA: Record<Exclude<SituacaoIa, 'analisada'>, { titulo: string; texto: string; tom: Tom }> = {
  pendente: {
    titulo: 'Aguardando análise',
    texto: 'O comentário está na fila da IA. Em alguns minutos o resumo e os temas aparecem aqui.',
    tom: 'info',
  },
  falhou: {
    titulo: 'Não foi possível analisar',
    texto: 'A IA não conseguiu analisar este comentário depois de 3 tentativas. Os temas continuam pelas palavras-chave.',
    tom: 'atencao',
  },
  limite: {
    titulo: 'Limite do mês atingido',
    texto: 'A conta chegou ao limite de análises deste mês. Os temas continuam pelas palavras-chave até o mês virar.',
    tom: 'atencao',
  },
}

/** A resposta tem análise pronta (resumo, sentimento e temas). */
export function analisada(ia: AnaliseIa | null | undefined): ia is AnaliseIa & { situacao: 'analisada' } {
  return ia?.situacao === 'analisada'
}

/**
 * Os filtros "Sentimento" e "Só reclamações" só aparecem com a IA ativa na conta, quando a lista já tem respostas
 * analisadas ou quando já vieram ligados no endereço (para a pessoa conseguir desligar).
 */
export function mostrarFiltrosIa(opcoes: { iaAtiva?: boolean | null; temAnalise?: boolean; filtroLigado?: boolean }): boolean {
  return !!opcoes.iaAtiva || !!opcoes.temAnalise || !!opcoes.filtroLigado
}
