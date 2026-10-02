// Aceite dos Termos de uso e da Política de privacidade (docs/api-aceite-lgpd.md §3): guarda de rotas e "de" seguro,
// texto de versão nova, desenho de um DocumentoLegal (seção, lista, tabela e links, sem v-html), a tela "Antes de
// continuar" (botão desabilitado até marcar, chamada com a versão, 409, erro de rede, Sair), Minha conta e Auditoria.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { Aceite } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { router as rotasDoApp, rolagemAoNavegar } from '@/router'
import { complementoRetirarAceite, destinoDepoisDoAceite, redirecionarAceite, textoAbertura, textoAceiteRegistrado, textoVersao } from '@/modulos/geral/legal/aceite'
import { idDaAncora, tipoDeLink } from '@/modulos/geral/legal/documento'
import type { DocumentoLegal } from '@/modulos/geral/legal/tipos'
import { VERSAO_DOCUMENTOS } from '@/modulos/geral/legal/versao'
import { rotuloEventoAuditoria } from '@/utils/rotulos'
import { destinoSeguro } from '@/utils/validacao'
import AceiteView from '@/modulos/geral/AceiteView.vue'
import DocumentoLegalView from '@/modulos/geral/DocumentoLegalView.vue'
import SecaoPrivacidade from '@/modulos/conta/SecaoPrivacidade.vue'
import DialogoConfirmacao from '@/components/ui/DialogoConfirmacao.vue'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { avisos } from '@/composables/avisos'
import { apiFalsa } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

const PENDENTE: Aceite = { versao_atual: 1, versao_aceita: null, aceito_em: null, pendente: true }
const EM_DIA: Aceite = { versao_atual: 1, versao_aceita: 1, aceito_em: '2026-10-02T13:45:00Z', pendente: false }

function entrar(aceite: Aceite | undefined, permissoes: string[] = ['contatos.ver', 'auditoria.ver']) {
  const s = useSessaoStore()
  s.definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 7, nome: 'Ana', email: 'ana@sol.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false, aceite },
      conta: { id: 3, nome: 'Sol', plano: 'profissional', situacao: 'ativa', teste_ate: null },
      permissoes: permissoes as never,
    },
    false,
  )
  s.inicializada = true // a guarda não busca /eu de novo
  return s
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  sessionStorage.clear()
  Element.prototype.scrollIntoView = vi.fn() as unknown as Element['scrollIntoView']
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('"de" seguro', () => {
  it('aceita só caminho interno', () => {
    expect(destinoDepoisDoAceite('/contatos?pagina=2#x')).toBe('/contatos?pagina=2#x')
    expect(destinoDepoisDoAceite('/relatorios/temas')).toBe('/relatorios/temas')
  })
  it('qualquer outra coisa vira /inicio', () => {
    for (const ruim of [undefined, null, '', 'contatos', '//mal.com', '/a//b', 'https://mal.com', '/\\mal.com', 'javascript:alert(1)', '/aceite', '/aceite?de=/x', ['/contatos']]) {
      expect(destinoDepoisDoAceite(ruim)).toBe('/inicio')
    }
  })
  it('a mesma regra (a mais estrita) vale para o "voltar" de Entrar', () => {
    for (const ruim of ['//mal.com', '/a//b', '/\\mal.com', '/x\u0000y', 'https://mal.com', undefined]) {
      expect(destinoSeguro(ruim)).toBe('/inicio')
    }
    expect(destinoSeguro('/contatos?pagina=2#x')).toBe('/contatos?pagina=2#x')
    expect(destinoSeguro('/aceite')).toBe('/aceite') // só o aceite recusa a si mesmo
  })
})

