// Etapa 5h com a API simulada (docs/api-etapa-5h.md §4 e §5): Plataforma em 4 abas (Visão geral em /plataforma, Contas,
// Parâmetros e Erros, com os endereços), a Visão geral (carregando, erro com "Tentar de novo", indicadores com o
// "sandbox", testes acabando com o e-mail para copiar e a ativação, tabela das contas com busca, filtro, ordem e a
// lista do celular) e Erros (vazio por período, carregando, erro, lista com a pilha sem HTML, filtros, resolver e
// reabrir, só superadmin).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { ContaVisao, ErroPlataforma, VisaoPlataforma } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { router as rotasDoApp } from '@/router'
import { useSessaoStore } from '@/stores/sessao'
import PlataformaView from '@/modulos/plataforma/PlataformaView.vue'
import { apiFalsa, type Chamada } from './apiFalsa'

const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
const AGORA = new Date('2026-10-04T15:00:00-03:00')

function entrar(superadmin = true) {
  const s = useSessaoStore()
  s.definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Marcelo', email: 'marcelo@toqqi.com', cargo: null, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, perfil: 'admin', superadmin },
      conta: { id: 1, nome: 'Toqqi', plano: 'profissional', situacao: 'cortesia', teste_ate: null, cobranca: { liberada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } },
      permissoes: [] as never,
    },
    false,
  )
  s.inicializada = true
}

// ── Dados ───────────────────────────────────────────────────────────────────

const ativacao = (n: number) => ({ contatos: n >= 1, envios_ligados: n >= 2, primeiro_envio: n >= 3, primeira_resposta: n >= 4 })

function conta(c: Partial<ContaVisao> & Pick<ContaVisao, 'id' | 'nome'>): ContaVisao {
  return {
    situacao: 'teste',
    plano: 'profissional',
    criada_em: '2026-09-20T12:00:00Z',
    teste_ate: '2026-10-04T12:00:00Z',
    ultimo_acesso: null,
    usuarios: 1,
    admin_email: null,
    contatos_ativos: 0,
    convites_30d: 0,
    respostas_30d: 0,
    respostas_total: 0,
    ativacao: ativacao(0),
    ia_analises_mes: 0,
    assinatura: null,
    ...c,
  }
}

const CONTAS: ContaVisao[] = [
  conta({ id: 2, nome: 'Alfa Distribuidora', admin_email: 'ana@alfa.com.br', criada_em: '2026-09-23T12:00:00Z', ultimo_acesso: '2026-10-03T12:00:00Z', contatos_ativos: 41, convites_30d: 12, respostas_30d: 8, respostas_total: 164, ativacao: ativacao(2), ia_analises_mes: 37 }),
  conta({ id: 3, nome: 'Beta Logística', admin_email: 'bia@beta.com.br', criada_em: '2026-10-02T12:00:00Z' }),
  conta({ id: 4, nome: 'Gama Foods', situacao: 'ativa', admin_email: 'gui@gama.com.br', criada_em: '2026-07-01T12:00:00Z', ultimo_acesso: '2026-10-04T10:00:00Z', respostas_30d: 30, respostas_total: 300, ativacao: ativacao(4), assinatura: { plano: 'profissional', valor: 349 } }),
  conta({ id: 5, nome: 'Delta Peças', situacao: 'pausada', admin_email: 'davi@delta.com.br', criada_em: '2026-06-01T12:00:00Z', ultimo_acesso: '2026-08-01T12:00:00Z', respostas_30d: 2, respostas_total: 50, ativacao: ativacao(4), assinatura: { plano: 'essencial', valor: '149.00' } }),
  conta({ id: 6, nome: 'Éta Ótica', situacao: 'teste_expirado', admin_email: 'eva@eta.com.br', criada_em: '2026-08-15T12:00:00Z', ultimo_acesso: '2026-09-01T12:00:00Z', ativacao: ativacao(1) }),
]

