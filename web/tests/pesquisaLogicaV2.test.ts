// Etapa 5l (docs/api-etapa-5l.md §5.2): a página pública segue o caminho da lógica. Uma por vez com pular, itens que
// aparecem e somem, conteúdo como passo, páginas ao vivo, progresso, ?nota= (com e sem obrigatória antes), final com
// html_final e botão, opções (embaralhar, lista suspensa, máximo), citações e envio só do caminho; e a prévia (finais,
// foco no item e "Reiniciar prévia").
import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import { FOCO_FINAL_PADRAO, TEMA_PADRAO, type Final, type FormularioPublico, type Grupo, type Pergunta, type Tema } from '@/pesquisa/tipos'

const PREFIXO = 'https://api.toqqi.com/api/v1/publico/imagens/'
const p = (id: string, tipo: Pergunta['tipo'], extra: Partial<Pergunta> = {}): Pergunta => ({ id, tipo, titulo: `Título ${id}`, obrigatoria: false, ...extra })
const g = (...condicoes: Grupo['condicoes']): Grupo => ({ juncao: 'todas', condicoes })
const formulario = (perguntas: Pergunta[], tema: Partial<Tema> = {}): FormularioPublico => ({
  nome: 'Teste',
  perguntas,
  tema: { ...TEMA_PADRAO, texto_botao: 'Mandar', ...tema },
  prefixo_imagens: PREFIXO,
})

enableAutoUnmount(afterEach)
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

/** O DOMPurify chega por import dinâmico: espera o HTML limpo ir para a tela. */
async function esperarHtml() {
  for (let i = 0; i < 5; i++) {
    await flushPromises()
    await new Promise((r) => setTimeout(r, 0))
  }
}

const titulo = (w: VueWrapper) => w.find('[data-titulo-pergunta]').text()
const contador = (w: VueWrapper) => w.find('[data-contador]').text()
const botoes = (w: VueWrapper) => w.findAll('button').map((b) => b.text())
const clicar = (w: VueWrapper, texto: string) => w.findAll('button').find((b) => b.text() === texto)!.trigger('click')
const enviarForm = async (w: VueWrapper) => {
  await w.get('form').trigger('submit')
  await flushPromises()
}

async function tocar(w: VueWrapper, seletor: string) {
  await w.find('fieldset').trigger('pointerdown')
  await w.get(seletor).setValue(true)
  vi.advanceTimersByTime(400)
  await flushPromises()
}

describe('uma por vez: o próximo item é o do caminho', () => {
  const comPular = [
    p('cliente', 'sim_nao', { titulo: 'É cliente?', logica: { pular: [{ id: 'r_aaaaaa', se: g({ fonte: 'cliente', op: 'igual', valor: false }), para: 'motivo' }] } }),
    p('nota', 'nps', { titulo: 'Recomendaria?' }),
    p('elogio', 'comentario', { titulo: 'O que mais gostou?', logica: { mostrar_se: g({ fonte: 'nota', op: 'grupo_e', valor: ['promotor'] }) } }),
    p('motivo', 'comentario', { titulo: 'Por que não?' }),
  ]

  it('pular manda direto para o destino; Voltar volta pelo caminho; o envio leva só o caminho', async () => {
    vi.useFakeTimers()
    const enviar = vi.fn(async () => ({ titulo_final: 'Obrigado', texto_final: '' }))
    const w = mount(Pesquisa, { props: { formulario: formulario(comPular), enviar }, attachTo: document.body })
    expect(titulo(w)).toContain('É cliente?')
    expect(contador(w)).toBe('Pergunta 1 de 3')
    // Responde "Sim" (a nota entra) e depois muda de ideia: com "Não", a nota sai do caminho.
    await tocar(w, 'input[type="radio"]')
    expect(titulo(w)).toContain('Recomendaria?')
    await clicar(w, 'Voltar')
    await w.findAll('input[type="radio"]')[1]!.trigger('pointerdown')
    await tocar(w, 'fieldset input[type="radio"]:not(:checked)')
    expect(titulo(w)).toContain('Por que não?')
    expect(contador(w)).toBe('Pergunta 2 de 2')
    expect(botoes(w)).toContain('Mandar')
    await clicar(w, 'Voltar')
    expect(titulo(w)).toContain('É cliente?')
    await enviarForm(w) // "Continuar" no 1º passo
    await w.get('textarea').setValue('Comprei em outro lugar')
    await enviarForm(w)
    expect(enviar).toHaveBeenCalledWith({ cliente: false, motivo: 'Comprei em outro lugar' })
  })

  it('itens aparecem e somem com a resposta (e o progresso acompanha o caminho)', async () => {
    vi.useFakeTimers()
    const w = mount(Pesquisa, { props: { formulario: formulario(comPular.slice(1)) }, attachTo: document.body })
    const barra = () => Number(w.get('[role="progressbar"]').attributes('aria-valuenow'))
    expect(contador(w)).toBe('Pergunta 1 de 2')
    expect(barra()).toBe(0)
    await w.find('fieldset').trigger('pointerdown')
    await w.get('input[value="10"]').setValue(true)
    expect(contador(w)).toBe('Pergunta 1 de 3')
    await w.get('input[value="3"]').setValue(true)
    expect(contador(w)).toBe('Pergunta 1 de 2')
    await w.get('input[value="9"]').setValue(true)
    vi.advanceTimersByTime(400)
    await flushPromises()
    expect(titulo(w)).toContain('O que mais gostou?')
    expect(barra()).toBe(33)
  })
})

