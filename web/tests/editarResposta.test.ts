// O cliente pode mudar a resposta (docs/api-editar-resposta.md) e a nota clicada no e-mail abre na pergunta 1: a
// pesquisa preenchida com a faixa, "Editar minha resposta" na tela final, a página pública (convite e link público com
// a chave) e a opção na aba Compartilhar.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import PublicoApp from '@/publico/PublicoApp.vue'
import AbaCompartilhar from '@/modulos/formularios/editor/AbaCompartilhar.vue'
import { TEMA_PADRAO, type FormularioPublico, type Pergunta } from '@/pesquisa/tipos'
import type { Formulario } from '@/api'
import { apiFalsa } from './apiFalsa'

const p = (id: string, tipo: Pergunta['tipo'], extra: Partial<Pergunta> = {}): Pergunta => ({ id, tipo, titulo: `Título ${id}`, obrigatoria: false, ...extra })
const formulario = (): FormularioPublico => ({
  nome: 'NPS',
  perguntas: [p('nota', 'nps'), p('porque', 'comentario', { titulo: 'Por quê?' })],
  tema: { ...TEMA_PADRAO, texto_botao: 'Enviar' },
  prefixo_imagens: 'https://api.toqqi.com/api/v1/publico/imagens/',
})
const daqui7Dias = () => new Date(Date.now() + 7 * 86_400_000).toISOString()
const diaMes = (iso: string) => new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', timeZone: 'America/Sao_Paulo' })

enableAutoUnmount(afterEach)
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

const marcada = (w: VueWrapper, v: number) => (w.get(`input[type="radio"][value="${v}"]`).element as HTMLInputElement).checked
async function seguir(w: VueWrapper) {
  await w.find('form').trigger('submit')
  await flushPromises()
}

describe('pesquisa: mudar a resposta', () => {
  it('abre preenchida, com a faixa no primeiro passo; a nota clicada no e-mail vale por cima', async () => {
    const w = mount(Pesquisa, {
      props: { formulario: formulario(), respostasIniciais: { nota: 3, porque: 'Atrasou' }, aviso: 'Você respondeu em 06/10. Pode mudar suas respostas até 13/10.', notaInicial: 8 },
    })
    await flushPromises()
    expect(w.get('[data-aviso-edicao]').text()).toBe('Você respondeu em 06/10. Pode mudar suas respostas até 13/10.')
    expect(marcada(w, 8)).toBe(true)
    await seguir(w)
    expect(w.find('[data-aviso-edicao]').exists()).toBe(false) // só no primeiro passo
    expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('Atrasou')
  })

  it('"Editar minha resposta" volta às perguntas com o que foi enviado; o próximo envio vai de novo', async () => {
    const ate = daqui7Dias()
    const enviar = vi.fn(async () => ({ titulo_final: 'Obrigado!', texto_final: '', edicao: { ate } }))
    const w = mount(Pesquisa, { props: { formulario: formulario(), enviar }, attachTo: document.body })
    await w.get('input[type="radio"][value="6"]').setValue(true)
    await seguir(w)
    await w.get('textarea').setValue('Demorou')
    await seguir(w)
    expect(enviar).toHaveBeenLastCalledWith({ nota: 6, porque: 'Demorou' })
    const bloco = w.get('[data-editar-resposta]')
    expect(bloco.text()).toContain(`Dá para mudar até ${diaMes(ate)}.`)
    await bloco.get('button').trigger('click')
    await flushPromises()
    expect(marcada(w, 6)).toBe(true)
    expect(w.get('[data-aviso-edicao]').text()).toBe(`Mude o que quiser e envie de novo. Dá para mudar até ${diaMes(ate)}.`)
    await w.get('input[type="radio"][value="9"]').setValue(true)
    await seguir(w)
    expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('Demorou')
    await seguir(w)
    expect(enviar).toHaveBeenCalledTimes(2)
    expect(enviar).toHaveBeenLastCalledWith({ nota: 9, porque: 'Demorou' })
    expect(w.find('[data-tela-final]').exists()).toBe(true)
  })

  it('sem edição, com o prazo vencido ou na prévia, não há o botão', async () => {
    for (const edicao of [null, { ate: new Date(Date.now() - 60_000).toISOString() }]) {
      const enviar = vi.fn(async () => ({ titulo_final: 'Obrigado!', texto_final: '', edicao }))
      const w = mount(Pesquisa, { props: { formulario: formulario(), enviar, notaInicial: 10 } })
      await seguir(w)
      await seguir(w)
      expect(w.find('[data-tela-final]').exists()).toBe(true)
      expect(w.find('[data-editar-resposta]').exists()).toBe(false)
    }
    const previa = mount(Pesquisa, { props: { formulario: formulario(), previa: true, notaInicial: 10 } })
    await seguir(previa)
    await seguir(previa)
    expect(previa.find('[data-editar-resposta]').exists()).toBe(false)
  })
})

