import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h, nextTick } from 'vue'
import type { Perfil, RespostaDetalhe, RespostaItem } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import RespostasView from '@/modulos/respostas/RespostasView.vue'
import ModalRegistrarResposta from '@/modulos/respostas/ModalRegistrarResposta.vue'
import { apiFalsa } from './apiFalsa'

const HOJE = hojeIso()

function resposta(id: number, extra: Partial<RespostaItem> = {}): RespostaItem {
  return {
    id,
    formulario: { id: 1, nome: 'Pesquisa pós-entrega' },
    contato: { id: 101, nome: 'Bruno Lima', email: 'bruno@x.com', perfil: null },
    empresa: { id: 14, nome: 'Mercado Bom Preço', grupo: null },
    canal: 'email',
    nota: 4,
    tipo_nota: 'nps',
    grupo: 'detrator',
    comentario: 'A entrega atrasou de novo.',
    respostas: {},
    contexto: {},
    referencia: null,
    criada_em: '2026-09-28T10:00:00-03:00',
    data: '2026-09-28T10:00:00-03:00',
    respondida_em: '2026-09-28T10:00:00-03:00',
    origem: 'pesquisa',
    temas: ['prazo_entrega'],
    temas_manuais: false,
    o_que_faltou: null,
    o_que_combinamos: null,
    analisada_em: null,
    analisada_por: null,
    registrada_por: null,
    arquivada: false,
    acao: { id: 9, situacao: 'a_fazer', prazo: null, prazo_selo: null },
    ...extra,
  }
}

let lista: RespostaItem[]
let router: Router

function detalhe(r: RespostaItem): RespostaDetalhe {
  return {
    ...r,
    perguntas: [{ id: 'nota', titulo: 'De 0 a 10, quanto você nos recomendaria?', tipo: 'nps', resposta: String(r.nota) }],
    convite: null,
    acoes: [
      { id: 9, situacao: 'a_fazer', prazo: null, prazo_selo: null, titulo: 'Ligar para o cliente' },
      { id: 10, situacao: 'concluida', prazo: null, prazo_selo: null, titulo: 'Rever o frete' },
    ],
  }
}

function api(extra: Record<string, Parameters<typeof apiFalsa>[0][string]> = {}) {
  return apiFalsa({
    'GET /respostas': () => ({
      itens: lista,
      total: lista.length,
      pagina: 1,
      por_pagina: 50,
      metricas: { nps: { valor: -100, faixa: 'critico', promotores: 0, neutros: 0, detratores: lista.length, total: lista.length }, csat: null, total: lista.length },
    }),
    'GET /respostas/temas': () => [{ chave: 'prazo_entrega', rotulo: 'Prazo de entrega' }],
    'GET /respostas/:id': ({ caminho }) => {
      const r = lista.find((x) => `/respostas/${x.id}` === caminho)
      return r ? detalhe(r) : new Response(JSON.stringify({ erro: { codigo: 'nao_encontrado', mensagem: 'x' } }), { status: 404 })
    },
    'DELETE /respostas/:id': ({ caminho }) => {
      lista = lista.filter((x) => `/respostas/${x.id}` !== caminho)
      return undefined
    },
    'GET /cadastros/grupos': () => [],
    'GET /cadastros/perfis': () => [],
    ...extra,
  })
}

function entrar(permissoes: string[], perfil: Perfil = 'gestor') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana', email: 'a@x.com', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

