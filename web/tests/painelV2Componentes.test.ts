import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import { defineComponent, h } from 'vue'
import type { Painel, TomComentarios } from '@/api/tipos'
import { useAssistenteStore } from '@/stores/assistente'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { somarDias } from '@/utils/periodo'
import BlocoEmpresas from '@/modulos/painel/BlocoEmpresas.vue'
import BlocoPalavras from '@/modulos/painel/BlocoPalavras.vue'
import BlocoTemas from '@/modulos/painel/BlocoTemas.vue'
import BlocoTom from '@/modulos/painel/BlocoTom.vue'
import GraficoEvolucao from '@/modulos/painel/GraficoEvolucao.vue'
import MedidorNps from '@/modulos/painel/MedidorNps.vue'
import PainelView from '@/modulos/painel/PainelView.vue'
import { PERGUNTA_TOQQIAI } from '@/modulos/painel/logica'
import { apiFalsa } from './apiFalsa'

const HOJE = hojeIso()
const TODAS = ['painel.ver', 'painel.exportar', 'respostas.ver', 'acoes.ver', 'contatos.ver', 'envios.ver', 'formularios.ver', 'configuracoes.gerenciar']

const TOM: TomComentarios = { analisados: 24, com_comentario: 24, total_respostas: 31, negativo: 11, misto: 3, neutro: 2, positivo: 8, anterior: { analisados: 25, negativo: 7 } }

function meses12(): Painel['evolucao_12m'] {
  const fim = new Date(`${HOJE}T12:00:00Z`)
  const lista = []
  for (let i = 11; i >= 0; i--) {
    const d = new Date(Date.UTC(fim.getUTCFullYear(), fim.getUTCMonth() - i, 1))
    const mes = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
    const nps = [50, 50, 55, 40, -36, 0, 14, 30, null, 57, 57, -33][11 - i]!
    lista.push({ mes, nps, total: nps === null ? 0 : 10, no_periodo: i <= 2 })
  }
  return lista
}

function painel(extra: Partial<Painel> = {}): Painel {
  return {
    periodo: { de: somarDias(HOJE, -89), ate: HOJE, anterior: { de: somarDias(HOJE, -179), ate: somarDias(HOJE, -90) } },
    nps: {
      valor: 23,
      faixa: 'pode_melhorar',
      promotores: 16,
      neutros: 6,
      detratores: 9,
      total: 31,
      pct: { promotores: 51.6, neutros: 19.4, detratores: 29 },
      decisores: { valor: -10, total: 8 },
    },
    variacao: { valor: -11, anterior: 34 },
    csat: { percentual: null, media: null, total: 0, satisfeitos: 0 },
    taxa_resposta: { percentual: null, responderam: 0, convidados: 0, amostra_pequena: false },
    movimentacao: { resgatados: 3, deixaram_de_ser_promotores: 7, itens: [] },
    atencao: {
      acoes_abertas: 0,
      acoes_vencidas: 0,
      tudo_em_dia: true,
      empresas: [],
      receita_em_risco: { valor: 265200, empresas: 8, sem_valor: 0, carteira: 552500 },
    },
    temas: [
      { chave: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 13, nota_media: 6.2, reclamacoes: 8, variacao: 9 },
      { chave: 'atendimento', rotulo: 'Atendimento', mencoes: 2, nota_media: 8, reclamacoes: 0, variacao: -4 },
    ],
    comentarios: [
      {
        resposta_id: 5,
        data: '2026-09-30T10:00:00-03:00',
        nota: 6,
        tipo_nota: 'nps',
        grupo: 'detrator',
        comentario: 'Produto bom, mas a entrega atrasou.',
        contato: { id: 1, nome: 'José Ricardo Neves' },
        empresa: { id: 2, nome: 'Frigorífico Rio Meia Ponte' },
      },
    ],
    evolucao: [{ mes: HOJE.slice(0, 7), nps: 23, total: 31 }],
    evolucao_12m: meses12(),
    empresas: {
      menor: [{ empresa: { id: 1, nome: 'Agropecuária Chapadão Azul' }, nps: -33, respostas: 3, valor_mensal: '48000.00' }],
      maior: [{ empresa: { id: 9, nome: 'Metalúrgica Veredas' }, nps: 67, respostas: 3, valor_mensal: null }],
    },
    palavras: [
      { palavra: 'entrega', total: 12 },
      { palavra: 'pouco', total: 2 },
    ],
    primeiros_passos: { contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: true },
    picos: [{ tema: 'prazo_entrega', rotulo: 'Prazo e entrega', reclamacoes: 6, media_anterior: 0.3, de: somarDias(HOJE, -6), ate: HOJE }],
    tom: TOM,
    ...extra,
  }
}

