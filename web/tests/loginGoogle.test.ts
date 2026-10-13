// Entrar com o Google (docs/api-login-google.md) com a API e o Google simulados: o ID do cliente e o script carregados
// uma vez, o botão "Continuar com o Google" do Toqqi nas telas de Entrar e de Cadastro (e nada sem o ID), a janela do
// Google (token de acesso, recusa, janela fechada ou bloqueada), a entrada de quem tem conta, o "Falta pouco" de quem
// não tem e as recusas.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { CadastroGooglePendente, Sessao } from '@/api/tipos'
import {
  carregarGoogle,
  ESCOPOS_GOOGLE,
  esquecerGoogle,
  idClienteGoogle,
  URL_LOGO_GOOGLE,
  URL_SCRIPT_GOOGLE,
  type GoogleOauth2,
  type RespostaTokenGoogle,
} from '@/composables/google'
import { useSessaoStore } from '@/stores/sessao'
import CadastroView from '@/modulos/acesso/CadastroView.vue'
import EntrarView from '@/modulos/acesso/EntrarView.vue'
import { PRIVACIDADE } from '@/modulos/geral/legal/privacidade'
import { apiFalsa, type Chamada } from './apiFalsa'

const t = (s: string | null | undefined) => (s ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
const CLIENT_ID = '123-abc.apps.googleusercontent.com'

const SESSAO: Sessao = {
  token: 'tok-sessao',
  expira_em: '2099-01-01T00:00:00Z',
  usuario: { id: 7, nome: 'Ana Souza', email: 'ana@alfa.com.br', cargo: null, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, perfil: 'admin', superadmin: false },
  conta: { id: 3, nome: 'Alfa', plano: 'profissional', situacao: 'teste', teste_ate: null, cobranca: { liberada: true, pago_ate: null, atrasada_desde: null, pausa_em: null, aviso: null } },
  permissoes: [] as never,
}
const NOVO: CadastroGooglePendente = { novo: true, cadastro: 'tok-cadastro', email: 'bia@beta.com.br', nome: 'Bia Lima' }

/**
 * O Google Identity Services falso (modelo de token): guarda as opções do `initTokenClient`, conta as janelas abertas
 * e deixa o teste fazer o papel da janela do Google (devolver o token ou o erro).
 */
function googleFalso() {
  const g = {
    opcoes: null as Parameters<GoogleOauth2['initTokenClient']>[0] | null,
    janelas: 0,
    /** A janela do Google respondeu (token ou recusa). */
    responder: (r: RespostaTokenGoogle) => g.opcoes!.callback(r),
    /** A janela não abriu, foi fechada ou deu outro erro. */
    falhar: (type: string) => g.opcoes!.error_callback!({ type }),
  }
  window.google = {
    accounts: {
      oauth2: {
        initTokenClient: (o) => {
          g.opcoes = o
          return { requestAccessToken: () => void g.janelas++ }
        },
      },
    },
  }
  return g
}

let router: Router
async function abrir(caminho: string): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/entrar', name: 'entrar', component: EntrarView },
      { path: '/cadastro', name: 'cadastro', component: CadastroView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

const corpo = (chamadas: Chamada[], caminho: string) => chamadas.filter((c) => c.caminho === caminho).map((c) => c.corpo)
const botao = (w: VueWrapper) => w.get('[data-botao-google]')

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  esquecerGoogle()
  delete window.google
  sessionStorage.clear()
  localStorage.clear()
})
afterEach(() => {
  document.body.innerHTML = ''
  document.head.querySelectorAll(`script[src="${URL_SCRIPT_GOOGLE}"]`).forEach((s) => s.remove())
})

describe('Entrar com o Google › carregamento', () => {
  it('o ID do cliente vem da API uma vez; sem ele (ou com falha), null e tenta de novo depois', async () => {
    let vezes = 0
    const { chamadas } = apiFalsa({ 'GET /auth/google/config': () => (++vezes === 1 ? new Response('{}', { status: 500 }) : { client_id: CLIENT_ID }) })
    expect(await idClienteGoogle()).toBeNull()
    expect(await idClienteGoogle()).toBe(CLIENT_ID)
    expect(await idClienteGoogle()).toBe(CLIENT_ID)
    expect(chamadas.filter((c) => c.caminho === '/auth/google/config')).toHaveLength(2)
  })

  it('o script do Google entra uma vez; se não carrega, null (e a próxima tela tenta de novo)', async () => {
    const primeira = carregarGoogle()
    const segunda = carregarGoogle()
    const scripts = () => document.head.querySelectorAll(`script[src="${URL_SCRIPT_GOOGLE}"]`)
    expect(scripts()).toHaveLength(1)
    scripts()[0]!.dispatchEvent(new Event('error'))
    expect(await primeira).toBeNull()
    expect(await segunda).toBeNull()
    expect(scripts()).toHaveLength(0)
    const terceira = carregarGoogle()
    const g = googleFalso()
    scripts()[0]!.dispatchEvent(new Event('load'))
    expect(await terceira).toBe(window.google!.accounts!.oauth2)
    expect(g.opcoes).toBeNull()
    expect(await carregarGoogle()).toBe(window.google!.accounts!.oauth2) // já carregado: nem cria outro script
    expect(scripts()).toHaveLength(1)
  })
})

