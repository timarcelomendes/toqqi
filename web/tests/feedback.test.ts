// Feedback (docs/api-feedback.md): a janela "Enviar feedback", Seus feedbacks, a conversa, Plataforma › Feedback, o
// diagnóstico que vai junto no erro e as regras puras.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { h } from 'vue'
import { formularioDoFeedback, type Feedback, type FeedbackPlataforma } from '@/api'
import { api } from '@/api/cliente'
import { useSessaoStore } from '@/stores/sessao'
import { limparFeedback, usarFeedback } from '@/composables/feedback'
import { diagnosticoAtual, diagnosticoParaEnvio, limparDiagnostico, registrarErroDoSite } from '@/utils/diagnostico'
import { criarAvisoDeErros } from '@/utils/erros'
import {
  erroDoTexto,
  infoSituacao,
  medidasReduzidas,
  nomeDaImagem,
  rotuloQuando,
  telaDeOrigem,
  textoDepoimento,
} from '@/modulos/feedback/logica'
import ModalFeedback from '@/modulos/feedback/ModalFeedback.vue'
import FeedbacksView from '@/modulos/feedback/FeedbacksView.vue'
import FeedbackView from '@/modulos/feedback/FeedbackView.vue'
import AbaFeedback from '@/modulos/plataforma/AbaFeedback.vue'
import FeedbackPlataformaView from '@/modulos/plataforma/FeedbackPlataformaView.vue'
import BarraLateral from '@/layouts/BarraLateral.vue'
import { apiFalsa, erro422 } from './apiFalsa'

function entrar(superadmin = false) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'ana@alfa.com.br', cargo: null, perfil: 'admin', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin },
      conta: { id: 1, nome: 'Alfa', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes: [],
    } as never,
    false,
  )
}

async function roteador(caminho: string): Promise<Router> {
  const vazio = { render: () => h('div') }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/formularios/:id', component: vazio, meta: { titulo: 'Formulário' } },
      { path: '/feedback/:id', component: vazio, meta: { titulo: 'Feedback' } },
      { path: '/plataforma/feedback/:id', component: vazio, meta: { titulo: 'Feedback' } },
      { path: '/:qualquer(.*)*', component: vazio },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  return router
}

const montados: VueWrapper[] = []

async function montar(componente: object, caminho: string, router?: Router): Promise<VueWrapper> {
  const w = mount(componente, { global: { plugins: [router ?? (await roteador(caminho))] }, attachTo: document.body })
  montados.push(w)
  await flushPromises()
  return w
}

const corpo = () => document.body
const naTela = <T extends HTMLElement = HTMLElement>(seletor: string) => corpo().querySelector<T>(seletor)
const camposDo = (f: unknown) => Object.fromEntries([...(f as FormData).entries()].map(([k, v]) => [k, typeof v === 'string' ? v : `arquivo:${(v as File).name}`]))

const mensagem = (id: number, autor: 'usuario' | 'equipe', texto: string, extra: object = {}) => ({
  id, autor, autor_nome: autor === 'equipe' ? 'Marcelo' : 'Ana', texto, situacao: null, criado_em: '2026-10-06T21:00:00Z', imagens: [], ...extra,
})

function feedbackFalso(extra: Partial<Feedback> = {}): Feedback {
  return {
    id: 7, tipo: 'erro', situacao: 'em_analise', impacto: 'bloqueia', autoriza_depoimento: false, pagina: '/formularios/3', pagina_titulo: 'Formulário',
    criado_em: '2026-10-06T21:00:00Z', atualizado_em: '2026-10-06T22:00:00Z',
    mensagens: [mensagem(1, 'usuario', 'O botão Salvar não responde.'), mensagem(2, 'equipe', 'Já estamos olhando.'), mensagem(3, 'equipe', '', { situacao: 'em_analise' })],
    ...extra,
  } as Feedback
}

