import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { h } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import { CHAVE_MENU_RECOLHIDO, recarregarMenuLateral, useMenuLateral } from '@/composables/menuLateral'
import BarraLateral from '@/layouts/BarraLateral.vue'

function entrar() {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes: ['painel.ver', 'contatos.ver', 'envios.ver', 'respostas.ver', 'acoes.ver', 'relatorios.ver', 'equipe.gerenciar'],
    },
    false,
  )
}

async function montar(recolhivel: boolean): Promise<VueWrapper> {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
  await router.push('/respostas')
  await router.isReady()
  const w = mount(BarraLateral, { props: { recolhivel }, global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const botao = (w: VueWrapper) => w.find('button[aria-controls="menu-lateral"]')

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  recarregarMenuLateral()
  entrar()
})
afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('menu lateral recolhível', () => {
  it('começa aberto, com nomes visíveis e o botão "Recolher menu"', async () => {
    const w = await montar(true)
    expect(botao(w).attributes('aria-expanded')).toBe('true')
    expect(botao(w).text()).toContain('Recolher menu')
    const respostas = w.findAll('a').find((a) => a.text().includes('Respostas'))!
    expect(respostas.find('span').classes()).not.toContain('sr-only')
    expect(respostas.attributes('aria-current')).toBe('page')
    expect(w.text()).toContain('Administração')
  })

  it('recolhido: só ícones, nomes continuam para leitores de tela, dica ao lado, e a escolha fica guardada', async () => {
    const w = await montar(true)
    await botao(w).trigger('click')
    expect(botao(w).attributes('aria-expanded')).toBe('false')
    expect(botao(w).find('.sr-only').text()).toBe('Expandir menu')
    expect(localStorage.getItem(CHAVE_MENU_RECOLHIDO)).toBe('1')
    const respostas = w.findAll('a').find((a) => a.text().includes('Respostas'))!
    expect(respostas.find('.sr-only').text()).toBe('Respostas')
    expect(respostas.find('[aria-hidden="true"].pointer-events-none').text()).toBe('Respostas')
    // Relatórios ficou pronto na 4b: sem "em breve" no nome nem no selo
    const relatorios = w.findAll('a').find((a) => a.text().includes('Relatórios'))!
    expect(relatorios.find('.sr-only').text()).toBe('Relatórios')
    expect(relatorios.text()).not.toContain('em breve')
    expect(relatorios.attributes('href')).toBe('/relatorios/empresas')
    // o título "Administração" some da tela, mas fica para leitores de tela
    expect(w.find('p.sr-only').text()).toBe('Administração')
    // logo compacto
    expect(w.find('a[aria-label="Toqqi, início"] img').exists()).toBe(true)
    await botao(w).trigger('click')
    expect(localStorage.getItem(CHAVE_MENU_RECOLHIDO)).toBeNull()
    expect(botao(w).attributes('aria-expanded')).toBe('true')
  })

  it('abre recolhido quando foi assim que a pessoa deixou', async () => {
    localStorage.setItem(CHAVE_MENU_RECOLHIDO, '1')
    recarregarMenuLateral()
    const w = await montar(true)
    expect(botao(w).attributes('aria-expanded')).toBe('false')
  })

  it('a gaveta do celular ignora a preferência: sempre aberta e sem o botão', async () => {
    useMenuLateral().definir(true)
    const w = await montar(false)
    expect(botao(w).exists()).toBe(false)
    const respostas = w.findAll('a').find((a) => a.text().includes('Respostas'))!
    expect(respostas.find('span').classes()).not.toContain('sr-only')
  })

  it('sem armazenamento no navegador: funciona do mesmo jeito, só não lembra', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    const w = await montar(true)
    await botao(w).trigger('click')
    expect(botao(w).attributes('aria-expanded')).toBe('false')
  })
})
