// Etapa 5d (docs/api-etapa-5d.md §6.3 e §6.4) com a API simulada: os passos sugeridos pela IA no painel da ação
// (pendente relê e para, pronta copia, falhou, limite, sem situação) e "Como a IA escreve" em Configurações › IA (salva
// modelo, estilo e o interruptor só com o campo que mudou, desfaz no erro). Não há modo só leitura para testar: a rota
// /configuracoes/ia e o GET /conta/ia já pedem configuracoes.gerenciar.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { Acao, ConfigIa, Perfil } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import PlanosAcaoView from '@/modulos/acoes/PlanosAcaoView.vue'
import IaView from '@/modulos/configuracoes/IaView.vue'
import { TEXTOS_PASSOS } from '@/modulos/ia/logica'
import { apiFalsa, erro422, type Chamada } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

function entrar(permissoes: string[], perfil: Perfil = 'gestor') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

async function abrir(caminho: string, rota: string, componente: object): Promise<VueWrapper> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: rota, name: rota.startsWith('/planos-de-acao') ? 'planos-de-acao' : undefined, component: componente },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  // Teleport de verdade: o painel lateral vai para o <body>, como no navegador.
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const ultimoAviso = () => avisos.at(-1)?.mensagem ?? ''
const doBody = (seletor: string) => new DOMWrapper(document.querySelector(seletor))

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
  document.body.innerHTML = ''
})

// ── Plano de ação: passos sugeridos pela IA (§6.3) ──────────────────────────

