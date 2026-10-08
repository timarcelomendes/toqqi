// Triagem de Respostas (docs/api-respostas-triagem.md): "Todas", "Para analisar" e "Com comentário" no endereço e na
// API, as contagens, o "Do que falam" (temas citados, com a parte de nota baixa) e o vazio de "Para analisar".
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { MetricasRespostas, RespostaItem } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import RespostasView from '@/modulos/respostas/RespostasView.vue'
import { FILTROS_PADRAO, contagemVisao, filtrosDaQuery, filtrosParaApi, queryDosFiltros, temasCitados } from '@/modulos/respostas/logica'
import { apiFalsa, type Chamada } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
function textos(alvo: { element: Element }): string {
  const partes: string[] = []
  const passeio = document.createTreeWalker(alvo.element, NodeFilter.SHOW_TEXT)
  for (let n = passeio.nextNode(); n; n = passeio.nextNode()) {
    const s = t(n.textContent ?? '')
    if (s) partes.push(s)
  }
  return partes.join(' ')
}

const METRICAS: MetricasRespostas = {
  nps: { valor: 33, faixa: 'pode_melhorar', promotores: 57, neutros: 27, detratores: 22, total: 106 },
  csat: null,
  total: 106,
  para_analisar: 34,
  com_comentario: 25,
  temas: [
    { chave: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 6, nota_baixa: 3 },
    { chave: 'atendimento', rotulo: 'Atendimento', mencoes: 5, nota_baixa: 0 },
    { chave: 'preco_condicoes', rotulo: 'Preço e condições', mencoes: 4, nota_baixa: 4 },
    { chave: 'produto_avarias', rotulo: 'Produto e avarias', mencoes: 3, nota_baixa: 2 },
  ],
}

describe('Respostas › triagem: regras', () => {
  it('a visão vai e volta do endereço e vira o filtro da API', () => {
    expect(filtrosDaQuery({ visao: 'para_analisar' }).visao).toBe('para_analisar')
    expect(filtrosDaQuery({ visao: 'qualquer' }).visao).toBe('todas')
    expect(queryDosFiltros({ ...FILTROS_PADRAO, visao: 'com_comentario' })).toEqual({ visao: 'com_comentario' })
    expect(queryDosFiltros({ ...FILTROS_PADRAO, visao: 'todas' })).toEqual({})
    expect(filtrosParaApi({ ...FILTROS_PADRAO, visao: 'para_analisar' }, '2026-10-08')).toEqual({ arquivadas: 'false', pagina: 1, para_analisar: true })
    expect(filtrosParaApi({ ...FILTROS_PADRAO, visao: 'com_comentario' }, '2026-10-08')).toEqual({ arquivadas: 'false', pagina: 1, com_comentario: true })
  })

  it('a contagem de cada visão vem das métricas (que não levam a visão em conta)', () => {
    expect(['todas', 'para_analisar', 'com_comentario'].map((v) => contagemVisao(v as 'todas', METRICAS))).toEqual([106, 34, 25])
    expect(contagemVisao('para_analisar', { total: 3 })).toBeNull()
    expect(contagemVisao('todas', null)).toBeNull()
  })

  it('temas citados: a barra pelo mais citado, a parte de nota baixa e o nome da conta', () => {
    expect(temasCitados(METRICAS, [{ chave: 'prazo_entrega', rotulo: 'Prazo de entrega' }]).map((x) => [x.rotulo, x.largura, x.parteBaixa, x.detalhe])).toEqual([
      ['Prazo de entrega', 100, 50, '3 com nota baixa'],
      ['Atendimento', 83, 0, 'Nenhuma com nota baixa'],
      ['Preço e condições', 67, 100, '4 com nota baixa'],
      ['Produto e avarias', 50, 67, '2 com nota baixa'],
    ])
    expect(temasCitados(null)).toEqual([])
    expect(temasCitados({ temas: [] })).toEqual([])
  })
})

// ── Componente ──────────────────────────────────────────────────────────────

function resposta(id: number, extra: Partial<RespostaItem> = {}): RespostaItem {
  return {
    id,
    formulario: { id: 1, nome: 'Pesquisa' },
    contato: { id: 100 + id, nome: `Cliente ${id}`, email: null, perfil: null },
    empresa: { id: 14, nome: 'Mercado Bom Preço', grupo: null },
    canal: 'email',
    nota: 3,
    tipo_nota: 'nps',
    grupo: 'detrator',
    comentario: 'A entrega atrasou.',
    respostas: {},
    contexto: {},
    referencia: null,
    criada_em: '2026-09-28T10:00:00-03:00',
    data: '2026-09-28T10:00:00-03:00',
    respondida_em: '2026-09-28T10:00:00-03:00',
    origem: 'pesquisa',
    temas: ['prazo_entrega'],
    temas_manuais: false,
    o_que_faltou: null,
    o_que_combinamos: null,
    analisada_em: null,
    analisada_por: null,
    registrada_por: null,
    arquivada: false,
    acao: null,
    ...extra,
  } as RespostaItem
}

