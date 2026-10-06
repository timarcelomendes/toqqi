// Editor de formulário da etapa 5l (docs/api-etapa-5l.md §5.3 e §5.8), montado na tela de verdade com a API falsa:
// adicionar pelo menu, mover/arrastar/Alt+setas, duplicar, excluir com dependências, opções e condições, construtor de
// lógica, regras de pular, atalhos da nota principal, finais, salvamento automático (espera, fila, normalizado, 409),
// publicar, descartar, desfazer/refazer e a prévia seguindo o item.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { h, nextTick } from 'vue'
import type { DocumentoFormulario, Final, Formulario, Pergunta } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { TEMA_PADRAO } from '@/pesquisa/tipos'
import { useSessaoStore } from '@/stores/sessao'
import EditorFormularioView from '@/modulos/formularios/EditorFormularioView.vue'
import { partesSoNoHtml } from '@/modulos/formularios/editor/htmlVisual'
import { apiFalsa, erro422, type Chamada } from './apiFalsa'

// O SortableJS não arrasta no jsdom: o teste guarda as opções e faz o papel dele (mexe no DOM e chama o onEnd).
const arraste = vi.hoisted(() => ({ listas: [] as { el: HTMLElement; opcoes: Record<string, unknown> }[] }))
vi.mock('sortablejs', () => ({
  default: {
    create: (el: HTMLElement, opcoes: Record<string, unknown>) => {
      arraste.listas.push({ el, opcoes })
      return { destroy: () => (arraste.listas = arraste.listas.filter((l) => l.el !== el)) }
    },
  },
}))
// O editor visual (TipTap) não roda no jsdom: aqui ele vira uma caixa simples; o texto formatado é testado pela aba HTML.
vi.mock('@/modulos/formularios/editor/EditorVisual.vue', async () => {
  const { defineComponent, h: hh } = await import('vue')
  return {
    __esModule: true,
    default: defineComponent({
      props: { modelValue: { type: String, default: '' } },
      setup(props, { expose }) {
        expose({ inserirTexto: () => {}, inserirImagem: () => {}, focar: () => {} })
        return () => hh('div', { 'data-editor-visual-falso': '' }, props.modelValue)
      },
    }),
  }
})

const PREFIXO = 'http://localhost:8000/api/v1/publico/imagens/'
const g = (fonte: string, ...grupos: string[]) => ({ juncao: 'todas' as const, condicoes: [{ fonte, op: 'grupo_e' as const, valor: grupos }] })
const clonar = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T

function perguntasBase(): Pergunta[] {
  return [
    { id: 'p_nota01', tipo: 'nps', titulo: 'Quanto você recomendaria a {empresa}?', obrigatoria: true },
    { id: 'p_melh01', tipo: 'comentario', titulo: 'O que podemos melhorar?', obrigatoria: false, logica: { mostrar_se: g('p_nota01', 'detrator', 'neutro') } },
    { id: 'p_moti01', tipo: 'escolha_unica', titulo: 'Qual o motivo principal?', obrigatoria: false, opcoes: ['Preço', 'Prazo', 'Atendimento'] },
    {
      id: 'p_cont01',
      tipo: 'sim_nao',
      titulo: 'Podemos falar com você?',
      obrigatoria: false,
      logica: { mostrar_se: { juncao: 'todas', condicoes: [{ fonte: 'p_moti01', op: 'um_de', valor: ['Preço', 'Prazo'] }] } },
    },
  ]
}

function finaisBase(): Final[] {
  return [{ id: 'f_prom01', nome: 'Promotores', titulo: 'Obrigado por recomendar!', html: '<p>Valeu!</p>', botao: null, mostrar_se: g('p_nota01', 'promotor') }]
}

function formulario(extra: Partial<Formulario> = {}): Formulario {
  return {
    id: 7,
    nome: 'NPS pós-entrega',
    descricao: null,
    tipo_principal: 'nps',
    ativo: true,
    publico: true,
    codigo_publico: 'abc123',
    padrao_nps: false,
    padrao_csat: false,
    respostas: 0,
    atualizado_em: '2026-10-01T12:00:00Z',
    versao: 3,
    publicado_em: '2026-10-01T12:00:00Z',
    publicado_por_nome: 'Ana',
    perguntas: perguntasBase(),
    tema: { ...TEMA_PADRAO },
    finais: finaisBase(),
    rascunho: null,
    rascunho_rev: 4,
    prefixo_imagens: PREFIXO,
    ...extra,
  }
}

const json = (corpo: unknown, status: number) => new Response(JSON.stringify(corpo), { status })

/**
 * A API do editor com estado: rascunho com `rev` (409 se outra aba gravou), publicar, descartar. `normalizar` faz o
 * papel da normalização do servidor; `segurarPut` deixa o próximo PUT pendurado até `soltarPut()`.
 */
function servidor(f: Formulario) {
  const s = {
    f: clonar(f),
    normalizar: (d: DocumentoFormulario) => d,
    problemas: {} as Record<string, string>,
    segurar: false,
    soltar: null as (() => void) | null,
    putsAoMesmoTempo: 0,
    maxAoMesmoTempo: 0,
    respostaPublicar: null as Response | null,
  }
  const api = apiFalsa({
    'GET /formularios/:id': () => clonar(s.f),
    'PUT /formularios/:id/rascunho': async ({ corpo }) => {
      s.putsAoMesmoTempo++
      s.maxAoMesmoTempo = Math.max(s.maxAoMesmoTempo, s.putsAoMesmoTempo)
      try {
        if (s.segurar) {
          s.segurar = false
          await new Promise<void>((r) => (s.soltar = r))
        }
        const { rev, ...doc } = corpo as DocumentoFormulario & { rev: number }
        if (rev !== s.f.rascunho_rev)
          return json({ erro: { codigo: 'rascunho_desatualizado', mensagem: 'Este formulário foi alterado.', campos: {}, rev: s.f.rascunho_rev, salvo_em: '2026-10-06T17:05:00Z', salvo_por_nome: 'Bruno' } }, 409)
        const normal = s.normalizar(clonar(doc))
        s.f.rascunho = { ...normal, salvo_em: '2026-10-06T17:00:00Z', salvo_por_nome: 'Ana' }
        s.f.rascunho_rev = (s.f.rascunho_rev ?? 0) + 1
        return { rev: s.f.rascunho_rev, salvo_em: '2026-10-06T17:00:00Z', problemas: s.problemas, avisos: {}, tem_rascunho: true, rascunho: normal }
      } finally {
        s.putsAoMesmoTempo--
      }
    },
    'POST /formularios/:id/publicar': ({ corpo }) => {
      if (s.respostaPublicar) return s.respostaPublicar
      if ((corpo as { rev: number }).rev !== s.f.rascunho_rev) return json({ erro: { codigo: 'rascunho_desatualizado', mensagem: 'Alterado.', campos: {} } }, 409)
      if (!s.f.rascunho) return json({ erro: { codigo: 'sem_rascunho', mensagem: 'Não há alterações para publicar.', campos: {} } }, 409)
      const { salvo_em: _e, salvo_por_nome: _p, ...doc } = s.f.rascunho
      Object.assign(s.f, doc, { rascunho: null, versao: (s.f.versao ?? 1) + 1, publicado_em: '2026-10-06T17:10:00Z', rascunho_rev: (s.f.rascunho_rev ?? 0) + 1 })
      return clonar(s.f)
    },
    'DELETE /formularios/:id/rascunho': () => {
      s.f.rascunho = null
      s.f.rascunho_rev = (s.f.rascunho_rev ?? 0) + 1
      return undefined
    },
    'PATCH /formularios/:id': ({ corpo }) => {
      Object.assign(s.f, corpo)
      return clonar(s.f)
    },
  })
  return {
    ...api,
    s,
    puts: () => api.chamadas.filter((c: Chamada) => c.metodo === 'PUT'),
    soltarPut: () => s.soltar?.(),
  }
}

