// Telas da etapa 5a com a API simulada: Assinatura (assinar, pagar, esperar o pagamento, trocar de plano, dados de
// cobrança, cancelar), o aviso do topo, a mensagem de limite de contatos, a Plataforma e o menu.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, type Component } from 'vue'
import type { AvisoCobranca as TipoAviso, ContaPlataforma, EstadoAssinatura, Perfil, PlanoAssinatura } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import AlertaLimitePlano from '@/components/app/AlertaLimitePlano.vue'
import AvisoCobranca from '@/components/app/AvisoCobranca.vue'
import Botao from '@/components/ui/Botao.vue'
import { filtrarNavegacao, navegacaoAdministracao } from '@/layouts/navegacao'
import { router as rotasDoApp } from '@/router'
import AssinaturaView from '@/modulos/assinatura/AssinaturaView.vue'
import PlataformaView from '@/modulos/plataforma/PlataformaView.vue'
import { apiFalsa } from './apiFalsa'

const AGORA = new Date('2026-10-01T12:00:00-03:00')
const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

const USUARIO = { id: 1, nome: 'Ana Paula', email: 'ana@sol.com.br', cargo: null, situacao: 'ativo' as const, email_confirmado: true, ultimo_acesso: null, superadmin: false }
const DADOS_EU = (aviso: TipoAviso | null = null) => ({
  usuario: { ...USUARIO, perfil: 'admin' as const },
  conta: { id: 1, nome: 'Sol', plano: 'profissional', situacao: 'ativa', teste_ate: null, cobranca: { liberada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso } },
  permissoes: ['assinatura.gerenciar'],
})