async function abrir(caminho = '/respostas'): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/respostas', name: 'respostas', component: RespostasView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const App = defineComponent({ render: () => h(RouterView) })
  const w = mount(App, { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return w
}

/** O <select> pelo texto do rótulo. */
function selecao(w: VueWrapper, rotulo: string) {
  const label = w.findAll('label').find((l) => l.text() === rotulo)
  if (!label) throw new Error(`Sem o campo "${rotulo}"`)
  return w.get(`[id="${label.attributes('for')}"]`)
}

const buscasNaApi = (chamadas: ReturnType<typeof api>['chamadas']) => chamadas.filter((c) => c.metodo === 'GET' && c.caminho === '/respostas')

beforeEach(() => {
  setActivePinia(createPinia())
  entrar(['respostas.ver', 'respostas.editar', 'contatos.ver', 'acoes.ver'])
  lista = [resposta(5), resposta(6, { contato: { id: 102, nome: 'Carla Souza', email: null, perfil: null }, nota: 9, grupo: 'promotor', acao: null, temas: [] })]
})

// Desmonta as telas de cada teste (timers e recargas não vazam para o seguinte).
enableAutoUnmount(afterEach)

afterEach(() => {
  vi.unstubAllGlobals()
  avisos.splice(0)
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
  document.body.innerHTML = ''
})

describe('respostas: filtros no endereço', () => {
  it('o que está no endereço vira a busca na API (período em datas de São Paulo)', async () => {
    const { chamadas } = api()
    const w = await abrir('/respostas?categoria=detrator&periodo=30&contato_id=101&busca=entrega')
    const busca = buscasNaApi(chamadas).at(-1)!.url.searchParams
    expect(Object.fromEntries(busca)).toEqual({
      arquivadas: 'false',
      pagina: '1',
      busca: 'entrega',
      categoria: 'detrator',
      contato_id: '101',
      de: somarDias(HOJE, -29),
      ate: HOJE,
    })
    // O filtro do contato aparece com o nome (vindo da própria lista) e dá para tirar.
    expect(w.text()).toContain('Respostas de Bruno Lima')
    expect((selecao(w, 'Categoria').element as HTMLSelectElement).value).toBe('detrator')
  })

  it('mudar um filtro escreve no endereço; tipo CSAT tira a categoria "detrator", que não existe nele', async () => {
    const { chamadas } = api()
    const w = await abrir('/respostas?categoria=detrator')
    await selecao(w, 'Tipo de pesquisa').setValue('csat')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tipo_nota: 'csat' })
    const ultima = Object.fromEntries(buscasNaApi(chamadas).at(-1)!.url.searchParams)
    expect(ultima).toMatchObject({ tipo_nota: 'csat' })
    expect(ultima).not.toHaveProperty('categoria')
  })

  it('datas escolhidas trocadas: avisa no campo e não busca', async () => {
    const { chamadas } = api()
    const w = await abrir('/respostas?de=2026-09-10&ate=2026-09-01')
    expect(buscasNaApi(chamadas)).toHaveLength(0)
    expect(w.text()).toContain('A data inicial precisa ser antes da final.')
  })

  it('"Só empresas ativas" vem do endereço (atalho do painel), vai para a API e dá para desligar', async () => {
    const { chamadas } = api()
    const w = await abrir('/respostas?so_ativos=true&tipo_nota=nps')
    expect(buscasNaApi(chamadas).at(-1)!.url.searchParams.get('so_ativos')).toBe('true')
    const chave = w.get('[role="switch"]')
    expect(chave.attributes('aria-checked')).toBe('true')
    await chave.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tipo_nota: 'nps' })
    expect(buscasNaApi(chamadas).at(-1)!.url.searchParams.has('so_ativos')).toBe(false)
  })

  it('salvar a análise com comentário novo busca a lista de novo (a busca ou o tema podem mudar)', async () => {
    const { chamadas } = api({
      'PATCH /respostas/:id': ({ corpo }) => {
        Object.assign(lista[0]!, corpo)
        return detalhe(lista[0]!)
      },
    })
    const w = await abrir('/respostas?analisar=5&busca=entrega')
    const antes = buscasNaApi(chamadas).length
    const painel = w.get('[role="dialog"]')
    const comentario = painel.findAll('textarea').find((t) => t.element.closest('div')?.textContent?.includes('Comentário do cliente'))!
    await comentario.setValue('Chegou certinho desta vez.')
    await painel.get('#form-analise').trigger('submit')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'PATCH')!.corpo).toMatchObject({ comentario: 'Chegou certinho desta vez.' })
    expect(buscasNaApi(chamadas).length).toBe(antes + 1)
  })

  it('voltar no navegador (endereço muda por fora) atualiza a tela e busca de novo', async () => {
    const { chamadas } = api()
    const w = await abrir('/respostas')
    const antes = buscasNaApi(chamadas).length
    await router.replace({ path: '/respostas', query: { arquivadas: 'true' } })
    await flushPromises()
    expect((selecao(w, 'Arquivadas').element as HTMLSelectElement).value).toBe('true')
    expect(buscasNaApi(chamadas)).toHaveLength(antes + 1)
    expect(buscasNaApi(chamadas).at(-1)!.url.searchParams.get('arquivadas')).toBe('true')
  })
})

