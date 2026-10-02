// Etapa 5c com a API simulada: Crescimento (abas, resumo, filtros, painel da indicação, mudanças de situação, registro à
// mão, CSV, vazio, foco e página quando uma linha sai) e Oportunidades (listas, oferta pelo WhatsApp com o link certo e o
// registro, trava contra clique duplo, resultado), mais as permissões de cada perfil e as rotas. No fim, o que a revisão
// da 5c tocou fora do módulo: o valor em reais de Contatos › Empresas e o formato dos webhooks de indicação.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { ConfigCrescimento, DadosNovaOferta, DadosResultadoOferta, Indicacao, Oferta, Oportunidade, Perfil } from '@/api/tipos'
import { avisos } from '@/composables/avisos'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import { router as rotasDoApp } from '@/router'
import { useSessaoStore } from '@/stores/sessao'
import CrescimentoView from '@/modulos/crescimento/CrescimentoView.vue'
import ModalEmpresa from '@/modulos/contatos/ModalEmpresa.vue'
import SecaoWebhooks from '@/modulos/integracoes/SecaoWebhooks.vue'
import { apiFalsa, erro422, type Chamada } from './apiFalsa'

const ref = (id: number, nome: string) => ({ id, nome })

function indicacoes(): Indicacao[] {
  return [
    {
      id: 41,
      origem: 'pesquisa',
      nome: 'Juliana Prado',
      empresa: 'Empório Bela Vista',
      telefone: '5511987654321',
      email: 'juliana@emporiobelavista.com.br',
      observacao: 'É a compradora da loja do centro. <b>Prefere</b> contato à tarde.',
      indicador: { contato: ref(101, 'Ana Souza'), empresa: ref(11, 'Mercado Bom Preço') },
      pode_identificar: true,
      responsavel: ref(1, 'Carla Ribeiro'),
      situacao: 'nova',
      valor_mensal: null,
      motivo: null,
      criada_em: '2026-10-02T09:00:00-03:00',
      atualizada_em: '2026-10-02T09:00:00-03:00',
    },
    {
      id: 40,
      origem: 'pesquisa',
      nome: 'Roberto Lima',
      empresa: 'Padaria Pão Quente',
      telefone: '1133224455',
      email: null,
      observacao: null,
      indicador: { contato: ref(102, 'Marcos Teixeira'), empresa: ref(12, 'Atacadão do Vale') },
      pode_identificar: false,
      responsavel: ref(2, 'Diego Martins'),
      situacao: 'em_contato',
      valor_mensal: null,
      motivo: null,
      criada_em: '2026-09-29T10:00:00-03:00',
      atualizada_em: '2026-10-01T10:00:00-03:00',
    },
    {
      id: 39,
      origem: 'manual',
      nome: 'Fernanda Alves',
      empresa: 'Supermercado Ideal',
      telefone: null,
      email: 'compras@ideal.com.br',
      observacao: null,
      indicador: { contato: null, empresa: null },
      pode_identificar: true,
      responsavel: null,
      situacao: 'cliente',
      valor_mensal: '4800.00',
      motivo: null,
      criada_em: '2026-09-12T10:00:00-03:00',
      atualizada_em: '2026-09-26T10:00:00-03:00',
    },
  ]
}
const RESUMO_LISTA = { novas: 1, em_contato: 1, clientes: 1, nao_avancou: 0, receita_mensal: '4800.00' }
const RESUMO = { indicacoes: { recebidas: 12, clientes: 3, taxa: 25, receita_mensal: '7150.00' }, ofertas: { feitas: 8, aceitas: 2, taxa: 0.25, receita: '5600.00' } }
const CONFIG: ConfigCrescimento = {
  indicacoes_ativas: true,
  titulo_convite: 'Que bom que você gostou!',
  texto_convite: 'Conhece outra empresa que ganharia com a {empresa}?',
  recompensa: null,
  texto_oferta: 'Olá, {nome}! Aqui é {representante}, da {empresa}. Obrigado pela ótima avaliação! Preparei uma condição especial para a {empresa_cliente}. Posso te contar?',
}
function oportunidades(): Oportunidade[] {
  return [
    {
      empresa: { id: 21, nome: 'Atacadão do Vale', valor_mensal: '3200.00' },
      grupo: ref(2, 'Varejo'),
      responsavel: ref(1, 'Carla Ribeiro'),
      nps: { valor: 100, total: 4 },
      contato: { id: 201, nome: 'Marcos Teixeira', telefone: '5511976543210', email: 'marcos@vale.com.br' },
      ultima_resposta: { data: '2026-09-27T10:00:00-03:00', nota: 10, tipo_nota: 'nps' },
      ultima_oferta: null,
    },
    {
      empresa: { id: 22, nome: 'Hortifruti Sabor', valor_mensal: '1850.00' },
      grupo: null,
      responsavel: null,
      nps: { valor: 75, total: 4 },
      contato: { id: 202, nome: 'Beatriz Costa', telefone: null, email: 'beatriz@sabor.com.br' },
      ultima_resposta: { data: '2026-09-20T10:00:00-03:00', nota: 9, tipo_nota: 'nps' },
      ultima_oferta: { id: 501, criada_em: '2026-09-24T10:00:00-03:00', resultado: null, valor: null },
    },
    {
      empresa: { id: 24, nome: 'Mercadinho Boa Vizinhança', valor_mensal: null },
      grupo: null,
      responsavel: null,
      nps: { valor: 33, total: 3 },
      contato: null,
      ultima_resposta: null,
      ultima_oferta: null,
    },
  ]
}

type Rotas = Parameters<typeof apiFalsa>[0]
/**
 * A API simulada guarda as indicações: o PATCH, o DELETE e o POST valem para as buscas seguintes. As ofertas também,
 * como a API: o POST devolve a oferta inteira; o PATCH sem `valor` mantém o que estava e os resultados que não são
 * "aceitou" o limpam.
 */