describe('página pública', () => {
  afterEach(() => window.history.pushState({}, '', '/'))

  it('convite já respondido que ainda dá para mudar: abre preenchido, com a faixa, e envia ao mesmo convite', async () => {
    window.history.pushState({}, '', '/r/tok123?nota=10')
    const edicao = { ate: '2026-10-13T12:00:00-03:00', respondida_em: '2026-10-06T12:00:00-03:00', respostas: { nota: 3, porque: 'Atrasou' } }
    const { chamadas } = apiFalsa({
      'GET /publico/convites/:token': () => ({ formulario: formulario(), variaveis: { empresa: 'Sol' }, ja_respondido: true, edicao }),
      'POST /publico/convites/:token/responder': () => ({ titulo_final: 'Obrigado!', texto_final: '', edicao: { ate: edicao.ate } }),
    })
    const w = mount(PublicoApp, { attachTo: document.body })
    await flushPromises()
    expect(w.get('[data-aviso-edicao]').text()).toBe('Você respondeu em 06/10. Pode mudar suas respostas até 13/10.')
    expect(marcada(w, 10)).toBe(true) // a nota clicada de novo no e-mail
    await seguir(w)
    await seguir(w)
    expect(chamadas.find((c) => c.metodo === 'POST')!.corpo).toEqual({ respostas: { nota: 10, porque: 'Atrasou' } })
  })

  it('convite já respondido sem edição: "Você já respondeu esta pesquisa"', async () => {
    window.history.pushState({}, '', '/r/tok123')
    apiFalsa({ 'GET /publico/convites/:token': () => ({ formulario: formulario(), variaveis: {}, ja_respondido: true, edicao: null }) })
    const w = mount(PublicoApp, { attachTo: document.body })
    await flushPromises()
    expect(w.text()).toContain('Você já respondeu esta pesquisa')
    expect(w.find('form').exists()).toBe(false)
  })

  it('link público: o envio guarda a chave e a mudança vai para /editar com ela', async () => {
    window.history.pushState({}, '', '/f/abc12345')
    const ate = daqui7Dias()
    const { chamadas } = apiFalsa({
      'GET /publico/formularios/:codigo': () => ({ formulario: formulario(), variaveis: {} }),
      'POST /publico/formularios/:codigo/responder': () => new Response(JSON.stringify({ titulo_final: 'Obrigado!', texto_final: '', edicao: { chave: '41.segredo', ate } }), { status: 201 }),
      'POST /publico/formularios/:codigo/editar': () => ({ titulo_final: 'Obrigado!', texto_final: '', edicao: { chave: '41.segredo', ate } }),
    })
    const w = mount(PublicoApp, { attachTo: document.body })
    await flushPromises()
    await w.get('input[type="radio"][value="4"]').setValue(true)
    await seguir(w)
    await seguir(w)
    await w.get('[data-editar-resposta] button').trigger('click')
    await flushPromises()
    await w.get('input[type="radio"][value="8"]').setValue(true)
    await seguir(w)
    await seguir(w)
    const editar = chamadas.find((c) => c.caminho === '/publico/formularios/abc12345/editar')!
    expect(editar.corpo).toEqual({ chave: '41.segredo', respostas: { nota: 8 } })
    expect(chamadas.filter((c) => c.caminho.endsWith('/responder'))).toHaveLength(1)
  })
})

describe('editor: aba Compartilhar', () => {
  beforeEach(() => vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText: vi.fn() } }))

  it('"O cliente pode mudar a resposta" salva na hora', async () => {
    const { chamadas } = apiFalsa({ 'PATCH /formularios/:id': () => ({ id: 5, permite_editar: true, atualizado_em: '2026-10-07T00:00:00Z' }) })
    const form = { id: 5, nome: 'NPS', publico: true, codigo_publico: 'abc12345', ativo: true, permite_editar: false, tema: {} } as unknown as Formulario
    const w = mount(AbaCompartilhar, { props: { formulario: form, podeEditar: true, alterado: false }, attachTo: document.body })
    await flushPromises()
    const secao = w.get('[data-secao-edicao]')
    expect(secao.text()).toContain('Até 7 dias depois de responder')
    await secao.get('[role="switch"]').trigger('click')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'PATCH')!.corpo).toEqual({ permite_editar: true })
    expect(w.emitted('atualizado')![0]![0]).toMatchObject({ permite_editar: true })
  })
})
