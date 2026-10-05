import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type {
  HistoricoEmpresa,
  NpsResumo,
  Perfil,
  RelatorioEmpresas,
  RelatorioEntregas,
  RelatorioGrupos,
  RelatorioOperacao,
  RelatorioResponsaveis,
  RelatorioTemas,
} from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import RelatoriosView from '@/modulos/relatorios/RelatoriosView.vue'
import { apiFalsa, type Chamada } from './apiFalsa'

const HOJE = hojeIso()

function bloco(p: number, n: number, d: number): NpsResumo {
  const total = p + n + d
  const valor = total ? Math.round(((p - d) * 100) / total) : null
  const faixa = valor === null ? null : valor >= 75 ? 'excelente' : valor >= 50 ? 'muito_bom' : valor >= 0 ? 'pode_melhorar' : 'critico'
  return { valor, faixa, promotores: p, neutros: n, detratores: d, total }
}

function relEmpresas(extra: Partial<RelatorioEmpresas> = {}): RelatorioEmpresas {
  return {
    resumo: {
      empresas: 3,
      com_respostas: 2,
      cobertura: { contatos_ativos: 10, responderam: 6, percentual: 60 },
      receita: { total: '35000.00', em_risco: '20000.00', empresas_em_risco: 1, sem_valor: 0, percentual: 57.1 },
      por_faixa: { excelente: 1, muito_bom: 0, pode_melhorar: 0, critico: 1, sem_respostas: 1 },
    },
    matriz: {
      mediana_valor: '17500.00',
      quadrantes: { proteger: 1, manter: 0, corrigir: 0, crescer: 1 },
      pontos: [
        { empresa: { id: 11, nome: 'Mercado Bom Preço' }, nps: -50, valor_mensal: '20000.00', respostas: 4, quadrante: 'proteger' },
        { empresa: { id: 12, nome: 'Atacadão do Vale' }, nps: 75, valor_mensal: '15000.00', respostas: 4, quadrante: 'crescer' },
      ],
      sem_valor: 0,
    },
    itens: [
      {
        empresa: { id: 11, nome: 'Mercado Bom Preço', ativa: true },
        grupo: { id: 2, nome: 'Varejo' },
        segmento: null,
        responsavel: { id: 1, nome: 'Carla Ribeiro' },
        valor_mensal: '20000.00',
        cliente_desde: '2024-01-10',
        nps: bloco(1, 0, 3),
        cobertura: { contatos_ativos: 4, responderam: 2, percentual: 50 },
        ultima_resposta: { data: '2026-09-28T10:00:00-03:00', nota: 3, tipo_nota: 'nps' },
        em_risco: true,
        quadrante: 'proteger',
        acoes_abertas: 2,
      },
      {
        empresa: { id: 12, nome: 'Atacadão do Vale', ativa: true },
        grupo: null,
        segmento: { id: 3, nome: 'Supermercados' },
        responsavel: null,
        valor_mensal: 15000,
        cliente_desde: null,
        nps: bloco(3, 1, 0),
        cobertura: { contatos_ativos: 4, responderam: 4, percentual: 100 },
        ultima_resposta: { data: '2026-09-20T10:00:00-03:00', nota: 10, tipo_nota: 'nps' },
        em_risco: false,
        quadrante: 'crescer',
        acoes_abertas: 0,
      },
      {
        empresa: { id: 13, nome: 'Padaria Pão Quente', ativa: false },
        grupo: null,
        segmento: null,
        responsavel: null,
        valor_mensal: null,
        cliente_desde: null,
        nps: bloco(0, 0, 0),
        cobertura: { contatos_ativos: 2, responderam: 0, percentual: 0 },
        ultima_resposta: null,
        em_risco: false,
        quadrante: null,
        acoes_abertas: 0,
      },
    ],
    total: 3,
    pagina: 1,
    por_pagina: 50,
    ...extra,
  }
}

function relGrupos(): RelatorioGrupos {
  const linha = (p: number, n: number, d: number, empresas: number) => ({ empresas, nps: bloco(p, n, d) })
  return {
    segmentos: [{ segmento: { id: 1, nome: 'Supermercados' }, ...linha(1, 1, 3, 2) }, { segmento: null, ...linha(2, 0, 0, 1) }],
    grupos: [{ grupo: { id: 2, nome: 'Varejo' }, ...linha(3, 1, 3, 3) }],
    tempo_cliente: [
      { faixa: 'ate_3m', rotulo: 'Até 3 meses', ...linha(1, 0, 0, 1) },
      { faixa: '3_6m', rotulo: '3 a 6 meses', ...linha(0, 0, 0, 0) },
      { faixa: '6_12m', rotulo: '6 a 12 meses', ...linha(0, 0, 0, 0) },
      { faixa: 'mais_1a', rotulo: 'Mais de 1 ano', ...linha(2, 1, 3, 2) },
      { faixa: 'sem_data', rotulo: 'Sem data de início', ...linha(0, 0, 0, 0) },
    ],
    valor: [
      { faixa: 'ate_2k', rotulo: 'Menos de R$ 2 mil', ...linha(0, 0, 0, 0) },
      { faixa: '2k_10k', rotulo: 'R$ 2 mil a 10 mil', ...linha(0, 0, 0, 0) },
      { faixa: '10k_50k', rotulo: 'R$ 10 mil a 50 mil', ...linha(3, 1, 3, 3) },
      { faixa: 'acima_50k', rotulo: 'R$ 50 mil ou mais', ...linha(0, 0, 0, 0) },
      { faixa: 'sem_valor', rotulo: 'Sem valor', ...linha(0, 0, 0, 0) },
    ],
    prioridades: [
      { tema: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 5, nota_media: 4.2, reclamacoes: 4 },
      { tema: 'atendimento', rotulo: 'Atendimento', mencoes: 3, nota_media: 9.3, reclamacoes: 0 },
    ],
  }
}

