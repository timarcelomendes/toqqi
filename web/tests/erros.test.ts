import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, lerErroApi, MENSAGEM_MUITAS_TENTATIVAS } from '@/api/erros'
import { configurarCliente, nomeDoArquivo, requisitar } from '@/api/cliente'

describe('lerErroApi', () => {
  it('lê código, mensagem e campos do formato da API', () => {
    const e = lerErroApi(422, {
      erro: { codigo: 'validacao', mensagem: 'Confira os campos.', campos: { email: 'E-mail inválido.' } },
    })
    expect(e).toBeInstanceOf(ApiError)
    expect(e.status).toBe(422)
    expect(e.codigo).toBe('validacao')
    expect(e.mensagem).toBe('Confira os campos.')
    expect(e.campo('email')).toBe('E-mail inválido.')
  })

  it('aceita campos com lista de mensagens e ignora valores que não são texto', () => {
    const e = lerErroApi(422, { erro: { codigo: 'x', mensagem: 'y', campos: { a: ['um', 'dois'], b: 3 } } })
    expect(e.campos).toEqual({ a: 'um dois' })
  })

  it('usa textos padrão quando o corpo não segue o formato', () => {
    const e = lerErroApi(500, '<html>erro</html>')
    expect(e.codigo).toBe('erro_servidor')
    expect(e.mensagem).toMatch(/Algo deu errado/)
    expect(e.campos).toEqual({})
  })

  it('401 sem corpo vira sessao_invalida', () => {
    expect(lerErroApi(401, undefined).codigo).toBe('sessao_invalida')
  })

  it('429 sempre mostra a mensagem padrão de muitas tentativas', () => {
    const e = lerErroApi(429, { erro: { codigo: 'muitas_tentativas', mensagem: 'Rate limit exceeded' } })
    expect(e.codigo).toBe('muitas_tentativas')
    expect(e.mensagem).toBe(MENSAGEM_MUITAS_TENTATIVAS)
  })
})

describe('requisitar', () => {
  const aoSessaoInvalida = vi.fn()
  const aoSemPermissao = vi.fn()

  function responder(status: number, corpo?: unknown) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(corpo === undefined ? null : JSON.stringify(corpo), { status })),
    )
  }

  afterEach(() => {
    vi.unstubAllGlobals()
    aoSessaoInvalida.mockReset()
    aoSemPermissao.mockReset()
  })

  it('envia o token e devolve o JSON', async () => {
    configurarCliente({ obterToken: () => 'abc', aoSessaoInvalida, aoSemPermissao })
    responder(200, { ok: true })
    await expect(requisitar('/eu')).resolves.toEqual({ ok: true })
    const [, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0]!
    expect((init as RequestInit).headers).toMatchObject({ Authorization: 'Bearer abc' })
  })

  it('204 devolve undefined', async () => {
    configurarCliente({ obterToken: () => 'abc', aoSessaoInvalida, aoSemPermissao })
    responder(204)
    await expect(requisitar('/auth/sair', { metodo: 'POST' })).resolves.toBeUndefined()
  })

  it('401 sessao_invalida com token chama o gancho de sessão', async () => {
    configurarCliente({ obterToken: () => 'abc', aoSessaoInvalida, aoSemPermissao })
    responder(401, { erro: { codigo: 'sessao_invalida', mensagem: 'Sua sessão expirou.' } })
    await expect(requisitar('/eu')).rejects.toMatchObject({ codigo: 'sessao_invalida' })
    expect(aoSessaoInvalida).toHaveBeenCalledOnce()
    expect(aoSessaoInvalida.mock.calls[0]![0].mensagem).toBe('Sua sessão expirou.')
  })

  it('401 de senha errada no login não derruba a sessão', async () => {
    configurarCliente({ obterToken: () => null, aoSessaoInvalida, aoSemPermissao })
    responder(401, { erro: { codigo: 'credenciais_invalidas', mensagem: 'E-mail ou senha incorretos.' } })
    await expect(requisitar('/auth/entrar', { metodo: 'POST', corpo: {}, autenticar: false })).rejects.toMatchObject({
      codigo: 'credenciais_invalidas',
      mensagem: 'E-mail ou senha incorretos.',
    })
    expect(aoSessaoInvalida).not.toHaveBeenCalled()
  })

  it('403 sem_permissao avisa, mas outros 403 (ex.: acesso_pendente) não', async () => {
    configurarCliente({ obterToken: () => 'abc', aoSessaoInvalida, aoSemPermissao })
    responder(403, { erro: { codigo: 'sem_permissao', mensagem: 'Sem permissão.' } })
    await expect(requisitar('/equipe')).rejects.toBeInstanceOf(ApiError)
    expect(aoSemPermissao).toHaveBeenCalledOnce()

    responder(403, { erro: { codigo: 'acesso_pendente', mensagem: 'Aguardando aprovação.' } })
    await expect(requisitar('/auth/entrar', { metodo: 'POST' })).rejects.toMatchObject({ codigo: 'acesso_pendente' })
    expect(aoSemPermissao).toHaveBeenCalledOnce()
  })

  it('falha de rede vira erro sem_conexao', async () => {
    configurarCliente({ obterToken: () => null, aoSessaoInvalida, aoSemPermissao })
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    await expect(requisitar('/eu')).rejects.toMatchObject({ status: 0, codigo: 'sem_conexao' })
  })
})

describe('etapa 2: upload e download', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('FormData vai sem Content-Type (o navegador põe o boundary)', async () => {
    configurarCliente({ obterToken: () => 'abc' })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ id: 1 }), { status: 201 })))
    const corpo = new FormData()
    corpo.append('arquivo', new Blob(['a;b']), 'x.csv')
    await requisitar('/importacao/analisar', { metodo: 'POST', corpo })
    const [, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0]!
    const headers = (init as RequestInit).headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
    expect(headers.Authorization).toBe('Bearer abc')
    expect((init as RequestInit).body).toBe(corpo)
  })

  it('lê o nome do arquivo do Content-Disposition', () => {
    expect(nomeDoArquivo('attachment; filename="respostas.csv"', 'x')).toBe('respostas.csv')
    expect(nomeDoArquivo("attachment; filename*=UTF-8''pesquisa%20p%C3%B3s.csv", 'x')).toBe('pesquisa pós.csv')
    expect(nomeDoArquivo(null, 'padrao.csv')).toBe('padrao.csv')
  })
})
