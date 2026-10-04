// Ajuda em jornadas (docs/ajuda-jornadas.md §3): leitura defensiva, número, próxima, "Saiba mais" e tópico "dono"; busca
// com jornadas e seções juntas; a página Jornadas em /ajuda e /ajuda/jornadas (mapa, cartões, atalho permitido e
// negado, Saiba mais, Próxima), âncoras com rolagem e foco, "Jornadas" no menu, a chamada no tópico e o conteúdo sem
// jornadas igual ao de antes.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { Perfil } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import AjudaView from '@/modulos/ajuda/AjudaView.vue'
import AssistenteFlutuante from '@/modulos/assistente/AssistenteFlutuante.vue'
import {
  buscarNaAjuda,
  jornadasDoGrupo,
  jornadasDoTopico,
  lerConteudo,
  lerReferencia,
  proximaJornada,
  referenciasDaJornada,
} from '@/modulos/ajuda/logica'
import { apiFalsa } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

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

const TOPICOS = [
  {
    id: 'primeiros-passos',
    titulo: 'Primeiros passos',
    resumo: 'Do cadastro à primeira pesquisa.',
    secoes: [{ id: 'visao-geral', titulo: 'Visão geral', somente_admin: false, atalho: 'inicio', palavras: ['começar'], blocos: [{ tipo: 'paragrafo', texto: 'O Toqqi mede a satisfação dos seus clientes.' }] }],
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
        palavras: ['importar', 'excel', 'csv'],
        blocos: [{ tipo: 'passos', itens: ['Abra Contatos.', 'Clique em “Importar planilha”.'] }],
      },
      { id: 'grupos', titulo: 'Grupos de contatos', somente_admin: false, atalho: 'contatos', palavras: ['grupo'], blocos: [{ tipo: 'paragrafo', texto: 'Separe os contatos por região.' }] },
    ],
  },
  {
    id: 'configuracoes',
    titulo: 'Configurações',
    resumo: 'Ajustes da conta.',
    secoes: [{ id: 'notificacoes', titulo: 'Notificações por e-mail', somente_admin: true, atalho: 'config_envios', palavras: ['email'], blocos: [{ tipo: 'paragrafo', texto: 'Escolha quem recebe o aviso de detrator.' }] }],
  },
  {
    id: 'integracoes',
    titulo: 'Integrações',
    resumo: 'Ligue o Toqqi a outros sistemas.',
    secoes: [{ id: 'chave-api', titulo: 'Chave da API', somente_admin: true, atalho: 'integracoes', palavras: ['api'], blocos: [{ tipo: 'paragrafo', texto: 'Crie uma chave para o seu sistema.' }] }],
  },
  {
    id: 'minha-conta',
    titulo: 'Minha conta',
    resumo: 'Seu nome e sua senha.',
    secoes: [{ id: 'trocar-senha', titulo: 'Trocar a senha', somente_admin: false, atalho: 'minha_conta', palavras: ['senha'], blocos: [{ tipo: 'paragrafo', texto: 'Em Minha conta, troque a senha.' }] }],
  },
]

const JORNADAS = [
  {
    id: 'cadastrar-clientes',
    grupo: 'ciclo',
    titulo: 'Cadastrar seus clientes',
    objetivo: 'Trazer sua lista de clientes para o Toqqi.',
    somente_admin: false,
    onde: ['Contatos', 'Importar planilha'],
    atalho: 'importar_contatos',
    como: ['Em Contatos, clique em “Importar planilha”.', 'Escolha o arquivo.', 'Clique em “Importar N contatos”.'],
    resultado: 'A tela “Importação concluída!” mostra quantos contatos são novos.',
    veja: ['contatos#importar-planilha', 'contatos#nao-existe', 'contatos#grupos'],
    palavras: ['subir lista', 'excel'],
  },
  {
    id: 'ligar-envios',
    grupo: 'ciclo',
    titulo: 'Ligar os envios',
    objetivo: 'Conferir o convite e ligar os envios por e-mail.',
    somente_admin: true,
    onde: ['Configurações', 'Envios'],
    atalho: 'config_envios',
    como: ['Em Configurações › Envios, confira o convite.', 'Ligue “Enviar pesquisas por e-mail” e clique em “Salvar alterações”.'],
    resultado: 'Os botões de envio por e-mail ficam liberados.',
    // A segunda referência é de Contatos: a chamada fica só em Configurações (o tópico da primeira).
    veja: ['configuracoes#notificacoes', 'contatos#grupos'],
    palavras: ['automático'],
  },
  {
    id: 'perguntar-toqqiai',
    grupo: 'alem',
    titulo: 'Perguntar ao ToqqiAI',
    objetivo: 'Perguntar em português sobre os seus clientes.',
    somente_admin: false,
    onde: ['Qualquer tela', 'Botão ToqqiAI'],
    atalho: null,
    como: ['Clique no botão “ToqqiAI”.', 'Escreva a pergunta e aperte Enter.'],
    resultado: 'A resposta traz os números da sua conta.',
    veja: ['primeiros-passos#visao-geral'],
    palavras: ['chat'],
  },
  {
    id: 'enviar-pesquisa',
    grupo: 'ciclo',
    titulo: 'Enviar a pesquisa',
    objetivo: 'Mandar a pesquisa agora para quem você escolher.',
    somente_admin: false,
    onde: ['Envios', 'Contatos'],
    atalho: 'envios',
    como: ['Marque quem vai receber.', 'Clique em “Enviar para selecionados”.'],
    resultado: 'Cada contato passa a “Aguardando resposta”.',
    veja: ['envios#nao-existe'],
    palavras: [],
  },
  {
    id: 'ligar-sistema',
    grupo: 'outro-grupo',
    titulo: 'Ligar o seu sistema',
    objetivo: 'Fazer a pesquisa sair sozinha a cada entrega.',
    somente_admin: true,
    onde: ['Integrações'],
    atalho: 'integracoes',
    como: ['Gere a chave de integração.', 'Entregue a chave a quem cuida do sistema.'],
    resultado: 'A cada entrega, o cliente recebe a pesquisa.',
    veja: ['integracoes#chave-api'],
    palavras: ['api', 'webhook'],
  },
]

