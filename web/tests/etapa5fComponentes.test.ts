// Etapa 5f com a API simulada (docs/api-etapa-5f.md §10): Configurações › Dados da conta (baixar tudo com o andamento
// anunciado, 409/429, contagens nos rádios, "Apagar…" desligado sem nada para apagar, diálogo com APAGAR em qualquer
// caixa, sucesso que relê as contagens, erros, foco de volta ao gatilho, só administrador, livre com o aceite pendente),
// "Exportar CSV" em Contatos e Empresas com os filtros da aba (e sem permissão), o grupo em Auditoria › Atividades, o
// aviso de exclusão no topo, o selo da Plataforma e a nota do SAIR no guia do WhatsApp.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, type Component } from 'vue'
import type { Aceite, AvisoCobranca as TipoAviso, ContaPlataforma, Perfil, ResultadoZonaRisco, WhatsappIntegracao, ZonaRisco } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { router as rotasDoApp } from '@/router'
import AvisoCobranca from '@/components/app/AvisoCobranca.vue'
import AbaAtividades from '@/modulos/auditoria/AbaAtividades.vue'
import DadosContaView from '@/modulos/configuracoes/DadosContaView.vue'
import NavConfiguracoes from '@/modulos/configuracoes/NavConfiguracoes.vue'
import AbaContatos from '@/modulos/contatos/AbaContatos.vue'
import AbaEmpresas from '@/modulos/contatos/AbaEmpresas.vue'
import GuiaWhatsapp from '@/modulos/integracoes/GuiaWhatsapp.vue'
import PlataformaView from '@/modulos/plataforma/PlataformaView.vue'
import { apiFalsa, erro422 } from './apiFalsa'

const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

const ZONA: ZonaRisco = {
  opcoes: {
    respostas: { respostas: 1234, acoes_sem_vinculo: 56 },
    contatos: { contatos: 5000, respostas: 1234, convites: 12000, envios: 30500, csat_sem_contato: 340 },
    tudo: { contatos: 5000, respostas: 1234, convites: 12000, envios: 30500, csat_sem_contato: 340, empresas: 300, acoes: 800, indicacoes: 40, ofertas: 25 },
  },
  mantidos: { csat: 412, descadastros: 12, usuarios: 4, formularios: 3 },
}
/** Depois de apagar os contatos: só sobram as empresas, as ações, as indicações e as ofertas. */
const ZONA_DEPOIS: ZonaRisco = {
  opcoes: {
    respostas: { respostas: 0, acoes_sem_vinculo: 0 },
    contatos: { contatos: 0, respostas: 0, convites: 0, envios: 0, csat_sem_contato: 0 },
    tudo: { contatos: 0, respostas: 0, convites: 0, envios: 0, csat_sem_contato: 0, empresas: 300, acoes: 800, indicacoes: 40, ofertas: 25 },
  },
  mantidos: { csat: 412, descadastros: 12, usuarios: 4, formularios: 3 },
}

const USUARIO = { id: 1, nome: 'Ana Paula', email: 'ana@sol.com.br', cargo: null, situacao: 'ativo' as const, email_confirmado: true, ultimo_acesso: null, superadmin: false }

function entrar(
  permissoes: string[],
  opcoes: { perfil?: Perfil; exclusaoEm?: string | null; aviso?: TipoAviso | null; aceite?: Aceite; superadmin?: boolean } = {},
) {
  const s = useSessaoStore()
  s.definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { ...USUARIO, perfil: opcoes.perfil ?? 'admin', superadmin: !!opcoes.superadmin, aceite: opcoes.aceite },
      conta: {
        id: 1,
        nome: 'Distribuidora Sol',
        plano: 'profissional',
        situacao: 'teste_expirado',
        teste_ate: '2026-07-01T00:00:00-03:00',
        cobranca: { liberada: false, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: opcoes.aviso ?? null, exclusao_em: opcoes.exclusaoEm ?? null },
      },
      permissoes: permissoes as never,
    },
    false,
  )
  s.inicializada = true // a guarda do app não busca /eu de novo
  return s
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
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}
/** Componente solto (aviso, guia) com o router. */
async function montar(componente: Component, caminho = '/inicio', props: Record<string, unknown> = {}): Promise<VueWrapper> {
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })
  await router.push(caminho)
  await router.isReady()
  const w = mount(componente, { props, global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

/** Elementos fora do componente (o Modal vai para o <body>). */
const $ = (sel: string) => document.body.querySelector<HTMLElement>(sel)
const $$ = (sel: string) => Array.from(document.body.querySelectorAll<HTMLElement>(sel))
async function clicar(el: HTMLElement | null) {
  if (!el) throw new Error('Elemento não encontrado')
  el.click()
  await flushPromises()
}
async function digitar(el: HTMLElement | null, valor: string) {
  if (!(el instanceof HTMLInputElement)) throw new Error('Campo não encontrado')
  el.value = valor
  el.dispatchEvent(new Event('input'))
  await flushPromises()
}
const campoConfirmacao = () => $('[data-modal-zona] input') as HTMLInputElement | null
const botaoApagarParaSempre = () => $('[data-apagar-para-sempre]') as HTMLButtonElement | null
const chamadasDe = (api: ReturnType<typeof apiFalsa>, metodo: string, caminho: string) => api.chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)
const consulta = (c: { url: URL } | undefined) => Object.fromEntries(c?.url.searchParams.entries() ?? [])

/** Uma promessa que o teste resolve quando quiser (para ver o "Gerando o arquivo…"). */
function adiada<T>() {
  let resolver!: (v: T) => void
  const promessa = new Promise<T>((r) => (resolver = r))
  return { promessa, resolver }
}
const zip = () =>
  new Response('PK', {
    status: 200,
    headers: { 'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="toqqi-distribuidora-sol-2026-10-03.zip"' },
  })
const erro = (status: number, codigo: string, mensagem: string) => new Response(JSON.stringify({ erro: { codigo, mensagem } }), { status })

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  sessionStorage.clear()
  avisos.splice(0)
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  Element.prototype.scrollIntoView = vi.fn() as unknown as Element['scrollIntoView']
})
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