function api(extra: Rotas = {}, opcoes: { vazio?: boolean; config?: Partial<ConfigCrescimento> } = {}) {
  let banco: Indicacao[] = opcoes.vazio ? [] : indicacoes()
  const idDe = (caminho: string) => Number(caminho.split('/').pop())
  const ofertas = new Map<number, Oferta>()
  const empresaDe = (id: number) => ref(id, oportunidades().find((o) => o.empresa.id === id)?.empresa.nome ?? '')
  return apiFalsa({
    'GET /crescimento/resumo': () => RESUMO,
    'GET /crescimento/configuracao': () => ({ ...CONFIG, ...opcoes.config }),
    'GET /crescimento/indicacoes': ({ url }) => {
      const s = url.searchParams.get('situacao')
      const itens = banco.filter((i) => !s || i.situacao === s)
      return { itens, total: itens.length, pagina: Number(url.searchParams.get('pagina') ?? 1), por_pagina: 50, resumo: opcoes.vazio ? { novas: 0, em_contato: 0, clientes: 0, nao_avancou: 0, receita_mensal: '0.00' } : RESUMO_LISTA }
    },
    'PATCH /crescimento/indicacoes/:id': ({ caminho, corpo }) => {
      banco = banco.map((i) => (i.id === idDe(caminho) ? ({ ...i, ...(corpo as object) } as Indicacao) : i))
      return banco.find((i) => i.id === idDe(caminho))
    },
    'DELETE /crescimento/indicacoes/:id': ({ caminho }) => {
      banco = banco.filter((i) => i.id !== idDe(caminho))
      return undefined
    },
    'POST /crescimento/indicacoes': ({ corpo }) => {
      const nova = { ...indicacoes()[0]!, id: 50, origem: 'manual', ...(corpo as object) } as Indicacao
      banco = [nova, ...banco]
      return new Response(JSON.stringify(nova), { status: 201 })
    },
    'GET /crescimento/oportunidades': ({ url }) => {
      const itens = url.searchParams.get('lista') === 'promotores' ? oportunidades().slice(0, 1) : oportunidades()
      return { itens, total: itens.length, pagina: 1, por_pagina: 50 }
    },
    'POST /crescimento/ofertas': ({ corpo }) => {
      const c = corpo as DadosNovaOferta
      const o: Oferta = {
        id: 900 + ofertas.size,
        empresa: empresaDe(Number(c.empresa_id)),
        contato: c.contato_id === null ? null : ref(Number(c.contato_id), 'Contato'),
        lista: c.lista,
        canal: c.canal ?? 'whatsapp',
        texto: c.texto,
        usuario: ref(1, 'Ana Paula Ribeiro'),
        criada_em: '2026-10-02T11:00:00-03:00',
        resultado: null,
        valor: null,
        resultado_em: null,
      }
      ofertas.set(Number(o.id), o)
      return new Response(JSON.stringify(o), { status: 201 })
    },
    'PATCH /crescimento/ofertas/:id': ({ caminho, corpo }) => {
      const id = idDe(caminho)
      const c = corpo as DadosResultadoOferta
      const antes: Oferta = ofertas.get(id) ?? {
        id,
        empresa: empresaDe(22),
        contato: ref(202, 'Beatriz Costa'),
        lista: 'pode_crescer',
        canal: 'email',
        texto: 'Oi',
        usuario: null,
        criada_em: '2026-09-24T10:00:00-03:00',
        resultado: null,
        valor: null,
        resultado_em: null,
      }
      const valor = c.resultado !== 'aceitou' ? null : c.valor !== undefined ? c.valor.toFixed(2) : antes.valor
      const depois: Oferta = { ...antes, resultado: c.resultado, valor, resultado_em: '2026-10-02T12:00:00-03:00' }
      ofertas.set(id, depois)
      return depois
    },
    'GET /responsaveis': () => [
      { id: 1, nome: 'Carla Ribeiro', funcao: null, email: null, foto_url: null, teams_webhook: null, empresas: 3 },
      { id: 2, nome: 'Diego Martins', funcao: null, email: null, foto_url: null, teams_webhook: null, empresas: 2 },
    ],
    'GET /cadastros/grupos': () => [{ id: 2, nome: 'Varejo', em_uso: 1 }],
    ...extra,
  })
}

const TODAS = ['crescimento.ver', 'crescimento.tratar', 'painel.exportar', 'contatos.ver', 'configuracoes.gerenciar']

function entrar(permissoes: string[] = TODAS, perfil: Perfil = 'admin') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana Paula Ribeiro', email: 'ana@sol.com.br', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Distribuidora Sol', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

let router: Router
async function abrir(caminho: string): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/crescimento/:aba', name: 'crescimento', component: CrescimentoView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div', 'outra página') } },
    ],
  })
  await router.push(caminho)
  await router.isReady()
  const App = defineComponent({ render: () => h(RouterView) })
  const w = mount(App, { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return w
}

/** A espera das recargas (200 ms) e da busca (300 ms). */
async function esperar(ms = 260) {
  await vi.advanceTimersByTimeAsync(ms)
  await flushPromises()
}

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()
const pedidos = (chamadas: Chamada[], metodo: string, caminho: string) => chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho)
const consulta = (c: Chamada | undefined) => Object.fromEntries(c?.url.searchParams ?? [])
const botao = (w: VueWrapper, texto: string | RegExp) => {
  const b = w.findAll('button').find((x) => (typeof texto === 'string' ? t(x.text()) === texto : texto.test(t(x.text()))))
  if (!b) throw new Error(`Sem o botão "${texto}"`)
  return b
}
function campo(w: VueWrapper, rotulo: string, dentro = '') {
  const label = w.findAll(`${dentro} label`).find((l) => t(l.text()) === rotulo || t(l.text()).startsWith(`${rotulo} `))
  if (!label) throw new Error(`Sem o campo "${rotulo}"`)
  return w.get(`[id="${label.attributes('for')}"]`)
}
const painel = (w: VueWrapper) => w.get('[role="dialog"]')

// Os links (WhatsApp, e-mail) não navegam no jsdom.
const semNavegar = (e: Event) => {
  if ((e.target as HTMLElement | null)?.closest?.('a')) e.preventDefault()
}

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  localStorage.clear()
  avisos.splice(0)
  vi.useFakeTimers({ shouldAdvanceTime: true })
  document.addEventListener('click', semNavegar, true)
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  document.removeEventListener('click', semNavegar, true)
  document.body.innerHTML = ''
  if (estadoConfirmacao.aberto) responderConfirmacao(false)
})