beforeEach(() => {
  setActivePinia(createPinia())
  limparFeedback()
  limparDiagnostico()
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:falso'), revokeObjectURL: vi.fn() }))
})
afterEach(async () => {
  await flushPromises()
  for (const w of montados.splice(0)) w.unmount()
  document.body.innerHTML = ''
})

describe('regras do feedback', () => {
  it('depoimento pronto para colar, tela de origem e textos', () => {
    expect(textoDepoimento('  O Toqqi\nmudou tudo. ', 'Ana Souza', 'Alfa Ltda')).toBe('“O Toqqi mudou tudo.” — Ana Souza, Alfa Ltda')
    expect(textoDepoimento('Ótimo', null, '')).toBe('“Ótimo”')
    expect(telaDeOrigem({ path: '/formularios/3?aba=1', titulo: 'Formulário' })).toEqual({ pagina: '/formularios/3', titulo: 'Formulário' })
    expect(telaDeOrigem({ path: '/feedback', titulo: 'Seus feedbacks' }, { path: '/contatos', titulo: 'Contatos' })).toEqual({ pagina: '/contatos', titulo: 'Contatos' })
    expect(telaDeOrigem({ path: '/feedback/3', titulo: 'Feedback' }, null)).toBeNull()
    expect(erroDoTexto('   ')).toBe('Escreva o que você quer contar.')
    expect(erroDoTexto('', true)).toBeNull()
    expect(erroDoTexto('x'.repeat(5001))).toBe('Use até 5.000 caracteres.')
    expect(infoSituacao('planejado')).toEqual({ rotulo: 'Planejado', tom: 'marca' })
    expect(infoSituacao('outra')).toEqual({ rotulo: 'outra', tom: 'neutro' })
  })

  it('quando: agora, minutos, hoje, ontem, data', () => {
    const agora = new Date('2026-10-06T21:30:00-03:00')
    expect(rotuloQuando('2026-10-06T21:29:40-03:00', agora)).toBe('agora há pouco')
    expect(rotuloQuando('2026-10-06T21:18:00-03:00', agora)).toBe('há 12 min')
    expect(rotuloQuando('2026-10-06T08:05:00-03:00', agora)).toBe('hoje às 08:05')
    expect(rotuloQuando('2026-10-05T23:59:00-03:00', agora)).toBe('ontem às 23:59')
    expect(rotuloQuando('2026-09-30T10:00:00-03:00', agora)).toBe('30/09 às 10:00')
    expect(rotuloQuando('2025-12-31T10:00:00-03:00', agora)).toBe('31/12/2025 às 10:00')
    expect(rotuloQuando(null)).toBe('—')
  })

  it('imagens: medidas reduzidas e nomes', () => {
    expect(medidasReduzidas(3840, 2160, 1920)).toEqual({ largura: 1920, altura: 1080 })
    expect(medidasReduzidas(800, 600, 1920)).toEqual({ largura: 800, altura: 600 })
    expect(nomeDaImagem('Captura de Tela.webp', 'image/jpeg')).toBe('Captura de Tela.jpg')
    expect(nomeDaImagem('image.png', 'image/png', 2)).toBe('print-2.png')
    expect(nomeDaImagem(null, 'image/png', 3)).toBe('print-3.png')
  })

  it('o envio leva os detalhes técnicos só quando marcados', () => {
    const imagem = { blob: new Blob(['x'], { type: 'image/png' }), nome: 'print-1.png' }
    const com = camposDo(formularioDoFeedback({ tipo: 'erro', texto: 'Falhou', impacto: 'bloqueia', detalhes: true, pagina: '/x', pagina_titulo: 'X', tela: '1280x800', versao_site: 'abc', diagnostico: '{"erros":[]}', imagens: [imagem] }))
    expect(com).toEqual({ tipo: 'erro', texto: 'Falhou', impacto: 'bloqueia', detalhes: 'true', pagina: '/x', pagina_titulo: 'X', tela: '1280x800', versao_site: 'abc', diagnostico: '{"erros":[]}', imagens: 'arquivo:print-1.png' })
    const sem = camposDo(formularioDoFeedback({ tipo: 'elogio', texto: 'Bom', autoriza_depoimento: true, detalhes: false, tela: '1280x800', versao_site: 'abc' }))
    expect(sem).toEqual({ tipo: 'elogio', texto: 'Bom', autoriza_depoimento: 'true', detalhes: 'false' })
  })
})

