// Assistente (etapa 5b, docs/api-etapa-5b.md §6.2) com a API simulada: botão, abrir e fechar com foco, enviar,
// estados, erros, sugestões, atalhos, cota, histórico de 8, nova conversa, texto sem HTML, celular, sair. E os achados
// da revisão: o foco nunca cai no <body>, novas tentativas do estado, camadas, tela baixa e "Tentar de novo" só onde é seguro.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { EstadoAssistente, Perfil, RespostaAssistente } from '@/api/tipos'
import { useAssistenteStore } from '@/stores/assistente'
import { useSessaoStore } from '@/stores/sessao'
import AppLayout from '@/layouts/AppLayout.vue'
import AssistenteFlutuante from '@/modulos/assistente/AssistenteFlutuante.vue'
import { apiFalsa } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

const USUARIO = { id: 7, nome: 'Ana Paula', email: 'ana@sol.com.br', cargo: null, situacao: 'ativo' as const, email_confirmado: true, ultimo_acesso: null, superadmin: false }
const TODAS = ['painel.ver', 'contatos.ver', 'importacao.usar', 'respostas.ver', 'relatorios.ver', 'configuracoes.gerenciar', 'assinatura.gerenciar', 'equipe.gerenciar']

function entrar(permissoes: string[] = TODAS, perfil: Perfil = 'admin') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { ...USUARIO, perfil },
      conta: { id: 3, nome: 'Sol', plano: 'profissional', situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

const COTA = { usadas: 12, limite: 500, restantes: 488, mes: '2026-10' }
const SUGESTOES = ['Qual é o NPS dos últimos 30 dias?', 'Quais clientes têm o NPS mais baixo nos últimos 90 dias?', 'Como importo meus contatos?']
const ESTADO = (p: Partial<EstadoAssistente> = {}): EstadoAssistente => ({ disponivel: true, motivo: null, cota: COTA, sugestoes: SUGESTOES, ...p })
const RESPOSTA = (p: Partial<RespostaAssistente> = {}): RespostaAssistente => ({
  resposta: 'O NPS de 02/09 a 01/10/2026 é 42, com 120 respostas.\nNo período anterior foi 37.\n\nDestaques:\n- subiu 5 pontos\n- 30 respostas a mais',
  sugestoes: ['E nos últimos 90 dias?', 'Quais clientes puxaram o NPS para baixo?'],
  atalhos: [
    { chave: 'relatorios', rotulo: 'Relatórios', caminho: '/relatorios/empresas' },
    { chave: 'tela_nova', rotulo: 'Tela nova', caminho: '/nova' },
  ],
  cota: { usadas: 13, limite: 500, restantes: 487, mes: '2026-10' },
  ...p,
})
const erroApi = (status: number, codigo: string, mensagem: string) => new Response(JSON.stringify({ erro: { codigo, mensagem } }), { status })

/**
 * Tela larga ou estreita, alta ou baixa (celular deitado, zoom de 200%); com ou sem "reduzir movimento" (sem, a resposta
 * aparece aos poucos). Consultas com largura e altura mínimas só batem com as duas.
 */
function telas({ larga = true, alta = true, reduzir = true } = {}) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: q.includes('prefers-reduced-motion')
      ? reduzir
      : (q.includes('min-width') || q.includes('min-height')) && (!q.includes('min-width') || larga) && (!q.includes('min-height') || alta),
    media: q,
    addEventListener() {},
    removeEventListener() {},
  }))
}

let router: Router
/** A página (em `main#conteudo`, como no AppLayout) e o assistente. */
async function montar(caminho = '/inicio'): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div', 'página') } }],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h('div', [h('main', { id: 'conteudo', tabindex: '-1' }, [h(RouterView)]), h(AssistenteFlutuante)]) }), {
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

const botaoFlutuante = (w: VueWrapper) => w.find('button[data-botao-assistente]')
const painel = (w: VueWrapper) => w.find('[role="dialog"]')
const caixa = (w: VueWrapper) => w.get<HTMLTextAreaElement>('#assistente-pergunta')
const chamadas = (api: ReturnType<typeof apiFalsa>, metodo: string, caminho: string) => api.chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)
/** Uma tecla em quem tem o foco (como no navegador: o evento sobe a partir dele). */
function teclar(key: string, opcoes: KeyboardEventInit = {}): KeyboardEvent {
  const ev = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...opcoes })
  ;(document.activeElement ?? document.body).dispatchEvent(ev)
  return ev
}

async function abrir(w: VueWrapper) {
  await botaoFlutuante(w).trigger('click')
  await flushPromises()
}
async function perguntar(w: VueWrapper, texto: string) {
  await caixa(w).setValue(texto)
  await caixa(w).trigger('keydown', { key: 'Enter' })
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  sessionStorage.clear()
  telas()
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
  document.body.style.overflow = ''
})