describe('bloco de conteúdo: um passo próprio', () => {
  const itens = [
    p('intro', 'conteudo', { titulo: 'Interno', html: '<h2>Bem-vindo</h2><p>Leva <strong>1 minuto</strong>.</p><script>alert(1)</script>' }),
    p('nota', 'nps', { titulo: 'Recomendaria?' }),
    p('aviso', 'conteudo', { html: '<p>Obrigado por chegar até aqui.</p>' }),
  ]

  it('mostra o HTML limpo com "Continuar"; o nome interno não aparece; último do caminho mostra o botão de enviar', async () => {
    const enviar = vi.fn(async () => ({ titulo_final: 'Fim', texto_final: '' }))
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), enviar }, attachTo: document.body })
    await esperarHtml()
    const bloco = w.get('[data-conteudo] [data-bloco-html]')
    expect(bloco.element.innerHTML).toBe('<h2>Bem-vindo</h2><p>Leva <strong>1 minuto</strong>.</p>')
    expect(w.text()).not.toContain('Interno')
    expect(w.find('[data-contador]').exists()).toBe(false) // conteúdo não é pergunta
    expect(botoes(w)).toContain('Continuar')
    await enviarForm(w)
    expect(titulo(w)).toContain('Recomendaria?')
    await w.get('input[value="8"]').setValue(true)
    await enviarForm(w)
    await esperarHtml()
    expect(w.get('[data-conteudo]').text()).toBe('Obrigado por chegar até aqui.')
    expect(botoes(w)).toContain('Mandar')
    // o leitor de tela ouve o começo do texto do bloco
    expect(w.get('[aria-live="polite"]').text()).toBe('Obrigado por chegar até aqui.')
    await enviarForm(w)
    expect(enviar).toHaveBeenCalledWith({ nota: 8 })
  })
})

describe('páginas: o caminho agrupado pelas quebras, ao vivo', () => {
  it('itens aparecem na mesma página e "Próxima" pula a página sem item no caminho', async () => {
    const itens = [
      p('nota', 'nps'),
      p('ruim', 'comentario', { titulo: 'O que deu errado?', logica: { mostrar_se: g({ fonte: 'nota', op: 'menor_igual', valor: 6 }) } }),
      p('q1', 'quebra_pagina'),
      p('so_ruim', 'sim_nao', { titulo: 'Podemos ligar?', logica: { mostrar_se: g({ fonte: 'nota', op: 'menor_igual', valor: 6 }) } }),
      p('q2', 'quebra_pagina'),
      p('email', 'texto_curto', { titulo: 'Seu e-mail', formato: 'email' }),
    ]
    const w = mount(Pesquisa, { props: { formulario: formulario(itens, { modo: 'paginas' }) }, attachTo: document.body })
    expect(w.text()).toContain('Página 1 de 2')
    expect(w.text()).not.toContain('O que deu errado?')
    await w.get('input[value="3"]').setValue(true)
    expect(w.text()).toContain('O que deu errado?')
    expect(w.text()).toContain('Página 1 de 3')
    await w.get('input[value="10"]').setValue(true)
    expect(w.text()).not.toContain('O que deu errado?')
    await enviarForm(w)
    expect(w.text()).toContain('Seu e-mail')
    expect(w.text()).toContain('Página 2 de 2')
  })
})

