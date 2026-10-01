import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, type Component } from 'vue'
import type { AnaliseIa, ConfigIa, Empresa, Painel, Perfil, RespostaDetalhe, RespostaItem } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import Medidor from '@/components/ui/Medidor.vue'
import { navegacaoPrincipal } from '@/layouts/navegacao'
import { router as rotasDoApp } from '@/router'
import IaView from '@/modulos/configuracoes/IaView.vue'
import MinhaContaView from '@/modulos/conta/MinhaContaView.vue'
import AbaEmpresasContatos from '@/modulos/contatos/AbaEmpresas.vue'
import PainelView from '@/modulos/painel/PainelView.vue'
import RespostasView from '@/modulos/respostas/RespostasView.vue'
import { apiFalsa } from './apiFalsa'

const HOJE = hojeIso()

const USUARIO = { id: 1, nome: 'Ana Paula', email: 'a@x.com', cargo: null, situacao: 'ativo' as const, email_confirmado: true, ultimo_acesso: null, superadmin: false }

function entrar(permissoes: string[], opcoes: { perfil?: Perfil; iaAtiva?: boolean; prefs?: Record<string, boolean> } = {}) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { ...USUARIO, perfil: opcoes.perfil ?? 'gestor', ...(opcoes.prefs ?? {}) },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null, ia_ativa: opcoes.iaAtiva ?? false },
      permissoes,
    },
    false,
  )
}

let router: Router

async function abrir(caminho: string, componente: Component, rota = caminho.split('?')[0]!): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: rota, component: componente },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return w
}

const botao = (w: VueWrapper, texto: string | RegExp) => {
  const b = w.findAll('button').find((x) => (typeof texto === 'string' ? x.text().trim() === texto : texto.test(x.text())))
  if (!b) throw new Error(`Sem o botão "${texto}"`)
  return b
}
const rotulos = (w: VueWrapper) => w.findAll('label').map((l) => l.text().trim())
/** O interruptor (role="switch") pelo texto do rótulo. */
function interruptor(w: VueWrapper, rotulo: string) {
  const label = w.findAll('label').find((l) => l.text().trim() === rotulo)
  if (!label) throw new Error(`Sem o interruptor "${rotulo}"`)
  return w.get(`[id="${label.attributes('for')}"]`)
}
const ultimoAviso = () => avisos.at(-1)?.mensagem ?? ''

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  avisos.splice(0)
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
  document.body.innerHTML = ''
})

// ── Painel ──────────────────────────────────────────────────────────────────

function painel(extra: Partial<Painel> = {}): Painel {
  return {
    periodo: { de: somarDias(HOJE, -89), ate: HOJE, anterior: { de: somarDias(HOJE, -179), ate: somarDias(HOJE, -90) } },
    nps: { valor: 34, faixa: 'pode_melhorar', promotores: 6, neutros: 2, detratores: 2, total: 10, pct: { promotores: 60, neutros: 20, detratores: 20 }, decisores: { valor: null, total: 0 } },
    variacao: null,
    csat: { percentual: null, media: null, total: 0, satisfeitos: 0 },
    taxa_resposta: { percentual: 18, responderam: 12, convidados: 67, amostra_pequena: true },
    movimentacao: { resgatados: 0, deixaram_de_ser_promotores: 0, itens: [] },
    atencao: { acoes_abertas: 0, acoes_vencidas: 0, tudo_em_dia: true, empresas: [], receita_em_risco: { valor: 0, empresas: 0, sem_valor: 0 } },
    temas: [
      { chave: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 38, nota_media: 5.9, reclamacoes: 21, variacao: 9 },
      { chave: 'atendimento', rotulo: 'Atendimento', mencoes: 27, nota_media: 8.8, reclamacoes: 1, variacao: -3 },
      { chave: 'comunicacao', rotulo: 'Comunicação', mencoes: 4, nota_media: 7, reclamacoes: 0, variacao: null },
    ],
    comentarios: [],
    evolucao: [],
    empresas: { menor: [], maior: [] },
    palavras: [],
    primeiros_passos: { contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: true },
    picos: [{ tema: 'prazo_entrega', rotulo: 'Prazo e entrega', reclamacoes: 7, media_anterior: 1.5, de: somarDias(HOJE, -6), ate: HOJE }],
    ...extra,
  }
}