function relTemas(iaAtiva = true): RelatorioTemas {
  const temas = [
    ['prazo_entrega', 'Prazo e entrega', 5, 4],
    ['produto_avarias', 'Produto e avarias', 2, 1],
    ['atendimento', 'Atendimento', 3, 0],
    ['preco_condicoes', 'Preço e condições', 0, 0],
    ['comunicacao', 'Comunicação', 1, 1],
    ['sistema_pedidos', 'Sistema e pedidos', 0, 0],
  ] as const
  return {
    ia: { ativa: iaAtiva, analisadas: iaAtiva ? 8 : 0, com_comentario: 10 },
    sentimento: iaAtiva ? { positivo: 3, neutro: 1, negativo: 3, misto: 1, sem_analise: 2 } : { positivo: 0, neutro: 0, negativo: 0, misto: 0, sem_analise: 10 },
    temas: temas.map(([tema, rotulo, mencoes, reclamacoes]) => ({
      tema,
      rotulo,
      mencoes,
      reclamacoes,
      elogios: 0,
      nota_media: mencoes ? 6.5 : null,
      variacao: mencoes ? 1 : null,
      sentimento: { positivo: 0, neutro: 0, negativo: iaAtiva ? reclamacoes : 0, sem_analise: iaAtiva ? 0 : mencoes },
    })),
    semanas: [
      { inicio: '2026-09-14', fim: '2026-09-20', respostas: 6, temas: { prazo_entrega: { mencoes: 3, reclamacoes: 2 } } },
      { inicio: '2026-09-21', fim: '2026-09-27', respostas: 4, temas: { prazo_entrega: { mencoes: 2, reclamacoes: 2 } } },
    ],
    picos: [{ tema: 'prazo_entrega', rotulo: 'Prazo e entrega', reclamacoes: 4, media_anterior: 0.5, de: somarDias(HOJE, -6), ate: HOJE }],
  }
}

function relEntregas(itens: RelatorioEntregas['itens'] = [], dimensao: RelatorioEntregas['dimensao'] = 'motorista'): RelatorioEntregas {
  return { dimensao, sem_valor: 7, itens, total: itens.length, pagina: 1, por_pagina: 50 }
}

const ENTREGA = {
  valor: 'Josué Almeida',
  respostas: 4,
  nps: bloco(1, 1, 2),
  csat: { percentual: 50, media: 3.5, total: 2 },
  reclamacoes: 2,
  temas: [{ tema: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 2 }],
  ultima_resposta: '2026-09-28T10:00:00-03:00',
  amostra_pequena: true,
}

function relResponsaveis(): RelatorioResponsaveis {
  return {
    itens: [
      { responsavel: { id: 2, nome: 'Diego Martins', foto_url: null }, empresas: 3, empresas_com_respostas: 2, nps: bloco(1, 1, 3), receita: '50000.00', receita_em_risco: '20000.00', acoes_abertas: 3, acoes_vencidas: 1 },
      { responsavel: null, empresas: 1, empresas_com_respostas: 0, nps: bloco(0, 0, 0), receita: '0.00', receita_em_risco: '0.00', acoes_abertas: 0, acoes_vencidas: 0 },
    ],
  }
}

function relOperacao(n = 3): RelatorioOperacao {
  return {
    taxa_resposta: { percentual: 25, responderam: 10, convidados: 40, amostra_pequena: false },
    canais: [
      { canal: 'email', convidados: 30, responderam: 6, percentual: 20 },
      { canal: 'whatsapp', convidados: 0, responderam: 0, percentual: null },
    ],
    acoes: { concluidas: 5, tempo_medio_dias: 2.5, no_prazo_percentual: 80, abertas: 4, vencidas: 1 },
    sem_resposta: {
      total: n,
      atrasados: Math.min(n, 1),
      intervalo_dias: 90,
      itens: Array.from({ length: n }, (_, i) => ({
        contato: { id: 300 + i, nome: `Contato ${i + 1}`, email: `c${i}@x.com` },
        empresa: i % 2 ? null : { id: 11, nome: 'Mercado Bom Preço' },
        ultimo_envio: '2026-06-01T10:00:00-03:00',
        dias: 120 - i,
        atrasado: i === 0,
      })),
    },
  }
}