describe('diagnóstico que vai junto no erro', () => {
  it('guarda os pedidos que falharam (com o request id) e os erros do site, sem 401', async () => {
    apiFalsa({
      'GET /contatos': () => new Response(JSON.stringify({ erro: { codigo: 'erro_interno', mensagem: 'x' } }), { status: 500, headers: { 'X-Request-ID': 'abc123' } }),
      'GET /eu': () => new Response(JSON.stringify({ erro: { codigo: 'sessao_invalida', mensagem: 'x' } }), { status: 401 }),
    })
    await expect(api.get('/contatos?busca=ana@x.com', { semTratamentoGlobal: true })).rejects.toThrow()
    await expect(api.get('/eu', { semTratamentoGlobal: true })).rejects.toThrow()
    const aviso = criarAvisoDeErros({ origem: 'http://app', caminho: () => '/contatos/12', enviar: () => {} })
    aviso.avisar(new TypeError('x is undefined'))
    aviso.avisar(new TypeError('x is undefined')) // repetido seguido: um só
    const d = diagnosticoAtual()
    expect(d.pedidos.map((p) => [p.metodo, p.caminho, p.status, p.codigo, p.request_id])).toEqual([['GET', '/contatos', 500, 'erro_interno', 'abc123']])
    expect(d.erros.map((e) => [e.tipo, e.mensagem, e.local])).toEqual([['TypeError', 'x is undefined', '/contatos/:id']])
    for (let i = 0; i < 15; i++) registrarErroDoSite({ tipo: 'E', mensagem: `m${i}`, local: '/' })
    expect(diagnosticoAtual().erros).toHaveLength(10)
    limparDiagnostico()
    expect(diagnosticoParaEnvio()).toBeNull()
  })
})