describe('guarda de rotas do aceite', () => {
  const rota = (fullPath: string, logado = true) => ({ path: fullPath.split(/[?#]/)[0]!, fullPath, meta: { logado } })

  it('pendente: página do app vai para /aceite com o caminho em "de"', () => {
    expect(redirecionarAceite(rota('/contatos?pagina=2'), { logado: true, aceite: PENDENTE })).toEqual({ path: '/aceite', query: { de: '/contatos?pagina=2' } })
    expect(redirecionarAceite(rota('/inicio'), { logado: true, aceite: PENDENTE })).toEqual({ path: '/aceite', query: {} })
  })

  it('pendente: as rotas livres ficam livres (mesmo com meta.logado)', () => {
    for (const livre of ['/aceite', '/termos', '/privacidade', '/confirmar-email', '/redefinir-senha', '/assinatura']) {
      expect(redirecionarAceite(rota(livre), { logado: true, aceite: PENDENTE })).toBeNull()
    }
    expect(redirecionarAceite(rota('/privacidade#cookies', false), { logado: true, aceite: PENDENTE })).toBeNull()
  })

  it('sem pendência: segue, e /aceite vai para /inicio', () => {
    expect(redirecionarAceite(rota('/contatos'), { logado: true, aceite: EM_DIA })).toBeNull()
    expect(redirecionarAceite(rota('/aceite'), { logado: true, aceite: EM_DIA })).toEqual({ path: '/inicio' })
    // Sessão sem o campo (API antiga): não bloqueia.
    expect(redirecionarAceite(rota('/contatos'), { logado: true, aceite: undefined })).toBeNull()
  })

  it('sem login, a guarda do aceite não age', () => {
    expect(redirecionarAceite(rota('/contatos'), { logado: false, aceite: undefined })).toBeNull()
  })

  it('no router do app: pendente vai para /aceite?de=; em dia, /aceite vai para /inicio', async () => {
    apiFalsa({ 'GET /ajuda': () => ({ versao: 1, topicos: [] }) })
    entrar(PENDENTE)
    await rotasDoApp.push('/contatos?busca=ana')
    expect(rotasDoApp.currentRoute.value.path).toBe('/aceite')
    expect(rotasDoApp.currentRoute.value.query.de).toBe('/contatos?busca=ana')
    await rotasDoApp.push('/privacidade#cookies')
    expect(rotasDoApp.currentRoute.value.path).toBe('/privacidade')

    useSessaoStore().atualizarAceite(EM_DIA)
    await rotasDoApp.push('/aceite')
    expect(rotasDoApp.currentRoute.value.path).toBe('/inicio')
    expect(rotasDoApp.resolve('/aceite').meta.titulo).toBe('Termos e privacidade')
  })

  it('no router do app: pendente com assinatura.gerenciar abre /assinatura; o resto do menu volta ao aceite', async () => {
    apiFalsa({ 'GET /ajuda': () => ({ versao: 1, topicos: [] }) })
    entrar({ ...EM_DIA, versao_atual: 2, pendente: true }, ['contatos.ver', 'assinatura.gerenciar'])
    await rotasDoApp.push('/assinatura')
    expect(rotasDoApp.currentRoute.value.path).toBe('/assinatura')
    await rotasDoApp.push('/contatos')
    expect(rotasDoApp.currentRoute.value.fullPath).toBe('/aceite?de=/contatos')
  })

  it('no router do app: sem assinatura.gerenciar, /assinatura continua barrada pela permissão', async () => {
    apiFalsa({ 'GET /ajuda': () => ({ versao: 1, topicos: [] }) })
    entrar(PENDENTE, ['contatos.ver'])
    await rotasDoApp.push('/assinatura')
    // a permissão manda para /inicio, e /inicio (pendente) manda para o aceite
    expect(rotasDoApp.currentRoute.value.path).toBe('/aceite')
  })

  it('/assinatura com aceite pendente monta o AppLayout (menu e assistente) e o menu para outra tela volta ao aceite', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }))
    const api = apiFalsa({
      'GET /ajuda': () => ({ versao: 1, topicos: [] }),
      'GET /assistente': () => ({ disponivel: true, motivo: null, cota: { usadas: 0, limite: 500, restantes: 500, mes: '2026-10' }, sugestoes: [] }),
      'GET /assinatura': () => new Response(JSON.stringify({ erro: { codigo: 'x', mensagem: 'Falhou.' } }), { status: 500 }),
    })
    entrar({ ...EM_DIA, versao_atual: 2, pendente: true }, ['contatos.ver', 'assinatura.gerenciar'])
    await rotasDoApp.push('/assinatura')
    const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [rotasDoApp] }, attachTo: document.body })
    await flushPromises()
    expect(rotasDoApp.currentRoute.value.path).toBe('/assinatura')
    expect(w.find('main#conteudo').exists()).toBe(true)
    expect(w.find('button[aria-label="Abrir menu"]').exists()).toBe(true)
    expect(w.find('button[data-botao-assistente]').exists()).toBe(true)
    expect(api.chamadas.some((c) => c.caminho === '/assinatura')).toBe(true)
    // um link do menu lateral leva a outra tela: a guarda manda de volta ao aceite
    await w.get('aside a[href="/contatos"]').trigger('click')
    await flushPromises()
    expect(rotasDoApp.currentRoute.value.fullPath).toBe('/aceite?de=/contatos')
  })

  it('/privacidade#cookies: o router não rola (a tela vai até a seção)', () => {
    const para = { path: '/privacidade', name: 'privacidade', hash: '#cookies', meta: { ancoras: true } }
    expect(rolagemAoNavegar(para, { path: '/aceite', name: 'aceite' }, null)).toBe(false)
    expect(rolagemAoNavegar({ ...para, hash: '' }, { path: '/aceite', name: 'aceite' }, null)).toEqual({ top: 0 })
  })
})