function historico(extra: Partial<HistoricoEmpresa> = {}): HistoricoEmpresa {
  return {
    empresa: {
      id: 11,
      nome: 'Mercado Bom Preço',
      ativa: true,
      grupo: { id: 2, nome: 'Varejo' },
      segmento: null,
      responsavel: { id: 1, nome: 'Carla Ribeiro' },
      valor_mensal: '20000.00',
      cliente_desde: '2024-01-10',
    },
    nps: bloco(1, 0, 3),
    csat: { percentual: 50, media: 3, total: 2 },
    cobertura: { contatos_ativos: 4, responderam: 2, percentual: 50 },
    acoes: { abertas: 2, vencidas: 1, concluidas: 3 },
    evolucao: [
      { mes: '2026-08', nps: -20, total: 5 },
      { mes: '2026-09', nps: -50, total: 4 },
    ],
    linha_do_tempo: [
      {
        resposta_id: 800,
        data: '2026-09-28T10:00:00-03:00',
        nota: 3,
        tipo_nota: 'nps',
        grupo: 'detrator',
        contato: { id: 101, nome: 'Ana Souza', cargo: 'Gerente de compras', perfil: { id: 1, nome: 'Decisor' } },
        canal: 'email',
        origem: 'pesquisa',
        comentario: 'A entrega atrasou de novo.',
        temas: ['prazo_entrega'],
        ia: { sentimento: 'negativo', resumo: 'Reclama do atraso na entrega.' },
        acao: { id: 900, situacao: 'a_fazer' },
      },
      {
        resposta_id: 801,
        data: '2026-08-10T12:00:00-03:00',
        nota: 9,
        tipo_nota: 'nps',
        grupo: 'promotor',
        contato: null,
        canal: 'importacao',
        origem: 'importacao',
        comentario: null,
        temas: [],
        ia: null,
        acao: null,
      },
    ],
    total: 9,
    ...extra,
  }
}

type Rotas = Parameters<typeof apiFalsa>[0]

function api(extra: Rotas = {}) {
  return apiFalsa({
    'GET /relatorios/empresas': () => relEmpresas(),
    'GET /relatorios/grupos': () => relGrupos(),
    'GET /relatorios/temas': () => relTemas(),
    'GET /relatorios/entregas': () => relEntregas([ENTREGA]),
    'GET /relatorios/responsaveis': () => relResponsaveis(),
    'GET /relatorios/responsaveis/:id/empresas': () => [
      { empresa: { id: 11, nome: 'Mercado Bom Preço' }, nps: bloco(1, 0, 3), nota_media: 4.5, valor_mensal: '20000.00', ultima_resposta: null, acoes_abertas: 2 },
      { empresa: { id: 14, nome: 'Empório Central' }, nps: bloco(0, 0, 0), nota_media: null, valor_mensal: null, ultima_resposta: null, acoes_abertas: 0 },
    ],
    'GET /relatorios/operacao': () => relOperacao(),
    'GET /relatorios/historico/:id': ({ caminho }) =>
      caminho.endsWith('/11') ? historico() : new Response(JSON.stringify({ erro: { codigo: 'nao_encontrado', mensagem: 'Empresa não encontrada.' } }), { status: 404 }),
    'GET /cadastros/grupos': () => [{ id: 2, nome: 'Varejo', em_uso: 3 }],
    'GET /cadastros/segmentos': () => [{ id: 3, nome: 'Supermercados', em_uso: 1 }],
    'GET /responsaveis': () => [],
    ...extra,
  })
}

const TODAS = ['painel.ver', 'painel.exportar', 'relatorios.ver', 'respostas.ver', 'acoes.ver', 'contatos.ver']

function entrar(permissoes: string[] = TODAS, perfil: Perfil = 'gestor') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null, ia_ativa: true },
      permissoes,
    },
    false,
  )
}

let router: Router

async function abrir(caminho: string): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/relatorios/:aba', name: 'relatorios', component: RelatoriosView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const App = defineComponent({ render: () => h(RouterView) })
  const w = mount(App, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

/** Espera a pequena demora das recargas (200 ms) e as respostas. */
async function esperarRecarga() {
  await vi.advanceTimersByTimeAsync(260)
  await flushPromises()
}

const pedidos = (chamadas: Chamada[], caminho: string) => chamadas.filter((c) => c.metodo === 'GET' && c.caminho === caminho)
const consulta = (c: Chamada | undefined) => Object.fromEntries(c?.url.searchParams ?? [])
const botao = (w: VueWrapper, texto: string | RegExp) => {
  const b = w.findAll('button').find((x) => (typeof texto === 'string' ? x.text().trim() === texto : texto.test(x.text())))
  if (!b) throw new Error(`Sem o botão "${texto}"`)
  return b
}
function selecao(w: VueWrapper, rotulo: string) {
  const label = w.findAll('label').find((l) => l.text() === rotulo)
  if (!label) throw new Error(`Sem o campo "${rotulo}"`)
  return w.get(`[id="${label.attributes('for')}"]`)
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  avisos.splice(0)
  document.body.innerHTML = ''
})

