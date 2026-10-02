// Pré-visualização do editor de formulários: além da página, o convite por e-mail e a mensagem do WhatsApp com os
// textos de Configurações › Envios, o logo e os botões de nota do formulário (só para quem vê os envios).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Pergunta, Tema, TipoFormulario } from '@/api/tipos'
import PreVisualizacao from '@/modulos/formularios/editor/PreVisualizacao.vue'
import { useSessaoStore } from '@/stores/sessao'
import { apiFalsa } from './apiFalsa'

const CONFIG = {
  remetente_nome: 'Distribuidora Sol',
  responder_para: 'contato@sol.com.br',
  assunto_convite: 'Como foi com a {empresa}?',
  texto_convite: 'Olá, {nome}!\n\nConte como foi a experiência da {empresa_cliente}.',
  assunto_lembrete: 'Lembrete',
  texto_lembrete: 'Ainda dá tempo.',
  texto_whatsapp: 'Oi, {nome}! Responde rapidinho? {link}',
}

const TEMA = { cor: '#E8501E', logo_url: 'https://cdn.exemplo/logo-form.png' } as unknown as Tema
const PERGUNTAS = [{ id: 'a', tipo: 'nps', titulo: 'Recomendaria?', obrigatoria: true }] as Pergunta[]

async function montar(permissoes: string[], tipo: TipoFormulario = 'nps', rotas: Record<string, () => unknown> = { 'GET /envios/configuracao': () => CONFIG }) {
  setActivePinia(createPinia())
  const sessao = useSessaoStore()
  sessao.permissoes = permissoes
  sessao.conta = { id: 1, nome: 'Distribuidora Sol', logo_url: null } as never
  const api = apiFalsa(rotas)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
  const w = mount(PreVisualizacao, {
    props: { nome: 'Pesquisa NPS', perguntas: PERGUNTAS, tema: TEMA, nomeEmpresa: 'Distribuidora Sol', tipo },
    global: { plugins: [router] },
  })
  await flushPromises()
  return { w, api }
}

const t = (s: string) => s.replace(/\s+/g, ' ').trim()

describe('pré-visualização por canal no editor de formulários', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('abre na página; E-mail mostra o convite com os textos da conta, o logo e a escala de 0 a 10', async () => {
    const { w, api } = await montar(['formularios.editar', 'envios.ver', 'configuracoes.gerenciar'])
    expect(w.get('[data-canal="pagina"]').attributes('aria-checked')).toBe('true')
    expect(api.chamadas).toHaveLength(0) // as mensagens só são buscadas quando a pessoa escolhe E-mail ou WhatsApp
    await w.get('[data-canal="email"]').trigger('click')
    await flushPromises()
    expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['GET /envios/configuracao'])
    const email = t(w.get('[aria-label="Prévia do e-mail"]').text())
    expect(email).toContain('Distribuidora Sol via Toqqi')
    expect(email).toContain('Como foi com a Distribuidora Sol?')
    expect(email).toContain('Olá, Maria!')
    expect(email).toContain('Conte como foi a experiência da Mercado Bom Preço.')
    expect(w.get('[data-teste="logo"] img').attributes('src')).toBe('https://cdn.exemplo/logo-form.png')
    expect(w.findAll('[aria-label="Prévia do e-mail"] [data-cor]')).toHaveLength(11)
    expect(w.find('[data-editar-mensagens]').attributes('href')).toBe('/configuracoes/envios')
    // Voltar para a página e de novo para o e-mail não busca outra vez
    await w.get('[data-canal="pagina"]').trigger('click')
    await w.get('[data-canal="email"]').trigger('click')
    await flushPromises()
    expect(api.chamadas).toHaveLength(1)
  })

  it('formulário CSAT mostra as notas de 1 a 5 no e-mail', async () => {
    const { w } = await montar(['envios.ver'], 'csat')
    await w.get('[data-canal="email"]').trigger('click')
    await flushPromises()
    expect(w.findAll('[aria-label="Prévia do e-mail"] [data-cor]').map((b) => b.text())).toEqual(['1', '2', '3', '4', '5'])
    expect(w.find('[data-editar-mensagens]').exists()).toBe(false) // só quem altera as configurações
  })

  it('WhatsApp mostra a mensagem do botão com o link de exemplo destacado', async () => {
    const { w } = await montar(['envios.ver'])
    await w.get('[data-canal="whatsapp"]').trigger('click')
    await flushPromises()
    const balao = w.get('[data-previa-whatsapp]')
    expect(t(balao.text())).toContain('Oi, Maria! Responde rapidinho?')
    expect(balao.get('span.underline').text()).toBe(`${window.location.origin}/r/exemplo`)
    expect(w.find('[data-aviso-logo]').exists()).toBe(false)
  })

  it('sem acesso aos envios, só a página (sem as opções e sem buscar as mensagens)', async () => {
    const { w, api } = await montar(['formularios.editar'])
    expect(w.find('[data-canais-previa]').exists()).toBe(false)
    expect(api.chamadas).toHaveLength(0)
    expect(w.text()).toContain('Recomeçar')
  })

  it('falha ao buscar as mensagens mostra o erro e deixa tentar de novo', async () => {
    let falhar = true
    const { w } = await montar(['envios.ver'], 'nps', {
      'GET /envios/configuracao': () =>
        falhar
          ? new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Serviço fora do ar.', campos: {} } }), { status: 503 })
          : CONFIG,
    })
    await w.get('[data-canal="email"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-previa-canal]').text()).toContain('Tentar de novo')
    falhar = false
    const tentar = w.findAll('[data-previa-canal] button').find((b) => b.text() === 'Tentar de novo')!
    await tentar.trigger('click')
    await flushPromises()
    expect(w.find('[aria-label="Prévia do e-mail"]').exists()).toBe(true)
  })
})
