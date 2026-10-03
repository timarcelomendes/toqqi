// Regras puras do banco de imagens da conta (docs/api-etapa-5e.md §3 e §6.2): textos da grade, limite e a imagem de
// topo escolhida. Sem Vue, para testar com facilidade.
import type { ImagemBanco, ImagemTopoEmail } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { textoDimensoes } from './visualEmail'

/** O limite da API (vem também em GET /imagens). */
export const LIMITE_BANCO_PADRAO = 30

/** A dica de tamanho para a imagem de topo. */
export const DICA_TAMANHO_TOPO = 'Para o topo do e-mail, use 1200 × 400 px.'

/** "3 de 30 imagens". */
export function textoQuantidadeImagens(quantidade: number, limite: number = LIMITE_BANCO_PADRAO): string {
  return `${quantidade} de ${limite} ${limite === 1 ? 'imagem' : 'imagens'}`
}

/** O banco chegou ao limite: para enviar outra, é preciso excluir uma. */
export function bancoCheio(quantidade: number, limite: number = LIMITE_BANCO_PADRAO): boolean {
  return quantidade >= limite
}

/** A mesma mensagem da API (409 `limite_imagens`). */
export function mensagemLimiteBanco(limite: number = LIMITE_BANCO_PADRAO): string {
  return `O banco de imagens tem até ${limite} imagens. Exclua uma para enviar outra.`
}

/** O nome do arquivo enviado; sem ele, a data em que a imagem chegou. */
export function nomeImagem(i: Pick<ImagemBanco, 'nome' | 'criada_em'>): string {
  return i.nome?.trim() || `Imagem de ${formatarData(i.criada_em)}`
}

/** "245 KB" ou "1,2 MB". */
export function tamanhoArquivo(bytes: number | null | undefined): string | null {
  if (!bytes || bytes < 0) return null
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`
}

/** "1200 × 400 px · 245 KB" (o que a API souber). */
export function detalhesImagem(i: Pick<ImagemBanco, 'largura' | 'altura' | 'tamanho'>): string {
  return [textoDimensoes(i.largura, i.altura), tamanhoArquivo(i.tamanho)].filter(Boolean).join(' · ')
}

/** A imagem escolhida no banco, no formato da configuração (`email_imagem_topo`). */
export function paraImagemTopo(i: Pick<ImagemBanco, 'id' | 'url' | 'largura' | 'altura'>): ImagemTopoEmail {
  return { id: i.id, url: i.url, largura: i.largura ?? null, altura: i.altura ?? null }
}

/** Mesmo id (o da API pode vir como número e o guardado como texto). */
export function mesmaImagem(a: { id: ImagemBanco['id'] } | null | undefined, id: ImagemBanco['id'] | null | undefined): boolean {
  return !!a && id !== null && id !== undefined && String(a.id) === String(id)
}