describe('respostas: analisar, arquivar e excluir', () => {
  it('?analisar=ID abre o painel com a resposta; "Analisar" escreve o ID no endereço', async () => {
    const { chamadas } = api()
    const w = await abrir('/respostas?analisar=5')
    expect(chamadas.some((c) => c.caminho === '/respostas/5')).toBe(true)
    const painel = w.get('[role="dialog"]')
    expect(painel.text()).toContain('Bruno Lima')
    expect(painel.text()).toContain('De 0 a 10, quanto você nos recomendaria?')
    expect(painel.text()).toContain('Ligar para o cliente')

    const w2 = await abrir('/respostas')
    const botao = w2.findAll('button').find((b) => b.text() === 'Analisar')!
    await botao.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ analisar: '5' })
  })

  it('excluir (só admin): a confirmação diz quantas ações somem junto; cancelar não apaga', async () => {
    entrar(['respostas.ver', 'respostas.editar', 'contatos.ver', 'acoes.ver'], 'admin')
    const { chamadas } = api()
    const w = await abrir()
    const menu = () => w.findAll('button[aria-haspopup="menu"]').find((b) => b.attributes('aria-label')?.includes('Bruno Lima'))!
    const excluirDeVez = async () => {
      await menu().trigger('click')
      await w.findAll('[role="menuitem"]').find((i) => i.text() === 'Excluir de vez')!.trigger('click')
      await flushPromises()
    }

    await excluirDeVez()
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Excluir a resposta de Bruno Lima?')
    expect(estadoConfirmacao.mensagem).toContain('as 2 ações ligadas a ela serão apagadas de vez')
    expect(estadoConfirmacao.mensagem).toContain('Não dá para desfazer')
    responderConfirmacao(false)
    await flushPromises()
    expect(chamadas.some((c) => c.metodo === 'DELETE')).toBe(false)

    await excluirDeVez()
    responderConfirmacao(true)
    await flushPromises()
    expect(chamadas.filter((c) => c.metodo === 'DELETE').map((c) => c.caminho)).toEqual(['/respostas/5'])
    expect(w.text()).not.toContain('Bruno Lima')
    expect(avisos.some((a) => a.mensagem === 'Resposta excluída.')).toBe(true)
  })

  it('salvar a nota nova também atualiza "O que o cliente respondeu" (o PATCH devolve o detalhe)', async () => {
    api({ 'PATCH /respostas/:id': ({ corpo }) => detalhe(resposta(5, { nota: (corpo as { nota: number }).nota, grupo: 'neutro' })) })
    const w = await abrir('/respostas?analisar=5')
    const painel = w.get('[role="dialog"]')
    expect(painel.get('dl dd').text()).toBe('4')
    await painel.get('input[type="radio"][value="8"]').setValue(true)
    await painel.get('#form-analise').trigger('submit')
    await flushPromises()
    expect(w.get('[role="dialog"] dl dd').text()).toBe('8')
  })

  it('registrada à mão: perguntas sem resposta não aparecem (o comentário tem campo próprio) e a data vem sem hora', async () => {
    lista[0] = resposta(5, { origem: 'manual', respondida_em: '2026-09-20T12:00:00-03:00', data: '2026-09-20T12:00:00-03:00' })
    api({
      'GET /respostas/:id': () => ({
        ...detalhe(lista[0]!),
        perguntas: [
          { id: 'nota', titulo: 'De 0 a 10, quanto você nos recomendaria?', tipo: 'nps', resposta: '4' },
          { id: 'motivo', titulo: 'O que mais pesou na sua nota?', tipo: 'comentario', resposta: null },
        ],
      }),
    })
    const w = await abrir('/respostas?analisar=5')
    const painel = w.get('[role="dialog"]')
    expect(painel.text()).toContain('De 0 a 10, quanto você nos recomendaria?')
    expect(painel.text()).not.toContain('O que mais pesou na sua nota?')
    expect(painel.text()).toContain('20/09/2026 · E-mail')
    expect(painel.text()).not.toContain('20/09/2026 às')
  })

  it('com a análise mudada e não salva, sair por um link do painel ("Abrir ação") pergunta antes', async () => {
    api()
    const w = await abrir('/respostas?analisar=5')
    const painel = w.get('[role="dialog"]')
    const comentario = painel.findAll('textarea').find((t) => t.element.closest('div')?.textContent?.includes('Comentário do cliente'))!
    await comentario.setValue('Mudei e não salvei.')
    const abrirAcao = () => w.get('[role="dialog"]').findAll('a').find((a) => a.text().includes('Abrir ação'))!.trigger('click')

    await abrirAcao()
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Sair sem salvar a análise?')
    responderConfirmacao(false)
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/respostas')

    await abrirAcao()
    await flushPromises()
    responderConfirmacao(true)
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/planos-de-acao/9')
  })

  it('sem perfil admin não aparece "Excluir de vez"; arquivar continua', async () => {
    api()
    const w = await abrir()
    await w.findAll('button[aria-haspopup="menu"]').find((b) => b.attributes('aria-label')?.includes('Bruno Lima'))!.trigger('click')
    const itens = w.findAll('[role="menuitem"]').map((i) => i.text())
    expect(itens).toContain('Arquivar')
    expect(itens).not.toContain('Excluir de vez')
  })

  it('só quem pode exportar vê "Exportar CSV"', async () => {
    api()
    let w = await abrir()
    expect(w.text()).not.toContain('Exportar CSV')
    w.unmount()
    entrar(['respostas.ver', 'painel.exportar'])
    w = await abrir()
    expect(w.text()).toContain('Exportar CSV')
    expect(w.text()).not.toContain('Registrar resposta')
  })
})