function entrar(permissoes: string[], opcoes: { perfil?: Perfil; aviso?: TipoAviso | null; atrasadaDesde?: string | null; superadmin?: boolean } = {}) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { ...USUARIO, perfil: opcoes.perfil ?? 'admin', superadmin: !!opcoes.superadmin },
      conta: {
        id: 1,
        nome: 'Sol',
        plano: 'profissional',
        situacao: 'teste',
        teste_ate: '2026-10-15T14:30:00-03:00',
        cobranca: { liberada: true, pago_ate: null, atrasada_desde: opcoes.atrasadaDesde ?? null, pausa_em: null, aviso: opcoes.aviso ?? null },
      },
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
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return w
}
/** Componente solto (aviso, alerta) com o router. */
async function montar(componente: Component, caminho = '/inicio', props: Record<string, unknown> = {}): Promise<VueWrapper> {
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
  await router.push(caminho)
  await router.isReady()
  const w = mount(componente, { props, global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const botao = (w: { findAll: (seletor: string) => DOMWrapper<Element>[] }, texto: string | RegExp) => {
  const b = w.findAll('button').find((x) => (typeof texto === 'string' ? t(x.text()) === texto : texto.test(t(x.text()))))
  if (!b) throw new Error(`Sem o botão "${texto}"`)
  return b
}
const campo = (w: VueWrapper, nome: string) => w.get<HTMLInputElement>(`input[data-campo="${nome}"]`)
const ultimoAviso = () => t(avisos.at(-1)?.mensagem ?? '')
const chamadas = (api: ReturnType<typeof apiFalsa>, metodo: string, caminho: string) => api.chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)

// ── Dados ───────────────────────────────────────────────────────────────────

const PLANOS: PlanoAssinatura[] = [
  { chave: 'essencial', nome: 'Essencial', preco: '149.00', contatos: 300 },
  { chave: 'profissional', nome: 'Profissional', preco: '349.00', contatos: 1500 },
  { chave: 'empresa', nome: 'Empresa', preco: '799.00', contatos: null },
]
const SUGERIDOS = { razao_social: 'Distribuidora Sol Nascente Ltda', documento: '11222333000181', email_cobranca: 'ana@sol.com.br', telefone: '5511987654321' }
const ASSINATURA = {
  plano: 'profissional',
  valor: '349.00',
  situacao: 'ativa',
  criada_em: '2026-10-01T15:00:00Z',
  cancelada_em: null,
  primeiro_vencimento: '2026-10-15',
  dados: { razao_social: 'Distribuidora Sol Nascente Ltda', documento: '11222333000181', email_cobranca: 'financeiro@sol.com.br', telefone: '5511987654321' },
}
const LINK = 'https://sandbox.asaas.com/i/abc123'

type ParcialEstado = Omit<Partial<EstadoAssinatura>, 'conta'> & { conta?: Partial<EstadoAssinatura['conta']> }
function estado(p: ParcialEstado = {}): EstadoAssinatura {
  return {
    contatos_ativos: 320,
    disponivel: true,
    planos: PLANOS,
    dados_sugeridos: SUGERIDOS,
    assinatura: null,
    fatura_aberta: null,
    cobrancas: [],
    ...p,
    conta: {
      situacao: 'teste',
      plano: 'profissional',
      teste_ate: '2026-10-15T14:30:00-03:00',
      pago_ate: null,
      atrasada_desde: null,
      liberada: true,
      pausa_em: null,
      ...p.conta,
    },
  }
}
/** Assinou no teste: a primeira fatura (pendente) vence no último dia do teste. */
const ASSINADA_NO_TESTE = () =>
  estado({ assinatura: ASSINATURA, fatura_aberta: { valor: '349.00', vencimento: '2026-10-15', situacao: 'pendente', link: LINK }, cobrancas: [{ valor: '349.00', vencimento: '2026-10-15', situacao: 'pendente', forma: null, pago_em: null, link: LINK }] })
const PAGA = () =>
  estado({
    assinatura: ASSINATURA,
    conta: { situacao: 'ativa', pago_ate: '2026-11-14' },
    cobrancas: [{ valor: '349.00', vencimento: '2026-10-15', situacao: 'paga', forma: 'pix', pago_em: '2026-10-01T15:00:00Z', link: LINK }],
  })

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  sessionStorage.clear()
  vi.useFakeTimers({ now: AGORA, toFake: ['Date'] })
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

// ── Assinatura: sem assinatura ──────────────────────────────────────────────

describe('Assinatura: sem assinatura', () => {
  it('mostra a situação (teste com a data de fim), o uso, os 3 planos e bloqueia o que não comporta os contatos', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({ 'GET /assinatura': () => estado() })
    const w = await abrir('/assinatura', AssinaturaView)
    expect(t(w.get('#t-situacao').text())).toBe('Teste grátis até 15/10/2026')
    expect(t(w.get('[data-selo-situacao]').text())).toBe('Em teste')
    expect(t(w.get('[data-uso]').text())).toBe('320 de 1.500')
    const radios = w.findAll<HTMLInputElement>('input[type="radio"]')
    expect(radios.map((r) => r.element.value)).toEqual(['essencial', 'profissional', 'empresa'])
    expect(radios.map((r) => r.element.disabled)).toEqual([true, false, false])
    expect(t(w.get('[data-plano="essencial"]').text())).toContain('Você tem 320 contatos ativos: este plano permite até 300.')
    expect(t(w.get('[data-plano="profissional"]').text())).toContain('Plano do seu teste')
    expect(t(w.get('[data-plano="empresa"]').text())).toContain('Contatos ativos sem limite')
    expect(t(w.get('[data-plano="empresa"]').text())).toContain('Envios, formulários e usuários ilimitados')
    // O formulário só aparece depois de escolher.
    expect(w.find('[data-form-assinar]').exists()).toBe(false)
  })

  it('escolher um plano abre o formulário com os dados da empresa (com máscaras) e o resumo da primeira fatura', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({ 'GET /assinatura': () => estado() })
    const w = await abrir('/assinatura', AssinaturaView)
    await w.get('input[value="profissional"]').setValue(true)
    expect(campo(w, 'razao_social').element.value).toBe('Distribuidora Sol Nascente Ltda')
    expect(campo(w, 'documento').element.value).toBe('11.222.333/0001-81')
    expect(campo(w, 'email_cobranca').element.value).toBe('ana@sol.com.br')
    expect(campo(w, 'telefone').element.value).toBe('(11) 98765-4321')
    expect(t(w.get('[data-resumo]').text())).toContain('Primeira fatura de R$ 349,00 com vencimento em 15/10/2026, no fim do teste. Ela cobre de 15/10 a 14/11/2026. Depois, todo dia 15.')
    expect(t(botao(w, /^Assinar/).text())).toBe('Assinar o plano Profissional')
    // Trocar o plano muda o resumo.
    await w.get('input[value="empresa"]').setValue(true)
    expect(t(w.get('[data-resumo]').text())).toContain('Primeira fatura de R$ 799,00')
    // A máscara vale ao digitar.
    await campo(w, 'documento').setValue('52998224725')
    expect(campo(w, 'documento').element.value).toBe('529.982.247-25')
  })

  it('teste encerrado: a fatura vence amanhã e os envios voltam com o pagamento', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({ 'GET /assinatura': () => estado({ conta: { situacao: 'teste_expirado', teste_ate: '2026-09-20T10:00:00-03:00', liberada: false }, contatos_ativos: 40 }) })
    const w = await abrir('/assinatura', AssinaturaView)
    expect(t(w.get('#t-situacao').text())).toBe('Seu teste grátis terminou em 20/09/2026')
    await w.get('input[value="essencial"]').setValue(true)
    const resumo = t(w.get('[data-resumo]').text())
    expect(resumo).toContain('Primeira fatura de R$ 149,00 com vencimento amanhã, 02/10/2026. Ela cobre de 02/10 a 01/11/2026. Depois, todo dia 2.')
    expect(resumo).toContain('Os envios voltam assim que o pagamento for confirmado: Pix e cartão em segundos, boleto em até 3 dias úteis.')
  })

  it('confere os campos antes de enviar (todos obrigatórios) e não chama a API', async () => {
    entrar(['assinatura.gerenciar'])
    const api = apiFalsa({ 'GET /assinatura': () => estado({ dados_sugeridos: { razao_social: null, documento: null, email_cobranca: 'ana@sol.com.br', telefone: null } }) })
    const w = await abrir('/assinatura', AssinaturaView)
    await w.get('input[value="profissional"]').setValue(true)
    await w.get('[data-form-assinar] form').trigger('submit')
    await flushPromises()
    expect(chamadas(api, 'POST', '/assinatura')).toHaveLength(0)
    expect(t(w.get('[data-form-assinar] [role="alert"]').text())).toBe('Confira os campos destacados.')
    expect(campo(w, 'razao_social').attributes('aria-invalid')).toBe('true')
    expect(t(w.text())).toContain('Informe a razão social (ou o nome completo, para CPF).')
    expect(t(w.text())).toContain('Informe o CPF ou o CNPJ.')
    expect(t(w.text())).toContain('Informe o telefone com DDD.')
    // O foco vai para o primeiro campo com erro.
    expect(document.activeElement).toBe(campo(w, 'razao_social').element)
  })

  it('assinar: envia plano e dados só com dígitos, mostra a fatura com "Pagar" e atualiza a sessão', async () => {
    entrar(['assinatura.gerenciar'])
    const api = apiFalsa({
      'GET /assinatura': () => estado(),
      'POST /assinatura': () => ASSINADA_NO_TESTE(),
      'GET /eu': () => DADOS_EU(),
    })
    const w = await abrir('/assinatura', AssinaturaView)
    await w.get('input[value="profissional"]').setValue(true)
    await campo(w, 'email_cobranca').setValue('financeiro@sol.com.br')
    await w.get('[data-form-assinar] form').trigger('submit')
    await flushPromises()
    expect(chamadas(api, 'POST', '/assinatura')[0]!.corpo).toEqual({
      plano: 'profissional',
      razao_social: 'Distribuidora Sol Nascente Ltda',
      documento: '11222333000181',
      email_cobranca: 'financeiro@sol.com.br',
      telefone: '11987654321',
    })
    expect(ultimoAviso()).toBe('Assinatura feita! A primeira fatura vence em 15/10/2026.')
    expect(chamadas(api, 'GET', '/eu')).toHaveLength(1)
    // A tela passa a mostrar a assinatura.
    expect(w.find('[data-form-assinar]').exists()).toBe(false)
    expect(t(w.get('#t-situacao').text())).toBe('Plano Profissional')
    const pagar = w.get('a[data-pagar]')
    expect(pagar.attributes('href')).toBe(LINK)
    expect(pagar.attributes('target')).toBe('_blank')
    expect(pagar.attributes('rel')).toContain('noopener')
    expect(t(pagar.text())).toBe('Pagar (abre em nova aba)')
    expect(t(w.get('[data-fatura-aberta]').text())).toContain('R$ 349,00, vence em 15/10/2026 e cobre de 15/10 a 14/11/2026.')
    expect(document.activeElement?.id).toBe('t-fatura')
  })

  it('depois de assinar, busca de novo a cada 10 s; quando a fatura é paga, avisa, atualiza a sessão e para', async () => {
    vi.useFakeTimers({ now: AGORA, toFake: ['Date', 'setTimeout', 'clearTimeout'] })
    entrar(['assinatura.gerenciar'])
    let respostaGet = estado()
    const api = apiFalsa({
      'GET /assinatura': () => respostaGet,
      'POST /assinatura': () => ASSINADA_NO_TESTE(),
      'GET /eu': () => DADOS_EU(),
    })
    const w = await abrir('/assinatura', AssinaturaView)
    await w.get('input[value="profissional"]').setValue(true)
    await w.get('[data-form-assinar] form').trigger('submit')
    await flushPromises()
    expect(t(w.get('[data-espera]').text())).toBe('Esperando a confirmação do pagamento: a tela se atualiza sozinha.')
    respostaGet = ASSINADA_NO_TESTE()
    await vi.advanceTimersByTimeAsync(10_000)
    expect(chamadas(api, 'GET', '/assinatura')).toHaveLength(2)
    respostaGet = PAGA()
    await vi.advanceTimersByTimeAsync(10_000)
    expect(chamadas(api, 'GET', '/assinatura')).toHaveLength(3)
    expect(ultimoAviso()).toBe('Pagamento confirmado. Sua assinatura está ativa.')
    // A sessão foi buscada ao assinar e de novo quando a conta ficou ativa.
    expect(chamadas(api, 'GET', '/eu')).toHaveLength(2)
    expect(w.find('[data-fatura-aberta]').exists()).toBe(false)
    expect(t(w.get('[data-selo-situacao]').text())).toBe('Ativa')
    await vi.advanceTimersByTimeAsync(60_000)
    expect(chamadas(api, 'GET', '/assinatura')).toHaveLength(3)
  })

  it('a espera dura no máximo 2 minutos com a fatura ainda em aberto', async () => {
    vi.useFakeTimers({ now: AGORA, toFake: ['Date', 'setTimeout', 'clearTimeout'] })
    entrar(['assinatura.gerenciar'])
    const api = apiFalsa({ 'GET /assinatura': () => ASSINADA_NO_TESTE(), 'GET /eu': () => DADOS_EU() })
    const w = await abrir('/assinatura', AssinaturaView)
    // Clicar em "Pagar" (a fatura abre em outra aba) começa a espera.
    document.addEventListener('click', (e) => e.preventDefault(), { capture: true, once: true })
    await w.get('a[data-pagar]').trigger('click')
    await vi.advanceTimersByTimeAsync(120_000)
    expect(chamadas(api, 'GET', '/assinatura')).toHaveLength(1 + 12)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(chamadas(api, 'GET', '/assinatura')).toHaveLength(1 + 12)
    expect(t(w.get('[data-espera]').text())).toContain('Pagou? A confirmação chega sozinha')
  })

  it('erros da API: campo recusado pelo Asaas, limite do plano e cobrança fora do ar', async () => {
    entrar(['assinatura.gerenciar'])
    let resposta: Response = new Response()
    apiFalsa({ 'GET /assinatura': () => estado(), 'POST /assinatura': () => resposta })
    const w = await abrir('/assinatura', AssinaturaView)
    await w.get('input[value="profissional"]').setValue(true)
    const enviar = async (status: number, erro: Record<string, unknown>) => {
      resposta = new Response(JSON.stringify({ erro }), { status })
      await w.get('[data-form-assinar] form').trigger('submit')
      await flushPromises()
    }
    await enviar(422, { codigo: 'cobranca_recusada', mensagem: 'Confira os campos destacados.', campos: { documento: 'O Asaas recusou este CPF/CNPJ. Confira os números.' } })
    expect(campo(w, 'documento').attributes('aria-invalid')).toBe('true')
    expect(t(w.text())).toContain('O Asaas recusou este CPF/CNPJ. Confira os números.')
    await enviar(422, { codigo: 'limite_do_plano', mensagem: 'Você tem 320 contatos ativos; o plano Essencial permite até 300. Desative contatos antes de assinar.' })
    expect(t(w.get('[data-form-assinar] [role="status"]').text())).toContain('Desative contatos antes de assinar.')
    await enviar(503, { codigo: 'cobranca_indisponivel', mensagem: 'A cobrança está temporariamente indisponível. Tente de novo em alguns minutos.' })
    expect(t(w.get('[data-form-assinar] [role="alert"]').text())).toBe('A cobrança está temporariamente indisponível. Tente de novo em alguns minutos.')
  })

  it('409 "já assinada" (outra aba): avisa e mostra a assinatura como está agora', async () => {
    entrar(['assinatura.gerenciar'])
    let atual = estado()
    apiFalsa({
      'GET /assinatura': () => atual,
      'POST /assinatura': () => {
        atual = ASSINADA_NO_TESTE()
        return new Response(JSON.stringify({ erro: { codigo: 'ja_assinada', mensagem: 'Sua conta já tem uma assinatura ativa.' } }), { status: 409 })
      },
    })
    const w = await abrir('/assinatura', AssinaturaView)
    await w.get('input[value="profissional"]').setValue(true)
    await w.get('[data-form-assinar] form').trigger('submit')
    await flushPromises()
    expect(ultimoAviso()).toBe('Sua conta já tem uma assinatura ativa.')
    expect(w.find('[data-fatura-aberta]').exists()).toBe(true)
  })

  it('cobrança online indisponível: avisa e não deixa escolher plano', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({ 'GET /assinatura': () => estado({ disponivel: false }) })
    const w = await abrir('/assinatura', AssinaturaView)
    expect(t(w.get('[data-indisponivel]').text())).toBe('A cobrança online ainda não está disponível. Fale com a equipe Toqqi.')
    expect(w.findAll<HTMLInputElement>('input[type="radio"]').every((r) => r.element.disabled)).toBe(true)
  })

  it('cortesia: não mostra planos', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({ 'GET /assinatura': () => estado({ conta: { situacao: 'cortesia', teste_ate: null } }) })
    const w = await abrir('/assinatura', AssinaturaView)
    expect(t(w.get('#t-situacao').text())).toBe('Conta cortesia')
    expect(t(w.get('[data-uso]').text())).toBe('320 (sem limite)')
    expect(w.find('input[type="radio"]').exists()).toBe(false)
  })

  it('erro ao carregar, com "Tentar de novo"', async () => {
    entrar(['assinatura.gerenciar'])
    let falhar = true
    apiFalsa({ 'GET /assinatura': () => (falhar ? new Response('{}', { status: 500 }) : estado()) })
    const w = await abrir('/assinatura', AssinaturaView)
    expect(t(w.get('[role="alert"]').text())).toContain('Algo deu errado do nosso lado.')
    falhar = false
    await botao(w, 'Tentar de novo').trigger('click')
    await flushPromises()
    expect(t(w.get('#t-situacao').text())).toBe('Teste grátis até 15/10/2026')
  })
})

