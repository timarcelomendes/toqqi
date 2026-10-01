// API falsa para os testes de componente: troca o fetch global e responde por "MÉTODO /caminho".
// Caminhos aceitam ":param" (ex.: "PATCH /acoes/:id").
import { vi } from 'vitest'

export interface Chamada {
  metodo: string
  caminho: string
  url: URL
  corpo: unknown
}

type Resposta = unknown | Response
type Rota = (c: Chamada) => Resposta | Promise<Resposta>

export function apiFalsa(rotas: Record<string, Rota>) {
  const chamadas: Chamada[] = []
  const padroes = Object.entries(rotas).map(([chave, rota]) => {
    const [metodo, caminho] = chave.split(' ') as [string, string]
    return { metodo, re: new RegExp(`^${caminho.replace(/:\w+/g, '[^/]+').replace(/\./g, '\\.')}$`), rota }
  })
  const fetch = vi.fn(async (entrada: string | URL, init: RequestInit = {}) => {
    const url = new URL(String(entrada))
    const metodo = (init.method ?? 'GET').toUpperCase()
    const caminho = url.pathname.replace(/^\/api\/v1/, '')
    const corpo = typeof init.body === 'string' ? (JSON.parse(init.body) as unknown) : init.body
    const chamada = { metodo, caminho, url, corpo }
    chamadas.push(chamada)
    const achada = padroes.find((p) => p.metodo === metodo && p.re.test(caminho))
    if (!achada) return new Response(JSON.stringify({ erro: { codigo: 'nao_encontrado', mensagem: 'Não encontrado.' } }), { status: 404 })
    const r = await achada.rota(chamada)
    if (r instanceof Response) return r
    return r === undefined ? new Response(null, { status: 204 }) : new Response(JSON.stringify(r), { status: 200 })
  })
  vi.stubGlobal('fetch', fetch)
  return { fetch, chamadas }
}

export function erro422(mensagem: string, campos: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ erro: { codigo: 'validacao', mensagem, campos } }), { status: 422 })
}