describe('textos', () => {
  it('primeira vez x versão nova (com a data da versão)', () => {
    expect(textoAbertura(PENDENTE)).toBe('Para usar o Toqqi, leia e aceite os Termos de uso e a Política de privacidade.')
    expect(textoAbertura({ versao_atual: 2, versao_aceita: 1, aceito_em: '2026-01-01T12:00:00Z', pendente: true }, '2027-03-15')).toBe(
      'Atualizamos os Termos de uso e a Política de privacidade em 15/03/2027.',
    )
  })

  it('versão do documento e o aceite em Minha conta', () => {
    expect(textoVersao(1, '2026-10-02')).toBe('Versão 1 · vigente desde 02/10/2026')
    expect(textoAceiteRegistrado(EM_DIA, () => '02/10/2026 às 10:45')).toBe(
      'Você aceitou os Termos de uso e a Política de privacidade (versão 1) em 02/10/2026 às 10:45.',
    )
    expect(textoAceiteRegistrado(PENDENTE, () => 'x')).toMatch(/Ainda não há registro/)
  })

  it('Auditoria: usa o rótulo da API e acrescenta "no cadastro" quando a origem é o cadastro', () => {
    // o rótulo que a API manda (ROTULOS em api/toqqi/core/auditoria.py)
    const rotulo = /"termos_aceitos":\s*"([^"]+)"/.exec(readFileSync(join(__dirname, '../../api/toqqi/core/auditoria.py'), 'utf8'))?.[1]
    expect(rotulo).toBe('Aceitou os termos e a política de privacidade')
    expect(rotuloEventoAuditoria({ evento: 'termos_aceitos', rotulo: rotulo!, detalhe: { versao: 1 } })).toBe(rotulo)
    expect(rotuloEventoAuditoria({ evento: 'termos_aceitos', rotulo: rotulo!, detalhe: { versao: 1, origem: 'cadastro' } })).toBe(
      'Aceitou os termos e a política de privacidade no cadastro',
    )
    expect(rotuloEventoAuditoria({ evento: 'termos_aceitos', rotulo: rotulo!, detalhe: { versao: 1, origem: 'tela' } })).toBe(rotulo)
    expect(rotuloEventoAuditoria({ evento: 'login_ok', rotulo: 'Entrou no sistema', detalhe: null })).toBe('Entrou no sistema')
  })

  it('links: interno, e-mail, externo e o resto não vira link', () => {
    expect(tipoDeLink('/termos')).toBe('interno')
    expect(tipoDeLink('/privacidade#cookies')).toBe('interno')
    expect(tipoDeLink('mailto:privacidade@toqqi.com')).toBe('email')
    expect(tipoDeLink('https://www.gov.br/anpd')).toBe('externo')
    expect(tipoDeLink('//mal.com')).toBe('invalido')
    expect(tipoDeLink('javascript:alert(1)')).toBe('invalido')
    expect(tipoDeLink('http://inseguro.com')).toBe('invalido')
    expect(idDaAncora('#cookies')).toBe('cookies')
    expect(idDaAncora('#%E2%9C%93')).toBe('✓')
    expect(idDaAncora('')).toBe('')
  })
})

const DOC: DocumentoLegal = {
  titulo: 'Política de teste',
  introducao: [{ tipo: 'p', texto: ['Vale junto com os ', { texto: 'Termos de uso', href: '/termos' }, '.'] }],
  secoes: [
    {
      id: 'direitos',
      titulo: 'Seus direitos',
      blocos: [
        { tipo: 'p', texto: 'Você pode pedir:' },
        { tipo: 'lista', itens: ['Acesso.', ['Correção, por ', { texto: 'privacidade@toqqi.com', href: 'mailto:privacidade@toqqi.com' }, '.']] },
      ],
    },
    {
      id: 'cookies',
      titulo: 'Cookies e armazenamento no navegador',
      blocos: [
        { tipo: 'tabela', colunas: ['Nome', 'Para que serve'], linhas: [['toqqi.tema', 'Tema claro ou escuro.'], ['toqqi.sessao', ['Sessão. Veja a ', { texto: 'ANPD', href: 'https://www.gov.br/anpd' }]]] },
        { tipo: 'p', texto: ['<b>sem html</b> ', { texto: 'ruim', href: 'javascript:alert(1)' }] },
      ],
    },
  ],
}

let router: Router
async function abrir(componente: unknown, caminho: string, props: Record<string, unknown> = {}): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/aceite', component: componente as never, props },
      { path: '/privacidade', component: componente as never, props },
      { path: '/minha-conta', component: componente as never, props },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', { 'data-outra': '' }, 'outra página') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