// ───────────────────────── Configurações › Dados da conta ─────────────────────────

function apiDados(extra: Record<string, Parameters<typeof apiFalsa>[0][string]> = {}) {
  return apiFalsa({
    'GET /conta/zona-de-risco': () => ZONA,
    'GET /conta/exportacao.zip': () => zip(),
    ...extra,
  })
}
const abrirDados = () => abrir('/configuracoes/dados-da-conta', DadosContaView)

describe('Configurações › Dados da conta › Exportar todos os dados', () => {
  it('"Baixar todos os dados" baixa o .zip; enquanto gera, "Gerando o arquivo…" numa região aria-live; depois, pronto', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    const espera = adiada<Response>()
    const api = apiDados({ 'GET /conta/exportacao.zip': () => espera.promessa })
    const w = await abrirDados()
    expect(t(w.get('h1').text())).toBe('Dados da conta')
    const secao = w.get('[data-exportar-tudo]')
    expect(t(secao.get('h2').text())).toBe('Exportar todos os dados')
    expect(t(secao.text())).toContain('Um arquivo .zip com uma planilha (CSV) por assunto. Senhas e chaves não vão.')
    const status = w.get('[data-status-exportacao]')
    expect(status.attributes('aria-live')).toBe('polite')
    expect(t(status.text())).toBe('')

    const botao = w.get('[data-baixar-tudo]')
    expect(t(botao.text())).toBe('Baixar todos os dados')
    await botao.trigger('click')
    await flushPromises()
    expect(t(w.get('[data-status-exportacao]').text())).toBe('Gerando o arquivo… pode levar até um minuto.')
    // Continua no Tab enquanto gera (aria-disabled, não disabled) e não pede de novo
    expect(w.get('[data-baixar-tudo]').attributes('aria-disabled')).toBe('true')
    expect(w.get('[data-baixar-tudo]').attributes('disabled')).toBeUndefined()
    await w.get('[data-baixar-tudo]').trigger('click')
    expect(chamadasDe(api, 'GET', '/conta/exportacao.zip')).toHaveLength(1)

    espera.resolver(zip())
    await flushPromises()
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(t(w.get('[data-status-exportacao]').text())).toBe('Pronto: o arquivo foi gerado. Confira os downloads do navegador.')
    expect(w.find('[data-erro-exportacao]').exists()).toBe(false)
  })

  it('409 (outra exportação) e 429 (5 por hora) aparecem num Alerta de erro', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    let resposta = () => erro(409, 'exportacao_em_andamento', 'Já tem uma exportação sendo gerada nesta conta. Aguarde terminar.')
    apiDados({ 'GET /conta/exportacao.zip': () => resposta() })
    const w = await abrirDados()
    await w.get('[data-baixar-tudo]').trigger('click')
    await flushPromises()
    const alerta = w.get('[data-erro-exportacao]')
    expect(alerta.attributes('role')).toBe('alert')
    expect(t(alerta.text())).toBe('Já tem uma exportação sendo gerada nesta conta. Aguarde terminar.')
    expect(t(w.get('[data-status-exportacao]').text())).toBe('')
    expect(URL.createObjectURL).not.toHaveBeenCalled()

    resposta = () => erro(429, 'muitas_tentativas', 'Limite excedido.')
    await w.get('[data-baixar-tudo]').trigger('click')
    await flushPromises()
    expect(t(w.get('[data-erro-exportacao]').text())).toBe('Você chegou ao limite de 5 exportações por hora. Tente de novo mais tarde.')
  })
})