describe('?nota= (a nota tocada no e-mail)', () => {
  it('abre na pergunta da nota, com ela marcada; o caminho segue a nota do link', async () => {
    const itens = [p('nota', 'nps'), p('ruim', 'comentario', { titulo: 'Conte mais', logica: { mostrar_se: g({ fonte: 'nota', op: 'menor_igual', valor: 6 }) } }), p('fim', 'sim_nao', { titulo: 'Voltaria?' })]
    const detrator = mount(Pesquisa, { props: { formulario: formulario(itens), notaInicial: 2 } })
    expect(titulo(detrator)).toContain('Título nota')
    expect((detrator.get('input[value="2"]').element as HTMLInputElement).checked).toBe(true)
    await enviarForm(detrator)
    expect(titulo(detrator)).toContain('Conte mais')
    const promotor = mount(Pesquisa, { props: { formulario: formulario(itens), notaInicial: 10 } })
    expect(titulo(promotor)).toContain('Título nota')
    await enviarForm(promotor)
    expect(titulo(promotor)).toContain('Voltaria?')
  })

  it('com itens antes da nota: começa no primeiro passo, e a nota já está marcada quando chega nela', async () => {
    const itens = [p('intro', 'conteudo', { html: '<p>Oi</p>' }), p('livre', 'texto_curto', { titulo: 'Apelido' }), p('pedido', 'texto_curto', { titulo: 'Número do pedido', obrigatoria: true }), p('nota', 'nps'), p('fim', 'comentario', { titulo: 'Algo mais?' })]
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), notaInicial: 9 }, attachTo: document.body })
    expect(w.find('[data-conteudo]').exists()).toBe(true)
    await enviarForm(w)
    expect(titulo(w)).toContain('Apelido')
    await enviarForm(w)
    expect(titulo(w)).toContain('Número do pedido')
    await enviarForm(w)
    expect(w.text()).toContain('Responda esta pergunta para continuar.')
    await w.get('input[type="text"]').setValue('123')
    await enviarForm(w)
    expect(titulo(w)).toContain('Título nota')
    expect((w.get('input[value="9"]').element as HTMLInputElement).checked).toBe(true)
  })
})

describe('final', () => {
  const itens = [p('nota', 'nps'), p('porque', 'comentario', { titulo: 'Por quê?' })]

  it('com html_final: título, HTML limpo (citação escapada) e o botão em nova aba', async () => {
    const enviar = vi.fn(async () => ({
      titulo_final: 'Valeu pela nota {{nota}}!',
      texto_final: '',
      final_id: 'f_prom01',
      html_final: '<p>Você disse: {{porque}}</p><img src="https://rastreador.com/x.png"><a href="https://g.page/x">Google</a>',
      botao_final: { texto: 'Avaliar no Google', url: 'https://g.page/r/abc' },
    }))
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), enviar, notaInicial: 10 }, attachTo: document.body })
    await enviarForm(w) // a nota (já marcada pelo link) → "Por quê?"
    await w.get('textarea').setValue('<b>ótimo</b> & rápido')
    await enviarForm(w)
    await esperarHtml()
    expect(enviar).toHaveBeenCalledWith({ nota: 10, porque: '<b>ótimo</b> & rápido' })
    expect(w.get('h1').text()).toBe('Valeu pela nota 10!')
    expect(w.get('[data-tela-final]').attributes('data-final')).toBe('f_prom01')
    const html = w.get('[data-html-final]').element.innerHTML
    expect(html).toContain('<p>Você disse: &lt;b&gt;ótimo&lt;/b&gt; &amp; rápido</p>')
    expect(html).not.toContain('rastreador')
    expect(html).toContain('target="_blank"')
    const botao = w.get('[data-botao-final]')
    expect(botao.attributes('href')).toBe('https://g.page/r/abc')
    expect(botao.attributes('target')).toBe('_blank')
    expect(botao.attributes('rel')).toBe('noopener noreferrer')
    expect(botao.text()).toContain('Avaliar no Google')
  })

  it('sem html_final: o texto do final como antes (e botão sem https não vira link)', async () => {
    const enviar = vi.fn(async () => ({ titulo_final: 'Obrigado!', texto_final: 'Até mais.', final_id: null, html_final: null, botao_final: { texto: 'X', url: 'javascript:alert(1)' } }))
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), enviar, notaInicial: 7 } })
    await enviarForm(w) // a nota → "Por quê?"
    await enviarForm(w)
    expect(w.get('h1').text()).toBe('Obrigado!')
    expect(w.text()).toContain('Até mais.')
    expect(w.find('[data-botao-final]').exists()).toBe(false)
    expect(w.find('[data-html-final]').exists()).toBe(false)
  })
})