describe('DocumentoLegalView', () => {
  it('título, versão, sumário com links, seções com âncora, lista, tabela e links certos', async () => {
    const w = await abrir(DocumentoLegalView, '/privacidade', { tipo: 'privacidade', documento: DOC })
    expect(t(w.get('h1').text())).toBe('Política de teste')
    expect(w.get('[data-teste="versao"]').text()).toMatch(new RegExp(`^Versão ${VERSAO_DOCUMENTOS} · vigente desde \\d{2}/\\d{2}/\\d{4}$`))

    const sumario = w.get('nav[aria-labelledby="sumario"]')
    expect(sumario.findAll('a').map((a) => [t(a.text()), a.attributes('href')])).toEqual([
      ['Seus direitos', '/privacidade#direitos'],
      ['Cookies e armazenamento no navegador', '/privacidade#cookies'],
    ])
    expect(w.get('section#direitos h2').text()).toBe('1. Seus direitos')
    expect(w.get('section#cookies h2').attributes('id')).toBe('t-cookies')

    expect(w.findAll('section#direitos ul li').map((li) => t(li.text()))).toEqual(['Acesso.', 'Correção, por privacidade@toqqi.com.'])
    // Interno = RouterLink (href do router); e-mail e outro site = <a> comum, o externo em nova aba.
    expect(w.get('a[href="/termos"]').text()).toBe('Termos de uso')
    expect(w.get('a[href="mailto:privacidade@toqqi.com"]').attributes('target')).toBeUndefined()
    const anpd = w.findAll('a[href="https://www.gov.br/anpd"]')
    expect(anpd.length).toBeGreaterThan(0)
    expect(anpd[0]!.attributes('target')).toBe('_blank')
    expect(anpd[0]!.attributes('rel')).toContain('noopener')

    // Tabela: no computador <table> com cabeçalho; no celular, um cartão por linha com os nomes das colunas.
    expect(w.findAll('table thead th').map((th) => th.text())).toEqual(['Nome', 'Para que serve'])
    expect(w.findAll('table tbody tr')).toHaveLength(2)
    expect(w.get('table tbody tr th[scope="row"]').text()).toBe('toqqi.tema')
    const cartoes = w.findAll('[data-teste="tabela-celular"] > li')
    expect(cartoes).toHaveLength(2)
    expect(cartoes[0]!.findAll('dt').map((d) => d.text())).toEqual(['Nome', 'Para que serve'])

    // Texto puro: nada de HTML interpretado nem link "javascript:".
    expect(w.text()).toContain('<b>sem html</b>')
    expect(w.find('b').exists()).toBe(false)
    expect(w.find('a[href^="javascript"]').exists()).toBe(false)
  })

  it('/privacidade#cookies rola até a seção ao abrir', async () => {
    const rolou = vi.fn()
    Element.prototype.scrollIntoView = rolou as unknown as Element['scrollIntoView']
    await abrir(DocumentoLegalView, '/privacidade#cookies', { tipo: 'privacidade', documento: DOC })
    await flushPromises()
    expect(rolou).toHaveBeenCalled()
    expect((rolou.mock.contexts[0] as HTMLElement).id).toBe('cookies')
    expect(document.activeElement?.id).toBe('t-cookies')
  })

  it('os documentos de verdade têm a seção de cookies e nenhum v-html nas telas', async () => {
    const w = await abrir(DocumentoLegalView, '/privacidade', { tipo: 'privacidade' })
    expect(w.find('section#cookies').exists()).toBe(true)
    for (const arq of ['DocumentoLegalView.vue', 'AceiteView.vue', 'legal/TextoLegal.vue']) {
      expect(readFileSync(join(__dirname, '../src/modulos/geral', arq), 'utf8')).not.toMatch(/\sv-html=/)
    }
  })
})