const AJUDA = { versao: 1, jornadas: JORNADAS, topicos: TOPICOS }
const SEM_JORNADAS = { versao: 1, topicos: TOPICOS }
const ESTADO = { disponivel: true, motivo: null, cota: { usadas: 1, limite: 500, restantes: 499, mes: '2026-10' }, sugestoes: [] }

function tela(larga: boolean) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('min-width') ? larga : q.includes('reduced-motion'), media: q, addEventListener() {}, removeEventListener() {} }))
}

let router: Router
async function abrirAjuda(caminho: string, conteudo: unknown = AJUDA): Promise<VueWrapper> {
  apiFalsa({ 'GET /ajuda': () => conteudo, 'GET /assistente': () => ESTADO })
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

const cartao = (w: VueWrapper, id: string) => w.get(`article[data-jornada="${id}"]`)
const caminhoAtual = () => router.currentRoute.value.fullPath
const focado = () => document.activeElement?.id
function semOs(el: Element, seletor: string): string {
  const copia = el.cloneNode(true) as Element
  copia.querySelectorAll(seletor).forEach((n) => n.remove())
  return t(copia.textContent ?? '')
}
/** O texto que um leitor de tela ouve (sem o que é aria-hidden) e o que aparece na tela (sem o sr-only). */
const textoLido = (el: Element) => semOs(el, '[aria-hidden="true"]')
const textoVisto = (el: Element) => semOs(el, '.sr-only')
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

describe('jornadas: leitura e regras', () => {
  it('lê com a mesma defesa dos tópicos: sem id, título, onde, como ou resultado fica de fora; grupo desconhecido vira "alem"; id repetido vale o primeiro', () => {
    const c = lerConteudo({
      versao: 1,
      topicos: [],
      jornadas: [
        null,
        'texto',
        { id: 'boa', grupo: 'ciclo', titulo: 'Boa', objetivo: 'Objetivo.', somente_admin: true, onde: ['A', '', 3, 'B'], atalho: 'envios', como: ['Um.', ' ', 'Dois.'], resultado: 'Fim.', veja: ['a#b', 7, ''], palavras: ['x', null] },
        { grupo: 'ciclo', titulo: 'Sem id', onde: ['A'], como: ['Um.'], resultado: 'Fim.' },
        { id: 'sem-titulo', titulo: '  ', onde: ['A'], como: ['Um.'], resultado: 'Fim.' },
        { id: 'sem-onde', titulo: 'Sem onde', onde: [], como: ['Um.'], resultado: 'Fim.' },
        { id: 'onde-texto', titulo: 'Onde em texto', onde: 'Contatos › Importar', como: ['Um.'], resultado: 'Fim.' },
        { id: 'sem-como', titulo: 'Sem como', onde: ['A'], como: [' '], resultado: 'Fim.' },
        { id: 'sem-resultado', titulo: 'Sem resultado', onde: ['A'], como: ['Um.'], resultado: '' },
        { id: 'boa', grupo: 'ciclo', titulo: 'Repetida', onde: ['A'], como: ['Um.'], resultado: 'Fim.' },
        { id: 'minima', grupo: 'novo-grupo', titulo: 'Mínima', onde: ['A'], como: ['Um.'], resultado: 'Fim.', somente_admin: 'sim', atalho: 5 },
        { id: 'sem-grupo', titulo: 'Sem grupo', onde: ['A'], como: ['Um.'], resultado: 'Fim.' },
      ],
    })
    expect(c.jornadas.map((j) => j.id)).toEqual(['boa', 'minima', 'sem-grupo'])
    expect(c.jornadas[0]).toEqual({
      id: 'boa',
      grupo: 'ciclo',
      titulo: 'Boa',
      objetivo: 'Objetivo.',
      somente_admin: true,
      onde: ['A', 'B'],
      atalho: 'envios',
      como: ['Um.', 'Dois.'],
      resultado: 'Fim.',
      veja: ['a#b'],
      palavras: ['x'],
    })
    expect(c.jornadas[1]).toMatchObject({ grupo: 'alem', objetivo: '', somente_admin: false, atalho: null, veja: [], palavras: [] })
    expect(c.jornadas[2]!.grupo).toBe('alem')
    // Conteúdo sem jornadas (ou com a chave estranha): lista vazia.
    expect(lerConteudo({ versao: 1, topicos: [] }).jornadas).toEqual([])
    expect(lerConteudo({ versao: 1, topicos: [], jornadas: { id: 'x' } }).jornadas).toEqual([])
  })

  it('número só no ciclo (1..N na ordem do conteúdo) e a próxima do ciclo (nenhuma na última nem nas "para ir além")', () => {
    const { jornadas } = lerConteudo(AJUDA)
    expect(jornadasDoGrupo(jornadas, 'ciclo').map((x) => [x.jornada.id, x.numero])).toEqual([
      ['cadastrar-clientes', 1],
      ['ligar-envios', 2],
      ['enviar-pesquisa', 3],
    ])
    expect(jornadasDoGrupo(jornadas, 'alem').map((x) => [x.jornada.id, x.numero])).toEqual([
      ['perguntar-toqqiai', null],
      ['ligar-sistema', null],
    ])
    const porId = (id: string) => jornadas.find((j) => j.id === id)!
    expect(proximaJornada(jornadas, porId('cadastrar-clientes'))?.id).toBe('ligar-envios')
    // A "para ir além" no meio da lista não entra na sequência.
    expect(proximaJornada(jornadas, porId('ligar-envios'))?.id).toBe('enviar-pesquisa')
    expect(proximaJornada(jornadas, porId('enviar-pesquisa'))).toBeNull()
    expect(proximaJornada(jornadas, porId('perguntar-toqqiai'))).toBeNull()
  })

  it('"Saiba mais": as referências que existem, na ordem e sem repetir; o tópico "dono" é o da primeira', () => {
    const { jornadas, topicos } = lerConteudo(AJUDA)
    const j = { ...jornadas[0]!, veja: ['contatos#grupos', 'contatos', '#grupos', 'contatos#', 'nada#grupos', 'contatos#nao-existe', 'contatos#grupos', 'configuracoes#notificacoes'] }
    expect(referenciasDaJornada(topicos, j).map((r) => [r.topico.id, r.secao.id, r.secao.titulo])).toEqual([
      ['contatos', 'grupos', 'Grupos de contatos'],
      ['configuracoes', 'notificacoes', 'Notificações por e-mail'],
    ])
    expect(lerReferencia('contatos#grupos')).toEqual({ topico: 'contatos', secao: 'grupos' })
    expect(lerReferencia('contatos')).toBeNull()
    expect(jornadasDoTopico(jornadas, 'contatos').map((x) => x.id)).toEqual(['cadastrar-clientes'])
    expect(jornadasDoTopico(jornadas, 'configuracoes').map((x) => x.id)).toEqual(['ligar-envios'])
    expect(jornadasDoTopico(jornadas, 'minha-conta')).toEqual([])
    // O tópico vem da primeira referência mesmo que a seção dela não exista ("Enviar a pesquisa" é de Envios).
    expect(jornadasDoTopico(jornadas, 'envios').map((x) => x.id)).toEqual(['enviar-pesquisa'])
  })
})

describe('busca com jornadas', () => {
  const conteudo = lerConteudo(AJUDA)

  it('acha jornadas e seções juntas; no empate, a jornada antes; o resultado da jornada vai para /ajuda/jornadas', () => {
    // "excel": palavra-chave da jornada e da seção (3 pontos cada): empate, a jornada primeiro.
    const r = buscarNaAjuda(conteudo, 'excel')
    expect(r.map((x) => `${x.topico.id}#${x.secao.id}`)).toEqual(['jornadas#cadastrar-clientes', 'contatos#importar-planilha'])
    expect(r[0]!.topico).toEqual({ id: 'jornadas', titulo: 'Jornadas' })
    expect(r[0]!.secao).toEqual({ id: 'cadastrar-clientes', titulo: 'Cadastrar seus clientes' })
    expect(r[0]!.jornada?.id).toBe('cadastrar-clientes')
    expect(r[1]!.jornada).toBeNull()
    // Mais pontos ganham do desempate: "importar" está no título e nas palavras da seção (3) e só no texto da jornada (1).
    expect(buscarNaAjuda(conteudo, 'importar').map((x) => x.secao.id)).toEqual(['importar-planilha', 'cadastrar-clientes'])
    // Mais palavras do termo ganham de mais pontos.
    expect(buscarNaAjuda(conteudo, 'automático email').map((x) => x.secao.id)).toEqual(['ligar-envios', 'notificacoes'])
    expect(buscarNaAjuda(conteudo, 'webhook').map((x) => x.secao.id)).toEqual(['ligar-sistema'])
  })

  it('o trecho sai do texto da jornada: o objetivo, "Onde: …", os passos ou o resultado (a primeira parte com a palavra)', () => {
    const trecho = (termo: string, id: string) => buscarNaAjuda(conteudo, termo).find((x) => x.secao.id === id)?.trecho
    expect(trecho('cadastrar', 'cadastrar-clientes')).toBe('Trazer sua lista de clientes para o Toqqi.')
    expect(trecho('importação', 'cadastrar-clientes')).toBe('Onde: Contatos › Importar planilha')
    expect(trecho('selecionados', 'enviar-pesquisa')).toBe('1. Marque quem vai receber. 2. Clique em “Enviar para selecionados”.')
    expect(trecho('aguardando', 'enviar-pesquisa')).toBe('Cada contato passa a “Aguardando resposta”.')
    // O rótulo "Onde" não conta como palavra do texto.
    expect(buscarNaAjuda(conteudo, 'ond')).toEqual([])
  })

  it('na tela: "Jornadas" no lugar do tópico, link para a âncora; clicar abre o cartão com o foco no título', async () => {
    entrar(['contatos.ver', 'importacao.usar'])
    const w = await abrirAjuda('/ajuda/contatos')
    await w.get<HTMLInputElement>('input[data-busca-ajuda]').setValue('excel')
    const links = w.findAll('[data-resultado]')
    expect(links.map((a) => a.attributes('data-resultado'))).toEqual(['jornadas#cadastrar-clientes', 'contatos#importar-planilha'])
    const primeiro = links[0]!.element.closest('li')!
    expect(primeiro.querySelector('[data-resultado-topico]')!.textContent).toBe('Jornadas')
    expect(t(links[0]!.text())).toBe('Cadastrar seus clientes')
    expect(links[0]!.attributes('href')).toBe('/ajuda/jornadas#cadastrar-clientes')
    expect(primeiro.querySelector('[data-resultado-trecho]')!.textContent).toBe('Trazer sua lista de clientes para o Toqqi.')
    expect(t(w.get('p.sr-only[role="status"]').text())).toBe('1 jornada e 1 seção encontradas')
    // Durante a busca, nada do menu fica marcado.
    expect(w.find('nav[aria-label="Tópicos da ajuda"] [aria-current]').exists()).toBe(false)
    await links[0]!.trigger('click')
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda/jornadas#cadastrar-clientes')
    expect(w.get<HTMLInputElement>('input[data-busca-ajuda]').element.value).toBe('')
    expect(w.find('[data-pagina-jornadas]').exists()).toBe(true)
    expect(focado()).toBe('t-ajuda-cadastrar-clientes')
    expect((rolou.mock.contexts.at(-1) as Element).id).toBe('ajuda-cadastrar-clientes')
  })
})

describe('página Jornadas', () => {
  it('/ajuda abre a página Jornadas: título, texto e o mapa com os dois grupos (números no ciclo, ícone no "para ir além")', async () => {
    entrar(['contatos.ver', 'importacao.usar'])
    const w = await abrirAjuda('/ajuda')
    expect(w.find('[data-topico-aberto]').exists()).toBe(false)
    const pagina = w.get('[data-pagina-jornadas]')
    expect(t(pagina.get('h2#t-topico').text())).toBe('Jornadas')
    expect(t(pagina.text())).toContain('Cada funcionalidade em três partes: onde fica, como fazer e o que você ganha. Na primeira vez, siga na ordem.')
    const mapa = pagina.get('nav[aria-label="Mapa das jornadas"]')
    const ciclo = mapa.get('ol[data-mapa-grupo="ciclo"]')
    const alem = mapa.get('ul[data-mapa-grupo="alem"]')
    expect(t(mapa.get(`#${ciclo.attributes('aria-labelledby')}`).text())).toBe('Do cadastro ao resultado')
    expect(t(mapa.get(`#${alem.attributes('aria-labelledby')}`).text())).toBe('Para ir além')
    // O número é enfeite (a lista numerada já diz a posição); o leitor de tela ouve o título e o caminho.
    expect(ciclo.findAll('a').map((a) => [a.attributes('href'), t(a.get('[data-mapa-numero]').text()), textoLido(a.element)])).toEqual([
      ['/ajuda/jornadas#cadastrar-clientes', '1', 'Cadastrar seus clientes, Contatos, Importar planilha'],
      ['/ajuda/jornadas#ligar-envios', '2', 'Ligar os envios, Configurações, Envios'],
      ['/ajuda/jornadas#enviar-pesquisa', '3', 'Enviar a pesquisa, Envios, Contatos'],
    ])
    expect(ciclo.get('[data-mapa-numero]').attributes('aria-hidden')).toBe('true')
    const ondeNoMapa = ciclo.get('[data-mapa-onde]')
    expect(textoVisto(ondeNoMapa.element)).toBe('Contatos› Importar planilha')
    expect(ondeNoMapa.findAll('span').filter((s) => s.text() === '›').map((s) => s.attributes('aria-hidden'))).toEqual(['true'])
    expect(alem.findAll('a').map((a) => a.attributes('href'))).toEqual(['/ajuda/jornadas#perguntar-toqqiai', '/ajuda/jornadas#ligar-sistema'])
    expect(alem.get('[data-mapa-numero]').text()).toBe('')
    expect(alem.get('[data-mapa-numero]').find('svg').exists()).toBe(true)
    expect(alem.get('[data-mapa-numero]').attributes('aria-hidden')).toBe('true')
  })

  it('/ajuda/jornadas também; os cartões vêm por grupo (h3) com h4, número, objetivo e as três paradas numa lista de descrição', async () => {
    entrar(['contatos.ver', 'importacao.usar'])
    const w = await abrirAjuda('/ajuda/jornadas')
    const pagina = w.get('[data-pagina-jornadas]')
    const grupos = pagina.findAll('section[data-grupo-jornadas]')
    expect(grupos.map((g) => [t(g.get('h3').text()), g.findAll('article').map((a) => a.attributes('data-jornada'))])).toEqual([
      ['Do cadastro ao resultado', ['cadastrar-clientes', 'ligar-envios', 'enviar-pesquisa']],
      ['Para ir além', ['perguntar-toqqiai', 'ligar-sistema']],
    ])
    const c = cartao(w, 'cadastrar-clientes')
    expect(c.attributes('id')).toBe('ajuda-cadastrar-clientes')
    expect(c.attributes('aria-labelledby')).toBe('t-ajuda-cadastrar-clientes')
    expect(t(c.get('h4#t-ajuda-cadastrar-clientes').text())).toBe('1. Cadastrar seus clientes')
    expect(c.get('h4').attributes('tabindex')).toBe('-1')
    expect(t(c.get('[data-numero]').text())).toBe('1')
    expect(t(c.get('[data-objetivo]').text())).toBe('Trazer sua lista de clientes para o Toqqi.')
    expect(c.find('[data-somente-admin]').exists()).toBe(false)
    // Onde, Como e Resultado numa dl.
    const dl = c.get('dl')
    expect(dl.findAll('dt').map((dt) => t(dt.text()))).toEqual(['Onde', 'Como', 'Resultado'])
    expect(dl.findAll('dd')).toHaveLength(3)
    const onde = dl.get('ol[data-onde]')
    expect(onde.attributes('aria-label')).toBe('Caminho até a tela')
    expect(onde.findAll('li').map((li) => textoLido(li.element))).toEqual(['Contatos', 'Importar planilha'])
    const separadores = onde.findAll('li span').filter((s) => s.text() === '›')
    expect(separadores).toHaveLength(1)
    expect(separadores[0]!.attributes('aria-hidden')).toBe('true')
    expect(dl.get('[data-parada="como"] ol').findAll('li').map((li) => li.text())).toEqual([
      'Em Contatos, clique em “Importar planilha”.',
      'Escolha o arquivo.',
      'Clique em “Importar N contatos”.',
    ])
    expect(t(dl.get('[data-parada="resultado"] dd').text())).toBe('A tela “Importação concluída!” mostra quantos contatos são novos.')
    // Ícones só de enfeite.
    for (const svg of c.findAll('svg')) expect(svg.attributes('aria-hidden')).toBe('true')
    // "Para ir além": sem número; "Só administrador" quando for o caso.
    const alem = cartao(w, 'ligar-sistema')
    expect(t(alem.get('h4').text())).toBe('Ligar o seu sistema')
    expect(alem.get('[data-numero]').text()).toBe('')
    expect(t(alem.get('[data-somente-admin]').text())).toBe('Só administrador')
    expect(t(cartao(w, 'ligar-envios').get('[data-somente-admin]').text())).toBe('Só administrador')
  })

  it('Onde: "Abrir <tela>" quando o perfil abre a tela; senão o aviso; sem atalho (ou com um que a tela não conhece), nada', async () => {
    entrar(['contatos.ver', 'importacao.usar'])
    let w = await abrirAjuda('/ajuda')
    const botao = cartao(w, 'cadastrar-clientes').get('[data-parada="onde"] a[data-atalho]')
    expect(t(botao.text())).toBe('Abrir Importar contatos')
    expect(botao.attributes('href')).toBe('/contatos/importar')
    expect(cartao(w, 'cadastrar-clientes').find('[data-sem-acesso]').exists()).toBe(false)
    const AVISO = 'Seu perfil não abre esta tela. Peça acesso a um administrador.'
    for (const id of ['ligar-envios', 'enviar-pesquisa', 'ligar-sistema']) {
      expect(cartao(w, id).find('[data-atalho]').exists(), id).toBe(false)
      expect(t(cartao(w, id).get('[data-sem-acesso]').text()), id).toBe(AVISO)
    }
    expect(cartao(w, 'perguntar-toqqiai').find('[data-atalho]').exists()).toBe(false)
    expect(cartao(w, 'perguntar-toqqiai').find('[data-sem-acesso]').exists()).toBe(false)
    w.unmount()

    // O administrador com as permissões abre as telas dele.
    setActivePinia(createPinia())
    entrar(['configuracoes.gerenciar', 'envios.ver'], 'admin')
    w = await abrirAjuda('/ajuda')
    expect(t(cartao(w, 'ligar-envios').get('[data-atalho]').text())).toBe('Abrir Configurações de envio')
    expect(cartao(w, 'ligar-envios').get('[data-atalho]').attributes('href')).toBe('/configuracoes/envios')
    expect(cartao(w, 'enviar-pesquisa').get('[data-atalho]').attributes('href')).toBe('/envios')
    expect(cartao(w, 'ligar-sistema').get('[data-atalho]').attributes('href')).toBe('/integracoes')
    expect(t(cartao(w, 'cadastrar-clientes').get('[data-sem-acesso]').text())).toBe(AVISO)
    w.unmount()

    // Chave que a tela não conhece: nem botão nem aviso.
    setActivePinia(createPinia())
    entrar([], 'admin')
    w = await abrirAjuda('/ajuda', { ...AJUDA, jornadas: [{ ...JORNADAS[0], atalho: 'tela_nova' }] })
    expect(cartao(w, 'cadastrar-clientes').find('[data-atalho]').exists()).toBe(false)
    expect(cartao(w, 'cadastrar-clientes').find('[data-sem-acesso]').exists()).toBe(false)
  })

  it('rodapé: "Saiba mais" com as seções que existem (vão ao tópico com a âncora) e "Próxima jornada" só no ciclo, menos na última', async () => {
    entrar(['contatos.ver'])
    const w = await abrirAjuda('/ajuda/jornadas')
    const saiba = cartao(w, 'cadastrar-clientes').get('footer ul')
    expect(t(w.get(`#${saiba.attributes('aria-labelledby')}`).text())).toBe('Saiba mais:')
    expect(saiba.findAll('a').map((a) => [t(a.text()), a.attributes('href')])).toEqual([
      ['Importar uma planilha', '/ajuda/contatos#importar-planilha'],
      ['Grupos de contatos', '/ajuda/contatos#grupos'],
    ])
    expect(cartao(w, 'ligar-envios').findAll('[data-saiba-mais]').map((a) => a.attributes('href'))).toEqual([
      '/ajuda/configuracoes#notificacoes',
      '/ajuda/contatos#grupos',
    ])
    const proxima = cartao(w, 'cadastrar-clientes').get('a[data-proxima]')
    expect(t(proxima.text())).toBe('Próxima jornada: Ligar os envios')
    expect(proxima.attributes('href')).toBe('/ajuda/jornadas#ligar-envios')
    expect(cartao(w, 'ligar-envios').get('a[data-proxima]').attributes('href')).toBe('/ajuda/jornadas#enviar-pesquisa')
    // Última do ciclo, sem referência que exista: sem rodapé.
    expect(cartao(w, 'enviar-pesquisa').find('[data-proxima]').exists()).toBe(false)
    expect(cartao(w, 'enviar-pesquisa').find('footer').exists()).toBe(false)
    // "Para ir além": "Saiba mais" sem "Próxima jornada".
    expect(cartao(w, 'perguntar-toqqiai').find('[data-proxima]').exists()).toBe(false)
    expect(cartao(w, 'perguntar-toqqiai').get('[data-saiba-mais]').attributes('href')).toBe('/ajuda/primeiros-passos#visao-geral')
    // "Saiba mais" abre o tópico e leva à seção.
    await cartao(w, 'cadastrar-clientes').get('[data-saiba-mais="contatos#grupos"]').trigger('click')
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda/contatos#grupos')
    expect(w.get('[data-topico-aberto]').attributes('data-topico-aberto')).toBe('contatos')
    expect(focado()).toBe('t-ajuda-grupos')
  })

  it('âncora /ajuda/jornadas#<id>: rola até o cartão e põe o foco no título; o mapa e a "Próxima jornada" também (mesmo se o endereço já é esse)', async () => {
    entrar(['contatos.ver'])
    const w = await abrirAjuda('/ajuda/jornadas#ligar-envios')
    expect(focado()).toBe('t-ajuda-ligar-envios')
    expect((rolou.mock.contexts.at(-1) as Element).id).toBe('ajuda-ligar-envios')
    // Bloco do mapa.
    await w.get('a[data-mapa-jornada="perguntar-toqqiai"]').trigger('click')
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda/jornadas#perguntar-toqqiai')
    expect(focado()).toBe('t-ajuda-perguntar-toqqiai')
    expect((rolou.mock.contexts.at(-1) as Element).id).toBe('ajuda-perguntar-toqqiai')
    // O mesmo bloco de novo, com o endereço igual: o router não muda, mas a tela leva ao cartão.
    w.get<HTMLInputElement>('input[data-busca-ajuda]').element.focus()
    rolou.mockClear()
    await w.get('a[data-mapa-jornada="perguntar-toqqiai"]').trigger('click')
    await flushPromises()
    expect(focado()).toBe('t-ajuda-perguntar-toqqiai')
    expect(rolou).toHaveBeenCalled()
    // "Próxima jornada".
    await cartao(w, 'cadastrar-clientes').get('a[data-proxima]').trigger('click')
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda/jornadas#ligar-envios')
    expect(focado()).toBe('t-ajuda-ligar-envios')
    // Voltar no histórico também leva ao cartão.
    router.back()
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda/jornadas#perguntar-toqqiai')
    expect(focado()).toBe('t-ajuda-perguntar-toqqiai')
  })
})

describe('menu da Ajuda', () => {
  it('"Jornadas" é o primeiro item, acima do rótulo "Tópicos", marcado em /ajuda e /ajuda/jornadas sem busca', async () => {
    entrar([])
    const w = await abrirAjuda('/ajuda')
    const nav = w.get('nav[aria-label="Tópicos da ajuda"]')
    const links = nav.findAll('a')
    expect(links.map((a) => [t(a.text()), a.attributes('href')])).toEqual([
      ['Jornadas', '/ajuda/jornadas'],
      ['Primeiros passos', '/ajuda/primeiros-passos'],
      ['Contatos', '/ajuda/contatos'],
      ['Configurações', '/ajuda/configuracoes'],
      ['Integrações', '/ajuda/integracoes'],
      ['Minha conta', '/ajuda/minha-conta'],
    ])
    // O rótulo "Tópicos" fica entre "Jornadas" e o primeiro tópico (é a primeira pílula no celular: o mesmo item da lista).
    const rotulo = nav.findAll('p').find((p) => t(p.text()) === 'Tópicos')!
    expect(links[0]!.element.compareDocumentPosition(rotulo.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(rotulo.element.compareDocumentPosition(links[1]!.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(nav.get('ul > li:first-child a').attributes('href')).toBe('/ajuda/jornadas')
    expect(links[0]!.get('svg').attributes('aria-hidden')).toBe('true')
    expect(nav.findAll('[aria-current="page"]').map((a) => t(a.text()))).toEqual(['Jornadas'])
    // Com busca, nada marcado; sem ela, de novo.
    await w.get<HTMLInputElement>('input[data-busca-ajuda]').setValue('senha')
    expect(nav.find('[aria-current]').exists()).toBe(false)
    await w.get<HTMLInputElement>('input[data-busca-ajuda]').setValue('')
    await router.push('/ajuda/jornadas')
    await flushPromises()
    expect(nav.findAll('[aria-current="page"]').map((a) => t(a.text()))).toEqual(['Jornadas'])
    // Num tópico, o tópico.
    await router.push('/ajuda/contatos')
    await flushPromises()
    expect(nav.findAll('[aria-current="page"]').map((a) => t(a.text()))).toEqual(['Contatos'])
  })

  it('escolher "Jornadas" no menu (num tópico, no celular) abre a página e põe o foco no título dela', async () => {
    tela(false)
    entrar([])
    const w = await abrirAjuda('/ajuda/minha-conta')
    await w.get<HTMLInputElement>('input[data-busca-ajuda]').setValue('senha')
    await w.get('a[data-topico="jornadas"]').trigger('click')
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda/jornadas')
    expect(w.get<HTMLInputElement>('input[data-busca-ajuda]').element.value).toBe('')
    expect(w.find('[data-pagina-jornadas]').exists()).toBe(true)
    expect(focado()).toBe('t-topico')
    expect(t(document.activeElement!.textContent ?? '')).toBe('Jornadas')
    expect((rolou.mock.contexts.at(-1) as Element).id).toBe('t-topico')
  })
})

describe('chamada no topo do tópico', () => {
  it('aparece no tópico da primeira referência da jornada, com o título, o objetivo e "Ver a jornada", que leva ao cartão', async () => {
    entrar(['contatos.ver'])
    const w = await abrirAjuda('/ajuda/contatos')
    const chamadas = w.findAll('[data-chamada-jornada]')
    expect(chamadas.map((c) => c.attributes('data-chamada-jornada'))).toEqual(['cadastrar-clientes'])
    const c = chamadas[0]!
    expect(textoVisto(c.get('[data-chamada-titulo]').element)).toBe('Jornada · Cadastrar seus clientes')
    expect(textoLido(c.get('[data-chamada-titulo]').element)).toBe('Jornada: Cadastrar seus clientes')
    expect(t(c.text())).toContain('Trazer sua lista de clientes para o Toqqi.')
    const link = c.get('a[data-ver-jornada]')
    expect(t(link.text())).toBe('Ver a jornada: Cadastrar seus clientes')
    expect(link.attributes('href')).toBe('/ajuda/jornadas#cadastrar-clientes')
    for (const svg of c.findAll('svg')) expect(svg.attributes('aria-hidden')).toBe('true')
    // Logo abaixo do cabeçalho do tópico, antes das seções.
    const cabecalho = w.get('[data-topico-aberto] > header').element
    const primeiraSecao = w.get('[data-secao]').element
    expect(cabecalho.compareDocumentPosition(c.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(c.element.compareDocumentPosition(primeiraSecao) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await link.trigger('click')
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda/jornadas#cadastrar-clientes')
    expect(w.find('[data-pagina-jornadas]').exists()).toBe(true)
    expect(focado()).toBe('t-ajuda-cadastrar-clientes')
    expect((rolou.mock.contexts.at(-1) as Element).id).toBe('ajuda-cadastrar-clientes')
  })

  it('em nenhum outro tópico: só a do tópico "dono"; tópico sem jornada, nenhuma', async () => {
    entrar([])
    const w = await abrirAjuda('/ajuda/configuracoes')
    const ids = () => w.findAll('[data-chamada-jornada]').map((c: DOMWrapper<Element>) => c.attributes('data-chamada-jornada'))
    // "Ligar os envios" cita Contatos na segunda referência, mas é de Configurações.
    expect(ids()).toEqual(['ligar-envios'])
    for (const [topico, esperado] of [
      ['contatos', ['cadastrar-clientes']],
      ['primeiros-passos', ['perguntar-toqqiai']],
      ['integracoes', ['ligar-sistema']],
      ['minha-conta', []],
    ] as const) {
      await router.push(`/ajuda/${topico}`)
      await flushPromises()
      expect(ids(), topico).toEqual(esperado)
    }
  })
})

describe('conteúdo sem jornadas', () => {
  it('igual a antes: /ajuda abre o primeiro tópico, sem "Jornadas" no menu nem chamadas; /ajuda/jornadas volta para /ajuda', async () => {
    entrar(['contatos.ver'])
    const w = await abrirAjuda('/ajuda', SEM_JORNADAS)
    expect(w.find('[data-pagina-jornadas]').exists()).toBe(false)
    expect(w.get('[data-topico-aberto]').attributes('data-topico-aberto')).toBe('primeiros-passos')
    const nav = w.get('nav[aria-label="Tópicos da ajuda"]')
    expect(nav.findAll('a').map((a) => t(a.text()))).toEqual(['Primeiros passos', 'Contatos', 'Configurações', 'Integrações', 'Minha conta'])
    expect(nav.get('a[aria-current="page"]').text()).toBe('Primeiros passos')
    // O rótulo "Tópicos" continua antes da lista, como era.
    expect(t(nav.element.firstElementChild!.textContent ?? '')).toBe('Tópicos')
    expect(w.find('[data-chamada-jornada]').exists()).toBe(false)
    w.unmount()

    setActivePinia(createPinia())
    entrar(['contatos.ver'])
    const w2 = await abrirAjuda('/ajuda/jornadas#cadastrar-clientes', SEM_JORNADAS)
    await flushPromises()
    expect(caminhoAtual()).toBe('/ajuda')
    expect(w2.get('[data-topico-aberto]').attributes('data-topico-aberto')).toBe('primeiros-passos')
    // A busca acha só seções, como antes.
    await w2.get<HTMLInputElement>('input[data-busca-ajuda]').setValue('excel')
    expect(w2.findAll('[data-resultado]').map((a) => a.attributes('data-resultado'))).toEqual(['contatos#importar-planilha'])
    expect(t(w2.get('p.sr-only[role="status"]').text())).toBe('1 seção encontrada')
  })

  it('jornadas todas malformadas contam como nenhuma', async () => {
    entrar([])
    const w = await abrirAjuda('/ajuda', { ...AJUDA, jornadas: [{ id: 'x', titulo: 'Sem onde', como: ['Um.'], resultado: 'Fim.' }] })
    expect(w.find('[data-pagina-jornadas]').exists()).toBe(false)
    expect(w.get('[data-topico-aberto]').attributes('data-topico-aberto')).toBe('primeiros-passos')
    expect(w.find('a[data-topico="jornadas"]').exists()).toBe(false)
  })
})
