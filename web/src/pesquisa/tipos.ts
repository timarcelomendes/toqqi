// Tipos da pesquisa (formulário, perguntas, tema), compartilhados pela página pública,
// pela pré-visualização do editor e pelo cliente da API. Sem dependências: a página
// pública precisa continuar leve.

export type TipoPergunta =
  | 'nps'
  | 'csat'
  | 'estrelas'
  | 'escala'
  | 'texto_curto'
  | 'comentario'
  | 'escolha_unica'
  | 'escolha_multipla'
  | 'sim_nao'
  | 'data'
  | 'quebra_pagina'

export type FormatoTexto = 'texto' | 'email' | 'telefone' | 'numero'

export type GrupoNota = 'detrator' | 'neutro' | 'promotor' | 'insatisfeito' | 'satisfeito'

export type CondicaoPergunta =
  | { tipo: 'grupo'; grupos: GrupoNota[] }
  | { tipo: 'nota'; operador: '<=' | '>='; valor: number }

export interface Pergunta {
  id: string
  tipo: TipoPergunta
  titulo: string
  descricao?: string | null
  obrigatoria: boolean
  opcoes?: string[]
  min?: number
  max?: number
  rotulo_min?: string | null
  rotulo_max?: string | null
  formato?: FormatoTexto
  condicao?: CondicaoPergunta | null
}

export type ModoTema = 'uma_por_vez' | 'paginas'

export interface Tema {
  cor: string
  logo_url?: string | null
  modo: ModoTema
  titulo_abertura?: string | null
  texto_abertura?: string | null
  texto_botao: string
  titulo_final: string
  texto_final: string
}

export interface Variaveis {
  empresa: string
  nome: string
  assunto: string
  referencia: string
}

/** O que a página pública recebe para desenhar a pesquisa. */
export interface FormularioPublico {
  nome: string
  perguntas: Pergunta[]
  tema: Tema
  /** Etapa 5i: "Pesquisa feita com Toqqi" (null quando a conta tirou, onde o plano permite; ausente na prévia). */
  mencao_toqqi?: { texto: string; url: string } | null
}

/** Valor de uma resposta: número (notas), texto, lista (múltipla escolha) ou sim/não. */
export type ValorResposta = number | string | string[] | boolean

export type Respostas = Record<string, ValorResposta>

export interface TelaFinal {
  titulo_final: string
  texto_final: string
  /**
   * Etapa 5c: convite para indicar outra empresa. Só no convite individual, com indicações ligadas na conta e nota
   * principal de promotor (NPS 9–10) ou CSAT 5. Textos já com as variáveis trocadas.
   */
  indicacao?: ConviteIndicacao | null
  /** Melhoria 5: o pedido de depoimento e o link para avaliar a empresa (só para nota alta, no convite individual). */
  depoimento?: TelaFinalDepoimento | null
}

export interface TelaFinalDepoimento {
  pedir: boolean
  avaliar_url: string | null
  avaliar_rotulo: string
}

/** Etapa 5c: o cartão de indicação da tela final (texto puro). */
export interface ConviteIndicacao {
  titulo: string
  texto: string
  recompensa: string | null
}

/** Corpo de POST /publico/convites/{token}/indicacoes. Opcionais vazios vão como null; telefone só com dígitos. */
export interface DadosIndicacao {
  nome: string
  empresa: string | null
  telefone: string | null
  email: string | null
  observacao: string | null
  pode_identificar: boolean
  confirmo: boolean
}

export const CAMPOS_CONTEXTO = ['pedido', 'nota_fiscal', 'rota', 'motorista', 'filial', 'transportadora'] as const
export type CampoContexto = (typeof CAMPOS_CONTEXTO)[number]
export type Contexto = Partial<Record<CampoContexto, string>>

export const ROTULOS_CONTEXTO: Record<CampoContexto, string> = {
  pedido: 'Pedido',
  nota_fiscal: 'Nota fiscal',
  rota: 'Rota',
  motorista: 'Motorista',
  filial: 'Filial',
  transportadora: 'Transportadora',
}

export const TEMA_PADRAO: Tema = {
  cor: '#ff5a36',
  logo_url: null,
  modo: 'uma_por_vez',
  titulo_abertura: null,
  texto_abertura: null,
  texto_botao: 'Enviar',
  titulo_final: 'Obrigado!',
  texto_final: 'Sua opinião ajuda muito a gente a melhorar.',
}
