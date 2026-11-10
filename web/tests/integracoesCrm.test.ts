// Integrações › Pipedrive e HubSpot (a mesma tela, pela chave): passos de cada CRM (HubSpot: chave de serviço, já que
// desde 26/10/2026 não se criam aplicativos privados novos), conectar, a consulta do HubSpot e o catálogo abrindo os dois.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent, h } from 'vue'
import CatalogoConectores from '@/modulos/integracoes/CatalogoConectores.vue'
import SecaoCrm from '@/modulos/integracoes/SecaoCrm.vue'
import { apiFalsa } from './apiFalsa'

const texto = (el: Element | null | undefined) => (el?.textContent ?? '').replace(/\s+/g, ' ').trim()
const desligado = { conectado: false }
const todos = (extra: object = {}) => ({
  rdstation_crm: desligado, omie: desligado, bling: { disponivel: true, conectado: false },
  pipedrive: desligado, hubspot: desligado, ...extra,
})

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  document.body.innerHTML = ''
})

describe('Integrações › Pipedrive e HubSpot', () => {
  it('Pipedrive: passos com o caminho do token e conectar manda o token e a opção', async () => {
    const { chamadas } = apiFalsa({
      'GET /integracoes/conectores': () => todos(),
      'PUT /integracoes/conectores/pipedrive': () => ({ conectado: true, pesquisar_ao_ganhar: true, aviso_cadastrado: true }),
    })
    const w = mount(SecaoCrm, { props: { chave: 'pipedrive' }, attachTo: document.body })
    await flushPromises()
    const passos = w.findAll('[data-passos-crm="pipedrive"] > li').map((li) => texto(li.element))
    expect(passos[0]).toBe('No Pipedrive, abra Configurações › Preferências pessoais › API e copie o seu token de API pessoal.')
    await w.get('input[type="password"]').setValue('  tok_0123456789  ')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(chamadas.at(-1)!.corpo).toEqual({ token: 'tok_0123456789', pesquisar_ao_ganhar: true })
    expect(w.text()).toContain('Conectado')
    expect(w.text()).toContain('Sincronizar agora')
  })

  it('token curto: erro no campo, sem chamar a API', async () => {
    const { chamadas } = apiFalsa({ 'GET /integracoes/conectores': () => todos() })
    const w = mount(SecaoCrm, { props: { chave: 'hubspot' }, attachTo: document.body })
    await flushPromises()
    await w.get('form').trigger('submit')
    expect(w.text()).toContain('Cole a chave de serviço do HubSpot.')
    expect(chamadas.map((c) => c.metodo)).toEqual(['GET'])
  })

  it('HubSpot: passos da chave de serviço, com os três escopos, e a última consulta', async () => {
    apiFalsa({ 'GET /integracoes/conectores': () => todos() })
    const w = mount(SecaoCrm, { props: { chave: 'hubspot' }, attachTo: document.body })
    await flushPromises()
    const passos = texto(w.get('[data-passos-crm="hubspot"]').element)
    expect(passos).toContain('Development › Keys › Service keys')
    for (const escopo of ['crm.objects.contacts.read', 'crm.objects.companies.read', 'crm.objects.deals.read']) expect(passos).toContain(escopo)
    expect(w.text()).not.toContain('aplicativo privado novo')

    apiFalsa({ 'GET /integracoes/conectores': () => todos({ hubspot: { conectado: true, pesquisar_ao_ganhar: true, consultado_em: null } }) })
    const w2 = mount(SecaoCrm, { props: { chave: 'hubspot' }, attachTo: document.body })
    await flushPromises()
    expect(texto(w2.get('[data-consulta-hubspot]').element)).toBe('A primeira consulta sai em até 30 minutos.')
  })

  it('o catálogo abre o Pipedrive e o HubSpot (não estão mais "em breve")', async () => {
    apiFalsa({ 'GET /integracoes/conectores': () => todos({ hubspot: { conectado: true, pesquisar_ao_ganhar: false } }) })
    const roteador = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: defineComponent({ render: () => h('div') }) }] })
    const w = mount(CatalogoConectores, { attachTo: document.body, global: { plugins: [roteador] } })
    await flushPromises()
    const pd = w.get('[data-conector="pipedrive"]')
    expect(pd.attributes('disabled')).toBeUndefined()
    expect(pd.attributes('aria-label')).toBe('Pipedrive: conectar')
    expect(w.get('[data-conector="hubspot"]').attributes('aria-label')).toBe('HubSpot: gerenciar')
    await pd.trigger('click')
    await flushPromises()
    expect(document.querySelector('[data-secao-crm="pipedrive"]')).not.toBeNull()
  })
})
