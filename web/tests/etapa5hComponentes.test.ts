// Etapa 5h (docs/api-etapa-5h.md §1 e §2) nas telas: o "Comece por aqui" (passos, permissões e a marca), o modo
// exemplo (liga, desliga, ?exemplo=1 e os links e botões desligados), o tom com a IA ligada ("Analisar agora"), o botão
// "Criar planos para N empresas" e a tela final da importação de respostas.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, nextTick } from 'vue'
import type { Conta, Painel, TomComentarios } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import ImportacaoView from '@/modulos/importacao/ImportacaoView.vue'
import InicioView from '@/modulos/inicio/InicioView.vue'
import { MENSAGEM_COR } from '@/modulos/inicio/logica'
import BlocoTom from '@/modulos/painel/BlocoTom.vue'
import { painelExemplo } from '@/modulos/painel/exemplo'
import { apiFalsa, erro422 } from './apiFalsa'

const HOJE = hojeIso()
const NOVENTA = { de: somarDias(HOJE, -89), ate: HOJE }
const ADMIN = [
  'painel.ver', 'painel.exportar', 'contatos.ver', 'contatos.editar', 'importacao.usar', 'envios.ver', 'formularios.ver',
  'respostas.ver', 'acoes.ver', 'acoes.tratar', 'configuracoes.gerenciar', 'assinatura.gerenciar',
]

function painelVazio(pp: Partial<Painel['primeiros_passos']> = {}): Painel {
  const meses = painelExemplo(HOJE).evolucao_12m!.map((m) => ({ ...m, nps: null, total: 0, no_periodo: false }))
  return {
    periodo: { ...NOVENTA, anterior: { de: somarDias(HOJE, -179), ate: somarDias(HOJE, -90) } },
    nps: { valor: null, faixa: null, promotores: 0, neutros: 0, detratores: 0, total: 0, pct: { promotores: 0, neutros: 0, detratores: 0 }, decisores: { valor: null, total: 0 } },
    variacao: null,
    csat: { percentual: null, media: null, total: 0, satisfeitos: 0 },
    taxa_resposta: { percentual: null, responderam: 0, convidados: 0, amostra_pequena: false },
    movimentacao: { resgatados: 0, deixaram_de_ser_promotores: 0, itens: [] },
    atencao: { acoes_abertas: 0, acoes_vencidas: 0, tudo_em_dia: true, empresas: [], receita_em_risco: { valor: 0, empresas: 0, sem_valor: 0, carteira: null }, detratores_sem_plano: 0 },
    temas: [],
    comentarios: [],
    evolucao: [],
    evolucao_12m: meses,
    empresas: { menor: [], maior: [] },
    palavras: [],
    primeiros_passos: { contatos: true, envios_ligados: false, primeiro_envio: false, primeira_resposta: false, ...pp },
    picos: [],
    tom: { analisados: 0, com_comentario: 0, total_respostas: 0, pendentes: 0, negativo: 0, misto: 0, neutro: 0, positivo: 0, anterior: null, ia_ligada: true, sem_analise: 0 },
  }
}

/** Um painel de conta com respostas (o de exemplo serve: é coerente). */
function painelComDados(extra: Partial<Painel> = {}): Painel {
  return { ...painelExemplo(HOJE), ...extra }
}

function entrar(permissoes: string[], conta: Partial<Conta> = {}) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Marcelo Mendes', email: 'm@x.com', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 42, nome: 'Distribuidora Aurora', plano: null, situacao: 'ativa', teste_ate: null, ...conta },
      permissoes,
    },
    false,
  )
}

let router: Router
async function abrir(endereco = '/inicio', componente: object = InicioView): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/inicio', component: componente },
      { path: '/contatos/importar', component: ImportacaoView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra tela') } },
    ],
  })
  await router.push(endereco)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await vi.dynamicImportSettled()
  await flushPromises()
  return w
}

const botao = (w: VueWrapper, texto: string) => w.findAll('button').find((b) => b.text().includes(texto))

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo // o jsdom não rola (o Início volta ao topo no modo exemplo)
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
})

// ── Comece por aqui ─────────────────────────────────────────────────────────