describe('botão do assistente', () => {
  it('busca GET /assistente ao entrar e mostra o botão "ToqqiAI" no canto, com o símbolo da marca (some na impressão)', async () => {
    entrar()
    const api = apiFalsa({ 'GET /assistente': () => ESTADO() })
    const w = await montar()
    expect(chamadas(api, 'GET', '/assistente')).toHaveLength(1)
    const b = botaoFlutuante(w)
    expect(b.exists()).toBe(true)
    expect(b.attributes('aria-label')).toBe('ToqqiAI')
    expect(t(b.text())).toBe('ToqqiAI')
    // Ícone: o símbolo da marca em traço (currentColor, branco sobre o coral do botão), decorativo; nada de ícone genérico.
    const icone = b.get('svg')
    expect(icone.attributes('data-icone-toqqiai')).toBe('simbolo')
    expect(icone.attributes('aria-hidden')).toBe('true')
    expect(icone.attributes('stroke')).toBe('currentColor')
    expect(icone.classes()).toContain('size-5')
    expect(b.findAll('svg')).toHaveLength(1)
    expect(b.find('.lucide').exists()).toBe(false)
    expect(b.classes()).toEqual(expect.arrayContaining(['fixed', 'bottom-4', 'right-4']))
    expect(b.element.closest('.print\\:hidden')).not.toBeNull()
    expect(painel(w).exists()).toBe(false)
  })

  it('sem IA na plataforma (ou se a API falhar), o botão não aparece', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO({ disponivel: false, motivo: 'ia_indisponivel', cota: null, sugestoes: [] }) })
    expect(botaoFlutuante(await montar()).exists()).toBe(false)
    apiFalsa({ 'GET /assistente': () => erroApi(500, 'erro_servidor', 'Erro.') })
    setActivePinia(createPinia())
    entrar()
    expect(botaoFlutuante(await montar()).exists()).toBe(false)
  })

  it('se GET /assistente falha, tenta de novo depois de 5 s, 15 s, 60 s e depois a cada 5 min; o botão aparece quando dá certo', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    entrar()
    let falhas = 4
    const api = apiFalsa({ 'GET /assistente': () => (falhas-- > 0 ? erroApi(500, 'erro_servidor', 'Erro.') : ESTADO()) })
    const w = await montar()
    const gets = () => chamadas(api, 'GET', '/assistente').length
    const passar = async (ms: number) => {
      await vi.advanceTimersByTimeAsync(ms)
      await flushPromises()
    }
    expect(gets()).toBe(1)
    expect(botaoFlutuante(w).exists()).toBe(false)
    await passar(4_999)
    expect(gets()).toBe(1)
    await passar(1)
    expect(gets()).toBe(2)
    await passar(14_999)
    expect(gets()).toBe(2)
    await passar(1)
    expect(gets()).toBe(3)
    await passar(60_000)
    expect(gets()).toBe(4)
    await passar(299_999)
    expect(gets()).toBe(4)
    await passar(1)
    expect(gets()).toBe(5)
    expect(botaoFlutuante(w).exists()).toBe(true)
    // Com o estado, as tentativas param.
    await passar(3_600_000)
    expect(gets()).toBe(5)
  })

  it('sem o estado, voltar para a aba tenta na hora, um pedido por vez (abrir o painel também não repete o pedido)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const aba = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    entrar()
    let vez = 0
    let soltar!: (r: Response | EstadoAssistente) => void
    const api = apiFalsa({
      'GET /assistente': () => (++vez === 1 ? erroApi(503, 'erro_servidor', 'Fora do ar.') : new Promise<Response | EstadoAssistente>((r) => (soltar = r))),
    })
    const w = await montar()
    const gets = () => chamadas(api, 'GET', '/assistente').length
    expect(gets()).toBe(1)
    // A aba escondida não busca; ao voltar, busca na hora (sem esperar os 5 s).
    document.dispatchEvent(new Event('visibilitychange'))
    expect(gets()).toBe(1)
    aba.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(gets()).toBe(2)
    // Com um pedido no caminho, nem a aba nem o relógio fazem outro.
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()
    expect(gets()).toBe(2)
    soltar(ESTADO())
    await flushPromises()
    expect(botaoFlutuante(w).exists()).toBe(true)
    // Com o estado, abrir o painel busca de novo (cota e sugestões), uma vez só mesmo com dois cliques seguidos.
    useAssistenteStore().abrir()
    useAssistenteStore().abrir()
    expect(gets()).toBe(3)
    soltar(ESTADO())
    await flushPromises()
    // E voltar para a aba com o estado carregado não busca.
    document.dispatchEvent(new Event('visibilitychange'))
    expect(gets()).toBe(3)
  })

  it('as tentativas param ao sair da conta e quando o botão sai da tela', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    entrar()
    const api = apiFalsa({ 'GET /assistente': () => erroApi(500, 'erro_servidor', 'Erro.'), 'POST /auth/sair': () => undefined })
    const gets = () => chamadas(api, 'GET', '/assistente').length
    // Saiu da conta (o botão continua montado até a troca de tela): nem o relógio nem a aba buscam.
    await montar()
    expect(gets()).toBe(1)
    await useSessaoStore().sair()
    await vi.advanceTimersByTimeAsync(3_600_000)
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(gets()).toBe(1)
    // O botão saiu da tela (fora da área logada): também para.
    setActivePinia(createPinia())
    entrar()
    const w = await montar()
    expect(gets()).toBe(2)
    w.unmount()
    await vi.advanceTimersByTimeAsync(3_600_000)
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(gets()).toBe(2)
  })

  it('camadas: o botão e o painel preso ao canto em z-[25] (abaixo do cabeçalho e dos menus); em tela cheia, o painel em z-[45]', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO() })
    const w = await montar()
    const classesBotao = botaoFlutuante(w).classes()
    expect(classesBotao).toContain('z-[25]')
    expect(classesBotao.filter((c) => /(^|:)z-/.test(c))).toEqual(['z-[25]'])
    await abrir(w)
    const classesPainel = painel(w).classes()
    expect(classesPainel.filter((c) => /(^|:)z-/.test(c))).toEqual(['z-[45]', 'painel:z-[25]'])
    // O modo do painel depende da largura e da altura (variante `painel:`), não só da largura (`sm:`).
    expect(classesPainel).toEqual(expect.arrayContaining(['fixed', 'inset-0', 'painel:inset-auto', 'painel:bottom-6', 'painel:right-6', 'painel:w-[25rem]']))
    expect(classesPainel.filter((c) => c.startsWith('sm:'))).toEqual([])
  })

  it('no AppLayout, o fim do conteúdo ganha folga para o botão não cobrir a última ação', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO(), 'GET /eu': () => ({}) })
    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: AppLayout, children: [{ path: ':qualquer(.*)*', component: { render: () => h('div', 'página') } }] }],
    })
    await router.push('/inicio')
    await router.isReady()
    const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    expect(w.find('button[data-botao-assistente]').exists()).toBe(true)
    expect(w.get('main#conteudo').classes()).toEqual(expect.arrayContaining(['pb-24', 'sm:pb-28']))
  })
})