describe('tela "Antes de continuar"', () => {
  const botao = (w: VueWrapper, teste: string) => w.get<HTMLButtonElement>(`[data-teste="${teste}"]`)

  it('mostra o texto, os itens, o aviso de cookies; o botão só funciona depois de marcar; aceita com a versão e vai para "de"', async () => {
    entrar(PENDENTE)
    const api = apiFalsa({ 'POST /eu/aceite': () => EM_DIA })
    const w = await abrir(AceiteView, '/aceite?de=/contatos%3Fpagina%3D2')
    expect(t(w.get('h1').text())).toBe('Antes de continuar')
    expect(t(w.get('[data-teste="abertura"]').text())).toMatch(/^Para usar o Toqqi, leia e aceite/)
    expect(w.findAll('ul li')).toHaveLength(3)
    expect(w.find('a[href="mailto:privacidade@toqqi.com"]').exists()).toBe(true)
    expect(w.text()).toContain('Por isso não há o que recusar.')
    expect(w.get('a[href="/privacidade#cookies"]').text()).toBe('Saiba mais')
    expect(w.get('a[href="/termos"]').attributes('target')).toBe('_blank')
    expect(w.get('a[href="/privacidade"]').attributes('target')).toBe('_blank')

    expect(botao(w, 'aceitar').element.disabled).toBe(true)
    await botao(w, 'aceitar').trigger('click')
    expect(api.chamadas).toHaveLength(0)

    await w.get('input[type="checkbox"]').setValue(true)
    expect(botao(w, 'aceitar').element.disabled).toBe(false)
    await botao(w, 'aceitar').trigger('click')
    await flushPromises()
    expect(api.chamadas.map((c) => [c.metodo, c.caminho, c.corpo])).toEqual([['POST', '/eu/aceite', { versao: VERSAO_DOCUMENTOS }]])
    expect(useSessaoStore().usuario?.aceite).toEqual(EM_DIA)
    expect(router.currentRoute.value.fullPath).toBe('/contatos?pagina=2')
  })

  it('"de" perigoso: vai para /inicio', async () => {
    entrar(PENDENTE)
    apiFalsa({ 'POST /eu/aceite': () => EM_DIA })
    const w = await abrir(AceiteView, '/aceite?de=//mal.com')
    await w.get('input[type="checkbox"]').setValue(true)
    await botao(w, 'aceitar').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/inicio')
  })

  it('versão nova: texto de atualização, com a data em que a versão 2 passou a valer', async () => {
    entrar({ versao_atual: 2, versao_aceita: 1, aceito_em: '2026-01-01T12:00:00Z', pendente: true })
    const w = await abrir(AceiteView, '/aceite')
    expect(t(w.get('[data-teste="abertura"]').text())).toMatch(/^Atualizamos os Termos de uso e a Política de privacidade em 02\/10\/2026\./)
  })

  it('409 com a API na mesma versão do site: recarrega /eu, desmarca e mostra o aviso; fica na tela', async () => {
    entrar({ versao_atual: VERSAO_DOCUMENTOS, versao_aceita: null, aceito_em: null, pendente: true })
    const api = apiFalsa({
      'POST /eu/aceite': () =>
        new Response(JSON.stringify({ erro: { codigo: 'versao_desatualizada', mensagem: 'Os termos foram atualizados. Recarregue a página para ver a versão nova.' } }), { status: 409 }),
      'GET /eu': () => ({
        usuario: { id: 7, nome: 'Ana', email: 'ana@sol.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false, aceite: { versao_atual: VERSAO_DOCUMENTOS, versao_aceita: null, aceito_em: null, pendente: true } },
        conta: { id: 3, nome: 'Sol', plano: 'profissional', situacao: 'ativa', teste_ate: null },
        permissoes: [],
      }),
    })
    const w = await abrir(AceiteView, '/aceite')
    await w.get('input[type="checkbox"]').setValue(true)
    await botao(w, 'aceitar').trigger('click')
    await flushPromises()
    expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['POST /eu/aceite', 'GET /eu'])
    expect(w.text()).toContain('Os termos foram atualizados.')
    expect(w.get<HTMLInputElement>('input[type="checkbox"]').element.checked).toBe(false)
    expect(botao(w, 'aceitar').element.disabled).toBe(true)
    expect(w.find('[data-teste="recarregar"]').exists()).toBe(false)
    expect(router.currentRoute.value.path).toBe('/aceite')
  })

  const ERRO_409 = () =>
    new Response(JSON.stringify({ erro: { codigo: 'versao_desatualizada', mensagem: 'Os termos foram atualizados. Recarregue a página para ver a versão nova.' } }), { status: 409 })
  const eu = (aceite: Aceite) => ({
    usuario: { id: 7, nome: 'Ana', email: 'ana@sol.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false, aceite },
    conta: { id: 3, nome: 'Sol', plano: 'profissional', situacao: 'ativa', teste_ate: null },
    permissoes: [],
  })

  it('manda sempre a versão do site, mesmo quando a sessão diz outra versão atual; depois de um 409 também', async () => {
    // A sessão (vinda da API) diz que a atual é a 2, mas o site mostra o texto da versão VERSAO_DOCUMENTOS.
    entrar({ versao_atual: VERSAO_DOCUMENTOS, versao_aceita: null, aceito_em: null, pendente: true })
    let primeira = true
    const api = apiFalsa({
      'POST /eu/aceite': () => (primeira ? ((primeira = false), ERRO_409()) : EM_DIA),
      // /eu volta com a mesma versão do site (o 409 foi por outro motivo, ex.: corrida)
      'GET /eu': () => eu({ versao_atual: VERSAO_DOCUMENTOS, versao_aceita: null, aceito_em: null, pendente: true }),
    })
    const w = await abrir(AceiteView, '/aceite')
    await w.get('input[type="checkbox"]').setValue(true)
    await botao(w, 'aceitar').trigger('click')
    await flushPromises()
    expect(w.find('[data-teste="recarregar"]').exists()).toBe(false)
    await w.get('input[type="checkbox"]').setValue(true)
    await botao(w, 'aceitar').trigger('click')
    await flushPromises()
    const enviados = api.chamadas.filter((c) => c.metodo === 'POST').map((c) => c.corpo)
    expect(enviados).toEqual([{ versao: VERSAO_DOCUMENTOS }, { versao: VERSAO_DOCUMENTOS }])
  })

  it('409 com a API numa versão maior que a do site: o botão vira "Recarregar a página", com a mensagem da API', async () => {
    entrar(PENDENTE)
    const api = apiFalsa({
      'POST /eu/aceite': ERRO_409,
      'GET /eu': () => eu({ versao_atual: VERSAO_DOCUMENTOS + 1, versao_aceita: null, aceito_em: null, pendente: true }),
    })
    const recarregar = vi.fn()
    const original = window.location
    Object.defineProperty(window, 'location', { configurable: true, value: { ...original, reload: recarregar } })
    try {
      const w = await abrir(AceiteView, '/aceite')
      await w.get('input[type="checkbox"]').setValue(true)
      await botao(w, 'aceitar').trigger('click')
      await flushPromises()
      expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['POST /eu/aceite', 'GET /eu'])
      expect(api.chamadas[0]!.corpo).toEqual({ versao: VERSAO_DOCUMENTOS })
      expect(w.text()).toContain('Os termos foram atualizados. Recarregue a página para ver a versão nova.')
      expect(w.find('[data-teste="aceitar"]').exists()).toBe(false)
      expect(t(botao(w, 'recarregar').text())).toBe('Recarregar a página')
      await botao(w, 'recarregar').trigger('click')
      expect(recarregar).toHaveBeenCalledOnce()
      expect(api.chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(1)
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: original })
    }
  })

  it('"Aceitar" fica desabilitado enquanto está saindo', async () => {
    entrar(PENDENTE)
    let soltar!: () => void
    const api = apiFalsa({ 'POST /auth/sair': () => new Promise<undefined>((r) => (soltar = () => r(undefined))), 'POST /eu/aceite': () => EM_DIA })
    const w = await abrir(AceiteView, '/aceite')
    router.addRoute({ path: '/entrar', name: 'entrar', component: { render: () => h('div', 'entrar') } })
    await w.get('input[type="checkbox"]').setValue(true)
    await botao(w, 'sair').trigger('click')
    await flushPromises()
    expect(botao(w, 'aceitar').element.disabled).toBe(true)
    await botao(w, 'aceitar').trigger('click')
    expect(api.chamadas.filter((c) => c.caminho === '/eu/aceite')).toHaveLength(0)
    soltar()
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/entrar')
  })

  it('versão nova + assinatura.gerenciar: linha "Não concorda?" com o link para cancelar', async () => {
    entrar({ versao_atual: 2, versao_aceita: 1, aceito_em: '2026-01-01T12:00:00Z', pendente: true }, ['assinatura.gerenciar'])
    const w = await abrir(AceiteView, '/aceite')
    expect(t(w.get('[data-teste="cancelar"]').text())).toBe('Não concorda? Você pode cancelar a assinatura.')
    expect(w.get('[data-teste="cancelar"] a').attributes('href')).toBe('/assinatura')
  })

  it('sem a linha de cancelar: primeira vez, ou sem a permissão', async () => {
    entrar(PENDENTE, ['assinatura.gerenciar'])
    let w = await abrir(AceiteView, '/aceite')
    expect(w.find('[data-teste="cancelar"]').exists()).toBe(false)
    w.unmount()
    setActivePinia(createPinia())
    entrar({ versao_atual: 2, versao_aceita: 1, aceito_em: '2026-01-01T12:00:00Z', pendente: true }, ['contatos.ver'])
    w = await abrir(AceiteView, '/aceite')
    expect(w.find('[data-teste="cancelar"]').exists()).toBe(false)
  })

  it('erro de rede: aviso na tela e o botão volta a funcionar', async () => {
    entrar(PENDENTE)
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    const w = await abrir(AceiteView, '/aceite')
    await w.get('input[type="checkbox"]').setValue(true)
    await botao(w, 'aceitar').trigger('click')
    await flushPromises()
    expect(w.find('[role="alert"]').exists()).toBe(true)
    expect(botao(w, 'aceitar').element.disabled).toBe(false)
    expect(router.currentRoute.value.path).toBe('/aceite')
  })

  it('Sair encerra a sessão e vai para Entrar', async () => {
    entrar(PENDENTE)
    const api = apiFalsa({ 'POST /auth/sair': () => undefined })
    const w = await abrir(AceiteView, '/aceite')
    router.addRoute({ path: '/entrar', name: 'entrar', component: { render: () => h('div', 'entrar') } })
    await botao(w, 'sair').trigger('click')
    await flushPromises()
    expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['POST /auth/sair'])
    expect(useSessaoStore().logado).toBe(false)
    expect(router.currentRoute.value.path).toBe('/entrar')
  })
})

