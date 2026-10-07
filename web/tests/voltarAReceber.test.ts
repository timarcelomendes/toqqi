// Voltar a receber sem achar o e-mail antigo (docs/api-voltar-a-receber.md): a página pública /sair pede o link por
// e-mail (a mesma mensagem sempre), o link inválido da /sair/:token leva a ela e a aba Descadastros passa o endereço.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { h } from 'vue'
import PaginaPedirLink from '@/publico/PaginaPedirLink.vue'
import PaginaDescadastro from '@/publico/PaginaDescadastro.vue'
import AbaDescadastros from '@/modulos/envios/AbaDescadastros.vue'
import ModalDescadastro from '@/modulos/envios/ModalDescadastro.vue'
import { conferirEmail, ehPedirLink } from '@/publico/descadastro'
import { PAGINA_SAIR } from '@/modulos/envios/logica'
import { useSessaoStore } from '@/stores/sessao'
import { apiFalsa, erro422 } from './apiFalsa'

const ler = (arquivo: string) => readFileSync(resolve(__dirname, '..', arquivo), 'utf8')
const MENSAGEM = 'Se este e-mail já recebeu pesquisas pelo Toqqi, o link chega em alguns minutos. Não achou? Olhe também no spam.'

enableAutoUnmount(afterEach)
afterEach(() => {
  document.body.innerHTML = ''
})

describe('regras da página /sair', () => {
  it('reconhece o endereço sem token', () => {
    expect(ehPedirLink('/sair')).toBe(true)
    expect(ehPedirLink('/sair/')).toBe(true)
    expect(ehPedirLink('/sair/abc.def')).toBe(false)
    expect(ehPedirLink('/saira')).toBe(false)
    expect(ehPedirLink('/r/abc')).toBe(false)
  })

  it('confere o e-mail antes de pedir', () => {
    expect(conferirEmail('  ')).toBe('Digite o seu e-mail.')
    expect(conferirEmail('maria')).toMatch(/^Confira o e-mail/)
    expect(conferirEmail('maria@cliente')).toMatch(/^Confira o e-mail/)
    expect(conferirEmail(`${'a'.repeat(250)}@b.com`)).toMatch(/^Confira o e-mail/)
    expect(conferirEmail(' maria@cliente.com.br ')).toBeNull()
  })
})

describe('PaginaPedirLink', () => {
  it('pede o link com o e-mail e mostra a mesma mensagem, com a volta para outro e-mail', async () => {
    const { chamadas } = apiFalsa({ 'POST /publico/descadastro/pedir-link': () => ({ mensagem: MENSAGEM }) })
    const w = mount(PaginaPedirLink, { attachTo: document.body })
    expect(document.title).toBe('Receber ou não as pesquisas')
    expect(w.get('[data-dica-whatsapp]').text()).toContain('responda SAIR para parar ou VOLTAR para voltar a receber')
    await w.get('input[type="email"]').setValue('  Maria@Cliente.com.br ')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(chamadas).toHaveLength(1)
    expect(chamadas[0]!.corpo).toEqual({ email: 'Maria@Cliente.com.br' })
    expect(w.get('[data-estado="enviado"]').text()).toContain('Confira o seu e-mail')
    expect(w.get('[data-mensagem]').text()).toBe(MENSAGEM)
    expect(document.activeElement?.id).toBe('titulo-pedir-link')
    await w.get('[data-estado="enviado"] button').trigger('click')
    await flushPromises()
    expect(w.find('[data-estado="pronto"]').exists()).toBe(true)
    expect((w.get('input[type="email"]').element as HTMLInputElement).value).toBe('')
  })

  it('e-mail vazio ou inválido não chega à API', async () => {
    const { chamadas } = apiFalsa({})
    const w = mount(PaginaPedirLink, { attachTo: document.body })
    await w.get('form').trigger('submit')
    expect(w.get('[data-erro]').text()).toBe('Digite o seu e-mail.')
    expect(w.get('input[type="email"]').attributes('aria-invalid')).toBe('true')
    await w.get('input[type="email"]').setValue('maria')
    await w.get('form').trigger('submit')
    expect(w.get('[data-erro]').text()).toMatch(/^Confira o e-mail/)
    expect(chamadas).toHaveLength(0)
  })

  it('mostra o erro da API (e-mail recusado, muitos pedidos ou sem conexão)', async () => {
    let resposta: Response = erro422('Dados inválidos.', { email: 'Informe um e-mail válido, como nome@empresa.com.br.' })
    apiFalsa({ 'POST /publico/descadastro/pedir-link': () => resposta })
    const w = mount(PaginaPedirLink, { attachTo: document.body })
    await w.get('input[type="email"]').setValue('maria@cliente.com.br')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.get('[data-erro]').text()).toBe('Informe um e-mail válido, como nome@empresa.com.br.')
    resposta = new Response(JSON.stringify({ erro: { codigo: 'muitas_tentativas', mensagem: 'Muitas tentativas. Aguarde um minuto.' } }), { status: 429 })
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.get('[data-erro]').text()).toBe('Muitas tentativas. Aguarde um minuto.')
    resposta = new Response('', { status: 503 })
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.get('[data-erro]').text()).toBe('Não deu certo agora. Confira sua internet e tente de novo.')
    expect(w.find('[data-estado="enviado"]').exists()).toBe(false)
  })
})