describe('Relatórios: abas e filtros no endereço', () => {
  it('abre na aba do endereço, com as 8 abas e os filtros comuns (90 dias, só ativas)', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/empresas')
    const abas = w.findAll('[role="tab"]')
    expect(abas.map((a) => a.text())).toEqual(['Empresas', 'Grupos de clientes', 'Temas', 'Entregas', 'Responsáveis', 'Operação', 'Desfecho', 'Histórico de uma empresa'])
    expect(abas[0]!.attributes('aria-selected')).toBe('true')
    expect(consulta(pedidos(chamadas, '/relatorios/empresas')[0])).toEqual({
      de: somarDias(HOJE, -89),
      ate: HOJE,
      so_ativos: 'true',
      ordem: 'prioridade',
      pagina: '1',
      por_pagina: '50',
    })
    expect(document.title).toBe('Empresas · Relatórios · Toqqi')
  })

  it('aba que não existe volta para Empresas', async () => {
    entrar()
    api()
    await abrir('/relatorios/vendas?periodo=30')
    await flushPromises()
    expect(router.currentRoute.value.params.aba).toBe('empresas')
    expect(router.currentRoute.value.query).toEqual({ periodo: '30' })
  })

  it('trocar de aba leva grupo e "só ativas" no endereço; o título da página acompanha', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/empresas?grupo_id=2&so_ativos=false&quadrante=proteger')
    await w.findAll('[role="tab"]').find((a) => a.text() === 'Temas')!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.params.aba).toBe('temas')
    expect(router.currentRoute.value.query).toEqual({ grupo_id: '2', so_ativos: 'false' })
    expect(consulta(pedidos(chamadas, '/relatorios/temas')[0])).toEqual({ de: somarDias(HOJE, -89), ate: HOJE, so_ativos: 'false', grupo_id: '2' })
    expect(document.title).toBe('Temas · Relatórios · Toqqi')
  })

  it('mudar o período escreve no endereço e busca de novo com as datas novas', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/temas')
    await selecao(w, 'Período').setValue('30')
    await esperarRecarga()
    expect(router.currentRoute.value.query).toEqual({ periodo: '30' })
    const temas = pedidos(chamadas, '/relatorios/temas')
    expect(temas).toHaveLength(2)
    expect(consulta(temas[1])).toEqual({ de: somarDias(HOJE, -29), ate: HOJE, so_ativos: 'true' })
    // O título continua com a aba depois da troca de filtro.
    expect(document.title).toBe('Temas · Relatórios · Toqqi')
  })

  it('voltar do navegador (o endereço muda por fora) leva a tela junto', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/empresas')
    await router.push('/relatorios/operacao?periodo=7')
    await esperarRecarga()
    expect(w.find('[role="tab"][aria-selected="true"]').text()).toBe('Operação')
    expect((selecao(w, 'Período').element as HTMLSelectElement).value).toBe('7')
  })

  it('"Exportar CSV" só com painel.exportar e só nas abas que têm CSV', async () => {
    entrar(TODAS.filter((p) => p !== 'painel.exportar'))
    api()
    let w = await abrir('/relatorios/empresas')
    expect(w.text()).not.toContain('Exportar')
    w.unmount()

    entrar()
    api()
    w = await abrir('/relatorios/temas')
    expect(w.text()).not.toContain('Exportar')
    w.unmount()
    w = await abrir('/relatorios/operacao')
    expect(w.text()).toContain('Exportar contatos sem resposta (CSV)')
    w.unmount()
    w = await abrir('/relatorios/historico')
    expect(w.text()).not.toContain('Exportar CSV')
    w.unmount()
    w = await abrir('/relatorios/historico?empresa_id=11')
    expect(w.text()).toContain('Exportar CSV')
  })

  it('o CSV das empresas leva os mesmos filtros (sem a página)', async () => {
    entrar()
    const { chamadas } = api({ 'GET /relatorios/empresas.csv': () => new Response('Empresa;NPS\n', { status: 200, headers: { 'Content-Type': 'text/csv' } }) })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const w = await abrir('/relatorios/empresas?quadrante=proteger&pagina=2&periodo=tudo')
    await botao(w, 'Exportar CSV').trigger('click')
    await flushPromises()
    expect(consulta(pedidos(chamadas, '/relatorios/empresas.csv')[0])).toEqual({ so_ativos: 'true', ordem: 'prioridade', quadrante: 'proteger' })
    expect(clique).toHaveBeenCalled()
  })

  it('os CSV de Entregas, Responsáveis, Operação e Histórico levam os filtros de cada aba', async () => {
    entrar()
    const csv = () => new Response('a;b\n', { status: 200, headers: { 'Content-Type': 'text/csv' } })
    const { chamadas } = api({
      'GET /relatorios/entregas.csv': csv,
      'GET /relatorios/responsaveis.csv': csv,
      'GET /relatorios/operacao/sem-resposta.csv': csv,
      'GET /relatorios/historico/11.csv': csv,
    })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const exportar = async (caminho: string, rotulo: string) => {
      const w = await abrir(caminho)
      await botao(w, rotulo).trigger('click')
      await flushPromises()
      w.unmount()
    }
    await exportar('/relatorios/entregas?dimensao=rota&ordem=nps&busca=Sul&pagina=2&grupo_id=2', 'Exportar CSV')
    expect(consulta(pedidos(chamadas, '/relatorios/entregas.csv')[0])).toEqual({
      de: somarDias(HOJE, -89),
      ate: HOJE,
      so_ativos: 'true',
      grupo_id: '2',
      dimensao: 'rota',
      ordem: 'nps',
      busca: 'Sul',
    })
    await exportar('/relatorios/responsaveis?periodo=30&so_ativos=false', 'Exportar CSV')
    expect(consulta(pedidos(chamadas, '/relatorios/responsaveis.csv')[0])).toEqual({ de: somarDias(HOJE, -29), ate: HOJE, so_ativos: 'false' })
    await exportar('/relatorios/operacao?periodo=tudo&grupo_id=3', 'Exportar contatos sem resposta (CSV)')
    expect(consulta(pedidos(chamadas, '/relatorios/operacao/sem-resposta.csv')[0])).toEqual({ so_ativos: 'true', grupo_id: '3' })
    await exportar('/relatorios/historico?empresa_id=11&periodo=7', 'Exportar CSV')
    expect(consulta(pedidos(chamadas, '/relatorios/historico/11.csv')[0])).toEqual({ de: somarDias(HOJE, -6), ate: HOJE })
  })

  it('no histórico, só o período (sem grupo nem "só ativas")', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/historico')
    expect(w.findAll('label').map((l) => l.text())).not.toContain('Grupo de empresas')
    expect(w.text()).not.toContain('Só empresas ativas')
    expect((selecao(w, 'Período').element as HTMLSelectElement).value).toBe('tudo')
  })
})