describe('Painel: picos e temas (4b)', () => {
  it('faixa de picos com "Ver respostas" (reclamações do tema nos 7 dias, empresas ativas)', async () => {
    entrar(['painel.ver', 'respostas.ver'])
    apiFalsa({ 'GET /painel': () => painel() })
    const w = await abrir('/inicio', PainelView)
    const picos = w.findAll('[data-pico]')
    expect(picos).toHaveLength(1)
    expect(picos[0]!.text()).toContain('Pico de reclamações em Prazo e entrega: 7 nos últimos 7 dias; a média era 1,5 por semana.')
    const link = picos[0]!.find('a')
    expect(Object.fromEntries(new URL(link.attributes('href')!, 'http://x').searchParams)).toEqual({
      tema: 'prazo_entrega',
      reclamacao: 'true',
      so_ativos: 'true',
      de: somarDias(HOJE, -6),
      ate: HOJE,
    })
  })

  it('sem picos (ou servidor antigo), nada aparece; sem respostas.ver, sem o botão', async () => {
    entrar(['painel.ver'])
    apiFalsa({ 'GET /painel': () => painel() })
    let w = await abrir('/inicio', PainelView)
    expect(w.find('[data-pico]').text()).not.toContain('Ver respostas')
    w.unmount()
    const { picos: _p, ...antigo } = painel({ picos: [] })
    apiFalsa({ 'GET /painel': () => antigo })
    w = await abrir('/inicio', PainelView)
    expect(w.find('[data-pico]').exists()).toBe(false)
  })

  it('temas mostram as reclamações e a variação com seta', async () => {
    entrar(['painel.ver'])
    apiFalsa({ 'GET /painel': () => painel() })
    const w = await abrir('/inicio', PainelView)
    const temas = w.get('[aria-labelledby="t-temas"]')
    expect(temas.text()).toContain('21 reclamações')
    expect(temas.text()).not.toContain('+9 em relação ao período anterior') // por extenso, sem ambiguidade
    expect(temas.text()).toContain('9 menções a mais que no período anterior')
    expect(temas.text()).toContain('1 reclamação')
    expect(temas.text()).toContain('3 menções a menos que no período anterior')
  })
})

// ── Respostas ───────────────────────────────────────────────────────────────

function resposta(id: number, extra: Partial<RespostaItem> = {}): RespostaItem {
  return {
    id,
    formulario: { id: 1, nome: 'Pesquisa' },
    contato: { id: 101, nome: 'Bruno Lima', email: 'b@x.com', perfil: null },
    empresa: { id: 14, nome: 'Mercado Bom Preço', grupo: null },
    canal: 'email',
    nota: 4,
    tipo_nota: 'nps',
    grupo: 'detrator',
    comentario: 'A entrega atrasou de novo.',
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
  }
}

const ANALISADA: AnaliseIa = {
  situacao: 'analisada',
  sentimento: 'misto',
  resumo: 'Reclama do atraso, mas elogia o atendimento.',
  temas: [
    { tema: 'prazo_entrega', sentimento: 'negativo' },
    { tema: 'atendimento', sentimento: 'positivo' },
  ],
  em: '2026-09-28T11:00:00-03:00',
}

function apiRespostas(lista: RespostaItem[]) {
  return apiFalsa({
    'GET /respostas': () => ({ itens: lista, total: lista.length, pagina: 1, por_pagina: 50, metricas: { nps: null, csat: null, total: lista.length } }),
    'GET /respostas/temas': () => [
      { chave: 'prazo_entrega', rotulo: 'Prazo e entrega' },
      { chave: 'atendimento', rotulo: 'Atendimento' },
    ],
    'GET /respostas/:id': ({ caminho }): RespostaDetalhe => {
      const r = lista.find((x) => caminho === `/respostas/${x.id}`)!
      return { ...r, perguntas: [], convite: null, acoes: [] }
    },
    'GET /cadastros/grupos': () => [],
    'GET /cadastros/perfis': () => [],
  })
}

