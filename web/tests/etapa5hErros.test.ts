// Etapa 5h, aviso de erros do site (docs/api-etapa-5h.md §4; src/utils/erros.ts): o local da tela sem ids nem tokens,
// o que fica de fora (respostas da API, rede, extensões, "ResizeObserver loop"), uma vez por mensagem e até 5 por
// carregamento, o corpo dentro dos 4 KB, o POST para a API (com o token da sessão, quando há) e a ligação com a janela
// e com o app Vue.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick } from 'vue'
import { API_URL } from '@/api/cliente'
import { ApiError, erroDeConexao } from '@/api/erros'
import {
  MAX_BYTES,
  MAX_POR_CARREGAMENTO,
  VERSAO_SITE,
  criarAvisoDeErros,
  descrever,
  deveIgnorar,
  localDaTela,
  montarCorpo,
  type ErroSite,
} from '@/utils/erros'

const ORIGEM = 'https://toqqi.com.br'
const NOSSA = `TypeError: x is undefined\n    at Ue (${ORIGEM}/assets/index-B2x9kQ1z.js:12:345)\n    at ${ORIGEM}/assets/vendor-AbCdEf12.js:1:2`

function erroCom(mensagem: string, pilha = NOSSA, nome = 'TypeError'): Error {
  const e = new Error(mensagem)
  e.name = nome
  e.stack = pilha
  return e
}