describe('Configurações › Dados da conta › Zona de risco', () => {
  it('cartão com borda de erro; rádios num fieldset com legenda, com o que cada opção apaga e as contagens', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    apiDados()
    const w = await abrirDados()
    const zona = w.get('[data-zona-risco]')
    expect(zona.classes()).toContain('border-erro/40')
    expect(t(zona.get('h2').text())).toBe('Zona de risco')
    const fieldset = zona.get('fieldset')
    expect(t(fieldset.get('legend').text())).toBe('O que apagar')
    const radios = fieldset.findAll<HTMLInputElement>('input[type="radio"]')
    expect(radios).toHaveLength(3)
    // Cada rádio tem o nome (rótulo) e a descrição (o que apaga) ligados
    const nome = (r: (typeof radios)[number]) => t(document.getElementById(r.attributes('aria-labelledby')!)?.textContent)
    const descricao = (r: (typeof radios)[number]) => t(document.getElementById(r.attributes('aria-describedby')!)?.textContent)
    expect(radios.map(nome)).toEqual(['Respostas', 'Contatos', 'Recomeçar do zero'])
    expect(descricao(radios[0]!)).toBe('Apaga 1.234 respostas NPS e de formulários personalizados, inclusive arquivadas. 56 planos de ação ficam sem o vínculo.')
    expect(descricao(radios[1]!)).toContain('Apaga 5.000 contatos, 1.234 respostas NPS e de formulários personalizados, 12.000 convites e 30.500 envios')
    expect(descricao(radios[2]!)).toContain('Apaga 300 empresas, 5.000 contatos')
    // A primeira (a que apaga menos) vem escolhida
    expect(radios[0]!.element.checked).toBe(true)
    expect(radios.every((r) => r.attributes('name') === radios[0]!.attributes('name'))).toBe(true)
    expect(t(w.get('[data-sempre-fica]').text())).toBe(
      'Sempre fica: usuários, configurações, formulários, 412 respostas CSAT e a lista de descadastro (12).',
    )
    const apagar = w.get('[data-abrir-zona]')
    expect(t(apagar.text())).toBe('Apagar…')
    expect(apagar.attributes('aria-disabled')).toBeUndefined()
  })

  it('"Apagar…" fica desligado (e explica) quando a opção não apaga nada; outra opção liga', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    apiDados({ 'GET /conta/zona-de-risco': () => ZONA_DEPOIS })
    const w = await abrirDados()
    const apagar = () => w.get('[data-abrir-zona]')
    expect(apagar().attributes('aria-disabled')).toBe('true')
    const dica = apagar().attributes('aria-describedby')!
    expect(t(document.getElementById(dica)?.textContent)).toBe('Esta opção não tem nada para apagar.')
    await apagar().trigger('click')
    await flushPromises()
    expect($('[role="alertdialog"]')).toBeNull()

    await w.get('[data-opcao="tudo"] input').setValue(true)
    expect(apagar().attributes('aria-disabled')).toBeUndefined()
    expect(w.find('[data-texto-opcao]').exists()).toBe(true)
  })

  it('diálogo: alertdialog, "Isso não tem volta" com as contagens, APAGAR em qualquer caixa; sucesso fecha, resume, relê e devolve o foco', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    let leituras = 0
    const resultado: ResultadoZonaRisco = {
      opcao: 'contatos',
      apagados: { contatos: 5000, respostas: 1234, convites: 12000, envios: 30500, csat_sem_contato: 340 },
      mantidos: ZONA.mantidos,
    }
    const api = apiDados({
      'GET /conta/zona-de-risco': () => (leituras++ === 0 ? ZONA : ZONA_DEPOIS),
      'POST /conta/zona-de-risco': () => resultado,
    })
    const w = await abrirDados()
    await w.get('[data-opcao="contatos"] input').setValue(true)
    const gatilho = w.get('[data-abrir-zona]').element as HTMLButtonElement
    gatilho.focus()
    await clicar(gatilho)

    const dialogo = $('[role="alertdialog"]')!
    expect(dialogo.getAttribute('aria-modal')).toBe('true')
    expect(t(document.getElementById(dialogo.getAttribute('aria-labelledby')!)?.textContent)).toBe('Apagar os contatos?')
    const resumo = t($('[data-resumo-opcao]')?.closest('[role="alert"]')?.textContent)
    expect(resumo).toContain('Isso não tem volta')
    expect(resumo).toContain('Apaga 5.000 contatos, 1.234 respostas NPS e de formulários personalizados, 12.000 convites e 30.500 envios')
    expect(t($('[data-baixar-antes]')?.textContent)).toBe('Baixar todos os dados antes')

    // O campo: rótulo, sem autocompletar nem corretor
    const campo = campoConfirmacao()!
    expect(t(document.querySelector(`label[for="${campo.id}"]`)?.textContent)).toBe('Para confirmar, digite APAGAR')
    expect(campo.getAttribute('autocomplete')).toBe('off')
    expect(campo.getAttribute('spellcheck')).toBe('false')
    expect(campo.getAttribute('autocorrect')).toBe('off')
    expect(botaoApagarParaSempre()!.disabled).toBe(true)
    await digitar(campo, 'apaga')
    expect(botaoApagarParaSempre()!.disabled).toBe(true)
    await digitar(campo, '  apagar ')
    expect(botaoApagarParaSempre()!.disabled).toBe(false)
    expect(t(botaoApagarParaSempre()!.textContent)).toBe('Apagar para sempre')

    await clicar(botaoApagarParaSempre())
    expect(chamadasDe(api, 'POST', '/conta/zona-de-risco').map((c) => c.corpo)).toEqual([{ opcao: 'contatos', confirmacao: 'apagar' }])
    expect($('[role="alertdialog"]')).toBeNull()
    const regiao = w.get('[data-resultado-zona]')
    expect(regiao.attributes('aria-live')).toBe('polite')
    expect(t(regiao.text())).toBe('Pronto: apagamos 5.000 contatos, 1.234 respostas, 12.000 convites e 30.500 envios.')
    // Releu as contagens: a opção "Contatos" agora não tem nada para apagar
    expect(chamadasDe(api, 'GET', '/conta/zona-de-risco')).toHaveLength(2)
    expect(t(w.get('[data-opcao="contatos"] [data-texto-opcao]').text())).toBe('Não há contatos nem respostas para apagar.')
    expect(w.get('[data-abrir-zona]').attributes('aria-disabled')).toBe('true')
    // O foco voltou para o botão que abriu o diálogo (ele continua na página)
    expect(document.activeElement).toBe(w.get('[data-abrir-zona]').element)
  })

  it('erros: 422 no campo (o diálogo fica), 409 e 503 com a mensagem da API; Cancelar fecha e devolve o foco', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    let resposta: () => Response = () => erro422('Digite APAGAR para confirmar.', { confirmacao: 'Digite APAGAR para confirmar.' })
    apiDados({ 'POST /conta/zona-de-risco': () => resposta() })
    const w = await abrirDados()
    const gatilho = w.get('[data-abrir-zona]').element as HTMLButtonElement
    gatilho.focus()
    await clicar(gatilho)
    expect(t(document.getElementById($('[role="alertdialog"]')!.getAttribute('aria-labelledby')!)?.textContent)).toBe('Apagar as respostas?')

    await digitar(campoConfirmacao(), 'APAGAR')
    await clicar(botaoApagarParaSempre())
    expect($('[role="alertdialog"]')).not.toBeNull()
    expect(campoConfirmacao()!.getAttribute('aria-invalid')).toBe('true')
    expect(t($('[data-modal-zona]')?.textContent)).toContain('Digite APAGAR para confirmar.')
    expect(document.activeElement).toBe(campoConfirmacao())

    resposta = () => erro(409, 'zona_em_andamento', 'Já tem uma exclusão em andamento nesta conta. Aguarde terminar.')
    await clicar(botaoApagarParaSempre())
    expect(campoConfirmacao()!.getAttribute('aria-invalid')).toBeNull()
    expect($$('[data-modal-zona] [role="alert"]').map((a) => t(a.textContent))).toContain('Já tem uma exclusão em andamento nesta conta. Aguarde terminar.')

    const indisponivel = 'Não deu para apagar agora e nada foi apagado. Tente de novo em alguns minutos.'
    resposta = () => erro(503, 'zona_indisponivel', indisponivel)
    await clicar(botaoApagarParaSempre())
    expect($$('[data-modal-zona] [role="alert"]').map((a) => t(a.textContent))).toContain(indisponivel)
    expect(t(w.get('[data-resultado-zona]').text())).toBe('')

    const cancelar = $$('[role="alertdialog"] footer button').find((b) => t(b.textContent) === 'Cancelar')!
    await clicar(cancelar)
    expect($('[role="alertdialog"]')).toBeNull()
    expect(document.activeElement).toBe(gatilho)
    // Abrir de novo começa limpo
    await clicar(gatilho)
    expect(campoConfirmacao()!.value).toBe('')
    expect($$('[data-modal-zona] [role="alert"]').map((a) => t(a.textContent))).toEqual([expect.stringContaining('Isso não tem volta')])
  })

  it('"Baixar todos os dados antes", dentro do diálogo, baixa o .zip e anuncia o andamento ali mesmo', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    const espera = adiada<Response>()
    const api = apiDados({ 'GET /conta/exportacao.zip': () => espera.promessa })
    const w = await abrirDados()
    await w.get('[data-abrir-zona]').trigger('click')
    await flushPromises()
    const status = $('[data-status-exportacao-modal]')!
    expect(status.getAttribute('aria-live')).toBe('polite')
    await clicar($('[data-baixar-antes]'))
    expect(chamadasDe(api, 'GET', '/conta/exportacao.zip')).toHaveLength(1)
    expect(t($('[data-status-exportacao-modal]')?.textContent)).toBe('Gerando o arquivo… pode levar até um minuto.')
    expect($('[data-baixar-antes]')!.getAttribute('aria-disabled')).toBe('true')
    espera.resolver(zip())
    await flushPromises()
    expect(t($('[data-status-exportacao-modal]')?.textContent)).toBe('Pronto: o arquivo foi gerado. Confira os downloads do navegador.')
    expect($('[role="alertdialog"]')).not.toBeNull()
  })

  it('erro ao ler as contagens: Alerta com "Tentar de novo"', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    let falhar = true
    apiDados({ 'GET /conta/zona-de-risco': () => (falhar ? erro(500, 'erro', 'Falhou.') : ZONA) })
    const w = await abrirDados()
    expect(t(w.get('[data-erro-zona]').text())).toContain('Falhou.')
    expect(w.find('[data-abrir-zona]').exists()).toBe(false)
    falhar = false
    await w.get('[data-erro-zona] button').trigger('click')
    await flushPromises()
    expect(w.find('[data-erro-zona]').exists()).toBe(false)
    expect(w.findAll('[data-zona-risco] input[type="radio"]')).toHaveLength(3)
  })
})