describe('Respostas: IA e contexto da entrega (4b)', () => {
  it('com a IA ativa: filtros "Sentimento (IA)" e "Só reclamações", que vão para a API', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    entrar(['respostas.ver'], { iaAtiva: true })
    const { chamadas } = apiRespostas([resposta(5)])
    const w = await abrir('/respostas', RespostasView)
    expect(rotulos(w)).toContain('Sentimento (IA)')
    expect(w.text()).toContain('Só reclamações')
    const label = w.findAll('label').find((l) => l.text() === 'Sentimento (IA)')!
    await w.get(`[id="${label.attributes('for')}"]`).setValue('negativo')
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    expect(router.currentRoute.value.query).toMatchObject({ sentimento: 'negativo' })
    const ultima = chamadas.filter((c) => c.caminho === '/respostas').at(-1)!
    expect(ultima.url.searchParams.get('sentimento')).toBe('negativo')
  })

  it('sem IA na conta e sem análises: os filtros de IA não aparecem', async () => {
    entrar(['respostas.ver'], { iaAtiva: false })
    apiRespostas([resposta(5, { ia: null })])
    const w = await abrir('/respostas', RespostasView)
    expect(rotulos(w)).not.toContain('Sentimento (IA)')
    expect(w.text()).not.toContain('Só reclamações')
  })

  it('resposta já analisada: selo do sentimento na lista e os filtros aparecem mesmo sem a IA ativa', async () => {
    entrar(['respostas.ver'], { iaAtiva: false })
    apiRespostas([resposta(5, { ia: ANALISADA }), resposta(6, { ia: { situacao: 'pendente', sentimento: null, resumo: null, temas: null, em: null } })])
    const w = await abrir('/respostas', RespostasView)
    expect(rotulos(w)).toContain('Sentimento (IA)')
    const selos = w.findAll('[data-sentimento]')
    expect(selos.length).toBeGreaterThan(0)
    expect(selos[0]!.text()).toContain('Sentimento pela IA:')
    expect(selos[0]!.text()).toContain('Misto')
    // Só a analisada tem selo (a pendente, não): uma no computador e outra no celular.
    expect(selos).toHaveLength(2)
  })

  it('contexto vindo de Entregas: chip em "Mostrando", vai para a API e sai no X', async () => {
    entrar(['respostas.ver'])
    const { chamadas } = apiRespostas([resposta(5)])
    const w = await abrir('/respostas?motorista=Josu%C3%A9%20Almeida&rota=Sul', RespostasView)
    const chips = w.findAll('[data-chip-contexto]')
    expect(chips.map((c) => c.text())).toEqual(['Motorista: Josué Almeida', 'Rota: Sul'])
    const pedido = chamadas.find((c) => c.caminho === '/respostas')!
    expect(pedido.url.searchParams.get('motorista')).toBe('Josué Almeida')
    expect(pedido.url.searchParams.get('rota')).toBe('Sul')
    await chips[0]!.get('button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ rota: 'Sul' })
  })

  it('"Análise da IA" no Analisar: pronta (resumo, sentimento, temas com sentimento) e as outras situações', async () => {
    entrar(['respostas.ver'], { iaAtiva: true })
    apiRespostas([
      resposta(5, { ia: ANALISADA }),
      resposta(6, { ia: { situacao: 'pendente', sentimento: null, resumo: null, temas: null, em: null } }),
      resposta(7, { ia: { situacao: 'falhou', sentimento: null, resumo: null, temas: null, em: null } }),
      resposta(8, { ia: { situacao: 'limite', sentimento: null, resumo: null, temas: null, em: null } }),
      resposta(9, { ia: null }),
    ])
    let w = await abrir('/respostas?analisar=5', RespostasView)
    const caixa = w.get('[data-analise-ia]')
    expect(caixa.text()).toContain('Reclama do atraso, mas elogia o atendimento.')
    expect(caixa.text()).toContain('Sentimento:')
    expect(caixa.text()).toContain('Misto')
    expect(caixa.text()).toContain('A IA lê só o texto do cliente, as opções que ele marcou e a nota.')
    expect(caixa.text()).toContain('Prazo e entrega · reclamação')
    expect(caixa.text()).toContain('Atendimento · elogio')
    for (const [id, titulo] of [
      [6, 'Aguardando análise'],
      [7, 'Não foi possível analisar'],
      [8, 'Limite do mês atingido'],
    ] as const) {
      w.unmount()
      w = await abrir(`/respostas?analisar=${id}`, RespostasView)
      expect(w.get('[data-analise-ia]').text()).toContain(titulo)
    }
    w.unmount()
    w = await abrir('/respostas?analisar=9', RespostasView)
    expect(w.find('[data-analise-ia]').exists()).toBe(false)
  })

  it('sem a IA ativa na conta, a caixa só aparece quando a análise está pronta', async () => {
    entrar(['respostas.ver'], { iaAtiva: false })
    apiRespostas([resposta(5, { ia: ANALISADA }), resposta(8, { ia: { situacao: 'limite', sentimento: null, resumo: null, temas: null, em: null } })])
    let w = await abrir('/respostas?analisar=8', RespostasView)
    expect(w.text()).toContain('A entrega atrasou de novo.')
    expect(w.find('[data-analise-ia]').exists()).toBe(false)
    w.unmount()
    w = await abrir('/respostas?analisar=5', RespostasView)
    expect(w.get('[data-analise-ia]').text()).toContain('Reclama do atraso, mas elogia o atendimento.')
  })
})