describe('sem acesso aos contatos (contatos.ver)', () => {
  it('não chama listas que pedem esse acesso; empresa e contato ficam só para ler, com aviso', async () => {
    entrar(['respostas.ver', 'respostas.editar'])
    const { chamadas } = api()
    const w = await abrir('/respostas?empresa_id=14')
    // O nome da empresa vem da própria lista de respostas; o campo não busca nada.
    const empresa = w.findAll('[role="group"]').find((g) => g.text().includes('Mercado Bom Preço'))
    expect(empresa?.exists()).toBe(true)
    expect(w.text()).toContain('Seu perfil não tem acesso à lista de empresas.')
    expect(w.find('input[role="combobox"]').exists()).toBe(false)
    // Sem grupo/perfil no endereço, esses filtros nem aparecem.
    expect(w.findAll('label').some((l) => l.text() === 'Grupo de empresas')).toBe(false)

    // Registrar: sem contato escolhido, explica e não deixa enviar.
    await w.findAll('button').find((b) => b.text().includes('Registrar resposta'))!.trigger('click')
    await flushPromises()
    const modal = w.findAll('[role="dialog"]').at(-1)!
    expect(modal.text()).toContain('Não dá para escolher o contato')
    expect(modal.get('button[type="submit"]').attributes('disabled')).toBeDefined()

    const proibidas = chamadas.filter((c) => /^\/(empresas|contatos|cadastros|responsaveis)/.test(c.caminho))
    expect(proibidas).toEqual([])
  })

  it('com o contato já escolhido (filtro do contato), registra normalmente', async () => {
    entrar(['respostas.ver', 'respostas.editar'])
    const { chamadas } = api({ 'POST /respostas': () => resposta(8) })
    const w = await abrir('/respostas?contato_id=101')
    await w.findAll('button').find((b) => b.text().includes('Registrar resposta'))!.trigger('click')
    await flushPromises()
    const modal = w.findAll('[role="dialog"]').at(-1)!
    expect(modal.text()).toContain('Bruno Lima')
    expect(modal.text()).not.toContain('Não dá para escolher o contato')
    await modal.get('input[type="radio"][value="6"]').setValue(true)
    await modal.get('form').trigger('submit')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'POST')!.corpo).toMatchObject({ contato_id: 101, nota: 6 })
  })
})

