import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import ImportacaoView from '@/modulos/importacao/ImportacaoView.vue'
import { apiFalsa } from './apiFalsa'

let router: Router

async function abrir(caminho: string): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/contatos/importar', name: 'importar', component: ImportacaoView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return w
}

const botao = (w: VueWrapper, texto: string) => w.findAll('button').find((b) => b.text().includes(texto))!

beforeEach(() => {
  setActivePinia(createPinia())
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'gestor', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes: ['contatos.ver', 'importacao.usar', 'respostas.ver'],
    },
    false,
  )
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('importar respostas antigas', () => {
  it('?tipo=respostas já começa em "Respostas antigas", com as instruções e o modelo certos', async () => {
    const { chamadas } = apiFalsa({ 'GET /importacao/modelo': () => new Response('email;data;nota\n', { status: 200, headers: { 'Content-Type': 'text/csv' } }) })
    const w = await abrir('/contatos/importar?tipo=respostas')
    expect((w.get('input[name="tipo-importacao"][value="respostas"]').element as HTMLInputElement).checked).toBe(true)
    expect(w.text()).toContain('Importar respostas antigas')
    expect(w.text()).toContain('nota de 0 a 10')
    // O link de voltar leva para Respostas (de onde a pessoa veio).
    expect(w.get('a').attributes('href')).toBe('/respostas')
    await botao(w, 'Baixar planilha modelo').trigger('click')
    await flushPromises()
    expect(chamadas.find((c) => c.caminho === '/importacao/modelo')!.url.searchParams.get('tipo')).toBe('respostas')
  })

  it('trocar para Contatos muda o texto e o endereço', async () => {
    apiFalsa({ 'GET /cadastros/grupos': () => [] })
    const w = await abrir('/contatos/importar?tipo=respostas')
    await w.get('input[name="tipo-importacao"][value="contatos"]').setValue(true)
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({})
    expect(w.text()).toContain('e-mail ou o telefone')
    expect(w.text()).not.toContain('nota de 0 a 10')
  })

  it('a análise vai com tipo=respostas; a conferência leva só o mapeamento e "atualizar"', async () => {
    const { chamadas } = apiFalsa({
      'POST /importacao/analisar': () => ({
        id: 'a1',
        tipo: 'respostas',
        colunas: ['E-mail do cliente', 'Data', 'NPS', 'Obs'],
        mapeamento_sugerido: { 'E-mail do cliente': 'email', Data: 'data', NPS: 'nota', Obs: null },
        total_linhas: 2,
        amostra: [{ linha: 2, valores: { 'E-mail do cliente': 'a@b.com', Data: '01/09/2026', NPS: '9', Obs: '' } }],
        campos: [
          { chave: 'email', rotulo: 'E-mail', obrigatorio: true },
          { chave: 'data', rotulo: 'Data da resposta', obrigatorio: true },
          { chave: 'nota', rotulo: 'Nota (0 a 10)', obrigatorio: true },
          { chave: 'comentario', rotulo: 'Comentário', obrigatorio: false },
        ],
      }),
      'POST /importacao/:id/conferir': () => ({ prontas: 2, novos: 2, atualizados: 0, com_problema: 0, problemas: [] }),
    })
    const w = await abrir('/contatos/importar?tipo=respostas')
    await botao(w, 'Já tenho minha planilha').trigger('click')
    const entrada = w.get('input[type="file"]')
    Object.defineProperty(entrada.element, 'files', { value: [new File(['email;data;nota'], 'antigas.csv', { type: 'text/csv' })] })
    await entrada.trigger('change')
    await botao(w, 'Continuar').trigger('click')
    await flushPromises()

    const analise = chamadas.find((c) => c.caminho === '/importacao/analisar')!
    expect((analise.corpo as FormData).get('tipo')).toBe('respostas')
    // Sem "E-mail ou telefone" nem "Reconhecer a mesma pessoa": isso é de contatos.
    expect(w.text()).not.toContain('E-mail ou telefone')
    expect(w.text()).not.toContain('Reconhecer a mesma pessoa')
    expect(w.text()).toContain('Atualizar as que já existem')

    await botao(w, 'Conferir').trigger('click')
    await flushPromises()
    expect(chamadas.find((c) => c.caminho === '/importacao/a1/conferir')!.corpo).toEqual({
      mapeamento: { 'E-mail do cliente': 'email', Data: 'data', NPS: 'nota' },
      atualizar_existentes: true,
    })
    expect(w.text()).toContain('Respostas novas')
  })
})