const PERMISSOES = ['formularios.ver', 'formularios.editar', 'configuracoes.gerenciar']

function entrar(permissoes = PERMISSOES) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Transportes Rápidos', plano: null, situacao: 'ativa', teste_ate: null, logo_url: null },
      permissoes,
    },
    false,
  )
}

async function abrir(f: Formulario = formulario(), permissoes = PERMISSOES) {
  entrar(permissoes)
  const api = servidor(f)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/formularios/:id', component: EditorFormularioView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'fora') } },
    ],
  })
  await router.push('/formularios/7')
  await router.isReady()
  const w = mount({ render: () => h(RouterView) }, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  await vi.waitFor(() => expect(document.querySelector('[data-aba-perguntas]')).not.toBeNull())
  await flushPromises()
  return { w, api, router }
}

// ── atalhos para a tela ──
const $ = <T extends Element = HTMLElement>(sel: string) => document.querySelector<T>(sel)
const $$ = <T extends Element = HTMLElement>(sel: string) => [...document.querySelectorAll<T>(sel)]
const ordem = () => $$('[data-estrutura] [data-item]').map((li) => li.getAttribute('data-item'))
const ordemFinais = () => $$('[data-estrutura] [data-final]').map((li) => li.getAttribute('data-final'))
const painel = () => $('[data-painel-edicao]')!
const titulosNaEstrutura = () => $$('[data-estrutura] [data-titulo-linha]').map((e) => e.textContent?.trim())

async function clicar(el: Element | null | undefined) {
  if (!el) throw new Error('elemento não encontrado')
  ;(el as HTMLElement).click()
  await flushPromises()
}

async function selecionar(id: string) {
  await clicar($(`[data-estrutura] [data-item="${id}"] [data-linha], [data-estrutura] [data-final="${id}"] [data-linha]`))
}

/** Tecla no documento (onde o editor escuta os atalhos), ou num elemento. */
async function teclar(key: string, opcoes: KeyboardEventInit = {}, alvo: EventTarget = document.body) {
  alvo.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...opcoes }))
  await flushPromises()
}

async function digitar(el: HTMLInputElement | HTMLTextAreaElement | null, texto: string) {
  if (!el) throw new Error('campo não encontrado')
  el.focus()
  el.value = texto
  el.dispatchEvent(new Event('input', { bubbles: true }))
  await nextTick()
}

async function escolher(select: HTMLSelectElement | null, valor: string) {
  if (!select) throw new Error('select não encontrado')
  select.value = valor
  select.dispatchEvent(new Event('change', { bubbles: true }))
  await flushPromises()
}

/** Ctrl+S: grava agora (sem esperar o 1,2 s). */
async function salvarAgora() {
  await teclar('s', { ctrlKey: true })
  await flushPromises()
}

const ultimoPut = (api: ReturnType<typeof servidor>) => api.puts().at(-1)!.corpo as DocumentoFormulario & { rev: number }
const pergunta = (doc: DocumentoFormulario, id: string) => doc.perguntas.find((p) => p.id === id)!

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  arraste.listas = []
})
afterEach(() => {
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
  vi.useRealTimers()
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
})

describe('Editor 5l › abrir', () => {
  it('abre o publicado com a nota principal selecionada, versão e situação; sem rascunho, Publicar fica desligado', async () => {
    await abrir()
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    expect($('[data-situacao]')!.textContent).toContain('Publicado · versão 3')
    expect($('[data-alteracoes-nao-publicadas]')).toBeNull()
    expect($<HTMLButtonElement>('[data-publicar]')!.disabled).toBe(true)
    expect($('[data-descartar]')).toBeNull()
    expect($('[data-item="p_nota01"] [data-linha]')!.getAttribute('aria-current')).toBe('true')
    expect(painel().textContent).toContain('nota principal')
    // Números só nas perguntas; lógica marcada na estrutura; o final por condição e o padrão
    expect($$('[data-estrutura] [data-numero]').map((e) => e.textContent)).toEqual(['P1', 'P2', 'P3', 'P4'])
    expect($('[data-item="p_melh01"] [data-marca-logica]')).not.toBeNull()
    expect($('[data-final="f_prom01"] [data-condicao-final]')!.textContent).toBe('Quando NPS é promotor')
    expect($('[data-final-padrao]')).not.toBeNull()
  })

  it('com rascunho, abre o rascunho (não o publicado) e mostra "Alterações não publicadas"', async () => {
    const rascunho = { perguntas: perguntasBase().slice(0, 2), tema: { ...TEMA_PADRAO }, finais: [], salvo_em: '2026-10-06T16:00:00Z', salvo_por_nome: 'Ana' }
    await abrir(formulario({ rascunho }))
    expect(ordem()).toEqual(['p_nota01', 'p_melh01'])
    expect($('[data-alteracoes-nao-publicadas]')!.textContent).toContain('Alterações não publicadas')
    expect($<HTMLButtonElement>('[data-publicar]')!.disabled).toBe(false)
    expect($('[data-descartar]')).not.toBeNull()
    expect($('[data-salvamento]')!.textContent).toContain('Rascunho salvo')
  })

  it('a condição antiga (`condicao`) vira `logica.mostrar_se` na nota principal', async () => {
    const perguntas: Pergunta[] = [
      { id: 'p_nota01', tipo: 'nps', titulo: 'Nota?', obrigatoria: true },
      { id: 'p_coment', tipo: 'comentario', titulo: 'Por quê?', obrigatoria: false, condicao: { tipo: 'grupo', grupos: ['detrator'] } },
    ]
    const { api } = await abrir(formulario({ perguntas, finais: [] }))
    await selecionar('p_coment')
    expect(painel().querySelector('[data-secao-logica]')!.textContent).toContain('Mostrar se: NPS é detrator')
    // Nada mudou de verdade: abrir não grava rascunho
    await salvarAgora()
    expect(api.puts()).toHaveLength(0)
  })
})