describe('opções', () => {
  it('aleatorizar: embaralha uma vez e fica igual ao voltar; a resposta segue a ordem salva', async () => {
    const aleatorios = [0.1, 0.9, 0.5, 0.2, 0.7]
    vi.spyOn(Math, 'random').mockImplementation(() => aleatorios.shift() ?? 0.3)
    const itens = [p('m', 'escolha_multipla', { opcoes: ['A', 'B', 'C', 'D'], aleatorizar: true }), p('fim', 'comentario')]
    const enviar = vi.fn(async () => ({ titulo_final: 'Ok', texto_final: '' }))
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), enviar }, attachTo: document.body })
    const ordem = () => w.findAll('label span').map((s) => s.text())
    const primeira = ordem()
    expect([...primeira].sort()).toEqual(['A', 'B', 'C', 'D'])
    expect(primeira).not.toEqual(['A', 'B', 'C', 'D'])
    await w.findAll('input[type="checkbox"]')[0]!.setValue(true)
    await w.findAll('input[type="checkbox"]')[3]!.setValue(true)
    await enviarForm(w)
    await clicar(w, 'Voltar')
    expect(ordem()).toEqual(primeira)
    await enviarForm(w)
    await enviarForm(w)
    const marcadas = [primeira[0]!, primeira[3]!].sort()
    expect(enviar).toHaveBeenCalledWith({ m: marcadas })
  })

  it('lista suspensa: <select> com o título como rótulo', async () => {
    const itens = [p('u', 'escolha_unica', { titulo: 'Sua cidade', opcoes: ['Recife', 'Natal'], exibicao: 'lista' })]
    const enviar = vi.fn(async () => ({ titulo_final: 'Ok', texto_final: '' }))
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), enviar } })
    const lista = w.get('select[data-lista-opcoes]')
    expect(document.getElementById(lista.attributes('aria-labelledby')!)?.textContent ?? w.get(`#${lista.attributes('aria-labelledby')}`).text()).toContain('Sua cidade')
    expect(lista.findAll('option').map((o) => o.text())).toEqual(['Escolha uma opção', 'Recife', 'Natal'])
    await lista.setValue('Natal')
    await enviarForm(w)
    expect(enviar).toHaveBeenCalledWith({ u: 'Natal' })
  })

  it('máximo de opções: as outras ficam desligadas no limite, com aviso', async () => {
    const itens = [p('m', 'escolha_multipla', { opcoes: ['A', 'B', 'C'], max_selecoes: 2 })]
    const w = mount(Pesquisa, { props: { formulario: formulario(itens) } })
    expect(w.get('[data-dica-multipla]').text()).toBe('Escolha até 2 opções.')
    const caixas = () => w.findAll('input[type="checkbox"]')
    await caixas()[0]!.setValue(true)
    expect(caixas()[2]!.attributes('disabled')).toBeUndefined()
    await caixas()[1]!.setValue(true)
    expect(caixas()[2]!.attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Você pode escolher até 2 opções.')
    await caixas()[0]!.setValue(false)
    expect(caixas()[2]!.attributes('disabled')).toBeUndefined()
  })

  it('texto de exemplo (placeholder) no campo', () => {
    const w = mount(Pesquisa, { props: { formulario: formulario([p('t', 'texto_curto', { placeholder: 'Ex.: 12345' })]) } })
    expect(w.get('input[type="text"]').attributes('placeholder')).toBe('Ex.: 12345')
  })
})