describe('Dados da conta: rota, menu e aceite', () => {
  it('rota só do administrador (meta.admin); o gestor volta ao início com o aviso', async () => {
    expect(rotasDoApp.resolve('/configuracoes/dados-da-conta').meta).toMatchObject({ titulo: 'Dados da conta', admin: true })
    apiFalsa({ 'GET /conta/zona-de-risco': () => ZONA, 'GET /ajuda': () => ({ versao: 1, topicos: [] }) })
    entrar(['configuracoes.gerenciar', 'contatos.ver'], { perfil: 'gestor' })
    await rotasDoApp.push('/configuracoes/dados-da-conta')
    expect(rotasDoApp.currentRoute.value.path).toBe('/inicio')
    expect(avisos.map((a) => a.mensagem)).toContain('Só um administrador da sua empresa pode abrir essa página.')

    setActivePinia(createPinia())
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    await rotasDoApp.push('/configuracoes/dados-da-conta')
    expect(rotasDoApp.currentRoute.value.path).toBe('/configuracoes/dados-da-conta')
  })

  it('com o aceite pendente, o administrador abre Dados da conta; outra seção de Configurações volta ao aceite', async () => {
    apiFalsa({ 'GET /conta/zona-de-risco': () => ZONA, 'GET /ajuda': () => ({ versao: 1, topicos: [] }) })
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'], { aceite: { versao_atual: 4, versao_aceita: 3, aceito_em: '2026-10-02T12:00:00Z', pendente: true } })
    await rotasDoApp.push('/configuracoes/dados-da-conta')
    expect(rotasDoApp.currentRoute.value.path).toBe('/configuracoes/dados-da-conta')
    await rotasDoApp.push('/configuracoes/empresa')
    expect(rotasDoApp.currentRoute.value.fullPath).toBe('/aceite?de=/configuracoes/empresa')
  })

  it('"Dados da conta" (ícone) em Configurações só para o administrador', async () => {
    entrar(['configuracoes.gerenciar', 'zona_risco.usar'])
    apiFalsa({})
    let w = await montar(NavConfiguracoes, '/configuracoes/dados-da-conta')
    const link = w.findAll('a').find((a) => t(a.text()) === 'Dados da conta')!
    expect(link.attributes('href')).toBe('/configuracoes/dados-da-conta')
    expect(link.attributes('aria-current')).toBe('page')
    expect(link.find('svg[aria-hidden="true"]').exists()).toBe(true)
    w.unmount()

    setActivePinia(createPinia())
    entrar(['configuracoes.gerenciar', 'envios.ver'], { perfil: 'gestor' })
    w = await montar(NavConfiguracoes, '/configuracoes/empresa')
    expect(w.findAll('a').some((a) => t(a.text()) === 'Dados da conta')).toBe(false)
  })
})