describe('Editor 5l › adicionar', () => {
  it('"/" abre o menu; a busca filtra sem acento; setas e Enter escolhem; o item entra depois do selecionado', async () => {
    const { api } = await abrir()
    await selecionar('p_melh01')
    await teclar('/')
    const busca = $<HTMLInputElement>('[data-busca-adicionar]')
    expect(busca).not.toBeNull()
    expect($('[data-menu-adicionar]')!.closest('[role="dialog"]')!.textContent).toContain('Entra depois de “P2 · O que podemos melhorar?”')
    // Todos os grupos
    expect($$('[data-menu-adicionar] [data-grupo]').map((e) => e.getAttribute('data-grupo'))).toEqual(['Notas', 'Escolhas', 'Texto', 'Data', 'Conteúdo', 'Estrutura'])

    await digitar(busca, 'telefone')
    expect($$('[data-menu-adicionar] [role="option"]').map((e) => e.getAttribute('data-opcao'))).toEqual(['telefone'])
    await digitar(busca, 'comentario')
    expect($$('[data-menu-adicionar] [role="option"]').map((e) => e.getAttribute('data-opcao'))).toContain('comentario')
    await digitar(busca, 'zzz')
    expect($('[data-menu-adicionar]')!.textContent).toContain('Nada encontrado para “zzz”.')

    // Teclado: busca "escolha", desce uma e Enter
    await digitar(busca, 'escolha')
    const opcoes = $$('[data-menu-adicionar] [role="option"]').map((e) => e.getAttribute('data-opcao'))
    expect(opcoes.slice(0, 2)).toEqual(['escolha_unica', 'escolha_multipla'])
    expect(busca!.getAttribute('aria-activedescendant')).toContain('escolha_unica')
    await teclar('ArrowDown', {}, busca!)
    expect(busca!.getAttribute('aria-activedescendant')).toContain('escolha_multipla')
    await teclar('Enter', {}, busca!)
    expect($('[data-menu-adicionar]')).toBeNull()

    const ids = ordem()
    expect(ids).toHaveLength(5)
    const novo = ids[2]!
    expect(novo).toMatch(/^p_[A-Za-z0-9]{6}$/)
    expect($(`[data-item="${novo}"]`)!.getAttribute('data-tipo')).toBe('escolha_multipla')
    expect($(`[data-item="${novo}"] [data-linha]`)!.getAttribute('aria-current')).toBe('true')
    // O foco vai para o título do item novo
    await vi.waitFor(() => expect(document.activeElement?.getAttribute('data-campo')).toBe('titulo'))
    // Grava o rascunho com o item novo
    await salvarAgora()
    expect(pergunta(ultimoPut(api), novo).tipo).toBe('escolha_multipla')
    expect(ultimoPut(api).rev).toBe(4)
  })

  it('"+" entre dois itens põe o novo naquela posição; conteúdo HTML e quebra de página também entram', async () => {
    await abrir()
    await clicar($$('[data-estrutura] [data-inserir-entre]')[0])
    expect($('[role="dialog"]')!.textContent).toContain('Entra depois de “P1 · Quanto você recomendaria a {empresa}?”')
    await clicar($('[data-menu-adicionar] [data-opcao="html"]'))
    const ids = ordem()
    expect($(`[data-item="${ids[1]}"]`)!.getAttribute('data-tipo')).toBe('conteudo')
    // Conteúdo não conta como pergunta: os números seguem P1, P2…
    expect($$('[data-estrutura] [data-numero]').map((e) => e.textContent)).toEqual(['P1', 'P2', 'P3', 'P4'])
    // HTML: abre na aba HTML
    expect(painel().querySelector('[data-campo="html"]')).not.toBeNull()

    await clicar($('[data-estrutura] [data-adicionar]'))
    await clicar($('[data-menu-adicionar] [data-opcao="quebra"]'))
    const depois = ordem()
    expect(depois).toHaveLength(6)
    expect($(`[data-item="${depois[2]}"]`)!.getAttribute('data-tipo')).toBe('quebra_pagina')
    expect($(`[data-item="${depois[2]}"]`)!.textContent).toContain('Página 2')
  })
})

