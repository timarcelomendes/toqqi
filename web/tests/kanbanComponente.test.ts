import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { Acao } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import PlanosAcaoView from '@/modulos/acoes/PlanosAcaoView.vue'
import { apiFalsa, erro422 } from './apiFalsa'

const HOJE = hojeIso()

function acao(id: number, extra: Partial<Acao> = {}): Acao {
  return {
    id,
    titulo: `Ação ${id}`,
    descricao: '',
    resolucao: null,
    situacao: 'a_fazer',
    prioridade: 'media',
    prazo: null,
    prazo_selo: null,
    empresa: { id: 1, nome: 'Mercado Bom Preço' },
    contato: null,
    responsavel: { id: 7, nome: 'Carla Ribeiro', email: 'carla@x.com', foto_url: null },
    resposta: null,
    origem: 'manual',
    grupo: null,
    tipo_nota: null,
    nota: null,
    criada_em: '2026-09-20T10:00:00-03:00',
    atualizada_em: '2026-09-20T10:00:00-03:00',
    iniciada_em: null,
    concluida_em: null,
    criado_por: null,
    concluida_por: null,
    ...extra,
  }
}

let acoes: Acao[]
let router: Router

function quadro() {
  return {
    colunas: {
      a_fazer: acoes.filter((a) => a.situacao === 'a_fazer'),
      em_andamento: acoes.filter((a) => a.situacao === 'em_andamento'),
      concluida: acoes.filter((a) => a.situacao === 'concluida'),
    },
    totais: { a_fazer: acoes.filter((a) => a.situacao === 'a_fazer').length, em_andamento: acoes.filter((a) => a.situacao === 'em_andamento').length, concluida: 20, vencidas: 1 },
  }
}

function api(extra: Record<string, Parameters<typeof apiFalsa>[0][string]> = {}) {
  return apiFalsa({
    'GET /acoes/quadro': () => quadro(),
    // antes de "GET /acoes/:id": a primeira rota que casa responde
    'GET /acoes/panorama': () => ({
      prazos: { abertas: 3, vencidas: 1, hoje: 0, proximos_7_dias: 2, depois: 0, sem_prazo: 0 },
      responsaveis: [{ responsavel: { id: 7, nome: 'Carla Ribeiro' }, abertas: 3, vencidas: 1 }],
      concluidas: { de: '2026-09-09', ate: '2026-10-08', total: 20, mediana_dias: 3, com_retorno: 5, anterior: { de: '2026-08-10', ate: '2026-09-08', total: 12, mediana_dias: 4, com_retorno: 2 } },
    }),
    'GET /responsaveis': () => [{ id: 7, nome: 'Carla Ribeiro', funcao: null, email: null, foto_url: null, teams_webhook: null, empresas: 3 }],
    'GET /cadastros/grupos': () => [],
    'PATCH /acoes/:id': ({ caminho, corpo }) => {
      const a = acoes.find((x) => `/acoes/${x.id}` === caminho)!
      Object.assign(a, corpo)
      return a
    },
    'GET /acoes/:id': ({ caminho }) => acoes.find((x) => `/acoes/${x.id}` === caminho),
    ...extra,
  })
}

async function abrir(caminho = '/planos-de-acao'): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/planos-de-acao/:id?', name: 'planos-de-acao', component: PlanosAcaoView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const App = defineComponent({ render: () => h(RouterView) })
  const w = mount(App, { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return w
}

const coluna = (w: VueWrapper, s: string) => w.get(`#coluna-${s}`)
const cartao = (w: VueWrapper, titulo: string) => w.findAll('article').find((a) => a.text().includes(titulo))!

beforeEach(() => {
  setActivePinia(createPinia())
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'gestor', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes: ['acoes.ver', 'acoes.tratar', 'acoes.excluir', 'contatos.ver'],
    },
    false,
  )
  acoes = [
    acao(1, { prazo: somarDias(HOJE, -3), prazo_selo: 'vencido', prioridade: 'alta' }),
    acao(2, { resolucao: 'Liguei e resolvi.' }),
    acao(3, { situacao: 'em_andamento', responsavel: null }),
  ]
})

// Desmonta a tela de cada teste (senão a recarga agendada de um teste dispara no seguinte).
enableAutoUnmount(afterEach)

afterEach(() => {
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
  localStorage.clear()
  sessionStorage.clear()
})