function visao(extra: Partial<VisaoPlataforma> = {}): VisaoPlataforma {
  return {
    gerado_em: '2026-10-04T18:00:00Z',
    totais: {
      contas: 5,
      por_situacao: { teste: 2, teste_expirado: 1, ativa: 1, atrasada: 0, pausada: 1, cancelada: 0, cortesia: 0 },
      pagantes: 2,
      receita_mensal: 498,
      ambiente: 'sandbox',
      novas_7d: 1,
      novas_30d: 3,
    },
    conversao: { de: '2026-08-05', ate: '2026-09-19', contas: 4, assinaram: 3, taxa: 0.75 },
    testes_acabando: [{ id: 2, nome: 'Alfa Distribuidora', email: 'ana@alfa.com.br', teste_ate: '2026-10-07T15:00:00Z', dias: 3, ultimo_acesso: '2026-10-03T12:00:00Z', ativacao: ativacao(2) }],
    contas: CONTAS,
    ...extra,
  }
}

function erro(e: Partial<ErroPlataforma> & Pick<ErroPlataforma, 'id'>): ErroPlataforma {
  return {
    origem: 'api',
    tipo: 'ZeroDivisionError',
    mensagem: 'division by zero',
    local: 'GET /api/v1/acoes/{acao_id}',
    pilha: 'obter (toqqi/modulos/acoes/servico.py:120)\nver (toqqi/modulos/acoes/rotas.py:47)',
    versao: 'a1b2c3d',
    ocorrencias: 12,
    primeira_em: '2026-10-01T12:00:00Z',
    ultima_em: '2026-10-04T17:32:00Z',
    ultimo_request_id: '4f9c2b7d0e1a4c3b9d8e7f6a5b4c3d2e',
    conta_id: 2,
    conta_nome: 'Alfa Distribuidora',
    resolvido_em: null,
    ...e,
  }
}

const ERROS: ErroPlataforma[] = [
  erro({ id: 1 }),
  erro({ id: 2, origem: 'site', tipo: 'TypeError', mensagem: 'Cannot read properties of undefined (reading …) <b>negrito</b>', local: '/contatos/:id', pilha: 'TypeError: x\nat Ue (/assets/index-B2x9kQ1z.js:12:345)', versao: 'local', ocorrencias: 1, ultimo_request_id: null, conta_id: 9, conta_nome: null }),
  erro({ id: 3, origem: 'tarefa', tipo: 'RuntimeError', mensagem: '', local: 'resumo', pilha: '', ocorrencias: 2, ultimo_request_id: null, conta_id: null, conta_nome: null }),
]

const erroApi = (status: number, codigo: string, mensagem: string) => new Response(JSON.stringify({ erro: { codigo, mensagem, campos: {} } }), { status })

function adiada<T>() {
  let resolver!: (v: T) => void
  const promessa = new Promise<T>((r) => (resolver = r))
  return { promessa, resolver }
}

// ── Montagem ────────────────────────────────────────────────────────────────

let router: Router
async function abrir(caminho: string) {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/plataforma/:aba(contas|parametros|erros)?', name: 'plataforma', component: PlataformaView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.body.querySelector<T>(sel)
const $$ = (sel: string) => Array.from(document.body.querySelectorAll<HTMLElement>(sel))
async function clicar(el: HTMLElement | null | undefined) {
  if (!el) throw new Error('Elemento não encontrado')
  el.click()
  await flushPromises()
}
async function escolher(el: HTMLElement | null, valor: string) {
  if (!(el instanceof HTMLSelectElement)) throw new Error('Lista não encontrada')
  el.value = valor
  el.dispatchEvent(new Event('change'))
  await flushPromises()
}
async function digitar(el: HTMLElement | null, valor: string) {
  if (!(el instanceof HTMLInputElement)) throw new Error('Campo não encontrado')
  el.value = valor
  el.dispatchEvent(new Event('input'))
  await flushPromises()
}
const botao = (texto: string, dentro: ParentNode = document.body) =>
  Array.from(dentro.querySelectorAll<HTMLElement>('button')).find((b) => t(b.textContent) === texto) ?? null
const chamadasDe = (api: { chamadas: Chamada[] }, metodo: string, caminho: string) => api.chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)
/** A lista de seleção pelo rótulo. */
function selecao(rotulo: string, dentro = document.body): HTMLSelectElement {
  const label = Array.from(dentro.querySelectorAll('label')).find((l) => t(l.textContent) === rotulo)
  return document.getElementById(label!.getAttribute('for')!) as HTMLSelectElement
}
const indicador = (chave: string) => $(`[data-indicador="${chave}"]`)!
/** Os pares da lista de dados (dt → dd) de um erro. */
const dadosDoErro = (el: HTMLElement) =>
  Object.fromEntries(Array.from(el.querySelectorAll('dl > div')).map((d) => [t(d.querySelector('dt')!.textContent), t(d.querySelector('dd')!.textContent)]))
