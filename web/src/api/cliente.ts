import { registrarPedidoQueFalhou } from '@/utils/diagnostico'
import { ApiError, erroDeConexao, lerErroApi } from './erros'

export const API_URL: string = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1').replace(/\/+$/, '')

type Metodo = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface OpcoesRequisicao {
  metodo?: Metodo
  corpo?: unknown
  query?: Record<string, string | number | boolean | null | undefined>
  /** Envia o token de sessão (padrão: sim, se houver). */
  autenticar?: boolean
  /** Não dispara os tratamentos globais (aviso de 403, saída em 401). */
  semTratamentoGlobal?: boolean
  sinal?: AbortSignal
}

/**
 * Ganchos que o app registra no início (main.ts). Ficam aqui para o cliente
 * não depender do router nem do Pinia diretamente.
 */
export interface GanchosCliente {
  obterToken: () => string | null
  aoSessaoInvalida: (erro: ApiError) => void
  aoSemPermissao: (erro: ApiError) => void
}

const ganchos: GanchosCliente = {
  obterToken: () => null,
  aoSessaoInvalida: () => {},
  aoSemPermissao: () => {},
}

export function configurarCliente(novos: Partial<GanchosCliente>): void {
  Object.assign(ganchos, novos)
}

function montarUrl(caminho: string, query?: OpcoesRequisicao['query']): string {
  const url = API_URL + (caminho.startsWith('/') ? caminho : `/${caminho}`)
  if (!query) return url
  const params = new URLSearchParams()
  for (const [chave, valor] of Object.entries(query)) {
    if (valor === undefined || valor === null || valor === '') continue
    params.set(chave, String(valor))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

async function lerCorpo(resposta: Response): Promise<unknown> {
  if (resposta.status === 204) return undefined
  const texto = await resposta.text()
  if (!texto) return undefined
  try {
    return JSON.parse(texto) as unknown
  } catch {
    return texto
  }
}

export async function requisitar<T>(caminho: string, opcoes: OpcoesRequisicao = {}): Promise<T> {
  const { metodo = 'GET', corpo, query, autenticar = true, semTratamentoGlobal = false, sinal } = opcoes
  const cabecalhos: Record<string, string> = { Accept: 'application/json' }
  const multipart = typeof FormData !== 'undefined' && corpo instanceof FormData
  // Com FormData o navegador define o Content-Type (com o boundary).
  if (corpo !== undefined && !multipart) cabecalhos['Content-Type'] = 'application/json'
  const token = autenticar ? ganchos.obterToken() : null
  if (token) cabecalhos.Authorization = `Bearer ${token}`

  let resposta: Response
  try {
    resposta = await fetch(montarUrl(caminho, query), {
      method: metodo,
      headers: cabecalhos,
      body: corpo === undefined ? undefined : multipart ? (corpo as FormData) : JSON.stringify(corpo),
      signal: sinal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    registrarPedidoQueFalhou({ metodo, caminho, status: 0, codigo: 'sem_conexao' })
    throw erroDeConexao()
  }

  const dados = await lerCorpo(resposta)
  if (resposta.ok) return dados as T
  const erro = tratarErro(resposta.status, dados, !!token, semTratamentoGlobal)
  // Diagnóstico do feedback de erro (utils/diagnostico): o pedido que falhou, com o código e o request id da API.
  if (resposta.status !== 401) {
    registrarPedidoQueFalhou({ metodo, caminho, status: resposta.status, codigo: erro.codigo, requestId: resposta.headers?.get?.('X-Request-ID') })
  }
  throw erro
}

function tratarErro(status: number, dados: unknown, comToken: boolean, semTratamentoGlobal: boolean): ApiError {
  const erro = lerErroApi(status, dados)
  if (!semTratamentoGlobal) {
    // Só tratamos 401 como "sessão caiu" quando havia sessão (ex.: senha errada no login também é 401).
    if (erro.status === 401 && erro.codigo === 'sessao_invalida' && comToken) ganchos.aoSessaoInvalida(erro)
    else if (erro.status === 403 && erro.codigo === 'sem_permissao') ganchos.aoSemPermissao(erro)
  }
  return erro
}

/** Nome do arquivo no cabeçalho Content-Disposition (filename* ou filename). */
export function nomeDoArquivo(disposicao: string | null, padrao: string): string {
  if (!disposicao) return padrao
  const estrela = disposicao.match(/filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i)
  if (estrela) {
    try {
      return decodeURIComponent(estrela[1]!.trim().replace(/^"|"$/g, ''))
    } catch {
      /* cai no filename simples */
    }
  }
  const simples = disposicao.match(/filename\s*=\s*"?([^";]+)"?/i)
  return simples ? simples[1]!.trim() : padrao
}

/**
 * Baixa um arquivo da API (CSV, modelo...) com o token no cabeçalho: busca como blob
 * e dispara o download no navegador. Erros viram ApiError como nas outras chamadas.
 */
export async function baixarArquivo(
  caminho: string,
  nomePadrao: string,
  query?: OpcoesRequisicao['query'],
): Promise<void> {
  const token = ganchos.obterToken()
  let resposta: Response
  try {
    resposta = await fetch(montarUrl(caminho, query), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  } catch {
    throw erroDeConexao()
  }
  if (!resposta.ok) throw tratarErro(resposta.status, await lerCorpo(resposta), !!token, false)
  const blob = await resposta.blob()
  const nome = nomeDoArquivo(resposta.headers.get('Content-Disposition'), nomePadrao)
  salvarBlob(blob, nome)
}

/**
 * Busca um arquivo da API como blob, com o token no cabeçalho (ex.: as imagens privadas do feedback, que não têm URL
 * pública). Erros viram ApiError, sem os tratamentos globais (a tela mostra a imagem que não carregou).
 */
export async function obterBlob(caminho: string, sinal?: AbortSignal): Promise<Blob> {
  const token = ganchos.obterToken()
  let resposta: Response
  try {
    resposta = await fetch(montarUrl(caminho), { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: sinal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw erroDeConexao()
  }
  if (!resposta.ok) throw tratarErro(resposta.status, await lerCorpo(resposta), !!token, true)
  return resposta.blob()
}

/** Dispara o download de um blob já pronto. */
export function salvarBlob(blob: Blob, nome: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nome
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const api = {
  get: <T>(caminho: string, opcoes?: Omit<OpcoesRequisicao, 'metodo' | 'corpo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'GET' }),
  post: <T>(caminho: string, corpo?: unknown, opcoes?: Omit<OpcoesRequisicao, 'metodo' | 'corpo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'POST', corpo }),
  put: <T>(caminho: string, corpo?: unknown, opcoes?: Omit<OpcoesRequisicao, 'metodo' | 'corpo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'PUT', corpo }),
  patch: <T>(caminho: string, corpo?: unknown, opcoes?: Omit<OpcoesRequisicao, 'metodo' | 'corpo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'PATCH', corpo }),
  delete: <T = void>(caminho: string, opcoes?: Omit<OpcoesRequisicao, 'metodo' | 'corpo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'DELETE' }),
}