describe('Editor 5l › mover, arrastar, duplicar e excluir', () => {
  it('Alt+↓ e Alt+↑ movem o selecionado; mover para antes da fonte avisa "A lógica de 1 item precisa de ajuste"', async () => {
    const { api } = await abrir()
    await selecionar('p_moti01')
    await teclar('ArrowDown', { altKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_cont01', 'p_moti01'])
    // p_cont01 agora vem antes da pergunta que a condição dela usa
    expect($('[data-aviso-logica]')!.textContent).toContain('A lógica de 1 item precisa de ajuste')
    expect($('[data-item="p_cont01"] [data-marca-problema]')).not.toBeNull()
    await teclar('ArrowUp', { altKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    expect($('[data-item="p_cont01"] [data-marca-problema]')).toBeNull()
    // A lógica voltou a valer: a faixa some sozinha
    expect($('[data-aviso-logica]')).toBeNull()
    // Alt+setas dentro de um campo de texto não movem
    await teclar('ArrowUp', { altKey: true }, painel().querySelector('input[data-campo="titulo"]')!)
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    // Mover e voltar dá o mesmo documento: nada para gravar
    await salvarAgora()
    expect(api.puts()).toHaveLength(0)
  })

  it('Alt+setas na linha da estrutura também move, e o foco acompanha a linha', async () => {
    await abrir()
    const linha = $<HTMLButtonElement>('[data-item="p_melh01"] [data-linha]')!
    linha.focus()
    await teclar('ArrowDown', { altKey: true }, linha)
    expect(ordem()).toEqual(['p_nota01', 'p_moti01', 'p_melh01', 'p_cont01'])
    await vi.waitFor(() => expect(document.activeElement).toBe($('[data-item="p_melh01"] [data-linha]')))
  })

  it('arrastar (SortableJS): o DOM volta para o Vue e a ordem do documento muda; arrastar o último não embaralha a lista depois', async () => {
    await abrir()
    await vi.waitFor(() => expect(arraste.listas.length).toBeGreaterThan(0))
    const ol = $('[data-estrutura] ol[aria-label="Itens do formulário"]')!
    const lista = arraste.listas.find((l) => l.el === ol)!
    expect(lista.opcoes.handle).toBe('[data-alca]')

    // Faz o que o SortableJS faz: tira o último e põe no começo; depois chama o onEnd.
    const arrastar = (de: number, para: number) => {
      const itens = [...ol.querySelectorAll(':scope > [data-item]')]
      const item = itens[de]!
      ol.removeChild(item)
      const resto = [...ol.querySelectorAll(':scope > [data-item]')]
      ol.insertBefore(item, resto[para] ?? resto.at(-1)!.nextSibling)
      ;(lista.opcoes.onEnd as (e: unknown) => void)({ from: ol, to: ol, item, oldIndex: de, newIndex: para, oldDraggableIndex: de, newDraggableIndex: para })
    }
    arrastar(3, 0)
    await flushPromises()
    expect(ordem()).toEqual(['p_cont01', 'p_nota01', 'p_melh01', 'p_moti01'])
    expect($('[data-aviso-logica]')).not.toBeNull()
    // Arrastar e soltar no mesmo lugar (o último): nada muda, e um item novo entra mesmo no fim
    arrastar(3, 3)
    await flushPromises()
    expect(ordem()).toEqual(['p_cont01', 'p_nota01', 'p_melh01', 'p_moti01'])
    await selecionar('p_moti01')
    await teclar('/')
    await clicar($('[data-menu-adicionar] [data-opcao="email"]'))
    const ids = ordem()
    expect(ids.slice(0, 4)).toEqual(['p_cont01', 'p_nota01', 'p_melh01', 'p_moti01'])
    expect($(`[data-item="${ids[4]}"]`)!.getAttribute('data-tipo')).toBe('texto_curto')
    // A ordem no DOM é a do documento (sem itens soltos depois da âncora do Vue)
    expect([...ol.children].map((li) => li.getAttribute('data-item'))).toEqual(ids)
  })

  it('"Mover para…" abre com o foco na lista, na posição de agora, e move para o lugar escolhido', async () => {
    await abrir()
    await clicar($('[data-item="p_cont01"] [data-acao="mover-para"]'))
    const dialogo = $('[role="dialog"]')!
    expect(dialogo.textContent).toContain('Mover para…')
    const lista = dialogo.querySelector<HTMLSelectElement>('select[data-mover-destino]')!
    await vi.waitFor(() => expect(document.activeElement).toBe(lista))
    expect(lista.value).toBe('p_moti01')
    expect([...lista.options].map((o) => o.textContent)).toEqual([
      'No começo do formulário',
      'Depois de P1 · Quanto você recomendaria a {empresa}?',
      'Depois de P2 · O que podemos melhorar?',
      'Depois de P3 · Qual o motivo principal?',
    ])
    await escolher(lista, 'p_nota01')
    await clicar(dialogo.querySelector('[data-confirmar-mover]'))
    expect(ordem()).toEqual(['p_nota01', 'p_cont01', 'p_melh01', 'p_moti01'])
    // De novo, para o começo
    await clicar($('[data-item="p_cont01"] [data-acao="mover-para"]'))
    await escolher($<HTMLSelectElement>('[role="dialog"] select[data-mover-destino]'), ':inicio')
    await clicar($('[role="dialog"] [data-confirmar-mover]'))
    expect(ordem()[0]).toBe('p_cont01')
  })

  it('duplicar (botão e Ctrl+D): cópia logo abaixo, id novo, "(cópia)", mantém "mostrar se" e tira as regras de pular', async () => {
    const perguntas = perguntasBase()
    perguntas[3]!.logica!.pular = [{ id: 'r_aaaa01', se: { juncao: 'todas', condicoes: [{ fonte: 'p_cont01', op: 'igual', valor: false }] }, para: 'fim' }]
    const { api } = await abrir(formulario({ perguntas }))
    await clicar($('[data-item="p_cont01"] [data-acao="duplicar"]'))
    const ids = ordem()
    expect(ids).toHaveLength(5)
    const copia = ids[4]!
    expect(copia).not.toBe('p_cont01')
    expect($(`[data-item="${copia}"] [data-titulo-linha]`)!.textContent).toContain('Podemos falar com você? (cópia)')
    await salvarAgora()
    const doc = ultimoPut(api)
    expect(pergunta(doc, copia).logica?.mostrar_se).toEqual(pergunta(doc, 'p_cont01').logica?.mostrar_se)
    expect(pergunta(doc, copia).logica?.pular).toBeUndefined()

    await selecionar('p_melh01')
    await teclar('d', { ctrlKey: true })
    expect(ordem()).toHaveLength(6)
    expect(ordem()[2]).not.toBe('p_moti01')
    expect($(`[data-item="${ordem()[2]}"] [data-linha]`)!.getAttribute('aria-current')).toBe('true')
  })

  it('excluir item usado na lógica pede confirmação e tira as condições que usam o item', async () => {
    const { api } = await abrir()
    await clicar($('[data-item="p_moti01"] [data-acao="excluir"]'))
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.mensagem).toContain('é usado na lógica de “P4 · Podemos falar com você?”')
    expect(estadoConfirmacao.confirmar).toBe('Excluir e remover as condições que usam este item')
    responderConfirmacao(true)
    await flushPromises()
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_cont01'])
    expect($('[data-item="p_cont01"] [data-marca-logica]')).toBeNull()
    // O vizinho fica selecionado
    expect($('[data-item="p_cont01"] [data-linha]')!.getAttribute('aria-current')).toBe('true')
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_cont01').logica).toBeUndefined()

    // Excluir a nota principal tira as condições dos outros e o final por grupo
    await clicar($('[data-item="p_nota01"] [data-acao="excluir"]'))
    expect(estadoConfirmacao.mensagem).toContain('o final “Promotores”')
    responderConfirmacao(true)
    await flushPromises()
    await salvarAgora()
    const doc = ultimoPut(api)
    expect(pergunta(doc, 'p_melh01').logica).toBeUndefined()
    expect(doc.finais[0]!.mostrar_se).toBeNull()
  })

  it('cancelar a exclusão não muda nada; item sem uso pede a confirmação simples; Delete na linha exclui', async () => {
    await abrir()
    await clicar($('[data-item="p_melh01"] [data-acao="excluir"]'))
    expect(estadoConfirmacao.confirmar).toBe('Excluir')
    responderConfirmacao(false)
    await flushPromises()
    expect(ordem()).toHaveLength(4)
    const linha = $<HTMLButtonElement>('[data-item="p_melh01"] [data-linha]')!
    linha.focus()
    await teclar('Delete', {}, linha)
    expect(estadoConfirmacao.aberto).toBe(true)
    responderConfirmacao(true)
    await flushPromises()
    expect(ordem()).toEqual(['p_nota01', 'p_moti01', 'p_cont01'])
  })
})

describe('Editor 5l › texto formatado: o que só a aba HTML edita', () => {
  it('tabela e div travam o Visual; script, iframe e span não (a limpeza tira ou o Visual dá conta)', () => {
    expect(partesSoNoHtml('<p>Oi</p><table><tr><td>1</td></tr></table><div>x</div>')).toEqual(['table', 'tbody', 'tr', 'td', 'div'])
    expect(partesSoNoHtml('<p onclick="x()">Oi <span style="color:red">a</span></p><script>alert(1)</script><iframe src="https://x.com"></iframe>')).toEqual([])
    expect(partesSoNoHtml('<h2>T</h2><ul><li><a href="https://x.com">l</a></li></ul><blockquote>c</blockquote><hr><img src="x" alt="">')).toEqual([])
  })
})

describe('Editor 5l › opções e condições', () => {
  it('renomear uma opção (ao sair do campo) atualiza as condições; o texto passando por outra opção não leva as condições dela', async () => {
    const perguntas = perguntasBase()
    perguntas[2]!.opcoes = ['Sim', 'Sim, muito', 'Não']
    perguntas[3]!.logica = { mostrar_se: { juncao: 'todas', condicoes: [{ fonte: 'p_moti01', op: 'um_de', valor: ['Sim'] }] } }
    const { api } = await abrir(formulario({ perguntas }))
    await selecionar('p_moti01')
    const campos = () => [...painel().querySelectorAll<HTMLInputElement>('[data-campo="opcoes"] input')]
    const segunda = campos()[1]!
    segunda.dispatchEvent(new FocusEvent('focus'))
    // Digitando: "Sim, muito" → "Sim" → "Talvez" (passa por "Sim", que é a outra opção)
    for (const t of ['Sim, muit', 'Sim', 'Si', 'Talvez']) await digitar(segunda, t)
    segunda.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_cont01').logica!.mostrar_se!.condicoes[0]!.valor).toEqual(['Sim'])

    // Renomear a opção usada: a condição acompanha
    const primeira = campos()[0]!
    primeira.dispatchEvent(new FocusEvent('focus'))
    await digitar(primeira, 'Sim, claro')
    primeira.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_cont01').logica!.mostrar_se!.condicoes[0]!.valor).toEqual(['Sim, claro'])
    expect(pergunta(ultimoPut(api), 'p_moti01').opcoes).toEqual(['Sim, claro', 'Talvez', 'Não'])
  })

  it('excluir uma opção usada pede confirmação, tira a opção da condição e a condição vazia some', async () => {
    const { api } = await abrir()
    await selecionar('p_moti01')
    await clicar(painel().querySelector('[aria-label="Remover opção 1"]'))
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.mensagem).toContain('A opção “Preço” é usada em 1 condição')
    responderConfirmacao(true)
    await flushPromises()
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_cont01').logica!.mostrar_se!.condicoes[0]!.valor).toEqual(['Prazo'])

    await clicar(painel().querySelector('[aria-label="Remover opção 1"]'))
    responderConfirmacao(true)
    await flushPromises()
    await salvarAgora()
    // Sem nenhuma opção, a condição sai; o grupo vazio deixa a pergunta sem lógica
    expect(pergunta(ultimoPut(api), 'p_cont01').logica).toBeUndefined()
    expect(pergunta(ultimoPut(api), 'p_moti01').opcoes).toEqual(['Atendimento'])
  })

  it('construtor: operadores conforme o tipo da pergunta, "todas"/"qualquer uma" e a frase na estrutura', async () => {
    const perguntas: Pergunta[] = [
      ...perguntasBase(),
      { id: 'p_data01', tipo: 'data', titulo: 'Quando foi a entrega?', obrigatoria: false },
      { id: 'p_mult01', tipo: 'escolha_multipla', titulo: 'O que usou?', obrigatoria: false, opcoes: ['App', 'Site'] },
      { id: 'p_fim001', tipo: 'texto_curto', titulo: 'Seu e-mail', formato: 'email', obrigatoria: false },
    ]
    const { api } = await abrir(formulario({ perguntas }))
    await selecionar('p_fim001')
    const secao = painel().querySelector('[data-secao-logica]')!
    // "Só se…": começa pela nota principal, no grupo
    await clicar(secao.querySelector('input[type="radio"][value="so_se"]'))
    const operadores = () => [...painel().querySelectorAll<HTMLSelectElement>('[data-logica-onde="mostrar_se"] select[data-operador]')]
    const textos = (s: HTMLSelectElement) => [...s.options].map((o) => o.textContent?.trim())
    expect(textos(operadores()[0]!)).toEqual([
      'está no grupo',
      'é',
      'não é',
      'é menor que',
      'é no máximo',
      'é maior que',
      'é pelo menos',
      'está entre',
      'foi respondida',
      'não foi respondida',
    ])
    expect(painel().querySelector('[data-logica-onde="mostrar_se"]')!.textContent).toContain('Mostrar quando esta condição valer:')

    // + Condição: usa a mesma pergunta; troca para a escolha única, a data e a múltipla
    await clicar(painel().querySelector('[data-logica-onde="mostrar_se"] [data-adicionar-condicao]'))
    expect(painel().querySelector('[data-logica-onde="mostrar_se"]')!.textContent).toContain('destas condições valerem:')
    const fontes = () => [...painel().querySelectorAll<HTMLSelectElement>('[data-logica-onde="mostrar_se"] select[data-fonte]')]
    await escolher(fontes()[1]!, 'p_moti01')
    expect(textos(operadores()[1]!)).toEqual(['é uma de', 'não é nenhuma de', 'foi respondida', 'não foi respondida'])
    await escolher(fontes()[1]!, 'p_data01')
    expect(textos(operadores()[1]!)).toEqual(['é', 'não é', 'antes de', 'até', 'depois de', 'a partir de', 'está entre', 'foi respondida', 'não foi respondida'])
    await escolher(fontes()[1]!, 'p_mult01')
    expect(textos(operadores()[1]!)).toEqual(['inclui alguma de', 'inclui todas', 'não inclui nenhuma de', 'foi respondida', 'não foi respondida'])
    await escolher(fontes()[1]!, 'p_cont01')
    expect(textos(operadores()[1]!)).toEqual(['é', 'foi respondida', 'não foi respondida'])
    // A pergunta não pode usar a si mesma nem as de depois
    expect([...fontes()[1]!.options].map((o) => o.value)).not.toContain('p_fim001')

    // Grupo NPS: Promotores; sim/não: Sim; junção "qualquer uma"
    await clicar(painel().querySelector('[data-condicao="1"] [data-grupo-valor="promotor"]'))
    await clicar([...painel().querySelectorAll<HTMLButtonElement>('[data-condicao="2"] [role="radio"]')].find((b) => b.textContent?.trim() === 'Sim'))
    await escolher(painel().querySelector('[data-logica-onde="mostrar_se"] select[data-juncao]'), 'qualquer')
    expect(painel().querySelector('[data-logica-onde="mostrar_se"]')!.textContent).toContain('ou')
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_fim001').logica!.mostrar_se).toEqual({
      juncao: 'qualquer',
      condicoes: [
        { fonte: 'p_nota01', op: 'grupo_e', valor: ['detrator', 'promotor'] },
        { fonte: 'p_cont01', op: 'igual', valor: true },
      ],
    })
    expect($('[data-item="p_fim001"] [data-marca-logica]')!.getAttribute('title')).toBe('Mostrar se: NPS é detrator ou promotor ou “Podemos falar com você?” é Sim')

    // Remover as duas condições volta para "Sempre"
    await clicar(painel().querySelector('[data-condicao="2"] [data-remover-condicao]'))
    await clicar(painel().querySelector('[data-condicao="1"] [data-remover-condicao]'))
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_fim001').logica).toBeUndefined()
  })

  it('a nota principal não tem condição: mostra os atalhos de segmento no lugar', async () => {
    await abrir()
    const secao = painel().querySelector('[data-secao-logica]')!
    expect(secao.textContent).toContain('A nota principal sempre aparece')
    expect(secao.querySelector('[data-criar-acompanhamento]')).not.toBeNull()
    expect(secao.querySelector('[data-criar-finais]')).not.toBeNull()
    expect(secao.querySelector('select[data-fonte]')).toBeNull()
  })
})