describe('janela Enviar feedback', () => {
  it('escolhe o tipo, valida, envia com a tela de origem e o diagnóstico e mostra a conclusão', async () => {
    entrar()
    const fake = apiFalsa({ 'POST /feedback': () => ({ ...feedbackFalso(), id: 42 }) })
    registrarErroDoSite({ tipo: 'TypeError', mensagem: 'falhou', local: '/formularios/:id' })
    await montar(ModalFeedback, '/formularios/3')
    usarFeedback().abrir()
    await flushPromises()
    expect(naTela('[data-passo-feedback="tipo"]')).not.toBeNull()
    expect([...corpo().querySelectorAll('[data-tipo-feedback]')].map((b) => b.getAttribute('data-tipo-feedback'))).toEqual(['erro', 'sugestao', 'melhoria', 'elogio'])
    naTela('[data-tipo-feedback="erro"]')!.click()
    await flushPromises()
    expect(naTela('[data-tela-origem]')!.textContent).toContain('Tela: Formulário')
    // sem texto: não envia
    naTela('[data-enviar-feedback]')!.click()
    await flushPromises()
    expect(fake.chamadas).toHaveLength(0)
    expect(corpo().textContent).toContain('Escreva o que você quer contar.')
    const area = naTela<HTMLTextAreaElement>('textarea[data-texto-feedback]')!
    area.value = '  O botão Salvar não responde.  '
    area.dispatchEvent(new Event('input'))
    const travado = [...corpo().querySelectorAll<HTMLInputElement>('input[type="radio"]')].find((r) => r.value === 'bloqueia')!
    travado.checked = true
    travado.dispatchEvent(new Event('change'))
    await flushPromises()
    naTela('[data-enviar-feedback]')!.click()
    await flushPromises()
    const [envio] = fake.chamadas
    expect(envio!.metodo).toBe('POST')
    const campos = camposDo(envio!.corpo)
    expect(campos).toMatchObject({ tipo: 'erro', texto: 'O botão Salvar não responde.', impacto: 'bloqueia', detalhes: 'true', pagina: '/formularios/3', pagina_titulo: 'Formulário' })
    expect(JSON.parse(campos.diagnostico!).erros[0].tipo).toBe('TypeError')
    expect(naTela('[data-passo-feedback="enviado"]')!.textContent).toContain('Recebemos seu feedback!')
    expect(naTela('[data-ver-conversa]')!.getAttribute('href')).toBe('/feedback/42')
  })

  it('elogio: sem detalhes técnicos, com a autorização do depoimento; erro da API aparece na janela', async () => {
    entrar()
    let tentativas = 0
    const fake = apiFalsa({ 'POST /feedback': () => (++tentativas === 1 ? erro422('Use imagens PNG ou JPG de até 1 MB.', { imagens: 'Use imagens PNG ou JPG de até 1 MB.' }) : { ...feedbackFalso(), tipo: 'elogio' }) })
    await montar(ModalFeedback, '/inicio')
    usarFeedback().abrir('elogio')
    await flushPromises()
    expect(naTela('[data-passo-feedback="texto"]')).not.toBeNull()
    expect(naTela('[data-detalhes-tecnicos]')).toBeNull()
    const area = naTela<HTMLTextAreaElement>('textarea')!
    area.value = 'Adorei o resumo da IA.'
    area.dispatchEvent(new Event('input'))
    const caixa = naTela('[data-autoriza-depoimento]')!.querySelector<HTMLInputElement>('input[type="checkbox"]')!
    caixa.checked = true
    caixa.dispatchEvent(new Event('change'))
    await flushPromises()
    naTela('[data-enviar-feedback]')!.click()
    await flushPromises()
    expect(naTela('[data-erro-feedback]')!.textContent).toContain('Use imagens PNG ou JPG de até 1 MB.')
    naTela('[data-enviar-feedback]')!.click()
    await flushPromises()
    expect(camposDo(fake.chamadas[1]!.corpo)).toEqual({ tipo: 'elogio', texto: 'Adorei o resumo da IA.', autoriza_depoimento: 'true', detalhes: 'false', pagina: '/inicio' })
    expect(naTela('[data-passo-feedback="enviado"]')).not.toBeNull()
  })
})