// ── Minha conta ─────────────────────────────────────────────────────────────

function apiConta(patch: Parameters<typeof apiFalsa>[0][string]) {
  return apiFalsa({
    'GET /auth/regras-senha': () => ({ minimo: 10, maximo: 128, exige: [] }),
    'GET /eu/sessoes': () => [],
    'PATCH /eu': patch,
  })
}

describe('Minha conta: e-mails do Toqqi (4b)', () => {
  it('só para quem tem painel.ver', async () => {
    entrar(['respostas.ver'])
    apiConta(() => ({}))
    const w = await abrir('/minha-conta', MinhaContaView)
    expect(w.text()).not.toContain('E-mails do Toqqi')
  })

  it('cada interruptor salva na hora (PATCH /eu) e atualiza a sessão', async () => {
    entrar(['painel.ver'], { prefs: { recebe_resumo_semanal: true, recebe_alertas: false } })
    const { chamadas } = apiConta(({ corpo }) => ({ ...USUARIO, perfil: 'gestor', recebe_resumo_semanal: true, recebe_alertas: false, ...(corpo as object) }))
    const w = await abrir('/minha-conta', MinhaContaView)
    expect(w.text()).toContain('E-mails do Toqqi')
    expect(interruptor(w, 'Resumo semanal').attributes('aria-checked')).toBe('true')
    const alerta = interruptor(w, 'Alerta de pico de reclamações')
    expect(alerta.attributes('aria-checked')).toBe('false')
    await alerta.trigger('click')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'PATCH')!.corpo).toEqual({ recebe_alertas: true })
    expect(interruptor(w, 'Alerta de pico de reclamações').attributes('aria-checked')).toBe('true')
    expect(useSessaoStore().usuario?.recebe_alertas).toBe(true)
    expect(ultimoAviso()).toContain('alertas de pico')
  })

  it('se não salvar, volta como estava e avisa', async () => {
    entrar(['painel.ver'], { prefs: { recebe_resumo_semanal: true, recebe_alertas: true } })
    apiConta(() => new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Não deu para salvar.' } }), { status: 500 }))
    const w = await abrir('/minha-conta', MinhaContaView)
    await interruptor(w, 'Resumo semanal').trigger('click')
    await flushPromises()
    expect(interruptor(w, 'Resumo semanal').attributes('aria-checked')).toBe('true')
    expect(ultimoAviso()).toBe('Não deu para salvar.')
  })
})

// ── Configurações › IA ──────────────────────────────────────────────────────

const CONFIG: ConfigIa = { disponivel: true, provedor: 'OpenAI', analise_respostas: true, mes: '2026-10', analises: 412, limite: 500, pendentes: 12, falharam_no_mes: 3 }

function apiIa(config: ConfigIa, extra: Parameters<typeof apiFalsa>[0] = {}) {
  let atual = { ...config }
  return apiFalsa({
    'GET /conta/ia': () => atual,
    'PUT /conta/ia': ({ corpo }) => {
      const ligar = (corpo as { analise_respostas: boolean }).analise_respostas
      atual = { ...atual, analise_respostas: ligar, pendentes: ligar ? atual.pendentes : 0 }
      return atual
    },
    'POST /conta/ia/analisar-recentes': () => ({ marcadas: 37, restantes_no_mes: 39 }),
    'GET /eu': () => ({ usuario: { ...USUARIO, perfil: 'admin' }, conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null, ia_ativa: false }, permissoes: ['configuracoes.gerenciar'] }),
    ...extra,
  })
}