describe('quem não acha o e-mail antigo', () => {
  it('o link inválido da /sair/:token leva à página de pedir um link novo', async () => {
    apiFalsa({})
    const w = mount(PaginaDescadastro, { props: { caminho: '/sair/' } })
    await flushPromises()
    expect(w.get('[data-pedir-link]').attributes('href')).toBe('/sair')
  })

  it('a aba Descadastros e o registro manual passam o endereço da página', async () => {
    setActivePinia(createPinia())
    useSessaoStore().definirSessao(
      {
        token: 't',
        expira_em: '2099-01-01T00:00:00Z',
        usuario: { id: 1, nome: 'Ana', email: 'ana@alfa.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
        conta: { id: 1, nome: 'Alfa', plano: null, situacao: 'ativa', teste_ate: null },
        permissoes: ['envios.ver', 'contatos.editar'],
      } as never,
      false,
    )
    apiFalsa({ 'GET /envios/descadastros': () => ({ itens: [], total: 0, pagina: 1, por_pagina: 50 }) })
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
    await router.push('/envios')
    const w = mount(AbaDescadastros, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    const link = w.get('[data-pagina-sair]')
    expect(link.attributes('href')).toBe(`${window.location.origin}/sair`)
    expect(link.text()).toBe(`${window.location.host}/sair`)
    expect(w.text()).toContain('ou respondendo VOLTAR no WhatsApp')
    const modal = mount(ModalDescadastro, { props: { aberto: true }, attachTo: document.body })
    await flushPromises()
    expect(document.body.textContent).toContain(`pedindo um link novo em ${PAGINA_SAIR.texto} ou respondendo VOLTAR no WhatsApp`)
    modal.unmount()
  })
})

describe('servidor e site', () => {
  it('o Render serve /sair pela entrada leve, com a mesma CSP, antes da regra geral do app', () => {
    const yaml = ler('../render.yaml')
    const regra = yaml.indexOf('source: /sair\n        destination: /responder.html')
    expect(regra).toBeGreaterThan(0)
    expect(regra).toBeLessThan(yaml.indexOf('source: /*\n        destination: /index.html'))
    const csp = (caminho: string) => yaml.slice(yaml.indexOf(`- path: ${caminho}\n        name: Content-Security-Policy`)).split('\n')[2]
    expect(csp('/sair')).toBe(csp('/sair/*'))
  })

  it('o rodapé do site e dos guias leva à página', () => {
    for (const arq of ['index.html', 'guias.html', 'reduzir-churn.html', 'clientes-insatisfeitos.html', 'customer-success.html']) {
      expect(ler(arq), arq).toContain('<a href="/sair" style="color:#CBD5E1;text-decoration:none">Sair ou voltar a receber pesquisas</a>')
    }
  })
})
