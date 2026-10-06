// Etapa 5h (B), §3: a página da pesquisa no celular (taxa de resposta).
// - NPS em duas linhas (0–5 e 6–10) quando o cartão tem menos de 420 px (container `pesquisa`), cada nota com 44 × 44 px
//   ou mais, "Nada provável" embaixo do 0 e "Muito provável" embaixo do 10; uma linha no cartão largo, como antes. A
//   escala de 8 a 11 notas faz o mesmo; CSAT, estrelas e escala de até 7 notas ficam como estão.
// - Sem a tela "Começar": título e texto de abertura no alto da primeira pergunta; sem "Voltar" na primeira; ?nota=N
//   começa depois da nota, como antes.
// - No fim, o aria-live anuncia o título final. A prévia do editor e o botão no site (a mesma página, embutida) seguem.
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { compile } from 'tailwindcss'
import type { Tema as TemaApi } from '@/api/tipos'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import { TEMA_PADRAO, type FormularioPublico, type Pergunta, type Tema } from '@/pesquisa/tipos'
import AbaAparencia from '@/modulos/formularios/editor/AbaAparencia.vue'
import PreVisualizacao from '@/modulos/formularios/editor/PreVisualizacao.vue'
import { useSessaoStore } from '@/stores/sessao'

const NPS: Pergunta = { id: 'nota', tipo: 'nps', titulo: 'Recomendaria a {empresa}?', obrigatoria: true }
const COMENTARIO: Pergunta = { id: 'porque', tipo: 'comentario', titulo: 'O que mais pesou na sua nota?', obrigatoria: false }
const ABERTURA: Partial<Tema> = { titulo_abertura: 'Olá, {nome}!', texto_abertura: 'Leva menos de um minuto e ajuda muito a {empresa}.' }
const VARIAVEIS = { nome: 'Ana Lima', empresa: 'Acme' }

const formulario = (perguntas: Pergunta[] = [NPS, COMENTARIO], tema: Partial<Tema> = ABERTURA): FormularioPublico => ({
  nome: 'Pesquisa NPS (interno)',
  perguntas,
  tema: { ...TEMA_PADRAO, ...tema },
})

function montar(props: Record<string, unknown> = {}) {
  return mount(Pesquisa, { props: { formulario: formulario(), variaveis: VARIAVEIS, ...props }, attachTo: document.body })
}

const notas = (w: VueWrapper) => w.findAll('[role="radiogroup"] label[data-nota]')
/** Uma variável CSS do estilo do elemento (ex.: --colunas da régua). */
const variavel = (el: Pick<DOMWrapper<Element>, 'element'>, nome: string) => (el.element as HTMLElement).style.getPropertyValue(nome)
const botoes = (w: VueWrapper) => w.findAll('button').map((b) => b.text())
const anuncio = (w: VueWrapper) => w.get('[aria-live="polite"]').text()

/** Toca numa nota (como no celular): marca e, com uma pergunta por vez, avança sozinho depois de 320 ms. */
async function tocar(w: VueWrapper, n: number) {
  await w.find('fieldset').trigger('pointerdown')
  await w.get(`input[type="radio"][value="${n}"]`).setValue(true)
  vi.advanceTimersByTime(400)
  await flushPromises()
}

/** O CSS que o Tailwind gera para as classes que estão na tela (as variantes do container `pesquisa` incluídas). */
async function cssDaTela(raiz: Element): Promise<string> {
  const classes = new Set<string>()
  for (const el of [raiz, ...raiz.querySelectorAll('*')]) el.classList.forEach((c) => classes.add(c))
  const exigir = createRequire(import.meta.url)
  const tailwind = await compile(`@import 'tailwindcss/utilities';`, {
    base: process.cwd(),
    loadStylesheet: async (id: string) => ({
      base: process.cwd(),
      path: id,
      content: readFileSync(exigir.resolve(id === 'tailwindcss/utilities' ? 'tailwindcss/utilities.css' : id), 'utf8'),
    }),
  })
  return tailwind.build([...classes])
}