describe('Configurações › IA (4b)', () => {
  it('situação, uso do mês (barra X de Y), fila e o que vai para a IA', async () => {
    entrar(['configuracoes.gerenciar'], { perfil: 'admin' })
    apiIa(CONFIG)
    const w = await abrir('/configuracoes/ia', IaView)
    expect(w.get('[data-situacao-ia]').text()).toContain('Ligada (OpenAI)')
    const medidor = w.get('[role="meter"]')
    expect(medidor.attributes('aria-valuenow')).toBe('412')
    expect(medidor.attributes('aria-valuemax')).toBe('500')
    expect(medidor.attributes('aria-valuetext')).toBe('412 de 500 análises')
    expect(w.text()).toContain('Outubro de 2026'.toLowerCase())
    expect(w.text()).toContain('Na fila12')
    expect(w.text()).toContain('Ainda dá para analisar76')
    expect(w.text()).toContain('Nunca o nome, o e-mail')
    expect(w.get('nav[aria-label="Seções de configurações"]').text()).toContain('IA')
  })

  it('desligar com comentários na fila pede confirmação; depois salva e atualiza a sessão', async () => {
    entrar(['configuracoes.gerenciar'], { perfil: 'admin', iaAtiva: true })
    const { chamadas } = apiIa(CONFIG)
    const w = await abrir('/configuracoes/ia', IaView)
    await interruptor(w, 'Analisar comentários com IA').trigger('click')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.mensagem).toContain('12 comentários estão na fila')
    responderConfirmacao(true)
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'PUT')!.corpo).toEqual({ analise_respostas: false })
    expect(ultimoAviso()).toContain('Análise com IA desligada')
    expect(chamadas.some((c) => c.caminho === '/eu')).toBe(true)
    expect(useSessaoStore().conta?.ia_ativa).toBe(false)
    expect(interruptor(w, 'Analisar comentários com IA').attributes('aria-checked')).toBe('false')
  })

  it('"Analisar comentários dos últimos 90 dias": confirma, manda e conta quantos foram para a fila', async () => {
    entrar(['configuracoes.gerenciar'], { perfil: 'admin' })
    const { chamadas } = apiIa(CONFIG)
    const w = await abrir('/configuracoes/ia', IaView)
    await botao(w, /Analisar comentários dos últimos 90 dias/).trigger('click')
    await flushPromises()
    expect(estadoConfirmacao.titulo).toBe('Analisar os comentários dos últimos 90 dias?')
    responderConfirmacao(true)
    await flushPromises()
    expect(chamadas.filter((c) => c.metodo === 'POST' && c.caminho === '/conta/ia/analisar-recentes')).toHaveLength(1)
    expect(ultimoAviso()).toBe('37 comentários foram para a fila. Restam 39 análises neste mês.')
    // Os números voltam a ser buscados sem trocar a tela pelo esqueleto.
    expect(chamadas.filter((c) => c.caminho === '/conta/ia' && c.metodo === 'GET')).toHaveLength(2)
    expect(w.find('[role="meter"]').exists()).toBe(true)
  })

  it('409 (IA indisponível): mostra a mensagem do servidor', async () => {
    entrar(['configuracoes.gerenciar'], { perfil: 'admin' })
    apiIa(CONFIG, {
      'POST /conta/ia/analisar-recentes': () => new Response(JSON.stringify({ erro: { codigo: 'ia_indisponivel', mensagem: 'A IA não está disponível agora.' } }), { status: 409 }),
    })
    const w = await abrir('/configuracoes/ia', IaView)
    await botao(w, /Analisar comentários dos últimos 90 dias/).trigger('click')
    await flushPromises()
    responderConfirmacao(true)
    await flushPromises()
    expect(ultimoAviso()).toBe('A IA não está disponível agora.')
  })

  it('sem a IA na plataforma: interruptor e botão desligados, com o motivo', async () => {
    entrar(['configuracoes.gerenciar'], { perfil: 'admin' })
    apiIa({ ...CONFIG, disponivel: false, provedor: null, analise_respostas: false, analises: 0, pendentes: 0 })
    const w = await abrir('/configuracoes/ia', IaView)
    expect(w.get('[data-situacao-ia]').text()).toContain('Não está ligada')
    expect(interruptor(w, 'Analisar comentários com IA').attributes('disabled')).toBeDefined()
    expect(botao(w, /Analisar comentários dos últimos 90 dias/).attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Disponível quando a IA estiver ligada na plataforma.')
  })
})