describe('abrir e fechar', () => {
  it('abre o painel (diálogo com título), busca o estado de novo, põe o foco na caixa; Esc fecha e o foco volta ao botão', async () => {
    entrar()
    const api = apiFalsa({ 'GET /assistente': () => ESTADO() })
    const w = await montar()
    const b = botaoFlutuante(w)
    ;(b.element as HTMLElement).focus()
    await abrir(w)
    const p = painel(w)
    expect(p.exists()).toBe(true)
    expect(p.attributes('aria-labelledby')).toBe('t-assistente')
    expect(t(w.get('#t-assistente').text())).toBe('ToqqiAI')
    // Ao lado do título, o selo da marca (decorativo: o nome já está escrito).
    const selo = p.get('header [data-icone-toqqiai]')
    expect(selo.attributes('data-icone-toqqiai')).toBe('selo')
    expect(selo.attributes('aria-hidden')).toBe('true')
    expect(selo.classes()).toContain('size-8')
    expect(p.get('header').find('.lucide-sparkles').exists()).toBe(false)
    expect(p.attributes('aria-modal')).toBeUndefined() // tela larga: não bloqueia a página
    expect(chamadas(api, 'GET', '/assistente')).toHaveLength(2)
    expect(document.activeElement).toBe(caixa(w).element)
    // Cabeçalho: cota com medidor fino.
    expect(t(w.get('[data-cota]').text())).toBe('Restam 488 de 500 análises este mês')
    const medidor = p.get('[role="meter"]')
    expect(medidor.attributes('aria-valuenow')).toBe('12')
    expect(medidor.attributes('aria-valuetext')).toBe('Restam 488 de 500 análises este mês')
    expect(medidor.classes()).toContain('h-1.5')
    // Rodapé discreto.
    expect(t(p.text())).toContain('Respostas geradas por IA com os dados da sua conta. Confira os números nos relatórios.')
    // Esc fecha; o foco volta ao botão.
    await p.trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(painel(w).exists()).toBe(false)
    expect(document.activeElement).toBe(botaoFlutuante(w).element)
  })

  it('o botão de fechar também fecha e devolve o foco', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO() })
    const w = await montar()
    await abrir(w)
    await w.get('button[aria-label="Fechar o ToqqiAI"]').trigger('click')
    await flushPromises()
    expect(painel(w).exists()).toBe(false)
    expect(document.activeElement).toBe(botaoFlutuante(w).element)
  })

  it('celular: painel em tela cheia e modal (trava a página); um atalho abre a tela e fecha o painel', async () => {
    telas({ larga: false })
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA() })
    const w = await montar()
    await abrir(w)
    expect(painel(w).attributes('aria-modal')).toBe('true')
    expect(painel(w).classes()).toEqual(expect.arrayContaining(['fixed', 'inset-0']))
    expect(document.body.style.overflow).toBe('hidden')
    await perguntar(w, 'Qual o NPS?')
    await w.get('[data-atalhos] a').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/relatorios/empresas')
    expect(painel(w).exists()).toBe(false)
    expect(document.body.style.overflow).toBe('')
  })

  it('tela baixa (celular deitado, zoom de 200%): tela cheia e modal mesmo com a largura de computador', async () => {
    telas({ larga: true, alta: false })
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO() })
    const w = await montar()
    await abrir(w)
    expect(painel(w).attributes('aria-modal')).toBe('true')
    expect(document.body.style.overflow).toBe('hidden')
    await w.get('button[aria-label="Fechar o ToqqiAI"]').trigger('click')
    await flushPromises()
    expect(document.body.style.overflow).toBe('')
  })

  it('celular: com o foco no próprio painel (caixa desligada), Tab e Shift+Tab continuam dentro dele', async () => {
    telas({ larga: false })
    // O jsdom não calcula layout (offsetParent é sempre null): aqui, todo elemento conta como visível.
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    entrar(['painel.ver'], 'consulta')
    apiFalsa({ 'GET /assistente': () => ESTADO({ disponivel: false, motivo: 'conta_pausada', sugestoes: [] }) })
    const w = await montar()
    await abrir(w)
    const p = painel(w).element as HTMLElement
    expect(document.activeElement).toBe(p)
    const fechar = w.get('button[aria-label="Fechar o ToqqiAI"]').element
    expect(teclar('Tab', { shiftKey: true }).defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(fechar)
    p.focus()
    expect(teclar('Tab').defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(fechar)
    // E o Esc fecha.
    p.focus()
    teclar('Escape')
    await flushPromises()
    expect(painel(w).exists()).toBe(false)
  })

  it('ao fechar, se o botão sumiu (a IA saiu da plataforma com o painel aberto), o foco vai para o conteúdo da página', async () => {
    entrar()
    let vez = 0
    apiFalsa({ 'GET /assistente': () => (++vez === 1 ? ESTADO() : ESTADO({ disponivel: false, motivo: 'ia_indisponivel', cota: null, sugestoes: [] })) })
    const w = await montar()
    ;(botaoFlutuante(w).element as HTMLElement).focus()
    await abrir(w)
    expect(botaoFlutuante(w).exists()).toBe(false)
    // A caixa desligou com o foco nela: o foco foi para o painel, e o Esc continua fechando.
    expect(caixa(w).element.disabled).toBe(true)
    expect(document.activeElement).toBe(painel(w).element)
    teclar('Escape')
    await flushPromises()
    expect(painel(w).exists()).toBe(false)
    expect(document.activeElement).toBe(w.get('main#conteudo').element)
  })

  it('tela larga: o atalho abre a tela e o painel continua aberto', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA() })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    await w.get('[data-atalhos] a').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/relatorios/empresas')
    expect(painel(w).exists()).toBe(true)
  })
})