describe('Crescimento › Indicações', () => {
  it('abre com o resumo dos últimos 90 dias e a lista (quem indicou, responsável, situação e data)', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/indicacoes')
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/resumo')[0])).toEqual({})
    expect(pedidos(chamadas, 'GET', '/crescimento/configuracao')).toHaveLength(1)
    expect(document.title).toBe('Indicações · Crescimento · Toqqi')

    const numeros = (sel: string) => w.get(sel).findAll('dt').map((dt) => `${t(dt.text())}: ${t(dt.element.nextElementSibling?.textContent ?? '')}`)
    expect(numeros('[data-resumo-indicacoes]')).toEqual(['Recebidas: 12', 'Viraram cliente: 325% das recebidas', 'Receita mensal: R$7,2milR$ 7.150,00'])
    // A taxa sai das contagens (a escala de `taxa` da API não importa)
    expect(numeros('[data-resumo-ofertas]')).toEqual(['Feitas: 8', 'Aceitas: 225% das feitas'])
    expect(t(w.get('[data-resumo-ofertas]').text())).toContain('R$ 5.600,00 em vendas')

    const linha = (id: number) => t(w.get(`[data-abrir="${id}"]`).element.closest('tr')!.textContent ?? '')
    expect(linha(41)).toContain('Juliana Prado')
    expect(linha(41)).toContain('Empório Bela Vista')
    expect(linha(41)).toContain('(11) 98765-4321')
    expect(linha(41)).toContain('Mercado Bom Preço · Ana Souza')
    expect(linha(41)).toContain('Carla Ribeiro')
    expect(linha(41)).toContain('Nova')
    expect(linha(41)).toContain('02/10/2026')
    expect(linha(40)).toContain('Não quis se identificar')
    expect(linha(39)).toContain('Não informado')
    expect(linha(39)).toContain('Sem responsável')
    expect(linha(39)).toContain('Virou cliente')
    expect(linha(39)).toContain('R$ 4.800,00/mês')
    // A situação com a contagem do resumo
    expect(t(w.get('[data-situacao="todas"]').text())).toBe('Todas 3')
    expect(t(w.get('[data-situacao="cliente"]').text())).toBe('Viraram cliente 1')
    expect(t(w.get('[data-receita-indicacoes]').text())).toContain('R$ 4.800,00')
    // Celular: os mesmos dados em cartões
    expect(w.find('[data-abrir-cartao="40"]').exists()).toBe(true)
  })

  it('aba que não existe abre Indicações; trocar de aba guarda os filtros de cada uma', async () => {
    entrar()
    api()
    await abrir('/crescimento/qualquer')
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/indicacoes')
    const w2 = await abrir('/crescimento/indicacoes?situacao=cliente')
    await w2.findAll('[role="tab"]')[1]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/oportunidades')
    expect(document.title).toBe('Oportunidades · Crescimento · Toqqi')
    await w2.findAll('[role="tab"]')[0]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/indicacoes?situacao=cliente')
  })

  it('filtros: situação, busca, responsável e período vão para a API e para o endereço; mudar filtro volta para a página 1', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/indicacoes?pagina=2')
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/indicacoes').at(-1))).toEqual({ pagina: '2' })

    await w.get('[data-situacao="em_contato"]').trigger('click')
    await esperar()
    expect(w.get('[data-situacao="em_contato"]').attributes('aria-pressed')).toBe('true')
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/indicacoes').at(-1))).toEqual({ situacao: 'em_contato' })
    expect(router.currentRoute.value.query).toEqual({ situacao: 'em_contato' })

    await w.get('input[type="search"]').setValue('  Bela ')
    await esperar(600)
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/indicacoes').at(-1))).toEqual({ situacao: 'em_contato', busca: 'Bela' })

    await botao(w, 'Filtros').trigger('click')
    expect(campo(w, 'Responsável').findAll('option').map((o) => o.text())).toEqual(['Todos', 'Sem responsável', 'Carla Ribeiro', 'Diego Martins'])
    const antes = pedidos(chamadas, 'GET', '/crescimento/indicacoes').length
    await campo(w, 'Responsável').setValue('2')
    await esperar()
    // O id da lista (número) e o do endereço (texto) são a mesma busca: um pedido só
    expect(pedidos(chamadas, 'GET', '/crescimento/indicacoes')).toHaveLength(antes + 1)
    await campo(w, 'Recebidas').setValue('30')
    await esperar()
    expect(pedidos(chamadas, 'GET', '/crescimento/indicacoes')).toHaveLength(antes + 2)
    const ultima = consulta(pedidos(chamadas, 'GET', '/crescimento/indicacoes').at(-1))
    expect(ultima).toMatchObject({ situacao: 'em_contato', busca: 'Bela', responsavel_id: '2' })
    expect(ultima.de).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(router.currentRoute.value.query).toEqual({ situacao: 'em_contato', busca: 'Bela', responsavel_id: '2', periodo: '30' })
    expect(t(botao(w, /^Filtros/).text())).toBe('Filtros 2')
  })

  it('painel: os dados como texto, WhatsApp e e-mail para falar com a pessoa e quem indicou', async () => {
    entrar()
    api()
    const w = await abrir('/crescimento/indicacoes')
    await w.get('[data-abrir="41"]').trigger('click')
    await flushPromises()
    const p = painel(w)
    expect(t(p.text())).toContain('Juliana Prado')
    // Observação aparece como texto (nada de HTML vindo da indicação)
    expect(p.text()).toContain('<b>Prefere</b>')
    expect(p.find('b').exists()).toBe(false)
    expect(p.get('[data-whatsapp-indicacao]').attributes('href')).toBe('https://wa.me/5511987654321')
    expect(p.get('[data-whatsapp-indicacao]').attributes('target')).toBe('_blank')
    expect(p.get('[data-email-indicacao]').attributes('href')).toBe('mailto:juliana@emporiobelavista.com.br')
    expect(t(p.text())).toContain('Mercado Bom Preço · Ana Souza')
    expect(p.find('[data-nao-identificar]').exists()).toBe(false)

    // Quem não quis se identificar: o aviso para não contar à pessoa indicada
    await w.get('[data-abrir="40"]').trigger('click')
    await flushPromises()
    expect(painel(w).find('[data-nao-identificar]').exists()).toBe(true)
    expect(painel(w).find('[data-email-indicacao]').exists()).toBe(false)
  })

  it('virar cliente pede o valor mensal e manda o PATCH com o valor; o painel fecha e a lista e o resumo atualizam', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/indicacoes')
    await w.get('[data-abrir="41"]').trigger('click')
    await flushPromises()
    expect(botao(w, 'Salvar').attributes('disabled')).toBeDefined()

    await campo(w, 'Situação', '[role="dialog"]').setValue('cliente')
    await flushPromises()
    await w.get('#painel-indicacao-form').trigger('submit')
    await flushPromises()
    expect(t(painel(w).text())).toContain('Informe o valor mensal do novo cliente (pode ser 0).')
    expect(pedidos(chamadas, 'PATCH', '/crescimento/indicacoes/41')).toHaveLength(0)

    await campo(w, 'Valor mensal do novo cliente', '[role="dialog"]').setValue('1.250,50')
    await w.get('#painel-indicacao-form').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'PATCH', '/crescimento/indicacoes/41')[0]!.corpo).toEqual({ situacao: 'cliente', valor_mensal: 1250.5 })
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    expect(avisos.map((a) => a.mensagem)).toContain('Indicação marcada como “Virou cliente”.')
    expect(t(w.get('[data-abrir="41"]').element.closest('tr')!.textContent ?? '')).toContain('Virou cliente')
    await esperar()
    expect(pedidos(chamadas, 'GET', '/crescimento/resumo')).toHaveLength(2)
  })

  it('não avançou manda o motivo; trocar só o responsável manda só ele; o erro 422 aparece no campo', async () => {
    entrar()
    let falhar = true
    const { chamadas } = api({
      'PATCH /crescimento/indicacoes/:id': ({ caminho, corpo }) => {
        if (falhar && (corpo as Record<string, unknown>).situacao === 'nao_avancou') return erro422('Confira os campos.', { motivo: 'Motivo muito longo.' })
        return { ...indicacoes().find((i) => String(i.id) === caminho.split('/').pop()), ...(corpo as object) }
      },
    })
    const w = await abrir('/crescimento/indicacoes')
    await w.get('[data-abrir="40"]').trigger('click')
    await flushPromises()
    await campo(w, 'Situação', '[role="dialog"]').setValue('nao_avancou')
    await flushPromises()
    await campo(w, 'Motivo', '[role="dialog"]').setValue('  Já tem fornecedor até dezembro. ')
    await w.get('#painel-indicacao-form').trigger('submit')
    await flushPromises()
    expect(t(painel(w).text())).toContain('Motivo muito longo.')
    falhar = false
    await w.get('#painel-indicacao-form').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'PATCH', '/crescimento/indicacoes/40').at(-1)!.corpo).toEqual({ situacao: 'nao_avancou', motivo: 'Já tem fornecedor até dezembro.' })

    await w.get('[data-abrir="41"]').trigger('click')
    await flushPromises()
    await campo(w, 'Responsável', '[role="dialog"]').setValue('2')
    await w.get('#painel-indicacao-form').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'PATCH', '/crescimento/indicacoes/41')[0]!.corpo).toEqual({ responsavel_id: 2 })
    // A situação não mudou: o painel continua aberto, já com o novo responsável
    expect(w.find('[role="dialog"]').exists()).toBe(true)
  })

  it('"Excluir (pedido da pessoa)" pede confirmação, apaga e tira da lista', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/indicacoes')
    await w.get('[data-abrir="39"]').trigger('click')
    await flushPromises()
    await botao(w, 'Excluir (pedido da pessoa)').trigger('click')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Excluir esta indicação?')
    responderConfirmacao(true)
    await flushPromises()
    expect(pedidos(chamadas, 'DELETE', '/crescimento/indicacoes/39')).toHaveLength(1)
    expect(w.find('[data-abrir="39"]').exists()).toBe(false)
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    // Era a última linha: o foco vai para a anterior (não cai no body)
    expect(document.activeElement).toBe(w.get('[data-abrir="40"]').element)
    await esperar()
    expect(document.activeElement).toBe(w.get('[data-abrir="40"]').element)
  })

  it('excluir leva o foco para a linha seguinte; sem nenhuma linha, para o título da lista', async () => {
    entrar()
    api()
    const w = await abrir('/crescimento/indicacoes')
    const excluir = async (id: number) => {
      ;(w.get(`[data-abrir="${id}"]`).element as HTMLElement).focus()
      await w.get(`[data-abrir="${id}"]`).trigger('click')
      await flushPromises()
      await botao(w, 'Excluir (pedido da pessoa)').trigger('click')
      await flushPromises()
      responderConfirmacao(true)
      await flushPromises()
      await esperar()
    }
    await excluir(40)
    expect(document.activeElement).toBe(w.get('[data-abrir="39"]').element)
    await excluir(41)
    expect(document.activeElement).toBe(w.get('[data-abrir="39"]').element)
    await excluir(39)
    expect(t(w.text())).toContain('Nenhuma indicação ainda')
    expect(document.activeElement).toBe(w.get('#t-lista-indicacoes').element)
  })

  it('mudar a situação com um filtro tira a linha da lista: o foco vai para o título (não para o body)', async () => {
    entrar()
    api()
    const w = await abrir('/crescimento/indicacoes?situacao=nova')
    ;(w.get('[data-abrir="41"]').element as HTMLElement).focus()
    await w.get('[data-abrir="41"]').trigger('click')
    await flushPromises()
    await campo(w, 'Situação', '[role="dialog"]').setValue('em_contato')
    await w.get('#painel-indicacao-form').trigger('submit')
    await flushPromises()
    await esperar()
    expect(w.find('[data-abrir="41"]').exists()).toBe(false)
    expect(t(w.text())).toContain('Nenhuma indicação com esses filtros')
    expect(document.activeElement).toBe(w.get('#t-lista-indicacoes').element)
  })

  it('página vazia depois da primeira volta para a última página que existe (com os botões de página)', async () => {
    entrar()
    const { chamadas } = api({
      'GET /crescimento/indicacoes': ({ url }) => {
        const p = Number(url.searchParams.get('pagina') ?? 1)
        return { itens: p <= 2 ? indicacoes() : [], total: 53, pagina: p, por_pagina: 50, resumo: RESUMO_LISTA }
      },
    })
    const w = await abrir('/crescimento/indicacoes?pagina=5')
    await esperar(400)
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/indicacoes').at(-1))).toEqual({ pagina: '2' })
    expect(router.currentRoute.value.query).toEqual({ pagina: '2' })
    expect(t(w.text())).not.toContain('Nenhuma indicação')
    expect(t(w.get('nav[aria-label="Paginação"]').text())).toContain('Página 2 de 2')
  })

  it('com o painel mudado, trocar de aba ou voltar no navegador pergunta antes; saindo sem salvar, o painel fecha', async () => {
    entrar()
    api()
    const w = await abrir('/crescimento/oportunidades')
    await w.findAll('[role="tab"]')[0]!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/indicacoes')
    await w.get('[data-abrir="41"]').trigger('click')
    await flushPromises()
    await campo(w, 'Situação', '[role="dialog"]').setValue('em_contato')
    await flushPromises()

    // Só o :aba muda (a mesma tela): antes, nem perguntava. "Continuar editando" fica onde está.
    const ida = router.push('/crescimento/oportunidades')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    expect(estadoConfirmacao.titulo).toBe('Sair sem salvar?')
    responderConfirmacao(false)
    await ida
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/indicacoes')
    expect(w.find('[role="dialog"]').exists()).toBe(true)

    // Voltar do navegador (para Oportunidades): a mesma pergunta; "Sair sem salvar" segue
    router.back()
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    responderConfirmacao(false)
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/indicacoes')
    router.back()
    await flushPromises()
    responderConfirmacao(true)
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/oportunidades')
    expect(w.find('[role="dialog"]').exists()).toBe(false)
  })

  it('só os filtros mudando no endereço também pergunta; saindo sem salvar, o painel fecha e a lista segue', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/indicacoes')
    await w.get('[data-abrir="41"]').trigger('click')
    await flushPromises()
    // Sem mudança: o endereço muda e o painel fica
    await router.push('/crescimento/indicacoes?situacao=nova')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(false)
    expect(w.find('[role="dialog"]').exists()).toBe(true)

    await campo(w, 'Responsável', '[role="dialog"]').setValue('2')
    const ida = router.push('/crescimento/indicacoes?situacao=cliente')
    await flushPromises()
    expect(estadoConfirmacao.aberto).toBe(true)
    responderConfirmacao(true)
    await ida
    await esperar()
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    expect(pedidos(chamadas, 'PATCH', '/crescimento/indicacoes/41')).toHaveLength(0)
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/indicacoes').at(-1))).toEqual({ situacao: 'cliente' })
  })

  it('contato e empresa de quem indicou apagados: "Não informado (contato excluído)", sem "Deixou dizer"', async () => {
    entrar()
    const orfa: Indicacao = { ...indicacoes()[0]!, id: 45, nome: 'Sônia Prado', indicador: { contato: null, empresa: null }, pode_identificar: true }
    api({ 'GET /crescimento/indicacoes': () => ({ itens: [orfa], total: 1, pagina: 1, por_pagina: 50, resumo: RESUMO_LISTA }) })
    const w = await abrir('/crescimento/indicacoes')
    const linha = w.get('[data-abrir="45"]').element.closest('tr')!
    expect(t(linha.textContent ?? '')).toContain('Não informado (contato excluído)')
    expect(t(linha.textContent ?? '')).not.toContain('Não quis se identificar')
    await w.get('[data-abrir="45"]').trigger('click')
    await flushPromises()
    expect(t(painel(w).get('[data-quem-indicou]').text())).toBe('Não informado (contato excluído)')
    expect(painel(w).find('[data-pode-identificar]').exists()).toBe(false)
    expect(t(painel(w).text())).not.toContain('Deixou dizer')
  })

  it('e-mails quebram depois do "@" e dos pontos (<wbr>), não no meio da palavra (sem break-all)', async () => {
    entrar()
    const sonia: Indicacao = { ...indicacoes()[0]!, id: 46, email: 'sonia@padariaprado.com.br' }
    api({ 'GET /crescimento/indicacoes': () => ({ itens: [sonia], total: 1, pagina: 1, por_pagina: 50, resumo: RESUMO_LISTA }) })
    const w = await abrir('/crescimento/indicacoes')
    const linha = w.get('[data-abrir="46"]').element.closest('tr')!
    const email = linha.querySelector('[data-email]')!
    expect(email.innerHTML).toBe('sonia@<wbr>padariaprado.<wbr>com.<wbr>br')
    expect(email.className).toContain('[overflow-wrap:anywhere]')
    expect(email.textContent).toBe('sonia@padariaprado.com.br')
    expect(w.findAll('.break-all')).toHaveLength(0)
    // O telefone não quebra
    expect(linha.querySelector('.whitespace-nowrap')?.textContent).toBe('(11) 98765-4321')
  })

  it('"Registrar indicação" (à mão) confere os campos e manda o corpo do contrato', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/indicacoes')
    await botao(w, 'Registrar indicação').trigger('click')
    await flushPromises()
    await w.get('#form-nova-indicacao').trigger('submit')
    await flushPromises()
    expect(t(w.get('#form-nova-indicacao').text())).toContain('Informe o nome de quem você indica.')
    expect(t(w.get('#form-nova-indicacao').text())).toContain('Informe o WhatsApp ou o e-mail (pelo menos um dos dois).')
    expect(pedidos(chamadas, 'POST', '/crescimento/indicacoes')).toHaveLength(0)

    await campo(w, 'Nome de quem foi indicado', '#form-nova-indicacao').setValue('Pedro Alves')
    await campo(w, 'WhatsApp ou telefone', '#form-nova-indicacao').setValue('11912345678')
    await campo(w, 'Responsável', '#form-nova-indicacao').setValue('1')
    await w.get('#form-nova-indicacao').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'POST', '/crescimento/indicacoes')[0]!.corpo).toEqual({
      nome: 'Pedro Alves',
      empresa: null,
      telefone: '11912345678',
      email: null,
      observacao: null,
      indicador_contato_id: null,
      indicador_empresa_id: null,
      responsavel_id: 1,
    })
    expect(w.find('#form-nova-indicacao').exists()).toBe(false)
    await esperar()
    expect(pedidos(chamadas, 'GET', '/crescimento/indicacoes').length).toBeGreaterThanOrEqual(2)
  })

  it('Exportar CSV (painel.exportar) leva os filtros da lista, sem a página', async () => {
    entrar()
    const { chamadas } = api({ 'GET /crescimento/indicacoes.csv': () => new Response('nome;empresa\n', { status: 200, headers: { 'Content-Type': 'text/csv' } }) })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const w = await abrir('/crescimento/indicacoes?situacao=nova&pagina=3&busca=Ana')
    await botao(w, 'Exportar CSV').trigger('click')
    await flushPromises()
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/indicacoes.csv')[0])).toEqual({ situacao: 'nova', busca: 'Ana' })
  })

  it('perfil consulta (só crescimento.ver): sem registrar, sem exportar e o painel só mostra', async () => {
    entrar(['crescimento.ver'], 'consulta')
    const { chamadas } = api()
    const w = await abrir('/crescimento/indicacoes')
    expect(w.findAll('button').some((b) => t(b.text()) === 'Registrar indicação')).toBe(false)
    expect(w.findAll('button').some((b) => t(b.text()) === 'Exportar CSV')).toBe(false)
    // Sem contatos.ver, a lista de responsáveis não é pedida
    expect(pedidos(chamadas, 'GET', '/responsaveis')).toHaveLength(0)
    await w.get('[data-abrir="41"]').trigger('click')
    await flushPromises()
    expect(w.find('#painel-indicacao-form').exists()).toBe(false)
    expect(t(painel(w).text())).toContain('Seu perfil pode ver as indicações, mas não mudar.')
    expect(w.findAll('button').some((b) => t(b.text()).startsWith('Excluir'))).toBe(false)
  })

  it('vazio explica como ligar o convite (com o link para Configurações › Crescimento para quem pode)', async () => {
    entrar()
    api({}, { vazio: true, config: { indicacoes_ativas: false } })
    const w = await abrir('/crescimento/indicacoes')
    expect(t(w.text())).toContain('Nenhuma indicação ainda')
    expect(t(w.text())).toContain('Ligue o convite de indicação')
    expect(w.findAll('a').find((a) => t(a.text()) === 'Ligar o convite')!.attributes('href')).toBe('/configuracoes/crescimento')

    setActivePinia(createPinia())
    entrar(['crescimento.ver', 'crescimento.tratar'], 'gestor')
    api({}, { vazio: true, config: { indicacoes_ativas: false } })
    const w2 = await abrir('/crescimento/indicacoes')
    expect(w2.findAll('a').some((a) => t(a.text()) === 'Ligar o convite')).toBe(false)
    expect(w2.find('[data-pedir-admin]').exists()).toBe(true)

    setActivePinia(createPinia())
    entrar()
    api({}, { vazio: true })
    const w3 = await abrir('/crescimento/indicacoes')
    expect(t(w3.text())).toContain('O convite já está ligado')
    expect(t(w3.text())).toContain('Use “Registrar indicação”')
  })

  it('vazio: "Registrar indicação" só para quem tem crescimento.tratar', async () => {
    entrar(['crescimento.ver'], 'consulta')
    api({}, { vazio: true })
    const w = await abrir('/crescimento/indicacoes')
    expect(t(w.get('[data-vazio-indicacoes]').text())).toContain('O convite já está ligado')
    expect(t(w.text())).not.toContain('Registrar indicação')
  })

  it('vazio sem a configuração: não diz "Ligue o convite"; o erro mostra "Tentar de novo"', async () => {
    entrar()
    let config: 'falha' | 'desligado' = 'falha'
    const { chamadas } = api(
      {
        'GET /crescimento/configuracao': () =>
          config === 'falha'
            ? new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Serviço fora do ar.' } }), { status: 503 })
            : { ...CONFIG, indicacoes_ativas: false },
      },
      { vazio: true },
    )
    const w = await abrir('/crescimento/indicacoes')
    expect(t(w.text())).toContain('Nenhuma indicação ainda')
    expect(t(w.text())).not.toContain('Ligue o convite')
    expect(w.findAll('a').some((a) => t(a.text()) === 'Ligar o convite')).toBe(false)
    expect(t(w.get('[data-vazio-indicacoes]').text())).toContain('Com o convite de indicação ligado, quem der nota 9 ou 10')
    const alerta = w.get('[data-erro-config]')
    expect(t(alerta.text())).toContain('Não deu para saber se o convite de indicação está ligado: Serviço fora do ar.')

    // Tentar de novo: agora a configuração chega (desligado) e o vazio explica como ligar
    config = 'desligado'
    await alerta.get('button').trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, 'GET', '/crescimento/configuracao')).toHaveLength(2)
    expect(w.find('[data-erro-config]').exists()).toBe(false)
    expect(t(w.text())).toContain('Ligue o convite de indicação')
  })

  it('enquanto a configuração não chega, o vazio não diz que o convite está desligado', async () => {
    entrar()
    api({ 'GET /crescimento/configuracao': () => new Promise(() => {}) }, { vazio: true })
    const w = await abrir('/crescimento/indicacoes')
    expect(t(w.text())).toContain('Nenhuma indicação ainda')
    expect(t(w.text())).not.toContain('Ligue o convite')
    expect(w.find('[data-erro-config]').exists()).toBe(false)
  })

  it('registro à mão: o responsável em branco diz que vai o da empresa de quem indicou', async () => {
    entrar()
    api()
    const w = await abrir('/crescimento/indicacoes')
    await botao(w, 'Registrar indicação').trigger('click')
    await flushPromises()
    const responsavel = campo(w, 'Responsável', '#form-nova-indicacao')
    expect(responsavel.findAll('option').map((o) => o.text())).toEqual(['O da empresa de quem indicou', 'Carla Ribeiro', 'Diego Martins'])
    expect(t(w.get('#form-nova-indicacao').text())).toContain('Em branco: o responsável da empresa de quem indicou.')
    expect(t(w.get('#form-nova-indicacao').text())).not.toContain('Ninguém por enquanto')
  })
})