describe('Comece por aqui', () => {
  it('sem nenhuma resposta, troca o painel: saudação, os 4 passos com o próximo em destaque e os dois cartões', async () => {
    entrar(ADMIN)
    const { chamadas } = apiFalsa({ 'GET /painel': () => painelVazio(), 'GET /cadastros/grupos': () => [], 'GET /conta/marca': () => ({ cor: null, tem_logo: false }) })
    const w = await abrir()
    expect(w.find('[data-comece]').exists()).toBe(true)
    expect(w.get('h1').text()).toMatch(/, Marcelo!$/)
    expect(w.get('[data-subtitulo-comece]').text()).toBe('Em 4 passos você recebe as primeiras respostas.')
    // sem os filtros nem os blocos do painel
    expect(w.find('[data-filtros]').exists()).toBe(false)
    expect(w.find('#t-resumo').exists()).toBe(false)
    expect(w.find('[data-atalhos-cabecalho]').exists()).toBe(false)
    // os 4 passos, na ordem, com o estado escrito
    const passos = w.findAll('[data-passo]')
    expect(passos.map((p) => p.attributes('data-passo'))).toEqual(['contatos', 'envios_ligados', 'primeiro_envio', 'primeira_resposta'])
    expect(passos[0]!.text()).toContain('Cadastrar seus clientes')
    expect(passos[0]!.text()).toContain('Feito')
    expect(passos[0]!.find('a').exists()).toBe(false) // feito: sem botão
    expect(passos[1]!.attributes('data-proximo')).toBeDefined()
    expect(passos[1]!.text()).toContain('Próximo passo')
    const proximo = passos[1]!.get('a')
    expect(proximo.attributes('href')).toBe('/configuracoes/envios')
    expect(proximo.classes()).toContain('bg-marca-forte') // o botão principal
    expect(passos[2]!.text()).toContain('A fazer')
    expect(passos[2]!.get('a').attributes('href')).toBe('/envios')
    expect(passos[2]!.get('a').classes()).not.toContain('bg-marca-forte')
    expect(w.get('[data-progresso]').text()).toBe('1 de 4 feitos')
    // a marca (lê GET /conta/marca) e o exemplo
    expect(chamadas.some((c) => c.caminho === '/conta/marca')).toBe(true)
    expect(w.get('[data-cartao-marca]').text()).toContain('Opcional')
    expect(w.get('[data-marca-logo]').text()).toBe('Ainda não tem')
    expect(w.get('[data-marca-cor]').text()).toContain('A dos modelos')
    expect(w.get('[data-cartao-exemplo]').text()).toContain('Ver com dados de exemplo')
  })

  it('o cartão do teste grátis continua acima, como hoje', async () => {
    entrar(ADMIN, { situacao: 'teste', plano: 'profissional', teste_ate: `${somarDias(HOJE, 12)}T03:00:00Z`, cobranca: { liberada: true, assinada: false, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } })
    apiFalsa({ 'GET /painel': () => painelVazio(), 'GET /conta/marca': () => ({ cor: null, tem_logo: false }) })
    const w = await abrir()
    expect(w.find('[data-cartao-teste]').exists()).toBe(true)
    expect(w.find('[data-comece]').exists()).toBe(true)
  })

  it('permissões: botão só quando o perfil abre a tela; a marca só para quem administra (e nem lê a API)', async () => {
    entrar(['painel.ver', 'contatos.ver'])
    const { chamadas } = apiFalsa({ 'GET /painel': () => painelVazio({ contatos: false }), 'GET /cadastros/grupos': () => [] })
    const w = await abrir()
    const passos = w.findAll('[data-passo]')
    expect(passos[0]!.get('a').attributes('href')).toBe('/contatos') // sem importacao.usar: vai para Contatos
    expect(passos.slice(1).every((p) => !p.find('a').exists())).toBe(true) // sem envios.ver nem respostas.ver
    expect(w.find('[data-cartao-marca]').exists()).toBe(false)
    expect(chamadas.some((c) => c.caminho === '/conta/marca')).toBe(false)
    expect(w.find('[data-cartao-exemplo]').exists()).toBe(true) // o exemplo é para todos
  })

  it('com a primeira resposta (inclusive importada), o Início volta a ser o painel', async () => {
    entrar(ADMIN)
    apiFalsa({ 'GET /painel': () => painelComDados({ primeiros_passos: { contatos: true, envios_ligados: false, primeiro_envio: false, primeira_resposta: true } }), 'GET /cadastros/grupos': () => [] })
    const w = await abrir()
    expect(w.find('[data-comece]').exists()).toBe(false)
    expect(w.find('#t-resumo').exists()).toBe(true)
    expect(w.find('[data-filtros]').exists()).toBe(true)
    expect(w.text()).toContain('Primeiros passos: 2 de 4.') // a linha dos primeiros passos, como hoje
  })
})