// ───────────────────────── Exportar CSV em Contatos e Empresas ─────────────────────────

const csv = () => new Response('Código;Nome\r\n', { status: 200, headers: { 'Content-Type': 'text/csv' } })

function apiListas() {
  return apiFalsa({
    'GET /contatos': (c) => ({ itens: [], total: 0, pagina: Number(c.url.searchParams.get('pagina') ?? 1), por_pagina: 50 }),
    'GET /empresas': (c) => ({ itens: [], total: 0, pagina: Number(c.url.searchParams.get('pagina') ?? 1), por_pagina: 50 }),
    'GET /cadastros/grupos': () => [{ id: 3, nome: 'Varejo', em_uso: 2 }],
    'GET /cadastros/segmentos': () => [{ id: 5, nome: 'Supermercados', em_uso: 1 }],
    'GET /cadastros/perfis': () => [],
    'GET /responsaveis': () => [],
    'GET /contatos.csv': () => csv(),
    'GET /empresas.csv': () => csv(),
  })
}

describe('"Exportar CSV" em Contatos e Empresas', () => {
  it('Contatos: na barra de filtros, só o ícone no celular (aria-label) e os filtros da aba no CSV, iguais aos da lista', async () => {
    entrar(['contatos.ver', 'painel.exportar'], { perfil: 'gestor' })
    const api = apiListas()
    const w = await abrir('/contatos', AbaContatos)
    const botao = w.get('[data-exportar-csv]')
    expect(botao.attributes('aria-label')).toBe('Exportar CSV')
    expect(botao.find('svg').exists()).toBe(true)
    expect(botao.get('span').classes()).toEqual(expect.arrayContaining(['hidden', 'sm:inline']))
    expect(t(botao.text())).toBe('Exportar CSV')

    // Filtros: "Todos", a busca e o grupo
    const todos = w.findAll('[role="radiogroup"] [role="radio"]').find((r) => t(r.text()) === 'Todos')!
    await todos.trigger('click')
    await w.get('input[type="search"]').setValue('  ana ')
    await w.get('#filtros-contatos select').setValue('3')
    await flushPromises()
    await botao.trigger('click')
    await flushPromises()
    const pedido = chamadasDe(api, 'GET', '/contatos.csv')
    expect(pedido).toHaveLength(1)
    expect(consulta(pedido[0])).toEqual({ busca: 'ana', grupo_id: '3', ativo: 'todos' })
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    // CSV = a lista: a mesma consulta do último GET /contatos, sem a página
    await new Promise((r) => setTimeout(r, 350)) // a busca da lista espera a pessoa parar de digitar
    await flushPromises()
    const { pagina: _p, ...daLista } = consulta(chamadasDe(api, 'GET', '/contatos').at(-1))
    expect(daLista).toEqual(consulta(pedido[0]))
  })

  it('Contatos: sem painel.exportar não há o botão; erro do CSV vira aviso', async () => {
    entrar(['contatos.ver'], { perfil: 'gestor' })
    apiListas()
    let w = await abrir('/contatos', AbaContatos)
    expect(w.find('[data-exportar-csv]').exists()).toBe(false)
    w.unmount()

    setActivePinia(createPinia())
    entrar(['contatos.ver', 'painel.exportar'], { perfil: 'gestor' })
    apiFalsa({
      'GET /contatos': () => ({ itens: [], total: 0, pagina: 1, por_pagina: 50 }),
      'GET /contatos.csv': () => erro(429, 'muitas_tentativas', 'x'),
    })
    w = await abrir('/contatos', AbaContatos)
    await w.get('[data-exportar-csv]').trigger('click')
    await flushPromises()
    expect(avisos.at(-1)?.mensagem).toBe('Muitas tentativas. Aguarde um minuto.')
  })

  it('Empresas: o botão ao lado de Ativas/Inativas/Todas, com os filtros da aba', async () => {
    entrar(['contatos.ver', 'painel.exportar'], { perfil: 'gestor' })
    const api = apiListas()
    const w = await abrir('/contatos', AbaEmpresas)
    const botao = w.get('[data-exportar-csv]')
    expect(botao.attributes('aria-label')).toBe('Exportar CSV')
    const todas = w.findAll('[role="radiogroup"] [role="radio"]').find((r) => t(r.text()) === 'Todas')!
    await todas.trigger('click')
    const segmento = w.findAll('select').find((s) => s.findAll('option').some((o) => o.text() === 'Supermercados'))!
    await segmento.setValue('5')
    await flushPromises()
    await botao.trigger('click')
    await flushPromises()
    expect(consulta(chamadasDe(api, 'GET', '/empresas.csv')[0])).toEqual({ segmento_id: '5', ativa: 'todas' })
    const { pagina: _p, ...daLista } = consulta(chamadasDe(api, 'GET', '/empresas').at(-1))
    expect(daLista).toEqual({ segmento_id: '5', ativa: 'todas' })
  })

  it('Empresas: sem painel.exportar não há o botão', async () => {
    entrar(['contatos.ver', 'contatos.editar'], { perfil: 'gestor' })
    apiListas()
    const w = await abrir('/contatos', AbaEmpresas)
    expect(w.find('[data-exportar-csv]').exists()).toBe(false)
  })
})