/** O conteúdo dos blocos de nível mais alto do CSS cujo cabeçalho é `prelude`. */
function blocos(css: string, prelude: string): string {
  let saida = ''
  let i = css.indexOf(prelude)
  while (i >= 0) {
    const abre = css.indexOf('{', i)
    let fundo = 1
    let j = abre + 1
    for (; j < css.length && fundo; j++) fundo += css[j] === '{' ? 1 : css[j] === '}' ? -1 : 0
    saida += css.slice(abre + 1, j - 1)
    i = css.indexOf(prelude, j)
  }
  return saida
}

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

// ───────────── Régua do NPS ─────────────

describe('régua do NPS no celular', () => {
  it('cartão estreito: duas linhas, 0–5 e 6–10, a segunda começando no meio; cartão largo: uma linha', () => {
    const w = montar()
    const grupo = w.get('[role="radiogroup"]')
    expect(grupo.attributes('data-regua')).toBe('duas-linhas')
    const ls = notas(w)
    // a ordem no DOM não muda: as setas do teclado andam 0, 1, … 10
    expect(ls.map((l) => l.attributes('data-nota'))).toEqual(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'])
    for (const l of ls.slice(0, 6)) expect(l.classes()).toEqual(expect.arrayContaining(['row-start-1', 'col-span-2']))
    for (const l of ls.slice(6)) expect(l.classes()).toEqual(expect.arrayContaining(['row-start-3', 'col-span-2']))
    expect(ls.filter((l) => l.classes('col-start-2')).map((l) => l.attributes('data-nota'))).toEqual(['6'])
    // 12 colunas no estreito (cada nota ocupa 2); 11 no largo, tudo na primeira linha
    expect(variavel(grupo, '--colunas')).toBe('12')
    expect(variavel(grupo, '--total')).toBe('11')
    expect(grupo.classes()).toEqual(
      expect.arrayContaining(['grid-cols-[repeat(var(--colunas),minmax(0,1fr))]', '@min-[420px]/pesquisa:grid-cols-[repeat(var(--total),minmax(0,1fr))]']),
    )
    for (const l of ls) expect(l.classes()).toEqual(expect.arrayContaining(['@min-[420px]/pesquisa:col-span-1', '@min-[420px]/pesquisa:row-start-1']))
    expect(ls[6]!.classes()).toContain('@min-[420px]/pesquisa:col-start-auto')
    // o container é a raiz da pesquisa: a largura de dentro dela é a do cartão
    expect(w.get('.pesquisa').classes()).toContain('@container/pesquisa')
  })

  it('cada nota com pelo menos 44 × 44 px num celular de 360 px', () => {
    const w = montar()
    const grupo = w.get('[role="radiogroup"]')
    for (const l of notas(w)) expect(l.get('span').classes()).toEqual(expect.arrayContaining(['h-12', 'text-base'])) // 48 px de altura
    expect(grupo.classes()).toContain('gap-x-1') // 4 px entre as notas
    // 360 px de tela: 16 px de margem de cada lado, 1 px de borda e 20 px de respiro no cartão → 286 px para a régua;
    // 12 colunas com 11 vãos de 4 px, cada nota ocupando 2 colunas e o vão entre elas
    const conteudo = 360 - 2 * 16 - 2 * 1 - 2 * 20
    const coluna = (conteudo - 11 * 4) / 12
    expect(2 * coluna + 4).toBeGreaterThanOrEqual(44)
    expect(w.get('.pesquisa').classes()).toEqual(expect.arrayContaining(['px-4']))
    expect(w.get('form').element.parentElement!.classList).toContain('p-5')
  })

  it('"Nada provável" embaixo do 0 e "Muito provável" embaixo do 10; no cartão largo, a linha de rótulos de antes', () => {
    const w = montar()
    const grupo = w.get('[role="radiogroup"]')
    const min = grupo.get('[data-rotulo-min]')
    const max = grupo.get('[data-rotulo-max]')
    expect(min.text()).toBe('Nada provável')
    expect(min.classes()).toEqual(expect.arrayContaining(['row-start-2', 'col-span-full', '@min-[420px]/pesquisa:hidden']))
    expect(max.text()).toBe('Muito provável')
    expect(max.classes()).toEqual(expect.arrayContaining(['row-start-4', 'text-right', '[grid-column:1/var(--fim)]', '@min-[420px]/pesquisa:hidden']))
    // o 10 ocupa as colunas 10 e 11 (termina na linha 12 da grade): o rótulo termina junto
    expect(variavel(grupo, '--fim')).toBe('12')
    const linha = w.get('[data-rotulos-linha]')
    expect(linha.classes()).toEqual(expect.arrayContaining(['hidden', '@min-[420px]/pesquisa:flex']))
    expect(linha.text()).toContain('Nada provável')
    // leitores de tela: os rótulos vão no nome da primeira e da última nota (os textos visíveis ficam escondidos deles)
    expect(w.get('input[value="0"]').attributes('aria-label')).toBe('0 (Nada provável)')
    expect(w.get('input[value="10"]').attributes('aria-label')).toBe('10 (Muito provável)')
    expect(w.get('input[value="5"]').attributes('aria-label')).toBe('5')
    expect(min.attributes('aria-hidden')).toBe('true')
    expect(max.attributes('aria-hidden')).toBe('true')
  })

  it('as classes geram as regras certas (container "pesquisa" a partir de 420 px)', async () => {
    const w = montar()
    const css = await cssDaTela(w.element)
    expect(css).toMatch(/\.\\@container\\\/pesquisa \{\s*container-type: inline-size;\s*container-name: pesquisa;/)
    expect(css).toContain('grid-template-columns: repeat(var(--colunas),minmax(0,1fr))')
    expect(css).toContain('grid-column: 1/var(--fim)')
    const largo = blocos(css, '@container pesquisa (width >= 420px)')
    expect(largo).toContain('grid-template-columns: repeat(var(--total),minmax(0,1fr))')
    expect(largo).toContain('grid-column: span 1 / span 1')
    expect(largo).toContain('grid-row-start: 1')
    expect(largo).toContain('grid-column-start: auto')
    expect(largo).toContain('display: none') // os rótulos de baixo do 0 e do 10
    expect(largo).toContain('display: flex') // a linha de rótulos
  })

  it('toque numa nota marca e avança sozinho; as setas trocam a nota sem avançar e Enter confirma', async () => {
    vi.useFakeTimers()
    const w = montar()
    await flushPromises()
    await w.find('fieldset').trigger('keydown', { key: 'ArrowRight' })
    await w.get('input[value="6"]').setValue(true)
    vi.advanceTimersByTime(1000)
    await flushPromises()
    expect(w.find('[data-titulo-pergunta]').text()).toContain('Recomendaria a Acme?')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('O que mais pesou na sua nota?')

    const w2 = montar()
    await flushPromises()
    await tocar(w2, 9)
    expect(w2.text()).toContain('O que mais pesou na sua nota?')
  })
})

// ───────────── Outras escalas ─────────────

describe('outras escalas', () => {
  const escala = (min: number, max: number): Pergunta => ({
    id: `e${min}${max}`,
    tipo: 'escala',
    titulo: 'Concorda?',
    obrigatoria: false,
    min,
    max,
    rotulo_min: 'Discordo',
    rotulo_max: 'Concordo',
  })
  const regua = (p: Pergunta) => montar({ formulario: formulario([p], {}) }).get('[role="radiogroup"]')

  it('escala de até 7 notas: uma linha, como antes', () => {
    const g = regua(escala(1, 7))
    expect(g.attributes('data-regua')).toBe('uma-linha')
    expect(g.classes()).toEqual(expect.arrayContaining(['grid-cols-[repeat(var(--total),minmax(0,1fr))]', 'gap-1.5']))
    expect(g.findAll('label').every((l) => !l.classes().some((c) => c.startsWith('row-start')))).toBe(true)
    expect(g.find('[data-rotulo-min]').exists()).toBe(false)
    expect(g.get('label span').classes()).toEqual(expect.arrayContaining(['h-11', 'text-sm']))
    expect(g.get('input[value="1"]').attributes('aria-label')).toBe('1 (Discordo)')
    expect(g.get('input[value="7"]').attributes('aria-label')).toBe('7 (Concordo)')
  })

  it('escala de 0 a 10: duas linhas como o NPS; de 1 a 10: 5 + 5, sem deslocar a segunda', () => {
    const onze = regua(escala(0, 10))
    expect(onze.attributes('data-regua')).toBe('duas-linhas')
    expect(variavel(onze, '--colunas')).toBe('12')
    expect(onze.findAll('label').filter((l) => l.classes('col-start-2')).map((l) => l.attributes('data-nota'))).toEqual(['6'])
    const dez = regua(escala(1, 10))
    expect(dez.attributes('data-regua')).toBe('duas-linhas')
    expect(variavel(dez, '--colunas')).toBe('10')
    expect(variavel(dez, '--fim')).toBe('11')
    expect(dez.findAll('label.row-start-1').map((l) => l.attributes('data-nota'))).toEqual(['1', '2', '3', '4', '5'])
    expect(dez.findAll('label.row-start-3').map((l) => l.attributes('data-nota'))).toEqual(['6', '7', '8', '9', '10'])
    expect(dez.findAll('label').some((l) => l.classes('col-start-2'))).toBe(false)
  })

  it('CSAT e estrelas ficam como estão', () => {
    const csat = montar({ formulario: formulario([{ id: 'c', tipo: 'csat', titulo: 'Como foi?', obrigatoria: true }], {}) })
    const g = csat.get('[role="radiogroup"]')
    expect(g.attributes('data-regua')).toBeUndefined()
    expect(g.classes()).toEqual(expect.arrayContaining(['grid-cols-5', 'gap-2']))
    expect(g.findAll('input[type="radio"]')).toHaveLength(5)
    const estrelas = montar({ formulario: formulario([{ id: 'e', tipo: 'estrelas', titulo: 'Nota', obrigatoria: true }], {}) })
    expect(estrelas.get('[role="radiogroup"]').attributes('data-regua')).toBeUndefined()
    expect(estrelas.findAll('[role="radiogroup"] label span.size-12')).toHaveLength(5) // 48 × 48 px
  })
})

// ───────────── Sem a tela "Começar" ─────────────

describe('abertura no alto da primeira pergunta', () => {
  it('título e texto de abertura na mesma tela da primeira pergunta, sem "Começar" e sem "Voltar"', async () => {
    const w = montar()
    await flushPromises()
    expect(w.text()).not.toContain('Começar')
    const form = w.get('form')
    const abertura = form.get('[data-abertura]')
    expect(abertura.get('h1').text()).toBe('Olá, Ana!')
    expect(abertura.text()).toContain('Leva menos de um minuto e ajuda muito a Acme.')
    // a abertura vem antes da pergunta, que já está na tela com a régua
    const h1 = abertura.get('h1').element
    const pergunta = form.get('[data-titulo-pergunta]').element
    expect(h1.compareDocumentPosition(pergunta) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(form.find('[role="radiogroup"]').exists()).toBe(true)
    expect(w.text()).toContain('Pergunta 1 de 2')
    expect(botoes(w)).not.toContain('Voltar')
    expect(botoes(w)).toContain('Continuar')
    expect(w.find('[role="progressbar"]').exists()).toBe(true)
  })

  it('some na segunda pergunta (que tem "Voltar") e volta com ela, com a nota ainda marcada', async () => {
    vi.useFakeTimers()
    const w = montar()
    await flushPromises()
    await tocar(w, 3)
    expect(w.text()).toContain('O que mais pesou na sua nota?')
    expect(w.find('[data-abertura]').exists()).toBe(false)
    expect(botoes(w)).toContain('Voltar')
    await w.findAll('button').find((b) => b.text() === 'Voltar')!.trigger('click')
    await flushPromises()
    expect(w.find('[data-abertura]').exists()).toBe(true)
    expect(botoes(w)).not.toContain('Voltar')
    expect((w.get('input[value="3"]').element as HTMLInputElement).checked).toBe(true)
    // o foco vai para a pergunta (a abertura fica logo acima)
    expect(document.activeElement?.hasAttribute('data-titulo-pergunta')).toBe(true)
  })

  it('só com o texto de boas-vindas: sem título (o nome do formulário é interno e não vira título)', () => {
    const w = montar({ formulario: formulario([NPS], { titulo_abertura: null, texto_abertura: 'Responda em 1 minuto, {nome}.' }) })
    const abertura = w.get('[data-abertura]')
    expect(abertura.find('h1').exists()).toBe(false)
    expect(abertura.text()).toBe('Responda em 1 minuto, Ana.')
    expect(w.text()).not.toContain('Pesquisa NPS (interno)')
  })

  it('sem abertura (ou só com espaços), a primeira pergunta abre direto', () => {
    for (const tema of [{}, { titulo_abertura: '  ', texto_abertura: '' }]) {
      const w = montar({ formulario: formulario([NPS, COMENTARIO], tema) })
      expect(w.find('[data-abertura]').exists()).toBe(false)
      expect(w.find('h1').exists()).toBe(false)
      expect(botoes(w)).not.toContain('Voltar')
    }
  })

  it('no modo páginas, a abertura fica no alto da primeira página', async () => {
    const quebra: Pergunta = { id: 'q', tipo: 'quebra_pagina', titulo: '', obrigatoria: false }
    const w = montar({ formulario: formulario([NPS, quebra, COMENTARIO], { ...ABERTURA, modo: 'paginas' }) })
    await flushPromises()
    expect(w.get('[data-abertura] h1').text()).toBe('Olá, Ana!')
    expect(w.text()).toContain('Página 1 de 2')
    await w.get('input[value="10"]').setValue(true)
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('Página 2 de 2')
    expect(w.find('[data-abertura]').exists()).toBe(false)
  })
})

// ───────────── ?nota=N ─────────────

describe('?nota=N (a nota tocada no e-mail)', () => {
  it('começa depois da nota, sem a abertura; "Voltar" leva à primeira pergunta, com a abertura e a nota marcada', async () => {
    const w = montar({ notaInicial: 9 })
    await flushPromises()
    expect(w.text()).toContain('O que mais pesou na sua nota?')
    expect(w.text()).toContain('Pergunta 2 de 2')
    expect(w.find('[data-abertura]').exists()).toBe(false)
    await w.findAll('button').find((b) => b.text() === 'Voltar')!.trigger('click')
    await flushPromises()
    expect(w.get('[data-abertura] h1').text()).toBe('Olá, Ana!')
    expect((w.get('input[value="9"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('nota fora da faixa é ignorada: começa na primeira pergunta, com a abertura e nada marcado', async () => {
    const w = montar({ notaInicial: 11 })
    await flushPromises()
    expect(w.find('[data-abertura]').exists()).toBe(true)
    expect(w.text()).toContain('Pergunta 1 de 2')
    expect(w.findAll('input[type="radio"]').some((i) => (i.element as HTMLInputElement).checked)).toBe(false)
  })

  it('formulário só com a nota: fica na primeira (e única) tela, com a abertura e a nota marcada', async () => {
    const w = montar({ formulario: formulario([NPS]), notaInicial: 7 })
    await flushPromises()
    expect(w.find('[data-abertura]').exists()).toBe(true)
    expect((w.get('input[value="7"]').element as HTMLInputElement).checked).toBe(true)
    expect(botoes(w)).toContain('Enviar')
  })
})

// ───────────── Anúncio final ─────────────

describe('anúncio para leitores de tela no fim', () => {
  it('o aria-live anuncia o título final (antes ficava "Pergunta 2 de 2")', async () => {
    const enviar = vi.fn(async () => ({ titulo_final: 'Valeu, {nome}!', texto_final: 'Até mais.' }))
    const w = montar({ enviar })
    await flushPromises()
    await w.get('input[value="10"]').setValue(true)
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(anuncio(w)).toBe('Pergunta 2 de 2')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(enviar).toHaveBeenCalledWith({ nota: 10 })
    expect(w.get('h1').text()).toBe('Valeu, Ana!')
    expect(anuncio(w)).toBe('Valeu, Ana!')
    expect(document.activeElement?.textContent?.trim()).toBe('Valeu, Ana!')
  })

  it('na pré-visualização (sem enviar), o título do tema; "Ver de novo" limpa o anúncio e volta para a abertura', async () => {
    const w = montar({ formulario: formulario([NPS], { ...ABERTURA, titulo_final: 'Obrigado, {nome}!' }), previa: true })
    await flushPromises()
    await w.get('input[value="8"]').setValue(true)
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(anuncio(w)).toBe('Obrigado, Ana!')
    await w.findAll('button').find((b) => b.text() === 'Ver de novo')!.trigger('click')
    await flushPromises()
    expect(anuncio(w)).toBe('')
    expect(w.find('[data-abertura]').exists()).toBe(true)
  })
})

// ───────────── Prévia do editor, widget e Aparência ─────────────

describe('a prévia do editor e o botão no site seguem a página', () => {
  const roteador = () => createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })

  it('prévia do editor: a abertura no alto da primeira pergunta e a régua em duas linhas; "Recomeçar" volta a ela', async () => {
    const sessao = useSessaoStore()
    sessao.permissoes = ['formularios.editar']
    sessao.conta = { id: 1, nome: 'Acme', logo_url: null } as never
    const tema = { ...TEMA_PADRAO, ...ABERTURA, cor: '#0e7490' } as unknown as TemaApi
    const w = mount(PreVisualizacao, {
      props: { nome: 'Pesquisa NPS', perguntas: [NPS, COMENTARIO] as never, tema, nomeEmpresa: 'Acme' },
      global: { plugins: [roteador()] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(w.text()).not.toContain('Começar')
    expect(w.get('[data-abertura] h1').text()).toBe('Olá, Maria!') // a cliente de exemplo da prévia
    expect(w.get('[role="radiogroup"][data-regua]').attributes('data-regua')).toBe('duas-linhas')
    expect(w.get('.pesquisa').classes()).toContain('@container/pesquisa')
    await w.get('input[value="10"]').setValue(true)
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(w.find('[data-abertura]').exists()).toBe(false)
    // Etapa 5l: "Recomeçar" virou "Reiniciar" (docs/api-etapa-5l.md §5.3).
    await w.findAll('button').find((b) => b.text().includes('Reiniciar'))!.trigger('click')
    await flushPromises()
    expect(w.find('[data-abertura]').exists()).toBe(true)
    expect(w.findAll('button').map((b) => b.text())).not.toContain('Voltar')
  })

  it('botão no site (pesquisa embutida, compacta): o mesmo container, a mesma régua e a abertura junto da pergunta', () => {
    const w = montar({ compacto: true })
    expect(w.get('.pesquisa').classes()).toContain('@container/pesquisa')
    expect(w.get('[role="radiogroup"]').attributes('data-regua')).toBe('duas-linhas')
    expect(w.find('form [data-abertura]').exists()).toBe(true)
  })

  it('Aparência: a dica do título de boas-vindas diz que ele aparece no alto da primeira pergunta', () => {
    const sessao = useSessaoStore()
    sessao.permissoes = ['formularios.editar', 'configuracoes.gerenciar']
    sessao.conta = { id: 1, nome: 'Acme', logo_url: null } as never
    const w = mount(AbaAparencia, {
      props: { tema: { ...TEMA_PADRAO } as unknown as TemaApi, descricao: '', erros: {}, formularioId: 7 },
      global: { plugins: [roteador()] },
    })
    expect(w.text()).toContain('Se preencher, aparece no alto da primeira pergunta, junto com o texto de boas-vindas.')
    expect(w.text()).not.toContain('tela de abertura')
  })
})