describe('conversa', () => {
  it('vazio: uma frase do que ele responde e as sugestões da API; clicar envia', async () => {
    entrar()
    const api = apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA() })
    const w = await montar()
    await abrir(w)
    expect(t(w.get('[data-vazio]').text())).toContain('Pergunte sobre o NPS e o CSAT dos seus clientes')
    const sugestoes = w.findAll('[data-vazio] [data-sugestoes] button')
    expect(sugestoes.map((s) => t(s.text()))).toEqual(SUGESTOES)
    await sugestoes[1]!.trigger('click')
    await flushPromises()
    expect(chamadas(api, 'POST', '/assistente/perguntar')[0]!.corpo).toEqual({ pergunta: SUGESTOES[1], historico: [] })
  })

  it('enviar com Enter: a pergunta aparece na hora, "Consultando os dados…", depois a resposta como texto, atalhos e sugestões; a cota se atualiza', async () => {
    entrar()
    let soltar!: (r: RespostaAssistente) => void
    const api = apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => new Promise<RespostaAssistente>((r) => (soltar = r)) })
    const w = await montar()
    await abrir(w)
    // Shift+Enter não envia (quebra a linha).
    await caixa(w).setValue('Qual o NPS da Alfa nos últimos 90 dias?')
    await caixa(w).trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(chamadas(api, 'POST', '/assistente/perguntar')).toHaveLength(0)
    expect(t(w.get('[data-contador]').text())).toBe('39/1.000 caracteres')
    await caixa(w).trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(chamadas(api, 'POST', '/assistente/perguntar')[0]!.corpo).toEqual({ pergunta: 'Qual o NPS da Alfa nos últimos 90 dias?', historico: [] })
    expect(caixa(w).element.value).toBe('')
    expect(t(w.get('[data-papel="usuario"]').text())).toBe('Você: Qual o NPS da Alfa nos últimos 90 dias?')
    expect(t(w.get('[data-consultando]').text())).toBe('Consultando os dados…')
    expect(w.get('[data-consultando] [data-icone-toqqiai]').attributes('data-icone-toqqiai')).toBe('selo')
    expect(t(w.get('[data-anuncio]').text())).toBe('Consultando os dados…')
    expect(w.get('[data-nova-conversa]').attributes('disabled')).toBeDefined()

    soltar(RESPOSTA())
    await flushPromises()
    expect(w.find('[data-consultando]').exists()).toBe(false)
    const resposta = w.get('[data-papel="assistente"]')
    // Identificada como do ToqqiAI: o selo da marca ao lado (decorativo) e o nome para leitores de tela.
    const avatar = resposta.get('[data-avatar]')
    expect(avatar.attributes('data-icone-toqqiai')).toBe('selo')
    expect(avatar.attributes('aria-hidden')).toBe('true')
    expect(resposta.get('.sr-only').text()).toBe('ToqqiAI:')
    // Quebras de linha mantidas e as linhas "- " em lista.
    expect(resposta.find('p').text()).toBe('O NPS de 02/09 a 01/10/2026 é 42, com 120 respostas.\nNo período anterior foi 37.')
    expect(resposta.findAll('[data-texto] li').map((li) => li.text())).toEqual(['subiu 5 pontos', '30 respostas a mais'])
    // Para leitores de tela, a resposta inteira de uma vez.
    expect(w.get('[data-anuncio]').attributes('aria-live')).toBe('polite')
    expect(w.get('[data-anuncio]').text()).toContain('subiu 5 pontos')
    // Atalhos: só o conhecido e permitido; vira link para a tela.
    const atalhos = resposta.findAll('[data-atalhos] a')
    expect(atalhos.map((a) => [t(a.text()), a.attributes('href')])).toEqual([['Abrir Relatórios', '/relatorios/empresas']])
    expect(resposta.findAll('[data-sugestoes] button').map((b) => t(b.text()))).toEqual(['E nos últimos 90 dias?', 'Quais clientes puxaram o NPS para baixo?'])
    expect(t(w.get('[data-cota]').text())).toBe('Restam 487 de 500 análises este mês')
    expect(document.activeElement).toBe(caixa(w).element)
  })

  it('enviar pelo botão: ele desliga enquanto a pergunta vai e o foco fica na caixa (não cai no <body>)', async () => {
    entrar()
    let soltar!: (r: RespostaAssistente) => void
    const api = apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => new Promise<RespostaAssistente>((r) => (soltar = r)) })
    const w = await montar()
    await abrir(w)
    await caixa(w).setValue('Qual o NPS?')
    const enviar = w.get<HTMLButtonElement>('button[aria-label="Enviar pergunta"]')
    enviar.element.focus()
    await enviar.trigger('click')
    await flushPromises()
    expect(chamadas(api, 'POST', '/assistente/perguntar')).toHaveLength(1)
    expect(enviar.element.disabled).toBe(true)
    expect(document.activeElement).toBe(caixa(w).element)
    soltar(RESPOSTA())
    await flushPromises()
    expect(document.activeElement).toBe(caixa(w).element)
    // O Esc (a partir de quem tem o foco) continua fechando.
    teclar('Escape')
    await flushPromises()
    expect(painel(w).exists()).toBe(false)
  })

  it('a sugestão de uma resposta envia com o histórico; só a última resposta mostra sugestões', async () => {
    entrar()
    const api = apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA() })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    await w.get('[data-papel="assistente"] [data-sugestoes] button').trigger('click')
    await flushPromises()
    const segunda = chamadas(api, 'POST', '/assistente/perguntar')[1]!.corpo as { pergunta: string; historico: unknown[] }
    expect(segunda.pergunta).toBe('E nos últimos 90 dias?')
    expect(segunda.historico).toEqual([
      { papel: 'usuario', texto: 'Qual o NPS?' },
      { papel: 'assistente', texto: RESPOSTA().resposta },
    ])
    expect(w.findAll('[data-papel="assistente"]')).toHaveLength(2)
    expect(w.findAll('[data-papel="assistente"] [data-sugestoes]')).toHaveLength(1)
  })

  it('sem v-html: HTML na resposta aparece como texto', async () => {
    entrar()
    apiFalsa({
      'GET /assistente': () => ESTADO(),
      'POST /assistente/perguntar': () => RESPOSTA({ resposta: '<img src=x onerror="alert(1)"> <b>negrito</b>\n- <a href="https://x.com">link</a>', atalhos: [] }),
    })
    const w = await montar()
    await abrir(w)
    await perguntar(w, '<script>alert(1)</script>')
    const resposta = w.get('[data-papel="assistente"]')
    expect(resposta.find('img').exists()).toBe(false)
    expect(resposta.find('b').exists()).toBe(false)
    expect(resposta.find('ul li a').exists()).toBe(false)
    expect(resposta.text()).toContain('<img src=x onerror="alert(1)"> <b>negrito</b>')
    expect(resposta.find('li').text()).toBe('<a href="https://x.com">link</a>')
    expect(w.find('[data-papel="usuario"] script').exists()).toBe(false)
    expect(w.get('[data-papel="usuario"]').text()).toContain('<script>alert(1)</script>')
  })

  it('a resposta aparece aos poucos (sem "reduzir movimento"); atalhos e sugestões depois do texto', async () => {
    telas({ reduzir: false })
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA() })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    const completo = RESPOSTA().resposta
    const visivel = () => w.get('[data-papel="assistente"]').text().replace(/^ToqqiAI:\s*/, '')
    expect(visivel().length).toBeLessThan(10)
    expect(w.find('[data-papel="assistente"] [data-atalhos]').exists()).toBe(false)
    vi.advanceTimersByTime(200)
    await flushPromises()
    expect(visivel().length).toBeGreaterThan(10)
    vi.advanceTimersByTime(2000)
    await flushPromises()
    expect(visivel()).toContain('30 respostas a mais')
    expect(completo).toContain('30 respostas a mais')
    expect(w.find('[data-papel="assistente"] [data-atalhos]').exists()).toBe(true)
    // Fechar e abrir de novo não revela outra vez.
    useAssistenteStore().fechar()
    await flushPromises()
    await abrir(w)
    expect(w.get('[data-papel="assistente"]').text()).toContain('30 respostas a mais')
  })

  it('o contador vai até 1.000 caracteres (a caixa não aceita mais)', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO() })
    const w = await montar()
    await abrir(w)
    expect(caixa(w).attributes('maxlength')).toBe('1000')
    await caixa(w).setValue('x'.repeat(1000))
    expect(t(w.get('[data-contador]').text())).toBe('1.000/1.000 caracteres')
    expect(w.get('[data-contador]').classes()).toContain('text-erro')
    // Só espaços não envia.
    await caixa(w).setValue('   ')
    expect(w.get('button[aria-label="Enviar pergunta"]').attributes('disabled')).toBeDefined()
  })
})