describe('Editor 5l › regras de pular e atalhos da nota principal', () => {
  it('+ Regra: começa por "é Não" no sim/não → Fim; destino só para frente; "Senão: segue para a próxima"', async () => {
    const perguntas: Pergunta[] = [...perguntasBase(), { id: 'p_tel001', tipo: 'texto_curto', formato: 'telefone', titulo: 'Seu telefone?', obrigatoria: false }]
    const { api } = await abrir(formulario({ perguntas }))
    await selecionar('p_cont01')
    const pular = () => painel().querySelector('[data-logica-onde="pular"]')!
    expect(pular().textContent).toContain('Senão: segue para a próxima.')
    await clicar(pular().querySelector('[data-adicionar-regra]'))
    const destino = pular().querySelector<HTMLSelectElement>('[data-regra="1"] select[data-destino]')!
    expect([...destino.options].map((o) => o.textContent?.trim())).toEqual(['P5 · Seu telefone?', 'Fim da pesquisa'])
    await salvarAgora()
    let regra = pergunta(ultimoPut(api), 'p_cont01').logica!.pular![0]!
    expect(regra.id).toMatch(/^r_[A-Za-z0-9]{6}$/)
    expect(regra.se).toEqual({ juncao: 'todas', condicoes: [{ fonte: 'p_cont01', op: 'igual', valor: false }] })
    expect(regra.para).toBe('fim')

    await escolher(destino, 'p_tel001')
    await salvarAgora()
    regra = pergunta(ultimoPut(api), 'p_cont01').logica!.pular![0]!
    expect(regra.para).toBe('p_tel001')
    expect($('[data-item="p_cont01"] [data-marca-logica]')!.getAttribute('title')).toContain('Se “Podemos falar com você?” é Não → ir para “Seu telefone?”')

    // Segunda regra e reordenar
    await clicar(pular().querySelector('[data-adicionar-regra]'))
    await clicar(pular().querySelector('[aria-label="Subir a regra 2"]'))
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_cont01').logica!.pular!.map((r) => r.para)).toEqual(['fim', 'p_tel001'])
    // Remover as regras: a lógica volta a ter só o "mostrar se"
    await clicar(pular().querySelector('[data-regra="1"] [data-remover-regra]'))
    await clicar(pular().querySelector('[data-regra="1"] [data-remover-regra]'))
    await salvarAgora()
    expect(pergunta(ultimoPut(api), 'p_cont01').logica!.pular).toBeUndefined()
    expect(pergunta(ultimoPut(api), 'p_cont01').logica!.mostrar_se).toBeTruthy()
  })

  it('regra que manda para trás (depois de mover) aparece como problema na regra', async () => {
    const perguntas: Pergunta[] = [
      { id: 'p_nota01', tipo: 'nps', titulo: 'Nota?', obrigatoria: true },
      { id: 'p_a00001', tipo: 'sim_nao', titulo: 'A?', obrigatoria: false, logica: { pular: [{ id: 'r_aaaa01', se: { juncao: 'todas', condicoes: [{ fonte: 'p_a00001', op: 'igual', valor: true }] }, para: 'p_c00001' }] } },
      { id: 'p_b00001', tipo: 'comentario', titulo: 'B?', obrigatoria: false },
      { id: 'p_c00001', tipo: 'comentario', titulo: 'C?', obrigatoria: false },
    ]
    await abrir(formulario({ perguntas, finais: [] }))
    await selecionar('p_c00001')
    await teclar('ArrowUp', { altKey: true })
    await teclar('ArrowUp', { altKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_c00001', 'p_a00001', 'p_b00001'])
    await selecionar('p_a00001')
    expect(painel().querySelector('[data-regra="1"]')!.textContent).toContain('A regra 1 manda para uma pergunta que vem antes desta (só dá para pular para frente).')
  })

  it('"Criar acompanhamento por segmento" e "Criar finais por segmento" na nota principal', async () => {
    const { api } = await abrir(formulario({ perguntas: [{ id: 'p_nota01', tipo: 'nps', titulo: 'Nota?', obrigatoria: true }], finais: [] }))
    await clicar(painel().querySelector('[data-criar-acompanhamento]'))
    expect(ordem()).toHaveLength(3)
    expect(titulosNaEstrutura().slice(1)).toEqual(['O que podemos melhorar?', 'O que você mais valoriza na Transportes Rápidos?'])
    await selecionar('p_nota01')
    await clicar(painel().querySelector('[data-criar-finais]'))
    expect(ordemFinais()).toHaveLength(2)
    expect($$('[data-final] [data-condicao-final]').map((e) => e.textContent)).toEqual(['Quando NPS é promotor', 'Quando NPS é detrator'])
    await salvarAgora()
    const doc = ultimoPut(api)
    expect(doc.perguntas[1]!.logica!.mostrar_se).toEqual(g('p_nota01', 'detrator', 'neutro'))
    expect(doc.perguntas[2]!.logica!.mostrar_se).toEqual(g('p_nota01', 'promotor'))
    expect(doc.finais.map((f) => f.nome)).toEqual(['Promotores', 'Detratores'])
  })
})

describe('Editor 5l › finais', () => {
  it('adicionar, ordem (↑/↓ e arrastar) e o aviso de final sem condição acima de outros', async () => {
    const { api } = await abrir()
    await clicar($('[data-estrutura] [data-adicionar-final]'))
    expect(ordemFinais()).toHaveLength(2)
    const novo = ordemFinais()[1]!
    // Final novo começa sem condição ("pega o resto")
    expect($(`[data-final="${novo}"] [data-condicao-final]`)!.textContent).toBe('Sempre (pega o resto)')
    await vi.waitFor(() => expect(document.activeElement?.closest('[data-campo="nome"]')).not.toBeNull())
    // Subir o final sem condição: o de baixo nunca aparece
    await clicar($(`[data-final="${novo}"] [data-acao="subir"]`))
    expect(ordemFinais()).toEqual([novo, 'f_prom01'])
    expect($('[data-final="f_prom01"]')!.textContent).toContain('Nunca aparece')
    await selecionar(novo)
    expect(painel().querySelector('[data-aviso-finais-abaixo]')!.textContent).toContain('Os finais abaixo deste nunca aparecem.')
    await selecionar('f_prom01')
    expect(painel().querySelector('[data-final-escondido]')).not.toBeNull()

    // Arrastar o final de volta para baixo
    const ol = $('[data-estrutura] ol[aria-label="Finais por condição"]')!
    await vi.waitFor(() => expect(arraste.listas.some((l) => l.el === ol)).toBe(true))
    const lista = arraste.listas.find((l) => l.el === ol)!
    const item = ol.querySelector(`[data-final="${novo}"]`)!
    ol.removeChild(item)
    ol.appendChild(item)
    ;(lista.opcoes.onEnd as (e: unknown) => void)({ from: ol, to: ol, item, oldIndex: 0, newIndex: 1, oldDraggableIndex: 0, newDraggableIndex: 1 })
    await flushPromises()
    expect(ordemFinais()).toEqual(['f_prom01', novo])
    expect($('[data-final="f_prom01"]')!.textContent).not.toContain('Nunca aparece')
    await salvarAgora()
    expect(ultimoPut(api).finais.map((f) => f.id)).toEqual(['f_prom01', novo])
  })

  it('botão do final: texto e endereço https; endereço http é problema no campo', async () => {
    await abrir()
    await selecionar('f_prom01')
    await clicar(painel().querySelector('[data-campo="botao"] [role="switch"]'))
    await digitar(painel().querySelector('input[data-campo="botao.texto"]'), 'Avaliar no Google')
    await digitar(painel().querySelector('input[data-campo="botao.url"]'), 'http://g.page/x')
    await flushPromises()
    expect(painel().querySelector('[data-campo="botao"]')!.textContent).toContain('Use um endereço https:// (até 500 caracteres).')
    expect($('[data-final="f_prom01"] [data-marca-problema]')).not.toBeNull()
    await digitar(painel().querySelector('input[data-campo="botao.url"]'), 'https://g.page/x')
    await flushPromises()
    expect(painel().querySelector('[data-campo="botao"]')!.textContent).not.toContain('Use um endereço https://')
    expect($('[data-final="f_prom01"] [data-marca-problema]')).toBeNull()
  })
})

describe('Editor 5l › salvamento automático', () => {
  it('espera ~1,2 s sem mudanças para gravar (uma vez só, com o rev) e aplica o normalizado sem virar passo no desfazer', async () => {
    const { api } = await abrir()
    api.s.normalizar = (d) => {
      for (const p of d.perguntas) if (p.tipo === 'conteudo') p.html = (p.html ?? '').replace(/<script[\s\S]*?<\/script>/g, '')
      return d
    }
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    await selecionar('p_melh01')
    const titulo = painel().querySelector<HTMLInputElement>('input[data-campo="titulo"]')!
    await digitar(titulo, 'O que podemos melhorar')
    await vi.advanceTimersByTimeAsync(700)
    await digitar(titulo, 'O que podemos melhorar na entrega?')
    await vi.advanceTimersByTimeAsync(700)
    expect(api.puts()).toHaveLength(0)
    expect($('[data-salvamento]')!.textContent).toContain('Salvando…')
    await vi.advanceTimersByTimeAsync(600)
    await flushPromises()
    expect(api.puts()).toHaveLength(1)
    expect(ultimoPut(api).rev).toBe(4)
    expect(pergunta(ultimoPut(api), 'p_melh01').titulo).toBe('O que podemos melhorar na entrega?')
    await vi.waitFor(() => expect($('[data-salvamento]')!.textContent).toContain('Rascunho salvo'))
    expect($('[data-alteracoes-nao-publicadas]')).not.toBeNull()

    // Conteúdo com <script>: o servidor devolve limpo e o editor aplica (sem outro PUT, sem passo no desfazer)
    titulo.blur()
    await teclar('/')
    await clicar($('[data-menu-adicionar] [data-opcao="html"]'))
    const html = painel().querySelector<HTMLTextAreaElement>('textarea[data-campo="html"]')!
    await digitar(html, '<p>Oi</p><script>alert(1)</script>')
    html.blur()
    await vi.advanceTimersByTimeAsync(1300)
    await flushPromises()
    expect(api.puts()).toHaveLength(2)
    expect(ultimoPut(api).rev).toBe(5)
    await vi.waitFor(() => expect(painel().querySelector<HTMLTextAreaElement>('textarea[data-campo="html"]')!.value).toBe('<p>Oi</p>'))
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(api.puts()).toHaveLength(2)
  })

  it('fila: nunca dois PUT ao mesmo tempo; o segundo sai com o rev novo', async () => {
    const { api } = await abrir()
    api.s.segurar = true
    await selecionar('p_melh01')
    const titulo = painel().querySelector<HTMLInputElement>('input[data-campo="titulo"]')!
    await digitar(titulo, 'Primeira mudança')
    void teclar('s', { ctrlKey: true })
    await vi.waitFor(() => expect(api.puts()).toHaveLength(1))
    await digitar(titulo, 'Segunda mudança')
    void teclar('s', { ctrlKey: true })
    await flushPromises()
    expect(api.puts()).toHaveLength(1)
    api.soltarPut()
    await vi.waitFor(() => expect(api.puts()).toHaveLength(2))
    await flushPromises()
    expect(api.s.maxAoMesmoTempo).toBe(1)
    expect((api.puts()[1]!.corpo as { rev: number }).rev).toBe(5)
    expect(pergunta(ultimoPut(api), 'p_melh01').titulo).toBe('Segunda mudança')
    await vi.waitFor(() => expect($('[data-salvamento]')!.getAttribute('data-salvamento')).toBe('salvo'))
  })

  it('409 rascunho_desatualizado: faixa com quem salvou; Publicar desligado; "Recarregar" traz a versão do servidor', async () => {
    const { api } = await abrir()
    // Outra aba gravou: o rev do servidor andou
    api.s.f.rascunho_rev = 9
    api.s.f.rascunho = { perguntas: perguntasBase().slice(0, 1), tema: { ...TEMA_PADRAO }, finais: [], salvo_em: '2026-10-06T17:05:00Z', salvo_por_nome: 'Bruno' }
    await selecionar('p_melh01')
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'Mudança daqui')
    await salvarAgora()
    await vi.waitFor(() => expect($('[data-faixa-conflito]')).not.toBeNull())
    expect($('[data-faixa-conflito]')!.textContent).toContain('Este formulário foi alterado em outra aba ou por outra pessoa (por Bruno, às 14:05).')
    expect($<HTMLButtonElement>('[data-publicar]')!.disabled).toBe(true)
    // Mudanças novas não tentam gravar por cima
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'Outra mudança')
    await salvarAgora()
    expect(api.puts()).toHaveLength(1)

    await clicar($('[data-recarregar]'))
    expect(estadoConfirmacao.aberto).toBe(true)
    responderConfirmacao(true)
    await flushPromises()
    expect($('[data-faixa-conflito]')).toBeNull()
    expect(ordem()).toEqual(['p_nota01'])
    expect($<HTMLButtonElement>('[data-desfazer]')!.disabled).toBe(true)
    // Daqui para frente grava com o rev do servidor
    await selecionar('p_nota01')
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'Nota de 0 a 10')
    await salvarAgora()
    expect(ultimoPut(api).rev).toBe(9)
  })

  it('problemas do rascunho: aviso de citação não bloqueia; o mesmo campo com outras palavras não repete; mudou, espera a resposta', async () => {
    const { api } = await abrir()
    await selecionar('p_melh01')
    const titulo = painel().querySelector<HTMLInputElement>('input[data-campo="titulo"]')!
    await digitar(titulo, '')
    api.s.problemas = {
      'perguntas.1.titulo': 'Escreva o título.',
      'perguntas.2.descricao': 'A citação {{p_xxxx01}} não aponta para uma pergunta anterior; ela vai sair vazia.',
      perguntas: 'Este é o formulário padrão de NPS: a nota principal precisa ser NPS.',
    }
    await salvarAgora()
    await vi.waitFor(() => expect($('[data-salvamento]')!.getAttribute('data-salvamento')).toBe('salvo'))
    await clicar($('[data-botao-problemas]'))
    const textoPainel = () => $('[data-painel-problemas]')!.textContent ?? ''
    // O título vazio aparece uma vez só (a mensagem do site), a do formulário e o aviso também
    expect(textoPainel()).toContain('Escreva o título da pergunta.')
    expect(textoPainel()).not.toContain('Escreva o título.')
    expect(textoPainel()).toContain('Este é o formulário padrão de NPS')
    expect(textoPainel()).toContain('A citação {{p_xxxx01}} não aponta')
    expect($('[data-grupo-problema="item:p_moti01"]')!.textContent).toContain('A citação')
    // Mudou o documento: os do servidor esperam a próxima resposta
    await clicar($('[data-painel-problemas]')!.closest('[role="dialog"]')!.querySelector('button[aria-label="Fechar"]'))
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'Qual o principal ponto?')
    await flushPromises()
    expect($('[data-botao-problemas]')).toBeNull()
  })

  it('sem rede: "Não foi possível salvar — tentar de novo"', async () => {
    const { api } = await abrir()
    await selecionar('p_melh01')
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'Sem rede')
    const fetchOriginal = api.fetch.getMockImplementation()!
    api.fetch.mockImplementation(async (url: string | URL, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'PUT') throw new TypeError('Failed to fetch')
      return fetchOriginal(url, init)
    })
    await salvarAgora()
    await vi.waitFor(() => expect($('[data-salvamento]')!.getAttribute('data-salvamento')).toBe('erro'))
    expect($('[data-salvamento]')!.textContent).toContain('Não foi possível salvar —')
    api.fetch.mockImplementation(fetchOriginal)
    await clicar($('[data-tentar-salvar]'))
    await vi.waitFor(() => expect($('[data-salvamento]')!.getAttribute('data-salvamento')).toBe('salvo'))
    expect(pergunta(ultimoPut(api), 'p_melh01').titulo).toBe('Sem rede')
  })
})