describe('Plano de ação: "Passos sugeridos pela IA"', () => {
  const PASSOS = ['Ligue para o cliente hoje e peça desculpas pelo atraso.', 'Confirme com a transportadora a nova data.', 'Avise o cliente quando a entrega sair.']

  function acao(id: number, extra: Partial<Acao> = {}): Acao {
    return {
      id,
      titulo: `Ação ${id}`,
      descricao: 'Entrega atrasada.',
      resolucao: null,
      situacao: 'a_fazer',
      prioridade: 'alta',
      prazo: null,
      prazo_selo: null,
      empresa: { id: 1, nome: 'Mercado Bom Preço' },
      contato: { id: 9, nome: 'Bruno' },
      responsavel: null,
      resposta: { id: 50, nota: 3, tipo_nota: 'nps', grupo: 'detrator', comentario: 'A entrega atrasou de novo.', data: '2026-09-30T10:00:00-03:00' },
      origem: 'automatica',
      grupo: 'detrator',
      tipo_nota: 'nps',
      nota: 3,
      criada_em: '2026-09-30T10:00:00-03:00',
      atualizada_em: '2026-09-30T10:00:00-03:00',
      iniciada_em: null,
      concluida_em: null,
      criado_por: null,
      concluida_por: null,
      ...extra,
    }
  }

  let acoes: Acao[]
  /** O que GET /acoes/:id devolve (por padrão, a ação como está na lista). */
  let ler: (a: Acao, vez: number) => Acao

  function api() {
    const leituras: Record<string, number> = {}
    const r = apiFalsa({
      'GET /acoes/quadro': () => ({
        colunas: { a_fazer: acoes, em_andamento: [], concluida: [] },
        totais: { a_fazer: acoes.length, em_andamento: 0, concluida: 0, vencidas: 0 },
      }),
      'GET /cadastros/grupos': () => [],
      'GET /acoes/:id': ({ caminho }) => {
        const a = acoes.find((x) => `/acoes/${x.id}` === caminho)!
        leituras[caminho] = (leituras[caminho] ?? 0) + 1
        return ler(a, leituras[caminho]!)
      },
    })
    return { ...r, leituras: (id: number) => r.chamadas.filter((c: Chamada) => c.metodo === 'GET' && c.caminho === `/acoes/${id}`).length }
  }

  /** Abre o painel pelo cartão do quadro (a ação vem do quadro, sem ler de novo). */
  async function abrirAcao(w: VueWrapper, id: number) {
    const cartao = w.findAll('article').find((a) => a.text().includes(`Ação ${id}`))!
    await cartao.get('h3 button').trigger('click')
    await flushPromises()
  }
  const bloco = () => doBody('[role="dialog"] [data-passos-ia]')

  beforeEach(() => {
    entrar(['acoes.ver', 'acoes.tratar'])
    ler = (a) => a
  })

  it('pendente: "A IA está sugerindo os passos…", relê a cada 5 s e para quando ficam prontos; a lista numerada copia', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    acoes = [acao(1, { ia_passos_situacao: 'pendente', ia_passos: null })]
    ler = (a, vez) => (vez >= 2 ? { ...a, ia_passos_situacao: 'pronta', ia_passos: PASSOS } : a)
    const { leituras } = api()
    const w = await abrir('/planos-de-acao', '/planos-de-acao/:id?', PlanosAcaoView)
    await abrirAcao(w, 1)
    expect(bloco().attributes('data-situacao')).toBe('pendente')
    expect(t(bloco().get('h3').text())).toBe('Passos sugeridos pela IA')
    expect(bloco().text()).toContain(TEXTOS_PASSOS.pendente)
    expect(bloco().find('[aria-live="polite"]').exists()).toBe(true)
    expect(leituras(1)).toBe(0)

    await vi.advanceTimersByTimeAsync(4_999)
    expect(leituras(1)).toBe(0)
    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
    expect(leituras(1)).toBe(1)
    expect(bloco().attributes('data-situacao')).toBe('pendente')

    await vi.advanceTimersByTimeAsync(5_000)
    await flushPromises()
    expect(leituras(1)).toBe(2)
    expect(bloco().attributes('data-situacao')).toBe('pronta')
    expect(bloco().get('[data-lista-passos]').element.tagName).toBe('OL')
    expect(bloco().findAll('[data-lista-passos] li').map((li) => t(li.text()))).toEqual(PASSOS)
    expect(bloco().text()).toContain('Sugestão da IA. Confira antes de seguir.')

    // Pronta: não relê mais.
    await vi.advanceTimersByTimeAsync(30_000)
    expect(leituras(1)).toBe(2)

    // Copiar leva os passos numerados.
    const escrever = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: escrever }, configurable: true })
    const copiar = bloco().findAll('button').find((b) => t(b.text()) === 'Copiar passos')!
    await copiar.trigger('click')
    await flushPromises()
    expect(escrever).toHaveBeenCalledWith(`1. ${PASSOS[0]}\n2. ${PASSOS[1]}\n3. ${PASSOS[2]}`)

    // O quadro guardou os passos: fechar e abrir de novo mostra a lista sem reler.
    await doBody('[role="dialog"] button[aria-label="Fechar"]').trigger('click')
    await flushPromises()
    await abrirAcao(w, 1)
    expect(bloco().attributes('data-situacao')).toBe('pronta')
    await vi.advanceTimersByTimeAsync(10_000)
    expect(leituras(1)).toBe(2)
  })

  it('continua pendente: relê 6 vezes, para e explica que os passos aparecem depois', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    acoes = [acao(1, { ia_passos_situacao: 'pendente', ia_passos: null })]
    const { leituras } = api()
    const w = await abrir('/planos-de-acao', '/planos-de-acao/:id?', PlanosAcaoView)
    await abrirAcao(w, 1)
    for (let i = 1; i <= 6; i++) {
      await vi.advanceTimersByTimeAsync(5_000)
      await flushPromises()
      expect(leituras(1)).toBe(i)
    }
    expect(bloco().get('[data-passos-demorando]').text()).toBe(TEXTOS_PASSOS.demorando)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(leituras(1)).toBe(6)
  })

  it('fechar o painel (ou sair da tela) para de reler', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    acoes = [acao(1, { ia_passos_situacao: 'pendente', ia_passos: null })]
    const { leituras } = api()
    const w = await abrir('/planos-de-acao', '/planos-de-acao/:id?', PlanosAcaoView)
    await abrirAcao(w, 1)
    await vi.advanceTimersByTimeAsync(5_000)
    await flushPromises()
    expect(leituras(1)).toBe(1)
    await doBody('[role="dialog"] button[aria-label="Fechar"]').trigger('click')
    await flushPromises()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    await vi.advanceTimersByTimeAsync(30_000)
    expect(leituras(1)).toBe(1)

    await abrirAcao(w, 1)
    await vi.advanceTimersByTimeAsync(5_000)
    await flushPromises()
    expect(leituras(1)).toBe(2)
    w.unmount()
    await vi.advanceTimersByTimeAsync(30_000)
    expect(leituras(1)).toBe(2)
  })

  it('falhou e limite: os textos; sem situação (sem comentário ou sem IA), nada aparece', async () => {
    acoes = [
      acao(1, { ia_passos_situacao: 'falhou', ia_passos: null }),
      acao(2, { ia_passos_situacao: 'limite', ia_passos: null }),
      acao(3, { ia_passos_situacao: null, ia_passos: null }),
      acao(4),
    ]
    const { leituras } = api()
    const w = await abrir('/planos-de-acao', '/planos-de-acao/:id?', PlanosAcaoView)
    await abrirAcao(w, 1)
    expect(t(bloco().get('[aria-live="polite"]').text())).toBe('A IA não conseguiu sugerir passos para esta ação.')
    expect(bloco().findAll('button').some((b) => t(b.text()) === 'Copiar passos')).toBe(false)
    await abrirAcao(w, 2)
    expect(t(bloco().get('[aria-live="polite"]').text())).toBe('O limite mensal de análises automáticas foi atingido.')
    await abrirAcao(w, 3)
    expect(document.querySelector('[role="dialog"]')).not.toBeNull()
    expect(bloco().exists()).toBe(false)
    await abrirAcao(w, 4)
    expect(bloco().exists()).toBe(false)
    expect(leituras(1) + leituras(2) + leituras(3) + leituras(4)).toBe(0)
  })

  it('pronta: aparece abaixo da descrição e antes da resposta que deu origem', async () => {
    acoes = [acao(1, { ia_passos_situacao: 'pronta', ia_passos: PASSOS.slice(0, 2) })]
    api()
    const w = await abrir('/planos-de-acao', '/planos-de-acao/:id?', PlanosAcaoView)
    await abrirAcao(w, 1)
    const painel = document.querySelector('[role="dialog"]')!
    const form = painel.querySelector('#painel-acao-form')!
    const passos = painel.querySelector('[data-passos-ia]')!
    const origem = painel.querySelector('[aria-labelledby="t-origem"]')!
    expect(form.compareDocumentPosition(passos) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(passos.compareDocumentPosition(origem) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(bloco().findAll('li')).toHaveLength(2)
  })
})