// ── Assinatura: com assinatura ──────────────────────────────────────────────

describe('Assinatura: com assinatura', () => {
  const COM_HISTORICO = () =>
    estado({
      assinatura: ASSINATURA,
      conta: { situacao: 'ativa', pago_ate: '2026-11-14' },
      cobrancas: [
        { valor: '349.00', vencimento: '2026-10-15', situacao: 'paga', forma: 'pix', pago_em: '2026-10-01T15:00:00Z', link: LINK },
        { valor: '149.00', vencimento: '2026-09-15', situacao: 'removida', forma: null, pago_em: null, link: 'https://sandbox.asaas.com/i/velha' },
      ],
    })

  it('plano, selo, valor, próximo vencimento, dados de cobrança e histórico', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({ 'GET /assinatura': () => COM_HISTORICO() })
    const w = await abrir('/assinatura', AssinaturaView)
    const topo = w.get('[data-situacao-conta]')
    expect(t(w.get('#t-situacao').text())).toBe('Plano Profissional')
    expect(t(w.get('[data-selo-situacao]').text())).toBe('Ativa')
    expect(t(topo.text())).toContain('Pago até 14/11/2026.')
    expect(t(topo.text())).toContain('R$ 349,00 por mês')
    expect(t(w.get('[data-proximo-vencimento]').text())).toBe('15/11/2026')
    const dados = t(w.get('[data-dados-cobranca]').text())
    expect(dados).toContain('11.222.333/0001-81')
    expect(dados).toContain('(11) 98765-4321')
    expect(dados).toContain('financeiro@sol.com.br')
    // Histórico (tabela e cartões): a fatura cancelada não tem link.
    const linhas = w.findAll('[data-historico] tbody tr')
    expect(linhas).toHaveLength(2)
    expect(t(linhas[0]!.text())).toContain('15/10/2026')
    expect(t(linhas[0]!.get('[data-periodo]').text())).toBe('cobre 15/10 a 14/11')
    expect(t(linhas[0]!.get('[data-pago-em]').text())).toBe('em 01/10/2026')
    expect(t(linhas[0]!.text())).toContain('Pix')
    expect(t(linhas[0]!.text())).toContain('Paga')
    expect(linhas[0]!.find('a').attributes('href')).toBe(LINK)
    expect(t(linhas[1]!.text())).toContain('Cancelada')
    expect(linhas[1]!.find('a').exists()).toBe(false)
    expect(t(linhas[1]!.get('[data-periodo]').text())).toBe('cobre 15/09 a 14/10')
    expect(linhas[1]!.find('[data-pago-em]').exists()).toBe(false)
    const cartoes = w.findAll('[data-historico] li')
    expect(cartoes).toHaveLength(2)
    expect(t(cartoes[0]!.text())).toContain('Cobre de 15/10 a 14/11/2026')
    expect(w.find('input[type="radio"]').exists()).toBe(false)
  })

  it('fatura vencida: selo "Atrasada", quando os envios param e "Pagar"', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({
      'GET /assinatura': () =>
        estado({
          assinatura: ASSINATURA,
          conta: { situacao: 'atrasada', pago_ate: '2026-10-14', atrasada_desde: '2026-09-28', pausa_em: '2026-10-06T03:00:00Z' },
          fatura_aberta: { valor: '349.00', vencimento: '2026-09-28', situacao: 'vencida', link: LINK },
        }),
    })
    const w = await abrir('/assinatura', AssinaturaView)
    expect(t(w.get('[data-selo-situacao]').text())).toBe('Atrasada')
    expect(t(w.get('[data-situacao-conta]').text())).toContain('A fatura venceu em 28/09/2026. Os envios param em 06/10/2026 se ela não for paga.')
    expect(t(w.get('[data-fatura-aberta]').text())).toContain('R$ 349,00, venceu em 28/09/2026 e cobre de 28/09 a 27/10/2026.')
    expect(w.find('[data-proximo-vencimento]').exists()).toBe(false)
  })

  it('trocar de plano: mostra o novo valor e o efeito na fatura; plano menor com contatos demais avisa e não deixa', async () => {
    entrar(['assinatura.gerenciar', 'contatos.ver'])
    const api = apiFalsa({
      'GET /assinatura': () => ASSINADA_NO_TESTE(),
      'PUT /assinatura/plano': () => estado({ ...ASSINADA_NO_TESTE(), assinatura: { ...ASSINATURA, plano: 'empresa', valor: '799.00' } }),
      'GET /eu': () => DADOS_EU(),
    })
    const w = await abrir('/assinatura', AssinaturaView)
    await botao(w, 'Trocar de plano').trigger('click')
    // (O stub do Teleport recria o conteúdo da janela a cada mudança: procura de novo a cada passo.)
    const janela = () => w.get('[role="dialog"]')
    expect(janela().findAll<HTMLInputElement>('input[type="radio"]').map((r) => r.element.checked)).toEqual([false, true, false])
    expect(t(janela().get('[data-plano="profissional"]').text())).toContain('Plano atual')
    expect(botao(janela(), 'Trocar de plano').attributes('disabled')).toBeDefined()
    // Plano menor: aviso e botão travado.
    await janela().get('input[value="essencial"]').setValue(true)
    expect(t(janela().text())).toContain('Você tem 320 contatos ativos; o plano Essencial permite até 300. Desative contatos antes de trocar.')
    expect(janela().get('a[href="/contatos"]').text()).toBe('Ver contatos')
    expect(botao(janela(), 'Trocar para o Essencial').attributes('disabled')).toBeDefined()
    // Plano maior: novo valor e a fatura em aberto junto.
    await janela().get('input[value="empresa"]').setValue(true)
    const efeito = t(janela().get('[data-efeito]').text())
    expect(efeito).toContain('O valor passa de R$ 349,00 para R$ 799,00 por mês.')
    expect(efeito).toContain('A fatura pendente, que vence em 15/10/2026, também passa para R$ 799,00.')
    expect(efeito).toContain('Os contatos ativos ficam sem limite (hoje você tem 320).')
    expect(botao(janela(), 'Trocar para o Empresa').attributes('disabled')).toBeUndefined()
    await janela().get('form').trigger('submit')
    await flushPromises()
    expect(chamadas(api, 'PUT', '/assinatura/plano')[0]!.corpo).toEqual({ plano: 'empresa' })
    expect(ultimoAviso()).toBe('Plano trocado para Empresa.')
    expect(chamadas(api, 'GET', '/eu')).toHaveLength(1)
    expect(t(w.get('#t-situacao').text())).toBe('Plano Empresa')
    expect(w.find('[role="dialog"]').exists()).toBe(false)
  })

  it('dados de cobrança: salvar fica travado sem mudança; mudou, manda só dígitos', async () => {
    entrar(['assinatura.gerenciar'])
    const api = apiFalsa({
      'GET /assinatura': () => PAGA(),
      'PUT /assinatura/dados': (c) => estado({ ...PAGA(), assinatura: { ...ASSINATURA, dados: c.corpo as typeof ASSINATURA.dados } }),
    })
    const w = await abrir('/assinatura', AssinaturaView)
    await botao(w, 'Editar dados de cobrança').trigger('click')
    const janela = () => w.get('[role="dialog"]')
    expect((janela().get('input[data-campo="email_cobranca"]').element as HTMLInputElement).value).toBe('financeiro@sol.com.br')
    expect(botao(janela(), 'Salvar dados').attributes('disabled')).toBeDefined()
    await janela().get('input[data-campo="telefone"]').setValue('21987650000')
    expect((janela().get('input[data-campo="telefone"]').element as HTMLInputElement).value).toBe('(21) 98765-0000')
    expect(botao(janela(), 'Salvar dados').attributes('disabled')).toBeUndefined()
    await janela().get('form').trigger('submit')
    await flushPromises()
    expect(chamadas(api, 'PUT', '/assinatura/dados')[0]!.corpo).toEqual({
      razao_social: 'Distribuidora Sol Nascente Ltda',
      documento: '11222333000181',
      email_cobranca: 'financeiro@sol.com.br',
      telefone: '21987650000',
    })
    expect(ultimoAviso()).toBe('Dados de cobrança salvos.')
    expect(t(w.get('[data-dados-cobranca]').text())).toContain('(21) 98765-0000')
  })

  it('cancelar: confirma com a data até quando usa, sem multa; depois volta a mostrar os planos', async () => {
    entrar(['assinatura.gerenciar'])
    const api = apiFalsa({
      'GET /assinatura': () => PAGA(),
      'POST /assinatura/cancelar': () => estado({ conta: { situacao: 'cancelada', pago_ate: '2026-11-14', liberada: true, teste_ate: null }, cobrancas: PAGA().cobrancas }),
      'GET /eu': () => DADOS_EU({ tipo: 'cancelada', data: '2026-11-14', dias: 44 }),
    })
    const w = await abrir('/assinatura', AssinaturaView)
    await botao(w, 'Cancelar assinatura').trigger('click')
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Cancelar a assinatura?')
    expect(estadoConfirmacao.mensagem).toBe('Você continua usando até 14/11/2026. Sem multa e sem devolução.')
    expect(estadoConfirmacao.perigo).toBe(true)
    responderConfirmacao(true)
    await flushPromises()
    expect(chamadas(api, 'POST', '/assinatura/cancelar')).toHaveLength(1)
    expect(ultimoAviso()).toBe('Assinatura cancelada. Você usa até 14/11/2026.')
    // uma ao abrir (a sessão do teste dizia "teste" e a tela, "ativa": sincroniza) e outra depois de cancelar
    expect(chamadas(api, 'GET', '/eu')).toHaveLength(2)
    expect(t(w.get('#t-situacao').text())).toBe('Assinatura cancelada')
    expect(w.findAll('input[type="radio"]')).toHaveLength(3)
    // O histórico continua.
    expect(w.findAll('[data-historico] tbody tr')).toHaveLength(1)
  })

  it('cancelar no teste, antes de pagar: volta para o teste', async () => {
    entrar(['assinatura.gerenciar'])
    apiFalsa({ 'GET /assinatura': () => ASSINADA_NO_TESTE() })
    const w = await abrir('/assinatura', AssinaturaView)
    await botao(w, 'Cancelar assinatura').trigger('click')
    expect(estadoConfirmacao.mensagem).toBe('Você volta para o teste grátis, que vai até 15/10/2026. Sem multa. A fatura em aberto é cancelada no Asaas.')
  })
})

