// Etapa 5c: o cartão de indicação na tela final da pesquisa (envio, validação, limite de 3, erros, "Indicar outra
// pessoa"), a página pública /r/:token com a API simulada e o cartão de exemplo na pré-visualização do editor.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Pergunta, Tema } from '@/api/tipos'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import { TEMA_PADRAO, type ConviteIndicacao, type DadosIndicacao, type FormularioPublico } from '@/pesquisa/tipos'
import PublicoApp from '@/publico/PublicoApp.vue'
import PreVisualizacao from '@/modulos/formularios/editor/PreVisualizacao.vue'
import { useSessaoStore } from '@/stores/sessao'
import { apiFalsa, erro422 } from './apiFalsa'

const CONVITE: ConviteIndicacao = {
  titulo: 'Que bom que você gostou!',
  texto: 'Conhece outra empresa que ganharia com a Distribuidora Sol? Indique e a gente entra em contato com cuidado.',
  recompensa: 'Se a indicação virar cliente, você ganha 10% no próximo pedido.',
}
const PERGUNTAS: Pergunta[] = [{ id: 'nota', tipo: 'nps', titulo: 'Recomendaria a {empresa}?', obrigatoria: true }]
const formulario = (perguntas: Pergunta[] = PERGUNTAS): FormularioPublico => ({ nome: 'NPS', perguntas, tema: { ...TEMA_PADRAO } })
const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

type Indicar = (d: DadosIndicacao) => Promise<string | void>

/** A pesquisa com nota 10 já marcada, enviada: a tela final com (ou sem) o cartão. */
async function terminar(opcoes: { indicacao?: ConviteIndicacao | null; indicar?: Indicar } = {}) {
  const enviar = vi.fn(async () => ({ titulo_final: 'Obrigado!', texto_final: 'Valeu.', indicacao: opcoes.indicacao === undefined ? CONVITE : opcoes.indicacao }))
  const w = mount(Pesquisa, {
    props: { formulario: formulario(), variaveis: { empresa: 'Distribuidora Sol', nome: 'Ana' }, notaInicial: 10, enviar, indicar: opcoes.indicar },
    attachTo: document.body,
  })
  await flushPromises()
  await w.find('form').trigger('submit')
  await flushPromises()
  return w
}

