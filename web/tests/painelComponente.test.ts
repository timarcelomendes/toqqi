import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { Painel } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData, hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import InicioView from '@/modulos/inicio/InicioView.vue'
import PainelView from '@/modulos/painel/PainelView.vue'
import { chavePassosOcultos } from '@/modulos/painel/logica'
import { apiFalsa } from './apiFalsa'

const HOJE = hojeIso()

function painel(extra: Partial<Painel> = {}): Painel {
  return {
    periodo: { de: somarDias(HOJE, -89), ate: HOJE, anterior: { de: somarDias(HOJE, -179), ate: somarDias(HOJE, -90) } },
    nps: {
      valor: 34,
      faixa: 'pode_melhorar',
      promotores: 62,
      neutros: 31,
      detratores: 27,
      total: 120,
      pct: { promotores: 51.7, neutros: 25.8, detratores: 22.5 },
      decisores: { valor: 41, total: 34 },
    },
    variacao: { valor: 6, anterior: 28 },
    csat: { percentual: 82, media: 4.21, total: 57, satisfeitos: 47 },
    taxa_resposta: { percentual: 18, responderam: 12, convidados: 67, amostra_pequena: true },
    movimentacao: {
      resgatados: 1,
      deixaram_de_ser_promotores: 0,
      itens: [
        {
          tipo: 'resgatado',
          contato: { id: 101, nome: 'Bruno Carvalho' },
          empresa: { id: 3, nome: 'Atacadão Serra' },
          nota_anterior: 4,
          nota_atual: 10,
          data_anterior: '2026-05-12',
          data_atual: '2026-09-18',
        },
      ],
    },
    atencao: {
      acoes_abertas: 4,
      acoes_vencidas: 2,
      tudo_em_dia: false,
      empresas: [
        {
          empresa: { id: 1, nome: 'Mercado Bom Preço' },
          nps: -20,
          acoes_abertas: 3,
          acoes_vencidas: 2,
          desde: '2026-09-12',
          responsavel: { id: 7, nome: 'Carla Ribeiro' },
          ultimo_comentario_detrator: 'A entrega atrasou de novo.',
          acao_id: 900,
        },
      ],
      receita_em_risco: { valor: 48750.5, empresas: 1, sem_valor: 0 },
    },
    temas: [{ chave: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 38, nota_media: 5.9 }],
    comentarios: [],
    evolucao: [
      { mes: '2026-08', nps: 36, total: 35 },
      { mes: '2026-09', nps: 34, total: 50 },
    ],
    empresas: { menor: [], maior: [] },
    palavras: [{ palavra: 'entrega', total: 31 }],
    primeiros_passos: { contatos: true, envios_ligados: true, primeiro_envio: false, primeira_resposta: false },
    ...extra,
  }
}

function entrar(permissoes: string[]) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana Paula', email: 'a@x.com', cargo: null, perfil: 'gestor', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 42, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

async function abrir(componente: object): Promise<VueWrapper> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/inicio', component: componente },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push('/inicio')
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await vi.dynamicImportSettled()
  await flushPromises()
  return w
}

const TODAS = ['painel.ver', 'painel.exportar', 'respostas.ver', 'acoes.ver', 'contatos.ver', 'importacao.usar', 'envios.ver']

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})

// Desmonta as telas de cada teste (timers e recargas não vazam para o seguinte).
enableAutoUnmount(afterEach)

afterEach(() => {
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
  localStorage.clear()
})

describe('Início', () => {
  it('com painel.ver, o Início é o painel: pede os últimos 90 dias, só empresas ativas', async () => {
    entrar(TODAS)
    const { chamadas } = apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
    const w = await abrir(InicioView)
    const pedido = chamadas.find((c) => c.caminho === '/painel')
    expect(pedido).toBeTruthy()
    expect(Object.fromEntries(pedido!.url.searchParams)).toEqual({ de: somarDias(HOJE, -89), ate: HOJE, so_ativos: 'true' })
    expect(w.text()).toContain('Pode melhorar')
    expect(w.text()).toContain('Precisa de atenção')
  })

  it('sem painel.ver, continua a tela de boas-vindas (e não pede o painel)', async () => {
    entrar(['contatos.ver'])
    const { chamadas } = apiFalsa({ 'GET /painel': () => painel() })
    const w = await abrir(InicioView)
    expect(chamadas.some((c) => c.caminho === '/painel')).toBe(false)
    expect(w.text()).toContain('Aqui é o seu ponto de partida')
  })
})

