// Etapa 5d (docs/api-etapa-5d.md §6.1 e §6.2) com a API simulada: o cartão "Resumo da IA" do painel (sem item, gerando,
// item, contagem, conta pausada, cota esgotada, 409/429/503, some sem IA, troca de filtro relê) e o "Parecer da IA" dos
// relatórios no painel lateral. E os achados da revisão: relógio do aparelho torto, nome fixo do botão para o leitor de
// tela, corridas (leitura antiga depois da geração; geração que termina depois de trocar o filtro), aviso do 429 que sai
// com a contagem, anúncio limpo na troca de filtro, contagem parada ao sair, foco depois de "Tentar de novo", o botão do
// parecer que volta depois de uma primeira leitura que falhou e a aba do histórico sem o parecer.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { defineComponent, h, nextTick, ref, type Component, type Ref } from 'vue'
import type { CotaIa, EstadoGeracaoIa, FiltrosGeracaoIa, ItemGeracaoIa, Painel, Perfil } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { useAssistenteStore } from '@/stores/assistente'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora, hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import CartaoResumoIa from '@/modulos/painel/CartaoResumoIa.vue'
import PainelView from '@/modulos/painel/PainelView.vue'
import RelatoriosView from '@/modulos/relatorios/RelatoriosView.vue'
import { MENSAGEM_COTA_ESGOTADA, TEXTOS_PARECER, TEXTOS_RESUMO } from '@/modulos/ia/logica'
import { apiFalsa, type Chamada } from './apiFalsa'

const HOJE = hojeIso()
const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
const erroApi = (status: number, codigo: string, mensagem: string) => new Response(JSON.stringify({ erro: { codigo, mensagem } }), { status })
/** O nome que o leitor de tela lê num elemento: o texto, sem o que está marcado com aria-hidden. */
function nomeAcessivel(el: { element: Element }): string {
  const copia = el.element.cloneNode(true) as Element
  copia.querySelectorAll('[aria-hidden="true"]').forEach((x) => x.remove())
  return t(copia.textContent ?? '')
}

function painel(): Painel {
  return {
    periodo: { de: somarDias(HOJE, -89), ate: HOJE, anterior: null },
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
    variacao: null,
    csat: { percentual: 82, media: 4.21, total: 57, satisfeitos: 47 },
    taxa_resposta: { percentual: 18, responderam: 12, convidados: 67, amostra_pequena: true },
    movimentacao: { resgatados: 0, deixaram_de_ser_promotores: 0, itens: [] },
    atencao: { acoes_abertas: 0, acoes_vencidas: 0, tudo_em_dia: true, empresas: [], receita_em_risco: { valor: 0, empresas: 0, sem_valor: 0 } },
    temas: [],
    comentarios: [],
    evolucao: [],
    empresas: { menor: [], maior: [] },
    palavras: [],
    primeiros_passos: { contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: true },
  }
}

const COTA: CotaIa = { usadas: 12, limite: 500, restantes: 488, mes: '2026-10' }
const COTA_DEPOIS: CotaIa = { usadas: 13, limite: 500, restantes: 487, mes: '2026-10' }
const GERADO_EM = '2026-10-02T17:30:00Z'
const RESUMO = {
  melhorar: 'O prazo de entrega puxou o NPS para baixo nos últimos 90 dias.',
  funciona: 'O atendimento foi elogiado em 12 comentários.',
  proximo_passo: 'Ligue para as 3 empresas com detratores nesta semana.',
}

function item<C>(conteudo: C, extra: Partial<ItemGeracaoIa<C>> = {}): ItemGeracaoIa<C> {
  return {
    conteudo,
    filtros: {},
    gerado_em: GERADO_EM,
    gerado_por: { id: 1, nome: 'Ana Paula' },
    modelo: 'equilibrado',
    modelo_rotulo: 'Equilibrado',
    estilo: 'equilibrada',
    ...extra,
  }
}

function estado<C>(extra: Partial<EstadoGeracaoIa<C>> = {}): EstadoGeracaoIa<C> {
  return { disponivel: true, motivo: null, cota: COTA, item: null, pode_gerar_em: null, ...extra }
}

function entrar(permissoes: string[], perfil: Perfil = 'gestor') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana Paula', email: 'a@x.com', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 42, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

/** O assistente já leu o estado (cota de 12 de 500), como acontece ao entrar. */
function assistenteComCota() {
  const assistente = useAssistenteStore()
  assistente.estado = { disponivel: true, motivo: null, cota: COTA, sugestoes: [] }
  return assistente
}

async function abrir(caminho: string, rota: string, componente: Component, teleportReal = false): Promise<VueWrapper> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: rota, name: rota === '/relatorios/:aba' ? 'relatorios' : undefined, component: componente },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), {
    global: { plugins: [router], stubs: teleportReal ? {} : { teleport: true } },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

const DO_PAINEL = ['painel.ver', 'painel.exportar', 'respostas.ver', 'contatos.ver']
const pedidos = (chamadas: Chamada[], metodo: string, caminho: string) => chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)
const consulta = (c: Chamada | undefined) => Object.fromEntries(c?.url.searchParams ?? [])
const cartaoResumo = (w: VueWrapper) => w.get('[data-resumo-ia]')
/** O botão de gerar dentro do cartão ou do painel lateral. */
function botaoGerar(el: { element: Element }): DOMWrapper<HTMLButtonElement> {
  const b = el.element.querySelector<HTMLButtonElement>('[data-gerar-ia]')
  if (!b) throw new Error('Sem o botão de gerar')
  return new DOMWrapper(b)
}

function apiPainel(rotas: Parameters<typeof apiFalsa>[0] = {}) {
  return apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /painel/resumo-ia': () => estado(), ...rotas })
}

