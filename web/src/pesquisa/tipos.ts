// Tipos da pesquisa (formulário, perguntas, tema), compartilhados pela página pública,
// pela pré-visualização do editor e pelo cliente da API. Sem dependências: a página
// pública precisa continuar leve.

/**
 * Tipos de item do formulário. Perguntas (respondíveis) e, etapa 5l, os não respondíveis: `conteudo` (texto formatado,
 * imagens, avisos) e `quebra_pagina`. O nome `TipoPergunta` ficou por compatibilidade: a lista de `perguntas` do
 * formulário é a lista de itens.
 */
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
  | 'conteudo'

export type FormatoTexto = 'texto' | 'email' | 'telefone' | 'numero'

export type GrupoNota = 'detrator' | 'neutro' | 'promotor' | 'insatisfeito' | 'satisfeito'

/** Formato antigo da condição (antes da etapa 5l). Só entrada: a API converte para `logica.mostrar_se` (§2.8). */
export type CondicaoPergunta =
  | { tipo: 'grupo'; grupos: GrupoNota[] }
  | { tipo: 'nota'; operador: '<=' | '>='; valor: number }

// ── Lógica (etapa 5l, docs/api-etapa-5l.md §1.3 e §2) ─────────────────────────

export type Juncao = 'todas' | 'qualquer'

export type Operador =
  | 'igual'
  | 'diferente'
  | 'menor'
  | 'menor_igual'
  | 'maior'
  | 'maior_igual'
  | 'entre'
  | 'grupo_e'
  | 'respondida'
  | 'nao_respondida'
  | 'um_de'
  | 'nenhum_de'
  | 'inclui_algum'
  | 'inclui_todos'
  | 'nao_inclui_nenhum'
  | 'contem'
  | 'nao_contem'
  | 'comeca_com'
  | 'termina_com'

/** Valor de uma condição: número, texto, data (AAAA-MM-DD), sim/não, faixa `[a, b]` ou lista (opções, grupos). */
export type ValorCondicao = number | string | boolean | (number | string)[]

export interface Condicao {
  /** Id de uma pergunta (nunca conteúdo nem quebra de página). */
  fonte: string
  op: Operador
  /** Ausente em `respondida` e `nao_respondida`. */
  valor?: ValorCondicao
}

/** Grupo de condições, sem aninhar: `todas` (E) ou `qualquer` (OU). Grupo null ou ausente vale como verdadeiro. */
export interface Grupo {
  juncao: Juncao
  condicoes: Condicao[]
}

/** Regra de pular: avaliada depois da pergunta; vale a 1ª verdadeira. `para` = id de item posterior ou "fim". */
export interface Regra {
  id: string
  se: Grupo
  para: string
}

export interface Logica {
  /** O item só aparece se o grupo for verdadeiro (perguntas e conteúdo). */
  mostrar_se?: Grupo | null
  /** Só perguntas. */
  pular?: Regra[]
}

export interface BotaoFinal {
  texto: string
  url: string
}

/** Final por condição (`formularios.finais`). Nenhum vale: o final padrão do tema. */
export interface Final {
  id: string
  /** Nome interno (editor e relatórios). */
  nome: string
  titulo: string
  html?: string | null
  botao?: BotaoFinal | null
  /** null = sempre vale. */
  mostrar_se?: Grupo | null
}

export type ExibicaoEscolha = 'botoes' | 'lista'
export type ModoConteudo = 'visual' | 'html'

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
  /** Formato antigo (só entrada); a saída da API nunca tem. */
  condicao?: CondicaoPergunta | null
  /** Etapa 5l: mostrar se e regras de pular. */
  logica?: Logica | null
  /** `conteudo`: o HTML (limpo pela API e de novo no navegador). */
  html?: string | null
  /** `conteudo`: em que aba o editor abre (só dica). */
  modo?: ModoConteudo
  /** Escolhas: embaralhar a ordem das opções para quem responde (uma vez por visita). */
  aleatorizar?: boolean
  /** Escolha única: botões (padrão) ou lista suspensa. */
  exibicao?: ExibicaoEscolha
  /** Escolha múltipla: no máximo N opções (2 até o número de opções), ou null. */
  max_selecoes?: number | null
  /** Texto curto e comentário: texto de exemplo dentro do campo. */
  placeholder?: string | null
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
  /** Etapa 5l: o começo das URLs das imagens da plataforma (só essas entram no HTML). */
  prefixo_imagens?: string | null
  /** Etapa 5l: há finais por condição (o navegador já prepara o limpador de HTML para o final). */
  tem_finais?: boolean
}

/** Valor de uma resposta: número (notas), texto, lista (múltipla escolha) ou sim/não. */
export type ValorResposta = number | string | string[] | boolean

export type Respostas = Record<string, ValorResposta>

export interface TelaFinal {
  titulo_final: string
  texto_final: string
  /** Etapa 5l: o final escolhido pela lógica (null = final padrão do tema). */
  final_id?: string | null
  /** Etapa 5l: o HTML do final escolhido (variáveis já trocadas pela API, com escape); null no final padrão. */
  html_final?: string | null
  /** Etapa 5l: o botão do final escolhido (abre em nova aba). */
  botao_final?: BotaoFinal | null
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

/** Prévia (etapa 5l): `focoId` com este valor mostra o final padrão do tema (não é id válido de item nem de final). */
export const FOCO_FINAL_PADRAO = ':final_padrao'

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
