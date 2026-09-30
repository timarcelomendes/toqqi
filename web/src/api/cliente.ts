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
  if (corpo !== undefined) cabecalhos['Content-Type'] = 'application/json'
  const token = autenticar ? ganchos.obterToken() : null
  if (token) cabecalhos.Authorization = `Bearer ${token}`

  let resposta: Response
  try {
    resposta = await fetch(montarUrl(caminho, query), {
      method: metodo,
      headers: cabecalhos,
      body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
      signal: sinal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw erroDeConexao()
  }

  const dados = await lerCorpo(resposta)
  if (resposta.ok) return dados as T

  const erro = lerErroApi(resposta.status, dados)
  if (!semTratamentoGlobal) {
    // Só tratamos 401 como "sessão caiu" quando havia sessão (ex.: senha errada no login também é 401).
    if (erro.status === 401 && erro.codigo === 'sessao_invalida' && token) ganchos.aoSessaoInvalida(erro)
    else if (erro.status === 403 && erro.codigo === 'sem_permissao') ganchos.aoSemPermissao(erro)
  }
  throw erro
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
