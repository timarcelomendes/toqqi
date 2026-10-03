// Etapa 5e com a API simulada: Configurações › Envios › "Visual dos e-mails" (cor do formulário ou própria, aviso de
// contraste, logo, imagem de topo pelo banco, assinatura e rodapé, e-mail de teste só sem mudanças pendentes), a prévia
// com o visual (também a do editor de formulários), o banco de imagens (enviar, escolher, excluir em uso, limite) e
// Auditoria › E-mails enviados (abas e rota, alerta e "Ver só as falhas", filtros, tabela e cartões, vazio, paginação).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, ref } from 'vue'
import type { ConfigEnvios, EmailEnviado, ImagemBanco, ImagemTopoEmail, Pergunta, Tema } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { router as rotasDoApp } from '@/router'
import { hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import ConfigEnviosView from '@/modulos/configuracoes/ConfigEnviosView.vue'
import ImagemTopoEmailCampo from '@/modulos/configuracoes/ImagemTopoEmail.vue'
import PreviaEmail from '@/modulos/configuracoes/PreviaEmail.vue'
import { montarPreviaEmail } from '@/modulos/configuracoes/mensagens'
import AuditoriaView from '@/modulos/auditoria/AuditoriaView.vue'
import PreVisualizacao from '@/modulos/formularios/editor/PreVisualizacao.vue'
import { apiFalsa } from './apiFalsa'

const CONFIG: ConfigEnvios = {
  envios_ativos: false,
  envio_automatico: false,
  formulario_id: 1,
  intervalo_dias: 90,
  descanso_dias: 30,
  lembretes: 1,
  dias_lembretes: [3],
  janela_inicio: '08:00',
  janela_fim: '18:00',
  so_dias_uteis: true,
  responder_para: null,
  remetente_nome: null,
  assunto_convite: 'Como foi com a {empresa}?',
  texto_convite: 'Olá, {nome}!\n\nConte como foi.',
  assunto_lembrete: 'Lembrete da {empresa}',
  texto_lembrete: 'Ainda dá tempo.',
  texto_whatsapp: 'Oi, {nome}! {link}',
  agradecimento_ativo: true,
  agradecimento: { promotor: 'Obrigado pela nota {nota}, {nome}!', neutro: 'Valeu, {nome}.', detrator: 'Sentimos muito, {nome}.' },
  canal: 'email',
  email_cor: null,
  email_mostrar_logo: true,
  email_imagem_topo: null,
  email_assinatura: null,
  email_rodape: null,
}

const FORMULARIO = {
  id: 1,
  nome: 'Pesquisa de atendimento',
  descricao: null,
  tipo_principal: 'personalizado',
  tema: { cor: '#0E7490' },
  ativo: true,
  publico: false,
  codigo_publico: 'abc',
  padrao_nps: false,
  padrao_csat: false,
  respostas: 0,
  atualizado_em: '2026-10-01T00:00:00Z',
}

const IMAGENS: ImagemBanco[] = [
  { id: 9, url: 'https://api.toqqi/publico/imagens/aaa', nome: 'banner-primavera.png', tipo: 'image/png', tamanho: 250_000, largura: 1200, altura: 400, criada_em: '2026-10-01T12:00:00Z', em_uso: false },
  { id: 4, url: 'https://api.toqqi/publico/imagens/bbb', nome: 'topo-antigo.jpg', tipo: 'image/jpeg', tamanho: 80_000, largura: null, altura: null, criada_em: '2026-09-01T12:00:00Z', em_uso: true },
]

function entrar(permissoes: string[]) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana Paula Ribeiro', email: 'ana@sol.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Distribuidora Sol', plano: null, situacao: 'ativa', teste_ate: null, logo_url: 'https://cdn.exemplo/logo-empresa.png' },
      permissoes,
    } as never,
    false,
  )
}

async function abrir(caminho: string, rotas: { path: string; name?: string; component: unknown }[]): Promise<{ w: VueWrapper; router: Router }> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [...rotas, { path: '/:qualquer(.*)*', component: { render: () => h('div') } }] as never,
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { w, router }
}

const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
function campo(w: VueWrapper, rotulo: string) {
  const label = w.findAll('label').find((l) => t(l.text()) === rotulo)
  if (!label) throw new Error(`Sem o campo "${rotulo}"`)
  return w.get<HTMLTextAreaElement | HTMLInputElement>(`[id="${label.attributes('for')}"]`)
}
/** Elementos fora do componente (o Modal vai para o <body>). */
const $ = (sel: string) => document.body.querySelector<HTMLElement>(sel)
const $$ = (sel: string) => Array.from(document.body.querySelectorAll<HTMLElement>(sel))
async function clicar(el: HTMLElement | null) {
  if (!el) throw new Error('Elemento não encontrado')
  el.click()
  await flushPromises()
}
const png = (nome = 'nova.png', bytes = 2000) =>
  new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, ...new Array(bytes).fill(0)])], nome, { type: 'image/png' })