/** Filtros do resumo: os últimos 90 e os últimos 7 dias. */
const F90: FiltrosGeracaoIa = { de: somarDias(HOJE, -89), ate: HOJE, so_ativos: true }
const F7: FiltrosGeracaoIa = { de: somarDias(HOJE, -6), ate: HOJE, so_ativos: true }
const doPeriodo = (c: Chamada, f: FiltrosGeracaoIa) => c.url.searchParams.get('de') === f.de || (c.corpo as FiltrosGeracaoIa | undefined)?.de === f.de

/** Só o cartão do resumo, com os filtros num ref (trocar o ref = trocar os filtros da tela, sem o resto do painel). */
function montarCartao(filtros: Ref<FiltrosGeracaoIa>): Promise<VueWrapper> {
  const Pagina = defineComponent({ render: () => h(CartaoResumoIa, { filtros: filtros.value, periodo: 'Período' }) })
  return abrir('/inicio', '/inicio', Pagina)
}

/** Uma resposta que só sai quando o teste liberar. */
function segurar<T>(valor: () => T) {
  let liberar!: () => void
  const pronto = new Promise<void>((r) => (liberar = r))
  return {
    rota: async () => {
      await pronto
      return valor()
    },
    liberar: () => liberar(),
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
})

describe('Painel: cartão "Resumo da IA"', () => {
  it('sem item: logo abaixo do Resumo (NPS), o texto curto e "Gerar resumo"; lê com os mesmos filtros do painel', async () => {
    entrar(DO_PAINEL)
    const { chamadas } = apiPainel()
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    // Início v2: o cartão do NPS virou o "Resumo" (medidor + O que mudou); o da IA vem logo depois dele
    expect(w.get('[aria-labelledby="t-resumo"]').element.nextElementSibling).toBe(cartao.element)
    expect(t(cartao.get('h2').text())).toBe('Resumo da IA')
    expect(cartao.text()).toContain('Últimos 90 dias')
    expect(t(cartao.get('[data-vazio]').text())).toBe(TEXTOS_RESUMO.vazio)
    expect(t(botaoGerar(cartao).text())).toBe('Gerar resumo')
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBeUndefined()
    const lido = pedidos(chamadas, 'GET', '/painel/resumo-ia')
    expect(lido).toHaveLength(1)
    expect(consulta(lido[0])).toEqual(consulta(pedidos(chamadas, 'GET', '/painel')[0]))
    expect(consulta(lido[0])).toEqual({ de: somarDias(HOJE, -89), ate: HOJE, so_ativos: 'true' })
    expect(cartao.find('[data-meta]').exists()).toBe(false)
  })

  it('gerar: botão ocupado e "Lendo os números do período…"; depois as 3 frases, o rodapé, "Restam X de Y" e a cota do assistente', async () => {
    entrar(DO_PAINEL)
    const assistente = assistenteComCota()
    const post = segurar(() => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: null }))
    const { chamadas } = apiPainel({ 'POST /painel/resumo-ia': post.rota })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()

    // Gerando: o botão continua no Tab (aria-disabled), ocupado; o esqueleto anuncia o que está acontecendo.
    expect(botaoGerar(cartao).attributes('aria-busy')).toBe('true')
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBe('true')
    expect(botaoGerar(cartao).attributes('disabled')).toBeUndefined()
    expect(cartao.get('[data-gerando] [role="status"]').attributes('aria-label')).toBe('Lendo os números do período…')
    expect(cartao.get('[data-gerando]').text()).toContain('Lendo os números do período…')
    expect(pedidos(chamadas, 'POST', '/painel/resumo-ia').map((c) => c.corpo)).toEqual([{ de: somarDias(HOJE, -89), ate: HOJE, grupo_id: null, so_ativos: true }])
    // Um clique a mais enquanto gera não manda outro pedido.
    await botaoGerar(cartao).trigger('click')
    expect(pedidos(chamadas, 'POST', '/painel/resumo-ia')).toHaveLength(1)

    post.liberar()
    await flushPromises()
    expect(cartao.find('[data-gerando]').exists()).toBe(false)
    expect(cartao.findAll('[data-frases] dt').map((d) => t(d.text()))).toEqual(['Precisa melhorar', 'Está funcionando', 'Próximo passo'])
    expect(cartao.findAll('[data-frases] dd').map((d) => t(d.text()))).toEqual([RESUMO.melhorar, RESUMO.funciona, RESUMO.proximo_passo])
    expect(t(cartao.get('[data-gerado]').text())).toBe(`Gerado em ${formatarDataHora(GERADO_EM)} por Ana Paula · Equilibrado`)
    expect(t(cartao.get('[data-restam]').text())).toBe('Restam 487 de 500 análises este mês')
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo')
    expect(assistente.cota).toEqual(COTA_DEPOIS)
    // O texto gerado vai inteiro para a região aria-live.
    const anuncio = cartao.get('[data-anuncio]')
    expect(anuncio.attributes('aria-live')).toBe('polite')
    expect(t(anuncio.text())).toBe(`Resumo gerado. Precisa melhorar: ${RESUMO.melhorar} Está funcionando: ${RESUMO.funciona} Próximo passo: ${RESUMO.proximo_passo}`)
  })

  it('contagem: depois de gerar, "Gerar de novo em N s" desabilitado até pode_gerar_em (e avisa quando libera)', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    apiPainel({
      'POST /painel/resumo-ia': () => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: new Date(Date.now() + 30_000).toISOString() }),
    })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo em 30 s')
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBe('true')
    // O leitor de tela lê sempre "Gerar de novo": a contagem fica fora do nome (senão anunciaria cada segundo).
    expect(nomeAcessivel(botaoGerar(cartao))).toBe('Gerar de novo')
    expect(botaoGerar(cartao).get('[data-contagem]').attributes('aria-hidden')).toBe('true')

    vi.advanceTimersByTime(5_000)
    await nextTick()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo em 25 s')
    expect(nomeAcessivel(botaoGerar(cartao))).toBe('Gerar de novo')
    // Clicar durante a contagem não faz nada.
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo em 25 s')

    vi.advanceTimersByTime(25_000)
    await nextTick()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo')
    expect(botaoGerar(cartao).find('[data-contagem]').exists()).toBe(false)
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBeUndefined()
    expect(t(cartao.get('[data-anuncio]').text())).toBe('Já dá para gerar de novo.')
  })

  it('relógio do aparelho atrasado 1 min: a espera dura 30 s no aparelho (não 1 min e meio)', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    // O servidor está 1 min à frente: o "daqui a 30 s" dele é daqui a 90 s no relógio do aparelho.
    apiPainel({ 'POST /painel/resumo-ia': () => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: new Date(Date.now() + 90_000).toISOString() }) })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo em 30 s')
    vi.advanceTimersByTime(29_000)
    await nextTick()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo em 1 s')
    vi.advanceTimersByTime(1_000)
    await nextTick()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo')
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBeUndefined()
    expect(t(cartao.get('[data-anuncio]').text())).toBe('Já dá para gerar de novo.')
  })

  it('relógio do aparelho adiantado: pode_gerar_em já passou para ele; o 429 da API diz quanto falta e a contagem segue', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    apiPainel({
      'GET /painel/resumo-ia': () => estado({ item: item(RESUMO), pode_gerar_em: new Date(Date.now() - 20_000).toISOString() }),
      'POST /painel/resumo-ia': () => erroApi(429, 'aguarde', 'Aguarde 10 s para gerar de novo.'),
    })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo')
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo em 10 s')
    vi.advanceTimersByTime(10_000)
    await nextTick()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo')
  })

  it('pode_gerar_em no GET (alguém gerou há pouco): a contagem já começa; item de outro modelo continua visível', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    apiPainel({
      'GET /painel/resumo-ia': () =>
        estado({ item: item(RESUMO, { modelo: 'detalhado', modelo_rotulo: 'Mais detalhado', gerado_por: null }), pode_gerar_em: new Date(Date.now() + 12_000).toISOString() }),
    })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    expect(t(cartao.get('[data-gerado]').text())).toBe(`Gerado em ${formatarDataHora(GERADO_EM)} · Mais detalhado`)
    expect(cartao.find('[data-restam]').exists()).toBe(false) // só depois de gerar
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo em 12 s')
    vi.advanceTimersByTime(12_000)
    await nextTick()
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo')
    expect(t(cartao.get('[data-anuncio]').text())).toBe('') // a espera não foi desta tela: nada a anunciar
  })

  it('conta pausada: "O resumo volta quando a assinatura estiver em dia.", sem botão', async () => {
    entrar(DO_PAINEL)
    apiPainel({ 'GET /painel/resumo-ia': () => estado({ disponivel: false, motivo: 'conta_pausada' }) })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    expect(t(cartao.get('[data-bloqueio]').text())).toBe('O resumo volta quando a assinatura estiver em dia.')
    expect(cartao.find('[data-gerar-ia]').exists()).toBe(false)
    expect(cartao.find('[data-vazio]').exists()).toBe(false)
  })

  it('cota esgotada: o item salvo continua, a mensagem no lugar do botão e o link para Configurações › IA só para o administrador', async () => {
    entrar([...DO_PAINEL, 'configuracoes.gerenciar'], 'admin')
    apiPainel({ 'GET /painel/resumo-ia': () => estado({ disponivel: false, motivo: 'cota_esgotada', item: item(RESUMO) }) })
    let w = await abrir('/inicio', '/inicio', PainelView)
    let cartao = cartaoResumo(w)
    expect(cartao.findAll('[data-frases] dd')).toHaveLength(3)
    expect(t(cartao.get('[data-bloqueio]').text())).toContain(MENSAGEM_COTA_ESGOTADA)
    expect(cartao.get('[data-link-config-ia]').attributes('href')).toBe('/configuracoes/ia')
    expect(t(cartao.get('[data-link-config-ia]').text())).toBe('Configurações › IA')
    expect(cartao.find('[data-gerar-ia]').exists()).toBe(false)
    w.unmount()

    setActivePinia(createPinia())
    entrar(DO_PAINEL)
    apiPainel({ 'GET /painel/resumo-ia': () => estado({ disponivel: false, motivo: 'cota_esgotada' }) })
    w = await abrir('/inicio', '/inicio', PainelView)
    cartao = cartaoResumo(w)
    expect(t(cartao.get('[data-bloqueio]').text())).toBe(MENSAGEM_COTA_ESGOTADA)
    expect(cartao.find('[data-link-config-ia]').exists()).toBe(false)
  })

  it('409 cota_esgotada no POST: a mensagem da API, o link do administrador e o assistente também para', async () => {
    entrar([...DO_PAINEL, 'configuracoes.gerenciar'], 'admin')
    const assistente = assistenteComCota()
    apiPainel({ 'POST /painel/resumo-ia': () => erroApi(409, 'cota_esgotada', 'O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º!') })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(cartao.get('[data-bloqueio]').text())).toContain('Ele renova no dia 1º!')
    expect(cartao.find('[data-link-config-ia]').exists()).toBe(true)
    expect(cartao.find('[data-gerar-ia]').exists()).toBe(false)
    expect(assistente.disponivel).toBe(false)
    expect(assistente.estado?.motivo).toBe('cota_esgotada')
  })

  it('a geração que gasta a última análise já tira o botão', async () => {
    entrar(DO_PAINEL)
    apiPainel({ 'POST /painel/resumo-ia': () => ({ item: item(RESUMO), cota: { usadas: 500, limite: 500, restantes: 0, mes: '2026-10' }, pode_gerar_em: null }) })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(cartao.findAll('[data-frases] dd')).toHaveLength(3)
    expect(t(cartao.get('[data-restam]').text())).toBe('Restam 0 de 500 análises este mês')
    expect(cartao.find('[data-gerar-ia]').exists()).toBe(false)
    expect(t(cartao.get('[data-bloqueio]').text())).toBe(MENSAGEM_COTA_ESGOTADA)
  })

  it('503: aviso com a mensagem e "Tentar de novo", que gera de novo e leva o foco para o botão de gerar', async () => {
    entrar(DO_PAINEL)
    let falhar = true
    const { chamadas } = apiPainel({
      'POST /painel/resumo-ia': () => (falhar ? erroApi(503, 'ia_indisponivel', 'A IA não respondeu agora. Tente de novo em instantes.') : { item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: null }),
    })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    const aviso = cartao.get('[data-erro-geracao]')
    expect(aviso.attributes('role')).toBe('alert')
    expect(aviso.text()).toContain('A IA não respondeu agora. Tente de novo em instantes.')
    // O aviso já é uma região viva (role="alert"): o anúncio à parte não repete o erro.
    expect(t(cartao.get('[data-anuncio]').text())).toBe('')
    falhar = false
    const tentar = cartao.get<HTMLButtonElement>('[data-tentar-de-novo]')
    tentar.element.focus()
    await tentar.trigger('click')
    // O aviso (com o "Tentar de novo") some na hora: o foco já está no botão de gerar, ocupado, e não no <body>.
    expect(cartao.find('[data-erro-geracao]').exists()).toBe(false)
    expect(document.activeElement).toBe(botaoGerar(cartao).element)
    expect(botaoGerar(cartao).attributes('aria-busy')).toBe('true')
    await flushPromises()
    expect(pedidos(chamadas, 'POST', '/painel/resumo-ia')).toHaveLength(2)
    expect(cartao.findAll('[data-frases] dd')).toHaveLength(3)
    expect(document.activeElement).toBe(botaoGerar(cartao).element)
  })

  it('"Tentar de novo" do 503 e a resposta tira o botão (cota esgotada): o foco vai para o título do cartão', async () => {
    entrar(DO_PAINEL)
    let resposta = () => erroApi(503, 'ia_indisponivel', 'A IA não respondeu agora. Tente de novo em instantes.')
    apiPainel({ 'POST /painel/resumo-ia': () => resposta() })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    resposta = () => erroApi(409, 'cota_esgotada', 'O limite mensal de análises de IA do seu plano foi atingido.')
    const tentar = cartao.get<HTMLButtonElement>('[data-tentar-de-novo]')
    tentar.element.focus()
    await tentar.trigger('click')
    await flushPromises()
    expect(cartao.find('[data-gerar-ia]').exists()).toBe(false)
    expect(cartao.get('[data-bloqueio]').text()).toContain('O limite mensal de análises de IA do seu plano foi atingido.')
    expect(document.activeElement).toBe(cartao.get('#t-resumo-ia').element)
    expect(cartao.get('#t-resumo-ia').attributes('tabindex')).toBe('-1')
  })

  it('409 sem_dados e 429: aviso com a mensagem da API, sem "Tentar de novo"; o 429 mostra a contagem e o aviso sai quando ela acaba', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    let resposta = () => erroApi(409, 'sem_dados', 'Não há respostas neste período para analisar.')
    apiPainel({ 'POST /painel/resumo-ia': () => resposta() })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(cartao.get('[data-erro-geracao]').text())).toBe('Não há respostas neste período para analisar.')
    expect(cartao.find('[data-tentar-de-novo]').exists()).toBe(false)
    expect(t(botaoGerar(cartao).text())).toBe('Gerar resumo')

    resposta = () => erroApi(429, 'aguarde', 'Aguarde 12 s para gerar de novo.')
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(cartao.get('[data-erro-geracao]').text())).toBe('Aguarde 12 s para gerar de novo.')
    expect(cartao.find('[data-tentar-de-novo]').exists()).toBe(false)
    expect(t(botaoGerar(cartao).text())).toBe('Gerar resumo em 12 s')
    expect(t(cartao.get('[data-anuncio]').text())).toBe('')

    // A contagem acabou: o botão volta e o "Aguarde 12 s" (que já não vale) sai junto.
    vi.advanceTimersByTime(11_000)
    await nextTick()
    expect(cartao.find('[data-erro-geracao]').exists()).toBe(true)
    vi.advanceTimersByTime(1_000)
    await nextTick()
    expect(cartao.find('[data-erro-geracao]').exists()).toBe(false)
    expect(t(botaoGerar(cartao).text())).toBe('Gerar resumo')
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBeUndefined()
    expect(t(cartao.get('[data-anuncio]').text())).toBe('Já dá para gerar de novo.')
  })

  it('429 "em andamento" (sem segundos): o aviso fica até a próxima geração', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    let resposta: () => unknown = () => erroApi(429, 'aguarde', 'Já tem um resumo sendo gerado. Aguarde alguns segundos.')
    apiPainel({ 'POST /painel/resumo-ia': () => resposta() })
    const w = await abrir('/inicio', '/inicio', PainelView)
    const cartao = cartaoResumo(w)
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(t(cartao.get('[data-erro-geracao]').text())).toBe('Já tem um resumo sendo gerado. Aguarde alguns segundos.')
    expect(t(botaoGerar(cartao).text())).toBe('Gerar resumo')
    vi.advanceTimersByTime(30_000)
    await nextTick()
    expect(cartao.find('[data-erro-geracao]').exists()).toBe(true)
    resposta = () => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: null })
    await botaoGerar(cartao).trigger('click')
    await flushPromises()
    expect(cartao.find('[data-erro-geracao]').exists()).toBe(false)
  })

  it('sair da tela para a contagem; uma geração que volta depois de sair não liga outra', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    const daqui = (ms: number) => new Date(Date.now() + ms).toISOString()
    apiFalsa({ 'GET /painel/resumo-ia': () => estado({ item: item(RESUMO), pode_gerar_em: daqui(20_000) }) })
    let w = await montarCartao(ref(F90))
    expect(t(botaoGerar(cartaoResumo(w)).text())).toBe('Gerar de novo em 20 s')
    expect(vi.getTimerCount()).toBe(1)
    w.unmount()
    expect(vi.getTimerCount()).toBe(0)

    const post = segurar(() => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: daqui(30_000) }))
    apiFalsa({ 'GET /painel/resumo-ia': () => estado(), 'POST /painel/resumo-ia': post.rota })
    w = await montarCartao(ref(F90))
    await botaoGerar(cartaoResumo(w)).trigger('click')
    await flushPromises()
    w.unmount()
    post.liberar()
    await flushPromises()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('some sem IA na plataforma (e se a leitura falhar de primeira)', async () => {
    entrar(DO_PAINEL)
    apiPainel({ 'GET /painel/resumo-ia': () => estado({ disponivel: false, motivo: 'ia_indisponivel', cota: null, item: item(RESUMO) }) })
    let w = await abrir('/inicio', '/inicio', PainelView)
    expect(w.find('[data-resumo-ia]').exists()).toBe(false)
    expect(w.text()).toContain('Pode melhorar') // o resto do painel continua
    w.unmount()

    setActivePinia(createPinia())
    entrar(DO_PAINEL)
    apiPainel({ 'GET /painel/resumo-ia': () => erroApi(500, 'erro_servidor', 'Erro.') })
    w = await abrir('/inicio', '/inicio', PainelView)
    expect(w.find('[data-resumo-ia]').exists()).toBe(false)
  })

  it('trocar o filtro lê o resumo de novo com os filtros novos (e mostra o salvo para eles)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    entrar(DO_PAINEL)
    const { chamadas } = apiPainel({
      'GET /painel/resumo-ia': ({ url }) =>
        url.searchParams.get('de') === somarDias(HOJE, -6) ? estado({ item: item({ ...RESUMO, melhorar: 'Na última semana, a entrega piorou.' }) }) : estado(),
      'POST /painel/resumo-ia': () => erroApi(409, 'sem_dados', 'Não há respostas neste período para analisar.'),
    })
    const w = await abrir('/inicio', '/inicio', PainelView)
    // Um aviso do período anterior some com a troca.
    await botaoGerar(cartaoResumo(w)).trigger('click')
    await flushPromises()
    expect(cartaoResumo(w).find('[data-erro-geracao]').exists()).toBe(true)

    const label = w.findAll('label').find((l) => l.text() === 'Período')!
    await w.get(`[id="${label.attributes('for')}"]`).setValue('7')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    const lidos = pedidos(chamadas, 'GET', '/painel/resumo-ia')
    expect(lidos).toHaveLength(2)
    expect(consulta(lidos[1])).toEqual({ de: somarDias(HOJE, -6), ate: HOJE, so_ativos: 'true' })
    const cartao = cartaoResumo(w)
    expect(cartao.text()).toContain('Últimos 7 dias')
    expect(cartao.text()).toContain('Na última semana, a entrega piorou.')
    expect(cartao.find('[data-erro-geracao]').exists()).toBe(false)
  })
})