describe('Sua marca nas pesquisas', () => {
  it('com logo ou cor própria, o cartão fica feito', async () => {
    entrar(ADMIN, { logo_url: 'https://api.toqqi.test/logo.png' })
    apiFalsa({ 'GET /painel': () => painelVazio(), 'GET /conta/marca': () => ({ cor: '#0E7490', tem_logo: true }) })
    const w = await abrir()
    expect(w.find('[data-marca-feita]').exists()).toBe(true)
    expect(w.get('[data-marca-logo] img').attributes('src')).toBe('https://api.toqqi.test/logo.png')
    expect(w.get('[data-marca-cor]').text()).toContain('#0E7490')
  })

  it('o modal: paleta de 8, prévia do botão na cor, salvar manda {cor} e o cartão fica feito', async () => {
    entrar(ADMIN)
    const { chamadas } = apiFalsa({
      'GET /painel': () => painelVazio(),
      'GET /conta/marca': () => ({ cor: null, tem_logo: false }),
      'PUT /conta/marca': (c) => ({ cor: (c.corpo as { cor: string }).cor, formularios_atualizados: 2 }),
    })
    const w = await abrir()
    await w.get('[data-escolher-marca]').trigger('click')
    const radios = w.findAll('input[name="cor-marca"]')
    expect(radios).toHaveLength(8)
    expect(w.text()).toContain('Logo') // o envio do logo (o mesmo de Configurações › Empresa)
    expect(w.text()).toContain('Enviar logo')
    // sem escolha, a prévia fica na cor dos modelos e não dá para salvar
    expect(w.get('[data-botao-previa]').attributes('style')).toContain('background-color: rgb(31, 111, 235)')
    expect(w.get('[data-salvar-cor]').attributes('disabled')).toBeDefined()
    await radios[2]!.setValue(true) // Verde
    expect((w.get('input[autocomplete="off"]').element as HTMLInputElement).value).toBe('#047857')
    expect(w.get('[data-botao-previa]').attributes('style')).toContain('background-color: rgb(4, 120, 87)')
    expect(w.get('[data-botao-previa]').attributes('style')).toContain('color: rgb(255, 255, 255)')
    await w.get('[data-salvar-cor]').trigger('click')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'PUT' && c.caminho === '/conta/marca')!.corpo).toEqual({ cor: '#047857' })
    expect(avisos.at(-1)?.mensagem).toBe('Cor salva: os e-mails e 2 formulários já usam a nova cor.')
    expect(w.find('[data-salvar-cor]').exists()).toBe(false) // o modal fechou
    expect(w.get('[data-marca-cor]').text()).toContain('#047857')
    expect(w.find('[data-marca-feita]').exists()).toBe(true)
  })

  it('cor digitada fora do formato: avisa no campo e não manda; o erro da API também vai para o campo', async () => {
    entrar(ADMIN)
    const { chamadas } = apiFalsa({
      'GET /painel': () => painelVazio(),
      'GET /conta/marca': () => ({ cor: null, tem_logo: false }),
      'PUT /conta/marca': () => erro422('Confira os campos destacados.', { cor: 'Cor recusada pela API.' }),
    })
    const w = await abrir()
    await w.get('[data-escolher-marca]').trigger('click')
    const campo = w.get('input[autocomplete="off"]')
    await campo.setValue('azul')
    await w.get('[data-salvar-cor]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain(MENSAGEM_COR)
    expect(w.get('input[autocomplete="off"]').attributes('aria-invalid')).toBe('true')
    expect(chamadas.some((c) => c.metodo === 'PUT')).toBe(false)
    await w.get('input[autocomplete="off"]').setValue('d63a18')
    await w.get('[data-salvar-cor]').trigger('click')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'PUT')!.corpo).toEqual({ cor: '#D63A18' })
    expect(w.text()).toContain('Cor recusada pela API.')
  })
})

