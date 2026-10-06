import type { Component } from 'vue'
import {
  AtSign,
  CalendarDays,
  CircleDot,
  CodeXml,
  FileText,
  Gauge,
  Hash,
  ListChecks,
  MessageSquareText,
  Phone,
  SeparatorHorizontal,
  SlidersHorizontal,
  Smile,
  Star,
  ToggleLeft,
  Type,
} from 'lucide-vue-next'
import type { Final, Pergunta, TipoPergunta } from '@/api/tipos'

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
    tipo: 'conteudo',
    rotulo: 'Conteúdo',
    descricao: 'Texto formatado, imagens, avisos e links, sem resposta.',
    icone: FileText,
    padrao: () => ({ titulo: '', obrigatoria: false, html: '', modo: 'visual' }),
  },
  {
    tipo: 'quebra_pagina',
    rotulo: 'Quebra de página',
    descricao: 'Divide a pesquisa em páginas (vale no modo "páginas").',
    icone: SeparatorHorizontal,
    padrao: () => ({ titulo: '', obrigatoria: false }),
  },
]

export const INFO_TIPO = Object.fromEntries(TIPOS_PERGUNTA.map((t) => [t.tipo, t])) as Record<TipoPergunta, InfoTipo>

// ── Menu "Adicionar" (§5.3): grupos, busca e descrição de uma linha ──────────

export type GrupoAdicionar = 'Notas' | 'Escolhas' | 'Texto' | 'Data' | 'Conteúdo' | 'Estrutura'

export interface OpcaoAdicionar {
  chave: string
  grupo: GrupoAdicionar
  rotulo: string
  descricao: string
  icone: Component
  tipo: TipoPergunta
  /** Palavras a mais para a busca. */
  busca: string
  /** O item novo (sem o id). */
  criar: () => Omit<Pergunta, 'id'>
}

const base = (tipo: TipoPergunta, extra: Partial<Pergunta> = {}): Omit<Pergunta, 'id'> => ({ tipo, ...INFO_TIPO[tipo].padrao(), ...extra })

export const OPCOES_ADICIONAR: OpcaoAdicionar[] = [
  { chave: 'nps', grupo: 'Notas', rotulo: 'NPS', descricao: 'Nota de 0 a 10: quanto recomendaria você.', icone: Gauge, tipo: 'nps', busca: 'nota recomendacao lealdade 0 10', criar: () => base('nps') },
  { chave: 'csat', grupo: 'Notas', rotulo: 'CSAT', descricao: 'Carinhas de 1 a 5: satisfação com um atendimento.', icone: Smile, tipo: 'csat', busca: 'satisfacao carinhas rostos 1 5', criar: () => base('csat') },
  { chave: 'estrelas', grupo: 'Notas', rotulo: 'Estrelas', descricao: 'Nota rápida de 1 a 5 estrelas.', icone: Star, tipo: 'estrelas', busca: 'avaliacao 5 estrelas', criar: () => base('estrelas') },
  { chave: 'escala', grupo: 'Notas', rotulo: 'Escala', descricao: 'Nota numa faixa que você escolhe (ex.: 1 a 7).', icone: SlidersHorizontal, tipo: 'escala', busca: 'numerica faixa esforco ces likert', criar: () => base('escala') },
  { chave: 'escolha_unica', grupo: 'Escolhas', rotulo: 'Única', descricao: 'A pessoa marca uma opção da lista.', icone: CircleDot, tipo: 'escolha_unica', busca: 'escolha opcao radio lista suspensa', criar: () => base('escolha_unica') },
  { chave: 'escolha_multipla', grupo: 'Escolhas', rotulo: 'Múltipla', descricao: 'A pessoa pode marcar várias opções.', icone: ListChecks, tipo: 'escolha_multipla', busca: 'escolha varias opcoes checkbox caixas', criar: () => base('escolha_multipla') },
  { chave: 'sim_nao', grupo: 'Escolhas', rotulo: 'Sim ou não', descricao: 'Uma pergunta direta, com duas respostas.', icone: ToggleLeft, tipo: 'sim_nao', busca: 'sim nao booleano', criar: () => base('sim_nao') },
  { chave: 'texto', grupo: 'Texto', rotulo: 'Resposta curta', descricao: 'Uma linha de texto livre.', icone: Type, tipo: 'texto_curto', busca: 'texto curto nome linha', criar: () => base('texto_curto') },
  { chave: 'comentario', grupo: 'Texto', rotulo: 'Comentário', descricao: 'Um espaço livre para escrever o que quiser.', icone: MessageSquareText, tipo: 'comentario', busca: 'texto longo opiniao paragrafo', criar: () => base('comentario') },
  { chave: 'email', grupo: 'Texto', rotulo: 'E-mail', descricao: 'Liga a resposta ao contato com esse e-mail.', icone: AtSign, tipo: 'texto_curto', busca: 'email correio contato', criar: () => base('texto_curto', { titulo: 'Qual é o seu e-mail?', formato: 'email' }) },
  { chave: 'telefone', grupo: 'Texto', rotulo: 'Telefone', descricao: 'Um número de telefone ou WhatsApp.', icone: Phone, tipo: 'texto_curto', busca: 'telefone celular whatsapp', criar: () => base('texto_curto', { titulo: 'Qual é o seu telefone?', formato: 'telefone' }) },
  { chave: 'numero', grupo: 'Texto', rotulo: 'Número', descricao: 'Só números (aceita vírgula).', icone: Hash, tipo: 'texto_curto', busca: 'numero valor quantidade', criar: () => base('texto_curto', { titulo: 'Quantas vezes você comprou com a gente este mês?', formato: 'numero' }) },
  { chave: 'data', grupo: 'Data', rotulo: 'Data', descricao: 'Um dia do calendário.', icone: CalendarDays, tipo: 'data', busca: 'dia calendario quando', criar: () => base('data') },
  { chave: 'conteudo', grupo: 'Conteúdo', rotulo: 'Texto e imagem', descricao: 'Avisos, instruções e imagens, com formatação.', icone: FileText, tipo: 'conteudo', busca: 'conteudo bloco aviso termos imagem texto formatado', criar: () => base('conteudo') },
  { chave: 'html', grupo: 'Conteúdo', rotulo: 'HTML', descricao: 'Escreva o HTML (sem scripts nem estilos).', icone: CodeXml, tipo: 'conteudo', busca: 'html codigo tabela', criar: () => base('conteudo', { modo: 'html' }) },
  { chave: 'quebra', grupo: 'Estrutura', rotulo: 'Quebra de página', descricao: 'Divide a pesquisa em páginas (modo "páginas").', icone: SeparatorHorizontal, tipo: 'quebra_pagina', busca: 'pagina divisao separador', criar: () => base('quebra_pagina') },
]