const linhasTabela = () => $$('[data-tabela-contas] tbody tr')
const nomesTabela = () => linhasTabela().map((tr) => t(tr.querySelector('td p')!.textContent))

beforeEach(() => {
  setActivePinia(createPinia())
  avisos.splice(0)
  vi.useFakeTimers({ now: AGORA, toFake: ['Date'] })
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
enableAutoUnmount(afterEach)

// ── Abas ────────────────────────────────────────────────────────────────────

describe('Plataforma: quatro abas e os endereços', () => {
  it('/plataforma abre a Visão geral; cada aba tem o seu endereço e busca na primeira vez que abre', async () => {
    entrar()
    const api = apiFalsa({
      'GET /plataforma/visao': () => visao(),
      'GET /plataforma/erros': () => [],
      'GET /plataforma/contas': () => [],
    })
    await abrir('/plataforma')
    const abas = $$('[role="tab"]')
    expect(abas.map((a) => t(a.textContent))).toEqual(['Visão geral', 'Contas', 'Parâmetros', 'Erros'])
    expect(abas[0]!.getAttribute('aria-selected')).toBe('true')
    expect(chamadasDe(api, 'GET', '/plataforma/visao')).toHaveLength(1)
    expect(chamadasDe(api, 'GET', '/plataforma/erros')).toHaveLength(0)
    await clicar(abas[3])
    expect(router.currentRoute.value.path).toBe('/plataforma/erros')
    const [pedido] = chamadasDe(api, 'GET', '/plataforma/erros')
    expect(Object.fromEntries(pedido!.url.searchParams)).toEqual({ situacao: 'abertos', dias: '7' })
    await clicar($$('[role="tab"]')[1])
    expect(router.currentRoute.value.path).toBe('/plataforma/contas')
    expect(chamadasDe(api, 'GET', '/plataforma/contas')).toHaveLength(1)
    await clicar($$('[role="tab"]')[0])
    expect(router.currentRoute.value.path).toBe('/plataforma')
    expect(chamadasDe(api, 'GET', '/plataforma/visao')).toHaveLength(1) // a aba guarda o que tem
    // voltar no navegador: a aba acompanha o endereço
    await router.push('/plataforma/erros')
    await flushPromises()
    expect($$('[role="tab"]')[3]!.getAttribute('aria-selected')).toBe('true')
    expect(chamadasDe(api, 'GET', '/plataforma/erros')).toHaveLength(1)
  })

  it('as rotas do app: /plataforma/erros é da Plataforma (só superadmin); /plataforma/visao não existe', async () => {
    expect(rotasDoApp.resolve('/plataforma/erros').name).toBe('plataforma')
    expect(rotasDoApp.resolve('/plataforma/erros').meta).toMatchObject({ titulo: 'Plataforma', superadmin: true })
    expect(rotasDoApp.resolve('/plataforma').name).toBe('plataforma')
    expect(rotasDoApp.resolve('/plataforma/visao').name).toBe('nao-encontrada')
    entrar(false)
    apiFalsa({ 'GET /ajuda': () => ({ versao: 1, topicos: [] }) })
    await rotasDoApp.push('/plataforma/erros')
    expect(rotasDoApp.currentRoute.value.path).toBe('/inicio')
    expect(avisos.map((a) => a.mensagem)).toContain('Esta área é só para a equipe da plataforma Toqqi.')
  })
})

// ── Visão geral ─────────────────────────────────────────────────────────────

describe('Plataforma › Visão geral', () => {
  it('carregando, erro com "Tentar de novo" e depois os dados', async () => {
    entrar()
    const espera = adiada<Response>()
    let pedidos = 0
    apiFalsa({ 'GET /plataforma/visao': () => (++pedidos === 1 ? espera.promessa : visao()) })
    await abrir('/plataforma')
    expect($('[role="status"][aria-label="Carregando a visão geral"]')).not.toBeNull()
    espera.resolver(erroApi(503, 'erro_servidor', 'Fora do ar agora.'))
    await flushPromises()
    expect(t($('[data-erro-visao]')!.textContent)).toBe('Fora do ar agora. Tentar de novo')
    await clicar(botao('Tentar de novo'))
    expect($('[data-erro-visao]')).toBeNull()
    expect($$('[data-indicador]')).toHaveLength(6)
    expect(t($('[data-atualizado]')!.textContent)).toBe('Números de 04/10/2026 às 15:00')
    await clicar($('[data-atualizar]'))
    expect(pedidos).toBe(3)
  })

  it('indicadores: em teste, pagantes, receita com "sandbox", testes acabando, novas e conversão', async () => {
    entrar()
    apiFalsa({ 'GET /plataforma/visao': () => visao() })
    await abrir('/plataforma')
    const ler = (chave: string) => ({
      rotulo: t(indicador(chave).querySelector('h2')!.textContent),
      valor: t(indicador(chave).querySelector('[data-valor]')!.textContent),
      detalhe: t(indicador(chave).querySelector('[data-detalhe]')!.textContent),
    })
    expect(['teste', 'pagantes', 'receita', 'acabando', 'novas', 'conversao'].map(ler)).toEqual([
      { rotulo: 'Em teste', valor: '2', detalhe: '1 teste encerrado sem assinar' },
      { rotulo: 'Pagantes', valor: '2', detalhe: '1 com fatura atrasada · 5 contas no total' },
      { rotulo: 'Receita mensal', valor: 'R$ 498,00', detalhe: 'das 2 assinaturas ativas' },
      { rotulo: 'Testes acabando em 7 dias', valor: '1', detalhe: 'A lista está logo abaixo' },
      { rotulo: 'Novas em 30 dias', valor: '3', detalhe: '1 nova nos últimos 7 dias' },
      { rotulo: 'Conversão do teste', valor: '75%', detalhe: '3 de 4 contas criadas entre 05/08 e 19/09 assinaram.' },
    ])
    expect(t(indicador('receita').querySelector('[data-selo]')!.textContent)).toBe('sandbox')
  })

  it('receita de produção sem o selo; conversão sem contas no período', async () => {
    entrar()
    const v = visao()
    v.totais.ambiente = 'producao'
    v.conversao = { de: '2026-08-05', ate: '2026-09-19', contas: 0, assinaram: 0, taxa: null }
    apiFalsa({ 'GET /plataforma/visao': () => v })
    await abrir('/plataforma')
    expect(indicador('receita').querySelector('[data-selo]')).toBeNull()
    expect(t(indicador('conversao').querySelector('[data-valor]')!.textContent)).toBe('—')
    expect(t(indicador('conversao').querySelector('[data-detalhe]')!.textContent)).toBe('Nenhuma conta com teste criada entre 05/08 e 19/09.')
  })

  it('testes acabando: dias que faltam, o que falta na ativação, último acesso e copiar o e-mail', async () => {
    entrar()
    const copiar = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: copiar }, configurable: true })
    apiFalsa({ 'GET /plataforma/visao': () => visao() })
    await abrir('/plataforma')
    const [item] = $$('[data-teste-acabando]')
    expect(t(item!.textContent)).toContain('Alfa Distribuidora')
    expect(t(item!.querySelector('[data-dias]')!.textContent)).toBe('Faltam 3 dias')
    expect(t(item!.textContent)).toContain('ana@alfa.com.br')
    expect(t(item!.textContent)).toContain('Entrou ontem · teste até 07/10/2026')
    expect(t(item!.textContent)).toContain('Falta: primeiro envio e primeira resposta.')
    expect(item!.querySelector('[data-ativacao]')!.getAttribute('aria-label')).toBe('Ativação: 2 de 4. Feitos: contatos e envios ligados.')
    expect(item!.querySelectorAll('[data-ativacao] [data-feito]')).toHaveLength(2)
    await clicar(botao('Copiar e-mail', item!))
    expect(copiar).toHaveBeenCalledWith('ana@alfa.com.br')
    expect(botao('Copiado!', item!)).not.toBeNull()
  })

  it('nenhum teste acabando: o aviso vazio', async () => {
    entrar()
    apiFalsa({ 'GET /plataforma/visao': () => visao({ testes_acabando: [] }) })
    await abrir('/plataforma')
    expect(t($('[data-testes-acabando]')!.textContent)).toContain('Nenhum teste acaba nos próximos 7 dias')
    expect(t(indicador('acabando').querySelector('[data-detalhe]')!.textContent)).toBe('Nenhum teste acaba nesta semana')
  })

  it('contas: ordem por último acesso, busca sem acento pelo nome ou e-mail, filtro por situação e a lista do celular', async () => {
    entrar()
    apiFalsa({ 'GET /plataforma/visao': () => visao() })
    await abrir('/plataforma')
    expect(nomesTabela()).toEqual(['Gama Foods', 'Alfa Distribuidora', 'Éta Ótica', 'Delta Peças', 'Beta Logística']) // quem nunca entrou por último
    expect($$('[data-lista-contas] [data-conta-visao]')).toHaveLength(5)
    expect(t($('[data-total-contas]')!.textContent)).toBe('5 contas')
    const alfa = linhasTabela()[1]!
    expect(t(alfa.textContent)).toContain('ana@alfa.com.br')
    expect(t(alfa.querySelector('td:nth-child(2)')!.textContent)).toBe('Em testeProfissional · sem assinaturacriada em 23/09/2026')
    expect(t(alfa.querySelector('td:nth-child(6)')!.textContent)).toBe('41 contatos ativos12 convites em 30 diasIA: 37 no mês')
    expect(t(alfa.textContent)).toContain('Entrou ontem')
    expect(t(alfa.textContent)).toContain('8164 no total')
    expect(t(linhasTabela()[0]!.textContent)).toContain('Profissional · R$ 349,00/mês')
    expect(t(linhasTabela()[3]!.querySelector('[data-situacao]')!.textContent)).toBe('Pausada')
    // busca: sem acento e pelo e-mail do administrador
    const busca = $<HTMLInputElement>('[data-contas-visao] input[type="search"]')
    await digitar(busca, 'eta otica')
    expect(nomesTabela()).toEqual(['Éta Ótica'])
    expect(t($('[data-total-contas]')!.textContent)).toBe('1 conta de 5')
    await digitar(busca, 'GUI@GAMA')
    expect(nomesTabela()).toEqual(['Gama Foods'])
    await digitar(busca, 'ninguém')
    expect(t($('[data-vazio-contas]')!.textContent)).toContain('Nenhuma conta com esses filtros')
    await clicar(botao('Limpar filtros', $('[data-vazio-contas]')!))
    expect(nomesTabela()).toHaveLength(5)
    // filtro por situação: só as que aparecem, com a contagem
    const situacao = selecao('Situação', $('[data-contas-visao]')!)
    expect(Array.from(situacao.options).map((o) => o.text)).toEqual(['Todas', 'Em teste (2)', 'Teste encerrado (1)', 'Ativa (1)', 'Pausada (1)'])
    await escolher(situacao, 'teste')
    expect(nomesTabela()).toEqual(['Alfa Distribuidora', 'Beta Logística'])
    await escolher(situacao, '')
    // ordem por criação e por respostas
    const ordem = selecao('Ordenar por', $('[data-contas-visao]')!)
    await escolher(ordem, 'criacao')
    expect(nomesTabela()).toEqual(['Beta Logística', 'Alfa Distribuidora', 'Éta Ótica', 'Gama Foods', 'Delta Peças'])
    await escolher(ordem, 'respostas')
    expect(nomesTabela()).toEqual(['Gama Foods', 'Alfa Distribuidora', 'Delta Peças', 'Beta Logística', 'Éta Ótica'])
  })
})

