// Pedidos de acesso: o número ao lado de Equipe no menu (GET /equipe/pendentes, só com equipe.gerenciar, relido a
// cada troca de página no máximo a cada 60 s) e Equipe aberta só com os pedidos pelo atalho do e-mail (?pedidos=1).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { h } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import { recarregarMenuLateral } from '@/composables/menuLateral'
import { limparPedidosAcesso, textoPedidos, usarPedidosAcesso } from '@/composables/pedidosAcesso'
import BarraLateral from '@/layouts/BarraLateral.vue'
import AbaUsuarios from '@/modulos/equipe/AbaUsuarios.vue'
import { apiFalsa } from './apiFalsa'

function entrar(permissoes: string[]) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    } as never,
    false,
  )
}

async function roteador(caminho = '/respostas'): Promise<Router> {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
  await router.push(caminho)
  await router.isReady()
  return router
}

async function montarMenu(recolhivel = false): Promise<{ w: VueWrapper; router: Router }> {
  const router = await roteador()
  const w = mount(BarraLateral, { props: { recolhivel }, global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { w, router }
}

const linkEquipe = (w: VueWrapper) => w.findAll('a').find((a) => a.text().includes('Equipe'))!

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  recarregarMenuLateral()
  limparPedidosAcesso()
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  document.body.innerHTML = ''
})

describe('número de pedidos de acesso ao lado de Equipe', () => {
  it('mostra o número (e o texto para leitores de tela); sem pedidos, nada', async () => {
    entrar(['equipe.gerenciar'])
    const api = apiFalsa({ 'GET /equipe/pendentes': () => ({ total: 2 }) })
    const { w } = await montarMenu()
    expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['GET /equipe/pendentes'])
    const equipe = linkEquipe(w)
    expect(equipe.get('[data-contador-menu]').text()).toBe('2')
    expect(equipe.text()).toContain('2 pedidos de acesso')
    // a tela Equipe acerta o número na hora
    usarPedidosAcesso().definir(0)
    await flushPromises()
    expect(linkEquipe(w).find('[data-contador-menu]').exists()).toBe(false)
  })

  it('relê a cada troca de página no máximo a cada 60 s; falha mantém o último número', async () => {
    entrar(['equipe.gerenciar'])
    let total = 1
    let falhar = false
    const api = apiFalsa({
      'GET /equipe/pendentes': () => (falhar ? new Response('{}', { status: 503 }) : { total }),
    })
    const agora = vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
    const { w, router } = await montarMenu()
    total = 3
    await router.push('/envios')
    await flushPromises()
    expect(api.chamadas).toHaveLength(1) // dentro dos 60 s
    agora.mockReturnValue(1_000_000 + 61_000)
    await router.push('/contatos')
    await flushPromises()
    expect(api.chamadas).toHaveLength(2)
    expect(linkEquipe(w).get('[data-contador-menu]').text()).toBe('3')
    falhar = true
    agora.mockReturnValue(1_000_000 + 130_000)
    await router.push('/inicio')
    await flushPromises()
    expect(api.chamadas).toHaveLength(3)
    expect(linkEquipe(w).get('[data-contador-menu]').text()).toBe('3')
  })

  it('menu recolhido: um ponto no ícone e a dica com o número', async () => {
    entrar(['equipe.gerenciar'])
    apiFalsa({ 'GET /equipe/pendentes': () => ({ total: 1 }) })
    const { w } = await montarMenu(true)
    await w.get('button[aria-controls="menu-lateral"]').trigger('click')
    const equipe = linkEquipe(w)
    expect(equipe.get('[data-contador-menu]').text()).toBe('')
    expect(equipe.text()).toContain('Equipe · 1 pedido de acesso')
  })

  it('sem equipe.gerenciar: nem chama a API nem mostra nada', async () => {
    entrar(['respostas.ver'])
    const api = apiFalsa({ 'GET /equipe/pendentes': () => ({ total: 5 }) })
    const { w } = await montarMenu()
    expect(api.chamadas).toHaveLength(0)
    expect(w.find('[data-contador-menu]').exists()).toBe(false)
  })

  it('texto no singular e no plural', () => {
    expect(textoPedidos(1)).toBe('1 pedido de acesso')
    expect(textoPedidos(4)).toBe('4 pedidos de acesso')
  })
})

describe('Equipe pelo atalho do e-mail', () => {
  const USUARIOS = [
    { id: 1, nome: 'Ana', email: 'ana@alfa.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
    { id: 2, nome: 'Nina', email: 'nina@alfa.com.br', cargo: null, perfil: 'consulta', situacao: 'pendente', email_confirmado: true, ultimo_acesso: null, superadmin: false },
    { id: 3, nome: 'Rui', email: 'rui@alfa.com.br', cargo: null, perfil: 'consulta', situacao: 'pendente', email_confirmado: true, ultimo_acesso: null, superadmin: false },
  ]

  it('?pedidos=1 abre só com os pedidos, e o número do menu segue a lista', async () => {
    entrar(['equipe.gerenciar'])
    apiFalsa({ 'GET /equipe': () => USUARIOS })
    const router = await roteador('/equipe?pedidos=1')
    const w = mount(AbaUsuarios, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    expect(w.text()).toContain('nina@alfa.com.br')
    expect(w.text()).toContain('rui@alfa.com.br')
    expect(w.text()).not.toContain('ana@alfa.com.br')
    expect(usarPedidosAcesso().total.value).toBe(2)
  })

  it('sem o atalho, a lista vem inteira', async () => {
    entrar(['equipe.gerenciar'])
    apiFalsa({ 'GET /equipe': () => USUARIOS })
    const router = await roteador('/equipe')
    const w = mount(AbaUsuarios, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    expect(w.text()).toContain('ana@alfa.com.br')
  })
})