// ── Cadastro de empresas: atalho para o histórico ───────────────────────────

describe('Contatos › Empresas: "Ver histórico" (4b)', () => {
  const EMPRESA: Empresa = {
    id: 14,
    nome: 'Mercado Bom Preço',
    documento: null,
    grupo: null,
    segmento: null,
    responsavel: null,
    valor_mensal: null,
    cliente_desde: null,
    codigo_externo: null,
    ativa: true,
    contatos: 3,
    criada_em: '2026-01-01T10:00:00-03:00',
  }
  const apiEmpresas = () =>
    apiFalsa({
      'GET /empresas': () => ({ itens: [EMPRESA], total: 1, pagina: 1, por_pagina: 50 }),
      'GET /cadastros/grupos': () => [],
      'GET /cadastros/segmentos': () => [],
      'GET /responsaveis': () => [],
    })

  it('com relatorios.ver, o menu da empresa leva ao histórico dela', async () => {
    entrar(['contatos.ver', 'relatorios.ver'])
    apiEmpresas()
    const w = await abrir('/contatos', AbaEmpresasContatos)
    await w.get('button[aria-label="Ações para Mercado Bom Preço"]').trigger('click')
    await flushPromises()
    const item = w.findAll('[role="menuitem"]').find((i) => i.text().includes('Ver histórico'))!
    expect(item.attributes('href')).toBe('/relatorios/historico?empresa_id=14')
  })

  it('sem relatorios.ver (e sem editar), não há menu', async () => {
    entrar(['contatos.ver'])
    apiEmpresas()
    const w = await abrir('/contatos', AbaEmpresasContatos)
    expect(w.find('button[aria-label="Ações para Mercado Bom Preço"]').exists()).toBe(false)
  })
})

// ── Rotas, menu e medidor ───────────────────────────────────────────────────

describe('rotas e menu da 4b', () => {
  it('Relatórios saiu do "em breve" e marca as páginas de dentro', () => {
    const item = navegacaoPrincipal.find((i) => i.rotulo === 'Relatórios')!
    expect(item.emBreve).toBeFalsy()
    expect(item.para).toBe('/relatorios/empresas')
    expect(item.prefixo).toBe('/relatorios')
  })

  it('cada rota nova pede a permissão certa; /relatorios leva para Empresas com o mesmo filtro', () => {
    const temas = rotasDoApp.resolve('/relatorios/temas')
    expect(temas.name).toBe('relatorios')
    expect(temas.params.aba).toBe('temas')
    expect(temas.meta.permissao).toBe('relatorios.ver')
    expect(rotasDoApp.resolve('/configuracoes/ia').meta.permissao).toBe('configuracoes.gerenciar')
    const redirecionar = rotasDoApp.getRoutes().find((r) => r.path === '/relatorios')!.redirect as (to: unknown) => unknown
    expect(redirecionar({ query: { periodo: '30' } })).toEqual({ path: '/relatorios/empresas', query: { periodo: '30' } })
  })
})

describe('Medidor (ui)', () => {
  it('role meter com X de Y; perto do limite fica em atenção e no limite, em erro', () => {
    const w = mount(Medidor, { props: { valor: 450, maximo: 500, rotulo: 'Análises' } })
    const m = w.get('[role="meter"]')
    expect(m.attributes('aria-label')).toBe('Análises')
    expect(m.attributes('aria-valuetext')).toBe('450 de 500')
    expect(m.get('div').classes()).toContain('bg-atencao')
    expect(m.get('div').attributes('style')).toContain('width: 90%')
    const cheio = mount(Medidor, { props: { valor: 600, maximo: 500, rotulo: 'Análises' } })
    expect(cheio.get('[role="meter"]').attributes('aria-valuenow')).toBe('500')
    expect(cheio.get('[role="meter"] div').classes()).toContain('bg-erro')
    const pouco = mount(Medidor, { props: { valor: 10, maximo: 500, rotulo: 'Análises' } })
    expect(pouco.get('[role="meter"] div').classes()).toContain('bg-grafico-serie')
  })
})