// ── Erros ───────────────────────────────────────────────────────────────────

describe('Plataforma › Erros', () => {
  it('vazio: "Nenhum erro nos últimos N dias", conforme o período', async () => {
    entrar()
    const api = apiFalsa({ 'GET /plataforma/erros': () => [] })
    await abrir('/plataforma/erros')
    expect(t($('[data-vazio-erros] h3')!.textContent)).toBe('Nenhum erro nos últimos 7 dias')
    await escolher(selecao('Período'), '30')
    expect(t($('[data-vazio-erros] h3')!.textContent)).toBe('Nenhum erro nos últimos 30 dias')
    expect(chamadasDe(api, 'GET', '/plataforma/erros').at(-1)!.url.searchParams.get('dias')).toBe('30')
  })

  it('carregando e erro com "Tentar de novo"', async () => {
    entrar()
    const espera = adiada<Response>()
    let pedidos = 0
    apiFalsa({ 'GET /plataforma/erros': () => (++pedidos === 1 ? espera.promessa : ERROS) })
    await abrir('/plataforma/erros')
    expect($('[role="status"][aria-label="Carregando os erros"]')).not.toBeNull()
    espera.resolver(erroApi(500, 'erro_servidor', 'Algo deu errado do nosso lado.'))
    await flushPromises()
    expect(t($('[data-erro-erros]')!.textContent)).toContain('Algo deu errado do nosso lado.')
    await clicar(botao('Tentar de novo'))
    expect($$('[data-erro]')).toHaveLength(3)
  })

  it('a lista: tipo, origem, mensagem sem HTML, onde, quantas vezes, conta, versão, pedido e a pilha', async () => {
    entrar()
    apiFalsa({ 'GET /plataforma/erros': () => ERROS })
    await abrir('/plataforma/erros')
    expect(t($('[data-total-erros]')!.textContent)).toBe('3 erros abertos nos últimos 7 dias')
    const [api, site, tarefa] = $$('[data-erro]')
    expect(t(api!.querySelector('[data-tipo]')!.textContent)).toBe('ZeroDivisionError')
    expect(t(api!.querySelector('[data-origem]')!.textContent)).toBe('API')
    expect(t(api!.querySelector('[data-local]')!.textContent)).toBe('GET /api/v1/acoes/{acao_id}')
    expect(dadosDoErro(api!)).toEqual({
      'Ocorrências:': '12 vezes',
      'Última:': '04/10/2026 às 14:32',
      'Primeira:': '01/10/2026 às 09:00',
      'Versão:': 'a1b2c3d',
      'Conta:': 'Alfa Distribuidora',
      'Pedido:': '4f9c2b7d0e1a4c3b9d8e7f6a5b4c3d2e',
    })
    const pilha = api!.querySelector('[data-pilha]')!
    expect(t(pilha.querySelector('summary')!.textContent)).toBe('Ver a pilha')
    expect(pilha.querySelector('pre')!.textContent).toBe(ERROS[0]!.pilha)
    // site: o HTML da mensagem fica como texto; a conta que não existe mais; uma vez só, sem "Primeira"
    expect(t(site!.querySelector('[data-origem]')!.textContent)).toBe('Site')
    expect(site!.querySelector('[data-mensagem] b')).toBeNull()
    expect(t(site!.querySelector('[data-mensagem]')!.textContent)).toContain('<b>negrito</b>')
    expect(t(site!.querySelector('[data-conta]')!.textContent)).toBe('Conta 9 (excluída)')
    expect(dadosDoErro(site!)).toEqual({ 'Ocorrências:': '1 vez', 'Última:': '04/10/2026 às 14:32', 'Versão:': 'local', 'Conta:': 'Conta 9 (excluída)' })
    // tarefa: sem mensagem, sem conta e sem pilha
    expect(t(tarefa!.querySelector('[data-origem]')!.textContent)).toBe('Tarefa')
    expect(t(tarefa!.querySelector('[data-mensagem]')!.textContent)).toBe('Sem mensagem.')
    expect(tarefa!.querySelector('[data-conta]')).toBeNull()
    expect(tarefa!.querySelector('[data-pilha]')).toBeNull()
  })

  it('filtros de origem e situação vão no pedido; "Limpar filtros" volta ao padrão', async () => {
    entrar()
    const api = apiFalsa({ 'GET /plataforma/erros': (c) => ERROS.filter((e) => !c.url.searchParams.get('origem') || e.origem === c.url.searchParams.get('origem')) })
    await abrir('/plataforma/erros')
    expect(botao('Limpar filtros')).toBeNull()
    await escolher(selecao('Origem'), 'site')
    await escolher(selecao('Situação'), 'todos')
    expect(Object.fromEntries(chamadasDe(api, 'GET', '/plataforma/erros').at(-1)!.url.searchParams)).toEqual({ origem: 'site', situacao: 'todos', dias: '7' })
    expect($$('[data-erro]')).toHaveLength(1)
    expect(t($('[data-total-erros]')!.textContent)).toBe('1 erro nos últimos 7 dias')
    await clicar(botao('Limpar filtros'))
    expect(Object.fromEntries(chamadasDe(api, 'GET', '/plataforma/erros').at(-1)!.url.searchParams)).toEqual({ situacao: 'abertos', dias: '7' })
    expect($$('[data-erro]')).toHaveLength(3)
  })

  it('"Resolver" e "Reabrir" mudam o item na hora (o foco fica no botão); a falha avisa', async () => {
    entrar()
    let falhar = false
    const api = apiFalsa({
      'GET /plataforma/erros': () => ERROS,
      'POST /plataforma/erros/:id/resolver': (c) => (falhar ? erroApi(404, 'nao_encontrado', 'Erro não encontrado.') : { ...ERROS.find((e) => c.caminho.includes(`/${e.id}/`))!, resolvido_em: '2026-10-04T18:10:00Z' }),
      'POST /plataforma/erros/:id/reabrir': (c) => ({ ...ERROS.find((e) => c.caminho.includes(`/${e.id}/`))!, resolvido_em: null }),
    })
    await abrir('/plataforma/erros')
    const primeiro = () => $('[data-erro="1"]')!
    const alternar = () => primeiro().querySelector<HTMLElement>('[data-alternar]')!
    expect(t(alternar().textContent)).toBe('Resolver o erro ZeroDivisionError')
    const antes = alternar()
    antes.focus()
    await clicar(antes)
    expect(chamadasDe(api, 'POST', '/plataforma/erros/1/resolver')).toHaveLength(1)
    expect(t(primeiro().querySelector('[data-resolvido]')!.textContent)).toBe('Resolvido')
    expect(dadosDoErro(primeiro())['Resolvido em:']).toBe('04/10/2026 às 15:10')
    expect(t(alternar().textContent)).toBe('Reabrir o erro ZeroDivisionError')
    expect(document.activeElement).toBe(alternar())
    expect(avisos.map((a) => a.mensagem)).toContain('ZeroDivisionError marcado como resolvido.')
    await clicar(alternar())
    expect(chamadasDe(api, 'POST', '/plataforma/erros/1/reabrir')).toHaveLength(1)
    expect(primeiro().querySelector('[data-resolvido]')).toBeNull()
    expect(avisos.map((a) => a.mensagem)).toContain('ZeroDivisionError reaberto.')
    falhar = true
    await clicar(alternar())
    expect(avisos.map((a) => a.mensagem)).toContain('Erro não encontrado.')
    expect(primeiro().querySelector('[data-resolvido]')).toBeNull()
  })
})