async function escolherArquivo(arquivo: File) {
  const entrada = $('[data-banco-imagens] input[type="file"]') as HTMLInputElement
  Object.defineProperty(entrada, 'files', { value: [arquivo], configurable: true })
  entrada.dispatchEvent(new Event('change'))
  await flushPromises()
}

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  avisos.splice(0)
})
afterEach(() => {
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

// ───────────────────────── Configurações › Envios › Visual dos e-mails ─────────────────────────

function apiEnvios(extra: Record<string, (c: { corpo: unknown }) => unknown> = {}) {
  return apiFalsa({
    'GET /envios/configuracao': () => CONFIG,
    'GET /formularios': () => [FORMULARIO],
    'GET /formularios/:id': () => ({ ...FORMULARIO, perguntas: [], tema: { cor: '#0E7490', logo_url: 'https://cdn.exemplo/logo-form.png' } }),
    'GET /imagens': () => ({ itens: IMAGENS, limite: 30 }),
    'POST /envios/configuracao/teste': () => ({ mensagem: 'Enviamos um e-mail de teste para ana@sol.com.br.' }),
    'PUT /envios/configuracao': ({ corpo }) => {
      const { email_imagem_topo_id: id, ...resto } = corpo as ConfigEnvios & { email_imagem_topo_id: number | null }
      const imagem = IMAGENS.find((i) => i.id === id)
      return { ...CONFIG, ...resto, email_imagem_topo: imagem ? { id: imagem.id, url: imagem.url, largura: imagem.largura, altura: imagem.altura } : null }
    },
    ...extra,
  })
}
const abrirEnvios = () => abrir('/configuracoes/envios', [{ path: '/configuracoes/envios', component: ConfigEnviosView }])
const previaVisual = (w: VueWrapper) => w.get('[data-previa-visual] [aria-label="Prévia do e-mail"]')

describe('Configurações › Envios › Visual dos e-mails', () => {
  it('cor do formulário por padrão; desligada, sugestões e o campo #RRGGBB; cor clara avisa e o botão sai com texto escuro', async () => {
    entrar(['configuracoes.gerenciar', 'envios.ver', 'formularios.ver'])
    apiEnvios()
    const { w } = await abrirEnvios()
    const secao = w.get('[data-secao-visual]')
    expect(t(secao.get('h2').text())).toBe('Visual dos e-mails')
    const usarFormulario = campo(w, 'Usar a cor do formulário')
    expect(usarFormulario.attributes('aria-checked')).toBe('true')
    expect(t(w.get('[data-cor-formulario]').text())).toContain('Agora: #0E7490, do formulário “Pesquisa de atendimento”.')
    // A prévia usa a cor do formulário (personalizado: o botão "Responder pesquisa" na cor, com texto branco)
    expect(previaVisual(w).get('[data-teste="faixa"]').attributes('data-cor-faixa')).toBe('#0E7490')
    expect(previaVisual(w).get('[data-teste="botao-responder"]').attributes('data-cor-texto')).toBe('#ffffff')
    expect(w.find('[data-sugestao]').exists()).toBe(false)

    await usarFormulario.trigger('click')
    await flushPromises()
    // Começa pela cor que já valia (a prévia não pula) e mostra as 6 sugestões e o código
    expect((campo(w, 'Código da cor').element as HTMLInputElement).value).toBe('#0E7490')
    expect(w.findAll('[data-sugestao]')).toHaveLength(6)
    expect(w.find('input[type="color"]').exists()).toBe(true)
    await w.get('[data-sugestao="#2563EB"]').trigger('click')
    expect(w.get('[data-sugestao="#2563EB"]').attributes('aria-pressed')).toBe('true')
    expect(previaVisual(w).get('[data-teste="faixa"]').attributes('data-cor-faixa')).toBe('#2563EB')
    expect(w.find('[data-aviso-contraste]').exists()).toBe(false)

    await campo(w, 'Código da cor').setValue('ffd400')
    expect(previaVisual(w).get('[data-teste="faixa"]').attributes('data-cor-faixa')).toBe('#FFD400')
    expect(previaVisual(w).get('[data-teste="botao-responder"]').attributes('data-cor-texto')).toBe('#111827')
    expect(t(w.get('[data-aviso-contraste]').text())).toBe('Cor clara: o texto do botão vai ficar escuro, para continuar fácil de ler.')
    // O aviso fica numa região que o leitor de tela anuncia
    expect(w.get('[data-aviso-contraste]').element.parentElement?.getAttribute('aria-live')).toBe('polite')

    await campo(w, 'Código da cor').setValue('#12')
    expect(campo(w, 'Código da cor').attributes('aria-invalid')).toBe('true')
    expect(t(w.text())).toContain('Use o formato #RRGGBB, por exemplo #D63A18.')
  })

  it('"Enviar e-mail de teste" usa o que está salvo: com mudanças pendentes fica inativo, com a dica', async () => {
    entrar(['configuracoes.gerenciar', 'envios.ver', 'formularios.ver'])
    const api = apiEnvios()
    const { w } = await abrirEnvios()
    const botao = () => w.get('[data-enviar-teste]')
    expect(t(botao().text())).toBe('Enviar e-mail de teste')
    expect(botao().attributes('aria-disabled')).toBeUndefined()
    expect(w.find('[data-dica-teste]').exists()).toBe(false)
    await botao().trigger('click')
    await flushPromises()
    expect(api.chamadas.filter((c) => c.metodo === 'POST' && c.caminho === '/envios/configuracao/teste')).toHaveLength(1)
    expect(avisos.map((a) => a.mensagem)).toContain('Enviamos um e-mail de teste para ana@sol.com.br.')

    await campo(w, 'Mostrar o logo').trigger('click')
    expect(botao().attributes('aria-disabled')).toBe('true')
    expect(t(w.get('[data-dica-teste]').text())).toBe('Salve as mudanças para enviar o teste.')
    expect(botao().attributes('aria-describedby')).toBe(w.get('[data-dica-teste]').attributes('id'))
    await botao().trigger('click')
    await flushPromises()
    expect(api.chamadas.filter((c) => c.metodo === 'POST' && c.caminho === '/envios/configuracao/teste')).toHaveLength(1)

    await w.get('#form-config-envios').trigger('submit')
    await flushPromises()
    expect(api.chamadas.filter((c) => c.metodo === 'PUT')).toHaveLength(1)
    expect(botao().attributes('aria-disabled')).toBeUndefined()
    expect(w.find('[data-dica-teste]').exists()).toBe(false)
  })

  it('logo, assinatura e rodapé na prévia (texto puro, escapado; as linhas fixas sempre); salvar manda o visual', async () => {
    entrar(['configuracoes.gerenciar', 'envios.ver', 'formularios.ver'])
    const api = apiEnvios()
    const { w } = await abrirEnvios()
    // Logo do formulário (vale mais que o da empresa), com a nota de qual logo vale
    expect(previaVisual(w).get('[data-teste="logo"] img').attributes('src')).toBe('https://cdn.exemplo/logo-form.png')
    expect(t(w.get('[data-nota-logo]').text())).toBe('Agora vale o logo do formulário “Pesquisa de atendimento”.')
    await campo(w, 'Mostrar o logo').trigger('click')
    expect(previaVisual(w).find('[data-teste="logo"]').exists()).toBe(false)
    expect(w.find('[data-nota-logo]').exists()).toBe(false)

    await campo(w, 'Assinatura (opcional)').setValue('<b>Equipe Sol</b>\n(11) 4000-0000')
    await campo(w, 'Rodapé (opcional)').setValue('Rua das Flores, 100\nSão Paulo (SP)')
    const assinatura = previaVisual(w).get('[data-teste="assinatura"]')
    expect(assinatura.text()).toContain('<b>Equipe Sol</b>')
    expect(assinatura.find('b').exists()).toBe(false)
    expect(previaVisual(w).get('[data-teste="rodape-conta"]').text()).toBe('Rua das Flores, 100\nSão Paulo (SP)')
    expect(t(previaVisual(w).get('[data-teste="rodape-fixo"]').text())).toBe('Você recebeu esta pesquisa porque é cliente de Distribuidora Sol.')
    expect(t(previaVisual(w).get('[data-teste="descadastro"]').text())).toBe('Não quero mais receber pesquisas')
    // Contador de caracteres ao lado do rótulo
    expect(t(w.text())).toContain('Caracteres usados: 32/300')
    // Agradecimento: o mesmo visual, com {nota} de exemplo e sem os botões da nota
    const opcaoAgradecimento = w.findAll('[data-previa-visual] label').find((l) => t(l.text()) === 'Agradecimento')!
    await opcaoAgradecimento.get('input').setValue(true)
    expect(t(previaVisual(w).text())).toContain('Obrigado pela nota 10, Maria!')
    expect(previaVisual(w).find('[data-teste="bloco-nota"]').exists()).toBe(false)
    expect(previaVisual(w).find('[data-teste="assinatura"]').exists()).toBe(true)

    await w.get('#form-config-envios').trigger('submit')
    await flushPromises()
    const put = api.chamadas.find((c) => c.metodo === 'PUT')!
    expect(put.corpo).toMatchObject({
      email_cor: null,
      email_mostrar_logo: false,
      email_imagem_topo_id: null,
      email_assinatura: '<b>Equipe Sol</b>\n(11) 4000-0000',
      email_rodape: 'Rua das Flores, 100\nSão Paulo (SP)',
    })
    expect(put.corpo).not.toHaveProperty('email_imagem_topo')
  })

  it('imagem de topo pelo banco: escolher (foco volta ao botão), a prévia mostra na largura do e-mail, salvar manda o id', async () => {
    entrar(['configuracoes.gerenciar', 'envios.ver', 'formularios.ver'])
    const api = apiEnvios()
    const { w } = await abrirEnvios()
    expect(w.find('[data-sem-imagem-topo]').exists()).toBe(true)
    const gatilho = w.get('[data-abrir-banco]')
    expect(t(gatilho.text())).toBe('Escolher imagem de topo')
    ;(gatilho.element as HTMLElement).focus()
    await gatilho.trigger('click')
    await flushPromises()
    expect($('[data-banco-imagens]')).not.toBeNull()
    expect(t($('[data-quantidade]')?.textContent)).toBe('2 de 30 imagens')
    await clicar($('[data-imagem="9"] [data-escolher]'))
    expect($('[data-banco-imagens]')).toBeNull()
    expect(document.activeElement).toBe(gatilho.element)
    expect(t(gatilho.text())).toBe('Trocar a imagem de topo')
    const img = previaVisual(w).get('[data-teste="imagem-topo"] img')
    expect(img.attributes()).toMatchObject({ src: 'https://api.toqqi/publico/imagens/aaa', alt: '', width: '544', height: '181' })
    expect(t(w.get('[data-imagem-topo]').text())).toContain('1200 × 400 px')

    await w.get('#form-config-envios').trigger('submit')
    await flushPromises()
    expect(api.chamadas.find((c) => c.metodo === 'PUT')!.corpo).toMatchObject({ email_imagem_topo_id: 9 })
    // "Remover" tira a imagem e o foco vai para "Escolher imagem"
    await w.get('[data-remover-imagem]').trigger('click')
    await flushPromises()
    expect(w.find('[data-sem-imagem-topo]').exists()).toBe(true)
    expect(previaVisual(w).find('[data-teste="imagem-topo"]').exists()).toBe(false)
    expect(document.activeElement).toBe(w.get('[data-abrir-banco]').element)
  })

  it('quem só vê as configurações vê o visual e a prévia, mas não muda nada nem envia o teste', async () => {
    entrar(['envios.ver'])
    apiEnvios()
    const { w } = await abrirEnvios()
    expect(w.find('[data-enviar-teste]').exists()).toBe(false)
    expect(w.get('[data-secao-visual] fieldset').attributes('disabled')).toBeDefined()
    expect(w.find('[data-previa-visual] [aria-label="Prévia do e-mail"]').exists()).toBe(true)
  })
})

// ───────────────────────── Prévia do e-mail ─────────────────────────

describe('PreviaEmail com o visual', () => {
  it('na ordem do e-mail: faixa → logo → imagem de topo → textos → nota → assinatura → rodapé da conta → linhas fixas', () => {
    const previa = montarPreviaEmail(
      { ...CONFIG, email_cor: '#FFD400', email_imagem_topo: { id: 9, url: 'https://x/topo.png', largura: 1200, altura: 400 }, email_assinatura: 'Equipe Sol', email_rodape: 'Rua A, 1' },
      'convite',
      'personalizado',
      { nome: 'Maria', empresa: 'Distribuidora Sol' },
      'https://x/logo.png',
    )
    const w = mount(PreviaEmail, { props: { previa, empresa: 'Distribuidora Sol' } })
    const ordem = w.findAll('[data-teste]').map((e) => e.attributes('data-teste'))
    expect(ordem).toEqual(['assunto', 'cartao', 'faixa', 'logo', 'imagem-topo', 'corpo', 'bloco-nota', 'botao-responder', 'assinatura', 'rodape', 'rodape-conta', 'rodape-fixo', 'descadastro'])
    const botao = w.get('[data-teste="botao-responder"]')
    expect(botao.attributes('style')).toContain('background-color: rgb(255, 212, 0)')
    expect(botao.attributes('style')).toContain('color: rgb(17, 24, 39)')
    expect(w.get('[data-teste="faixa"]').attributes('aria-hidden')).toBe('true')
    // O e-mail é sempre claro (não segue o modo escuro do site)
    expect(w.get('[data-teste="cartao"]').classes()).toContain('bg-white')
  })
})

describe('editor de formulários: prévia do convite por e-mail com o visual', () => {
  const TEMA = { cor: '#E8501E', logo_url: 'https://cdn.exemplo/logo-form.png' } as unknown as Tema
  const PERGUNTAS = [{ id: 'a', tipo: 'nps', titulo: 'Recomendaria?', obrigatoria: true }] as Pergunta[]

  async function montar(config: Partial<ConfigEnvios>) {
    setActivePinia(createPinia())
    const sessao = useSessaoStore()
    sessao.permissoes = ['envios.ver']
    sessao.conta = { id: 1, nome: 'Distribuidora Sol', logo_url: null } as never
    apiFalsa({ 'GET /envios/configuracao': () => ({ ...CONFIG, ...config }) })
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
    const w = mount(PreVisualizacao, { props: { nome: 'Pesquisa NPS', perguntas: PERGUNTAS, tema: TEMA, nomeEmpresa: 'Distribuidora Sol', tipo: 'nps' }, global: { plugins: [router] } })
    await flushPromises()
    await w.get('[data-canal="email"]').trigger('click')
    await flushPromises()
    return w.get('[aria-label="Prévia do e-mail"]')
  }

  it('sem cor da conta, a cor deste formulário; com cor da conta, ela; assinatura e rodapé da conta', async () => {
    const doFormulario = await montar({ email_cor: null })
    expect(doFormulario.get('[data-teste="faixa"]').attributes('data-cor-faixa')).toBe('#E8501E')
    const daConta = await montar({ email_cor: '#2563EB', email_assinatura: 'Equipe Sol', email_rodape: 'Rua A, 1', email_mostrar_logo: false })
    expect(daConta.get('[data-teste="faixa"]').attributes('data-cor-faixa')).toBe('#2563EB')
    expect(t(daConta.get('[data-teste="assinatura"]').text())).toBe('Equipe Sol')
    expect(t(daConta.get('[data-teste="rodape-conta"]').text())).toBe('Rua A, 1')
    expect(daConta.find('[data-teste="logo"]').exists()).toBe(false)
  })
})

// ───────────────────────── Banco de imagens ─────────────────────────

describe('banco de imagens', () => {
  async function abrirBanco(
    itens: ImagemBanco[] = IMAGENS,
    extra: Record<string, (c: { corpo: unknown }) => unknown> = {},
    salva: ImagemTopoEmail | null = null,
  ) {
    const api = apiFalsa({ 'GET /imagens': () => ({ itens, limite: 30 }), ...extra })
    const modelo = ref<ImagemTopoEmail | null>({ id: 9, url: IMAGENS[0]!.url, largura: 1200, altura: 400 })
    const w = mount(
      defineComponent({
        render: () =>
          h(ImagemTopoEmailCampo, { modelValue: modelo.value, salva, 'onUpdate:modelValue': (v: ImagemTopoEmail | null) => (modelo.value = v) }),
      }),
      { attachTo: document.body },
    )
    await w.get('[data-abrir-banco]').trigger('click')
    await flushPromises()
    return { w, api, modelo }
  }

  it('grade com nome, dimensões, "Em uso" e a escolhida; "X de 30 imagens" e a dica de tamanho', async () => {
    await abrirBanco()
    const cartoes = $$('[data-grade-imagens] [data-imagem]')
    expect(cartoes).toHaveLength(2)
    expect(t(cartoes[0]!.textContent)).toContain('banner-primavera.png')
    expect(t(cartoes[0]!.textContent)).toContain('1200 × 400 px · 244 KB')
    expect(t(cartoes[0]!.textContent)).toContain('Escolhida')
    expect(cartoes[1]!.querySelector('[data-em-uso]')?.textContent?.trim()).toBe('Em uso')
    // As miniaturas são botões com nome
    expect(cartoes[1]!.querySelector('button[data-escolher]')?.getAttribute('aria-label')).toBe('Escolher topo-antigo.jpg')
    expect(t($('[data-quantidade]')?.textContent)).toBe('2 de 30 imagens')
    expect(t($('[role="dialog"]')?.textContent)).toContain('PNG ou JPG de até 1 MB. Para o topo do e-mail, use 1200 × 400 px.')
    // Ao abrir, o foco vai para "Enviar imagem"
    expect(document.activeElement).toBe($('[data-enviar-imagem]'))
  })

  it('enviar: confere o arquivo antes (1 MB), manda o multipart `arquivo` e a imagem nova entra no topo da grade', async () => {
    const nova: ImagemBanco = { ...IMAGENS[0]!, id: 12, nome: 'nova.png', em_uso: false, url: 'https://api.toqqi/publico/imagens/ccc' }
    const { api } = await abrirBanco(IMAGENS, { 'POST /imagens': () => new Response(JSON.stringify(nova), { status: 201 }) })
    await escolherArquivo(png('grande.png', 1024 * 1024))
    expect(t($('[data-erro-banco]')?.textContent)).toBe('Use uma imagem PNG ou JPG de até 1 MB.')
    expect(api.chamadas.some((c) => c.metodo === 'POST')).toBe(false)

    await escolherArquivo(png('nova.png'))
    const post = api.chamadas.find((c) => c.metodo === 'POST')!
    expect(post.caminho).toBe('/imagens')
    expect((post.corpo as FormData).get('arquivo')).toBeInstanceOf(File)
    expect($('[data-erro-banco]')).toBeNull()
    expect($$('[data-grade-imagens] [data-imagem]').map((e) => e.dataset.imagem)).toEqual(['12', '9', '4'])
    expect(t($('[data-quantidade]')?.textContent)).toBe('3 de 30 imagens')
    expect(t($('[data-anuncio-banco]')?.textContent)).toBe('Imagem enviada: nova.png. Para usar, escolha a imagem na lista.')
  })

  it('excluir pede confirmação; a imagem em uso fica, com a mensagem da API; a escolhida excluída volta para a salva', async () => {
    const salva = { id: 4, url: IMAGENS[1]!.url, largura: IMAGENS[1]!.largura, altura: IMAGENS[1]!.altura }
    const { modelo, api } = await abrirBanco(
      IMAGENS,
      {
        'DELETE /imagens/4': () =>
          new Response(JSON.stringify({ erro: { codigo: 'imagem_em_uso', mensagem: 'Esta imagem está no visual dos e-mails. Troque a imagem de topo antes de excluir.' } }), { status: 409 }),
        'DELETE /imagens/9': () => undefined,
      },
      salva,
    )
    await clicar($('[data-imagem="4"] [data-excluir]'))
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Excluir esta imagem?')
    responderConfirmacao(true)
    await flushPromises()
    expect(t($('[data-erro-banco]')?.textContent)).toBe('Esta imagem está no visual dos e-mails. Troque a imagem de topo antes de excluir.')
    expect($('[data-imagem="4"]')).not.toBeNull()

    // Cancelar não exclui
    await clicar($('[data-imagem="9"] [data-excluir]'))
    responderConfirmacao(false)
    await flushPromises()
    expect(api.chamadas.filter((c) => c.metodo === 'DELETE')).toHaveLength(1)

    await clicar($('[data-imagem="9"] [data-excluir]'))
    responderConfirmacao(true)
    await flushPromises()
    expect($('[data-imagem="9"]')).toBeNull()
    expect(t($('[data-quantidade]')?.textContent)).toBe('1 de 30 imagens')
    expect(t($('[data-anuncio-banco]')?.textContent)).toBe('Imagem excluída: banner-primavera.png.')
    expect(modelo.value).toEqual(salva) // salvar depois não tira dos e-mails a imagem que estava salva
  })

  it('sem imagem salva, excluir a escolhida deixa o visual sem imagem de topo', async () => {
    const { modelo } = await abrirBanco(IMAGENS, { 'DELETE /imagens/9': () => undefined })
    await clicar($('[data-imagem="9"] [data-excluir]'))
    responderConfirmacao(true)
    await flushPromises()
    expect(modelo.value).toBeNull()
  })

  it('com 30 imagens, "Enviar imagem" fica inativo e explica o limite; o 409 da API aparece como veio', async () => {
    const cheias = Array.from({ length: 30 }, (_, i) => ({ ...IMAGENS[0]!, id: 100 + i, nome: `img-${i}.png` }))
    await abrirBanco(cheias)
    expect(t($('[data-quantidade]')?.textContent)).toBe('30 de 30 imagens')
    expect($('[data-enviar-imagem]')?.getAttribute('aria-disabled')).toBe('true')
    expect(t($('[data-banco-cheio]')?.textContent)).toBe('O banco de imagens tem até 30 imagens. Exclua uma para enviar outra.')

    vi.unstubAllGlobals()
    document.body.innerHTML = ''
    const { api } = await abrirBanco(IMAGENS, {
      'POST /imagens': () =>
        new Response(JSON.stringify({ erro: { codigo: 'limite_imagens', mensagem: 'O banco de imagens tem até 30 imagens. Exclua uma para enviar outra.' } }), { status: 409 }),
    })
    await escolherArquivo(png())
    expect(t($('[data-erro-banco]')?.textContent)).toBe('O banco de imagens tem até 30 imagens. Exclua uma para enviar outra.')
    expect(api.chamadas.filter((c) => c.metodo === 'GET' && c.caminho === '/imagens').length).toBeGreaterThanOrEqual(2) // recarrega a contagem
  })

  it('banco vazio mostra o estado vazio', async () => {
    await abrirBanco([])
    expect(t($('[data-banco-imagens]')?.textContent)).toContain('Nenhuma imagem ainda')
    expect(t($('[data-quantidade]')?.textContent)).toBe('0 de 30 imagens')
  })
})

// ───────────────────────── Auditoria › E-mails enviados ─────────────────────────

const EMAILS: EmailEnviado[] = [
  { id: 1, tipo: 'convite', tipo_rotulo: 'Convite de pesquisa', destinatario: 'maria@mercadobompreco.com.br', assunto: 'Como foi com a Distribuidora Sol?', situacao: 'enviado', erro: null, criado_em: '2026-10-02T13:00:00Z' },
  { id: 2, tipo: 'senha', tipo_rotulo: 'Redefinição de senha', destinatario: 'joao@sol.com.br', assunto: 'Redefina sua senha', situacao: 'falhou', erro: 'O endereço de e-mail não existe.', criado_em: '2026-10-01T10:00:00Z' },
]

const rotaAuditoria = () => {
  const r = rotasDoApp.getRoutes().find((x) => x.name === 'auditoria')!
  return { path: r.path, name: 'auditoria', component: AuditoriaView }
}

function apiAuditoria(resposta: (pagina: number) => unknown = (pagina) => ({ itens: EMAILS, total: 45, pagina, por_pagina: 20, falhas_7_dias: 2 })) {
  return apiFalsa({
    'GET /auditoria/emails': (c) => resposta(Number(c.url.searchParams.get('pagina') ?? 1)),
    'GET /auditoria': () => ({ itens: [], total: 0, pagina: 1, por_pagina: 20 }),
  })
}
const ultimaBusca = (api: ReturnType<typeof apiFalsa>) => {
  const c = api.chamadas.filter((x) => x.caminho === '/auditoria/emails').at(-1)!
  return Object.fromEntries(c.url.searchParams.entries())
}

describe('Auditoria › E-mails enviados', () => {
  it('rota: /auditoria/emails (auditoria.ver); /auditoria fica em Atividades', () => {
    const r = rotasDoApp.resolve('/auditoria/emails')
    expect(r.name).toBe('auditoria')
    expect(r.params.aba).toBe('emails')
    expect(r.meta.permissao).toBe('auditoria.ver')
    expect(rotasDoApp.resolve('/auditoria').name).toBe('auditoria')
    expect(rotasDoApp.resolve('/auditoria/outra').name).toBe('nao-encontrada')
  })

  it('abas: Atividades em /auditoria; "E-mails enviados" muda o endereço; ?aba=emails também abre os e-mails', async () => {
    entrar(['auditoria.ver'])
    const api = apiAuditoria()
    const { w, router } = await abrir('/auditoria', [rotaAuditoria()])
    const abas = w.findAll('[role="tab"]')
    expect(abas.map((a) => t(a.text()))).toEqual(['Atividades', 'E-mails enviados'])
    expect(abas[0]!.attributes('aria-selected')).toBe('true')
    expect(api.chamadas.map((c) => c.caminho)).toEqual(['/auditoria'])
    await abas[1]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/auditoria/emails')
    expect(api.chamadas.map((c) => c.caminho)).toEqual(['/auditoria', '/auditoria/emails'])
    await w.findAll('[role="tab"]')[0]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/auditoria')

    await router.push('/auditoria?aba=emails')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/auditoria/emails')
    expect(w.findAll('[role="tab"]')[1]!.attributes('aria-selected')).toBe('true')
  })

  it('últimos 30 dias; alerta das falhas com "Ver só as falhas"; tabela e cartões no celular; notas', async () => {
    entrar(['auditoria.ver'])
    const api = apiAuditoria()
    const { w } = await abrir('/auditoria/emails', [rotaAuditoria()])
    const hoje = hojeIso()
    expect(ultimaBusca(api)).toEqual({ de: somarDias(hoje, -29), ate: hoje, pagina: '1' })
    expect(t(w.get('[data-alerta-falhas]').text())).toContain('2 e-mails falharam nos últimos 7 dias.')
    expect(t(w.get('[data-total-emails]').text())).toBe('45 e-mails no período')

    // Tabela (computador) e cartões (celular): os dois no HTML, um de cada vez pela largura
    const tabela = w.get('[data-tabela-emails]')
    expect(tabela.classes()).toEqual(expect.arrayContaining(['hidden', 'md:block']))
    expect(tabela.findAll('th').map((th) => t(th.text()))).toEqual(['Data', 'Tipo', 'Destinatário', 'Assunto', 'Situação', 'Erro'])
    const linhas = tabela.findAll('tbody tr')
    expect(linhas).toHaveLength(2)
    expect(t(linhas[1]!.text())).toContain('Redefinição de senha')
    expect(t(linhas[1]!.text())).toContain('joao@sol.com.br')
    expect(t(linhas[1]!.text())).toContain('Falhou')
    expect(t(linhas[1]!.text())).toContain('O endereço de e-mail não existe.')
    const cartoes = w.get('[data-cartoes-emails]')
    expect(cartoes.classes()).toContain('md:hidden')
    expect(cartoes.findAll('[data-cartao-email]')).toHaveLength(2)
    expect(t(cartoes.findAll('[data-cartao-email]')[0]!.text())).toContain('Enviado')
    expect(t(cartoes.findAll('[data-cartao-email]')[0]!.text())).toContain('Para maria@mercadobompreco.com.br')
    expect(w.findAll('[data-nota-emails] p').map((p) => t(p.text()))).toEqual([
      'Enviado = o provedor aceitou o e-mail. Devoluções da caixa de quem recebe não aparecem aqui.',
      'Guardamos os últimos 90 dias.',
    ])

    await w.get('[data-so-falhas]').trigger('click')
    await flushPromises()
    expect(ultimaBusca(api)).toEqual({ de: somarDias(hoje, -6), ate: hoje, situacao: 'falhou', pagina: '1' })
    expect(t(w.get('[data-so-falhas]').text())).toBe('Ver todos os e-mails')
    expect(t(w.get('[data-total-emails]').text())).toBe('45 e-mails com falha nos últimos 7 dias')
    await w.get('[data-so-falhas]').trigger('click')
    await flushPromises()
    expect(ultimaBusca(api)).toEqual({ de: somarDias(hoje, -29), ate: hoje, pagina: '1' })
  })

  it('filtros (tipo, situação, busca, datas) e paginação', async () => {
    entrar(['auditoria.ver'])
    const api = apiAuditoria()
    const { w } = await abrir('/auditoria/emails', [rotaAuditoria()])
    expect(t(w.text())).toContain('Página 1 de 3')
    await w.findAll('nav[aria-label="Paginação"] button').find((b) => t(b.text()) === 'Próxima')!.trigger('click')
    await flushPromises()
    expect(ultimaBusca(api).pagina).toBe('2')

    await campo(w, 'Tipo').setValue('convite')
    await flushPromises()
    expect(ultimaBusca(api)).toMatchObject({ tipo: 'convite', pagina: '1' })
    await campo(w, 'Situação').setValue('enviado')
    await flushPromises()
    expect(ultimaBusca(api)).toMatchObject({ tipo: 'convite', situacao: 'enviado' })

    const antes = api.chamadas.length
    await campo(w, 'Buscar').setValue('  maria ')
    await new Promise((r) => setTimeout(r, 450))
    await flushPromises()
    expect(api.chamadas.length).toBe(antes + 1)
    expect(ultimaBusca(api)).toMatchObject({ busca: 'maria' })

    // "Escolher as datas" começa no período que valia; data fora dos 90 dias avisa e não busca
    await campo(w, 'Período').setValue('personalizado')
    await flushPromises()
    const hoje = hojeIso()
    expect((campo(w, 'De').element as HTMLInputElement).value).toBe(somarDias(hoje, -29))
    const contagem = api.chamadas.length
    await campo(w, 'De').setValue(somarDias(hoje, -120))
    await flushPromises()
    expect(t(w.text())).toContain('Guardamos só os últimos 90 dias. Escolha uma data inicial mais recente.')
    expect(api.chamadas.length).toBe(contagem)

    await w.get('[data-limpar-filtros]').trigger('click')
    await flushPromises()
    expect(ultimaBusca(api)).toEqual({ de: somarDias(hoje, -29), ate: hoje, pagina: '1' })
  })

  it('vazio: sem falhas não há alerta; com filtro, o vazio diz para mudar os filtros', async () => {
    entrar(['auditoria.ver'])
    apiAuditoria(() => ({ itens: [], total: 0, pagina: 1, por_pagina: 20, falhas_7_dias: 0 }))
    const { w } = await abrir('/auditoria/emails', [rotaAuditoria()])
    expect(w.find('[data-alerta-falhas]').exists()).toBe(false)
    expect(t(w.get('[data-vazio-emails]').text())).toContain('Nenhum e-mail no período')
    expect(w.find('[data-tabela-emails]').exists()).toBe(false)
    await campo(w, 'Situação').setValue('falhou')
    await flushPromises()
    expect(t(w.get('[data-vazio-emails]').text())).toContain('Nenhum e-mail com esses filtros')
  })
})