describe('Crescimento › Oportunidades', () => {
  const TEXTO = 'Olá, Marcos! Aqui é Ana, da Distribuidora Sol. Obrigado pela ótima avaliação! Preparei uma condição especial para a Atacadão do Vale. Posso te contar?'

  it('as duas listas com o critério de cada uma e a regra de ouro; grupo e responsável filtram', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/oportunidades')
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/oportunidades')[0])).toEqual({ lista: 'pode_crescer' })
    expect(t(w.get('[data-criterio]').text())).toContain('quadrante “Pode crescer” de Relatórios › Empresas')
    expect(t(w.get('[data-regra-de-ouro]').text())).toContain('com detrator (nota 0 a 6) nos últimos 90 dias ou com plano de ação aberto')

    await w.get('input[type="radio"][value="promotores"]').setValue(true)
    await esperar()
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/oportunidades').at(-1))).toEqual({ lista: 'promotores' })
    expect(router.currentRoute.value.query).toEqual({ lista: 'promotores' })
    expect(t(w.get('[data-criterio]').text())).toContain('nota 9 ou 10 nos últimos 30 dias')

    await campo(w, 'Grupo de empresas').setValue('2')
    await campo(w, 'Responsável').setValue('1')
    await esperar()
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/oportunidades').at(-1))).toEqual({ lista: 'promotores', grupo_id: '2', responsavel_id: '1' })
  })

  it('"Oferecer pelo WhatsApp" abre wa.me com o texto da oferta e registra a oferta; sem telefone, e-mail; sem contato, nada', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/oportunidades')
    const link = w.get('[data-oferecer="21"]')
    expect(link.attributes('href')).toBe(`https://wa.me/5511976543210?text=${encodeURIComponent(TEXTO)}`)
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
    expect(t(link.text())).toBe('Oferecer pelo WhatsApp para Atacadão do Vale (abre em nova aba)')
    expect(w.find('[data-resultado="21"]').exists()).toBe(false)

    await link.trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, 'POST', '/crescimento/ofertas')[0]!.corpo).toEqual({ empresa_id: 21, contato_id: 201, lista: 'pode_crescer', canal: 'whatsapp', texto: TEXTO })
    expect(t(w.get('[data-resultado="21"]').text())).toBe('Registrar resultado da oferta para Atacadão do Vale')
    expect(pedidos(chamadas, 'GET', '/crescimento/resumo')).toHaveLength(2)

    const email = w.get('[data-oferecer="22"]')
    expect(email.attributes('href')).toMatch(/^mailto:beatriz@sabor\.com\.br\?subject=Uma%20condi%C3%A7%C3%A3o%20especial%20para%20a%20Hortifruti%20Sabor&body=Ol%C3%A1%2C%20Beatriz!/)
    expect(email.attributes('target')).toBeUndefined()
    expect(t(email.text())).toContain('Oferecer por e-mail')
    // A oferta por e-mail fica gravada como e-mail (não como WhatsApp)
    await email.trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, 'POST', '/crescimento/ofertas')[1]!.corpo).toMatchObject({ empresa_id: 22, contato_id: 202, canal: 'email' })

    expect(w.find('[data-oferecer="24"]').exists()).toBe(false)
    expect(t(w.text())).toContain('Sem contato disponível')
  })

  it('clique duplo abre uma conversa e registra uma oferta só; a empresa fica travada alguns segundos', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/oportunidades')
    // Sem o "não navegar" geral: aqui importa saber se a tela barrou o link (o que ela não barra, o teste barra depois).
    document.removeEventListener('click', semNavegar, true)
    const barrados: boolean[] = []
    const depois = (e: Event) => {
      barrados.push(e.defaultPrevented)
      e.preventDefault()
    }
    document.addEventListener('click', depois)
    const clicar = (detail: number, sel = '[data-oferecer="21"]') => w.get(sel).element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, detail }))
    try {
      clicar(1)
      clicar(2) // o segundo clique de um clique duplo
      await flushPromises()
      expect(barrados).toEqual([false, true])
      expect(pedidos(chamadas, 'POST', '/crescimento/ofertas')).toHaveLength(1)
      expect(w.get('[data-oferecer="21"]').attributes('aria-disabled')).toBe('true')

      // Registrada: outro clique logo em seguida (no cartão, a mesma empresa) também não abre nem registra
      clicar(1, '[data-oferecer-cartao="21"]')
      await flushPromises()
      expect(barrados).toEqual([false, true, true])
      expect(pedidos(chamadas, 'POST', '/crescimento/ofertas')).toHaveLength(1)

      // Passados os segundos da trava, oferecer de novo vale
      await esperar(5000)
      expect(w.get('[data-oferecer="21"]').attributes('aria-disabled')).toBeUndefined()
      clicar(1)
      await flushPromises()
      expect(barrados.at(-1)).toBe(false)
      expect(pedidos(chamadas, 'POST', '/crescimento/ofertas')).toHaveLength(2)
    } finally {
      document.removeEventListener('click', depois)
    }
  })

  it('falha ao registrar a oferta avisa (a conversa já abriu); o 422 (regra de ouro na hora) pede para não mandar e atualiza a lista', async () => {
    entrar()
    let vez = 0
    let saiu = false
    const { chamadas } = api({
      'POST /crescimento/ofertas': () => {
        if (++vez === 1) return new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Serviço fora do ar.' } }), { status: 503 })
        if (vez === 2) return erro422('Confira os campos destacados.', { contato_id: 'Este contato saiu da lista e não recebe ofertas.' })
        // Como a API: a regra de ouro conferida na hora, com o motivo na mensagem e no campo
        saiu = true
        const motivo = 'Esta empresa saiu das oportunidades: ela tem um plano de ação aberto.'
        return new Response(JSON.stringify({ erro: { codigo: 'dados_invalidos', mensagem: motivo, campos: { empresa_id: motivo } } }), { status: 422 })
      },
      'GET /crescimento/oportunidades': () => {
        const itens = oportunidades().filter((o) => !saiu || o.empresa.id !== 21)
        return { itens, total: itens.length, pagina: 1, por_pagina: 50 }
      },
    })
    const w = await abrir('/crescimento/oportunidades')
    await w.get('[data-oferecer="21"]').trigger('click')
    await flushPromises()
    expect(avisos.map((a) => a.mensagem)).toContain('A conversa abriu, mas a oferta não foi registrada: Serviço fora do ar.')
    expect(w.find('[data-resultado="21"]').exists()).toBe(false)
    // Sem registro, não trava: dá para tentar de novo na hora
    await w.get('[data-oferecer="21"]').trigger('click')
    await flushPromises()
    expect(avisos.map((a) => a.mensagem)).toContain('Este contato saiu da lista e não recebe ofertas. A oferta não foi registrada: não mande a mensagem que abriu.')

    const listas = pedidos(chamadas, 'GET', '/crescimento/oportunidades').length
    await w.get('[data-oferecer="21"]').trigger('click')
    await flushPromises()
    expect(avisos.map((a) => a.mensagem)).toContain('Esta empresa saiu das oportunidades: ela tem um plano de ação aberto. A oferta não foi registrada: não mande a mensagem que abriu.')
    expect(pedidos(chamadas, 'GET', '/crescimento/oportunidades').length).toBeGreaterThan(listas)
    expect(w.find('[data-oferecer="21"]').exists()).toBe(false)
  })

  it('sem a configuração (carregando ou com erro), "Oferecer" fica desligado; o erro mostra "Tentar de novo"', async () => {
    entrar()
    let falhar = true
    const { chamadas } = api({
      'GET /crescimento/configuracao': () =>
        falhar ? new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Serviço fora do ar.' } }), { status: 503 }) : CONFIG,
    })
    const w = await abrir('/crescimento/oportunidades')
    const oferecer = w.get('[data-oferecer="21"]')
    expect(oferecer.element.tagName).toBe('BUTTON')
    expect(oferecer.attributes('disabled')).toBeDefined()
    expect(oferecer.attributes('href')).toBeUndefined()
    expect(w.get('[data-oferecer-cartao="22"]').attributes('disabled')).toBeDefined()
    const alerta = w.get('[data-erro-config]')
    expect(t(alerta.text())).toContain('Não deu para carregar o texto da oferta: Serviço fora do ar.')
    // Clicar no botão desligado não registra nada
    await oferecer.trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, 'POST', '/crescimento/ofertas')).toHaveLength(0)

    falhar = false
    await alerta.get('button').trigger('click')
    await flushPromises()
    expect(pedidos(chamadas, 'GET', '/crescimento/configuracao')).toHaveLength(2)
    expect(w.find('[data-erro-config]').exists()).toBe(false)
    expect(w.get('[data-oferecer="21"]').element.tagName).toBe('A')
    expect(w.get('[data-oferecer="21"]').attributes('href')).toBe(`https://wa.me/5511976543210?text=${encodeURIComponent(TEXTO)}`)
  })

  it('enquanto a configuração não chega, "Oferecer" fica desligado (sem o texto padrão no lugar)', async () => {
    entrar()
    api({ 'GET /crescimento/configuracao': () => new Promise(() => {}) })
    const w = await abrir('/crescimento/oportunidades')
    expect(w.get('[data-oferecer="21"]').attributes('disabled')).toBeDefined()
    expect(w.find('a[href^="https://wa.me"]').exists()).toBe(false)
    expect(w.find('[data-erro-config]').exists()).toBe(false)
  })

  it('"Registrar resultado": nada marcado de saída; aceitou com valor; recusou sem valor', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/oportunidades')
    await w.get('[data-resultado="22"]').trigger('click')
    await flushPromises()
    expect(w.findAll('#form-resultado-oferta input[type="radio"]').map((r) => (r.element as HTMLInputElement).checked)).toEqual([false, false, false])
    await w.get('#form-resultado-oferta').trigger('submit')
    await flushPromises()
    expect(t(w.get('[data-erro-resultado]').text())).toBe('Escolha como foi a oferta.')
    expect(pedidos(chamadas, 'PATCH', '/crescimento/ofertas/501')).toHaveLength(0)

    await w.get('input[type="radio"][value="aceitou"]').setValue(true)
    expect(w.find('[data-erro-resultado]').exists()).toBe(false)
    await campo(w, 'Valor da venda', '#form-resultado-oferta').setValue('1.200,00')
    await w.get('#form-resultado-oferta').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'PATCH', '/crescimento/ofertas/501')[0]!.corpo).toEqual({ resultado: 'aceitou', valor: 1200 })
    expect(t(w.get('[data-resultado="22"]').element.closest('td')!.textContent ?? '')).toContain('Aceitou')
    expect(t(w.get('[data-resultado="22"]').text())).toContain('Mudar resultado')

    await w.get('[data-resultado="22"]').trigger('click')
    await flushPromises()
    await w.get('input[type="radio"][value="recusou"]').setValue(true)
    expect(w.find('#form-resultado-oferta input[inputmode="decimal"]').exists()).toBe(false)
    await w.get('#form-resultado-oferta').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'PATCH', '/crescimento/ofertas/501')[1]!.corpo).toEqual({ resultado: 'recusou' })
    expect(t(w.get('[data-resultado="22"]').element.closest('td')!.textContent ?? '')).toContain('Recusou')
  })

  it('"Mudar resultado" de uma oferta aceita abre com o valor; com o campo vazio, o valor não vai (e não se perde)', async () => {
    entrar()
    const { chamadas } = api()
    const w = await abrir('/crescimento/oportunidades')
    await w.get('[data-resultado="22"]').trigger('click')
    await flushPromises()
    await w.get('input[type="radio"][value="aceitou"]').setValue(true)
    await campo(w, 'Valor da venda', '#form-resultado-oferta').setValue('1.250')
    await w.get('#form-resultado-oferta').trigger('submit')
    await flushPromises()
    // "1.250" é mil duzentos e cinquenta (não R$ 1,25)
    expect(pedidos(chamadas, 'PATCH', '/crescimento/ofertas/501')[0]!.corpo).toEqual({ resultado: 'aceitou', valor: 1250 })

    await w.get('[data-resultado="22"]').trigger('click')
    await flushPromises()
    expect(w.get('input[type="radio"][value="aceitou"]').element).toHaveProperty('checked', true)
    const valor = campo(w, 'Valor da venda', '#form-resultado-oferta')
    expect((valor.element as HTMLInputElement).value).toBe('1.250,00')
    expect(t(w.get('#form-resultado-oferta').text())).toContain('Em branco, fica o valor já registrado')
    await valor.setValue('')
    avisos.splice(0)
    await w.get('#form-resultado-oferta').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'PATCH', '/crescimento/ofertas/501')[1]!.corpo).toEqual({ resultado: 'aceitou' })
    expect(avisos.map((a) => a.mensagem)).toContain('Resultado registrado: aceitou (R$ 1.250,00).')

    // Sem mexer no campo, o mesmo valor vai de volta
    await w.get('[data-resultado="22"]').trigger('click')
    await flushPromises()
    expect((campo(w, 'Valor da venda', '#form-resultado-oferta').element as HTMLInputElement).value).toBe('1.250,00')
    await w.get('#form-resultado-oferta').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'PATCH', '/crescimento/ofertas/501')[2]!.corpo).toEqual({ resultado: 'aceitou', valor: 1250 })
  })

  it('Exportar CSV leva a lista escolhida; só crescimento.ver não oferece nem registra resultado', async () => {
    entrar()
    const { chamadas } = api({ 'GET /crescimento/oportunidades.csv': () => new Response('empresa\n', { status: 200, headers: { 'Content-Type': 'text/csv' } }) })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const w = await abrir('/crescimento/oportunidades?lista=promotores')
    await botao(w, 'Exportar CSV').trigger('click')
    await flushPromises()
    expect(consulta(pedidos(chamadas, 'GET', '/crescimento/oportunidades.csv')[0])).toEqual({ lista: 'promotores' })

    setActivePinia(createPinia())
    entrar(['crescimento.ver'], 'consulta')
    api()
    const w2 = await abrir('/crescimento/oportunidades')
    expect(w2.find('[data-oferecer]').exists()).toBe(false)
    expect(w2.find('[data-oferecer-cartao]').exists()).toBe(false)
    expect(w2.find('[data-resultado]').exists()).toBe(false)
    expect(t(w2.text())).toContain('Seu perfil pode ver as oportunidades, mas não registrar ofertas.')
    expect(w2.findAll('button').some((b) => t(b.text()) === 'Exportar CSV')).toBe(false)
  })
})