// ── Aviso do topo ───────────────────────────────────────────────────────────

describe('aviso do topo das telas', () => {
  it('teste acabando: texto, "Escolher plano" para quem cuida da assinatura e fechar até a próxima sessão', async () => {
    entrar(['assinatura.gerenciar'], { aviso: { tipo: 'teste_acabando', data: '2026-10-04', dias: 3 } })
    let w = await montar(AvisoCobranca)
    const aviso = w.get('[data-aviso-cobranca]')
    expect(aviso.attributes('aria-label')).toBe('Aviso sobre a assinatura')
    expect(t(aviso.text())).toContain('Seu teste grátis termina em 3 dias.')
    const acao = w.get('[data-acao-aviso]')
    expect(t(acao.text())).toBe('Escolher plano')
    expect(acao.attributes('href')).toBe('/assinatura')
    await w.get('button[aria-label="Fechar aviso"]').trigger('click')
    expect(w.find('[data-aviso-cobranca]').exists()).toBe(false)
    w.unmount()
    w = await montar(AvisoCobranca)
    expect(w.find('[data-aviso-cobranca]').exists()).toBe(false)
    // Mudou o aviso (um dia a menos): aparece de novo.
    w.unmount()
    useSessaoStore().atualizarConta({ cobranca: { liberada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: { tipo: 'teste_acabando', data: '2026-10-04', dias: 2 } } })
    w = await montar(AvisoCobranca)
    expect(t(w.get('[data-aviso-cobranca]').text())).toContain('Seu teste grátis termina em 2 dias.')
  })

  it('atrasada para quem não cuida da assinatura: "Fale com o administrador da conta.", sem botão e sem fechar', async () => {
    entrar(['painel.ver'], { perfil: 'gestor', aviso: { tipo: 'atrasada', data: '2026-10-18', dias: 5 }, atrasadaDesde: '2026-10-10' })
    const w = await montar(AvisoCobranca)
    expect(t(w.get('[data-aviso-cobranca]').text())).toBe('A fatura venceu em 10/10. Os envios param em 18/10 se ela não for paga. Fale com o administrador da conta.')
    expect(w.find('[data-acao-aviso]').exists()).toBe(false)
    expect(w.find('button[aria-label="Fechar aviso"]').exists()).toBe(false)
  })

  it('pausada: "Pagar agora"; na própria tela de Assinatura o aviso não aparece (a tela já mostra a situação)', async () => {
    entrar(['assinatura.gerenciar'], { aviso: { tipo: 'pausada', data: '2026-10-10', dias: null } })
    let w = await montar(AvisoCobranca)
    expect(t(w.get('[data-aviso-cobranca]').text())).toContain('Envios pausados por falta de pagamento.')
    expect(t(w.get('[data-acao-aviso]').text())).toBe('Pagar agora')
    w.unmount()
    w = await montar(AvisoCobranca, '/assinatura')
    expect(w.find('[data-aviso-cobranca]').exists()).toBe(false)
  })

  it('sem aviso (ou servidor sem `cobranca`), nada', async () => {
    entrar(['assinatura.gerenciar'])
    const w = await montar(AvisoCobranca)
    expect(w.find('[data-aviso-cobranca]').exists()).toBe(false)
  })
})