describe('store: atualizarUsuario (PATCH /eu)', () => {
  it('mescla com o usuário atual e mantém o aceite quando a resposta não traz', () => {
    const s = entrar(PENDENTE)
    const { aceite: _, ...semAceite } = s.usuario!
    s.atualizarUsuario({ ...semAceite, cargo: 'Diretora' })
    expect(s.usuario?.cargo).toBe('Diretora')
    expect(s.usuario?.aceite).toEqual(PENDENTE)
    expect(JSON.parse(sessionStorage.getItem('toqqi.sessao')!).usuario.aceite).toEqual(PENDENTE)
  })

  it('quando a resposta traz o aceite, vale o da resposta', () => {
    const s = entrar(PENDENTE)
    s.atualizarUsuario({ ...s.usuario!, aceite: EM_DIA })
    expect(s.usuario?.aceite).toEqual(EM_DIA)
  })
})

describe('Minha conta: cartão Privacidade', () => {
  it('mostra a versão e a data do aceite e os dois links', async () => {
    entrar(EM_DIA)
    const w = await abrir(SecaoPrivacidade, '/minha-conta')
    expect(t(w.get('h2').text())).toBe('Privacidade')
    expect(t(w.get('[data-teste="aceite"]').text())).toMatch(
      /^Você aceitou os Termos de uso e a Política de privacidade \(versão 1\) em 02\/10\/2026 às 10:45\.$/,
    )
    expect(w.get('a[href="/termos"]').text()).toBe('Termos de uso')
    expect(w.get('a[href="/privacidade"]').text()).toBe('Política de privacidade')
  })
})