// ───────────────────────── Auditoria › Atividades: grupo ─────────────────────────

describe('Auditoria › Atividades: filtro por grupo', () => {
  const GRUPOS = [
    { chave: 'acesso', rotulo: 'Acesso e segurança' },
    { chave: 'equipe', rotulo: 'Equipe e permissões' },
    { chave: 'exclusoes', rotulo: 'Exclusões definitivas' },
  ]
  const ITEM = {
    id: 9,
    criado_em: '2026-10-03T10:00:00-03:00',
    evento: 'zona_risco',
    rotulo: 'Zona de risco usada',
    gravidade: 'atencao',
    usuario: { id: 1, nome: 'Ana Paula' },
    detalhe: null,
    ip: '200.1.2.3',
    grupo: 'exclusoes',
  }

  it('"Grupo" entre Gravidade e Buscar, com "Todos" e os grupos da API; escolher filtra; "Limpar filtros" limpa', async () => {
    entrar(['auditoria.ver'], { perfil: 'gestor' })
    const api = apiFalsa({
      'GET /auditoria': () => ({ itens: [ITEM], total: 1, pagina: 1, por_pagina: 20 }),
      'GET /auditoria/grupos': () => GRUPOS,
    })
    const w = await abrir('/auditoria', AbaAtividades)
    const rotulos = w.get('.cartao').findAll('label').map((l) => t(l.text()))
    expect(rotulos).toEqual(['De', 'Até', 'Gravidade', 'Grupo', 'Buscar'])
    const grupo = w.get('[data-filtro-grupo] select')
    expect(grupo.findAll('option').map((o) => t(o.text()))).toEqual(['Todos', 'Acesso e segurança', 'Equipe e permissões', 'Exclusões definitivas'])
    expect(consulta(chamadasDe(api, 'GET', '/auditoria')[0]).grupo).toBeUndefined()

    await grupo.setValue('exclusoes')
    await flushPromises()
    expect(consulta(chamadasDe(api, 'GET', '/auditoria').at(-1))).toMatchObject({ grupo: 'exclusoes', pagina: '1' })
    // O detalhe mostra o grupo do evento
    await w.get('button[aria-expanded]').trigger('click')
    const termos = w.get('#detalhe-9').findAll('dt').map((d) => t(d.text()))
    const valores = w.get('#detalhe-9').findAll('dd').map((d) => t(d.text()))
    expect(valores[termos.indexOf('Grupo')]).toBe('Exclusões definitivas')

    const limpar = w.findAll('button').find((b) => t(b.text()) === 'Limpar filtros')!
    await limpar.trigger('click')
    await flushPromises()
    expect((w.get('[data-filtro-grupo] select').element as HTMLSelectElement).value).toBe('')
    expect(consulta(chamadasDe(api, 'GET', '/auditoria').at(-1)).grupo).toBeUndefined()
    expect(w.findAll('button').some((b) => t(b.text()) === 'Limpar filtros')).toBe(false)
  })

  it('sem os grupos (falha), o filtro fica só com "Todos" e a lista segue', async () => {
    entrar(['auditoria.ver'], { perfil: 'gestor' })
    apiFalsa({
      'GET /auditoria': () => ({ itens: [ITEM], total: 1, pagina: 1, por_pagina: 20 }),
      'GET /auditoria/grupos': () => erro(500, 'erro', 'Falhou.'),
    })
    const w = await abrir('/auditoria', AbaAtividades)
    expect(w.get('[data-filtro-grupo] select').findAll('option').map((o) => t(o.text()))).toEqual(['Todos'])
    expect(t(w.text())).toContain('Zona de risco usada')
  })
})