function campo(w: VueWrapper, rotulo: string) {
  const label = w.findAll('[data-cartao-indicacao] label').find((l) => t(l.text()).startsWith(rotulo))
  if (!label) throw new Error(`Sem o campo "${rotulo}"`)
  return label.attributes('for') ? w.get(`[id="${label.attributes('for')}"]`) : label.get('input')
}
async function preencher(w: VueWrapper, dados: { nome?: string; telefone?: string; email?: string; confirmo?: boolean } = {}) {
  if (dados.nome !== undefined) await campo(w, 'Nome de quem você indica').setValue(dados.nome)
  if (dados.telefone !== undefined) await campo(w, 'WhatsApp ou telefone').setValue(dados.telefone)
  if (dados.email !== undefined) await campo(w, 'E-mail').setValue(dados.email)
  if (dados.confirmo) await campo(w, 'Confirmo que essa pessoa aceita').setValue(true)
}
const enviarCartao = async (w: VueWrapper) => {
  await w.get('[data-cartao-indicacao] form').trigger('submit')
  await flushPromises()
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('cartão de indicação na tela final', () => {
  it('aparece com o título, o texto e a recompensa só quando a API manda `indicacao`', async () => {
    const w = await terminar({ indicar: vi.fn() })
    const cartao = w.get('[data-cartao-indicacao]')
    expect(t(cartao.text())).toContain('Que bom que você gostou!')
    expect(t(cartao.text())).toContain('Conhece outra empresa que ganharia com a Distribuidora Sol?')
    expect(t(cartao.get('[data-recompensa]').text())).toBe(CONVITE.recompensa)
    expect(t(cartao.text())).toContain('Confirmo que essa pessoa aceita receber um contato de Distribuidora Sol.')
    // "Pode dizer que fui eu que indiquei" já vem marcado; a confirmação, não
    expect((campo(w, 'Pode dizer que fui eu que indiquei').element as HTMLInputElement).checked).toBe(true)
    expect((campo(w, 'Confirmo que essa pessoa aceita').element as HTMLInputElement).checked).toBe(false)

    const sem = await terminar({ indicacao: null, indicar: vi.fn() })
    expect(sem.find('[data-cartao-indicacao]').exists()).toBe(false)
    const formatoErrado = await terminar({ indicacao: { titulo: 3 } as unknown as ConviteIndicacao, indicar: vi.fn() })
    expect(formatoErrado.find('[data-cartao-indicacao]').exists()).toBe(false)
  })

  it('confere nome, telefone ou e-mail e a confirmação antes de enviar (e leva o foco ao primeiro erro)', async () => {
    const indicar = vi.fn<Indicar>()
    const w = await terminar({ indicar })
    await enviarCartao(w)
    const cartao = t(w.get('[data-cartao-indicacao]').text())
    expect(cartao).toContain('Informe o nome de quem você indica.')
    expect(cartao).toContain('Informe o WhatsApp ou o e-mail (pelo menos um dos dois).')
    expect(cartao).toContain('Marque a confirmação para enviar.')
    expect(indicar).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(campo(w, 'Nome de quem você indica').element)
    expect(campo(w, 'Nome de quem você indica').attributes('aria-invalid')).toBe('true')

    await preencher(w, { nome: 'Juliana Prado', telefone: '123', confirmo: true })
    await enviarCartao(w)
    expect(t(w.get('[data-cartao-indicacao]').text())).toContain('Informe DDD e número, ex.: (11) 91234-5678.')
    expect(indicar).not.toHaveBeenCalled()
  })

  it('envia o corpo do contrato, agradece e deixa "Indicar outra pessoa" até 3 vezes', async () => {
    const indicar = vi.fn<Indicar>(async () => 'Obrigado pela indicação!')
    const w = await terminar({ indicar })
    await preencher(w, { nome: ' Juliana Prado ', telefone: '11987654321', confirmo: true })
    // O telefone aparece formatado enquanto a pessoa digita
    expect((campo(w, 'WhatsApp ou telefone').element as HTMLInputElement).value).toBe('(11) 98765-4321')
    await campo(w, 'Pode dizer que fui eu que indiquei').setValue(false)
    await enviarCartao(w)
    expect(indicar).toHaveBeenCalledWith({
      nome: 'Juliana Prado',
      empresa: null,
      telefone: '11987654321',
      email: null,
      observacao: null,
      pode_identificar: false,
      confirmo: true,
    })
    const final = w.get('[data-indicacao-final]')
    expect(t(final.text())).toContain('Obrigado pela indicação!')
    expect(document.activeElement).toBe(final.element)

    for (const n of [2, 3]) {
      await w.findAll('button').find((b) => t(b.text()) === 'Indicar outra pessoa')!.trigger('click')
      await flushPromises()
      // O formulário volta limpo, com "Pode dizer..." marcado de novo
      expect((campo(w, 'Nome de quem você indica').element as HTMLInputElement).value).toBe('')
      expect((campo(w, 'Pode dizer que fui eu que indiquei').element as HTMLInputElement).checked).toBe(true)
      expect(document.activeElement).toBe(campo(w, 'Nome de quem você indica').element)
      await preencher(w, { nome: `Pessoa ${n}`, email: `p${n}@empresa.com.br`, confirmo: true })
      await enviarCartao(w)
    }
    expect(indicar).toHaveBeenCalledTimes(3)
    expect(indicar.mock.calls[2]![0]).toMatchObject({ nome: 'Pessoa 3', telefone: null, email: 'p3@empresa.com.br', pode_identificar: true })
    expect(w.findAll('button').some((b) => t(b.text()) === 'Indicar outra pessoa')).toBe(false)
    expect(t(w.get('[data-indicacao-final]').text())).toContain('Você fez 3 indicações, o máximo por pesquisa.')
  })

  it('409 de limite mostra a mensagem da API; 422 marca o campo; sem conexão, a mensagem geral', async () => {
    const limite = vi.fn<Indicar>(async () => {
      throw { codigo: 'limite_indicacoes', mensagem: 'Você já fez 3 indicações. Obrigado!' }
    })
    const w = await terminar({ indicar: limite })
    await preencher(w, { nome: 'Juliana', email: 'j@x.com.br', confirmo: true })
    await enviarCartao(w)
    expect(t(w.get('[data-indicacao-final]').text())).toBe('Você já fez 3 indicações. Obrigado!')
    expect(w.find('[data-cartao-indicacao] form').exists()).toBe(false)

    const campos = vi.fn<Indicar>(async () => {
      throw { mensagem: 'Confira os campos.', campos: { email: 'E-mail inválido.' } }
    })
    const w2 = await terminar({ indicar: campos })
    await preencher(w2, { nome: 'Juliana', email: 'j@x.com.br', confirmo: true })
    await enviarCartao(w2)
    expect(t(w2.get('[data-cartao-indicacao]').text())).toContain('E-mail inválido.')
    expect(campo(w2, 'E-mail').attributes('aria-invalid')).toBe('true')

    const rede = vi.fn<Indicar>(async () => {
      throw { mensagem: 'Sem conexão no momento. Confira sua internet e tente de novo.' }
    })
    const w3 = await terminar({ indicar: rede })
    await preencher(w3, { nome: 'Juliana', email: 'j@x.com.br', confirmo: true })
    await enviarCartao(w3)
    expect(w3.get('[data-cartao-indicacao] [role="alert"]').text()).toBe('Sem conexão no momento. Confira sua internet e tente de novo.')
    // Os dados continuam para tentar de novo
    expect((campo(w3, 'Nome de quem você indica').element as HTMLInputElement).value).toBe('Juliana')
  })

  it('409 de indicação indisponível encerra o cartão como o limite: a mensagem da API, sem o formulário', async () => {
    const indisponivel = vi.fn<Indicar>(async () => {
      throw { codigo: 'indicacao_indisponivel', mensagem: 'Esta pesquisa não aceita indicações.' }
    })
    const w = await terminar({ indicar: indisponivel })
    await preencher(w, { nome: 'Juliana', email: 'j@x.com.br', confirmo: true })
    await enviarCartao(w)
    const final = w.get('[data-indicacao-final]')
    expect(t(final.text())).toBe('Esta pesquisa não aceita indicações.')
    expect(document.activeElement).toBe(final.element)
    expect(w.find('[data-cartao-indicacao] form').exists()).toBe(false)
    expect(w.find('[data-cartao-indicacao] [role="alert"]').exists()).toBe(false)
    expect(w.findAll('[data-cartao-indicacao] button').some((b) => t(b.text()) === 'Indicar outra pessoa')).toBe(false)

    // Sem mensagem da API, um texto padrão
    const semMensagem = await terminar({
      indicar: vi.fn<Indicar>(async () => {
        throw { codigo: 'indicacao_indisponivel' }
      }),
    })
    await preencher(semMensagem, { nome: 'Juliana', email: 'j@x.com.br', confirmo: true })
    await enviarCartao(semMensagem)
    expect(t(semMensagem.get('[data-indicacao-final]').text())).toBe('Esta pesquisa não aceita mais indicações.')
  })

  it('textos do convite e do que a pessoa digita são só texto (nada de HTML)', async () => {
    const w = await terminar({ indicacao: { titulo: '<img src=x onerror=alert(1)>', texto: '<b>oi</b>', recompensa: null }, indicar: vi.fn() })
    const cartao = w.get('[data-cartao-indicacao]')
    expect(cartao.find('img').exists()).toBe(false)
    expect(cartao.find('b').exists()).toBe(false)
    expect(cartao.text()).toContain('<b>oi</b>')
    expect(cartao.find('[data-recompensa]').exists()).toBe(false)
  })
})

describe('página pública /r/:token', () => {
  beforeEach(() => window.history.pushState({}, '', '/r/tok123'))
  afterEach(() => window.history.pushState({}, '', '/'))

  it('responde, mostra o cartão e manda a indicação para o convite certo', async () => {
    const { chamadas } = apiFalsa({
      'GET /publico/convites/:token': () => ({ formulario: formulario(), variaveis: { empresa: 'Distribuidora Sol', nome: 'Ana' } }),
      'POST /publico/convites/:token/responder': () => ({ titulo_final: 'Obrigado!', texto_final: '', indicacao: CONVITE }),
      'POST /publico/convites/:token/indicacoes': () => new Response(JSON.stringify({ mensagem: 'Obrigado pela indicação!' }), { status: 201 }),
    })
    const w = mount(PublicoApp, { attachTo: document.body })
    await flushPromises()
    await w.get('input[type="radio"][value="10"]').setValue(true)
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(chamadas.find((c) => c.caminho === '/publico/convites/tok123/responder')!.corpo).toEqual({ respostas: { nota: 10 } })
    await preencher(w, { nome: 'Juliana Prado', email: 'juliana@bela.com.br', confirmo: true })
    await enviarCartao(w)
    const pedido = chamadas.find((c) => c.metodo === 'POST' && c.caminho === '/publico/convites/tok123/indicacoes')!
    expect(pedido.corpo).toEqual({ nome: 'Juliana Prado', empresa: null, telefone: null, email: 'juliana@bela.com.br', observacao: null, pode_identificar: true, confirmo: true })
    expect(t(w.get('[data-indicacao-final]').text())).toContain('Obrigado pela indicação!')
  })

  it('a 4ª indicação (409) e os erros da API chegam ao cartão', async () => {
    apiFalsa({
      'GET /publico/convites/:token': () => ({ formulario: formulario(), variaveis: { empresa: 'Sol' } }),
      'POST /publico/convites/:token/responder': () => ({ titulo_final: 'Obrigado!', texto_final: '', indicacao: CONVITE }),
      'POST /publico/convites/:token/indicacoes': () =>
        new Response(JSON.stringify({ erro: { codigo: 'limite_indicacoes', mensagem: 'Você já fez 3 indicações. Obrigado!' } }), { status: 409 }),
    })
    const w = mount(PublicoApp, { attachTo: document.body })
    await flushPromises()
    await w.get('input[type="radio"][value="9"]').setValue(true)
    await w.find('form').trigger('submit')
    await flushPromises()
    await preencher(w, { nome: 'Juliana Prado', telefone: '(11) 98765-4321', confirmo: true })
    await enviarCartao(w)
    expect(t(w.get('[data-indicacao-final]').text())).toBe('Você já fez 3 indicações. Obrigado!')
  })

  it('409 indicacao_indisponivel da API (ex.: indicações desligadas depois da resposta) encerra o cartão', async () => {
    apiFalsa({
      'GET /publico/convites/:token': () => ({ formulario: formulario(), variaveis: { empresa: 'Sol' } }),
      'POST /publico/convites/:token/responder': () => ({ titulo_final: 'Obrigado!', texto_final: '', indicacao: CONVITE }),
      'POST /publico/convites/:token/indicacoes': () =>
        new Response(JSON.stringify({ erro: { codigo: 'indicacao_indisponivel', mensagem: 'Esta pesquisa não aceita indicações.' } }), { status: 409 }),
    })
    const w = mount(PublicoApp, { attachTo: document.body })
    await flushPromises()
    await w.get('input[type="radio"][value="10"]').setValue(true)
    await w.find('form').trigger('submit')
    await flushPromises()
    await preencher(w, { nome: 'Juliana Prado', telefone: '(11) 98765-4321', confirmo: true })
    await enviarCartao(w)
    expect(t(w.get('[data-indicacao-final]').text())).toBe('Esta pesquisa não aceita indicações.')
    expect(w.find('[data-cartao-indicacao] form').exists()).toBe(false)
  })

  it('422 da API marca o campo do cartão', async () => {
    apiFalsa({
      'GET /publico/convites/:token': () => ({ formulario: formulario(), variaveis: { empresa: 'Sol' } }),
      'POST /publico/convites/:token/responder': () => ({ titulo_final: 'Obrigado!', texto_final: '', indicacao: CONVITE }),
      'POST /publico/convites/:token/indicacoes': () => erro422('Confira os campos.', { telefone: 'Telefone inválido.' }),
    })
    const w = mount(PublicoApp, { attachTo: document.body })
    await flushPromises()
    await w.get('input[type="radio"][value="10"]').setValue(true)
    await w.find('form').trigger('submit')
    await flushPromises()
    await preencher(w, { nome: 'Juliana Prado', telefone: '(11) 98765-4321', confirmo: true })
    await enviarCartao(w)
    expect(t(w.get('[data-cartao-indicacao]').text())).toContain('Telefone inválido.')
  })
})

describe('pré-visualização do editor', () => {
  const TEMA = { ...TEMA_PADRAO } as Tema
  const CONFIG = { indicacoes_ativas: true, titulo_convite: 'Gostou, {nome}?', texto_convite: 'Indique alguém para a {empresa}.', recompensa: null, texto_oferta: 'x' }

  async function montar(permissoes: string[], config = CONFIG) {
    setActivePinia(createPinia())
    const sessao = useSessaoStore()
    sessao.permissoes = permissoes
    sessao.conta = { id: 1, nome: 'Distribuidora Sol', logo_url: null } as never
    const api = apiFalsa({ 'GET /crescimento/configuracao': () => config })
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
    const w = mount(PreVisualizacao, {
      props: { nome: 'NPS', perguntas: PERGUNTAS, tema: TEMA, nomeEmpresa: 'Distribuidora Sol' },
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()
    return { w, api }
  }
  async function responder(w: VueWrapper, nota: number) {
    await w.get(`input[type="radio"][value="${nota}"]`).setValue(true)
    await w.find('form').trigger('submit')
    await flushPromises()
  }

  it('com nota de promotor, o cartão aparece como exemplo (envio desligado), com os textos de Configurações › Crescimento', async () => {
    const { w, api } = await montar(['formularios.editar', 'crescimento.ver'])
    expect(api.chamadas).toHaveLength(0)
    await responder(w, 10)
    expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['GET /crescimento/configuracao'])
    const cartao = w.get('[data-cartao-indicacao]')
    expect(t(cartao.text())).toContain('Gostou, Maria?')
    expect(t(cartao.text())).toContain('Indique alguém para a Distribuidora Sol.')
    expect(cartao.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(cartao.find('[data-aviso-exemplo]').exists()).toBe(true)
    // Recomeçar e terminar de novo não busca outra vez
    await w.findAll('button').find((b) => t(b.text()) === 'Ver de novo')!.trigger('click')
    await flushPromises()
    await responder(w, 9)
    expect(api.chamadas).toHaveLength(1)
    expect(w.find('[data-cartao-indicacao]').exists()).toBe(true)
  })

  it('nota baixa, indicações desligadas ou sem acesso ao Crescimento: sem cartão', async () => {
    const baixa = await montar(['formularios.editar', 'crescimento.ver'])
    await responder(baixa.w, 8)
    expect(baixa.w.find('[data-cartao-indicacao]').exists()).toBe(false)
    expect(baixa.api.chamadas).toHaveLength(0)

    const desligadas = await montar(['crescimento.ver'], { ...CONFIG, indicacoes_ativas: false })
    await responder(desligadas.w, 10)
    expect(desligadas.w.find('[data-cartao-indicacao]').exists()).toBe(false)

    const semAcesso = await montar(['formularios.editar'])
    await responder(semAcesso.w, 10)
    expect(semAcesso.w.find('[data-cartao-indicacao]').exists()).toBe(false)
    expect(semAcesso.api.chamadas).toHaveLength(0)
  })
})