describe('fora de Crescimento', () => {
  it('Contatos › Empresas: "1.250" no valor mensal é mil duzentos e cinquenta; valor que não dá para ler fica e é apontado', async () => {
    entrar()
    const { chamadas } = api({
      'GET /cadastros/segmentos': () => [],
      'POST /empresas': ({ corpo }) => new Response(JSON.stringify({ id: 77, ...(corpo as object) }), { status: 201 }),
    })
    const w = mount(ModalEmpresa, { props: { empresa: null, aberto: false }, global: { stubs: { teleport: true } }, attachTo: document.body })
    await w.setProps({ aberto: true })
    await flushPromises()
    // O campo é buscado a cada passo: com o Teleport trocado pelo stub, cada novo desenho do modal recria os campos.
    const valor = () => campo(w, 'Valor mensal')
    const lido = () => (valor().element as HTMLInputElement).value
    // O blur à mão: o trigger do test-utils marca a hora do evento e, com o relógio falso parado, o Vue o ignoraria.
    const digitarESair = async (texto: string) => {
      await valor().setValue(texto)
      valor().element.dispatchEvent(new FocusEvent('blur'))
      await flushPromises()
    }
    await digitarESair('1.2.3')
    // Antes, sumia ao sair do campo (ou virava um número errado); agora fica para a pessoa conferir
    expect(lido()).toBe('1.2.3')
    await campo(w, 'Nome').setValue('Padaria Prado')
    await w.get('#form-empresa').trigger('submit')
    await flushPromises()
    expect(t(w.get('#form-empresa').text())).toContain('Digite um valor, ex.: 1.250,00.')
    expect(pedidos(chamadas, 'POST', '/empresas')).toHaveLength(0)

    await digitarESair('1.250')
    expect(lido()).toBe('1.250,00')
    await w.get('#form-empresa').trigger('submit')
    await flushPromises()
    expect(pedidos(chamadas, 'POST', '/empresas')[0]!.corpo).toMatchObject({ nome: 'Padaria Prado', valor_mensal: 1250 })
  })

  it('Integrações › "Para o técnico" descreve os dados dos eventos de indicação', async () => {
    api({ 'GET /integracoes/webhooks': () => [] })
    const w = mount(SecaoWebhooks, { global: { stubs: { teleport: true } }, attachTo: document.body })
    await flushPromises()
    const formato = t(w.get('[data-formato-indicacoes]').text())
    expect(formato).toContain('Em indicacao.criada (pela pesquisa ou registrada pela equipe) e indicacao.atualizada (mudou de situação), dados traz o item da lista de indicações')
    expect(formato).toContain('indicador: {contato, empresa}, pode_identificar, responsavel, situacao, valor_mensal')
    expect(formato).toContain('em indicacao.atualizada, também situacao_anterior')
  })
})

