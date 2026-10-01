import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { defineComponent, h } from 'vue'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import ConfigAcoesView from '@/modulos/configuracoes/ConfigAcoesView.vue'
import { apiFalsa } from './apiFalsa'

function entrar(permissoes: string[]) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'gestor', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

async function abrir(): Promise<VueWrapper> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/configuracoes/acoes', component: ConfigAcoesView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push('/configuracoes/acoes')
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const CONFIG = { prazo_detrator: 2, prazo_neutro: 5, prazo_promotor: 7, acao_promotor: false }

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
})

describe('configurações dos planos de ação', () => {
  it('sem configuracoes.gerenciar: vê os prazos, mas não muda', async () => {
    entrar(['acoes.ver'])
    apiFalsa({ 'GET /acoes/configuracao': () => CONFIG })
    const w = await abrir()
    expect((w.get('#prazo-prazo_detrator').element as HTMLInputElement).value).toBe('2')
    expect(w.get('fieldset').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('só um administrador consegue mudar')
    expect(w.text()).not.toContain('Salvar alterações')
    // A seção aparece no menu de Configurações.
    expect(w.get('nav[aria-label="Seções de configurações"]').text()).toContain('Planos de ação')
  })

  it('prazo fora de 1 a 90 não salva; certo, salva com números e a escolha dos promotores', async () => {
    entrar(['acoes.ver', 'configuracoes.gerenciar'])
    const { chamadas } = apiFalsa({
      'GET /acoes/configuracao': () => CONFIG,
      'PUT /acoes/configuracao': ({ corpo }) => corpo,
    })
    const w = await abrir()
    await w.get('#prazo-prazo_detrator').setValue('120')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(chamadas.some((c) => c.metodo === 'PUT')).toBe(false)
    expect(w.text()).toContain('Use um número de dias de 1 a 90.')

    await w.get('#prazo-prazo_detrator').setValue('3')
    await w.get('[role="switch"]').trigger('click')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'PUT')!.corpo).toEqual({ prazo_detrator: 3, prazo_neutro: 5, prazo_promotor: 7, acao_promotor: true })
    expect(avisos.at(-1)?.mensagem).toContain('salvas')
  })
})