describe('Resumo da IA: corridas, anúncio e foco (trocando os filtros do cartão)', () => {
  const RESUMO_7 = { ...RESUMO, melhorar: 'Na última semana, a entrega piorou.' }

  it('uma leitura que ainda está indo quando a geração termina não troca o item novo pelo de antes', async () => {
    entrar(DO_PAINEL)
    const filtros = ref(F90)
    const post = segurar(() => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: null }))
    let leituraPresa: ReturnType<typeof segurar<EstadoGeracaoIa<unknown>>> | null = null
    const { chamadas } = apiFalsa({
      // A leitura presa traz o que estava salvo antes da geração (nada).
      'GET /painel/resumo-ia': (c) => (leituraPresa && doPeriodo(c, F90) ? leituraPresa.rota() : estado()),
      'POST /painel/resumo-ia': post.rota,
    })
    const w = await montarCartao(filtros)
    await botaoGerar(cartaoResumo(w)).trigger('click')
    await flushPromises()
    // Enquanto gera, a pessoa vai para 7 dias e volta para 90: a leitura dos 90 dias fica presa.
    filtros.value = F7
    await flushPromises()
    leituraPresa = segurar(() => estado())
    filtros.value = F90
    await flushPromises()
    expect(pedidos(chamadas, 'GET', '/painel/resumo-ia')).toHaveLength(3)
    expect(cartaoResumo(w).find('[data-gerando]').exists()).toBe(true)

    post.liberar()
    await flushPromises()
    expect(cartaoResumo(w).findAll('[data-frases] dd').map((d) => t(d.text()))).toEqual([RESUMO.melhorar, RESUMO.funciona, RESUMO.proximo_passo])
    // A leitura antiga chega depois: é descartada (o item novo fica).
    leituraPresa.liberar()
    await flushPromises()
    const cartao = cartaoResumo(w)
    expect(cartao.findAll('[data-frases] dd')).toHaveLength(3)
    expect(cartao.find('[data-vazio]').exists()).toBe(false)
    expect(t(cartao.get('[data-restam]').text())).toBe('Restam 487 de 500 análises este mês')
    expect(t(botaoGerar(cartao).text())).toBe('Gerar de novo')
  })

  it('trocar o filtro enquanto gera: "Lendo os números…" não aparece nos filtros novos; ao terminar, avisa que ficou pronto para os anteriores', async () => {
    entrar(DO_PAINEL)
    const filtros = ref(F90)
    const post = segurar(() => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: null }))
    const { chamadas } = apiFalsa({
      'GET /painel/resumo-ia': (c) => (doPeriodo(c, F7) ? estado({ item: item(RESUMO_7) }) : estado()),
      'POST /painel/resumo-ia': (c) => (doPeriodo(c, F90) ? post.rota() : { item: item(RESUMO_7), cota: COTA_DEPOIS, pode_gerar_em: null }),
    })
    const w = await montarCartao(filtros)
    await botaoGerar(cartaoResumo(w)).trigger('click')
    await flushPromises()
    expect(cartaoResumo(w).find('[data-gerando]').exists()).toBe(true)

    filtros.value = F7
    await flushPromises()
    let cartao = cartaoResumo(w)
    expect(cartao.find('[data-gerando]').exists()).toBe(false)
    expect(cartao.findAll('[data-frases] dd').map((d) => t(d.text()))[0]).toBe(RESUMO_7.melhorar)
    expect(cartao.find('[data-gerado]').exists()).toBe(true)
    // Outra geração está indo (a API responderia 429): o botão não gera, mas não aparece ocupado nos filtros novos.
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBe('true')
    expect(botaoGerar(cartao).attributes('aria-busy')).toBeUndefined()
    await botaoGerar(cartao).trigger('click')
    expect(pedidos(chamadas, 'POST', '/painel/resumo-ia')).toHaveLength(1)

    post.liberar()
    await flushPromises()
    cartao = cartaoResumo(w)
    expect(t(cartao.get('[data-pronto-anterior]').text())).toBe('O resumo pedido ficou pronto para os filtros anteriores. Volte a eles para ver.')
    expect(cartao.get('[data-pronto-anterior]').attributes('role')).toBe('status')
    expect(cartao.findAll('[data-frases] dd').map((d) => t(d.text()))[0]).toBe(RESUMO_7.melhorar) // a tela continua com os 7 dias
    expect(cartao.find('[data-restam]').exists()).toBe(false)
    expect(botaoGerar(cartao).attributes('aria-disabled')).toBeUndefined()

    // A próxima geração tira o aviso.
    await botaoGerar(cartao).trigger('click')
    expect(cartaoResumo(w).find('[data-pronto-anterior]').exists()).toBe(false)
    await flushPromises()
    expect(pedidos(chamadas, 'POST', '/painel/resumo-ia')).toHaveLength(2)
  })

  it('o aviso "ficou pronto para os filtros anteriores" sai na troca de filtro seguinte (e o parecer tem o seu texto)', async () => {
    expect(TEXTOS_PARECER.prontoAnterior).toBe('O parecer pedido ficou pronto para os filtros anteriores. Volte a eles para ver.')
    entrar(DO_PAINEL)
    const filtros = ref(F90)
    const post = segurar(() => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: null }))
    apiFalsa({
      'GET /painel/resumo-ia': (c) => (doPeriodo(c, F90) ? estado({ item: item(RESUMO) }) : estado()),
      'POST /painel/resumo-ia': post.rota,
    })
    const w = await montarCartao(filtros)
    await botaoGerar(cartaoResumo(w)).trigger('click')
    await flushPromises()
    filtros.value = F7
    await flushPromises()
    post.liberar()
    await flushPromises()
    expect(cartaoResumo(w).find('[data-pronto-anterior]').exists()).toBe(true)
    // Volta para os 90 dias: o aviso sai e o resumo salvo para eles aparece.
    filtros.value = F90
    await flushPromises()
    expect(cartaoResumo(w).find('[data-pronto-anterior]').exists()).toBe(false)
    expect(cartaoResumo(w).findAll('[data-frases] dd')).toHaveLength(3)
  })

  it('o anúncio para o leitor de tela (texto gerado) é limpo quando os filtros mudam', async () => {
    entrar(DO_PAINEL)
    const filtros = ref(F90)
    apiFalsa({ 'GET /painel/resumo-ia': () => estado(), 'POST /painel/resumo-ia': () => ({ item: item(RESUMO), cota: COTA_DEPOIS, pode_gerar_em: null }) })
    const w = await montarCartao(filtros)
    await botaoGerar(cartaoResumo(w)).trigger('click')
    await flushPromises()
    expect(t(cartaoResumo(w).get('[data-anuncio]').text())).toMatch(/^Resumo gerado\. Precisa melhorar:/)
    filtros.value = F7
    await nextTick()
    expect(t(cartaoResumo(w).get('[data-anuncio]').text())).toBe('')
  })

  it('relógio atrasado: ler de novo a mesma espera (outro filtro, mesma conta) não recomeça a contagem', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(DO_PAINEL)
    // O servidor está 1 min à frente e a espera é da conta: o GET de qualquer filtro manda o mesmo pode_gerar_em.
    const podeGerarEm = new Date(Date.now() + 90_000).toISOString()
    apiFalsa({ 'GET /painel/resumo-ia': () => estado({ item: item(RESUMO), pode_gerar_em: podeGerarEm }) })
    const filtros = ref(F90)
    const w = await montarCartao(filtros)
    expect(t(botaoGerar(cartaoResumo(w)).text())).toBe('Gerar de novo em 30 s')
    vi.advanceTimersByTime(10_000)
    filtros.value = F7
    await flushPromises()
    expect(t(botaoGerar(cartaoResumo(w)).text())).toBe('Gerar de novo em 20 s')
    vi.advanceTimersByTime(20_000)
    await nextTick()
    expect(t(botaoGerar(cartaoResumo(w)).text())).toBe('Gerar de novo')
  })

  it('"Tentar de novo" da leitura que falhou: deu certo, o aviso some e o foco vai para o botão de gerar', async () => {
    entrar(DO_PAINEL)
    const filtros = ref(F90)
    let falhar = false
    apiFalsa({ 'GET /painel/resumo-ia': () => (falhar ? erroApi(500, 'erro_servidor', 'O servidor não respondeu.') : estado()) })
    const w = await montarCartao(filtros)
    falhar = true
    filtros.value = F7
    await flushPromises()
    const aviso = cartaoResumo(w).get('[data-erro-leitura]')
    expect(aviso.text()).toContain('O servidor não respondeu.')
    expect(cartaoResumo(w).find('[data-gerar-ia]').exists()).toBe(false)

    // Falhou de novo: o aviso fica e o foco continua no "Tentar de novo" (aria-disabled enquanto lê, não disabled).
    const tentar = () => cartaoResumo(w).get<HTMLButtonElement>('[data-tentar-ler]')
    tentar().element.focus()
    await tentar().trigger('click')
    expect(tentar().attributes('aria-disabled')).toBe('true')
    expect(tentar().attributes('disabled')).toBeUndefined()
    await flushPromises()
    expect(document.activeElement).toBe(tentar().element)

    falhar = false
    await tentar().trigger('click')
    await flushPromises()
    expect(cartaoResumo(w).find('[data-erro-leitura]').exists()).toBe(false)
    expect(document.activeElement).toBe(botaoGerar(cartaoResumo(w)).element)
  })
})

