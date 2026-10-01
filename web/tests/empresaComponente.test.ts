import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { DadosEmpresaConta } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { itemAtivo, navegacaoAdministracao } from '@/layouts/navegacao'
import { router as rotasDoApp } from '@/router'
import EmpresaView from '@/modulos/configuracoes/EmpresaView.vue'
import { apiFalsa, erro422 } from './apiFalsa'

const URL_LOGO = 'http://localhost:8000/api/v1/publico/imagens/Kx7Qm2Vt9Lp4Rz8Wn3Bc6Hd1Fj5Gs0Ya2Ue7Io4Pq9'

const VAZIA: DadosEmpresaConta = {
  nome: 'Transportes Rápidos',
  razao_social: null,
  documento: null,
  telefone: null,
  email_contato: null,
  site: null,
  cep: null,
  logradouro: null,
  numero: null,
  complemento: null,
  bairro: null,
  cidade: null,
  uf: null,
  logo_url: null,
  atualizado_em: null,
}

let router: Router

function entrar(logo: string | null = null) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Transportes Rápidos', plano: null, situacao: 'ativa', teste_ate: null, logo_url: logo },
      permissoes: ['configuracoes.gerenciar', 'envios.ver', 'acoes.ver'],
    },
    false,
  )
}

async function abrir(): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/configuracoes/empresa', component: EmpresaView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  await router.push('/configuracoes/empresa')
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

/** O campo pelo rótulo (sem o "(opcional)"). */
function campo(w: VueWrapper, rotulo: string) {
  const label = w.findAll('label').find((l) => l.text().replace(/\(opcional\)/, '').trim() === rotulo)
  if (!label) throw new Error(`Campo "${rotulo}" não encontrado`)
  return w.get<HTMLInputElement>(`[id="${label.attributes('for')}"]`)
}

/** A mensagem de erro ligada ao campo (aria-describedby), ou null. */
function erroDo(w: VueWrapper, rotulo: string): string | null {
  const c = campo(w, rotulo)
  const id = (c.attributes('aria-describedby') ?? '').split(' ').find((i) => i.endsWith('-erro'))
  return id ? w.get(`[id="${id}"]`).text() : null
}

const botao = (w: VueWrapper, texto: string) => {
  const b = w.findAll('button').find((x) => x.text().trim() === texto)
  if (!b) throw new Error(`Botão "${texto}" não encontrado`)
  return b
}

const png = () => new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0x0d])], 'logo.png', { type: 'image/png' })

async function escolherArquivo(w: VueWrapper, arquivo: File) {
  const entrada = w.get('input[type="file"]')
  Object.defineProperty(entrada.element, 'files', { value: [arquivo], configurable: true })
  await entrada.trigger('change')
  await flushPromises()
}

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
})