// ───────────────────────── Aviso de exclusão, Plataforma e WhatsApp ─────────────────────────

describe('aviso do topo: dia da exclusão da conta encerrada', () => {
  it('administrador: o texto, "Baixar os dados" e "Escolher plano"; fica no lugar do aviso de cobrança e não fecha', async () => {
    entrar(['assinatura.gerenciar', 'configuracoes.gerenciar'], { exclusaoEm: '2027-01-15', aviso: { tipo: 'teste_expirado', data: '2026-06-30', dias: null } })
    const w = await montar(AvisoCobranca)
    const aviso = w.get('[data-aviso-exclusao]')
    expect(aviso.attributes('aria-label')).toBe('Aviso sobre a exclusão da conta')
    expect(t(aviso.get('[role="status"]').text())).toBe('Os dados desta conta serão excluídos em 15/01/2027. Baixe uma cópia ou assine um plano.')
    expect(t(w.get('[data-acao-exclusao="baixar"]').text())).toBe('Baixar os dados')
    expect(w.get('[data-acao-exclusao="baixar"]').attributes('href')).toBe('/configuracoes/dados-da-conta')
    expect(t(w.get('[data-acao-exclusao="plano"]').text())).toBe('Escolher plano')
    expect(w.get('[data-acao-exclusao="plano"]').attributes('href')).toBe('/assinatura')
    expect(w.find('[data-aviso-cobranca]').exists()).toBe(false)
    expect(w.find('button[aria-label="Fechar aviso"]').exists()).toBe(false)
  })

  it('demais perfis: "… Fale com o administrador da conta.", sem botões', async () => {
    entrar(['painel.ver'], { perfil: 'gestor', exclusaoEm: '2027-01-15' })
    const w = await montar(AvisoCobranca)
    expect(t(w.get('[data-aviso-exclusao]').text())).toBe('Os dados desta conta serão excluídos em 15/01/2027. Fale com o administrador da conta.')
    expect(w.find('[data-acao-exclusao]').exists()).toBe(false)
  })

  it('também na Assinatura e em Dados da conta (sem o botão da própria tela); sem `exclusao_em`, o aviso de cobrança de sempre', async () => {
    entrar(['assinatura.gerenciar'], { exclusaoEm: '2027-01-15' })
    let w = await montar(AvisoCobranca, '/assinatura')
    expect(w.find('[data-aviso-exclusao]').exists()).toBe(true)
    expect(w.find('[data-acao-exclusao="plano"]').exists()).toBe(false)
    expect(w.find('[data-acao-exclusao="baixar"]').exists()).toBe(true)
    w.unmount()
    w = await montar(AvisoCobranca, '/configuracoes/dados-da-conta')
    expect(w.find('[data-acao-exclusao="baixar"]').exists()).toBe(false)
    expect(w.find('[data-acao-exclusao="plano"]').exists()).toBe(true)
    w.unmount()

    setActivePinia(createPinia())
    entrar(['assinatura.gerenciar'], { exclusaoEm: null, aviso: { tipo: 'teste_expirado', data: '2026-06-30', dias: null } })
    w = await montar(AvisoCobranca)
    expect(w.find('[data-aviso-exclusao]').exists()).toBe(false)
    expect(t(w.get('[data-aviso-cobranca]').text())).toContain('Seu teste grátis terminou.')
  })
})

