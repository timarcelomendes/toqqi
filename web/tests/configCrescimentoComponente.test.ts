// Etapa 5c com a API simulada: Configurações › Crescimento (ligar o convite, textos com "Inserir" variáveis, prévia do
// cartão como na pesquisa e do balão do WhatsApp, salvar, só leitura) e a aba nova em Configurações.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { ConfigCrescimento } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import ConfigCrescimentoView from '@/modulos/configuracoes/ConfigCrescimentoView.vue'
import NavConfiguracoes from '@/modulos/configuracoes/NavConfiguracoes.vue'
import { apiFalsa, erro422 } from './apiFalsa'

const CONFIG: ConfigCrescimento = {
  indicacoes_ativas: false,
  titulo_convite: 'Que bom que você gostou, {nome}!',
  texto_convite: 'Conhece outra empresa que ganharia com a {empresa}? Indique e a gente entra em contato com cuidado.',
  recompensa: 'Se virar cliente, você ganha 10% no próximo pedido.',
  texto_oferta: 'Olá, {nome}! Aqui é {representante}, da {empresa}. Preparei uma condição especial para a {empresa_cliente}.',
}

function entrar(permissoes: string[]) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana Paula Ribeiro', email: 'ana@sol.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Distribuidora Sol', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

async function abrir(componente = ConfigCrescimentoView): Promise<VueWrapper> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/configuracoes/crescimento', component: componente },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push('/configuracoes/crescimento')
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
function campo(w: VueWrapper, rotulo: string) {
  const label = w.findAll('label').find((l) => t(l.text()) === rotulo)
  if (!label) throw new Error(`Sem o campo "${rotulo}"`)
  return w.get<HTMLTextAreaElement | HTMLInputElement>(`[id="${label.attributes('for')}"]`)
}

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  avisos.splice(0)
})
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('Configurações › Crescimento', () => {
  it('mostra a prévia do cartão como na pesquisa (envio desligado) e o balão da oferta, com as variáveis trocadas', async () => {
    entrar(['configuracoes.gerenciar', 'crescimento.ver'])
    apiFalsa({ 'GET /crescimento/configuracao': () => CONFIG })
    const w = await abrir()
    const cartao = w.get('[data-previa-convite] [data-cartao-indicacao]')
    expect(t(cartao.text())).toContain('Que bom que você gostou, Maria!')
    expect(t(cartao.text())).toContain('Conhece outra empresa que ganharia com a Distribuidora Sol?')
    expect(t(cartao.get('[data-recompensa]').text())).toBe('Se virar cliente, você ganha 10% no próximo pedido.')
    expect(t(cartao.text())).toContain('Confirmo que essa pessoa aceita receber um contato de Distribuidora Sol.')
    // Exemplo: sem formulário próprio (a página já é um formulário), campos e envio desligados
    expect(cartao.find('form').exists()).toBe(false)
    expect(cartao.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(cartao.get('input[type="text"]').attributes('disabled')).toBeDefined()
    expect(cartao.find('[data-aviso-exemplo]').exists()).toBe(true)
    expect(t(w.get('[data-previa-whatsapp]').text())).toContain(
      'Olá, Maria! Aqui é Ana, da Distribuidora Sol. Preparei uma condição especial para a Mercado Bom Preço.',
    )
  })

  it('"Inserir" põe a variável onde está o cursor e a prévia acompanha', async () => {
    entrar(['configuracoes.gerenciar'])
    apiFalsa({ 'GET /crescimento/configuracao': () => ({ ...CONFIG, texto_oferta: 'Oi, {nome}.' }) })
    const w = await abrir()
    const oferta = campo(w, 'Texto da oferta')
    oferta.element.setSelectionRange(oferta.element.value.length, oferta.element.value.length)
    const grupo = w.get('[aria-label="Inserir informação em Texto da oferta"]')
    expect(grupo.findAll('button').map((b) => b.text())).toEqual(['{nome}', '{empresa}', '{empresa_cliente}', '{representante}'])
    await grupo.findAll('button')[3]!.trigger('click')
    expect(oferta.element.value).toBe('Oi, {nome}.{representante}')
    expect(t(w.get('[data-previa-whatsapp]').text())).toContain('Oi, Maria.Ana')
    // Convite e recompensa: só {nome} e {empresa}
    expect(w.get('[aria-label="Inserir informação em Título"]').findAll('button').map((b) => b.text())).toEqual(['{nome}', '{empresa}'])
    expect(w.get('[aria-label="Inserir informação em Recompensa (opcional)"]').findAll('button').map((b) => b.text())).toEqual(['{nome}', '{empresa}'])
  })

  it('confere os campos antes de salvar; salva com a recompensa vazia como null e liga o convite', async () => {
    entrar(['configuracoes.gerenciar', 'crescimento.ver'])
    const { chamadas } = apiFalsa({
      'GET /crescimento/configuracao': () => CONFIG,
      'PUT /crescimento/configuracao': ({ corpo }) => corpo,
    })
    const w = await abrir()
    expect(w.get('[data-barra-fixa] button[type="submit"]').attributes('disabled')).toBeDefined()
    await w.get('[role="switch"]').trigger('click')
    await campo(w, 'Título').setValue('   ')
    await campo(w, 'Recompensa (opcional)').setValue('  ')
    await w.get('#form-config-crescimento').trigger('submit')
    await flushPromises()
    expect(t(w.text())).toContain('Escreva o título do convite.')
    expect(chamadas.filter((c) => c.metodo === 'PUT')).toHaveLength(0)

    await campo(w, 'Título').setValue('Que bom que você gostou!')
    await w.get('#form-config-crescimento').trigger('submit')
    await flushPromises()
    expect(chamadas.filter((c) => c.metodo === 'PUT')[0]!.corpo).toEqual({
      indicacoes_ativas: true,
      titulo_convite: 'Que bom que você gostou!',
      texto_convite: CONFIG.texto_convite,
      recompensa: null,
      texto_oferta: CONFIG.texto_oferta,
      depoimentos_ativos: false,
      link_avaliacao: null,
    })
    expect(avisos.map((a) => a.mensagem)).toContain('Convite de indicação ligado. Ele aparece para quem der nota alta nos próximos convites.')
    expect(w.find('[data-previa-convite] [data-recompensa]').exists()).toBe(false)
  })

  it('o erro da API aparece no campo', async () => {
    entrar(['configuracoes.gerenciar'])
    apiFalsa({
      'GET /crescimento/configuracao': () => CONFIG,
      'PUT /crescimento/configuracao': () => erro422('Confira os campos.', { texto_oferta: 'Texto grande demais.' }),
    })
    const w = await abrir()
    await campo(w, 'Texto da oferta').setValue('Outro texto, {nome}.')
    await w.get('#form-config-crescimento').trigger('submit')
    await flushPromises()
    expect(t(w.text())).toContain('Texto grande demais.')
    expect(campo(w, 'Texto da oferta').attributes('aria-invalid')).toBe('true')
  })

  it('quem só vê o Crescimento consulta, mas não muda (sem barra de salvar)', async () => {
    entrar(['crescimento.ver'])
    apiFalsa({ 'GET /crescimento/configuracao': () => CONFIG })
    const w = await abrir()
    expect(t(w.text())).toContain('Você pode ver estas configurações, mas só um administrador consegue mudar.')
    expect(w.get('#form-config-crescimento fieldset').attributes('disabled')).toBeDefined()
    expect(w.find('[data-barra-fixa]').exists()).toBe(false)
  })

  it('a aba Crescimento aparece em Configurações para quem gerencia ou vê o Crescimento', async () => {
    entrar(['crescimento.ver'])
    apiFalsa({})
    const w = await abrir(NavConfiguracoes)
    const link = w.findAll('a').find((a) => t(a.text()) === 'Crescimento')!
    expect(link.attributes('href')).toBe('/configuracoes/crescimento')
    expect(link.attributes('aria-current')).toBe('page')

    setActivePinia(createPinia())
    entrar(['envios.ver'])
    const w2 = await abrir(NavConfiguracoes)
    expect(w2.findAll('a').some((a) => t(a.text()) === 'Crescimento')).toBe(false)
  })
})