describe('Configurações › Empresa', () => {
  it('rota só para quem gerencia as configurações; o item Configurações do menu abre nela', () => {
    const rota = rotasDoApp.resolve('/configuracoes/empresa')
    expect(rota.name).toBe('config-empresa')
    expect(rota.meta.permissao).toBe('configuracoes.gerenciar')
    const configuracoes = navegacaoAdministracao.find((i) => i.rotulo === 'Configurações')!
    expect(configuracoes.para).toBe('/configuracoes/empresa')
    expect(itemAtivo(configuracoes, '/configuracoes/seguranca', {}, false)).toBe(true)
  })

  it('conta só com o nome: campos vazios, sem logo, e Empresa é a primeira seção de Configurações', async () => {
    entrar()
    apiFalsa({ 'GET /conta/dados': () => VAZIA })
    const w = await abrir()
    expect(campo(w, 'Nome da empresa').element.value).toBe('Transportes Rápidos')
    expect(campo(w, 'CNPJ').element.value).toBe('')
    expect(w.text()).toContain('É assim que a empresa aparece nas pesquisas e nos e-mails')
    expect(w.text()).toContain('Também aceita CPF.')
    expect(w.findAll('select option')).toHaveLength(28) // "Escolha" + 27 UFs
    expect(w.text()).toContain('Sua empresa ainda não tem logo.')
    expect(w.text()).toContain('Enviar logo')
    expect(w.text()).not.toContain('Remover')
    expect(botao(w, 'Salvar alterações').attributes('disabled')).toBeDefined()
    const secoes = w.get('nav[aria-label="Seções de configurações"]').findAll('a')
    expect(secoes[0]!.text()).toBe('Empresa')
    expect(secoes[0]!.attributes('aria-current')).toBe('page')
  })

  it('máscaras ao digitar e, ao salvar, a API recebe só os dígitos; o nome no topo muda na hora', async () => {
    entrar()
    const { chamadas } = apiFalsa({
      'GET /conta/dados': () => VAZIA,
      'PUT /conta/dados': ({ corpo }) => ({
        ...VAZIA,
        ...(corpo as object),
        telefone: '5511912345678',
        site: 'https://www.rapidos.com.br',
        atualizado_em: '2026-10-01T12:00:00Z',
      }),
    })
    const w = await abrir()
    await campo(w, 'Nome da empresa').setValue('Rápidos Transportes')
    await campo(w, 'CNPJ').setValue('11222333000181')
    expect(campo(w, 'CNPJ').element.value).toBe('11.222.333/0001-81')
    await campo(w, 'Telefone ou WhatsApp').setValue('11912345678')
    expect(campo(w, 'Telefone ou WhatsApp').element.value).toBe('(11) 91234-5678')
    await campo(w, 'Site').setValue('www.rapidos.com.br')
    await campo(w, 'Número').setValue('1000')
    expect(w.text()).toContain('Você tem alterações não salvas.')

    await w.get('form').trigger('submit')
    await flushPromises()
    const put = chamadas.find((c) => c.metodo === 'PUT')!
    expect(put.caminho).toBe('/conta/dados')
    expect(put.corpo).toEqual({
      nome: 'Rápidos Transportes',
      razao_social: null,
      documento: '11222333000181',
      telefone: '11912345678',
      email_contato: null,
      site: 'www.rapidos.com.br',
      cep: null,
      logradouro: null,
      numero: '1000',
      complemento: null,
      bairro: null,
      cidade: null,
      uf: null,
    })
    expect(useSessaoStore().conta?.nome).toBe('Rápidos Transportes')
    expect(avisos.at(-1)?.mensagem).toBe('Dados da empresa salvos.')
    // Volta como o servidor gravou, sem alterações pendentes.
    expect(campo(w, 'Site').element.value).toBe('https://www.rapidos.com.br')
    expect(w.text()).not.toContain('Você tem alterações não salvas.')
    expect(w.text()).toContain('Última alteração em')
  })

  it('confere antes de enviar: CNPJ errado não vai para a API e o erro aparece no campo', async () => {
    entrar()
    const { chamadas } = apiFalsa({ 'GET /conta/dados': () => VAZIA })
    const w = await abrir()
    await campo(w, 'CNPJ').setValue('11222333000180')
    await campo(w, 'CEP').setValue('0131')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(chamadas.some((c) => c.metodo === 'PUT')).toBe(false)
    expect(erroDo(w, 'CNPJ')).toBe('CNPJ ou CPF inválido. Confira os números.')
    expect(erroDo(w, 'CEP')).toBe('Informe o CEP com 8 números, como 01310-100.')
    expect(w.text()).toContain('Confira os campos destacados.')
    expect(document.activeElement).toBe(campo(w, 'CNPJ').element)
  })

  it('422 do servidor: cada mensagem aparece no seu campo e nada muda na sessão', async () => {
    entrar()
    apiFalsa({
      'GET /conta/dados': () => VAZIA,
      'PUT /conta/dados': () =>
        erro422('Confira os campos destacados.', {
          site: 'Informe um site válido, como www.suaempresa.com.br.',
          email_contato: 'Informe um e-mail válido, como nome@empresa.com.br.',
        }),
    })
    const w = await abrir()
    await campo(w, 'Nome da empresa').setValue('Outro nome')
    await campo(w, 'Site').setValue('www.rapidos.local')
    await campo(w, 'E-mail').setValue('contato@rapidos.test')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(erroDo(w, 'Site')).toBe('Informe um site válido, como www.suaempresa.com.br.')
    expect(erroDo(w, 'E-mail')).toBe('Informe um e-mail válido, como nome@empresa.com.br.')
    expect(campo(w, 'Site').attributes('aria-invalid')).toBe('true')
    expect(useSessaoStore().conta?.nome).toBe('Transportes Rápidos')
    // As alterações continuam na tela para corrigir.
    expect(campo(w, 'Nome da empresa').element.value).toBe('Outro nome')
  })

  it('CEP completo preenche só os campos vazios do endereço', async () => {
    entrar()
    const { chamadas } = apiFalsa({
      'GET /conta/dados': () => VAZIA,
      'GET /ws/:cep/json/': () => ({ cep: '01310-100', logradouro: 'Avenida Paulista', bairro: 'Bela Vista', localidade: 'São Paulo', uf: 'SP' }),
    })
    const w = await abrir()
    await campo(w, 'Logradouro').setValue('Av. Paulista, escrita à mão')
    await campo(w, 'CEP').setValue('01310100')
    await vi.waitFor(() => expect(campo(w, 'Cidade').element.value).toBe('São Paulo'))
    expect(chamadas.find((c) => c.url.hostname === 'viacep.com.br')?.url.href).toBe('https://viacep.com.br/ws/01310100/json/')
    expect(campo(w, 'CEP').element.value).toBe('01310-100')
    expect(campo(w, 'Logradouro').element.value).toBe('Av. Paulista, escrita à mão')
    expect(campo(w, 'Bairro').element.value).toBe('Bela Vista')
    expect((w.get('select').element as HTMLSelectElement).value).toBe('SP')
    expect(w.text()).toContain('Endereço preenchido pelo CEP. Confira e complete o número.')
  })

  it('CEP que não existe (ou ViaCEP fora do ar): nada muda e não aparece erro', async () => {
    entrar()
    apiFalsa({ 'GET /conta/dados': () => VAZIA, 'GET /ws/:cep/json/': () => ({ erro: true }) })
    const w = await abrir()
    await campo(w, 'CEP').setValue('99999999')
    await flushPromises()
    await flushPromises()
    expect(campo(w, 'Cidade').element.value).toBe('')
    expect(w.text()).not.toContain('Endereço preenchido')
    expect(w.text()).not.toContain('Buscando o endereço')
    expect(w.find('[role="alert"]').exists()).toBe(false)

    // Sem internet: também segue manual.
    vi.unstubAllGlobals()
    apiFalsa({
      'GET /ws/:cep/json/': () => {
        throw new TypeError('Failed to fetch')
      },
    })
    await campo(w, 'CEP').setValue('01310100')
    await flushPromises()
    await flushPromises()
    expect(campo(w, 'Cidade').element.value).toBe('')
    expect(w.text()).not.toContain('Buscando o endereço')
  })

  it('sair com alterações não salvas pede confirmação (e fechar a aba também avisa)', async () => {
    entrar()
    apiFalsa({ 'GET /conta/dados': () => VAZIA })
    const w = await abrir()
    const semMudanca = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(semMudanca)
    expect(semMudanca.defaultPrevented).toBe(false)

    await campo(w, 'Razão social').setValue('Transportes Rápidos Ltda.')
    const fechar = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(fechar)
    expect(fechar.defaultPrevented).toBe(true)

    const ida = router.push('/inicio')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Sair sem salvar?')
    responderConfirmacao(false)
    await ida
    expect(router.currentRoute.value.path).toBe('/configuracoes/empresa')

    // Descartar volta ao que estava salvo e libera a saída.
    await botao(w, 'Descartar').trigger('click')
    expect(campo(w, 'Razão social').element.value).toBe('')
    await router.push('/inicio')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(false)
    expect(router.currentRoute.value.path).toBe('/inicio')
  })

  it('enviar o logo vale na hora: PUT /conta/logo com o arquivo, prévia e sessão atualizadas, sem perder o que está sendo editado', async () => {
    entrar()
    const { chamadas } = apiFalsa({
      'GET /conta/dados': () => VAZIA,
      'PUT /conta/logo': () => ({ ...VAZIA, logo_url: URL_LOGO, atualizado_em: '2026-10-01T12:00:00Z' }),
    })
    const w = await abrir()
    await campo(w, 'Razão social').setValue('Transportes Rápidos Ltda.')
    await escolherArquivo(w, png())
    await vi.waitFor(() => expect(chamadas.some((c) => c.metodo === 'PUT' && c.caminho === '/conta/logo')).toBe(true))
    await flushPromises()
    const envio = chamadas.find((c) => c.caminho === '/conta/logo')!
    expect(envio.corpo).toBeInstanceOf(FormData)
    expect(((envio.corpo as FormData).get('arquivo') as File).name).toBe('logo.png')
    const imagens = w.findAll('img')
    expect(imagens).toHaveLength(2) // fundo claro e escuro
    expect(imagens.every((i) => i.attributes('src') === URL_LOGO)).toBe(true)
    expect(useSessaoStore().conta?.logo_url).toBe(URL_LOGO)
    expect(w.text()).toContain('Trocar logo')
    expect(campo(w, 'Razão social').element.value).toBe('Transportes Rápidos Ltda.')
    expect(w.text()).toContain('Você tem alterações não salvas.')
  })

  it('arquivo que não é PNG/JPG nem sai daqui; mensagem igual à da API', async () => {
    entrar()
    const { chamadas } = apiFalsa({ 'GET /conta/dados': () => VAZIA })
    const w = await abrir()
    await escolherArquivo(w, new File(['GIF89a....'], 'logo.png', { type: 'image/png' }))
    await vi.waitFor(() => expect(w.text()).toContain('Use uma imagem PNG ou JPG de até 300 KB.'))
    expect(chamadas.some((c) => c.caminho === '/conta/logo')).toBe(false)
  })

  it('depois de entrar, a sessão busca GET /eu para ter o logo da conta (a resposta do login não traz)', async () => {
    const usuario = { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'admin' as const, situacao: 'ativo' as const, email_confirmado: true, ultimo_acesso: null, superadmin: false }
    const conta = { id: 1, nome: 'Transportes Rápidos', plano: null, situacao: 'ativa', teste_ate: null }
    const { chamadas } = apiFalsa({
      'POST /auth/entrar': () => ({ token: 't', expira_em: '2099-01-01T00:00:00Z', usuario, conta, permissoes: ['configuracoes.gerenciar'] }),
      'GET /eu': () => ({ usuario, conta: { ...conta, logo_url: URL_LOGO }, permissoes: ['configuracoes.gerenciar'] }),
    })
    const sessao = useSessaoStore()
    await sessao.entrar('a@x.com', 'segredo', false)
    await vi.waitFor(() => expect(sessao.conta?.logo_url).toBe(URL_LOGO))
    expect(chamadas.map((c) => `${c.metodo} ${c.caminho}`)).toEqual(['POST /auth/entrar', 'GET /eu'])
  })

  it('remover o logo pede confirmação e chama DELETE /conta/logo', async () => {
    entrar(URL_LOGO)
    const { chamadas } = apiFalsa({ 'GET /conta/dados': () => ({ ...VAZIA, logo_url: URL_LOGO }), 'DELETE /conta/logo': () => undefined })
    const w = await abrir()
    await botao(w, 'Remover').trigger('click')
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Remover o logo da empresa?')
    responderConfirmacao(true)
    await flushPromises()
    expect(chamadas.some((c) => c.metodo === 'DELETE' && c.caminho === '/conta/logo')).toBe(true)
    expect(useSessaoStore().conta?.logo_url).toBeNull()
    expect(w.findAll('img')).toHaveLength(0)
    expect(w.text()).toContain('Sua empresa ainda não tem logo.')
    expect(avisos.at(-1)?.mensagem).toBe('Logo removido.')
  })
})