describe('Relatórios › Empresas', () => {
  it('mostra os cartões, a matriz com a contagem por quadrante e a tabela', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/empresas')
    expect(w.text()).toContain('Empresas com respostas')
    expect(w.text()).toContain('de 3 empresas no filtro')
    // Receita em risco: o número curto e o valor exato para leitor de tela.
    expect(w.text().replace(/\u00a0/g, ' ')).toContain('R$ 20.000,00')
    expect(w.find('[data-matriz]').exists()).toBe(true)
    const proteger = botao(w, /Proteger já/)
    expect(proteger.attributes('aria-pressed')).toBe('false')
    expect(proteger.text()).toContain('1')
    expect(w.text()).toContain('Mercado Bom Preço')
    expect(w.text()).toContain('Em risco')
    expect(w.text()).toContain('Inativa')
    expect(w.text()).toContain('Nunca respondeu')
  })

  it('a contagem do quadrante filtra a tabela (e fica no endereço)', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/empresas')
    await botao(w, /Proteger já/).trigger('click')
    await esperarRecarga()
    expect(router.currentRoute.value.query).toEqual({ quadrante: 'proteger' })
    expect(consulta(pedidos(chamadas, '/relatorios/empresas').at(-1)).quadrante).toBe('proteger')
    expect(botao(w, /Proteger já/).attributes('aria-pressed')).toBe('true')
    expect(w.text()).toContain('Mostrando:')
    // De novo: tira o filtro.
    await botao(w, /Proteger já/).trigger('click')
    await esperarRecarga()
    expect(router.currentRoute.value.query).toEqual({})
  })

  it('filtro novo volta para a página 1', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/empresas?pagina=3')
    await botao(w, /Pode crescer/).trigger('click')
    await esperarRecarga()
    expect(router.currentRoute.value.query).toEqual({ quadrante: 'crescer' })
  })

  it('o nome da empresa abre o histórico dela (com todo o período, se o período não foi escolhido)', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/empresas?grupo_id=2')
    await w.findAll('button').find((b) => b.text() === 'Mercado Bom Preço')!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.params.aba).toBe('historico')
    expect(router.currentRoute.value.query).toEqual({ grupo_id: '2', empresa_id: '11' })
    await flushPromises()
    expect(consulta(pedidos(chamadas, '/relatorios/historico/11')[0])).toEqual({})
  })

  it('erro na primeira carga: mensagem e "Tentar de novo"', async () => {
    entrar()
    let falhar = true
    const { chamadas } = api({
      'GET /relatorios/empresas': () =>
        falhar ? new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'O relatório não carregou.' } }), { status: 500 }) : relEmpresas(),
    })
    const w = await abrir('/relatorios/empresas')
    expect(w.text()).toContain('O relatório não carregou.')
    falhar = false
    await botao(w, 'Tentar de novo').trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, '/relatorios/empresas')).toHaveLength(2)
    expect(w.text()).toContain('Empresas com respostas')
  })

  it('sem empresas: explica o que fazer; com filtro: oferece limpar', async () => {
    entrar()
    const vazio = relEmpresas({ itens: [], total: 0 })
    api({ 'GET /relatorios/empresas': () => vazio })
    let w = await abrir('/relatorios/empresas')
    expect(w.text()).toContain('Nenhuma empresa no filtro')
    w.unmount()
    w = await abrir('/relatorios/empresas?quadrante=manter')
    expect(w.text()).toContain('Nenhuma empresa com esses filtros')
    await botao(w, 'Limpar busca e filtros').trigger('click')
    await esperarRecarga()
    expect(router.currentRoute.value.query).toEqual({})
  })
})