export const GRUPOS_ADICIONAR: GrupoAdicionar[] = ['Notas', 'Escolhas', 'Texto', 'Data', 'Conteúdo', 'Estrutura']

const semAcento = (s: string) => s.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase()

/** Opções do menu que combinam com a busca (rótulo, descrição, grupo e palavras a mais). */
export function filtrarOpcoes(busca: string): OpcaoAdicionar[] {
  const termos = semAcento(busca).trim().split(/\s+/).filter(Boolean)
  if (!termos.length) return OPCOES_ADICIONAR
  return OPCOES_ADICIONAR.filter((o) => {
    const texto = semAcento(`${o.rotulo} ${o.descricao} ${o.grupo} ${o.busca}`)
    return termos.every((t) => texto.includes(t))
  })
}

// ── Ids (p_, r_ e f_ + 6, como a API) ───────────────────────────────────────

const ALFABETO = 'abcdefghijklmnopqrstuvwxyz0123456789'

function seis(): string {
  let s = ''
  for (let i = 0; i < 6; i++) s += ALFABETO[Math.floor(Math.random() * ALFABETO.length)]
  return s
}

/** `prefixo` + 6 caracteres [a-z0-9], sem repetir os usados. */
export function novoId(prefixo: 'p_' | 'r_' | 'f_', usados: Iterable<string>): string {
  const ja = new Set(usados)
  for (;;) {
    const id = prefixo + seis()
    if (!ja.has(id)) return id
  }
}

/** Id curto e estável, único no formulário (etapa 5l: `p_` + 6). */
export function novoIdPergunta(existentes: { id: string }[]): string {
  return novoId('p_', existentes.map((p) => p.id))
}

/** Os ids de regra já usados no formulário (únicos no formulário todo). */
export function idsDeRegras(itens: readonly Pergunta[]): string[] {
  return itens.flatMap((p) => (p.logica?.pular ?? []).map((r) => r.id))
}

export function criarPergunta(tipo: TipoPergunta, existentes: { id: string }[]): Pergunta {
  return { id: novoIdPergunta(existentes), tipo, ...INFO_TIPO[tipo].padrao() }
}

export function criarDaOpcao(opcao: OpcaoAdicionar, existentes: { id: string }[]): Pergunta {
  return { ...opcao.criar(), id: novoIdPergunta(existentes) } as Pergunta
}

/**
 * Cópia com id novo. A lógica de mostrar continua com as mesmas fontes; as regras de pular vêm vazias (evita saltos
 * duplicados).
 */
export function duplicarPergunta(p: Pergunta, existentes: { id: string }[]): Pergunta {
  const copia = JSON.parse(JSON.stringify(p)) as Pergunta
  const titulo = p.titulo ? `${p.titulo} (cópia)` : p.titulo
  const mostrar = copia.logica?.mostrar_se
  delete copia.logica
  const nova: Pergunta = { ...copia, id: novoIdPergunta(existentes), titulo }
  if (mostrar) nova.logica = { mostrar_se: mostrar }
  return nova
}

/** Final novo (o nome e o título já preenchidos para a pessoa ajustar). */
export function criarFinal(existentes: readonly Final[], extra: Partial<Final> = {}): Final {
  return {
    id: novoId('f_', existentes.map((f) => f.id)),
    nome: `Final ${existentes.length + 1}`,
    titulo: 'Obrigado!',
    html: '',
    botao: null,
    mostrar_se: null,
    ...extra,
  }
}

/** Move um item de `de` para `para` (índices), devolvendo uma nova lista. */
export function mover<T>(lista: T[], de: number, para: number): T[] {
  if (de === para || de < 0 || de >= lista.length) return lista
  const nova = [...lista]
  const [item] = nova.splice(de, 1)
  nova.splice(Math.max(0, Math.min(para, nova.length)), 0, item!)
  return nova
}
