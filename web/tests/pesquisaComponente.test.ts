import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import { TEMA_PADRAO, type FormularioPublico, type Pergunta } from '@/pesquisa/tipos'

const perguntas: Pergunta[] = [
  { id: 'nota', tipo: 'nps', titulo: 'Olá, {nome}! Recomendaria a {empresa}?', obrigatoria: true },
  { id: 'ruim', tipo: 'comentario', titulo: 'O que deu errado?', obrigatoria: true, condicao: { tipo: 'grupo', grupos: ['detrator'] } },
  { id: 'fim', tipo: 'sim_nao', titulo: 'Voltaria a comprar?', obrigatoria: false },
]
const formulario = (modo: 'uma_por_vez' | 'paginas' = 'uma_por_vez'): FormularioPublico => ({
  nome: 'Teste',
  perguntas,
  tema: { ...TEMA_PADRAO, modo, texto_botao: 'Mandar' },
})

afterEach(() => {
  vi.useRealTimers()
  document.body.innerHTML = ''
})

describe('Pesquisa (uma por vez)', () => {
  it('mostra variáveis, valida obrigatória e avança sozinho ao tocar na nota', async () => {
    vi.useFakeTimers()
    const w = mount(Pesquisa, { props: { formulario: formulario(), variaveis: { nome: '', empresa: 'Acme' } }, attachTo: document.body })
    await flushPromises()
    expect(w.text()).toContain('Olá! Recomendaria a Acme?')
    expect(w.text()).toContain('Pergunta 1 de 2')

    await w.find('form').trigger('submit')
    expect(w.text()).toContain('Escolha uma opção para continuar.')

    await w.find('fieldset').trigger('pointerdown')
    await w.find('input[type="radio"][value="3"]').setValue(true)
    // Detrator: a pergunta condicional aparece.
    expect(w.text()).toContain('Pergunta 1 de 3')
    vi.advanceTimersByTime(400)
    await flushPromises()
    expect(w.text()).toContain('O que deu errado?')
  })

  it('?nota=N abre na pergunta da nota, com ela marcada; segue e envia só o que está visível', async () => {
    const enviar = vi.fn(async () => ({ titulo_final: 'Valeu, {nome}!', texto_final: 'Até mais.' }))
    const w = mount(Pesquisa, { props: { formulario: formulario(), variaveis: { nome: 'Ana Lima' }, notaInicial: 10, enviar } })
    await flushPromises()
    expect(w.text()).toContain('Recomendaria')
    expect((w.get('input[type="radio"][value="10"]').element as HTMLInputElement).checked).toBe(true)
    expect(w.get('[data-dica-nota]').text()).toContain('Marcamos a nota 10')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('Voltaria a comprar?')
    expect(w.text()).toContain('Mandar')
    await w.findAll('input[type="radio"]')[0]!.setValue(true)
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(enviar).toHaveBeenCalledWith({ nota: 10, fim: true })
    expect(w.text()).toContain('Valeu, Ana!')
  })

  it('mostra erro de rede e mantém as respostas para tentar de novo', async () => {
    const enviar = vi.fn().mockRejectedValueOnce({ mensagem: 'Sem conexão.' }).mockResolvedValueOnce({ titulo_final: 'Ok', texto_final: '' })
    const w = mount(Pesquisa, { props: { formulario: formulario(), notaInicial: 9, enviar } })
    await flushPromises()
    await w.find('form').trigger('submit') // a nota (já marcada pelo link) → a próxima pergunta
    await flushPromises()
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('Sem conexão.')
    expect(w.text()).toContain('Tentar de novo')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(enviar).toHaveBeenCalledTimes(2)
    expect(w.text()).toContain('Ok')
  })

  it('erro 422 do servidor volta para a pergunta certa', async () => {
    const enviar = vi.fn().mockRejectedValueOnce({ mensagem: 'Confira', campos: { 'respostas.nota': 'Nota fora da faixa.' } })
    const w = mount(Pesquisa, { props: { formulario: formulario(), notaInicial: 9, enviar } })
    await flushPromises()
    await w.find('form').trigger('submit') // a nota (já marcada pelo link) → a próxima pergunta
    await flushPromises()
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('Nota fora da faixa.')
    expect(w.text()).toContain('Recomendaria')
  })

  it('teclas 1 e 0 marcam 10 no NPS', async () => {
    vi.useFakeTimers()
    const w = mount(Pesquisa, { props: { formulario: formulario() }, attachTo: document.body })
    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '1' }))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '0' }))
    await flushPromises()
    expect((w.find('input[type="radio"][value="10"]').element as HTMLInputElement).checked).toBe(true)
  })
})

it('com teclado (setas) não avança sozinho', async () => {
  vi.useFakeTimers()
  const w = mount(Pesquisa, { props: { formulario: formulario() }, attachTo: document.body })
  await flushPromises()
  await w.find('fieldset').trigger('keydown', { key: 'ArrowRight' })
  await w.find('input[type="radio"][value="9"]').setValue(true)
  vi.advanceTimersByTime(1000)
  await flushPromises()
  expect(w.text()).toContain('Recomendaria')
  await w.find('form').trigger('submit')
  expect(w.text()).toContain('Voltaria a comprar?')
})

describe('Pesquisa (páginas)', () => {
  it('mostra as perguntas da página juntas e a pré-visualização termina sem API', async () => {
    const w = mount(Pesquisa, { props: { formulario: formulario('paginas'), previa: true } })
    await flushPromises()
    expect(w.text()).toContain('Recomendaria')
    expect(w.text()).toContain('Voltaria a comprar?')
    await w.find('input[type="radio"][value="9"]').setValue(true)
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain(TEMA_PADRAO.titulo_final)
    expect(w.text()).toContain('Ver de novo')
  })
})
