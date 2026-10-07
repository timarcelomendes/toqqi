// Ajuda (etapa 5b, docs/api-etapa-5b.md §6.1) com a API simulada: tópicos, busca sem acento, endereço com tópico e
// seção, atalhos por permissão, celular, "Pergunte ao assistente"; o item "Ajuda" na barra lateral; a cota em
// Configurações › IA; e nenhum v-html nas telas novas.
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { ConfigIa, Perfil } from '@/api/tipos'
import { useAssistenteStore } from '@/stores/assistente'
import { useSessaoStore } from '@/stores/sessao'
import BarraLateral from '@/layouts/BarraLateral.vue'
import { router as rotasDoApp } from '@/router'
import AjudaView from '@/modulos/ajuda/AjudaView.vue'
import AssistenteFlutuante from '@/modulos/assistente/AssistenteFlutuante.vue'
import IaView from '@/modulos/configuracoes/IaView.vue'
import { apiFalsa } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

function entrar(permissoes: string[], perfil: Perfil = 'gestor') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 7, nome: 'Ana', email: 'ana@sol.com.br', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 3, nome: 'Sol', plano: 'profissional', situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

const AJUDA = {
  versao: 1,
  topicos: [
    {
      id: 'primeiros-passos',
      titulo: 'Primeiros passos',
      resumo: 'Do cadastro à primeira pesquisa.',
      secoes: [{ id: 'visao-geral', titulo: 'Visão geral', somente_admin: false, atalho: 'inicio', palavras: ['começar'], blocos: [{ tipo: 'paragrafo', texto: 'O Toqqi mede a satisfação dos seus clientes com NPS e CSAT.' }] }],
    },
    {
      id: 'contatos',
      titulo: 'Contatos',
      resumo: 'Quem recebe as pesquisas.',
      secoes: [
        {
          id: 'importar-planilha',
          titulo: 'Importar uma planilha',
          somente_admin: false,
          atalho: 'importar_contatos',
          palavras: ['importar', 'planilha', 'csv', 'excel'],
          blocos: [
            { tipo: 'paragrafo', texto: 'Traga seus contatos de uma planilha do Excel ou CSV.' },
            { tipo: 'passos', itens: ['Abra Contatos e clique em "Importar planilha".', 'Escolha o arquivo.', 'Confira as colunas e importe.'] },
            { tipo: 'lista', itens: ['Até 5 MB.', 'Uma linha por contato.'] },
            { tipo: 'dica', texto: 'Use a primeira linha para os nomes das colunas.' },
          ],
        },
        { id: 'grupos', titulo: 'Grupos de contatos', somente_admin: false, atalho: 'contatos', palavras: ['grupo'], blocos: [{ tipo: 'paragrafo', texto: 'Separe os contatos por região.' }] },
      ],
    },
    {
      id: 'integracoes',
      titulo: 'Integrações',
      resumo: 'Ligue o Toqqi a outros sistemas.',
      secoes: [{ id: 'chave-api', titulo: 'Chave da API', somente_admin: true, atalho: 'integracoes', palavras: ['api', 'webhook'], blocos: [{ tipo: 'paragrafo', texto: 'Crie uma chave para o seu sistema mandar contatos.' }] }],
    },
    {
      id: 'configuracoes',
      titulo: 'Configurações',
      resumo: 'Ajustes da conta.',
      secoes: [
        { id: 'notificacoes', titulo: 'Notificações por e-mail', somente_admin: false, atalho: null, palavras: ['email'], blocos: [{ tipo: 'paragrafo', texto: 'Escolha quem recebe o aviso de detrator.' }, { tipo: 'video', url: 'x' }] },
      ],
    },
  ],
}
const ESTADO = { disponivel: true, motivo: null, cota: { usadas: 1, limite: 500, restantes: 499, mes: '2026-10' }, sugestoes: ['Como importo meus contatos?'] }