function entrar(permissoes: string[]) {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Ana Paula', email: 'a@x.com', cargo: null, perfil: 'gestor', situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 42, nome: 'Conta', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

let router: Router
async function abrir(endereco = '/inicio'): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/inicio', component: PainelView },
      { path: '/:qualquer(.*)*', component: { render: () => h('div') } },
    ],
  })
  await router.push(endereco)
  await router.isReady()
  const w = mount(defineComponent({ render: () => h(RouterView) }), { global: { plugins: [router], stubs: { teleport: true } }, attachTo: document.body })
  await flushPromises()
  return w
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('Início v2: a página', () => {
  it('Resumo: medidor, faixa, variação, manchete com pico + receita, distribuição e decisores', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
    const w = await abrir()
    expect(w.get('h2#t-resumo').text()).toBe('NPS dos últimos 90 dias')
    expect(w.get('[data-medidor]').attributes('aria-label')).toBe('NPS 23 numa escala de −100 a 100, faixa Pode melhorar')
    expect(w.get('[data-variacao]').text()).toContain('11 pontos sobre os 90 dias antes (34)')
    expect(w.get('[data-variacao]').text()).toContain('O NPS caiu 11 pontos')
    expect(w.get('[data-manchete-titulo]').text()).toBe(
      'O NPS caiu 11 pontos. 6 reclamações de Prazo e entrega em 7 dias, quando a média era 0,3 por semana.',
    )
    expect(w.get('[data-manchete-apoio]').text()).toBe(
      '8 empresas tiveram detrator no período, somando R$ 265,2 mil por mês em contrato. Nenhuma tem plano de ação aberto.',
    )
    const botoes = w.get('[data-manchete]').element.parentElement!.textContent!
    expect(botoes).toContain('Ver as 6 reclamações')
    expect(botoes).toContain('Ver os detratores')
    expect(w.text()).toContain('9 detratores')
    expect(w.text()).toContain('31 respostas de NPS')
    expect(w.text()).toMatch(/decisores: −10/)
  })

  it('cabeçalho: data por extenso; filtros acessíveis com nome; "Só ativas" é um botão de alternar', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
    const w = await abrir()
    expect(w.find('select#filtro-periodo').exists()).toBe(true)
    expect(w.find('label[for="filtro-periodo"]').text()).toBe('Período')
    const ativas = w.findAll('button').find((b) => b.text().startsWith('Só ativas'))!
    expect(ativas.attributes('aria-pressed')).toBe('true')
    expect(w.text()).toContain('Exportar CSV')
    expect(w.text()).toContain('Como ler os números')
  })

  it('filtros vão para o endereço e vêm dele', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      entrar(TODAS)
      const { chamadas } = apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
      const w = await abrir('/inicio?periodo=30&so_ativos=false')
      const primeiro = chamadas.find((c) => c.caminho === '/painel')!
      expect(Object.fromEntries(primeiro.url.searchParams)).toEqual({ de: somarDias(HOJE, -29), ate: HOJE, so_ativos: 'false' })
      expect(w.get('h2#t-resumo').text()).toBe('NPS dos últimos 30 dias')
      await w.get('select#filtro-periodo').setValue('7')
      await w.findAll('button').find((b) => b.text().startsWith('Só ativas'))!.trigger('click')
      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      expect(router.currentRoute.value.query).toEqual({ periodo: '7' })
      const ultimo = chamadas.filter((c) => c.caminho === '/painel').at(-1)!
      expect(Object.fromEntries(ultimo.url.searchParams)).toEqual({ de: somarDias(HOJE, -6), ate: HOJE, so_ativos: 'true' })
    } finally {
      vi.useRealTimers()
    }
  })

  it('indicadores: receita com % da carteira; CSAT e taxa sem dados viram cartões apagados com atalho (só para quem pode)', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
    let w = await abrir()
    expect(w.get('[data-indicador="receita"]').text()).toContain('8 empresas com detrator · 48% da carteira')
    const csat = w.get('[data-indicador="csat"]')
    expect(csat.attributes('data-apagado')).toBeDefined()
    expect(csat.find('a').attributes('href')).toBe('/formularios')
    expect(w.get('[data-indicador="taxa"]').find('a').attributes('href')).toBe('/envios')
    w.unmount()

    entrar(['painel.ver'])
    apiFalsa({ 'GET /painel': () => painel({ atencao: { ...painel().atencao, receita_em_risco: { valor: 1000, empresas: 1, sem_valor: 0 } } }) })
    w = await abrir()
    expect(w.get('[data-indicador="csat"]').find('a').exists()).toBe(false)
    expect(w.get('[data-indicador="taxa"]').find('a').exists()).toBe(false)
    // Sem carteira (servidor antigo), sem porcentagem.
    expect(w.get('[data-indicador="receita"]').text()).not.toContain('carteira')
    // Sem respostas.ver nem acoes.ver, a manchete não oferece botões.
    expect(w.text()).not.toContain('Ver as 6 reclamações')
    expect(w.text()).not.toContain('Ver os detratores')
  })

  it('ToqqiAI: o botão só aparece com o assistente disponível e abre o chat com a pergunta', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
    let w = await abrir()
    expect(w.find('[data-toqqiai]').exists()).toBe(false)
    w.unmount()
    const assistente = useAssistenteStore()
    assistente.estado = { disponivel: true, motivo: null, cota: null, sugestoes: [] }
    w = await abrir()
    await w.get('[data-toqqiai]').trigger('click')
    expect(assistente.aberto).toBe(true)
    expect(assistente.rascunho).toBe(PERGUNTA_TOQQIAI)
  })

  it('evolução de 12 meses com destaque; sem `evolucao_12m` (servidor antigo), usa `evolucao`; sem `tom`, sem o bloco', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
    let w = await abrir()
    expect(w.get('#t-evolucao').text()).toBe('NPS nos últimos 12 meses')
    expect(w.find('[data-periodo]').exists()).toBe(true)
    expect(w.findAll('[data-extremo]')).toHaveLength(2)
    expect(w.find('[data-tom]').exists()).toBe(true)
    w.unmount()

    const { evolucao_12m: _e, tom: _t, ...antigo } = painel()
    apiFalsa({ 'GET /painel': () => antigo, 'GET /cadastros/grupos': () => [] })
    w = await abrir()
    expect(w.get('#t-evolucao').text()).toBe('Evolução do NPS')
    expect(w.find('[data-periodo]').exists()).toBe(false)
    expect(w.find('[data-tom]').exists()).toBe(false)
  })

  it('pico de outro recorte: com grupo filtrado ou período que não termina hoje, a manchete segue para a regra 2', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [{ id: 3, nome: 'Rede Leste' }] })
    let w = await abrir('/inicio?grupo_id=3')
    expect(w.get('[data-manchete-titulo]').text()).toBe('O NPS caiu 11 pontos em relação aos 90 dias antes.')
    expect(w.text()).not.toContain('Ver as 6 reclamações')
    expect(w.text()).not.toContain('Também com pico')
    w.unmount()

    const de = somarDias(HOJE, -40)
    const ate = somarDias(HOJE, -10)
    w = await abrir(`/inicio?periodo=personalizado&de=${de}&ate=${ate}`)
    expect(w.get('[data-manchete-titulo]').text()).toMatch(/^O NPS caiu 11 pontos em relação/)
    expect(w.text()).not.toContain('Ver as 6 reclamações')
    w.unmount()

    // Sem grupo e terminando hoje, o pico volta.
    w = await abrir('/inicio?periodo=30')
    expect(w.get('[data-manchete-titulo]').text()).toContain('6 reclamações de Prazo e entrega')
    expect(w.text()).toContain('Ver as 6 reclamações')
  })

  it('endereço inválido: período sem datas ou trocado volta aos 90 dias, busca e corrige o endereço; grupo inexistente sai', async () => {
    entrar(TODAS)
    const { chamadas } = apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [{ id: 3, nome: 'Rede Leste' }] })
    let w = await abrir('/inicio?periodo=personalizado')
    expect(w.find('[role="status"]').exists()).toBe(false)
    expect(w.get('h2#t-resumo').text()).toBe('NPS dos últimos 90 dias')
    expect(router.currentRoute.value.query).toEqual({})
    expect(chamadas.filter((c) => c.caminho === '/painel')).toHaveLength(1)
    w.unmount()

    w = await abrir(`/inicio?periodo=personalizado&de=${HOJE}&ate=${somarDias(HOJE, -5)}&so_ativos=false`)
    expect(w.get('h2#t-resumo').text()).toBe('NPS dos últimos 90 dias')
    expect(router.currentRoute.value.query).toEqual({ so_ativos: 'false' })
    w.unmount()

    w = await abrir('/inicio?periodo=30&grupo_id=999&utm=x')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ periodo: '30', utm: 'x' })
    expect((w.get('select#filtro-grupo').element as HTMLSelectElement).value).toBe('')
  })

  it('variação zero: "= Igual aos N dias antes (34)" em cinza', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel({ variacao: { valor: 0, anterior: 34 } }), 'GET /cadastros/grupos': () => [] })
    const w = await abrir()
    const v = w.get('[data-variacao]')
    expect(v.text().replace(/\s+/g, ' ')).toBe('= Igual aos 90 dias antes (34)')
    expect(v.find('.text-texto-suave').exists()).toBe(true)
    expect(v.find('.text-erro').exists()).toBe(false)
  })

  it('receita sem nenhum valor cadastrado: cartão apagado com link só para quem edita contatos', async () => {
    const semValor = () => painel({ atencao: { ...painel().atencao, receita_em_risco: { valor: 0, empresas: 3, sem_valor: 3, carteira: null } } })
    entrar(TODAS.concat('contatos.editar'))
    apiFalsa({ 'GET /painel': semValor, 'GET /cadastros/grupos': () => [] })
    let w = await abrir()
    const r = w.get('[data-indicador="receita"]')
    expect(r.attributes('data-apagado')).toBeDefined()
    expect(r.text()).toContain('Cadastre o valor mensal das empresas')
    expect(r.get('a').attributes('href')).toBe('/contatos?aba=empresas')
    w.unmount()
    entrar(TODAS)
    w = await abrir()
    expect(w.get('[data-indicador="receita"]').find('a').exists()).toBe(false)
    expect(w.get('[data-indicador="receita"]').text()).toContain('Cadastre o valor mensal das empresas')
  })

  it('evolução que termina antes do mês atual: "NPS em 12 meses até {mês de ano}"', async () => {
    entrar(TODAS)
    const ev = meses12()!.map((m, i) => ({ ...m, mes: `2025-${String(i + 1).padStart(2, '0')}` }))
    apiFalsa({ 'GET /painel': () => painel({ evolucao_12m: ev }), 'GET /cadastros/grupos': () => [] })
    const w = await abrir()
    expect(w.get('#t-evolucao').text()).toBe('NPS em 12 meses até dezembro de 2025')
  })

  it('espaço no fim da página para o botão flutuante do ToqqiAI', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [] })
    const w = await abrir()
    expect(w.get('[aria-busy], .\\@container').classes()).toContain('pb-28')
  })

  it('Quem mudou de lado: os dois números com os selos de grupo', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
    const w = await abrir()
    expect(w.get('[data-resgatados]').text()).toMatch(/^3detrator.*promotor.*resgatados/)
    expect(w.get('[data-deixaram]').text()).toMatch(/^7promotor.*8 ou menos.*deixaram de ser promotores/)
  })

  it('comentários como citações, com a nota no selo e o link para a análise', async () => {
    entrar(TODAS)
    apiFalsa({ 'GET /painel': () => painel(), 'GET /cadastros/grupos': () => [], 'GET /conta/ia': () => ({}) })
    const w = await abrir()
    const c = w.get('[data-comentario]')
    expect(c.element.tagName).toBe('A')
    expect(c.attributes('href')).toBe('/respostas?analisar=5')
    expect(c.classes()).toContain('bg-erro-suave')
    expect(c.find('q').text()).toBe('Produto bom, mas a entrega atrasou.')
    expect(c.text()).toContain('Nota 6 de 10, Detrator')
  })
})