// ── Configurações › IA: "Como a IA escreve" (§6.4) ──────────────────────────

describe('Configurações › IA: "Como a IA escreve"', () => {
  const MODELOS = [
    { valor: 'rapido', rotulo: 'Rápido e econômico', descricao: 'Respostas curtas e rápidas.' },
    { valor: 'equilibrado', rotulo: 'Equilibrado', descricao: 'O padrão: bom para o dia a dia.' },
    { valor: 'detalhado', rotulo: 'Mais detalhado', descricao: 'Análises mais cuidadosas; pode demorar um pouco mais.' },
  ]
  const ESTILOS = [
    { valor: 'objetiva', rotulo: 'Objetiva', descricao: 'Frases curtas, só o essencial.' },
    { valor: 'equilibrada', rotulo: 'Equilibrada', descricao: 'Claro e cordial (padrão).' },
    { valor: 'criativa', rotulo: 'Criativa', descricao: 'Tom mais próximo e ideias práticas.' },
  ]
  const CONFIG: ConfigIa = {
    disponivel: true,
    provedor: 'OpenAI',
    analise_respostas: true,
    mes: '2026-10',
    analises: 40,
    limite: 500,
    pendentes: 0,
    falharam_no_mes: 0,
    cota: { usadas: 12, limite: 500, restantes: 488, mes: '2026-10' },
    modelo: 'equilibrado',
    estilo: 'equilibrada',
    passos_acoes: true,
    modelos: MODELOS,
    estilos: ESTILOS,
  }

  let atual: ConfigIa
  function api(put?: (corpo: Record<string, unknown>) => unknown) {
    atual = { ...CONFIG }
    return apiFalsa({
      'GET /conta/ia': () => atual,
      'PUT /conta/ia': ({ corpo }) => {
        if (put) return put(corpo as Record<string, unknown>)
        atual = { ...atual, ...(corpo as Partial<ConfigIa>) }
        return atual
      },
    })
  }
  const secao = (w: VueWrapper) => w.get('[data-como-ia-escreve]')
  const radio = (w: VueWrapper, valor: string) => secao(w).get<HTMLInputElement>(`input[type="radio"][value="${valor}"]`)
  const interruptor = (w: VueWrapper) => secao(w).get('[role="switch"]')
  const puts = (chamadas: Chamada[]) => chamadas.filter((c) => c.metodo === 'PUT').map((c) => c.corpo)

  it('modelo e estilo em cartões com rótulo e descrição (da API) e o interruptor dos passos', async () => {
    entrar(['configuracoes.gerenciar'], 'admin')
    api()
    const w = await abrir('/configuracoes/ia', '/configuracoes/ia', IaView)
    const s = secao(w)
    expect(t(s.get('h2').text())).toBe('Como a IA escreve')
    expect(s.findAll('legend').map((l) => t(l.text()))).toEqual(['Modelo', 'Estilo'])
    expect(s.findAll('[data-escolha="modelo"] label').map((l) => t(l.text()))).toEqual(MODELOS.map((m) => `${m.rotulo} ${m.descricao}`))
    expect(s.findAll('[data-escolha="estilo"] label').map((l) => t(l.text()))).toEqual(ESTILOS.map((m) => `${m.rotulo} ${m.descricao}`))
    expect(radio(w, 'equilibrado').element.checked).toBe(true)
    expect(radio(w, 'equilibrada').element.checked).toBe(true)
    expect(interruptor(w).attributes('aria-checked')).toBe('true')
    expect(s.text()).toContain('Sugerir passos nas ações')
    expect(s.text()).toContain('Ao criar uma ação a partir de uma resposta, a IA sugere até 3 passos. Não gasta a cota do plano.')
    // Logo abaixo da cota do plano.
    expect(w.get('[data-cota-plano]').element.nextElementSibling).toBe(s.element)
  })

  it('salva na hora, só o campo que mudou, e avisa', async () => {
    entrar(['configuracoes.gerenciar'], 'admin')
    const { chamadas } = api()
    const w = await abrir('/configuracoes/ia', '/configuracoes/ia', IaView)

    await radio(w, 'rapido').setValue(true)
    await flushPromises()
    expect(puts(chamadas)).toEqual([{ modelo: 'rapido' }])
    expect(ultimoAviso()).toBe('Modelo salvo: Rápido e econômico.')
    expect(radio(w, 'rapido').element.checked).toBe(true)
    expect(secao(w).get('[data-opcao="rapido"]').classes()).toContain('border-marca')

    await radio(w, 'criativa').setValue(true)
    await flushPromises()
    expect(puts(chamadas)).toEqual([{ modelo: 'rapido' }, { estilo: 'criativa' }])
    expect(ultimoAviso()).toBe('Estilo salvo: Criativa.')

    await interruptor(w).trigger('click')
    await flushPromises()
    expect(puts(chamadas)).toEqual([{ modelo: 'rapido' }, { estilo: 'criativa' }, { passos_acoes: false }])
    expect(ultimoAviso()).toMatch(/^Sugestão de passos desligada/)
    expect(interruptor(w).attributes('aria-checked')).toBe('false')
    // O resto da tela continua com o estado que a API devolveu.
    expect(radio(w, 'rapido').element.checked).toBe(true)
    expect(radio(w, 'criativa').element.checked).toBe(true)
  })

  it('duas trocas seguidas: vão uma de cada vez, na ordem', async () => {
    entrar(['configuracoes.gerenciar'], 'admin')
    const { chamadas } = api()
    const w = await abrir('/configuracoes/ia', '/configuracoes/ia', IaView)
    await radio(w, 'detalhado').setValue(true)
    await radio(w, 'objetiva').setValue(true)
    await flushPromises()
    await flushPromises()
    expect(puts(chamadas)).toEqual([{ modelo: 'detalhado' }, { estilo: 'objetiva' }])
    expect(radio(w, 'detalhado').element.checked).toBe(true)
    expect(radio(w, 'objetiva').element.checked).toBe(true)
  })

  it('se não salvar, volta como estava e mostra a mensagem', async () => {
    entrar(['configuracoes.gerenciar'], 'admin')
    const { chamadas } = api(() => erro422('Escolha um modelo da lista.'))
    const w = await abrir('/configuracoes/ia', '/configuracoes/ia', IaView)
    await radio(w, 'detalhado').setValue(true)
    await flushPromises()
    expect(puts(chamadas)).toEqual([{ modelo: 'detalhado' }])
    expect(ultimoAviso()).toBe('Escolha um modelo da lista.')
    expect(radio(w, 'equilibrado').element.checked).toBe(true)
    expect(radio(w, 'detalhado').element.checked).toBe(false)

    await interruptor(w).trigger('click')
    await flushPromises()
    expect(interruptor(w).attributes('aria-checked')).toBe('true')
  })

  it('API anterior à 5d (sem modelo, estilo e passos): a seção não aparece', async () => {
    entrar(['configuracoes.gerenciar'], 'admin')
    apiFalsa({ 'GET /conta/ia': () => ({ disponivel: true, provedor: 'OpenAI', analise_respostas: true, mes: '2026-10', analises: 0, limite: 500, pendentes: 0, falharam_no_mes: 0 }) })
    const w = await abrir('/configuracoes/ia', '/configuracoes/ia', IaView)
    expect(w.find('[data-como-ia-escreve]').exists()).toBe(false)
  })
})
