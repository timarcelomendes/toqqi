// Estrutura dos documentos legais (docs/api-aceite-lgpd.md §3). Texto puro: nada de HTML; links são dados.

/** Um trecho de texto: string simples, ou uma sequência de pedaços com links (href interno "/..." ou "mailto:"/"https://"). */
export type Texto = string | Array<string | { texto: string; href: string }>

export type Bloco =
  | { tipo: 'p'; texto: Texto }
  | { tipo: 'lista'; itens: Texto[] }
  | { tipo: 'tabela'; colunas: string[]; linhas: Texto[][] }

export interface Secao {
  /** Âncora da seção (ex.: "cookies" → /privacidade#cookies). Só letras minúsculas, números e hífen. */
  id: string
  titulo: string
  blocos: Bloco[]
}

export interface DocumentoLegal {
  titulo: string
  /** Parágrafos antes da primeira seção. */
  introducao: Bloco[]
  secoes: Secao[]
}