describe('registrar resposta à mão', () => {
  async function abrirModal(contatoInicial: { id: number; nome: string } | null) {
    const w = mount(ModalRegistrarResposta, { props: { aberto: false, contatoInicial }, global: { stubs: { teleport: true } }, attachTo: document.body })
    await w.setProps({ aberto: true })
    await flushPromises()
    return w
  }

  it('sem nota não envia e diz o que falta', async () => {
    const { chamadas } = api({ 'POST /respostas': () => resposta(7) })
    const w = await abrirModal({ id: 101, nome: 'Bruno Lima' })
    await w.get('#form-registrar-resposta').trigger('submit')
    await flushPromises()
    expect(chamadas.some((c) => c.metodo === 'POST')).toBe(false)
    expect(w.text()).toContain('Escolha a nota, de 0 a 10.')
  })

  it('manda contato, nota, canal e comentário (a data de hoje não vai: fica a hora do registro); avisa da ação', async () => {
    const { chamadas } = api({ 'POST /respostas': ({ corpo }) => resposta(7, { nota: (corpo as { nota: number }).nota }) })
    const w = await abrirModal({ id: 101, nome: 'Bruno Lima' })
    expect((w.get('input[type="date"]').element as HTMLInputElement).value).toBe(HOJE)
    await w.get('input[type="radio"][value="4"]').setValue(true)
    await w.get('textarea').setValue('  Ligou reclamando do frete.  ')
    await w.get('#form-registrar-resposta').trigger('submit')
    await flushPromises()
    const post = chamadas.find((c) => c.metodo === 'POST')!
    expect(post).toMatchObject({ caminho: '/respostas', corpo: { contato_id: 101, nota: 4, canal: 'manual', comentario: 'Ligou reclamando do frete.' } })
    expect(post.corpo).not.toHaveProperty('data')
    expect(w.emitted('registrada')).toHaveLength(1)
    expect(w.emitted('update:aberto')?.at(-1)).toEqual([false])
    expect(avisos.at(-1)?.mensagem).toContain('uma ação foi criada em Planos de ação')
  })

  it('Esc na busca de contato fecha só a lista; o segundo Esc fecha a janela', async () => {
    api({ 'GET /contatos': () => ({ itens: [{ id: 101, nome: 'Bruno Lima', email: 'bruno@x.com', empresa: null }], total: 1, pagina: 1, por_pagina: 8 }) })
    const w = await abrirModal(null)
    const busca = w.get('input[role="combobox"]')
    await busca.setValue('bru')
    expect(busca.attributes('aria-expanded')).toBe('true')
    const esc = () => busca.element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    esc()
    await nextTick()
    expect(busca.attributes('aria-expanded')).toBe('false')
    expect(w.emitted('update:aberto')).toBeUndefined()
    expect((busca.element as HTMLInputElement).value).toBe('bru')
    esc()
    await nextTick()
    expect(w.emitted('update:aberto')?.at(-1)).toEqual([false])
    w.unmount()
  })

  it('com outra data (nota que chegou antes), a data vai junto', async () => {
    const { chamadas } = api({ 'POST /respostas': () => resposta(7) })
    const w = await abrirModal({ id: 101, nome: 'Bruno Lima' })
    await w.get('input[type="radio"][value="9"]').setValue(true)
    await w.get('input[type="date"]').setValue(somarDias(HOJE, -3))
    await w.get('#form-registrar-resposta').trigger('submit')
    await flushPromises()
    expect(chamadas.find((c) => c.metodo === 'POST')!.corpo).toMatchObject({ nota: 9, data: somarDias(HOJE, -3) })
  })
})
