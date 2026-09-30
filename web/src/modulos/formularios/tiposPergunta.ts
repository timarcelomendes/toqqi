import type { Component } from 'vue'
import {
  CalendarDays,
  CircleDot,
  Gauge,
  ListChecks,
  MessageSquareText,
  SeparatorHorizontal,
  SlidersHorizontal,
  Smile,
  Star,
  ToggleLeft,
  Type,
} from 'lucide-vue-next'
import type { Pergunta, TipoPergunta } from '@/api/tipos'

export interface InfoTipo {
  tipo: TipoPergunta
  rotulo: string
  descricao: string
  icone: Component
  padrao: () => Omit<Pergunta, 'id' | 'tipo'>
}

export const TIPOS_PERGUNTA: InfoTipo[] = [
  {
    tipo: 'nps',
    rotulo: 'Nota de 0 a 10 (NPS)',
    descricao: 'Quanto a pessoa recomendaria você. É a nota mais usada para medir lealdade.',
    icone: Gauge,
    padrao: () => ({ titulo: 'De 0 a 10, quanto você recomendaria a {empresa} para um amigo ou colega?', obrigatoria: true, rotulo_min: 'Nada provável', rotulo_max: 'Muito provável' }),
  },
  {
    tipo: 'csat',
    rotulo: 'Carinhas de 1 a 5 (CSAT)',
    descricao: 'Satisfação com um atendimento ou entrega, de muito insatisfeito a muito satisfeito.',
    icone: Smile,
    padrao: () => ({ titulo: 'Como você avalia {assunto}?', obrigatoria: true }),
  },
  {
    tipo: 'estrelas',
    rotulo: 'Estrelas de 1 a 5',
    descricao: 'Uma nota rápida em estrelas, como nos aplicativos.',
    icone: Star,
    padrao: () => ({ titulo: 'Que nota você dá para {assunto}?', obrigatoria: true }),
  },
  {
    tipo: 'escala',
    rotulo: 'Escala numérica',
    descricao: 'Uma nota numa faixa que você escolhe, por exemplo de 1 a 7.',
    icone: SlidersHorizontal,
    padrao: () => ({ titulo: 'Foi fácil resolver o que você precisava?', obrigatoria: false, min: 1, max: 5, rotulo_min: 'Muito difícil', rotulo_max: 'Muito fácil' }),
  },
  {
    tipo: 'comentario',
    rotulo: 'Comentário',
    descricao: 'Um espaço livre para a pessoa escrever o que quiser.',
    icone: MessageSquareText,
    padrao: () => ({ titulo: 'Quer contar mais alguma coisa?', obrigatoria: false }),
  },
  {
    tipo: 'texto_curto',
    rotulo: 'Resposta curta',
    descricao: 'Uma linha de texto: nome, e-mail, telefone ou número.',
    icone: Type,
    padrao: () => ({ titulo: 'Qual é o seu nome?', obrigatoria: false, formato: 'texto' }),
  },
  {
    tipo: 'escolha_unica',
    rotulo: 'Escolha uma opção',
    descricao: 'A pessoa marca só uma resposta de uma lista.',
    icone: CircleDot,
    padrao: () => ({ titulo: 'Qual foi o principal motivo da sua nota?', obrigatoria: false, opcoes: ['Atendimento', 'Prazo de entrega', 'Preço'] }),
  },
  {
    tipo: 'escolha_multipla',
    rotulo: 'Escolha várias opções',
    descricao: 'A pessoa pode marcar mais de uma resposta da lista.',
    icone: ListChecks,
    padrao: () => ({ titulo: 'O que podemos melhorar?', obrigatoria: false, opcoes: ['Atendimento', 'Prazo de entrega', 'Preço'] }),
  },
  {
    tipo: 'sim_nao',
    rotulo: 'Sim ou não',
    descricao: 'Uma pergunta direta, com duas respostas.',
    icone: ToggleLeft,
    padrao: () => ({ titulo: 'Seu problema foi resolvido?', obrigatoria: false }),
  },
  {
    tipo: 'data',
    rotulo: 'Data',
    descricao: 'Um dia do calendário, por exemplo a data da entrega.',
    icone: CalendarDays,
    padrao: () => ({ titulo: 'Em que dia foi a entrega?', obrigatoria: false }),
  },
  {
    tipo: 'quebra_pagina',
    rotulo: 'Quebra de página',
    descricao: 'Divide a pesquisa em páginas (vale no modo "páginas").',
    icone: SeparatorHorizontal,
    padrao: () => ({ titulo: 'Nova página', obrigatoria: false }),
  },
]

export const INFO_TIPO = Object.fromEntries(TIPOS_PERGUNTA.map((t) => [t.tipo, t])) as Record<TipoPergunta, InfoTipo>

/** Id curto e estável, único no formulário. */
export function novoIdPergunta(existentes: { id: string }[]): string {
  const usados = new Set(existentes.map((p) => p.id))
  for (;;) {
    const id = 'p' + Math.random().toString(36).slice(2, 8)
    if (!usados.has(id)) return id
  }
}

export function criarPergunta(tipo: TipoPergunta, existentes: { id: string }[]): Pergunta {
  return { id: novoIdPergunta(existentes), tipo, ...INFO_TIPO[tipo].padrao() }
}

export function duplicarPergunta(p: Pergunta, existentes: { id: string }[]): Pergunta {
  const copia = JSON.parse(JSON.stringify(p)) as Pergunta
  return { ...copia, id: novoIdPergunta(existentes), titulo: p.titulo ? `${p.titulo} (cópia)` : p.titulo }
}

/** Move um item de `de` para `para` (índices), devolvendo uma nova lista. */
export function mover<T>(lista: T[], de: number, para: number): T[] {
  if (de === para || de < 0 || de >= lista.length) return lista
  const nova = [...lista]
  const [item] = nova.splice(de, 1)
  nova.splice(Math.max(0, Math.min(para, nova.length)), 0, item!)
  return nova
}
