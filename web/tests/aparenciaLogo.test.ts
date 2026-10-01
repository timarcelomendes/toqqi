import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { h, reactive } from 'vue'
import type { Pergunta, Tema } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { TEMA_PADRAO } from '@/pesquisa/tipos'
import { useSessaoStore } from '@/stores/sessao'
import AbaAparencia from '@/modulos/formularios/editor/AbaAparencia.vue'
import PreVisualizacao from '@/modulos/formularios/editor/PreVisualizacao.vue'
import { apiFalsa, erro422 } from './apiFalsa'

const LOGO_FORM = 'http://localhost:8000/api/v1/publico/imagens/Fm1Qx8Lt3Vp6Rz0Wn5Bc2Hd9Fj4Gs7Ya1Ue6Io3Pq8'
const LOGO_EMPRESA = 'http://localhost:8000/api/v1/publico/imagens/Em7Kz2Vt9Lp4Rz8Wn3Bc6Hd1Fj5Gs0Ya2Ue7Io4Pq9'

function entrar(logo: string | null, permissoes = ['formularios.ver', 'formularios.editar', 'configuracoes.gerenciar']) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Transportes Rápidos', plano: null, situacao: 'ativa', teste_ate: null, logo_url: logo },
      permissoes,
    },
    false,
  )
}

const roteador = () =>
  createRouter({ history: createMemoryHistory(), routes: [{ path: '/:qualquer(.*)*', component: { render: () => h('div') } }] })

function abrirAparencia(tema: Tema): VueWrapper {
  return mount(AbaAparencia, {
    props: { tema, descricao: '', erros: {}, formularioId: 7 },
    global: { plugins: [roteador()] },
    attachTo: document.body,
  })
}

const png = () => new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0x0d])], 'logo.png', { type: 'image/png' })

async function escolherArquivo(w: VueWrapper, arquivo: File) {
  const entrada = w.get('input[type="file"]')
  Object.defineProperty(entrada.element, 'files', { value: [arquivo], configurable: true })
  await entrada.trigger('change')
  await flushPromises()
}

const temEndereco = (w: VueWrapper) => w.findAll('label').some((l) => l.text() === 'Endereço da imagem')

enableAutoUnmount(afterEach)
beforeEach(() => setActivePinia(createPinia()))
afterEach(() => {
  vi.unstubAllGlobals()
  avisos.splice(0)
  document.body.innerHTML = ''
})