// ───────────── §5: retirar o aceite (Minha conta › Privacidade) e a abertura da tela depois de retirar ─────────────
describe('retirar o aceite', () => {
  // O cartão e o diálogo de confirmação do App (o mesmo componente que o site inteiro usa).
  const CartaoComDialogo = defineComponent({ render: () => [h(SecaoPrivacidade), h(DialogoConfirmacao)] })
  const MENSAGEM = 'Aceite retirado. Para voltar a usar o Toqqi, entre de novo e aceite os termos.'
  const SEM_ACEITE = 'Você não tem um aceite em vigor para retirar.'

  afterEach(() => {
    if (estadoConfirmacao.aberto) responderConfirmacao(false)
    avisos.splice(0)
  })

  function comPerfil(perfil: 'admin' | 'gestor' | 'consulta', permissoes: string[] = []) {
    const s = entrar(EM_DIA, permissoes)
    s.usuario = { ...s.usuario!, perfil }
    return s
  }

  async function abrirCartao() {
    const w = await abrir(CartaoComDialogo, '/minha-conta')
    router.addRoute({ path: '/entrar', name: 'entrar', component: { render: () => h('div', 'entrar') } })
    return w
  }
  const dialogo = () => document.querySelector<HTMLElement>('[role="alertdialog"]')
  const botaoDialogo = (rotulo: string) =>
    [...(dialogo()?.querySelectorAll('button') ?? [])].find((b) => t(b.textContent ?? '') === rotulo) as HTMLButtonElement

  it('o botão abre o diálogo com o título, o texto e os botões do contrato', async () => {
    comPerfil('gestor')
    const api = apiFalsa({})
    const w = await abrirCartao()
    expect(t(w.get('[data-teste="retirar-aceite"]').text())).toBe('Retirar meu aceite')
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(t(dialogo()!.querySelector('h2')!.textContent!)).toBe('Retirar o aceite?')
    expect(t(dialogo()!.textContent!)).toContain(
      'Você vai sair do Toqqi em todos os aparelhos. Para voltar a usar, será preciso aceitar os Termos de uso e a Política de privacidade de novo. O registro do seu aceite anterior continua guardado, como prova.',
    )
    expect(botaoDialogo('Retirar e sair')).toBeTruthy()
    expect(botaoDialogo('Cancelar')).toBeTruthy()
    expect(botaoDialogo('Retirar e sair').className).toContain('bg-red-700') // variante perigo
    expect(api.chamadas).toHaveLength(0)
  })

  it('a frase extra aparece só para o administrador', async () => {
    comPerfil('gestor', ['assinatura.gerenciar'])
    let w = await abrirCartao()
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    expect(document.querySelector('[data-teste="confirmacao-complemento"]')).toBeNull()
    expect(dialogo()!.textContent).not.toContain('único administrador')
    responderConfirmacao(false)
    w.unmount()

    setActivePinia(createPinia())
    comPerfil('admin', ['assinatura.gerenciar'])
    w = await abrirCartao()
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    expect(t(document.querySelector('[data-teste="confirmacao-complemento"]')!.textContent!)).toBe(
      'Se você for o único administrador, ninguém conseguirá mudar as configurações da conta até você voltar e aceitar. Para encerrar o uso do Toqqi pela empresa, cancele a assinatura.',
    )
  })

  it('o link para /assinatura só aparece com a permissão assinatura.gerenciar', async () => {
    comPerfil('admin', ['assinatura.gerenciar'])
    let w = await abrirCartao()
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    const link = document.querySelector<HTMLAnchorElement>('[data-teste="confirmacao-complemento"] a')!
    expect(link.getAttribute('href')).toBe('/assinatura')
    expect(t(link.textContent!)).toBe('cancele a assinatura')
    responderConfirmacao(false)
    w.unmount()

    setActivePinia(createPinia())
    comPerfil('admin', ['contatos.ver'])
    w = await abrirCartao()
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    expect(document.querySelector('[data-teste="confirmacao-complemento"]')).not.toBeNull()
    expect(document.querySelector('[data-teste="confirmacao-complemento"] a')).toBeNull()
    expect(complementoRetirarAceite(false, true)).toBeNull()
  })

  it('confirmar chama a rota com {confirmar: true}, limpa a sessão como o Sair e vai para Entrar com o aviso', async () => {
    const s = comPerfil('admin', ['assinatura.gerenciar'])
    const api = apiFalsa({ 'POST /eu/aceite/revogar': () => ({ mensagem: MENSAGEM }) })
    const w = await abrirCartao()
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    botaoDialogo('Retirar e sair').click()
    await flushPromises()
    expect(api.chamadas.map((c) => [c.metodo, c.caminho, c.corpo])).toEqual([['POST', '/eu/aceite/revogar', { confirmar: true }]])
    // A API já encerrou as sessões: não chama /auth/sair, só limpa o que está no navegador.
    expect(s.logado).toBe(false)
    expect(s.token).toBeNull()
    expect(sessionStorage.getItem('toqqi.sessao')).toBeNull()
    expect(localStorage.getItem('toqqi.sessao')).toBeNull()
    expect(router.currentRoute.value.path).toBe('/entrar')
    expect(avisos.map((a) => [a.tipo, a.mensagem])).toEqual([['sucesso', MENSAGEM]])
  })

  it('cancelar não chama a API e mantém a sessão', async () => {
    const s = comPerfil('admin')
    const api = apiFalsa({ 'POST /eu/aceite/revogar': () => ({ mensagem: MENSAGEM }) })
    const w = await abrirCartao()
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    botaoDialogo('Cancelar').click()
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(false)
    expect(api.chamadas).toHaveLength(0)
    expect(s.logado).toBe(true)
    expect(router.currentRoute.value.path).toBe('/minha-conta')
  })

  it('409: mostra a mensagem da API, recarrega /eu e continua logado', async () => {
    const s = comPerfil('gestor')
    const api = apiFalsa({
      'POST /eu/aceite/revogar': () =>
        new Response(JSON.stringify({ erro: { codigo: 'sem_aceite', mensagem: SEM_ACEITE } }), { status: 409 }),
      'GET /eu': () => ({
        usuario: { ...s.usuario!, aceite: { versao_atual: 1, versao_aceita: null, aceito_em: null, pendente: true, revogado_em: '2026-10-02T15:00:00Z' } },
        conta: s.conta,
        permissoes: [],
      }),
    })
    const w = await abrirCartao()
    await w.get('[data-teste="retirar-aceite"]').trigger('click')
    await flushPromises()
    botaoDialogo('Retirar e sair').click()
    await flushPromises()
    expect(api.chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['POST /eu/aceite/revogar', 'GET /eu'])
    expect(t(w.get('[data-teste="erro-retirar"]').text())).toBe(SEM_ACEITE)
    expect(s.logado).toBe(true)
    expect(s.usuario?.aceite?.revogado_em).toBe('2026-10-02T15:00:00Z')
    expect(w.find('[data-teste="retirar-aceite"]').exists()).toBe(false) // sem aceite em vigor, sem botão
    expect(router.currentRoute.value.path).toBe('/minha-conta')
  })

  it('tela de aceite depois de retirar: abertura com a data da retirada (o resto igual)', async () => {
    const revogado: Aceite = { versao_atual: 1, versao_aceita: null, aceito_em: null, pendente: true, revogado_em: '2026-10-02T15:00:00Z' }
    expect(textoAbertura(revogado)).toBe(
      'Você retirou o seu aceite em 02/10/2026. Para voltar a usar o Toqqi, leia e aceite os Termos de uso e a Política de privacidade.',
    )
    // revogado_em nulo ou ausente: como antes.
    expect(textoAbertura({ ...revogado, revogado_em: null })).toBe('Para usar o Toqqi, leia e aceite os Termos de uso e a Política de privacidade.')
    expect(textoAbertura(PENDENTE)).toBe('Para usar o Toqqi, leia e aceite os Termos de uso e a Política de privacidade.')

    entrar(revogado)
    const w = await abrir(AceiteView, '/aceite')
    expect(t(w.get('[data-teste="abertura"]').text())).toBe(
      'Você retirou o seu aceite em 02/10/2026. Para voltar a usar o Toqqi, leia e aceite os Termos de uso e a Política de privacidade. Eles explicam como tratamos os seus dados e os dos seus clientes, seguindo a LGPD.',
    )
    expect(w.findAll('ul li')).toHaveLength(3)
    expect(w.find('[data-teste="aceitar"]').exists()).toBe(true)
  })

  it('a Política e os Termos falam da retirada, com link para Minha conta', async () => {
    for (const tipo of ['privacidade', 'termos'] as const) {
      const w = await abrir(DocumentoLegalView, tipo === 'privacidade' ? '/privacidade' : '/aceite', { tipo })
      const link = w.findAll('a[href="/minha-conta"]')
      expect(link.length).toBeGreaterThan(0)
      expect(t(link[0]!.text())).toBe('Minha conta › Privacidade › Retirar meu aceite')
      w.unmount()
    }
    const w = await abrir(DocumentoLegalView, '/privacidade', { tipo: 'privacidade' })
    expect(t(w.get('section#finalidades-e-bases-legais').text())).toContain(
      'O aceite destes documentos não é um consentimento: ele registra que você conhece e concorda com as regras de uso do Toqqi, contratado pela sua empresa. Mesmo assim, você pode retirá-lo quando quiser em Minha conta › Privacidade › Retirar meu aceite. Ao retirar, você sai do Toqqi e só volta a usá-lo aceitando de novo; guardamos o registro do aceite anterior e da retirada como prova, pelo tempo descrito em Retenção, e você deixa de receber os e-mails do Toqqi. Retirar o aceite não apaga a sua conta nem os seus dados: para isso, veja Seus direitos. Para encerrar o uso pela empresa, o administrador cancela a assinatura.',
    )
  })
})