describe('Editor 5l › publicar e descartar', () => {
  it('publicar: grava o que falta, publica com o rev e volta a "sem alterações", com a versão nova', async () => {
    const { api } = await abrir()
    await selecionar('p_melh01')
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'O que faltou?')
    await flushPromises()
    expect($('[data-alteracoes-nao-publicadas]')).not.toBeNull()
    await clicar($('[data-publicar]'))
    await vi.waitFor(() => expect(api.chamadas.some((c) => c.metodo === 'POST' && c.caminho === '/formularios/7/publicar')).toBe(true))
    const publicar = api.chamadas.find((c) => c.caminho === '/formularios/7/publicar')!
    expect(publicar.corpo).toEqual({ rev: 5 })
    // O PUT veio antes
    expect(api.chamadas.findIndex((c) => c.metodo === 'PUT')).toBeLessThan(api.chamadas.indexOf(publicar))
    await vi.waitFor(() => expect(avisos.at(-1)?.mensagem).toBe('Publicado. Quem abrir o link agora vê esta versão.'))
    expect($('[data-situacao]')!.textContent).toContain('versão 4')
    expect($('[data-alteracoes-nao-publicadas]')).toBeNull()
    expect($<HTMLButtonElement>('[data-publicar]')!.disabled).toBe(true)
    // Continuar editando grava com o rev depois da publicação
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'O que faltou para o 10?')
    await salvarAgora()
    expect(ultimoPut(api).rev).toBe(6)
  })

  it('com erro no site, Publicar abre o painel de problemas (sem chamar a API); clicar leva ao item e ao campo', async () => {
    const { api } = await abrir()
    await selecionar('p_moti01')
    await digitar(painel().querySelector('input[data-campo="titulo"]'), '')
    await flushPromises()
    expect($('[data-botao-problemas]')!.textContent).toContain('1')
    await selecionar('p_nota01')
    await clicar($('[data-publicar]'))
    await vi.waitFor(() => expect($('[data-painel-problemas]')).not.toBeNull())
    expect(api.chamadas.some((c) => c.caminho.endsWith('/publicar'))).toBe(false)
    const grupo = $('[data-grupo-problema="item:p_moti01"]')!
    expect(grupo.textContent).toContain('P3 · Pergunta sem título')
    expect(grupo.textContent).toContain('Escreva o título da pergunta.')
    await clicar(grupo.querySelector('[data-ir-problema]'))
    expect($('[data-painel-problemas]')).toBeNull()
    expect($('[data-item="p_moti01"] [data-linha]')!.getAttribute('aria-current')).toBe('true')
    await vi.waitFor(() => expect(document.activeElement?.getAttribute('data-campo')).toBe('titulo'))
  })

  it('422 ao publicar: o painel abre com os problemas do servidor; clicar seleciona o item e foca a condição', async () => {
    const { api } = await abrir()
    await selecionar('p_melh01')
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'Mudou')
    api.s.respostaPublicar = erro422('Revise o formulário.', { 'perguntas.3.logica': 'A condição 1 usa uma opção que não existe.' })
    await clicar($('[data-publicar]'))
    await vi.waitFor(() => expect($('[data-painel-problemas]')).not.toBeNull())
    const grupo = $('[data-grupo-problema="item:p_cont01"]')!
    expect(grupo.textContent).toContain('A condição 1 usa uma opção que não existe.')
    await clicar(grupo.querySelector('[data-ir-problema]'))
    expect($('[data-item="p_cont01"] [data-linha]')!.getAttribute('aria-current')).toBe('true')
    await vi.waitFor(() => expect(document.activeElement?.closest('[data-condicao="1"]')).not.toBeNull())
    expect(painel().querySelector('[data-condicao="1"] [data-erro-condicao]')!.textContent).toContain('A condição 1 usa uma opção que não existe.')
  })

  it('descartar: confirma, DELETE e volta ao publicado; Desfazer traz as alterações de volta', async () => {
    const { api } = await abrir()
    await selecionar('p_melh01')
    await clicar($('[data-item="p_melh01"] [data-acao="duplicar"]'))
    await salvarAgora()
    expect(ordem()).toHaveLength(5)
    await clicar($('[data-descartar]'))
    expect(estadoConfirmacao.titulo).toBe('Descartar as alterações?')
    responderConfirmacao(true)
    await vi.waitFor(() => expect(api.chamadas.some((c) => c.metodo === 'DELETE' && c.caminho === '/formularios/7/rascunho')).toBe(true))
    await flushPromises()
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    expect($('[data-alteracoes-nao-publicadas]')).toBeNull()
    expect(avisos.at(-1)?.mensagem).toContain('Alterações descartadas')
    await clicar($('[data-desfazer]'))
    expect(ordem()).toHaveLength(5)
    await salvarAgora()
    expect(ultimoPut(api).rev).toBe(6)
  })
})