function aviso(extra: Parameters<typeof criarAvisoDeErros>[0] = {}) {
  const enviados: { erro: ErroSite; token: string | null }[] = []
  const a = criarAvisoDeErros({ origem: ORIGEM, caminho: () => '/contatos/123', enviar: (erro, token) => enviados.push({ erro, token }), ...extra })
  return { a, enviados }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('local da tela', () => {
  it('sem query nem hash, com ids e tokens trocados', () => {
    expect(localDaTela('/contatos/123?busca=Ana#topo')).toBe('/contatos/:id')
    expect(localDaTela('/planos-de-acao/45')).toBe('/planos-de-acao/:id')
    expect(localDaTela('/relatorios/temas')).toBe('/relatorios/temas')
    expect(localDaTela('/importacao/550e8400-e29b-41d4-a716-446655440000')).toBe('/importacao/:token')
    expect(localDaTela('/r/Zx8kQ2mN4pR6sT8vW0yB2dF4h')).toBe('/r/:token')
    expect(localDaTela('/r/curto')).toBe('/r/:token')
    expect(localDaTela('/f/AbC123')).toBe('/f/:codigo')
    expect(localDaTela('/sair/abc.def')).toBe('/sair/:token')
    expect(localDaTela('/configuracoes/dados-da-conta')).toBe('/configuracoes/dados-da-conta')
    expect(localDaTela('/' + 'a'.repeat(300))).toHaveLength(200)
  })
})

describe('o que fica de fora', () => {
  it('respostas da API e falhas de rede', () => {
    expect(deveIgnorar(new ApiError(500, 'erro_servidor', 'Algo deu errado'), ORIGEM)).toBe(true)
    expect(deveIgnorar(new ApiError(404, 'nao_encontrado', 'x'), ORIGEM)).toBe(true)
    expect(deveIgnorar(erroDeConexao(), ORIGEM)).toBe(true)
    expect(deveIgnorar({ name: 'ApiError', status: 409, message: 'x' }, ORIGEM)).toBe(true)
    for (const m of ['Failed to fetch', 'NetworkError when attempting to fetch resource.', 'Load failed',
      'Failed to fetch dynamically imported module: /assets/x.js', 'Importing a module script failed.']) {
      expect(deveIgnorar(erroCom(m), ORIGEM)).toBe(true)
    }
    expect(deveIgnorar(new DOMException('cancelado', 'AbortError'), ORIGEM)).toBe(true)
  })

  it('"ResizeObserver loop" e "Script error."', () => {
    expect(deveIgnorar(erroCom('ResizeObserver loop limit exceeded', ''), ORIGEM)).toBe(true)
    expect(deveIgnorar(erroCom('ResizeObserver loop completed with undelivered notifications.', ''), ORIGEM)).toBe(true)
    expect(deveIgnorar(new Error('Script error.'), ORIGEM)).toBe(true)
  })

  it('erros de extensões: pilha só com endereços de fora do nosso', () => {
    const extensao = 'TypeError: x\n    at f (chrome-extension://abcdefghij/conteudo.js:1:2)'
    const firefox = 'f@moz-extension://1234-abcd/conteudo.js:3:4'
    const safari = 'f@webkit-masked-url://hidden/:1:2'
    const outroSite = 'TypeError: x\n    at f (https://outro.com/script.js:1:2)'
    for (const pilha of [extensao, firefox, safari, outroSite]) expect(deveIgnorar(erroCom('x', pilha), ORIGEM)).toBe(true)
    // misturada (nosso código chamou a extensão, ou o contrário): fica
    expect(deveIgnorar(erroCom('x', `${extensao}\n    at g (${ORIGEM}/assets/index-B2x9kQ1z.js:1:2)`), ORIGEM)).toBe(false)
    // sem pilha nenhuma não dá para saber: fica
    expect(deveIgnorar(erroCom('x', ''), ORIGEM)).toBe(false)
    expect(deveIgnorar('texto lançado', ORIGEM)).toBe(false)
    // o arquivo do evento "error" da janela, quando é de extensão ou de outro site
    expect(deveIgnorar(erroCom('x', ''), ORIGEM, 'chrome-extension://abc/x.js')).toBe(true)
    expect(deveIgnorar(erroCom('x', ''), ORIGEM, 'https://cdn.outro.com/x.js')).toBe(true)
    expect(deveIgnorar(erroCom('x', ''), ORIGEM, `${ORIGEM}/assets/x.js`)).toBe(false)
  })

  it('o resto passa', () => {
    expect(deveIgnorar(erroCom('Cannot read properties of undefined'), ORIGEM)).toBe(false)
    expect(deveIgnorar(erroCom('Falhou', `Error: Falhou\n    at f (http://localhost:5401/src/main.ts:3:1)`), 'http://localhost:5401')).toBe(false)
  })
})

describe('descrever o que foi lançado', () => {
  it('Error, objeto e texto', () => {
    expect(descrever(erroCom('m', 'p', 'RangeError'))).toEqual({ tipo: 'RangeError', mensagem: 'm', pilha: 'p' })
    expect(descrever({ name: 'PromiseRejection', message: 'motivo' })).toEqual({ tipo: 'PromiseRejection', mensagem: 'motivo', pilha: '' })
    expect(descrever('só texto')).toEqual({ tipo: 'Error', mensagem: 'só texto', pilha: '' })
    expect(descrever(undefined)).toEqual({ tipo: 'Error', mensagem: 'undefined', pilha: '' })
  })
})

describe('uma vez por mensagem, até 5 por carregamento', () => {
  it('manda tipo, mensagem, local, pilha e versão; a mesma mensagem só uma vez', () => {
    const { a, enviados } = aviso({ obterToken: () => 'tok' })
    expect(a.avisar(erroCom('x is undefined'))).toBe(true)
    expect(a.avisar(erroCom('x is undefined'))).toBe(false)
    expect(enviados).toEqual([{ erro: { tipo: 'TypeError', mensagem: 'x is undefined', local: '/contatos/:id', pilha: NOSSA, versao: VERSAO_SITE }, token: 'tok' }])
    expect(VERSAO_SITE).toBe('local')
    // outro tipo com a mesma mensagem é outra mensagem
    expect(a.avisar(erroCom('x is undefined', NOSSA, 'RangeError'))).toBe(true)
    expect(a.enviados).toBe(2)
  })

  it('no máximo 5 por carregamento; os ignorados não contam', () => {
    const { a, enviados } = aviso()
    expect(a.avisar(new ApiError(500, 'erro_servidor', 'x'))).toBe(false)
    const resultados = Array.from({ length: 7 }, (_, i) => a.avisar(erroCom(`erro ${i}`)))
    expect(resultados).toEqual([true, true, true, true, true, false, false])
    expect(enviados).toHaveLength(MAX_POR_CARREGAMENTO)
  })

  it('o token que falha ao ler não impede o envio, e um erro ao mandar não quebra nada', () => {
    const { a, enviados } = aviso({
      obterToken: () => {
        throw new Error('sem pinia')
      },
    })
    expect(a.avisar(erroCom('a'))).toBe(true)
    expect(enviados[0]!.token).toBeNull()
    const quebrado = criarAvisoDeErros({
      origem: ORIGEM,
      enviar: () => {
        throw new Error('rede')
      },
    })
    expect(quebrado.avisar(erroCom('b'))).toBe(false)
  })
})

describe('o corpo cabe nos 4 KB da API', () => {
  it('a pilha cede primeiro, depois a mensagem; tudo em UTF-8', () => {
    const grande = { tipo: 'TypeError', mensagem: 'ç'.repeat(900), local: '/inicio', pilha: 'á'.repeat(5000), versao: 'abc 1234!' }
    const corpo = montarCorpo(grande)
    expect(new TextEncoder().encode(corpo).length).toBeLessThanOrEqual(MAX_BYTES)
    const lido = JSON.parse(corpo) as ErroSite
    expect(lido.versao).toBe('abc1234')
    expect(lido.mensagem.length).toBeGreaterThan(400)
    expect(lido.pilha.length).toBeLessThan(5000)
    // nem sem a pilha cabe: a mensagem cede também
    const enorme = montarCorpo({ ...grande, tipo: '€'.repeat(300), local: '€'.repeat(300), mensagem: '€'.repeat(5000) })
    expect(new TextEncoder().encode(enorme).length).toBeLessThanOrEqual(MAX_BYTES)
    const lidoEnorme = JSON.parse(enorme) as ErroSite
    expect(lidoEnorme.pilha).toBe('')
    expect(lidoEnorme.mensagem.length).toBeLessThan(1000)
    expect([lidoEnorme.tipo.length, lidoEnorme.local.length]).toEqual([200, 200])
    expect(JSON.parse(montarCorpo({ ...grande, tipo: '' })).tipo).toBe('Error')
  })
})

describe('POST /publico/erros', () => {
  it('manda para a API, com o token quando há e sem esperar resposta', async () => {
    const fetch = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetch)
    const a = criarAvisoDeErros({ origem: ORIGEM, caminho: () => '/inicio', obterToken: () => 'abc' })
    expect(a.avisar(erroCom('falhou'))).toBe(true)
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`${API_URL}/publico/erros`)
    expect(init).toMatchObject({ method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer abc' } })
    expect(JSON.parse(init.body as string)).toEqual({ tipo: 'TypeError', mensagem: 'falhou', local: '/inicio', pilha: NOSSA, versao: 'local' })
    // sem sessão, sem Authorization; a falha do fetch fica quieta
    fetch.mockImplementationOnce(async () => {
      throw new TypeError('Failed to fetch')
    })
    const b = criarAvisoDeErros({ origem: ORIGEM, caminho: () => '/r/abc' })
    expect(b.avisar(erroCom('outro'))).toBe(true)
    await nextTick()
    expect((fetch.mock.calls[1] as unknown as [string, RequestInit])[1].headers).toEqual({ 'Content-Type': 'application/json' })
  })
})

describe('instalar na página', () => {
  it('liga a janela uma vez ("error" e "unhandledrejection") e o errorHandler do app, que continua no console', async () => {
    vi.resetModules()
    const { instalarAvisoDeErros } = await import('@/utils/erros')
    const fetch = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetch)
    const corpos = () => fetch.mock.calls.map((c) => JSON.parse((c as unknown as [string, RequestInit])[1].body as string) as ErroSite)
    const pagina = window.location.origin

    const aviso = instalarAvisoDeErros(null, { obterToken: () => null })
    expect(instalarAvisoDeErros(null)).toBe(aviso) // de novo: o mesmo, sem ligar outra vez
    window.dispatchEvent(new ErrorEvent('error', { error: erroCom('na janela', `TypeError: na janela\n    at f (${pagina}/assets/a.js:1:2)`), message: 'na janela', filename: `${pagina}/assets/a.js` }))
    window.dispatchEvent(new ErrorEvent('error', { message: 'de extensão', filename: 'chrome-extension://abc/x.js' }))
    const rejeicao = new Event('unhandledrejection')
    Object.assign(rejeicao, { reason: 'motivo em texto' })
    window.dispatchEvent(rejeicao)
    const rejeicaoApi = new Event('unhandledrejection')
    Object.assign(rejeicaoApi, { reason: new ApiError(500, 'erro_servidor', 'x') })
    window.dispatchEvent(rejeicaoApi)
    expect(corpos().map((c) => [c.tipo, c.mensagem])).toEqual([['TypeError', 'na janela'], ['PromiseRejection', 'motivo em texto']])

    const consoleErro = vi.spyOn(console, 'error').mockImplementation(() => {})
    const raiz = document.createElement('div')
    document.body.appendChild(raiz)
    const app = createApp(
      defineComponent({
        setup() {
          throw new RangeError('no componente')
        },
        render: () => h('div'),
      }),
    )
    instalarAvisoDeErros(app)
    app.mount(raiz)
    expect(corpos().at(-1)).toMatchObject({ tipo: 'RangeError', mensagem: 'no componente' })
    expect(consoleErro).toHaveBeenCalled()
    app.unmount()
    raiz.remove()
  })
})