// ── Limite de contatos ──────────────────────────────────────────────────────

describe('mensagem de limite de contatos', () => {
  it('quem cuida da assinatura vê "Ver planos"; os outros, para falar com o administrador', async () => {
    entrar(['assinatura.gerenciar'])
    let w = await montar(AlertaLimitePlano, '/contatos', { mensagem: 'Seu plano permite até 300 contatos ativos.' })
    expect(t(w.text())).toContain('Seu plano permite até 300 contatos ativos. Para cadastrar mais, troque para um plano maior')
    expect(t(w.get('a[href="/assinatura"]').text())).toBe('Ver planos')
    w.unmount()
    entrar(['contatos.editar'], { perfil: 'gestor' })
    w = await montar(AlertaLimitePlano, '/contatos', { mensagem: 'Seu plano permite até 300 contatos ativos.' })
    expect(t(w.text())).toContain('peça ao administrador da conta para trocar de plano')
    expect(w.find('a[href="/assinatura"]').exists()).toBe(false)
  })
})

// ── Plataforma ──────────────────────────────────────────────────────────────

describe('Plataforma (etapa 5a)', () => {
  const conta = (c: Partial<ContaPlataforma>): ContaPlataforma => ({
    id: 1,
    nome: 'Conta',
    plano: 'profissional',
    situacao: 'teste',
    teste_ate: '2026-10-15T14:30:00-03:00',
    usuarios: 2,
    criada_em: '2026-09-01T10:00:00Z',
    pago_ate: null,
    atrasada_desde: null,
    assinatura: null,
    ...c,
  })
  const CONTAS = [
    conta({ id: 2, nome: 'Assinante', situacao: 'ativa', pago_ate: '2026-11-14', assinatura: { plano: 'profissional', valor: '349.00', situacao: 'ativa' } }),
    conta({ id: 3, nome: 'Devedora', situacao: 'atrasada', atrasada_desde: '2026-09-28', assinatura: { plano: 'essencial', valor: '149.00', situacao: 'ativa' } }),
    conta({ id: 4, nome: 'Expirada', situacao: 'teste_expirado', teste_ate: '2026-09-20T10:00:00-03:00' }),
    conta({ id: 5, nome: 'Amiga', situacao: 'cortesia', teste_ate: null, plano: null }),
  ]
  const linha = (w: VueWrapper, nome: string) => w.findAll('tbody tr').find((tr) => tr.text().includes(nome))!

  it('selos das situações novas, assinatura com valor, "pago até" e "+14 dias" travado com assinatura ou cortesia', async () => {
    entrar([], { superadmin: true })
    apiFalsa({ 'GET /plataforma/contas': () => CONTAS })
    const w = await abrir('/plataforma', PlataformaView)
    expect(t(linha(w, 'Assinante').text())).toContain('Ativa')
    expect(t(linha(w, 'Assinante').text())).toContain('Profissional · R$ 349,00/mês')
    expect(t(linha(w, 'Assinante').find('td:nth-child(3)').text())).toBe('ProfissionalR$ 349,00/mês')
    expect(t(linha(w, 'Assinante').text())).toContain('Pago até 14/11/2026')
    expect(t(linha(w, 'Devedora').text())).toContain('Atrasada')
    expect(t(linha(w, 'Devedora').text())).toContain('Vencida em 28/09/2026')
    expect(t(linha(w, 'Expirada').text())).toContain('Teste encerrado')
    expect(t(linha(w, 'Expirada').text())).toContain('Sem assinatura (plano Profissional)')
    expect(t(linha(w, 'Expirada').text())).toContain('Teste até 20/09/2026')
    expect(t(linha(w, 'Expirada').text())).toContain('2 usuários · criada em 01/09/2026')
    expect(t(linha(w, 'Amiga').text())).toContain('Cortesia')
    const estender = (nome: string) => linha(w, nome).findAll('button').find((b) => b.text().includes('+14 dias'))!
    expect(estender('Assinante').attributes('disabled')).toBeDefined()
    expect(t(estender('Assinante').text())).toContain('indisponível: Conta com assinatura ativa')
    expect(estender('Amiga').attributes('disabled')).toBeDefined()
    expect(estender('Expirada').attributes('disabled')).toBeUndefined()
    // Teste que já acabou: os 14 dias contam de hoje.
    await estender('Expirada').trigger('click')
    expect(estadoConfirmacao.mensagem).toBe('O teste acabou em 20/09/2026. Os 14 dias contam a partir de hoje.')
  })

  it('cortesia numa conta com assinatura avisa que a assinatura no Asaas será cancelada', async () => {
    entrar([], { superadmin: true })
    apiFalsa({ 'GET /plataforma/contas': () => CONTAS })
    const w = await abrir('/plataforma', PlataformaView)
    await linha(w, 'Assinante').findAll('button').find((b) => b.text().includes('Cortesia'))!.trigger('click')
    expect(t(estadoConfirmacao.mensagem ?? '')).toBe(
      'A conta passa a usar o Toqqi sem cobrança, sem data para acabar. A assinatura no Asaas (Profissional · R$ 349,00/mês) será cancelada, com as faturas em aberto.',
    )
    expect(estadoConfirmacao.confirmar).toBe('Cancelar a assinatura e dar cortesia')
    expect(estadoConfirmacao.perigo).toBe(true)
    responderConfirmacao(false)
    await linha(w, 'Expirada').findAll('button').find((b) => b.text().includes('Cortesia'))!.trigger('click')
    expect(estadoConfirmacao.mensagem).toBe('A conta passa a usar o Toqqi sem cobrança, sem data para acabar.')
  })
})

// ── Menu, rota e botão de link externo ──────────────────────────────────────

describe('menu e rota da Assinatura', () => {
  it('rota só com assinatura.gerenciar; item em Administração só para quem pode', () => {
    expect(rotasDoApp.resolve('/assinatura').meta.permissao).toBe('assinatura.gerenciar')
    const rotulos = (permissoes: string[]) => filtrarNavegacao(navegacaoAdministracao, (p) => permissoes.includes(p), false, false).map((i) => i.rotulo)
    expect(rotulos(['assinatura.gerenciar'])).toContain('Assinatura')
    expect(rotulos(['painel.ver'])).not.toContain('Assinatura')
  })

  it('Botao com href abre outro site em nova aba e avisa o leitor de tela', () => {
    const w = mount(Botao, { props: { href: 'https://www.asaas.com/i/1' }, slots: { default: 'Pagar' } })
    const a = w.get('a')
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toBe('noopener noreferrer')
    expect(t(a.text())).toBe('Pagar (abre em nova aba)')
    expect(a.get('.sr-only').text()).toBe('(abre em nova aba)')
  })
})