// ── Modo exemplo ────────────────────────────────────────────────────────────

describe('modo exemplo', () => {
  async function noExemplo() {
    entrar(ADMIN)
    const api = apiFalsa({ 'GET /painel': () => painelVazio(), 'GET /cadastros/grupos': () => [], 'GET /conta/marca': () => ({ cor: null, tem_logo: false }) })
    const w = await abrir()
    await w.get('[data-ver-exemplo]').trigger('click')
    await flushPromises()
    return { w, ...api }
  }

  it('liga pelo "Comece por aqui": faixa no topo com o foco, o painel de exemplo e nada novo pedido à API', async () => {
    const { w, chamadas } = await noExemplo()
    const faixa = w.get('[data-faixa-exemplo]')
    expect(faixa.text()).toContain('Você está vendo dados de exemplo.')
    expect(faixa.text()).toContain('Voltar para os meus dados')
    expect(document.activeElement?.textContent).toContain('Você está vendo dados de exemplo.')
    // a faixa vem antes de tudo
    expect(w.element.querySelector('[data-faixa-exemplo]')!.compareDocumentPosition(w.element.querySelector('h1')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(w.find('[data-comece]').exists()).toBe(false)
    expect(w.get('#t-resumo').text()).toBe('NPS dos últimos 90 dias')
    expect(w.get('[data-medidor]').attributes('aria-label')).toContain('NPS 27')
    expect(w.text()).toContain('Mercearia Lua Nova')
    expect(w.text()).toContain('Tratar Atacado Ventania')
    expect(w.find('[data-resumo-ia-exemplo]').exists()).toBe(true)
    expect(chamadas.some((c) => c.caminho.startsWith('/painel/resumo-ia'))).toBe(false)
    expect(chamadas.some((c) => c.metodo !== 'GET')).toBe(false)
  })

  it('links e botões do painel desligados (o leitor de tela continua lendo tudo), menos "Como ler o painel"', async () => {
    const { w } = await noExemplo()
    const painel = w.get('[data-modo-exemplo]')
    expect(painel.findAll('a[href]')).toHaveLength(0)
    const ligados = painel.findAll('button').filter((b) => b.attributes('disabled') === undefined && b.attributes('aria-disabled') !== 'true')
    expect(ligados).toHaveLength(0)
    const criar = painel.get('[data-criar-planos]')
    expect(criar.text()).toContain('Criar planos para 4 empresas')
    expect(criar.attributes('disabled')).toBeDefined()
    // os filtros aparecem, desligados; "Como ler os números" e "Como ler o painel" continuam
    expect(w.get('select#filtro-periodo').attributes('disabled')).toBeDefined()
    expect(botao(w, 'Só ativas')!.attributes('disabled')).toBeDefined()
    expect(botao(w, 'Exportar CSV')!.attributes('disabled')).toBeDefined()
    expect(w.get('[data-como-ler]').attributes('disabled')).toBeUndefined()
    Element.prototype.scrollIntoView = vi.fn() // o jsdom não rola
    await w.get('[data-como-ler]').trigger('click')
    await flushPromises()
    expect(w.get('#ajuda-painel details').attributes('open')).toBeDefined()
    // nada some para o leitor de tela: os blocos não ficam escondidos nem inertes
    expect(painel.attributes('inert')).toBeUndefined()
    expect(painel.attributes('aria-hidden')).toBeUndefined()
    // e clicar num comentário ou numa empresa não navega
    await painel.get('[data-comentario]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/inicio')
  })

  it('"Voltar para os meus dados" volta ao "Comece por aqui", com o foco no botão do exemplo', async () => {
    const { w } = await noExemplo()
    await w.get('[data-voltar-exemplo]').trigger('click')
    await flushPromises()
    await nextTick()
    expect(w.find('[data-faixa-exemplo]').exists()).toBe(false)
    expect(w.find('[data-comece]').exists()).toBe(true)
    expect(document.activeElement?.hasAttribute('data-ver-exemplo')).toBe(true)
  })

  it('?exemplo=1 abre direto nele (mesmo numa conta com dados) e sai do endereço; o modo não fica salvo', async () => {
    entrar(ADMIN)
    apiFalsa({ 'GET /painel': () => painelComDados({ atencao: { ...painelComDados().atencao, detratores_sem_plano: 0 } }), 'GET /cadastros/grupos': () => [] })
    let w = await abrir('/inicio?exemplo=1&utm=x')
    expect(w.find('[data-faixa-exemplo]').exists()).toBe(true)
    expect(router.currentRoute.value.query).toEqual({ utm: 'x' })
    expect(w.find('[data-criar-planos]').exists()).toBe(true) // os números são os do exemplo, não os da conta
    // sair do Início desliga
    await router.push('/respostas')
    await flushPromises()
    await router.push('/inicio')
    await vi.dynamicImportSettled()
    await flushPromises()
    expect(w.find('[data-faixa-exemplo]').exists()).toBe(false)
    expect(w.find('[data-criar-planos]').exists()).toBe(false)
    w.unmount()
    // abrir de novo (recarregar) sem o parâmetro: os dados da conta
    w = await abrir('/inicio')
    expect(w.find('[data-faixa-exemplo]').exists()).toBe(false)
    expect(w.find('[data-modo-exemplo]').exists()).toBe(false)
  })
})

// ── Tom dos comentários ─────────────────────────────────────────────────────

describe('tom: comentários que a IA ainda não leu', () => {
  const NAO_LIDOS: TomComentarios = { analisados: 0, com_comentario: 12, total_respostas: 20, pendentes: 0, negativo: 0, misto: 0, neutro: 0, positivo: 0, anterior: null, ia_ligada: true, sem_analise: 12 }

  function montarTom(tom: TomComentarios) {
    const r = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => h('div') } }] })
    return mount(BlocoTom, { props: { tom, textoAnterior: 'os 90 dias antes' }, global: { plugins: [r] }, attachTo: document.body })
  }

  it('"Analisar agora" (quem administra) chama a análise dos últimos 90 dias e passa a "analisando"', async () => {
    entrar(ADMIN)
    const { chamadas } = apiFalsa({ 'POST /conta/ia/analisar-recentes': () => ({ marcadas: 12, restantes_no_mes: 900 }) })
    const w = montarTom(NAO_LIDOS)
    expect(w.get('[data-tom-nao-lidos]').text()).toContain('12 comentários ainda não foram lidos pela IA.')
    expect(w.find('[data-tom-ligar]').exists()).toBe(false)
    await w.get('[data-analisar-agora]').trigger('click')
    await flushPromises()
    expect(chamadas.filter((c) => c.metodo === 'POST' && c.caminho === '/conta/ia/analisar-recentes')).toHaveLength(1)
    expect(w.find('[data-tom-analisando]').exists()).toBe(true)
    expect(avisos.at(-1)?.mensagem).toBe('12 comentários foram para a análise da IA.')
    // números novos do painel (troca de filtro ou recarga) mandam no bloco de novo
    await w.setProps({ tom: { ...NAO_LIDOS, sem_analise: 3 } })
    expect(w.get('[data-tom-nao-lidos]').text()).toContain('3 comentários')
  })

  it('nada marcado (só os últimos 90 dias, até o limite) ou erro: continua o convite, com o aviso', async () => {
    entrar(ADMIN)
    apiFalsa({ 'POST /conta/ia/analisar-recentes': () => ({ marcadas: 0, restantes_no_mes: 0 }) })
    let w = montarTom(NAO_LIDOS)
    await w.get('[data-analisar-agora]').trigger('click')
    await flushPromises()
    expect(w.find('[data-tom-nao-lidos]').exists()).toBe(true)
    expect(avisos.at(-1)?.mensagem).toContain('Nenhum comentário foi para a análise')
    w.unmount()
    apiFalsa({
      'POST /conta/ia/analisar-recentes': () =>
        new Response(JSON.stringify({ erro: { codigo: 'ia_indisponivel', mensagem: 'A análise com IA volta a funcionar quando a assinatura estiver em dia.', campos: {} } }), { status: 409 }),
    })
    w = montarTom(NAO_LIDOS)
    await w.get('[data-analisar-agora]').trigger('click')
    await flushPromises()
    expect(avisos.at(-1)?.mensagem).toBe('A análise com IA volta a funcionar quando a assinatura estiver em dia.')
    expect(w.find('[data-tom-nao-lidos]').exists()).toBe(true)
  })

  it('sem configuracoes.gerenciar: o texto, sem o botão; IA desligada: o convite de hoje; curtos demais: avisa', async () => {
    entrar(['painel.ver'])
    apiFalsa({})
    let w = montarTom(NAO_LIDOS)
    expect(w.get('[data-tom-nao-lidos]').text()).toContain('12 comentários ainda não foram lidos pela IA.')
    expect(w.find('[data-analisar-agora]').exists()).toBe(false)
    w.unmount()
    w = montarTom({ ...NAO_LIDOS, ia_ligada: false })
    expect(w.get('[data-tom-ligar]').text()).toBe('A análise por IA está desligada ou ainda não chegou a estes comentários.')
    w.unmount()
    w = montarTom({ ...NAO_LIDOS, sem_analise: 0 })
    expect(w.get('[data-tom-curtos]').text()).toContain('curtos demais')
  })
})