describe('Plataforma: selo da exclusão', () => {
  const conta = (c: Partial<ContaPlataforma>): ContaPlataforma => ({
    id: 2,
    nome: 'Padaria Prado',
    plano: 'essencial',
    situacao: 'teste_expirado',
    teste_ate: '2026-07-01T00:00:00-03:00',
    usuarios: 1,
    criada_em: '2026-06-01T10:00:00Z',
    pago_ate: null,
    atrasada_desde: null,
    assinatura: null,
    admins: [],
    ...c,
  })

  it('"Exclusão em dd/mm/aaaa" na conta com o dia marcado; as outras, sem selo', async () => {
    entrar([], { superadmin: true })
    apiFalsa({ 'GET /plataforma/contas': () => [conta({ exclusao_em: '2027-01-15' }), conta({ id: 3, nome: 'Outra', exclusao_em: null })] })
    const w = await abrir('/plataforma/contas', PlataformaView)
    const linhas = w.findAll('tbody tr')
    expect(linhas).toHaveLength(2)
    expect(linhas[0]!.findAll('[data-selo-exclusao]').map((s) => t(s.text()))).toContain('Exclusão em 15/01/2027')
    expect(linhas[1]!.find('[data-selo-exclusao]').exists()).toBe(false)
  })
})

describe('Guia do WhatsApp: rodapé com SAIR obrigatório', () => {
  it('o rodapé não é mais opcional e a nota explica por quê', async () => {
    entrar(['configuracoes.gerenciar'])
    apiFalsa({})
    const dados: WhatsappIntegracao = {
      conectado: false,
      numero_exibicao: null,
      nome_verificado: null,
      phone_number_id: null,
      waba_id: null,
      modelo: null,
      ativo: false,
      franquia: { plano: 'profissional', limite: 300, usadas_mes: 0, excedente_ativo: false, excedentes_mes: 0, valor_excedente: 0.3 },
      ultimo_erro: null,
      webhook_url: 'https://api.toqqi/whatsapp/webhook',
      webhook_verificacao: 'abc',
    }
    const w = await montar(GuiaWhatsapp, '/integracoes', { dados })
    const texto = t(w.text())
    expect(texto).toContain('Rodapé (obrigatório)')
    expect(texto).not.toContain('opcional, recomendado')
    expect(texto).toContain('Para não receber mais pesquisas, responda SAIR.')
    expect(t(w.get('[data-nota-sair]').text())).toBe(
      'O rodapé com SAIR é obrigatório: é ele que diz ao cliente como parar de receber. Sem a palavra SAIR no corpo ou no rodapé, o Toqqi não aceita o modelo. Quem responder SAIR sai da lista na hora e não recebe mais pesquisas.',
    )
  })
})