describe('Editor 5l › desfazer, refazer e atalhos', () => {
  it('digitação no mesmo campo vira um passo só; mover é outro; Ctrl+Z, Ctrl+Shift+Z e Ctrl+Y', async () => {
    await abrir()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
    await selecionar('p_melh01')
    const titulo = () => painel().querySelector<HTMLInputElement>('input[data-campo="titulo"]')!
    await digitar(titulo(), 'O que')
    await vi.advanceTimersByTimeAsync(100)
    await digitar(titulo(), 'O que faltou')
    await vi.advanceTimersByTimeAsync(100)
    await digitar(titulo(), 'O que faltou?')
    titulo().blur()
    await vi.advanceTimersByTimeAsync(1000)
    await teclar('ArrowDown', { altKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_moti01', 'p_melh01', 'p_cont01'])

    await teclar('z', { ctrlKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    expect(titulo().value).toBe('O que faltou?')
    await teclar('z', { ctrlKey: true })
    expect(titulo().value).toBe('O que podemos melhorar?')
    expect($<HTMLButtonElement>('[data-desfazer]')!.disabled).toBe(true)

    await teclar('z', { ctrlKey: true, shiftKey: true })
    expect(titulo().value).toBe('O que faltou?')
    await teclar('y', { ctrlKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_moti01', 'p_melh01', 'p_cont01'])
    expect($<HTMLButtonElement>('[data-refazer]')!.disabled).toBe(true)
    // Botões também
    await clicar($('[data-desfazer]'))
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    await clicar($('[data-refazer]'))
    expect(ordem()).toEqual(['p_nota01', 'p_moti01', 'p_melh01', 'p_cont01'])
  })

  it('desfazer volta também a seleção; excluir e desfazer traz o item e as condições', async () => {
    await abrir()
    await selecionar('p_moti01')
    await clicar($('[data-item="p_moti01"] [data-acao="excluir"]'))
    responderConfirmacao(true)
    await flushPromises()
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_cont01'])
    await teclar('z', { metaKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    expect($('[data-item="p_cont01"] [data-marca-logica]')).not.toBeNull()
    expect($('[data-item="p_moti01"] [data-linha]')!.getAttribute('aria-current')).toBe('true')
  })

  it('"?" abre a ajuda dos atalhos; "/" e "?" dentro de um campo são texto; com janela aberta, atalhos ficam quietos', async () => {
    await abrir()
    await teclar('?')
    const dialogo = $('[role="dialog"]')!
    expect(dialogo.textContent).toContain('Atalhos do teclado')
    expect(dialogo.textContent).toContain('Desfazer')
    // Com a ajuda aberta, "/" não abre o menu de adicionar
    await teclar('/')
    expect($('[data-menu-adicionar]')).toBeNull()
    await teclar('Escape', {}, dialogo)
    await flushPromises()
    const titulo = painel().querySelector<HTMLInputElement>('input[data-campo="titulo"]')!
    titulo.focus()
    await teclar('/', {}, titulo)
    expect($('[data-menu-adicionar]')).toBeNull()
  })

  it('sem permissão de editar: nada de atalhos, ações ou salvamento', async () => {
    const { api } = await abrir(formulario(), ['formularios.ver'])
    expect(document.body.textContent).toContain('Seu perfil pode ver este formulário, mas não editar.')
    expect($('[data-publicar]')).toBeNull()
    expect($('[data-estrutura] [data-adicionar]')).toBeNull()
    expect($('[data-estrutura] [data-alca]')).toBeNull()
    await teclar('/')
    expect($('[data-menu-adicionar]')).toBeNull()
    await teclar('ArrowDown', { altKey: true })
    expect(ordem()).toEqual(['p_nota01', 'p_melh01', 'p_moti01', 'p_cont01'])
    await salvarAgora()
    expect(api.puts()).toHaveLength(0)
  })
})

describe('Editor 5l › prévia seguindo o item', () => {
  const previa = () => $('[data-coluna-previa]')!

  it('mostra o item selecionado; item escondido vem com a faixa do motivo; final mostra a tela final', async () => {
    await abrir()
    await vi.waitFor(() => expect(previa().querySelector('[data-titulo-pergunta]')).not.toBeNull())
    expect(previa().textContent).toContain('Quanto você recomendaria a Transportes Rápidos?')

    await selecionar('p_melh01')
    await vi.waitFor(() => expect(previa().textContent).toContain('O que podemos melhorar?'))
    expect(previa().querySelector('[data-faixa-foco]')!.textContent).toContain('Na pesquisa, este item só aparece quando: NPS é detrator ou neutro')

    await selecionar('f_prom01')
    await vi.waitFor(() => expect(previa().querySelector('[data-tela-final]')).not.toBeNull())
    expect(previa().querySelector('[data-tela-final]')!.getAttribute('data-final')).toBe('f_prom01')
    expect(previa().textContent).toContain('Obrigado por recomendar!')
    expect(previa().querySelector('[data-faixa-foco]')!.textContent).toContain('Este final aparece quando: NPS é promotor')

    await clicar($('[data-final-padrao] [data-linha]'))
    await vi.waitFor(() => expect(previa().querySelector('[data-tela-final]')!.getAttribute('data-final')).toBe('padrao'))
    expect(previa().querySelector('[data-faixa-foco]')!.textContent).toContain('Este final aparece quando nenhum outro final vale.')
  })

  it('mudar o título aparece na prévia na hora; Celular/Computador e Reiniciar', async () => {
    await abrir()
    await selecionar('p_moti01')
    await digitar(painel().querySelector('input[data-campo="titulo"]'), 'Por que essa nota?')
    await vi.waitFor(() => expect(previa().textContent).toContain('Por que essa nota?'))
    await clicar(previa().querySelector('[data-aparelho-opcao="computador"]'))
    expect(previa().querySelector('[data-aparelho-atual]')!.getAttribute('data-aparelho-atual')).toBe('computador')
    // Reiniciar volta para o começo, como quem abre o link
    await clicar(previa().querySelector('[data-reiniciar]'))
    await vi.waitFor(() => expect(previa().textContent).toContain('Pergunta 1 de 2'))
    expect(previa().textContent).toContain('Quanto você recomendaria a Transportes Rápidos?')
  })
})