/** Tela larga (computador) ou estreita (celular). */
function tela(larga: boolean) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('min-width') ? larga : q.includes('reduced-motion'), media: q, addEventListener() {}, removeEventListener() {} }))
}

let router: Router
/** A Ajuda dentro de um "layout" com o botão do assistente (como no AppLayout). */
async function abrirAjuda(caminho: string): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/ajuda/:topico?', component: AjudaView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h('div', [h(RouterView), h(AssistenteFlutuante)]) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const topicoAberto = (w: VueWrapper) => w.get('[data-topico-aberto]').attributes('data-topico-aberto')
const busca = (w: VueWrapper) => w.get<HTMLInputElement>('input[data-busca-ajuda]')
let rolou: ReturnType<typeof vi.fn>

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  sessionStorage.clear()
  tela(true)
  rolou = vi.fn()
  Element.prototype.scrollIntoView = rolou as unknown as Element['scrollIntoView']
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('Ajuda: tópicos', () => {
  it('título, busca, a lista de tópicos e o primeiro aberto em /ajuda, com os blocos', async () => {
    entrar(['contatos.ver', 'importacao.usar'])
    const api = apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda')
    expect(api.chamadas.filter((c) => c.caminho === '/ajuda')).toHaveLength(1)
    expect(t(w.get('h1').text())).toBe('Ajuda')
    expect(busca(w).attributes('placeholder')).toBe('Buscar na ajuda')
    expect(w.get('label[for="' + busca(w).attributes('id') + '"]').text()).toBe('Buscar na ajuda')
    const nav = w.get('nav[aria-label="Tópicos da ajuda"]')
    expect(nav.findAll('a').map((a) => [t(a.text()), a.attributes('href')])).toEqual([
      ['Primeiros passos', '/ajuda/primeiros-passos'],
      ['Contatos', '/ajuda/contatos'],
      ['Integrações', '/ajuda/integracoes'],
      ['Configurações', '/ajuda/configuracoes'],
    ])
    expect(topicoAberto(w)).toBe('primeiros-passos')
    expect(nav.get('a[aria-current="page"]').text()).toBe('Primeiros passos')
    expect(t(w.get('#t-topico').text())).toBe('Primeiros passos')
    expect(t(w.text())).toContain('Do cadastro à primeira pesquisa.')
    // Rodapé com o assistente disponível.
    expect(t(w.get('[data-rodape-ajuda]').text())).toContain('Ainda com dúvida?')
  })

  it('/ajuda/contatos: passos numerados, lista, dica e o atalho "Abrir <tela>" só com permissão', async () => {
    entrar(['contatos.ver', 'importacao.usar'])
    apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda/contatos')
    expect(topicoAberto(w)).toBe('contatos')
    const secao = w.get('[data-secao="importar-planilha"]')
    expect(secao.findAll('ol li').map((li) => li.text())).toEqual(['Abra Contatos e clique em "Importar planilha".', 'Escolha o arquivo.', 'Confira as colunas e importe.'])
    expect(secao.findAll('ul li').map((li) => li.text())).toEqual(['Até 5 MB.', 'Uma linha por contato.'])
    const dica = secao.get('[role="status"]')
    expect(t(dica.get('p.font-semibold').text())).toBe('Dica')
    expect(t(dica.text())).toContain('Use a primeira linha para os nomes das colunas.')
    const atalho = secao.get('a[data-atalho]')
    expect(t(atalho.text())).toBe('Abrir Importar contatos')
    expect(atalho.attributes('href')).toBe('/contatos/importar')
    // Sem importacao.usar, sem o botão.
    setActivePinia(createPinia())
    entrar(['contatos.ver'])
    const w2 = await abrirAjuda('/ajuda/contatos')
    expect(w2.find('[data-secao="importar-planilha"] [data-atalho]').exists()).toBe(false)
    expect(w2.get('[data-secao="grupos"] [data-atalho]').attributes('href')).toBe('/contatos')
  })

  it('seção só de administrador: etiqueta "Só administrador"; o atalho de Integrações só para o administrador', async () => {
    entrar([], 'gestor')
    apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda/integracoes')
    expect(t(w.get('[data-secao="chave-api"] [data-somente-admin]').text())).toBe('Só administrador')
    expect(w.find('[data-secao="chave-api"] [data-atalho]').exists()).toBe(false)
    setActivePinia(createPinia())
    entrar([], 'admin')
    const w2 = await abrirAjuda('/ajuda/integracoes')
    expect(w2.get('[data-secao="chave-api"] [data-atalho]').attributes('href')).toBe('/integracoes')
    // Bloco de tipo desconhecido é ignorado; seção sem atalho, sem botão.
    await router.push('/ajuda/configuracoes')
    await flushPromises()
    expect(w2.get('[data-secao="notificacoes"]').text()).toContain('Escolha quem recebe o aviso de detrator.')
    expect(w2.find('[data-secao="notificacoes"] [data-atalho]').exists()).toBe(false)
  })

  it('endereço com tópico e seção: abre o tópico, rola até a seção e põe o foco no título dela', async () => {
    entrar(['contatos.ver'])
    apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda/contatos#grupos')
    expect(topicoAberto(w)).toBe('contatos')
    expect(document.activeElement?.id).toBe('t-ajuda-grupos')
    expect(rolou).toHaveBeenCalled()
    expect((rolou.mock.contexts.at(-1) as Element).id).toBe('ajuda-grupos')
    // Mudar só a âncora também leva à seção.
    await router.push('/ajuda/contatos#importar-planilha')
    await flushPromises()
    expect(document.activeElement?.id).toBe('t-ajuda-importar-planilha')
  })

  it('tópico que não existe volta para /ajuda', async () => {
    entrar([])
    apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda/nao-existe')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/ajuda')
    expect(topicoAberto(w)).toBe('primeiros-passos')
  })

  it('celular: lista de tópicos antes do conteúdo; escolher um tópico leva ao título dele (com foco)', async () => {
    tela(false)
    entrar(['contatos.ver'])
    apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda')
    const nav = w.get('[data-topicos]').element
    const artigo = w.get('[data-topico-aberto]').element
    expect(nav.compareDocumentPosition(artigo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await w.get('a[data-topico="contatos"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/ajuda/contatos')
    expect(topicoAberto(w)).toBe('contatos')
    expect(document.activeElement?.id).toBe('t-topico')
    expect((rolou.mock.contexts.at(-1) as Element).id).toBe('t-topico')
  })

  it('erro ao carregar: mensagem e "Tentar de novo"', async () => {
    entrar([])
    let vez = 0
    apiFalsa({ 'GET /ajuda': () => (++vez === 1 ? new Response(null, { status: 500 }) : AJUDA), 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda')
    expect(t(w.get('[role="alert"]').text())).toContain('Algo deu errado do nosso lado')
    await w.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(topicoAberto(w)).toBe('primeiros-passos')
  })
})

describe('Ajuda: busca', () => {
  it('sem acento e em todos os tópicos: mostra as seções com o nome do tópico; clicar abre a seção', async () => {
    entrar(['contatos.ver'])
    apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda')
    await busca(w).setValue('NOTIFICACAO')
    let resultados = w.findAll('[data-resultado]')
    expect(resultados.map((r) => r.attributes('data-resultado'))).toEqual(['configuracoes#notificacoes'])
    expect(t(resultados[0]!.text())).toBe('Notificações por e-mail')
    const cartao = resultados[0]!.element.closest('li')!
    expect(cartao.querySelector('[data-resultado-topico]')!.textContent).toBe('Configurações')
    expect(cartao.querySelector('[data-resultado-trecho]')!.textContent).toBe('Escolha quem recebe o aviso de detrator.')
    expect(resultados[0]!.attributes('href')).toBe('/ajuda/configuracoes#notificacoes')
    expect(t(w.get('#t-resultados').text())).toBe('Resultados para “NOTIFICACAO”')
    expect(t(w.get('p.sr-only[role="status"]').text())).toBe('1 seção encontrada')
    // Com acento também; e "regiao" acha "região".
    await busca(w).setValue('região')
    resultados = w.findAll('[data-resultado]')
    expect(resultados.map((r) => r.attributes('data-resultado'))).toEqual(['contatos#grupos'])
    await resultados[0]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/ajuda/contatos#grupos')
    expect(busca(w).element.value).toBe('')
    expect(topicoAberto(w)).toBe('contatos')
    expect(document.activeElement?.id).toBe('t-ajuda-grupos')
  })

  it('nada encontrado: "Nenhum resultado" e "Pergunte ao ToqqiAI" (com o símbolo da marca), que abre o chat com o termo na caixa (sem enviar)', async () => {
    entrar(['contatos.ver'])
    const api = apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ESTADO })
    const w = await abrirAjuda('/ajuda')
    await busca(w).setValue('boleto vencido')
    expect(w.findAll('[data-resultado]')).toHaveLength(0)
    expect(t(w.get('[data-resultados]').text())).toContain('Nenhum resultado')
    const perguntar = w.get('button[data-perguntar-assistente]')
    expect(t(perguntar.text())).toBe('Pergunte ao ToqqiAI')
    expect(perguntar.get('svg').attributes('data-icone-toqqiai')).toBe('simbolo')
    expect(perguntar.get('svg').attributes('aria-hidden')).toBe('true')
    expect(perguntar.find('.lucide-sparkles').exists()).toBe(false)
    // O rodapé também chama o ToqqiAI pelo nome, com o mesmo ícone.
    const rodape = w.get('[data-rodape-ajuda]')
    expect(t(rodape.text())).toBe('Ainda com dúvida? O ToqqiAI responde sobre o uso do Toqqi e sobre os resultados dos seus clientes. Pergunte ao ToqqiAI')
    expect(rodape.get('button svg').attributes('data-icone-toqqiai')).toBe('simbolo')
    await perguntar.trigger('click')
    await flushPromises()
    expect(useAssistenteStore().aberto).toBe(true)
    expect(w.get<HTMLTextAreaElement>('#assistente-pergunta').element.value).toBe('boleto vencido')
    expect(api.chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(0)
  })

  it('sem o ToqqiAI disponível, sem "Pergunte ao ToqqiAI" (nem o rodapé)', async () => {
    entrar(['contatos.ver'])
    apiFalsa({ 'GET /ajuda': () => AJUDA, 'GET /assistente': () => ({ disponivel: false, motivo: 'ia_indisponivel', cota: null, sugestoes: [] }) })
    const w = await abrirAjuda('/ajuda')
    expect(w.find('[data-rodape-ajuda]').exists()).toBe(false)
    await busca(w).setValue('boleto')
    expect(t(w.get('[data-resultados]').text())).toContain('Nenhum resultado')
    expect(w.find('button[data-perguntar-assistente]').exists()).toBe(false)
  })
})

describe('Ajuda na navegação', () => {
  it('rota /ajuda para qualquer logado; item "Ajuda" no rodapé da barra, acima de "Recolher menu" (e na gaveta)', async () => {
    const r = rotasDoApp.resolve('/ajuda/contatos')
    expect(r.name).toBe('ajuda')
    expect(r.params.topico).toBe('contatos')
    expect(r.meta.permissao).toBeUndefined()
    expect(r.meta.logado).toBe(true)
    expect(rotasDoApp.resolve('/ajuda').name).toBe('ajuda')

    entrar([])
    router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
    await router.push('/ajuda/contatos')
    await router.isReady()
    const w = mount(BarraLateral, { props: { recolhivel: true }, global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    const rodape = w.get('button[aria-controls="menu-lateral"]').element.parentElement!
    const itens = Array.from(rodape.children).map((el) => (el.textContent ?? '').trim())
    expect(itens).toEqual(['Ajuda', 'Feedback', 'Recolher menu']) // Feedback: abaixo de Ajuda
    const ajuda = w.findAll('a').find((a) => t(a.text()) === 'Ajuda')!
    expect(ajuda.attributes('href')).toBe('/ajuda')
    expect(ajuda.attributes('aria-current')).toBe('page')
    w.unmount()
    const gaveta = mount(BarraLateral, { props: { recolhivel: false }, global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    expect(gaveta.findAll('a').some((a) => t(a.text()) === 'Ajuda')).toBe(true)
  })
})

describe('Configurações › IA: cota do plano', () => {
  const CONFIG: ConfigIa = { disponivel: true, provedor: 'OpenAI', analise_respostas: true, mes: '2026-10', analises: 40, limite: 500, pendentes: 0, falharam_no_mes: 0 }

  async function abrirIa(config: ConfigIa, extra: Parameters<typeof apiFalsa>[0] = {}) {
    entrar(['configuracoes.gerenciar'], 'admin')
    apiFalsa({ 'GET /conta/ia': () => config, ...extra })
    router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: IaView }] })
    await router.push('/configuracoes/ia')
    await router.isReady()
    const w = mount(IaView, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    return w
  }

  it('"X de Y análises usadas em <mês>" com medidor e a frase da cota', async () => {
    const w = await abrirIa({ ...CONFIG, cota: { usadas: 12, limite: 500, restantes: 488, mes: '2026-10' } })
    const bloco = w.get('[data-cota-plano]')
    expect(t(bloco.get('h2').text())).toBe('Cota de IA do plano')
    expect(t(bloco.get('[data-cota-texto]').text())).toBe('12 de 500 análises usadas em outubro de 2026')
    const medidor = bloco.get('[role="meter"]')
    expect(medidor.attributes('aria-valuenow')).toBe('12')
    expect(medidor.attributes('aria-valuemax')).toBe('500')
    expect(medidor.attributes('aria-valuetext')).toBe('12 de 500 análises usadas em outubro de 2026')
    // Etapa 5g: sem as análises de cada nível (servidor antigo), a frase não cita números.
    expect(t(bloco.text())).toContain(
      'Cada pergunta ao ToqqiAI, cada resumo do painel e cada parecer dos relatórios usam análises da cota conforme o nível do modelo. A análise de cada resposta e os passos das ações não entram nesta conta.',
    )
    // O cartão da cota (gasta pelo ToqqiAI) tem o ícone dele, não um ícone genérico.
    expect(bloco.get('svg').attributes('data-icone-toqqiai')).toBe('simbolo')
    expect(bloco.find('.lucide-bot-message-square').exists()).toBe(false)
    expect(bloco.find('[role="status"]').exists()).toBe(false)
  })

  it('cota esgotada avisa; servidor sem a cota não mostra o bloco', async () => {
    const w = await abrirIa({ ...CONFIG, cota: { usadas: 2000, limite: 2000, restantes: 0, mes: '2026-10' } })
    expect(t(w.get('[data-cota-plano] [role="status"]').text())).toContain('A cota deste mês acabou: o ToqqiAI, o resumo do painel e o parecer dos relatórios voltam no dia 1º.')
    expect(t(w.get('[data-cota-texto]').text())).toBe('2.000 de 2.000 análises usadas em outubro de 2026')
    w.unmount()
    setActivePinia(createPinia())
    const w2 = await abrirIa(CONFIG)
    expect(w2.find('[data-cota-plano]').exists()).toBe(false)
  })

  it('acompanha o assistente: vale a cota mais recente do mesmo mês (a da tela ou a da última resposta)', async () => {
    const estado = (usadas: number, mes = '2026-10') => ({ disponivel: true, motivo: null, sugestoes: [], cota: { usadas, limite: 500, restantes: 500 - usadas, mes } })
    // O assistente leu a cota ao entrar (10); a tela, depois (12): vale a da tela.
    entrar(['configuracoes.gerenciar'], 'admin')
    const assistente = useAssistenteStore()
    assistente.estado = estado(10)
    const w = await abrirIa(
      { ...CONFIG, cota: { usadas: 12, limite: 500, restantes: 488, mes: '2026-10' } },
      { 'PUT /conta/ia': () => ({ ...CONFIG, analise_respostas: false, cota: { usadas: 15, limite: 500, restantes: 485, mes: '2026-10' } }) },
    )
    const texto = () => t(w.get('[data-cota-texto]').text())
    expect(texto()).toBe('12 de 500 análises usadas em outubro de 2026')
    // Uma pergunta ao assistente (a resposta traz a cota): a tela acompanha, com o medidor.
    assistente.estado = estado(13)
    await flushPromises()
    expect(texto()).toBe('13 de 500 análises usadas em outubro de 2026')
    expect(w.get('[data-cota-plano] [role="meter"]').attributes('aria-valuenow')).toBe('13')
    // Cota de outro mês (o mês virou com a tela aberta) não se mistura com a da tela.
    assistente.estado = estado(1, '2026-11')
    await flushPromises()
    expect(texto()).toBe('13 de 500 análises usadas em outubro de 2026')
    // A tela leu de novo (salvou a chave da análise): a leitura nova vale.
    const chave = w.findAll('label').find((l) => t(l.text()) === 'Analisar comentários com IA')!
    await w.get(`[id="${chave.attributes('for')}"]`).trigger('click')
    await flushPromises()
    expect(texto()).toBe('15 de 500 análises usadas em outubro de 2026')
  })
})

describe('Configurações › IA: o que é enviado à IA', () => {
  it('separa a análise dos comentários do ToqqiAI, que manda a conversa e os dados que consulta', async () => {
    entrar(['configuracoes.gerenciar'], 'admin')
    apiFalsa({ 'GET /conta/ia': () => ({ disponivel: true, provedor: 'OpenAI', analise_respostas: true, mes: '2026-10', analises: 0, limite: 500, pendentes: 0, falharam_no_mes: 0 }) })
    router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: IaView }] })
    await router.push('/configuracoes/ia')
    await router.isReady()
    const w = mount(IaView, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    const bloco = w.get('[data-ia-privacidade]')
    expect(t(bloco.get('h2').text())).toBe('O que é enviado à IA')
    // Etapa 5d: também os passos das ações e o resumo do painel e o parecer dos relatórios.
    expect(bloco.findAll('h3').map((h3) => t(h3.text()))).toEqual([
      'Na análise dos comentários',
      'Nos passos das ações',
      'No resumo do painel e no parecer dos relatórios',
      'No ToqqiAI',
    ])
    // O "Nunca o nome… a empresa do cliente" vale só para a análise dos comentários.
    const analise = bloco.get('[data-envio-analise]')
    expect(t(analise.text())).toContain('Nunca o nome, o e-mail, o telefone, a empresa do cliente ou os dados do pedido.')
    const doAssistente = bloco.get('[data-envio-assistente]')
    expect(doAssistente.findAll('li').map((li) => t(li.text()))).toEqual([
      'A pergunta, as últimas mensagens da conversa e o nome da sua conta.',
      'Os dados que ele consulta para responder: números, nomes de empresas e de contatos e comentários dos clientes.',
      'O provedor (OpenAI) não guarda a conversa.',
    ])
    expect(t(doAssistente.text())).not.toContain('Nunca')
  })
})

describe('sem HTML vindo de fora', () => {
  it('as telas da Ajuda e do assistente não usam v-html nem innerHTML', () => {
    for (const pasta of ['src/modulos/ajuda', 'src/modulos/assistente']) {
      for (const arquivo of readdirSync(pasta)) {
        const fonte = readFileSync(join(pasta, arquivo), 'utf8')
        expect(fonte, arquivo).not.toMatch(/v-html|innerHTML|outerHTML|insertAdjacentHTML/)
      }
    }
  })
})