describe('Entrar com o Google › tela Entrar', () => {
  it('sem o ID do cliente, nem o botão nem o "ou"', async () => {
    apiFalsa({ 'GET /auth/google/config': () => ({ client_id: null }) })
    const w = await abrir('/entrar')
    expect(w.find('[data-entrar-google]').exists()).toBe(false)
    expect(t(w.text())).not.toContain('ou entre com seu e-mail')
  })

  it('o botão do Toqqi: do tamanho do "Entrar", com o "G" oficial e o texto do Google; o "ou" embaixo', async () => {
    googleFalso()
    apiFalsa({ 'GET /auth/google/config': () => ({ client_id: CLIENT_ID }) })
    const w = await abrir('/entrar')
    expect(w.get('[data-entrar-google]').attributes('data-estado')).toBe('pronto')
    const b = botao(w)
    expect(b.element.tagName).toBe('BUTTON')
    expect(b.attributes('type')).toBe('button')
    expect(t(b.text())).toBe('Continuar com o Google')
    // o mesmo tamanho e os mesmos cantos do "Entrar" (Botao lg), no estilo secundário
    expect(b.classes()).toEqual(expect.arrayContaining(['h-12', 'rounded-xl', 'w-full', 'border-borda-forte']))
    const logo = b.get('img')
    expect(logo.attributes()).toMatchObject({ src: URL_LOGO_GOOGLE, alt: '', width: '20', height: '20', referrerpolicy: 'no-referrer' })
    expect(t(w.get('[data-entrar-google]').text())).toBe('Continuar com o Google ou entre com seu e-mail')
  })

  it('ao clicar, a janela do Google; com o token, a sessão aberta (com o "lembrar") e o destino', async () => {
    const g = googleFalso()
    let soltar: (v: unknown) => void = () => {}
    const { chamadas } = apiFalsa({ 'GET /auth/google/config': () => ({ client_id: CLIENT_ID }), 'POST /auth/google': () => new Promise((r) => (soltar = r)) })
    const w = await abrir('/entrar?voltar=/respostas')
    expect(g.opcoes).toMatchObject({ client_id: CLIENT_ID, scope: ESCOPOS_GOOGLE, prompt: 'select_account' })
    expect(ESCOPOS_GOOGLE).toBe('openid email profile')
    await w.get('input[type="checkbox"]').setValue(true) // "Lembrar de mim neste aparelho"
    await botao(w).trigger('click')
    expect(g.janelas).toBe(1)
    g.responder({ access_token: 'tok-google', expires_in: 3599, scope: 'email profile openid' })
    await flushPromises()
    // enquanto a API confere: "Entrando com o Google…", apagado, sem o "G" e sem abrir outra janela
    expect(t(botao(w).text())).toBe('Entrando com o Google…')
    expect(botao(w).attributes('aria-busy')).toBe('true')
    expect(botao(w).attributes('aria-disabled')).toBe('true')
    expect(botao(w).find('img').exists()).toBe(false)
    await botao(w).trigger('click')
    expect(g.janelas).toBe(1)
    expect(corpo(chamadas, '/auth/google')).toEqual([{ token_acesso: 'tok-google', lembrar: true }])
    soltar(SESSAO)
    await flushPromises()
    expect(useSessaoStore().token).toBe('tok-sessao')
    expect(router.currentRoute.value.fullPath).toBe('/respostas')
  })

  it('janela fechada ou recusada: nada muda; bloqueada ou com erro: o aviso embaixo do botão (some no clique seguinte)', async () => {
    const g = googleFalso()
    const { chamadas } = apiFalsa({ 'GET /auth/google/config': () => ({ client_id: CLIENT_ID }) })
    const w = await abrir('/entrar')
    const aviso = () => w.find('[data-erro-google]')
    await botao(w).trigger('click')
    g.falhar('popup_closed')
    g.responder({ error: 'access_denied' })
    await flushPromises()
    expect(aviso().exists()).toBe(false)
    g.falhar('popup_failed_to_open')
    await flushPromises()
    expect(aviso().attributes('role')).toBe('alert')
    expect(t(aviso().text())).toBe('O navegador bloqueou a janela do Google. Permita janelas pop-up neste site e tente de novo.')
    await botao(w).trigger('click')
    expect(aviso().exists()).toBe(false)
    expect(g.janelas).toBe(2)
    g.responder({ error: 'invalid_request' })
    await flushPromises()
    expect(t(aviso().text())).toBe('Não deu para entrar com o Google agora. Tente de novo ou entre com e-mail e senha.')
    await botao(w).trigger('click')
    g.falhar('unknown')
    await flushPromises()
    expect(t(aviso().text())).toContain('Não deu para entrar com o Google agora.')
    expect(corpo(chamadas, '/auth/google')).toEqual([])
  })

  it('o botão aparece enquanto o script do Google carrega (sem pular a tela), mas só abre a janela depois; sem o script, some', async () => {
    apiFalsa({ 'GET /auth/google/config': () => ({ client_id: CLIENT_ID }) })
    const w = await abrir('/entrar')
    expect(w.get('[data-entrar-google]').attributes('data-estado')).toBe('carregando')
    await botao(w).trigger('click') // ainda sem o cliente do Google: o clique não faz nada
    const script = document.head.querySelector(`script[src="${URL_SCRIPT_GOOGLE}"]`)!
    const g = googleFalso()
    script.dispatchEvent(new Event('load'))
    await flushPromises()
    expect(w.get('[data-entrar-google]').attributes('data-estado')).toBe('pronto')
    expect(g.janelas).toBe(0)
    await botao(w).trigger('click')
    expect(g.janelas).toBe(1)

    // em outra tela, o script não carrega (bloqueador): o botão e o "ou" somem
    esquecerGoogle()
    delete window.google
    document.head.querySelectorAll(`script[src="${URL_SCRIPT_GOOGLE}"]`).forEach((s) => s.remove())
    const w2 = await abrir('/entrar')
    document.head.querySelector(`script[src="${URL_SCRIPT_GOOGLE}"]`)!.dispatchEvent(new Event('error'))
    await flushPromises()
    expect(w2.find('[data-entrar-google]').exists()).toBe(false)
    expect(t(w2.text())).not.toContain('ou entre com seu e-mail')
  })

  it('quem ainda não tem conta vai terminar o cadastro; as recusas aparecem como na entrada com senha', async () => {
    const g = googleFalso()
    let resposta: unknown = NOVO
    apiFalsa({ 'GET /auth/google/config': () => ({ client_id: CLIENT_ID }), 'POST /auth/google': () => resposta })
    const w = await abrir('/entrar')
    await botao(w).trigger('click')
    g.responder({ access_token: 'tok-google' })
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/cadastro')
    expect(useSessaoStore().googlePendente).toEqual(NOVO)
    expect(useSessaoStore().token).toBeNull()

    await router.push('/entrar')
    await flushPromises()
    resposta = new Response(JSON.stringify({ erro: { codigo: 'acesso_pendente', mensagem: 'Seu acesso ainda não foi aprovado.' } }), { status: 403 })
    g.responder({ access_token: 'tok-google' })
    await flushPromises()
    expect(t(w.text())).toContain('Seu acesso está aguardando aprovação')
    resposta = new Response(JSON.stringify({ erro: { codigo: 'google_outra_conta', mensagem: 'Este e-mail já entra no Toqqi por outra conta do Google.' } }), { status: 409 })
    g.responder({ access_token: 'tok-google' })
    await flushPromises()
    expect(t(w.text())).toContain('Este e-mail já entra no Toqqi por outra conta do Google.')
    expect(router.currentRoute.value.path).toBe('/entrar')
  })
})