describe('Início v2: blocos', () => {
  it('medidor: o marcador fica no valor; número escrito', () => {
    const w = mount(MedidorNps, { props: { valor: 0 } })
    const m = w.get('[data-marcador]')
    expect([m.attributes('cx'), m.attributes('cy')]).toEqual(['110', '20'])
    expect(w.text()).toContain('0')
    expect(w.findAll('path')).toHaveLength(3)
  })

  it('medidor nas pontas: −100 e 100 (e fora da escala fica na ponta)', () => {
    let w = mount(MedidorNps, { props: { valor: -100 } })
    expect(w.get('[data-marcador]').attributes()).toMatchObject({ cx: '20', cy: '110' })
    expect(w.text()).toContain('−100')
    w = mount(MedidorNps, { props: { valor: 100, faixa: 'Excelente' } })
    expect(w.get('[data-marcador]').attributes()).toMatchObject({ cx: '200', cy: '110' })
    expect(w.attributes('aria-label')).toBe('NPS 100 numa escala de −100 a 100, faixa Excelente')
    w = mount(MedidorNps, { props: { valor: 140 } })
    expect(w.get('[data-marcador]').attributes()).toMatchObject({ cx: '200', cy: '110' })
  })

  it('temas: barra divergente, frase do leitor de tela, variação e nota; link só com respostas.ver', async () => {
    setActivePinia(createPinia())
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => h('div') } }] })
    const temas = painel().temas
    let w = mount(BlocoTemas, { props: { temas, consulta: { de: '2026-07-05' }, podeVerRespostas: true }, global: { plugins: [router] } })
    const linhas = w.findAll('[data-tema]')
    expect(linhas).toHaveLength(2)
    expect(linhas[0]!.text()).toContain('Prazo e entrega: 13 menções, 8 reclamações, nota média 6,2, 9 menções a mais que no período anterior')
    expect(linhas[0]!.text()).toContain('▲ 9')
    expect(linhas[0]!.text()).toContain('nota 6,2')
    expect(linhas[1]!.text()).toContain('▼ 4')
    // A seta das menções fica cinza: mais menções não é necessariamente ruim.
    for (const l of linhas) expect(l.get('[data-variacao-tema]').classes()).toEqual(['text-texto-suave'])
    expect(linhas[0]!.find('a').attributes('href')).toBe('/respostas?de=2026-07-05&tema=prazo_entrega')
    expect(w.text()).toContain('reclamação')
    expect(w.text()).toContain('outras menções')
    w = mount(BlocoTemas, { props: { temas, consulta: {}, podeVerRespostas: false }, global: { plugins: [router] } })
    expect(w.find('a').exists()).toBe(false)
    w = mount(BlocoTemas, { props: { temas: [], consulta: {}, podeVerRespostas: false }, global: { plugins: [router] } })
    expect(w.text()).toContain('Nenhum assunto encontrado')
  })

  it('tom: % de negativos, variação, barra com rótulo e legenda com contagens', () => {
    setActivePinia(createPinia())
    entrar(['painel.ver'])
    const w = mount(BlocoTom, { props: { tom: TOM, textoAnterior: 'os 90 dias antes' }, global: { stubs: { RouterLink: true } } })
    expect(w.text()).toContain('24 de 31 respostas vieram com comentário (77%).')
    expect(w.text()).toContain('46%')
    expect(w.text()).toContain('▲ 18 pontos')
    expect(w.text()).toContain('18 pontos a mais que no período anterior')
    expect(w.get('[role="img"]').attributes('aria-label')).toBe('Tom dos comentários: negativo 11; misto 3; neutro 2; positivo 8')
    expect(w.text()).toContain('Nos 90 dias antes, 28% eram negativos')
  })

  it('tom sem análises: "sendo analisados" com pendentes; convite com link só para quem administra; sem ler /conta/ia', async () => {
    setActivePinia(createPinia())
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => h('div') } }] })
    const { chamadas } = apiFalsa({})
    const vazio: TomComentarios = { ...TOM, analisados: 0, negativo: 0, misto: 0, neutro: 0, positivo: 0, anterior: null, pendentes: 0 }
    entrar(['painel.ver'])
    let w = mount(BlocoTom, { props: { tom: vazio, textoAnterior: 'os 90 dias antes' }, global: { plugins: [router] } })
    await flushPromises()
    expect(w.get('[data-tom-ligar]').text()).toBe('A análise por IA está desligada ou ainda não chegou a estes comentários.')
    expect(w.find('a').exists()).toBe(false)

    entrar(['painel.ver', 'configuracoes.gerenciar'])
    w = mount(BlocoTom, { props: { tom: vazio, textoAnterior: 'os 90 dias antes' }, global: { plugins: [router] } })
    await flushPromises()
    expect(w.get('[data-tom-ligar]').text()).toContain('Ligue a análise por IA em Configurações › IA para ver o tom')
    expect(w.get('[data-tom-ligar] a').attributes('href')).toBe('/configuracoes/ia')

    w = mount(BlocoTom, { props: { tom: { ...vazio, pendentes: 4 }, textoAnterior: 'os 90 dias antes' }, global: { plugins: [router] } })
    await flushPromises()
    expect(w.get('[data-tom-analisando]').text()).toContain('Os comentários ainda estão sendo analisados')

    w = mount(BlocoTom, { props: { tom: { ...vazio, com_comentario: 0 }, textoAnterior: 'x' }, global: { plugins: [router] } })
    expect(w.text()).toContain('Nenhum comentário neste período.')
    // O bloco não lê mais Configurações › IA.
    expect(chamadas.some((c) => c.caminho === '/conta/ia')).toBe(false)
  })

  it('tom reage à troca das props (troca de filtro): dados → fila → convite → dados', async () => {
    setActivePinia(createPinia())
    entrar(['painel.ver', 'configuracoes.gerenciar'])
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => h('div') } }] })
    const vazio: TomComentarios = { ...TOM, analisados: 0, negativo: 0, misto: 0, neutro: 0, positivo: 0, anterior: null }
    const w = mount(BlocoTom, { props: { tom: TOM, textoAnterior: 'os 90 dias antes' }, global: { plugins: [router] } })
    expect(w.text()).toContain('46%')
    await w.setProps({ tom: { ...vazio, pendentes: 2 } })
    expect(w.find('[data-tom-analisando]').exists()).toBe(true)
    expect(w.text()).not.toContain('46%')
    await w.setProps({ tom: { ...vazio, pendentes: 0 } })
    expect(w.find('[data-tom-analisando]').exists()).toBe(false)
    expect(w.find('[data-tom-ligar]').exists()).toBe(true)
    await w.setProps({ tom: { ...TOM, negativo: 6, analisados: 24 } })
    expect(w.find('[data-tom-ligar]').exists()).toBe(false)
    expect(w.text()).toContain('25%')
    expect(w.text()).toContain('▼ 3 pontos')
  })

  it('nuvem: tamanho por nível e contagem para leitor de tela', () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => h('div') } }] })
    const w = mount(BlocoPalavras, { props: { palavras: painel().palavras, consulta: {}, podeVerRespostas: true }, global: { plugins: [router] } })
    const itens = w.findAll('[data-nivel]')
    expect(itens.map((i) => i.attributes('data-nivel'))).toEqual(['4', '1'])
    expect(itens[0]!.classes()).toContain('text-3xl')
    expect(itens[0]!.text()).toBe('entrega: 12 comentários')
    expect(itens[0]!.attributes('href')).toBe('/respostas?busca=entrega')
  })

  it('empresas: régua do zero até o valor, valor mensal curto e NPS escrito', () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => h('div') } }] })
    const w = mount(BlocoEmpresas, { props: { empresas: painel().empresas, consulta: { tipo_nota: 'nps' }, podeVerRespostas: true }, global: { plugins: [router] } })
    const menor = w.get('[data-lista="menor"]')
    expect(menor.text()).toContain('3 respostas · R$ 48 mil/mês')
    expect(menor.text()).toContain('NPS −33')
    expect(menor.get('[data-regua] span').attributes('style')).toContain('left: 33.5%')
    expect(menor.get('[data-regua] span').classes()).toContain('bg-grafico-detrator')
    const maior = w.get('[data-lista="maior"]')
    expect(maior.text()).not.toContain('/mês')
    expect(maior.get('[data-regua] span').classes()).toContain('bg-grafico-promotor')
    expect(w.text()).toContain('Cuidar primeiro')
    expect(w.text()).toContain('Mais satisfeitas')
  })

  it('evolução com destaque: fundo do período, menor e maior marcados, tabela com a coluna do período', async () => {
    const pontos = meses12()!
    const w = mount(GraficoEvolucao, { props: { pontos, destaque: true } })
    expect(w.findAll('[data-extremo]')).toHaveLength(2)
    expect(w.text()).toContain('−36')
    expect(w.text()).toContain('57')
    expect(w.find('[data-periodo]').exists()).toBe(true)
    expect(w.get('[data-periodo] text').text()).toBe('Período')
    expect(w.get('[data-periodo] rect').classes()).toContain('fill-marca-suave')
    // O fundo do período vem antes de tudo (atrás da área, da grade e da linha).
    expect(w.get('svg').element.firstElementChild!.getAttribute('data-periodo')).not.toBeNull()
    expect(w.findAll('polygon').length).toBeGreaterThanOrEqual(1)
    // O mês sem resposta quebra a linha.
    expect(w.find('path').attributes('d')!.match(/M/g)).toHaveLength(2)
    expect(w.get('[role="group"]').attributes('aria-label')).toMatch(/Menor: −36 em .*; maior: 57 em/)
    // O menor mês (−36) fica no fundo da escala: o valor vai ao lado do ponto (não abaixo), longe do nome do mês.
    const menor = w.findAll('text').find((t) => t.text() === '−36')!
    const ponto = w.findAll('[data-extremo]').find((c) => c.classes().includes('stroke-grafico-detrator'))!
    expect(Number(menor.attributes('y'))).toBeLessThanOrEqual(Number(ponto.attributes('cy')) + 4)
    expect(menor.attributes('text-anchor')).toBe('end')
    // A área azul é recortada fora do período (as cores não se misturam).
    expect(w.get('polygon').attributes('clip-path')).toMatch(/^url\(#recorte-area-/)
    const mes = w.findAll('text').find((t) => /^[a-z]{3}\/\d{2}$/.test(t.text()))!
    expect(Number(mes.attributes('y')) - Number(menor.attributes('y'))).toBeGreaterThan(14)
    await w.setProps({ tabela: true })
    const linhas = w.findAll('tbody tr')
    expect(linhas).toHaveLength(12)
    expect(linhas[11]!.text()).toContain('Sim')
    expect(linhas[0]!.text()).toContain('Não')
  })
})

describe('receita gerada pelo Toqqi (melhoria 6)', () => {
  it('soma indicações que viraram cliente e ofertas aceitas, só para quem vê o Crescimento', async () => {
    entrar(['painel.ver', 'crescimento.ver'])
    apiFalsa({
      'GET /painel': () => painel(),
      'GET /crescimento/resumo': () => ({
        periodo: { de: HOJE, ate: HOJE },
        indicacoes: { recebidas: 5, clientes: 2, taxa: 40, receita_mensal: '3000.00' },
        ofertas: { feitas: 4, aceitas: 1, taxa: 25, receita: '1500.00' },
      }),
    })
    let w = await abrir()
    const c = w.get('[data-indicador="gerada"]')
    expect(c.text()).toContain('2 indicações viraram cliente · 1 oferta aceita')
    expect(c.find('a').attributes('href')).toBe('/crescimento')
    w.unmount()

    entrar(['painel.ver'])
    apiFalsa({ 'GET /painel': () => painel() })
    w = await abrir()
    expect(w.find('[data-indicador="gerada"]').exists()).toBe(false)
  })
})