// ── Criar planos para N empresas ────────────────────────────────────────────

describe('"Criar planos para N empresas" no "O que mudou"', () => {
  const comDetratores = () => painelComDados({ atencao: { ...painelExemplo(HOJE).atencao, detratores_sem_plano: 3 } })

  it('chama o endpoint com os filtros dos números na tela, avisa e leva a Planos de ação', async () => {
    entrar(ADMIN)
    const { chamadas } = apiFalsa({ 'GET /painel': comDetratores, 'GET /cadastros/grupos': () => [], 'POST /acoes/detratores': () => ({ criadas: 3, restantes: 0 }) })
    const w = await abrir()
    const criar = w.get('[data-criar-planos]')
    expect(criar.text()).toBe('Criar planos para 3 empresas')
    await criar.trigger('click')
    await flushPromises()
    const pedido = chamadas.find((c) => c.metodo === 'POST' && c.caminho === '/acoes/detratores')!
    expect(pedido.corpo).toEqual({ ...NOVENTA, so_ativos: true })
    expect(avisos.at(-1)?.mensagem).toBe('3 planos criados.')
    expect(router.currentRoute.value.path).toBe('/planos-de-acao')
  })

  it('sem acoes.tratar, sem o botão; nada criado (outra pessoa criou antes): avisa e atualiza o painel', async () => {
    entrar(ADMIN.filter((p) => p !== 'acoes.tratar'))
    apiFalsa({ 'GET /painel': comDetratores, 'GET /cadastros/grupos': () => [] })
    let w = await abrir()
    expect(w.find('[data-criar-planos]').exists()).toBe(false)
    w.unmount()
    entrar(ADMIN)
    const { chamadas } = apiFalsa({ 'GET /painel': comDetratores, 'GET /cadastros/grupos': () => [], 'POST /acoes/detratores': () => ({ criadas: 0, restantes: 0 }) })
    w = await abrir()
    await w.get('[data-criar-planos]').trigger('click')
    await flushPromises()
    expect(avisos.at(-1)?.mensagem).toBe('Nenhum plano novo: as empresas com detrator já têm plano aberto.')
    expect(router.currentRoute.value.path).toBe('/inicio')
    expect(chamadas.filter((c) => c.caminho === '/painel')).toHaveLength(2)
  })
})