describe('Entrar com o Google › tela Cadastro', () => {
  it('"Falta pouco": o e-mail do Google, o nome já preenchido, a empresa e o aceite; cria a conta e entra', async () => {
    const { chamadas } = apiFalsa({ 'POST /auth/google/cadastro': () => SESSAO })
    useSessaoStore().googlePendente = { ...NOVO }
    const w = await abrir('/cadastro')
    expect(t(w.text())).toContain('Falta pouco')
    expect(t(w.text())).toContain('Você entrou com o Google como bia@beta.com.br')
    const form = w.get('[data-cadastro-google]')
    const campos = form.findAll('input')
    expect((campos[1]!.element as HTMLInputElement).value).toBe('Bia Lima')
    await form.trigger('submit')
    expect(t(form.text())).toContain('Informe o nome da sua empresa.')
    expect(t(form.text())).toContain('Para continuar, aceite os termos')
    expect(corpo(chamadas, '/auth/google/cadastro')).toEqual([])
    await campos[0]!.setValue('Beta Atacado')
    await campos[2]!.setValue('11987654321')
    await form.get('input[type="checkbox"]').setValue(true)
    await form.trigger('submit')
    await flushPromises()
    expect(corpo(chamadas, '/auth/google/cadastro')).toEqual([
      { cadastro: 'tok-cadastro', empresa: 'Beta Atacado', nome: 'Bia Lima', telefone: '11987654321', aceite_termos: true, origem: null },
    ])
    expect(useSessaoStore().token).toBe('tok-sessao')
    expect(useSessaoStore().googlePendente).toBeNull()
    expect(router.currentRoute.value.path).toBe('/inicio')
  })

  it('token vencido: volta ao cadastro normal com o aviso; "Usar outro e-mail" também volta', async () => {
    apiFalsa({
      'POST /auth/google/cadastro': () =>
        new Response(JSON.stringify({ erro: { codigo: 'cadastro_vencido', mensagem: 'O tempo para terminar o cadastro acabou.' } }), { status: 400 }),
    })
    const s = useSessaoStore()
    s.googlePendente = { ...NOVO }
    const w = await abrir('/cadastro')
    const form = w.get('[data-cadastro-google]')
    await form.findAll('input')[0]!.setValue('Beta')
    await form.get('input[type="checkbox"]').setValue(true)
    await form.trigger('submit')
    await flushPromises()
    expect(s.googlePendente).toBeNull()
    expect(t(w.text())).toContain('Crie sua conta')
    expect(t(w.text())).toContain('O tempo para terminar o cadastro acabou.')
    s.googlePendente = { ...NOVO }
    await flushPromises()
    await w.findAll('button').find((b) => t(b.text()) === 'Usar outro e-mail')!.trigger('click')
    expect(s.googlePendente).toBeNull()
    expect(w.find('[data-cadastro-google]').exists()).toBe(false)
  })

  it('o botão "Continuar com o Google": quem já tem conta entra direto; quem não tem vê o "Falta pouco"', async () => {
    const g = googleFalso()
    let resposta: unknown = SESSAO
    const { chamadas } = apiFalsa({ 'GET /auth/google/config': () => ({ client_id: CLIENT_ID }), 'POST /auth/google': () => resposta })
    const w = await abrir('/cadastro')
    expect(t(botao(w).text())).toBe('Continuar com o Google')
    expect(t(w.get('[data-entrar-google]').text())).toBe('Continuar com o Google ou cadastre com seu e-mail')
    await botao(w).trigger('click')
    g.responder({ access_token: 'tok-google' })
    await flushPromises()
    expect(corpo(chamadas, '/auth/google')).toEqual([{ token_acesso: 'tok-google', lembrar: false }])
    expect(router.currentRoute.value.path).toBe('/inicio')
    useSessaoStore().limpar()
    await router.push('/cadastro')
    await flushPromises()
    resposta = NOVO
    g.responder({ access_token: 'tok-google' })
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/cadastro')
    expect(t(w.text())).toContain('Falta pouco')
  })
})

describe('Entrar com o Google › Política de privacidade (versão 8)', () => {
  const secao = (id: string) => JSON.stringify(PRIVACIDADE.secoes.find((x) => x.id === id))
  it('o que o Google envia, o Google entre os fornecedores e o botão carregado do Google', () => {
    expect(secao('dados-que-tratamos')).toContain('Usuários do Toqqi (entrar com o Google)')
    expect(secao('dados-que-tratamos')).toContain('Não recebemos sua senha do Google nem acesso ao Gmail, ao Drive, à agenda ou aos contatos.')
    expect(secao('compartilhamento')).toContain('Entrar com o Google (opcional), nas telas de entrar e de cadastro')
    expect(secao('transferencia-internacional')).toContain('Render, OpenAI, ZeptoMail, Resend e Google')
    expect(secao('cookies')).toContain('o botão “Entrar com o Google” é carregado do próprio Google')
  })
})