describe('painel', () => {
  it('"Tratar" leva direto à ação mais urgente da empresa', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
    const w = await abrir(PainelView)
    const tratar = w.findAll('a').find((a) => a.text().startsWith('Tratar'))
    expect(tratar?.attributes('href')).toBe('/planos-de-acao/900')
    expect(w.text()).toMatch(/R\$\s48\.750,50 por mês/)
  })

  it('sem nada aberto, mostra "Tudo em dia"', async () => {
    entrar(TODAS)
    const base = painel()
    apiFalsa({
      'GET /painel': () => painel({ atencao: { ...base.atencao, acoes_abertas: 0, acoes_vencidas: 0, tudo_em_dia: true, empresas: [] } }),
      'GET /cadastros/grupos': () => [],
    })
    const w = await abrir(PainelView)
    expect(w.text()).toContain('Tudo em dia')
    expect(w.findAll('a').some((a) => a.text().startsWith('Tratar'))).toBe(false)
  })

  it('"Ocultar" esconde os primeiros passos e lembra neste navegador (por conta)', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
    let w = await abrir(PainelView)
    expect(w.text()).toContain('Primeiros passos')
    expect(w.text()).toContain('2 de 4 feitos')
    await w.findAll('button').find((b) => b.text() === 'Ocultar')!.trigger('click')
    expect(w.find('#t-passos').exists()).toBe(false)
    expect(localStorage.getItem(chavePassosOcultos(42))).toBe('1')
    expect(w.text()).toContain('Mostrar primeiros passos')

    // Abrindo de novo, continua escondido.
    w.unmount()
    w = await abrir(PainelView)
    expect(w.find('#t-passos').exists()).toBe(false)

    // E dá para mostrar de novo.
    await w.findAll('button').find((b) => b.text() === 'Mostrar primeiros passos')!.trigger('click')
    expect(w.find('#t-passos').exists()).toBe(true)
    expect(localStorage.getItem(chavePassosOcultos(42))).toBeNull()
  })

  it('se o navegador não deixa guardar, esconde só agora e avisa', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
    const w = await abrir(PainelView)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('cheio', 'QuotaExceededError')
    })
    await w.findAll('button').find((b) => b.text() === 'Ocultar')!.trigger('click')
    expect(w.find('#t-passos').exists()).toBe(false)
    expect(avisos.at(-1)?.mensagem).toContain('Seu navegador não deixou guardar')
    vi.restoreAllMocks()
  })

  it('com todos os passos feitos, o bloco não aparece', async () => {
    entrar(TODAS)
    apiFalsa({
      'GET /painel': () => painel({ primeiros_passos: { contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: 3 } }),
      'GET /cadastros/grupos': () => [],
    })
    const w = await abrir(PainelView)
    expect(w.find('#t-passos').exists()).toBe(false)
    expect(w.text()).not.toContain('Mostrar primeiros passos')
  })

  it('"Exportar CSV" só para quem tem painel.exportar; manda os mesmos filtros', async () => {
    entrar(TODAS.filter((p) => p !== 'painel.exportar'))
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
    let w = await abrir(PainelView)
    expect(w.text()).not.toContain('Exportar CSV')
    w.unmount()

    entrar(TODAS)
    const { chamadas } = apiFalsa({
      'GET /painel': () => painel(),
      'GET /cadastros/grupos': () => [],
      'GET /painel/exportar.csv': () => new Response('data;nota\n', { status: 200, headers: { 'Content-Type': 'text/csv' } }),
    })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    w = await abrir(PainelView)
    await w.findAll('button').find((b) => b.text().includes('Exportar CSV'))!.trigger('click')
    await flushPromises()
    const csv = chamadas.find((c) => c.caminho === '/painel/exportar.csv')
    expect(Object.fromEntries(csv!.url.searchParams)).toEqual({ de: somarDias(HOJE, -89), ate: HOJE, so_ativos: 'true' })
    expect(clique).toHaveBeenCalled()
    vi.restoreAllMocks()
  })

  it('trocar o período pede o painel de novo com as datas novas', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      entrar(TODAS)
      const { chamadas } = apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
      const w = await abrir(PainelView)
      const label = w.findAll('label').find((l) => l.text() === 'Período')!
      await w.get(`[id="${label.attributes('for')}"]`).setValue('7')
      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      const pedidos = chamadas.filter((c) => c.caminho === '/painel')
      expect(pedidos).toHaveLength(2)
      expect(Object.fromEntries(pedidos[1]!.url.searchParams)).toEqual({ de: somarDias(HOJE, -6), ate: HOJE, so_ativos: 'true' })
      // Enquanto carrega, o painel anterior continua na tela.
      expect(w.text()).toContain('Precisa de atenção')
    } finally {
      vi.useRealTimers()
    }
  })

  it('datas escolhidas trocadas ou incompletas: avisa no campo, não busca e o título fica o dos números na tela', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      entrar(TODAS)
      const { chamadas } = apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
      const w = await abrir(PainelView)
      const campo = (rotulo: string) => w.get(`[id="${w.findAll('label').find((l) => l.text().startsWith(rotulo))!.attributes('for')}"]`)
      await campo('Período').setValue('personalizado')
      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      const pedidos = () => chamadas.filter((c) => c.caminho === '/painel').length
      expect(pedidos()).toBe(2)
      const titulo = `De ${formatarData(somarDias(HOJE, -89))} a ${formatarData(HOJE)}`
      expect(w.text()).toContain(titulo)

      // Inicial depois da final.
      await campo('De').setValue(HOJE)
      await campo('Até').setValue(somarDias(HOJE, -5))
      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      expect(pedidos()).toBe(2)
      expect(w.text()).toContain('A data inicial precisa ser antes da final.')
      expect(w.text()).toContain(titulo)
      expect(w.text()).not.toContain(`De ${formatarData(HOJE)} a`)

      // Sem a data final.
      await campo('Até').setValue('')
      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      expect(pedidos()).toBe(2)
      expect(w.text()).toContain('Escolha a data final.')
      expect(w.text()).not.toContain('Desde')
      // Os atalhos continuam com o período dos números na tela.
      const tema = w.findAll('a').find((a) => a.attributes('href')?.includes('tema='))!
      expect(new URL(tema.attributes('href')!, 'http://x').searchParams.get('de')).toBe(somarDias(HOJE, -89))
    } finally {
      vi.useRealTimers()
    }
  })

  it('atalhos para Respostas levam as mesmas datas, o grupo e "só ativas"; os blocos de NPS levam tipo_nota=nps', async () => {
    entrar(TODAS)
    apiFalsa({
      'GET /painel': () =>
        painel({
          empresas: { menor: [{ empresa: { id: 1, nome: 'Mercado Bom Preço' }, nps: -20, respostas: 10 }], maior: [] },
          comentarios: [
            {
              resposta_id: 5,
              data: '2026-09-29T10:00:00-03:00',
              nota: 3,
              tipo_nota: 'nps',
              grupo: 'detrator',
              comentario: 'Atrasou.',
              contato: { id: 101, nome: 'Ana' },
              empresa: null,
            },
          ],
        }),
      'GET /cadastros/grupos': () => [],
    })
    const w = await abrir(PainelView)
    const links = w.findAll('a').map((a) => a.attributes('href') ?? '').filter((h) => h.startsWith('/respostas'))
    const consulta = (trecho: string) => Object.fromEntries(new URL(links.find((h) => h.includes(trecho))!, 'http://x').searchParams)
    const base = { de: somarDias(HOJE, -89), ate: HOJE, so_ativos: 'true' }
    expect(consulta('tema=')).toEqual({ ...base, tipo_nota: 'nps', tema: 'prazo_entrega' })
    expect(consulta('empresa_id=')).toEqual({ ...base, tipo_nota: 'nps', empresa_id: '1' })
    expect(consulta('categoria=neutro')).toEqual({ ...base, tipo_nota: 'nps', categoria: 'neutro' })
    // Palavras e comentários contam NPS e CSAT: sem tipo_nota.
    expect(consulta('busca=')).toEqual({ ...base, busca: 'entrega' })
    expect(links).toContain(`/respostas?de=${base.de}&ate=${base.ate}&so_ativos=true`)
    // Abrir um comentário vai direto para a análise dele.
    expect(links).toContain('/respostas?analisar=5')
  })
})