describe('erros', () => {
  it('limite por minuto (429): mensagem do contrato na conversa e "Tentar de novo", que manda a mesma pergunta', async () => {
    entrar()
    let vez = 0
    const api = apiFalsa({
      'GET /assistente': () => ESTADO(),
      'POST /assistente/perguntar': () => (++vez === 1 ? erroApi(429, 'limite_perguntas', 'Muitas perguntas em pouco tempo. Aguarde um minuto e tente de novo.') : RESPOSTA()),
    })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    expect(t(w.get('[data-erro]').text())).toBe('Muitas perguntas em pouco tempo. Aguarde um minuto e tente de novo. Tentar de novo')
    expect(t(w.get('[data-anuncio]').text())).toBe('Muitas perguntas em pouco tempo. Aguarde um minuto e tente de novo.')
    const repetir = w.findAll('[data-erro] button').find((b) => t(b.text()) === 'Tentar de novo')!
    await repetir.trigger('click')
    await flushPromises()
    const posts = chamadas(api, 'POST', '/assistente/perguntar')
    expect(posts).toHaveLength(2)
    expect(posts[1]!.corpo).toEqual({ pergunta: 'Qual o NPS?', historico: [] })
    expect(w.findAll('[data-papel="usuario"]')).toHaveLength(1)
    expect(w.find('[data-erro]').exists()).toBe(false)
    expect(w.findAll('[data-papel="assistente"]')).toHaveLength(1)
  })

  it('"Tentar de novo" some enquanto a pergunta vai de novo: o foco passa para a caixa (não cai no <body>)', async () => {
    entrar()
    let vez = 0
    let soltar!: (r: RespostaAssistente) => void
    apiFalsa({
      'GET /assistente': () => ESTADO(),
      'POST /assistente/perguntar': () =>
        ++vez === 1
          ? erroApi(503, 'ia_indisponivel', 'O ToqqiAI está indisponível no momento. Tente de novo em instantes.')
          : new Promise<RespostaAssistente>((r) => (soltar = r)),
    })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    const repetir = w.get<HTMLButtonElement>('[data-erro] button')
    repetir.element.focus()
    await repetir.trigger('click')
    await flushPromises()
    expect(repetir.element.isConnected).toBe(false)
    expect(w.find('[data-consultando]').exists()).toBe(true)
    expect(document.activeElement).toBe(caixa(w).element)
    soltar(RESPOSTA())
    await flushPromises()
    expect(w.find('[data-erro]').exists()).toBe(false)
    expect(document.activeElement).toBe(caixa(w).element)
  })

  it('erro do servidor (500) ou inesperado: a mensagem na conversa, sem "Tentar de novo" (a análise pode ter sido gasta)', async () => {
    entrar()
    apiFalsa({
      'GET /assistente': () => ESTADO(),
      'POST /assistente/perguntar': () => erroApi(500, 'erro_servidor', 'Algo deu errado do nosso lado. Tente de novo em instantes.'),
    })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    expect(t(w.get('[data-erro]').text())).toBe('Algo deu errado do nosso lado. Tente de novo em instantes.')
    expect(w.find('[data-erro] button').exists()).toBe(false)
    // A caixa continua ligada (dá para perguntar de novo à mão).
    expect(caixa(w).element.disabled).toBe(false)
    expect(document.activeElement).toBe(caixa(w).element)
  })

  it('indisponível (503): mensagem da API e "Tentar de novo"; a pergunta que falhou não entra no histórico', async () => {
    entrar()
    let vez = 0
    const api = apiFalsa({
      'GET /assistente': () => ESTADO(),
      'POST /assistente/perguntar': () => (++vez === 1 ? erroApi(503, 'ia_indisponivel', 'O ToqqiAI está indisponível no momento. Tente de novo em instantes.') : RESPOSTA()),
    })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Primeira')
    expect(t(w.get('[data-erro]').text())).toContain('O ToqqiAI está indisponível no momento. Tente de novo em instantes.')
    // Outra pergunta: a que falhou fica na tela, sem "Tentar de novo", e não vai no histórico.
    await perguntar(w, 'Segunda')
    expect(chamadas(api, 'POST', '/assistente/perguntar')[1]!.corpo).toEqual({ pergunta: 'Segunda', historico: [] })
    expect(w.findAll('[data-erro] button')).toHaveLength(0)
  })

  it('cota esgotada (409): desliga a caixa e explica; administrador vê "Ver uso em Configurações › IA"', async () => {
    entrar()
    apiFalsa({
      'GET /assistente': () => ESTADO(),
      'POST /assistente/perguntar': () => erroApi(409, 'cota_esgotada', 'O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º.'),
    })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    expect(t(w.get('[data-erro]').text())).toBe('O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º.')
    expect(caixa(w).element.disabled).toBe(true)
    const bloqueio = w.get('[data-bloqueio]')
    expect(t(bloqueio.text())).toContain('O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º.')
    expect(bloqueio.get('a').attributes('href')).toBe('/configuracoes/ia')
    expect(t(bloqueio.get('a').text())).toBe('Ver uso em Configurações › IA')
    expect(t(w.get('[data-cota]').text())).toBe('Restam 0 de 500 análises este mês')
    // A caixa desligou com o foco nela: o foco vai para o painel (não para o <body>).
    expect(document.activeElement).toBe(painel(w).element)
  })

  it('conta pausada (estado ao abrir): o botão aparece, a caixa fica desligada e explica; sem permissão, sem o link', async () => {
    entrar(['painel.ver'], 'consulta')
    apiFalsa({ 'GET /assistente': () => ESTADO({ disponivel: false, motivo: 'conta_pausada', sugestoes: [] }) })
    const w = await montar()
    expect(botaoFlutuante(w).exists()).toBe(true)
    await abrir(w)
    expect(caixa(w).element.disabled).toBe(true)
    expect(t(w.get('[data-bloqueio]').text())).toBe('O ToqqiAI volta quando a assinatura estiver em dia.')
    expect(w.find('[data-bloqueio] a').exists()).toBe(false)
    expect(w.find('[data-sugestoes]').exists()).toBe(false)
    // Sem caixa ativa, o foco fica no painel.
    expect(document.activeElement).toBe(painel(w).element)
  })

  it('conta pausada (409) para o administrador: "Ver assinatura"', async () => {
    entrar()
    apiFalsa({
      'GET /assistente': () => ESTADO(),
      'POST /assistente/perguntar': () => erroApi(409, 'conta_pausada', 'O ToqqiAI volta quando a assinatura estiver em dia.'),
    })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    expect(w.get('[data-bloqueio] a').attributes('href')).toBe('/assinatura')
    expect(t(w.get('[data-bloqueio] a').text())).toBe('Ver assinatura')
  })

  it('a resposta que gasta a última análise já desliga a caixa; o foco vai para o painel e o Esc continua fechando', async () => {
    entrar()
    apiFalsa({
      'GET /assistente': () => ESTADO({ cota: { usadas: 99, limite: 100, restantes: 1, mes: '2026-10' } }),
      'POST /assistente/perguntar': () => RESPOSTA({ cota: { usadas: 100, limite: 100, restantes: 0, mes: '2026-10' } }),
    })
    const w = await montar()
    ;(botaoFlutuante(w).element as HTMLElement).focus()
    await abrir(w)
    expect(t(w.get('[data-cota]').text())).toBe('Resta 1 de 100 análises este mês')
    await perguntar(w, 'Qual o NPS?')
    expect(caixa(w).element.disabled).toBe(true)
    expect(t(w.get('[data-bloqueio]').text())).toContain('renova no dia 1º')
    expect(document.activeElement).toBe(painel(w).element)
    teclar('Escape')
    await flushPromises()
    expect(painel(w).exists()).toBe(false)
    expect(document.activeElement).toBe(botaoFlutuante(w).element)
  })
})