describe('rotas e permissões', () => {
  it('Crescimento pede crescimento.ver; /crescimento leva para Indicações', () => {
    expect(rotasDoApp.resolve('/crescimento/indicacoes').meta.permissao).toBe('crescimento.ver')
    expect(rotasDoApp.resolve('/crescimento/oportunidades').name).toBe('crescimento')
    expect(rotasDoApp.resolve('/configuracoes/crescimento').meta.algumaPermissao).toEqual(['configuracoes.gerenciar', 'crescimento.ver'])
  })

  it('Configurações › Crescimento abre com configuracoes.gerenciar ou crescimento.ver; sem as duas, volta ao início', async () => {
    vi.stubGlobal('scrollTo', vi.fn())
    entrar(['crescimento.ver'], 'consulta')
    const sessao = useSessaoStore()
    sessao.inicializada = true
    api()
    await rotasDoApp.push('/configuracoes/crescimento')
    expect(rotasDoApp.currentRoute.value.name).toBe('config-crescimento')
    await rotasDoApp.push('/crescimento')
    expect(rotasDoApp.currentRoute.value.fullPath).toBe('/crescimento/indicacoes')
    sessao.permissoes = ['configuracoes.gerenciar']
    await rotasDoApp.push('/configuracoes/crescimento')
    expect(rotasDoApp.currentRoute.value.name).toBe('config-crescimento')
    await rotasDoApp.push('/inicio')
    sessao.permissoes = ['painel.ver']
    await rotasDoApp.push('/configuracoes/crescimento')
    expect(rotasDoApp.currentRoute.value.name).toBe('inicio')
    await rotasDoApp.push('/crescimento/indicacoes')
    expect(rotasDoApp.currentRoute.value.name).toBe('inicio')
  })
})