describe('Editor › Aparência: logo do formulário', () => {
  it('enviar arquivo chama POST /formularios/{id}/logo e o tema guarda a URL devolvida (nunca data:)', async () => {
    entrar(null)
    const { chamadas } = apiFalsa({ 'POST /formularios/:id/logo': () => ({ logo_url: LOGO_FORM }) })
    const tema = reactive<Tema>({ ...TEMA_PADRAO })
    const w = abrirAparencia(tema)
    expect(w.get('input[type="file"]').attributes('accept')).toBe('image/png,image/jpeg')

    await escolherArquivo(w, png())
    await vi.waitFor(() => expect(tema.logo_url).toBe(LOGO_FORM))
    const envio = chamadas.find((c) => c.metodo === 'POST')!
    expect(envio.caminho).toBe('/formularios/7/logo')
    expect(envio.corpo).toBeInstanceOf(FormData)
    expect(((envio.corpo as FormData).get('arquivo') as File).name).toBe('logo.png')
    expect(tema.logo_url?.startsWith('data:')).toBe(false)
    await flushPromises()
    // Imagem enviada: a URL interna não aparece para editar; o botão vira "Trocar imagem".
    expect(temEndereco(w)).toBe(false)
    expect(w.text()).toContain('Trocar imagem')
    expect(w.get('img[alt="Logo do formulário"]').attributes('src')).toBe(LOGO_FORM)
    expect(avisos.at(-1)?.mensagem).toContain('Salve o formulário')
  })

  it('SVG, WebP ou GIF não são aceitos (nem chegam à API)', async () => {
    entrar(null)
    const { chamadas } = apiFalsa({})
    const tema = reactive<Tema>({ ...TEMA_PADRAO })
    const w = abrirAparencia(tema)
    await escolherArquivo(w, new File(['<svg xmlns="http://www.w3.org/2000/svg"/>'], 'logo.svg', { type: 'image/svg+xml' }))
    await vi.waitFor(() => expect(w.text()).toContain('Use uma imagem PNG ou JPG de até 300 KB.'))
    expect(chamadas).toHaveLength(0)
    expect(tema.logo_url).toBeNull()
  })

  it('recusa do servidor (422 arquivo) aparece no lugar do logo', async () => {
    entrar(null)
    apiFalsa({ 'POST /formularios/:id/logo': () => erro422('Dados inválidos.', { arquivo: 'Use uma imagem PNG ou JPG de até 300 KB.' }) })
    const tema = reactive<Tema>({ ...TEMA_PADRAO })
    const w = abrirAparencia(tema)
    await escolherArquivo(w, png())
    await vi.waitFor(() => expect(w.get('[role="alert"]').text()).toBe('Use uma imagem PNG ou JPG de até 300 KB.'))
    expect(tema.logo_url).toBeNull()
  })

  it('endereço https:// continua valendo (o campo aparece para quem não enviou arquivo)', async () => {
    entrar(null)
    const tema = reactive<Tema>({ ...TEMA_PADRAO, logo_url: 'https://suaempresa.com.br/logo.png' })
    const w = abrirAparencia(tema)
    expect(temEndereco(w)).toBe(true)
    expect(w.text()).toContain('Enviar imagem')
  })

  it('sem logo no formulário, mostra o logo da empresa com o aviso "Usando o logo da empresa"', async () => {
    entrar(LOGO_EMPRESA)
    const tema = reactive<Tema>({ ...TEMA_PADRAO })
    const w = abrirAparencia(tema)
    expect(w.text()).toContain('Usando o logo da empresa.')
    expect(w.get('img[alt="Logo da empresa"]').attributes('src')).toBe(LOGO_EMPRESA)
    expect(w.get('[data-logo-empresa] a').attributes('href')).toBe('/configuracoes/empresa')
    // O tema do formulário continua sem logo próprio.
    expect(tema.logo_url).toBeNull()

    // Com logo próprio, o da empresa sai de cena.
    tema.logo_url = LOGO_FORM
    await flushPromises()
    expect(w.text()).not.toContain('Usando o logo da empresa')
  })

  it('imagem que não abre ganha aviso (sem piscar enquanto o endereço é digitado)', async () => {
    vi.useFakeTimers()
    try {
      entrar(null)
      const tema = reactive<Tema>({ ...TEMA_PADRAO, logo_url: 'https://suaempresa.com.br/logo-que-nao-existe.png' })
      const w = abrirAparencia(tema)
      await w.get('img[alt="Logo do formulário"]').trigger('error')
      vi.advanceTimersByTime(300)
      await flushPromises()
      expect(w.text()).not.toContain('Não conseguimos mostrar esta imagem')
      vi.advanceTimersByTime(600)
      await flushPromises()
      expect(w.text()).toContain('Não conseguimos mostrar esta imagem')
      // Endereço novo: o aviso some até a imagem nova falhar também.
      tema.logo_url = 'https://suaempresa.com.br/logo.png'
      await flushPromises()
      expect(w.text()).not.toContain('Não conseguimos mostrar esta imagem')
    } finally {
      vi.useRealTimers()
    }
  })

  it('quem não cuida das configurações vê o aviso, mas sem o link para trocar o logo da empresa', () => {
    entrar(LOGO_EMPRESA, ['formularios.ver', 'formularios.editar'])
    const w = abrirAparencia(reactive<Tema>({ ...TEMA_PADRAO }))
    expect(w.text()).toContain('Usando o logo da empresa.')
    expect(w.find('[data-logo-empresa] a').exists()).toBe(false)
  })
})

describe('Pré-visualização: logo da empresa quando o formulário não tem', () => {
  const perguntas: Pergunta[] = [{ id: 'nota', tipo: 'nps', titulo: 'Recomendaria a {empresa}?', obrigatoria: true }]
  const abrirPrevia = (tema: Tema) =>
    mount(PreVisualizacao, { props: { nome: 'NPS', perguntas, tema, nomeEmpresa: 'Transportes Rápidos' }, attachTo: document.body })

  it('sem logo no formulário: a pesquisa mostra o da empresa e avisa', async () => {
    entrar(LOGO_EMPRESA)
    const w = abrirPrevia({ ...TEMA_PADRAO })
    await flushPromises()
    expect(w.get('.pesquisa header img').attributes('src')).toBe(LOGO_EMPRESA)
    expect(w.get('[data-aviso-logo]').text()).toBe('Usando o logo da empresa')
  })

  it('com logo no formulário: mostra o dele, sem aviso', async () => {
    entrar(LOGO_EMPRESA)
    const w = abrirPrevia({ ...TEMA_PADRAO, logo_url: LOGO_FORM })
    await flushPromises()
    expect(w.get('.pesquisa header img').attributes('src')).toBe(LOGO_FORM)
    expect(w.find('[data-aviso-logo]').exists()).toBe(false)
  })

  it('sem nenhum dos dois: sem logo e sem aviso', async () => {
    entrar(null)
    const w = abrirPrevia({ ...TEMA_PADRAO })
    await flushPromises()
    expect(w.find('.pesquisa header img').exists()).toBe(false)
    expect(w.find('[data-aviso-logo]').exists()).toBe(false)
  })
})