let router: Router
async function abrir(rotas: Parameters<typeof apiFalsa>[0], caminho = '/respostas'): Promise<{ w: VueWrapper; chamadas: Chamada[] }> {
  const { chamadas } = apiFalsa({ 'GET /respostas/temas': () => [], 'GET /cadastros/grupos': () => [], 'GET /cadastros/perfis': () => [], ...rotas })
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/respostas', name: 'respostas', component: RespostasView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const App = defineComponent({ render: () => h(RouterView) })
  const w = mount(App, { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return { w, chamadas }
}
const buscas = (c: Chamada[]) => c.filter((x) => x.metodo === 'GET' && x.caminho === '/respostas')
const consulta = (c: Chamada | undefined) => Object.fromEntries(c?.url.searchParams ?? [])

beforeEach(() => {
  setActivePinia(createPinia())
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'gestor', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes: ['respostas.ver', 'respostas.editar', 'contatos.ver', 'acoes.ver'],
    },
    false,
  )
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('Respostas › triagem: tela', () => {
  it('mostra as visões com a contagem; escolher uma vai para o endereço e para a API', async () => {
    const { w, chamadas } = await abrir({
      'GET /respostas': ({ url }) => ({
        itens: url.searchParams.get('para_analisar') ? [resposta(1)] : [resposta(1), resposta(2, { nota: 9, grupo: 'promotor', comentario: '', temas: [] })],
        total: url.searchParams.get('para_analisar') ? 1 : 2,
        pagina: 1,
        por_pagina: 50,
        metricas: METRICAS,
      }),
    })
    expect(w.findAll('[data-visao]').map((b) => [textos(b), b.attributes('aria-pressed')])).toEqual([
      ['Todas 106', 'true'],
      ['Para analisar 34', 'false'],
      ['Com comentário 25', 'false'],
    ])
    await w.get('[data-visao="para_analisar"]').trigger('click')
    await flushPromises()
    expect(consulta(buscas(chamadas).at(-1))).toMatchObject({ para_analisar: 'true' })
    expect(router.currentRoute.value.query).toMatchObject({ visao: 'para_analisar' })
    expect(w.get('[data-visao="para_analisar"]').attributes('aria-pressed')).toBe('true')
    // "Limpar filtros" (da área Filtros) não tira a visão
    expect(w.find('[data-vazio-analisar]').exists()).toBe(false)
  })

  it('"Do que falam": os temas com a parte de nota baixa e a legenda; um clique filtra pelo tema, outro tira', async () => {
    const { w, chamadas } = await abrir({ 'GET /respostas': () => ({ itens: [resposta(1)], total: 1, pagina: 1, por_pagina: 50, metricas: METRICAS }) })
    const temas = w.findAll('[data-tema]')
    expect(temas.map((x) => textos(x))).toEqual([
      'Prazo e entrega 6 menções 3 com nota baixa',
      'Atendimento 5 menções Nenhuma com nota baixa',
      'Preço e condições 4 menções 4 com nota baixa',
      'Produto e avarias 3 menções 2 com nota baixa',
    ])
    expect(textos(w.get('[data-legenda-temas]'))).toBe('Com nota baixa As outras')
    // no celular, só os 3 primeiros (o 4º fica escondido até "Ver mais 1 tema")
    expect(temas[3]!.element.closest('li')!.className).toContain('hidden sm:block')
    const ver = w.findAll('button').find((b) => t(b.text()) === 'Ver mais 1 tema')!
    await ver.trigger('click')
    expect(w.findAll('[data-tema]')[3]!.element.closest('li')!.className).not.toContain('hidden')
    await temas[0]!.trigger('click')
    await flushPromises()
    expect(consulta(buscas(chamadas).at(-1))).toMatchObject({ tema: 'prazo_entrega' })
    expect(w.get('[data-tema="prazo_entrega"]').attributes('aria-pressed')).toBe('true')
    await w.get('[data-tema="prazo_entrega"]').trigger('click')
    await flushPromises()
    expect(consulta(buscas(chamadas).at(-1)).tema).toBeUndefined()
  })

  it('sem temas, sem o bloco; "Para analisar" vazio é boa notícia, com "Ver todas as respostas"', async () => {
    const { w } = await abrir(
      { 'GET /respostas': () => ({ itens: [], total: 0, pagina: 1, por_pagina: 50, metricas: { ...METRICAS, para_analisar: 0, temas: [] } }) },
      '/respostas?visao=para_analisar',
    )
    expect(w.find('[data-temas-citados]').exists()).toBe(false)
    expect(textos(w.get('[data-vazio-analisar]'))).toContain('Nada para analisar')
    await w.findAll('button').find((b) => t(b.text()) === 'Ver todas as respostas')!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.visao).toBeUndefined()
  })
})
