import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PaginaDescadastro from '@/publico/PaginaDescadastro.vue'
import { montarMotivo, tokenDoCaminho } from '@/publico/descadastro'

function resposta(corpo: unknown, status = 200) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Simula a API: cada chamada consome a próxima resposta da fila. */
function simularApi(...respostas: Response[]) {
  const fn = vi.fn(async () => respostas.shift() ?? resposta({}, 500))
  vi.stubGlobal('fetch', fn)
  return fn
}

function corpoDa(fn: ReturnType<typeof simularApi>, i: number): unknown {
  const init = (fn.mock.calls[i] as unknown as [string, RequestInit])[1]
  return JSON.parse(String(init.body))
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('regras da página de descadastro', () => {
  it('lê o token do caminho', () => {
    expect(tokenDoCaminho('/sair/abc.def')).toBe('abc.def')
    expect(tokenDoCaminho('/sair/a%2Bb?x=1')).toBe('a+b')
    expect(tokenDoCaminho('/sair/')).toBeNull()
    expect(tokenDoCaminho('/r/abc')).toBeNull()
  })

  it('monta o motivo com o rápido e o texto livre (até 300)', () => {
    expect(montarMotivo('Recebo pesquisas demais', '')).toBe('Recebo pesquisas demais')
    expect(montarMotivo('Não sou cliente', '  mudei  de empresa ')).toBe('Não sou cliente: mudei de empresa')
    expect(montarMotivo('Não quero informar', '')).toBeUndefined()
    expect(montarMotivo(null, '')).toBeUndefined()
    expect(montarMotivo(null, 'só texto')).toBe('só texto')
    expect(montarMotivo('Recebo pesquisas demais', 'x'.repeat(400))!.length).toBe(300)
  })
})

describe('PaginaDescadastro', () => {
  it('mostra e-mail mascarado e empresa, sai da lista com motivo e pode voltar', async () => {
    const api = simularApi(
      resposta({ email_mascarado: 'ma***@empresa.com.br', empresa: 'Acme', descadastrado: false }),
      resposta({ descadastrado: true }),
      resposta({ descadastrado: false }),
    )
    const w = mount(PaginaDescadastro, { props: { caminho: '/sair/tok123' }, attachTo: document.body })
    await flushPromises()
    expect(w.get('[data-teste="email"]').text()).toBe('ma***@empresa.com.br')
    expect(w.text()).toContain('Acme')
    expect(String((api.mock.calls[0] as unknown as [string])[0])).toContain('/publico/descadastro/tok123')

    await w.findAll('input[type="radio"]')[1]!.setValue(true) // "Não sou cliente"
    await w.get('textarea').setValue('Comprei uma vez só')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(corpoDa(api, 1)).toEqual({ motivo: 'Não sou cliente: Comprei uma vez só' })
    expect(w.find('[data-estado="saiu"]').exists()).toBe(true)
    expect(w.text()).toContain('Pronto, você saiu da lista')

    const voltar = w.findAll('button').find((b) => b.text().includes('Mudei de ideia'))!
    await voltar.trigger('click')
    await flushPromises()
    expect(corpoDa(api, 2)).toEqual({ voltar: true })
    expect(w.find('[data-estado="voltou"]').exists()).toBe(true)
    w.unmount()
  })

  it('sem motivo escolhido, envia o pedido sem motivo', async () => {
    const api = simularApi(resposta({ email_mascarado: 'a***@b.com', empresa: 'Acme', descadastrado: false }), resposta({ descadastrado: true }))
    const w = mount(PaginaDescadastro, { props: { caminho: '/sair/tok' } })
    await flushPromises()
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(corpoDa(api, 1)).toEqual({})
  })

  it('quem já saiu vê a confirmação com a opção de voltar', async () => {
    simularApi(resposta({ email_mascarado: 'a***@b.com', empresa: 'Acme', descadastrado: true }))
    const w = mount(PaginaDescadastro, { props: { caminho: '/sair/tok' } })
    await flushPromises()
    expect(w.find('[data-estado="saiu"]').exists()).toBe(true)
    expect(w.text()).toContain('Mudei de ideia, quero voltar a receber')
  })

  it('link inválido (404) e endereço sem token', async () => {
    simularApi(resposta({ erro: { codigo: 'link_invalido', mensagem: 'Link inválido' } }, 404))
    const w = mount(PaginaDescadastro, { props: { caminho: '/sair/xyz' } })
    await flushPromises()
    expect(w.find('[data-estado="invalido"]').exists()).toBe(true)

    const api = simularApi()
    const w2 = mount(PaginaDescadastro, { props: { caminho: '/sair/' } })
    await flushPromises()
    expect(w2.find('[data-estado="invalido"]').exists()).toBe(true)
    expect(api).not.toHaveBeenCalled()
  })

  it('sem conexão: mostra erro e tenta de novo', async () => {
    const fn = vi.fn()
    fn.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    fn.mockResolvedValueOnce(resposta({ email_mascarado: 'a***@b.com', empresa: 'Acme', descadastrado: false }))
    vi.stubGlobal('fetch', fn)
    const w = mount(PaginaDescadastro, { props: { caminho: '/sair/tok' } })
    await flushPromises()
    expect(w.find('[data-estado="erro"]').exists()).toBe(true)
    await w.get('[data-estado="erro"] button').trigger('click')
    await flushPromises()
    expect(w.find('form').exists()).toBe(true)
  })
})