describe('quadro de planos de ação', () => {
  it('mostra as três colunas com os totais e o selo do prazo', async () => {
    api()
    const w = await abrir()
    expect(coluna(w, 'a_fazer').text()).toContain('Ação 1')
    expect(coluna(w, 'em_andamento').text()).toContain('Ação 3')
    expect(cartao(w, 'Ação 1').text()).toContain('Prazo vencido')
    expect(cartao(w, 'Ação 3').text()).toContain('Sem responsável')
    expect(w.text()).toContain('Ver todas as concluídas (20)')
  })

  it('"Mover para…" (teclado e toque) muda a coluna e grava a situação', async () => {
    const { chamadas } = api()
    const w = await abrir()
    const c = cartao(w, 'Ação 2')
    await c.get('button[aria-haspopup="menu"]').trigger('click')
    const item = c.findAll('[role="menuitem"]').find((i) => i.text() === 'Em andamento')!
    await item.trigger('click')
    await flushPromises()
    expect(chamadas.find((x) => x.metodo === 'PATCH')).toMatchObject({ caminho: '/acoes/2', corpo: { situacao: 'em_andamento' } })
    expect(coluna(w, 'em_andamento').text()).toContain('Ação 2')
    expect(coluna(w, 'a_fazer').text()).not.toContain('Ação 2')
  })

  it('computador: depois de mover pelo menu, o foco vai para o cartão na coluna nova e o leitor de tela ouve', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
    api()
    const w = await abrir()
    const c = cartao(w, 'Ação 2')
    await c.get('button[aria-haspopup="menu"]').trigger('click')
    await c.findAll('[role="menuitem"]').find((i) => i.text() === 'Em andamento')!.trigger('click')
    await flushPromises()
    const foco = document.activeElement as HTMLElement
    expect(foco.textContent?.trim()).toBe('Ação 2')
    expect(coluna(w, 'em_andamento').element.contains(foco)).toBe(true)
    expect(w.find('[aria-live="polite"]').text()).toBe('Ação movida para Em andamento: Ação 2.')
  })

  it('celular: o foco fica na coluna atual (no cartão seguinte) ou vai para a aba de destino', async () => {
    api()
    const w = await abrir()
    // A fazer tem Ação 1 e Ação 2: movendo a Ação 1, o foco vai para a Ação 2 (que ficou no lugar dela).
    let c = cartao(w, 'Ação 1')
    acoes[0]!.responsavel = { id: 7, nome: 'Carla Ribeiro', email: null, foto_url: null }
    await c.get('button[aria-haspopup="menu"]').trigger('click')
    await c.findAll('[role="menuitem"]').find((i) => i.text() === 'Em andamento')!.trigger('click')
    await flushPromises()
    expect((document.activeElement as HTMLElement).textContent?.trim()).toBe('Ação 2')
    expect(avisos.at(-1)?.mensagem).toBe('Ação movida para Em andamento.')
    // Agora a última: a coluna fica vazia e o foco vai para a aba "Em andamento".
    c = cartao(w, 'Ação 2')
    await c.get('button[aria-haspopup="menu"]').trigger('click')
    await c.findAll('[role="menuitem"]').find((i) => i.text() === 'Em andamento')!.trigger('click')
    await flushPromises()
    expect(document.activeElement?.id).toBe('aba-coluna-em_andamento')
  })

  it('arrastar e soltar entre colunas (computador)', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
    const { chamadas } = api()
    const w = await abrir()
    const arrastar = (tipo: string) => {
      const e = new Event(tipo, { bubbles: true, cancelable: true })
      Object.defineProperty(e, 'dataTransfer', { value: { setData: vi.fn(), effectAllowed: '', dropEffect: '' } })
      return e
    }
    const card = cartao(w, 'Ação 2')
    expect(card.attributes('draggable')).toBe('true')
    card.element.dispatchEvent(arrastar('dragstart'))
    await flushPromises()
    coluna(w, 'concluida').element.dispatchEvent(arrastar('dragover'))
    await flushPromises()
    expect(coluna(w, 'concluida').classes()).toContain('border-marca')
    coluna(w, 'concluida').element.dispatchEvent(arrastar('drop'))
    await flushPromises()
    expect(chamadas.find((x) => x.metodo === 'PATCH')).toMatchObject({ caminho: '/acoes/2', corpo: { situacao: 'concluida' } })
    expect(coluna(w, 'concluida').text()).toContain('Ação 2')
  })

  it('concluir sem o que foi feito não grava: abre o painel com o campo e o aviso na hora', async () => {
    const { chamadas } = api()
    const w = await abrir()
    const c = cartao(w, 'Ação 1')
    await c.get('button[aria-haspopup="menu"]').trigger('click')
    await c.findAll('[role="menuitem"]').find((i) => i.text() === 'Concluído')!.trigger('click')
    await flushPromises()
    expect(chamadas.some((x) => x.metodo === 'PATCH')).toBe(false)
    expect(router.currentRoute.value.params.id).toBe('1')
    expect(w.text()).toContain('Para concluir, falta pouco')
    expect(w.text()).toContain('Conte o que foi feito para concluir.')
    const resolucao = w.findAll('textarea').find((t) => t.element.closest('div')?.textContent?.includes('O que foi feito'))
    expect(resolucao?.exists()).toBe(true)

    // Preenchendo e concluindo pelo painel, grava tudo de uma vez.
    await resolucao!.setValue('Liguei, pedi desculpas e combinei aviso antes da entrega.')
    expect(w.text()).not.toContain('Conte o que foi feito para concluir.')
    await w.get('#painel-acao-form').trigger('submit')
    await flushPromises()
    expect(chamadas.find((x) => x.metodo === 'PATCH')).toMatchObject({
      corpo: { situacao: 'concluida', resolucao: 'Liguei, pedi desculpas e combinei aviso antes da entrega.' },
    })
    // Concluiu: o painel fecha e a ação está em Concluído.
    expect(router.currentRoute.value.params.id ?? '').toBe('')
    expect(coluna(w, 'concluida').text()).toContain('Ação 1')
  })

  it('recusou porque a ação mudou em outra sessão: busca de novo e cartão e painel mostram o que vale', async () => {
    const { chamadas } = api({
      'PATCH /acoes/:id': () => erro422('Para concluir, falta informação.', { responsavel_id: 'Escolha o responsável antes de concluir.' }),
    })
    const w = await abrir()
    // Em outra sessão, tiraram o responsável da Ação 2 (o quadro ainda mostra o antigo).
    acoes[1]!.responsavel = null
    expect(cartao(w, 'Ação 2').text()).toContain('Carla Ribeiro')
    const c = cartao(w, 'Ação 2')
    await c.get('button[aria-haspopup="menu"]').trigger('click')
    await c.findAll('[role="menuitem"]').find((i) => i.text() === 'Concluído')!.trigger('click')
    await flushPromises()
    expect(chamadas.some((x) => x.metodo === 'GET' && x.caminho === '/acoes/2')).toBe(true)
    expect(cartao(w, 'Ação 2').text()).toContain('Sem responsável')
    const select = w.get('#campo-responsavel-acao select').element as HTMLSelectElement
    expect(select.value).toBe('')
    expect(w.text()).toContain('Escolha o responsável antes de concluir.')
  })

  it('salvar no painel recusado: busca de novo, mantém o que a pessoa mudou e o aviso do servidor', async () => {
    let tentativas = 0
    const { chamadas } = api({
      'PATCH /acoes/:id': () => {
        tentativas++
        return erro422('Para concluir, falta informação.', { responsavel_id: 'Escolha o responsável antes de concluir.' })
      },
    })
    const w = await abrir('/planos-de-acao/2')
    acoes[1]!.responsavel = null
    const descricao = w.findAll('textarea').find((t) => t.element.closest('div')?.textContent?.includes('Descrição'))!
    await descricao.setValue('Combinar visita na terça.')
    await w.get('#painel-acao-form select').setValue('concluida')
    await w.get('#painel-acao-form').trigger('submit')
    await flushPromises()
    expect(tentativas).toBe(1)
    expect(chamadas.some((x) => x.metodo === 'GET' && x.caminho === '/acoes/2')).toBe(true)
    // O que a pessoa mudou continua; o responsável (que ela não mexeu) mostra o valor atual.
    expect((descricao.element as HTMLTextAreaElement).value).toBe('Combinar visita na terça.')
    expect((w.get('#painel-acao-form select').element as HTMLSelectElement).value).toBe('concluida')
    expect((w.get('#campo-responsavel-acao select').element as HTMLSelectElement).value).toBe('')
    expect(w.text()).toContain('Escolha o responsável antes de concluir.')
    expect(cartao(w, 'Ação 2').text()).toContain('Sem responsável')
  })

  it('se o servidor recusar (422), a ação volta e o painel mostra o que ele pediu', async () => {
    const { chamadas } = api({
      'PATCH /acoes/:id': () => erro422('Para concluir, falta informação.', { responsavel_id: 'Escolha o responsável antes de concluir.' }),
    })
    const w = await abrir()
    const c = cartao(w, 'Ação 2')
    await c.get('button[aria-haspopup="menu"]').trigger('click')
    await c.findAll('[role="menuitem"]').find((i) => i.text() === 'Concluído')!.trigger('click')
    await flushPromises()
    expect(chamadas.filter((x) => x.metodo === 'PATCH')).toHaveLength(1)
    expect(coluna(w, 'a_fazer').text()).toContain('Ação 2')
    expect(coluna(w, 'concluida').text()).not.toContain('Ação 2')
    expect(w.text()).toContain('Escolha o responsável antes de concluir.')
  })

  it('com a ação mudada e não salva, "Ver a resposta completa" pergunta antes de sair', async () => {
    useSessaoStore().permissoes = [...useSessaoStore().permissoes, 'respostas.ver']
    acoes[1] = acao(2, { resposta: { id: 55, nota: 3, tipo_nota: 'nps', grupo: 'detrator', comentario: 'Atrasou.', data: '2026-09-28T10:00:00-03:00' } })
    api()
    const w = await abrir('/planos-de-acao/2')
    await w.get('#painel-acao-form input').setValue('Ação 2 (mudada)')
    const link = w.get('[role="dialog"]').findAll('a').find((a) => a.text().includes('Ver a resposta completa'))!
    await link.trigger('click')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    responderConfirmacao(false)
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/planos-de-acao/2')
  })

  it('o link direto /planos-de-acao/:id abre o painel da ação', async () => {
    api()
    const w = await abrir('/planos-de-acao/3')
    expect(w.find('[role="dialog"]').exists()).toBe(true)
    expect(w.get('[role="dialog"]').text()).toContain('Ação 3')
    expect((w.get('#painel-acao-form input').element as HTMLInputElement).value).toBe('Ação 3')
  })

  it('link para uma ação que não existe mais avisa e volta para o quadro', async () => {
    api({ 'GET /acoes/:id': () => new Response(JSON.stringify({ erro: { codigo: 'nao_encontrado', mensagem: 'x' } }), { status: 404 }) })
    await abrir('/planos-de-acao/999')
    await flushPromises()
    expect(avisos.some((a) => a.mensagem.includes('não existe mais'))).toBe(true)
    expect(router.currentRoute.value.params.id ?? '').toBe('')
  })

  it('filtros vão para o endereço e para a API; tipo CSAT tira a categoria "detrator"', async () => {
    const { chamadas } = api()
    const w = await abrir('/planos-de-acao?categoria=detrator&so_vencidas=true')
    const quadros = () => chamadas.filter((c) => c.caminho === '/acoes/quadro')
    expect(Object.fromEntries(quadros().at(-1)!.url.searchParams)).toEqual({ categoria: 'detrator', so_vencidas: 'true' })
    const label = w.findAll('label').find((l) => l.text() === 'Tipo de pesquisa')!
    await w.get(`[id="${label.attributes('for')}"]`).setValue('csat')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tipo_nota: 'csat', so_vencidas: 'true' })
    expect(Object.fromEntries(quadros().at(-1)!.url.searchParams)).toEqual({ tipo_nota: 'csat', so_vencidas: 'true' })
  })

  it('resumo do topo: segue os filtros, busca de novo a cada carga do quadro e filtra por responsável e por vencidas', async () => {
    const { chamadas } = api()
    const w = await abrir('/planos-de-acao?categoria=detrator')
    const panoramas = () => chamadas.filter((c) => c.caminho === '/acoes/panorama')
    expect(panoramas()).toHaveLength(1)
    expect(Object.fromEntries(panoramas()[0]!.url.searchParams)).toEqual({ categoria: 'detrator' })
    expect(w.get('[data-manchete-acoes]').text()).toContain('1 de 3 ações abertas está vencida')
    // clicar na pessoa filtra o quadro (e o resumo) por ela
    await w.get('[data-pessoa="7"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ categoria: 'detrator', responsavel_id: '7' })
    expect(Object.fromEntries(panoramas().at(-1)!.url.searchParams)).toEqual({ categoria: 'detrator', responsavel_id: '7' })
    // "1 vencida" liga o "Só vencidas" do quadro
    await w.get('[data-legenda-prazo="vencidas"] button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toMatchObject({ so_vencidas: 'true' })
    expect(w.findAll('button').find((b) => b.text().includes('Só vencidas'))!.attributes('aria-pressed')).toBe('true')
  })

  it('sem acoes.tratar, não dá para mover nem criar', async () => {
    useSessaoStore().permissoes = ['acoes.ver']
    api()
    const w = await abrir()
    expect(w.find('button[aria-haspopup="menu"]').exists()).toBe(false)
    expect(w.text()).not.toContain('Nova ação')
  })
})