describe('Relatórios › Grupos de clientes', () => {
  it('NPS por segmento, grupo, tempo e valor; "Ver em tabela"; o que resolver primeiro com links', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/grupos')
    for (const t of ['Por segmento', 'Por grupo de empresas', 'Por tempo como cliente', 'Por valor do contrato', 'O que resolver primeiro']) expect(w.text()).toContain(t)
    expect(w.text()).toContain('Sem segmento')
    const ver = w.findAll('button').filter((b) => b.text().includes('Ver em tabela'))
    expect(ver.length).toBe(4)
    await ver[0]!.trigger('click')
    expect(ver[0]!.attributes('aria-pressed')).toBe('true')
    expect(w.findAll('table').length).toBeGreaterThan(0)
    const link = w.findAll('a').find((a) => a.text().includes('Prazo e entrega'))!
    const alvo = new URL(link.attributes('href')!, 'http://x')
    expect(alvo.pathname).toBe('/respostas')
    expect(Object.fromEntries(alvo.searchParams)).toMatchObject({ tema: 'prazo_entrega', tipo_nota: 'nps', so_ativos: 'true' })
  })
})

describe('Relatórios › Temas', () => {
  it('com IA: cobertura da análise, picos, sentimento e a tabela dos 6 temas (reclamações levam às respostas)', async () => {
    entrar([...TODAS, 'configuracoes.gerenciar'], 'admin')
    api()
    const w = await abrir('/relatorios/temas')
    expect(w.get('[data-aviso-ia]').text()).toContain('8 de 10 comentários analisados pela IA')
    expect(w.get('[data-aviso-ia]').find('a[href="/configuracoes/ia"]').exists()).toBe(true)
    expect(w.text()).toContain('Pico de reclamações em Prazo e entrega')
    expect(w.text()).toContain('Sentimento dos comentários')
    expect(w.text()).toContain('Sentimento (IA)')
    // Sem prometer que a IA vai "chegar" nos que faltam; o admin vê como pedir a análise.
    expect(w.get('[data-aviso-ia]').text()).toContain('Os outros usam as palavras-chave')
    expect(w.get('[data-aviso-ia]').text()).toContain('Para pedir a análise dos comentários dos últimos 90 dias')
    const reclamacoes = w.find('a[aria-label="4 reclamações de Prazo e entrega: ver as respostas"]')
    expect(Object.fromEntries(new URL(reclamacoes.attributes('href')!, 'http://x').searchParams)).toMatchObject({ tema: 'prazo_entrega', reclamacao: 'true' })
    // Menções × reclamações no gráfico: rádios nativos (as setas trocam a opção).
    const radios = w.findAll<HTMLInputElement>('input[type="radio"]')
    expect(radios.map((r) => r.element.value)).toEqual(['mencoes', 'reclamacoes'])
    expect(new Set(radios.map((r) => r.element.name)).size).toBe(1)
    expect(radios[0]!.element.checked).toBe(true)
    await radios[1]!.setValue(true)
    expect(radios[1]!.element.checked).toBe(true)
    expect(w.text()).toContain('Quantas respostas reclamaram de cada tema.')
  })

  it('sem IA: "Temas por palavras-chave", sem tom nem coluna de sentimento', async () => {
    entrar()
    api({ 'GET /relatorios/temas': () => relTemas(false) })
    const w = await abrir('/relatorios/temas')
    expect(w.get('[data-aviso-ia]').text()).toContain('Temas por palavras-chave')
    // Gestor não configura a IA: sem o link.
    expect(w.get('[data-aviso-ia]').find('a').exists()).toBe(false)
    expect(w.text()).not.toContain('Sentimento dos comentários')
    expect(w.text()).not.toContain('Sentimento (IA)')
  })
})