describe('Relatórios: "Parecer da IA"', () => {
  const PARECER ={ resumo: 'O NPS caiu 6 pontos com reclamações de entrega. A receita em risco é de R$ 262 mil.', recomendacoes: ['Ligue para a Pequi Marista.', 'Reveja a transportadora.'] }

  function apiRelatorios(rotas: Parameters<typeof apiFalsa>[0] = {}) {
    return apiFalsa({ 'GET /relatorios/parecer-ia': () => estado({ item: item(PARECER) }), ...rotas })
  }
  /** O painel lateral vai para o <body> (Teleport de verdade, como no navegador). */
  const dialogo = (_w?: VueWrapper) => new DOMWrapper(document.querySelector('[role="dialog"]')!)

  it('o botão nas ações do cabeçalho abre o painel lateral com o parecer dos filtros comuns: "Resumo" e "Recomendações da semana"', async () => {
    entrar(['relatorios.ver'])
    const { chamadas } = apiRelatorios()
    const w = await abrir('/relatorios/temas?periodo=30&grupo_id=2&so_ativos=false', '/relatorios/:aba', RelatoriosView, true)
    // Lê ao abrir a tela, com os filtros comuns (para saber se o botão aparece).
    const lidos = pedidos(chamadas, 'GET', '/relatorios/parecer-ia')
    expect(lidos).toHaveLength(1)
    expect(consulta(lidos[0])).toEqual({ de: somarDias(HOJE, -29), ate: HOJE, grupo_id: '2', so_ativos: 'false' })
    const botao = w.get('header [data-abrir-parecer]')
    expect(t(botao.text())).toBe('Parecer da IA')
    expect(document.querySelector('[role="dialog"]')).toBeNull()

    await botao.trigger('click')
    await flushPromises()
    const d = dialogo(w)
    expect(t(d.get('h2').text())).toBe('Parecer da IA')
    expect(d.text()).toContain('Últimos 30 dias · Grupo escolhido · Empresas ativas e inativas')
    expect(d.findAll('h3').map((x) => t(x.text()))).toEqual(['Resumo', 'Recomendações da semana'])
    expect(t(d.get('[data-resumo]').text())).toBe(PARECER.resumo)
    expect(d.get('[data-recomendacoes]').element.tagName).toBe('OL')
    expect(d.findAll('[data-recomendacoes] li').map((li) => t(li.text()))).toEqual(PARECER.recomendacoes)
    expect(t(d.get('[data-gerado]').text())).toBe(`Gerado em ${formatarDataHora(GERADO_EM)} por Ana Paula · Equilibrado`)
    expect(t(botaoGerar(d).text())).toBe('Gerar de novo')
    // Abrir lê de novo (alguém pode ter gerado nesse meio-tempo).
    expect(pedidos(chamadas, 'GET', '/relatorios/parecer-ia')).toHaveLength(2)
  })

  it('gerar no painel: manda os filtros comuns, mostra o parecer novo, o "Restam" e a contagem', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    entrar(['relatorios.ver'])
    const novo = { resumo: 'Parecer novo.', recomendacoes: ['Uma só recomendação.'] }
    const { chamadas } = apiRelatorios({
      'GET /relatorios/parecer-ia': () => estado(),
      'POST /relatorios/parecer-ia': () => ({ item: item(novo), cota: COTA_DEPOIS, pode_gerar_em: new Date(Date.now() + 30_000).toISOString() }),
    })
    const w = await abrir('/relatorios/temas?grupo_id=5', '/relatorios/:aba', RelatoriosView, true)
    await w.get('[data-abrir-parecer]').trigger('click')
    await flushPromises()
    const d = dialogo(w)
    expect(t(d.get('[data-vazio]').text())).toBe(TEXTOS_PARECER.vazio)
    expect(t(botaoGerar(d).text())).toBe('Gerar parecer')
    await botaoGerar(d).trigger('click')
    await flushPromises()
    // O painel continua o mesmo (não é montado de novo: o foco fica onde estava).
    expect(d.element.isConnected).toBe(true)
    expect(pedidos(chamadas, 'POST', '/relatorios/parecer-ia').map((c) => c.corpo)).toEqual([{ de: somarDias(HOJE, -89), ate: HOJE, grupo_id: 5, so_ativos: true }])
    expect(t(d.get('[data-resumo]').text())).toBe('Parecer novo.')
    expect(d.findAll('[data-recomendacoes] li')).toHaveLength(1)
    expect(t(d.get('[data-restam]').text())).toBe('Restam 487 de 500 análises este mês')
    expect(t(botaoGerar(d).text())).toBe('Gerar de novo em 30 s')
    expect(t(d.get('[data-anuncio]').text())).toBe('Parecer gerado. Resumo: Parecer novo. Recomendações da semana: 1. Uma só recomendação.')
  })

  it('conta pausada: o texto do parecer, sem botão; sem IA na plataforma o botão do cabeçalho não aparece', async () => {
    entrar(['relatorios.ver'])
    apiRelatorios({ 'GET /relatorios/parecer-ia': () => estado({ disponivel: false, motivo: 'conta_pausada' }) })
    let w = await abrir('/relatorios/temas', '/relatorios/:aba', RelatoriosView, true)
    await w.get('[data-abrir-parecer]').trigger('click')
    await flushPromises()
    expect(t(dialogo(w).get('[data-bloqueio]').text())).toBe('O parecer volta quando a assinatura estiver em dia.')
    expect(dialogo(w).find('[data-gerar-ia]').exists()).toBe(false)
    w.unmount()

    setActivePinia(createPinia())
    entrar(['relatorios.ver'])
    apiRelatorios({ 'GET /relatorios/parecer-ia': () => estado({ disponivel: false, motivo: 'ia_indisponivel', cota: null }) })
    w = await abrir('/relatorios/temas', '/relatorios/:aba', RelatoriosView, true)
    expect(w.find('[data-abrir-parecer]').exists()).toBe(false)
  })

  /** Escolhe uma opção num campo de seleção pelo rótulo. */
  async function escolher(w: VueWrapper, rotulo: string, valor: string) {
    const label = w.findAll('label').find((l) => t(l.text()) === rotulo)!
    await w.get(`[id="${label.attributes('for')}"]`).setValue(valor)
    await flushPromises()
  }

  it('a primeira leitura falhou (502 durante uma atualização): com o painel fechado, a troca de filtro lê de novo e o botão aparece', async () => {
    entrar(['relatorios.ver'])
    let falhar = true
    const { chamadas } = apiRelatorios({ 'GET /relatorios/parecer-ia': () => (falhar ? erroApi(502, 'erro_servidor', 'O servidor não respondeu.') : estado({ item: item(PARECER) })) })
    const w = await abrir('/relatorios/temas', '/relatorios/:aba', RelatoriosView, true)
    expect(pedidos(chamadas, 'GET', '/relatorios/parecer-ia')).toHaveLength(1)
    expect(w.find('[data-abrir-parecer]').exists()).toBe(false)

    falhar = false
    await escolher(w, 'Período', '30')
    expect(pedidos(chamadas, 'GET', '/relatorios/parecer-ia')).toHaveLength(2)
    expect(w.find('header [data-abrir-parecer]').exists()).toBe(true)
    // Já leu uma vez: com o painel fechado, outra troca de filtro não lê (só ao abrir).
    await escolher(w, 'Período', '7')
    expect(pedidos(chamadas, 'GET', '/relatorios/parecer-ia')).toHaveLength(2)
    await w.get('[data-abrir-parecer]').trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, 'GET', '/relatorios/parecer-ia')).toHaveLength(3)
    expect(consulta(pedidos(chamadas, 'GET', '/relatorios/parecer-ia')[2])).toEqual({ de: somarDias(HOJE, -6), ate: HOJE, so_ativos: 'true' })
  })

  it('datas escolhidas incompletas ao abrir a tela: não lê; quando ficam válidas, lê e o botão aparece', async () => {
    entrar(['relatorios.ver'])
    const de = somarDias(HOJE, -20)
    const { chamadas } = apiRelatorios()
    const w = await abrir(`/relatorios/temas?de=${de}`, '/relatorios/:aba', RelatoriosView, true)
    expect(pedidos(chamadas, 'GET', '/relatorios/parecer-ia')).toHaveLength(0)
    expect(w.find('[data-abrir-parecer]').exists()).toBe(false)
    const ate = w.findAll('label').find((l) => t(l.text()) === 'Até')!
    await w.get(`[id="${ate.attributes('for')}"]`).setValue(HOJE)
    await flushPromises()
    expect(pedidos(chamadas, 'GET', '/relatorios/parecer-ia').map(consulta)).toEqual([{ de, ate: HOJE, so_ativos: 'true' }])
    expect(w.find('[data-abrir-parecer]').exists()).toBe(true)
  })

  it('aba "Histórico de uma empresa": sem o botão do parecer (ela não mostra os filtros de grupo e de só ativas); nas outras, ele volta', async () => {
    entrar(['relatorios.ver'])
    apiRelatorios()
    const w = await abrir('/relatorios/historico?grupo_id=2&so_ativos=false', '/relatorios/:aba', RelatoriosView, true)
    expect(w.findAll('label').map((l) => t(l.text()))).not.toContain('Grupo de empresas')
    expect(w.find('[data-abrir-parecer]').exists()).toBe(false)
    await w.findAll('[role="tab"]').find((a) => t(a.text()) === 'Temas')!.trigger('click')
    await flushPromises()
    expect(w.find('header [data-abrir-parecer]').exists()).toBe(true)
  })
})