describe('citações', () => {
  it('título cita a resposta anterior como texto; HTML do conteúdo cita escapado', async () => {
    const itens = [
      p('nome', 'texto_curto', { titulo: 'Como podemos te chamar?' }),
      p('nota', 'nps', { titulo: '{{nome}}, de 0 a 10, quanto recomendaria?' }),
      p('c', 'conteudo', { html: '<p>Obrigado, <strong>{{nome}}</strong>! Nota {{nota}}.</p>' }),
    ]
    const w = mount(Pesquisa, { props: { formulario: formulario(itens) }, attachTo: document.body })
    await w.get('input[type="text"]').setValue('<i>Ana</i>')
    await enviarForm(w)
    expect(titulo(w)).toContain('<i>Ana</i>, de 0 a 10, quanto recomendaria?')
    await w.get('input[value="9"]').setValue(true)
    await enviarForm(w)
    await esperarHtml()
    expect(w.get('[data-conteudo] [data-bloco-html]').element.innerHTML).toBe('<p>Obrigado, <strong>&lt;i&gt;Ana&lt;/i&gt;</strong>! Nota 9.</p>')
  })
})

describe('prévia (sem API)', () => {
  const itens = [
    p('nota', 'nps', { titulo: 'Recomendaria?' }),
    p('ruim', 'comentario', { titulo: 'O que melhorar?', logica: { mostrar_se: g({ fonte: 'nota', op: 'grupo_e', valor: ['detrator'] }) } }),
  ]
  const finais: Final[] = [
    { id: 'f_promot', nome: 'Promotores', titulo: 'Obrigado, {nome}!', html: '<p>Indique a {empresa}.</p>', botao: { texto: 'Avaliar', url: 'https://g.page/x' }, mostrar_se: g({ fonte: 'nota', op: 'grupo_e', valor: ['promotor'] }) },
  ]

  it('o final sai da lógica (com variáveis escapadas no HTML); sem final que valha, o do tema', async () => {
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), previa: true, finais, variaveis: { nome: 'Maria', empresa: 'A&B <Ltda>' } }, attachTo: document.body })
    await w.get('input[value="10"]').setValue(true)
    await enviarForm(w)
    await esperarHtml()
    expect(w.get('h1').text()).toBe('Obrigado, Maria!')
    expect(w.get('[data-html-final]').element.innerHTML).toBe('<p>Indique a A&amp;B &lt;Ltda&gt;.</p>')
    expect(w.get('[data-botao-final]').attributes('href')).toBe('https://g.page/x')
    await clicar(w, 'Ver de novo')
    await w.get('input[value="8"]').setValue(true)
    await enviarForm(w)
    expect(w.get('h1').text()).toBe(TEMA_PADRAO.titulo_final)
  })

  it('focoId abre no item; fora do caminho ele aparece com a faixa; "Reiniciar prévia" volta ao começo', async () => {
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), previa: true, focoId: 'ruim', motivoFoco: 'NPS é detrator' }, attachTo: document.body })
    expect(titulo(w)).toContain('O que melhorar?')
    expect(w.get('[data-faixa-foco]').text()).toBe('Na pesquisa, este item só aparece quando: NPS é detrator')
    await w.setProps({ focoId: 'nota' })
    expect(titulo(w)).toContain('Recomendaria?')
    expect(w.find('[data-faixa-foco]').exists()).toBe(false)
    await w.get('input[value="3"]').setValue(true)
    await w.setProps({ focoId: 'ruim' })
    expect(titulo(w)).toContain('O que melhorar?')
    expect(w.find('[data-faixa-foco]').exists()).toBe(false) // agora está no caminho
    await w.get('[data-reiniciar-previa]').trigger('click')
    expect(titulo(w)).toContain('Recomendaria?')
    expect((w.get('input[value="3"]').element as HTMLInputElement).checked).toBe(false)
  })

  it('focoId num final mostra a tela dele, com quando ele aparece; o padrão também', async () => {
    const w = mount(Pesquisa, { props: { formulario: formulario(itens), previa: true, finais, focoId: 'f_promot', motivoFoco: 'NPS é promotor', variaveis: { nome: 'Maria' } } })
    expect(w.get('h1').text()).toBe('Obrigado, Maria!')
    expect(w.get('[data-faixa-foco]').text()).toBe('Este final aparece quando: NPS é promotor')
    await w.setProps({ focoId: FOCO_FINAL_PADRAO })
    expect(w.get('h1').text()).toBe(TEMA_PADRAO.titulo_final)
    expect(w.get('[data-faixa-foco]').text()).toBe('Este final aparece quando nenhum outro final vale.')
  })
})