describe('Relatórios › Entregas', () => {
  it('tabela com amostra pequena e "Ver respostas" com o motorista e os filtros', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/entregas')
    expect(w.text()).toContain('Josué Almeida')
    expect(w.text()).toContain('Amostra pequena')
    expect(w.text()).toContain('7 respostas do período não informam o motorista')
    const link = w.findAll('a').find((a) => a.text().includes('Ver respostas'))!
    expect(Object.fromEntries(new URL(link.attributes('href')!, 'http://x').searchParams)).toEqual({
      de: somarDias(HOJE, -89),
      ate: HOJE,
      so_ativos: 'true',
      motorista: 'Josué Almeida',
    })
  })

  it('trocar a dimensão escreve no endereço e busca por ela', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/entregas')
    const rota = w.get<HTMLInputElement>('input[type="radio"][value="rota"]')
    await rota.setValue(true)
    await esperarRecarga()
    expect(router.currentRoute.value.query).toEqual({ dimensao: 'rota' })
    expect(consulta(pedidos(chamadas, '/relatorios/entregas').at(-1)).dimensao).toBe('rota')
    expect(rota.element.checked).toBe(true)
    expect(w.get<HTMLInputElement>('input[type="radio"][value="motorista"]').element.checked).toBe(false)
  })

  it('sem dados: explica como mandar a informação no convite (e o atalho para as integrações só para admin)', async () => {
    entrar()
    api({ 'GET /relatorios/entregas': () => relEntregas([]) })
    let w = await abrir('/relatorios/entregas?dimensao=filial')
    const vazio = w.get('[data-vazio-entregas]')
    expect(vazio.text()).toContain('Nenhuma resposta informa a filial')
    expect(vazio.text()).toContain('contexto')
    expect(vazio.text()).not.toContain('Ver as integrações')
    // Sem itens nem busca, não há o que buscar.
    expect(w.find('input[type="search"]').exists()).toBe(false)
    w.unmount()
    entrar(TODAS, 'admin')
    w = await abrir('/relatorios/entregas')
    expect(w.get('[data-vazio-entregas]').text()).toContain('Ver as integrações')
  })
})

describe('Relatórios › Responsáveis', () => {
  it('abrir uma carteira busca as empresas dela (com os filtros); o nome da empresa abre o histórico', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/responsaveis?periodo=30')
    expect(w.text()).toContain('Diego Martins')
    expect(w.text()).toContain('Sem responsável')
    const linha = w.findAll('button[aria-expanded]').find((b) => b.text().includes('Diego Martins'))!
    expect(linha.attributes('aria-expanded')).toBe('false')
    await linha.trigger('click')
    await flushPromises()
    const pedido = pedidos(chamadas, '/relatorios/responsaveis/2/empresas')
    expect(pedido).toHaveLength(1)
    expect(consulta(pedido[0])).toEqual({ de: somarDias(HOJE, -29), ate: HOJE, so_ativos: 'true' })
    expect(linha.attributes('aria-expanded')).toBe('true')
    expect(w.get(`#${linha.attributes('aria-controls')}`).text()).toContain('Mercado Bom Preço')
    expect(w.text()).toContain('Sem respostas')
    // Fechar e abrir de novo, com os mesmos filtros, não busca outra vez.
    await linha.trigger('click')
    await linha.trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, '/relatorios/responsaveis/2/empresas')).toHaveLength(1)
    await w.findAll('button').find((b) => b.text() === 'Empório Central')!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.params.aba).toBe('historico')
    expect(router.currentRoute.value.query).toEqual({ periodo: '30', empresa_id: '14' })
  })

  it('"Sem responsável" busca a carteira 0', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/responsaveis')
    await w.findAll('button[aria-expanded]').find((b) => b.text().includes('Sem responsável'))!.trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, '/relatorios/responsaveis/0/empresas')).toHaveLength(1)
  })

  it('carteira aberta busca de novo quando o período muda, e a resposta atrasada do filtro antigo é ignorada', async () => {
    entrar()
    let liberarAntiga: () => void = () => undefined
    const empresa = (id: number, nome: string) => ({ empresa: { id, nome }, nps: bloco(1, 0, 0), nota_media: 9, valor_mensal: null, ultima_resposta: null, acoes_abertas: 0 })
    const { chamadas } = api({
      'GET /relatorios/responsaveis/:id/empresas': ({ url }) =>
        // A do filtro antigo (90 dias) demora e chega depois da nova.
        url.searchParams.get('de') === somarDias(HOJE, -89)
          ? new Promise<void>((r) => (liberarAntiga = r)).then(() => [empresa(41, 'Empresa do filtro antigo')])
          : [empresa(42, 'Empresa do filtro novo')],
    })
    const w = await abrir('/relatorios/responsaveis')
    const linha = w.findAll('button[aria-expanded]').find((b) => b.text().includes('Diego Martins'))!
    await linha.trigger('click')
    await flushPromises()
    await selecao(w, 'Período').setValue('30')
    await esperarRecarga()
    const pedidosCarteira = pedidos(chamadas, '/relatorios/responsaveis/2/empresas')
    expect(pedidosCarteira.map((c) => c.url.searchParams.get('de'))).toEqual([somarDias(HOJE, -89), somarDias(HOJE, -29)])
    const carteira = () => w.get(`#${linha.attributes('aria-controls')}`).text()
    expect(carteira()).toContain('Empresa do filtro novo')
    liberarAntiga()
    await flushPromises()
    expect(carteira()).toContain('Empresa do filtro novo')
    expect(carteira()).not.toContain('Empresa do filtro antigo')
    // Com os mesmos filtros, fechar e abrir não busca de novo.
    await linha.trigger('click')
    await linha.trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, '/relatorios/responsaveis/2/empresas')).toHaveLength(2)
  })

  it('carteira fechada busca de novo ao abrir, se os filtros mudaram enquanto estava fechada', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/responsaveis')
    const linha = () => w.findAll('button[aria-expanded]').find((b) => b.text().includes('Diego Martins'))!
    await linha().trigger('click')
    await flushPromises()
    await linha().trigger('click')
    await selecao(w, 'Grupo de empresas').setValue('2')
    await esperarRecarga()
    // Fechada: não busca na troca de filtro…
    expect(pedidos(chamadas, '/relatorios/responsaveis/2/empresas')).toHaveLength(1)
    // …e busca ao abrir, já com o grupo.
    await linha().trigger('click')
    await flushPromises()
    const todos = pedidos(chamadas, '/relatorios/responsaveis/2/empresas')
    expect(todos).toHaveLength(2)
    expect(todos[1]!.url.searchParams.get('grupo_id')).toBe('2')
  })
})