// ── Tela final da importação de respostas ───────────────────────────────────

describe('importação de respostas: a tela final', () => {
  const ANALISE = {
    id: 'a1',
    tipo: 'respostas',
    colunas: ['email', 'data', 'nota', 'comentario'],
    mapeamento_sugerido: { email: 'email', data: 'data', nota: 'nota', comentario: 'comentario' },
    total_linhas: 3,
    amostra: [{ linha: 2, valores: { email: 'a@b.com', data: '01/09/2026', nota: '3', comentario: 'Atrasou' } }],
    campos: [
      { chave: 'email', rotulo: 'E-mail', obrigatorio: true },
      { chave: 'data', rotulo: 'Data da resposta', obrigatorio: true },
      { chave: 'nota', rotulo: 'Nota (0 a 10)', obrigatorio: true },
      { chave: 'comentario', rotulo: 'Comentário', obrigatorio: false },
    ],
  }

  async function importar(permissoes: string[], resultado: object, semPlano = 2) {
    entrar(permissoes)
    const api = apiFalsa({
      'POST /importacao/analisar': () => ANALISE,
      'POST /importacao/:id/conferir': () => ({ prontas: 3, novos: 3, atualizados: 0, com_problema: 0, problemas: [], avisos: [] }),
      'POST /importacao/:id/importar': () => resultado,
      'GET /painel': () => painelComDados({ atencao: { ...painelExemplo(HOJE).atencao, detratores_sem_plano: semPlano } }),
      'POST /acoes/detratores': () => ({ criadas: semPlano, restantes: 0 }),
    })
    const w = await abrir('/contatos/importar?tipo=respostas')
    await botao(w, 'Já tenho minha planilha')!.trigger('click')
    const entrada = w.get('input[type="file"]')
    Object.defineProperty(entrada.element, 'files', { value: [new File(['email;data;nota'], 'historico.csv', { type: 'text/csv' })] })
    await entrada.trigger('change')
    await botao(w, 'Continuar')!.trigger('click')
    await flushPromises()
    await botao(w, 'Conferir')!.trigger('click')
    await flushPromises()
    await botao(w, 'Importar 3 respostas')!.trigger('click')
    await flushPromises()
    return { w, ...api }
  }

  it('diz que a IA vai ler os comentários e convida a criar os planos (últimos 90 dias)', async () => {
    const { w, chamadas } = await importar(ADMIN, { novos: 3, atualizados: 0, ignorados: 0, problemas: [], ia_marcadas: 7 })
    expect(w.text()).toContain('Importação concluída!')
    expect(w.get('[data-ia-importados]').text()).toBe(
      'A IA vai ler os 7 comentários dos últimos 90 dias: o tom e os temas aparecem no Início em alguns minutos.',
    )
    const painel = chamadas.find((c) => c.caminho === '/painel')!
    expect(Object.fromEntries(painel.url.searchParams)).toEqual({ ...NOVENTA, so_ativos: 'true' })
    const convite = w.get('[data-convite-planos]')
    expect(convite.text()).toContain('2 empresas tiveram detrator nos últimos 90 dias')
    await convite.get('[data-criar-planos]').trigger('click')
    await flushPromises()
    expect(chamadas.find((c) => c.caminho === '/acoes/detratores')!.corpo).toEqual({ ...NOVENTA, so_ativos: true })
    expect(avisos.at(-1)?.mensagem).toBe('2 planos criados.')
    expect(router.currentRoute.value.path).toBe('/planos-de-acao')
  })

  it('sem comentários para a IA e sem detrator sem plano: nem o aviso nem o convite', async () => {
    const { w } = await importar(ADMIN, { novos: 3, atualizados: 0, ignorados: 0, problemas: [], ia_marcadas: 0 }, 0)
    expect(w.text()).toContain('Importação concluída!')
    expect(w.find('[data-ia-importados]').exists()).toBe(false)
    expect(w.find('[data-convite-planos]').exists()).toBe(false)
  })

  it('sem acoes.tratar (ou sem o painel), nem pergunta ao painel; servidor antigo (sem ia_marcadas), sem o aviso', async () => {
    const { w, chamadas } = await importar(['respostas.ver', 'importacao.usar', 'painel.ver'], { novos: 3, atualizados: 0, ignorados: 0, problemas: [] })
    expect(w.text()).toContain('Importação concluída!')
    expect(chamadas.some((c) => c.caminho === '/painel')).toBe(false)
    expect(w.find('[data-convite-planos]').exists()).toBe(false)
    expect(w.find('[data-ia-importados]').exists()).toBe(false)
  })
})