describe('Seus feedbacks e a conversa', () => {
  it('a lista mostra tipo, situação e resposta nova; vazia, convida a enviar', async () => {
    entrar()
    apiFalsa({
      'GET /feedback': () => ({
        itens: [{ id: 7, tipo: 'erro', situacao: 'planejado', impacto: null, autoriza_depoimento: false, trecho: 'O botão Salvar…', mensagens: 2, imagens: 1, pagina_titulo: 'Formulário', criado_em: '2026-10-06T21:00:00Z', atualizado_em: '2026-10-06T22:00:00Z', novidade: true }],
        novidades: 1,
      }),
    })
    const w = await montar(FeedbacksView, '/feedback')
    const item = w.get('[data-feedback="7"]')
    expect(item.get('[data-situacao]').text()).toBe('Planejado')
    expect(item.find('[data-novidade]').exists()).toBe(true)
    expect(item.get('[data-trecho]').text()).toBe('O botão Salvar…')
    expect(item.get('a').attributes('href')).toBe('/feedback/7')
    expect(usarFeedback().novidades.value).toBe(1)

    apiFalsa({ 'GET /feedback': () => ({ itens: [], novidades: 0 }) })
    const vazia = await montar(FeedbacksView, '/feedback')
    expect(vazia.find('[data-vazio-feedbacks]').exists()).toBe(true)
  })

  it('a conversa: você à direita, equipe com o selo, mudança de situação no meio; responder e autorizar o depoimento', async () => {
    entrar()
    let atual = feedbackFalso()
    const fake = apiFalsa({
      'GET /feedback/7': () => atual,
      'GET /feedback/novidades': () => ({ novidades: 0 }),
      'POST /feedback/7/mensagens': () => (atual = { ...atual, mensagens: [...atual.mensagens, mensagem(4, 'usuario', 'Obrigada!')] }),
      'PATCH /feedback/8': () => ({ ...atual, id: 8, tipo: 'elogio', autoriza_depoimento: false }),
      'GET /feedback/8': () => ({ ...atual, id: 8, tipo: 'elogio', autoriza_depoimento: true }),
    })
    const router = await roteador('/feedback/7')
    const w = await montar(FeedbackView, '/feedback/7', router)
    const autores = w.findAll('[data-autor-nome]').map((x) => x.text())
    expect(autores).toEqual(['Você', 'Marcelo'])
    expect(w.text()).toContain('Equipe Toqqi')
    expect(w.get('[data-mudanca]').text()).toMatch(/Marcelo mudou a situação para\s*Em análise/)
    expect(w.text()).toContain('Impede o trabalho')
    await w.get('textarea[data-texto-resposta]').setValue('Obrigada!')
    await w.get('[data-responder]').trigger('submit')
    await flushPromises()
    const post = fake.chamadas.find((c) => c.metodo === 'POST')!
    expect(camposDo(post.corpo)).toEqual({ texto: 'Obrigada!' })
    expect(w.findAll('[data-mensagem]')).toHaveLength(4)

    await router.push('/feedback/8')
    await flushPromises()
    expect(w.find('[data-depoimento]').exists()).toBe(true)
    await w.get('[data-depoimento] [role="switch"]').trigger('click')
    await flushPromises()
    expect(fake.chamadas.find((c) => c.metodo === 'PATCH')!.corpo).toEqual({ autoriza_depoimento: false })
  })
})