describe('Relatórios › Operação', () => {
  it('taxa de resposta, canais, ações e os contatos sem resposta (atrasados em destaque)', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/operacao')
    expect(w.text()).toContain('Taxa de resposta')
    expect(w.text()).toContain('25%')
    expect(w.text()).toContain('6 de 30 convidados responderam')
    expect(w.text()).toContain('Nenhum convite saiu por WhatsApp no período.')
    expect(w.text()).toContain('2,5')
    expect(w.text()).toContain('80%')
    expect(w.text()).toContain('1 vencida')
    const lista = w.get('[data-sem-resposta]')
    expect(lista.text()).toContain('3 contatos')
    expect(lista.text()).toContain('1 atrasado')
    expect(lista.text()).toContain('mais de 90 dias')
    expect(lista.text()).toContain('Contato 1')
    expect(lista.text()).toContain('Atrasado')
    expect(lista.find('a[href="/contatos/300"]').exists()).toBe(true)
  })

  it('a lista vem de uma vez e a tela mostra de 50 em 50', async () => {
    entrar()
    api({ 'GET /relatorios/operacao': () => relOperacao(60) })
    const w = await abrir('/relatorios/operacao')
    const lista = w.get('[data-sem-resposta]')
    expect(lista.text()).toContain('Contato 50')
    expect(lista.text()).not.toContain('Contato 51')
    expect(lista.text()).toContain('Página 1 de 2')
    await lista.findAll('button').find((b) => b.text().includes('Próxima'))!.trigger('click')
    expect(lista.text()).toContain('Contato 51')
  })

  it('ninguém esperando resposta', async () => {
    entrar()
    api({ 'GET /relatorios/operacao': () => relOperacao(0) })
    const w = await abrir('/relatorios/operacao')
    expect(w.text()).toContain('Ninguém esperando resposta')
  })
})

describe('Relatórios › Histórico de uma empresa', () => {
  it('sem empresa escolhida: pede para escolher e não busca', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/historico')
    expect(w.text()).toContain('Escolha uma empresa')
    expect(chamadas.some((c) => c.caminho.startsWith('/relatorios/historico'))).toBe(false)
  })

  it('com a empresa: cabeçalho, números, evolução e a linha do tempo', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/relatorios/historico?empresa_id=11')
    expect(consulta(pedidos(chamadas, '/relatorios/historico/11')[0])).toEqual({})
    expect(w.get('h2').text()).toContain('Mercado Bom Preço')
    expect((w.get('input[role="combobox"]').element as HTMLInputElement).value).toBe('Mercado Bom Preço')
    expect(w.text()).toContain('Carla Ribeiro')
    expect(w.text()).toContain('Evolução do NPS')
    expect(w.text()).toContain('1 vencida')
    const linha = w.get('[data-linha-do-tempo]')
    expect(linha.text()).toContain('Mostrando as 2 mais recentes de 9')
    expect(linha.text()).toContain('setembro de 2026')
    expect(linha.text()).toContain('agosto de 2026')
    expect(linha.text()).toContain('Ana Souza · Gerente de compras · Decisor')
    expect(linha.text()).toContain('Reclama do atraso na entrega.')
    expect(linha.text()).toContain('Negativo')
    expect(linha.text()).toContain('Importada')
    expect(linha.text()).toContain('Sem contato identificado')
    expect(linha.find('a[href="/respostas?empresa_id=11&analisar=800"]').exists()).toBe(true)
    expect(linha.find('a[href="/planos-de-acao/900"]').exists()).toBe(true)
  })

  it('empresa que não é da conta: "Empresa não encontrada"', async () => {
    entrar()
    api()
    const w = await abrir('/relatorios/historico?empresa_id=999')
    expect(w.text()).toContain('Empresa não encontrada')
  })

  it('sem acesso aos contatos, a busca usa o relatório de empresas', async () => {
    entrar(['painel.ver', 'relatorios.ver'])
    const { chamadas } = api()
    const w = await abrir('/relatorios/historico')
    const campo = w.get('input[role="combobox"]')
    await campo.setValue('mer')
    await campo.trigger('input')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    const busca = pedidos(chamadas, '/relatorios/empresas').at(-1)
    expect(consulta(busca)).toEqual({ busca: 'mer', so_ativos: 'false', ordem: 'nome', por_pagina: '8' })
    await w.findAll('[role="option"]').find((o) => o.text().includes('Atacadão do Vale'))!.trigger('mousedown')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ empresa_id: '12' })
  })
})