describe('histórico no navegador', () => {
  it('guarda por conta e usuário (até 20), volta ao reabrir e manda só as últimas 8', async () => {
    const chave = 'toqqi.assistente.3.7'
    const antigas = Array.from({ length: 10 }, (_, i) => ({ papel: i % 2 ? 'assistente' : 'usuario', texto: `m${i}` }))
    sessionStorage.setItem(chave, JSON.stringify(antigas))
    entrar()
    const api = apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA() })
    const w = await montar()
    await abrir(w)
    expect(w.findAll('[data-papel]')).toHaveLength(10)
    await perguntar(w, 'Nova pergunta')
    const corpo = chamadas(api, 'POST', '/assistente/perguntar')[0]!.corpo as { historico: { texto: string }[] }
    expect(corpo.historico).toHaveLength(8)
    expect(corpo.historico.map((m) => m.texto)).toEqual(['m2', 'm3', 'm4', 'm5', 'm6', 'm7', 'm8', 'm9'])
    const guardada = JSON.parse(sessionStorage.getItem(chave)!) as { texto: string }[]
    expect(guardada).toHaveLength(12)
    expect(guardada.at(-1)!.texto).toBe(RESPOSTA().resposta)
    // Até 20 mensagens.
    for (let i = 0; i < 5; i++) await perguntar(w, `p${i}`)
    expect(JSON.parse(sessionStorage.getItem(chave)!)).toHaveLength(20)
    expect(w.findAll('[data-papel]')).toHaveLength(20)
  })

  it('"Nova conversa" limpa a tela e o navegador e volta o foco para a caixa', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA() })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    expect(sessionStorage.getItem('toqqi.assistente.3.7')).not.toBeNull()
    await w.get('[data-nova-conversa]').trigger('click')
    await flushPromises()
    expect(w.find('[data-papel]').exists()).toBe(false)
    expect(w.find('[data-vazio]').exists()).toBe(true)
    expect(sessionStorage.getItem('toqqi.assistente.3.7')).toBeNull()
    expect(document.activeElement).toBe(caixa(w).element)
  })

  it('sair apaga a conversa (e o botão some)', async () => {
    entrar()
    apiFalsa({ 'GET /assistente': () => ESTADO(), 'POST /assistente/perguntar': () => RESPOSTA(), 'POST /auth/sair': () => undefined })
    const w = await montar()
    await abrir(w)
    await perguntar(w, 'Qual o NPS?')
    sessionStorage.setItem('toqqi.assistente.9.9', '[]')
    await useSessaoStore().sair()
    await flushPromises()
    expect(sessionStorage.getItem('toqqi.assistente.3.7')).toBeNull()
    expect(sessionStorage.getItem('toqqi.assistente.9.9')).toBeNull()
    expect(useAssistenteStore().mensagens).toEqual([])
    expect(painel(w).exists()).toBe(false)
    expect(botaoFlutuante(w).exists()).toBe(false)
  })
})