describe('Plataforma › Feedback', () => {
  function plataformaFalsa(): FeedbackPlataforma {
    return {
      ...feedbackFalso(), tipo: 'elogio', impacto: null, autoriza_depoimento: true, situacao: 'recebido',
      conta: { id: 3, nome: 'Alfa Ltda', plano: 'profissional', situacao: 'teste' },
      autor: { id: 5, nome: 'Ana Souza', email: 'ana@alfa.com.br', perfil: 'gestor', cargo: 'CS', situacao: 'ativo' },
      contexto: { pagina: '/inicio', pagina_titulo: 'Início', navegador: 'Chrome', tela: '1280x800', versao_site: 'abc',
        diagnostico: { pedidos: [{ quando: null, metodo: 'POST', caminho: '/contatos', status: 500, codigo: 'erro_interno', request_id: 'rid9' }] } },
      nota_interna: '',
      mensagens: [mensagem(1, 'usuario', 'O Toqqi mudou nosso atendimento.')],
    } as FeedbackPlataforma
  }

  it('a lista filtra, marca o que pede atenção e acerta o número da aba', async () => {
    entrar(true)
    const fake = apiFalsa({
      'GET /plataforma/feedback': () => ({
        itens: [{ id: 9, tipo: 'erro', situacao: 'recebido', impacto: 'bloqueia', autoriza_depoimento: false, trecho: 'Tela branca', mensagens: 1, imagens: 0, pagina_titulo: null, criado_em: '2026-10-06T21:00:00Z', atualizado_em: '2026-10-06T21:00:00Z', conta_id: 3, conta_nome: 'Alfa Ltda', autor_nome: 'Ana', autor_email: 'ana@alfa.com.br', atencao: true }],
        contagem: { atencao: 1, abertos: 1 },
      }),
    })
    const w = await montar(AbaFeedback, '/plataforma/feedback')
    expect(w.get('[data-feedback="9"]').text()).toContain('Precisa de atenção.')
    expect(w.find('[data-bloqueia]').exists()).toBe(true)
    expect(w.get('[data-total-feedback]').text()).toContain('1 feedback precisa de atenção')
    expect(usarFeedback().atencao.value).toBe(1)
    await w.get('select').setValue('erro')
    await flushPromises()
    expect(fake.chamadas.at(-1)!.url.searchParams.get('tipo')).toBe('erro')
    expect(fake.chamadas.at(-1)!.url.searchParams.get('situacao')).toBe('abertos')
  })

  it('o detalhe: depoimento para copiar, diagnóstico, responder com situação e só mudar a situação', async () => {
    entrar(true)
    let atual = plataformaFalsa()
    const fake = apiFalsa({
      'GET /plataforma/feedback/7': () => atual,
      'GET /plataforma/feedback/contagem': () => ({ atencao: 0, abertos: 1 }),
      'POST /plataforma/feedback/7/mensagens': (c) => {
        const { texto, situacao } = c.corpo as { texto: string; situacao: string | null }
        atual = { ...atual, situacao: (situacao ?? atual.situacao) as never, mensagens: [...atual.mensagens, mensagem(atual.mensagens.length + 1, 'equipe', texto, { situacao })] as never }
        return atual
      },
      'PATCH /plataforma/feedback/7': (c) => (atual = { ...atual, nota_interna: (c.corpo as { nota_interna: string }).nota_interna }),
    })
    const w = await montar(FeedbackPlataformaView, '/plataforma/feedback/7')
    expect(w.get('[data-depoimento-plataforma]').text()).toContain('“O Toqqi mudou nosso atendimento.” — Ana Souza, Alfa Ltda')
    expect(w.get('[data-diagnostico]').text()).toContain('POST /contatos')
    expect(w.get('[data-diagnostico]').text()).toContain('rid9')
    expect(w.get('[data-quem-mandou]').text()).toContain('ana@alfa.com.br')

    // só a situação: o botão diz "Mudar a situação" e vai sem texto
    await w.get('[data-situacao-equipe] select').setValue('concluido')
    expect(w.get('[data-enviar-equipe]').text()).toContain('Mudar a situação')
    await w.get('[data-responder-equipe]').trigger('submit')
    await flushPromises()
    expect(fake.chamadas.filter((c) => c.metodo === 'POST').at(-1)!.corpo).toEqual({ texto: '', situacao: 'concluido' })
    expect(w.get('[data-situacao]').text()).toBe('Concluído')

    // resposta com texto
    await w.get('textarea[data-texto-equipe]').setValue('Obrigado, Ana!')
    await w.get('[data-responder-equipe]').trigger('submit')
    await flushPromises()
    expect(fake.chamadas.filter((c) => c.metodo === 'POST').at(-1)!.corpo).toEqual({ texto: 'Obrigado, Ana!', situacao: null })

    // nota interna
    await w.get('[data-nota-interna] textarea').setValue('Usar na landing')
    await w.get('[data-salvar-nota]').trigger('click')
    await flushPromises()
    expect(fake.chamadas.find((c) => c.metodo === 'PATCH')!.corpo).toEqual({ nota_interna: 'Usar na landing' })
  })
})

describe('menu', () => {
  it('o botão Feedback abre a janela e mostra as respostas novas; Plataforma mostra o que pede atenção', async () => {
    entrar(true)
    apiFalsa({
      'GET /feedback/novidades': () => ({ novidades: 2 }),
      'GET /plataforma/feedback/contagem': () => ({ atencao: 3, abertos: 4 }),
      'GET /equipe/pendentes': () => ({ total: 0 }),
    })
    const w = await montar(BarraLateral, '/inicio')
    expect(w.get('[data-contador-feedback]').text()).toBe('2')
    expect(w.get('[data-botao-feedback]').text()).toContain('2 respostas novas')
    const plataforma = w.findAll('a').find((a) => a.attributes('href') === '/plataforma')!
    expect(plataforma.text()).toContain('3 feedbacks precisam de atenção')
    await w.get('[data-botao-feedback]').trigger('click')
    expect(usarFeedback().janela.aberta).toBe(true)
  })
})
