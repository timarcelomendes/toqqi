// O panorama do topo de Crescimento (docs/api-crescimento-panorama.md): as regras puras (período, receita e comparação,
// mês a mês, trilhas, próximos passos, quem mais indica) e o componente com a API simulada (os números, os links que
// levam à lista certa, o período, o vazio, a conta que ainda não começou, o erro e a recarga sem piscar).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import type { ConfigCrescimento, PanoramaCrescimento, Perfil } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import PanoramaView from '@/modulos/crescimento/PanoramaCrescimento.vue'
import {
  barrasMeses,
  detalheMes,
  enderecoDoDestino,
  ehPeriodoPanorama,
  intervaloPanorama,
  mesCurto,
  mesLongo,
  moedaCurta,
  moedaInteira,
  origemReceita,
  partesReceita,
  periodoAnterior,
  periodoAtual,
  proximosPassos,
  quemMaisIndica,
  temMovimento,
  textoNota,
  trilhaIndicacoes,
  trilhaOfertas,
  variacaoReceita,
} from '@/modulos/crescimento/panorama'
import { apiFalsa, type Chamada } from './apiFalsa'

const t = (s: string) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim()

/** Os textos de um elemento separados por espaço (os pedaços são caixas separadas na tela, sem espaço no HTML). */
function textos(alvo: { element: Element }): string {
  const partes: string[] = []
  const passeio = document.createTreeWalker(alvo.element, NodeFilter.SHOW_TEXT)
  for (let n = passeio.nextNode(); n; n = passeio.nextNode()) {
    const s = t(n.textContent ?? '')
    if (s) partes.push(s)
  }
  return partes.join(' ')
}

/** Os 12 meses ("2025-11"…"2026-10") que terminam no mês de `hoje`, com o valor de cada um (do mais antigo). */
function meses(hoje: string, valores: number[] = []): PanoramaCrescimento['meses'] {
  const [a, m] = hoje.split('-').map(Number) as [number, number]
  return Array.from({ length: 12 }, (_, i) => {
    const n = a * 12 + (m - 1) - (11 - i)
    const mes = `${Math.floor(n / 12)}-${String((n % 12) + 1).padStart(2, '0')}`
    const total = valores[i] ?? 0
    return { mes, indicacoes: total, ofertas: 0, total }
  })
}

function panorama(extra: Partial<PanoramaCrescimento> = {}, hoje = hojeIso()): PanoramaCrescimento {
  return {
    periodo: { de: '2026-07-11', ate: '2026-10-08' },
    anterior: { de: '2026-04-12', ate: '2026-07-10' },
    receita: { total: '23650.00', indicacoes: '20880.00', ofertas: '2770.00', anterior: '8700.00' },
    indicacoes: { promotores: 30, recebidas: 20, novas: 4, em_contato: 6, clientes: 7, nao_avancou: 3, abordadas: 16, esperando_contato: 5 },
    ofertas: { feitas: 10, aceitas: 4, recusadas: 2, sem_resposta: 1, aguardando: 3, prontas: 6, sem_oferta: 1 },
    fas: [
      { empresa: { id: 1, nome: 'Rede Compre Bem' }, indicacoes: 6, clientes: 3, receita_mensal: '12400.00' },
      { empresa: { id: 2, nome: 'Atacadão do Vale' }, indicacoes: 4, clientes: 1, receita_mensal: '4100.00' },
      { empresa: { id: 5, nome: 'Empório Bela Vista' }, indicacoes: 2, clientes: 0, receita_mensal: 0 },
    ],
    depoimentos: {
      aprovados: 4,
      pendentes: 2,
      destaque: {
        resposta_id: 99,
        comentario: 'A entrega chega sempre no horário e a equipe liga antes quando falta algum item.',
        assinatura: 'Juliana, Supermercado Ideal',
        nota: 10,
        tipo_nota: 'nps',
        data_resposta: '2026-10-02T12:00:00-03:00',
      },
    },
    meses: meses(hoje, [0, 0, 0, 0, 0, 0, 2300, 6400, 1500, 3720, 18430, 0]),
    tem_historico: true,
    ...extra,
  }
}

// ── Regras ──────────────────────────────────────────────────────────────────

describe('Crescimento › panorama: regras', () => {
  it('período: 30, 90 ou 365 dias terminando hoje, e as frases', () => {
    expect(intervaloPanorama('30', '2026-10-08')).toEqual({ de: '2026-09-09', ate: '2026-10-08' })
    expect(intervaloPanorama('90', '2026-10-08')).toEqual({ de: '2026-07-11', ate: '2026-10-08' })
    expect(intervaloPanorama('365', '2026-10-08')).toEqual({ de: '2025-10-09', ate: '2026-10-08' })
    expect([periodoAtual('30'), periodoAtual('365'), periodoAnterior('90'), periodoAnterior('365')]).toEqual([
      'nos últimos 30 dias',
      'nos últimos 12 meses',
      'nos 90 dias anteriores',
      'nos 12 meses anteriores',
    ])
    expect([ehPeriodoPanorama('90'), ehPeriodoPanorama('7'), ehPeriodoPanorama(90)]).toEqual([true, false, false])
  })

  it('receita: o número grande em partes, o valor curto e o inteiro', () => {
    expect(partesReceita('23650.00')).toEqual({ numero: '23,7', sufixo: 'mil' })
    expect(partesReceita(850)).toEqual({ numero: '850', sufixo: '' })
    expect(partesReceita(null)).toEqual({ numero: '0', sufixo: '' })
    expect(partesReceita('1250000')).toEqual({ numero: '1,3', sufixo: 'mi' })
    expect([moedaCurta(14950), moedaCurta(1000), moedaCurta(850.4), moedaCurta(0)]).toEqual(['R$ 15 mil', 'R$ 1 mil', 'R$ 850', 'R$ 0'])
    expect(t(moedaInteira('23650.00'))).toBe('R$ 23.650,00')
  })

  it('comparação com o período anterior: subiu, caiu, igual; sem anterior ou com tudo zerado, nada', () => {
    const p = panorama()
    expect(variacaoReceita(p, '90')).toEqual({ texto: 'R$ 15 mil a mais que nos 90 dias anteriores', sentido: 'subiu' })
    expect(variacaoReceita({ ...p, receita: { ...p.receita, total: 500, anterior: 1500 } }, '30')).toEqual({
      texto: 'R$ 1 mil a menos que nos 30 dias anteriores',
      sentido: 'caiu',
    })
    expect(variacaoReceita({ ...p, receita: { ...p.receita, total: '700.00', anterior: 700 } }, '365')).toEqual({
      texto: 'O mesmo que nos 12 meses anteriores',
      sentido: 'igual',
    })
    expect(variacaoReceita({ ...p, receita: { ...p.receita, anterior: null } }, '90')).toBeNull()
    expect(variacaoReceita({ ...p, receita: { total: 0, indicacoes: 0, ofertas: 0, anterior: 0 } }, '90')).toBeNull()
  })

  it('de onde veio a receita', () => {
    const p = panorama()
    expect(origemReceita(p)).toBe('7 indicações viraram cliente e 4 ofertas foram aceitas.')
    expect(origemReceita({ ...p, indicacoes: { ...p.indicacoes, clientes: 1 }, ofertas: { ...p.ofertas, aceitas: 0 } })).toBe('1 indicação virou cliente.')
    expect(origemReceita({ ...p, indicacoes: { ...p.indicacoes, clientes: 0 }, ofertas: { ...p.ofertas, aceitas: 1 } })).toBe('1 oferta foi aceita.')
    expect(origemReceita({ ...p, indicacoes: { ...p.indicacoes, clientes: 0 }, ofertas: { ...p.ofertas, aceitas: 0 } })).toBe(
      'Nenhuma indicação virou cliente e nenhuma oferta foi aceita no período.',
    )
  })

  it('mês a mês: em destaque os meses do período, o mês de hoje marcado, altura pelo maior mês', () => {
    const p = panorama({}, '2026-10-08')
    const b90 = barrasMeses(p, '90', '2026-10-08')
    expect(b90.map((b) => b.mes)).toEqual([
      '2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10',
    ])
    expect(b90.filter((b) => b.noPeriodo).map((b) => b.mes)).toEqual(['2026-07', '2026-08', '2026-09', '2026-10'])
    expect(barrasMeses(p, '30', '2026-10-08').filter((b) => b.noPeriodo).map((b) => b.mes)).toEqual(['2026-09', '2026-10'])
    expect(barrasMeses(p, '365', '2026-10-08').every((b) => b.noPeriodo)).toBe(true)
    expect(b90.filter((b) => b.atual).map((b) => b.mes)).toEqual(['2026-10'])
    expect(b90.map((b) => b.altura)).toEqual([0, 0, 0, 0, 0, 0, 12, 35, 8, 20, 100, 0])
    // um mês bem pequeno ainda aparece
    const pequeno = barrasMeses({ ...p, meses: meses('2026-10-08', [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1000]) }, '90', '2026-10-08')
    expect([pequeno[0]!.altura, pequeno[11]!.altura]).toEqual([3, 100])
    expect([mesCurto('2026-10'), mesCurto('2025-01'), mesLongo('2026-03'), mesLongo('2026-12')]).toEqual(['out/26', 'jan/25', 'março de 2026', 'dezembro de 2026'])
    const set = { ...b90[10]!, indicacoes: 16580, ofertas: 1850 }
    expect(t(detalheMes(set))).toBe('R$ 16.580,00 de indicações e R$ 1.850,00 de ofertas')
    expect(t(detalheMes({ ...set, indicacoes: 0 }))).toBe('R$ 1.850,00 de ofertas')
  })

  it('trilha do promotor ao cliente: larguras pela maior etapa, as taxas e só os números que a lista mostra igual levam a ela', () => {
    const e = trilhaIndicacoes(panorama(), '90')
    expect(e.map((x) => [x.chave, x.valor, x.rotulo, x.detalhe, x.largura, x.resultado])).toEqual([
      ['promotores', 30, 'Promotores', 'notas 9 e 10', 100, false],
      ['recebidas', 20, 'Indicações recebidas', null, 67, false],
      ['abordadas', 16, 'Abordadas', '80% das indicações', 53, false],
      ['clientes', 7, 'Viraram cliente', '35% das indicações', 23, true],
    ])
    expect(e.map((x) => x.destino)).toEqual([
      null,
      { aba: 'indicacoes', query: { periodo: '90' } },
      null,
      { aba: 'indicacoes', query: { periodo: '90', situacao: 'cliente' } },
    ])
    // singular, zero e a barra mínima
    const p = panorama({ indicacoes: { promotores: 1, recebidas: 1, novas: 0, em_contato: 0, clientes: 0, nao_avancou: 1, abordadas: 1, esperando_contato: 0 } })
    expect(trilhaIndicacoes(p, '30').map((x) => [x.rotulo, x.largura, x.detalhe])).toEqual([
      ['Promotor', 100, 'notas 9 e 10'],
      ['Indicação recebida', 100, null],
      ['Abordada', 100, '100% das indicações'],
      ['Viraram cliente', 0, '0% das indicações'],
    ])
    const muitos = panorama({ indicacoes: { promotores: 500, recebidas: 3, novas: 3, em_contato: 0, clientes: 0, nao_avancou: 0, abordadas: 0, esperando_contato: 3 } })
    expect(trilhaIndicacoes(muitos, '90').map((x) => x.largura)).toEqual([100, 2, 0, 0])
    const vazia = panorama({ indicacoes: { promotores: 0, recebidas: 0, novas: 0, em_contato: 0, clientes: 0, nao_avancou: 0, abordadas: 0, esperando_contato: 0 } })
    expect(trilhaIndicacoes(vazia, '90').map((x) => [x.largura, x.detalhe])).toEqual([
      [0, 'notas 9 e 10'],
      [0, null],
      [0, null],
      [0, null],
    ])
  })

  it('trilha das ofertas: quantas sem resultado e a taxa das aceitas, sem link', () => {
    expect(trilhaOfertas(panorama()).map((x) => [x.rotulo, x.valor, x.detalhe, x.largura, x.resultado, x.destino])).toEqual([
      ['Ofertas feitas', 10, '3 sem resultado', 100, false, null],
      ['Aceitas', 4, '40% das feitas', 40, true, null],
    ])
    const p = panorama({ ofertas: { feitas: 1, aceitas: 1, recusadas: 0, sem_resposta: 0, aguardando: 0, prontas: 0, sem_oferta: 0 } })
    expect(trilhaOfertas(p).map((x) => [x.rotulo, x.detalhe])).toEqual([
      ['Oferta feita', null],
      ['Aceita', '100% das feitas'],
    ])
  })

  it('próximos passos: o convite desligado primeiro, depois quem espera contato, os sem oferta e os depoimentos (até 3)', () => {
    const p = panorama()
    expect(proximosPassos(p).map((x) => [x.chave, x.quantidade, x.texto, x.acao, enderecoDoDestino(x.destino)])).toEqual([
      ['esperando', 5, 'indicações esperando o primeiro contato', 'Ver as indicações', { name: 'crescimento', params: { aba: 'indicacoes' }, query: { situacao: 'nova' } }],
      ['sem_oferta', 1, 'cliente feliz ainda sem oferta', 'Ver as oportunidades', { name: 'crescimento', params: { aba: 'oportunidades' }, query: {} }],
      ['depoimentos', 2, 'depoimentos esperando a sua aprovação', 'Revisar os depoimentos', { name: 'crescimento', params: { aba: 'depoimentos' }, query: {} }],
    ])
    const comConvite = proximosPassos(p, { conviteDesligado: true, podeConfigurar: true })
    expect(comConvite.map((x) => x.chave)).toEqual(['convite', 'esperando', 'sem_oferta'])
    expect(comConvite[0]).toMatchObject({ quantidade: null, acao: 'Ligar o convite', destino: { caminho: '/configuracoes/crescimento' } })
    expect(enderecoDoDestino(comConvite[0]!.destino)).toBe('/configuracoes/crescimento')
    expect(proximosPassos(p, { conviteDesligado: true })[0]!.acao).toBe('Ver o convite')
    const um = panorama({
      indicacoes: { ...p.indicacoes, esperando_contato: 1 },
      ofertas: { ...p.ofertas, sem_oferta: 2 },
      depoimentos: { ...p.depoimentos, pendentes: 1 },
    })
    expect(proximosPassos(um).map((x) => [x.texto, x.acao])).toEqual([
      ['indicação esperando o primeiro contato', 'Ver a indicação'],
      ['clientes felizes ainda sem oferta', 'Ver as oportunidades'],
      ['depoimento esperando a sua aprovação', 'Revisar o depoimento'],
    ])
    const nada = panorama({
      indicacoes: { ...p.indicacoes, esperando_contato: 0 },
      ofertas: { ...p.ofertas, sem_oferta: 0 },
      depoimentos: { ...p.depoimentos, pendentes: 0 },
    })
    expect(proximosPassos(nada)).toEqual([])
  })

  it('quem mais indica: a barra pela maior, a parte que virou cliente e o detalhe', () => {
    expect(quemMaisIndica(panorama()).map((f) => [f.nome, f.indicacoes, f.largura, f.parteClientes, f.detalhe])).toEqual([
      ['Rede Compre Bem', 6, 100, 50, '3 viraram cliente, R$ 12,4 mil/mês'],
      ['Atacadão do Vale', 4, 67, 25, '1 virou cliente, R$ 4,1 mil/mês'],
      ['Empório Bela Vista', 2, 33, 0, 'Nenhuma virou cliente'],
    ])
    const semValor = panorama({ fas: [{ empresa: { id: 3, nome: 'Café Central' }, indicacoes: 1, clientes: 1, receita_mensal: 0 }] })
    expect(quemMaisIndica(semValor)[0]).toMatchObject({ largura: 100, parteClientes: 100, detalhe: '1 virou cliente' })
  })

  it('a nota do depoimento e se há movimento no período', () => {
    expect([textoNota(10, 'nps'), textoNota(5, 'csat'), textoNota(null, 'nps')]).toEqual(['Nota 10', 'Nota 5 de 5', null])
    const p = panorama()
    expect(temMovimento(p)).toBe(true)
    expect(temMovimento({ ...p, indicacoes: { ...p.indicacoes, promotores: 0, recebidas: 0 }, ofertas: { ...p.ofertas, feitas: 0 } })).toBe(false)
    expect(temMovimento({ ...p, indicacoes: { ...p.indicacoes, promotores: 0, recebidas: 0 }, ofertas: { ...p.ofertas, feitas: 1 } })).toBe(true)
  })
})

// ── Componente ──────────────────────────────────────────────────────────────

const TODAS = ['crescimento.ver', 'crescimento.tratar', 'contatos.ver', 'configuracoes.gerenciar', 'envios.ver']
const CONFIG: ConfigCrescimento = { indicacoes_ativas: true, titulo_convite: 'Oi', texto_convite: 'Indique', recompensa: null, texto_oferta: 'Olá' }

function entrar(permissoes: string[] = TODAS, perfil: Perfil = 'admin') {
  useSessaoStore().definirSessao(
    {
      token: 't',
      expira_em: '2099-01-01T00:00:00Z',
      usuario: { id: 1, nome: 'Marina Lopes', email: 'marina@aurora.com.br', cargo: null, perfil, situacao: 'ativo', email_confirmado: true, ultimo_acesso: null, superadmin: false },
      conta: { id: 1, nome: 'Distribuidora Aurora', plano: null, situacao: 'ativa', teste_ate: null },
      permissoes,
    },
    false,
  )
}

let router: Router
async function montar(
  resposta: (c: Chamada) => unknown = () => panorama(),
  opcoes: { permissoes?: string[]; config?: ConfigCrescimento | null } = {},
): Promise<{ w: VueWrapper; chamadas: Chamada[] }> {
  entrar(opcoes.permissoes)
  const { chamadas } = apiFalsa({ 'GET /crescimento/panorama': resposta })
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/crescimento/:aba', name: 'crescimento', component: { render: () => null } },
      { path: '/:qualquer(.*)*', component: { render: () => null } },
    ],
  })
  await router.push('/crescimento/indicacoes')
  await router.isReady()
  const w = mount(PanoramaView, { props: { config: opcoes.config === undefined ? CONFIG : opcoes.config }, global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { w, chamadas }
}

const consulta = (c: Chamada | undefined) => Object.fromEntries(c?.url.searchParams ?? [])
const pedidos = (chamadas: Chamada[]) => chamadas.filter((c) => c.metodo === 'GET' && c.caminho === '/crescimento/panorama')
const href = (w: VueWrapper, sel: string) => w.get(sel).attributes('href')

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  localStorage.clear()
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('Crescimento › panorama: componente', () => {
  it('mostra a receita (com a comparação e o mês a mês), as trilhas, os próximos passos, quem mais indica e o depoimento', async () => {
    const { w, chamadas } = await montar()
    expect(consulta(pedidos(chamadas)[0])).toEqual(intervaloPanorama('90', hojeIso()))

    expect(textos(w.get('[data-receita]'))).toBe('R$ 23,7 mil /mês R$ 23.650,00 por mês')
    expect(t(w.get('[data-origem]').text())).toBe('7 indicações viraram cliente e 4 ofertas foram aceitas.')
    expect(t(w.get('[data-variacao]').text())).toBe('R$ 15 mil a mais que nos 90 dias anteriores')
    expect(w.get('[data-variacao]').classes()).toContain('text-sucesso')

    // trilha das indicações: valores, barras (o resultado em destaque) e só dois links
    const etapa = (c: string) => w.get(`[data-etapa="${c}"]`)
    expect(['promotores', 'recebidas', 'abordadas', 'clientes'].map((c) => textos(etapa(c)))).toEqual([
      'Promotores notas 9 e 10 30',
      'Indicações recebidas 20 , ver na lista',
      'Abordadas 80% das indicações 16',
      'Viraram cliente 35% das indicações 7 , ver na lista',
    ])
    expect(etapa('promotores').get('[data-barra]').attributes('style')).toContain('width: 100%')
    expect(etapa('clientes').get('[data-barra]').attributes('style')).toContain('width: 23%')
    expect(etapa('clientes').get('[data-barra]').classes()).toContain('bg-marca')
    expect(etapa('promotores').get('[data-barra]').classes()).toContain('bg-grafico-cinza')
    expect(etapa('promotores').find('a').exists()).toBe(false)
    expect(etapa('abordadas').find('a').exists()).toBe(false)
    expect(href(w, '[data-etapa="recebidas"] a')).toBe('/crescimento/indicacoes?periodo=90')
    expect(href(w, '[data-etapa="clientes"] a')).toBe('/crescimento/indicacoes?periodo=90&situacao=cliente')
    expect(textos(w.get('[data-trilha="indicacoes"] [data-receita-trilha]'))).toBe('R$ 20,9 mil /mês Receita: R$ 20.880,00 por mês')
    expect(textos(w.get('[data-trilha="ofertas"]'))).toContain('Ofertas feitas 3 sem resultado 10')
    expect(w.find('[data-trilha="ofertas"] a').exists()).toBe(false)

    // próximos passos
    expect(w.findAll('[data-passo]').map((p) => [p.attributes('data-passo'), textos(p), p.attributes('href')])).toEqual([
      ['esperando', '5 indicações esperando o primeiro contato Ver as indicações', '/crescimento/indicacoes?situacao=nova'],
      ['sem_oferta', '1 cliente feliz ainda sem oferta Ver as oportunidades', '/crescimento/oportunidades'],
      ['depoimentos', '2 depoimentos esperando a sua aprovação Revisar os depoimentos', '/crescimento/depoimentos'],
    ])

    // quem mais indica: o nome leva à empresa; a legenda diz o que é cada cor
    const fas = w.findAll('[data-fa]')
    expect(fas.map((f) => textos(f))).toEqual([
      'Rede Compre Bem 6 indicações 3 viraram cliente, R$ 12,4 mil/mês',
      'Atacadão do Vale 4 indicações 1 virou cliente, R$ 4,1 mil/mês',
      'Empório Bela Vista 2 indicações Nenhuma virou cliente',
    ])
    expect(fas[0]!.get('a').attributes('href')).toBe('/contatos/empresas/1')
    expect(textos(w.get('[data-legenda]'))).toBe('Viraram cliente As outras')

    // o depoimento mais recente
    const dep = textos(w.get('[data-depoimento-destaque]'))
    expect(dep).toContain('A entrega chega sempre no horário e a equipe liga antes quando falta algum item.')
    expect(dep).toContain('Juliana, Supermercado Ideal Nota 10, em 02/10/2026')
    expect(dep).toContain('Ver os depoimentos 4 aprovados')

    // mês a mês: 12 barras, os meses do período em destaque e a tabela para leitores de tela
    const barras = w.findAll('[data-meses] [data-mes]')
    expect(barras).toHaveLength(12)
    const inicio = intervaloPanorama('90', hojeIso()).de.slice(0, 7)
    const destaque = barras.filter((b) => b.classes().some((c) => c.startsWith('bg-marca')))
    expect(destaque.map((b) => b.attributes('data-mes'))).toEqual(barras.map((b) => b.attributes('data-mes')!).filter((m) => m >= inicio))
    const linhas = w.findAll('[data-meses] table tbody tr')
    expect(linhas).toHaveLength(12)
    expect(textos(linhas[11]!)).toMatch(/\(até hoje\) R\$ 0,00$/)
  })

  it('passar o mouse num mês mostra a dica com o valor inteiro e de onde veio', async () => {
    const { w } = await montar()
    const barras = w.findAll('[data-meses] [data-mes]')
    await barras[10]!.element.parentElement!.dispatchEvent(new Event('pointerenter'))
    await flushPromises()
    const mes = barras[10]!.attributes('data-mes')!
    expect(textos(w.get('[data-dica-mes]'))).toBe(`${mesLongo(mes)} R$ 18.430,00/mês R$ 18.430,00 de indicações`)
    expect(w.get('[data-dica-mes]').classes()).toContain('right-0') // perto da borda direita, não sai do cartão
    await barras[11]!.element.parentElement!.dispatchEvent(new Event('pointerenter'))
    await flushPromises()
    expect(textos(w.get('[data-dica-mes]'))).toBe(`${mesLongo(barras[11]!.attributes('data-mes')!)}, até hoje R$ 0,00/mês`)
    await barras[11]!.element.parentElement!.parentElement!.dispatchEvent(new Event('pointerleave'))
    await flushPromises()
    expect(w.find('[data-dica-mes]').exists()).toBe(false)
  })

  it('trocar o período busca de novo (os números antigos ficam apagados até chegar) e avisa o novo total', async () => {
    let soltar: (() => void) | null = null
    const { w, chamadas } = await montar(async (c) => {
      if (c.url.searchParams.get('de') === intervaloPanorama('365', hojeIso()).de) {
        await new Promise<void>((r) => (soltar = r))
        return panorama({ receita: { total: 32400, indicacoes: 26100, ofertas: 6300, anterior: 0 } })
      }
      return panorama()
    })
    await w.get('input[type="radio"][value="365"]').setValue()
    await flushPromises()
    expect(consulta(pedidos(chamadas).at(-1))).toEqual(intervaloPanorama('365', hojeIso()))
    expect(w.get('[data-panorama-principal]').classes()).toContain('opacity-60')
    expect(w.get('[data-panorama]').attributes('aria-busy')).toBe('true')
    // enquanto não chega, os links seguem com o período dos números na tela
    expect(href(w, '[data-etapa="clientes"] a')).toBe('/crescimento/indicacoes?periodo=90&situacao=cliente')
    soltar!()
    await flushPromises()
    expect(w.get('[data-panorama-principal]').classes()).not.toContain('opacity-60')
    expect(textos(w.get('[data-receita]'))).toBe('R$ 32,4 mil /mês R$ 32.400,00 por mês')
    expect(t(w.get('[data-variacao]').text())).toBe('R$ 32,4 mil a mais que nos 12 meses anteriores')
    expect(t(w.get('[aria-live="polite"]').text())).toBe('Receita gerada pelo Toqqi nos últimos 12 meses: R$ 32.400,00 por mês.')
    expect(href(w, '[data-etapa="clientes"] a')).toBe('/crescimento/indicacoes?periodo=365&situacao=cliente')
  })

  it('trocar o período e a busca falhar: os números de antes ficam, com o aviso e "Tentar de novo"', async () => {
    let falhar = true
    const { w, chamadas } = await montar((c) => {
      if (c.url.searchParams.get('de') === intervaloPanorama('30', hojeIso()).de && falhar) {
        falhar = false
        return new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Fora do ar.' } }), { status: 503 })
      }
      return panorama()
    })
    await w.get('input[type="radio"][value="30"]').setValue()
    await flushPromises()
    expect(textos(w.get('[data-erro-atualizar]'))).toContain('Não deu para atualizar o panorama')
    expect(textos(w.get('[data-receita]'))).toContain('R$ 23,7 mil') // os de antes
    expect(href(w, '[data-etapa="clientes"] a')).toBe('/crescimento/indicacoes?periodo=90&situacao=cliente')
    await w.findAll('[data-erro-atualizar] button')[0]!.trigger('click')
    await flushPromises()
    expect(consulta(pedidos(chamadas).at(-1))).toEqual(intervaloPanorama('30', hojeIso()))
    expect(w.find('[data-erro-atualizar]').exists()).toBe(false)
    expect(href(w, '[data-etapa="clientes"] a')).toBe('/crescimento/indicacoes?periodo=30&situacao=cliente')
  })

  it('um número ou passo que leva a uma aba avisa a tela (ela rola até a lista); o convite e a empresa, não', async () => {
    const { w } = await montar(() => panorama(), { config: { ...CONFIG, indicacoes_ativas: false } })
    await w.get('[data-etapa="clientes"] a').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/indicacoes?periodo=90&situacao=cliente')
    expect(w.emitted('irParaLista')).toHaveLength(1)
    await w.get('[data-passo="esperando"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/crescimento/indicacoes?situacao=nova')
    expect(w.emitted('irParaLista')).toHaveLength(2)
    await w.get('[data-passo="convite"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/configuracoes/crescimento')
    expect(w.emitted('irParaLista')).toHaveLength(2)
  })

  it('o convite desligado vira o primeiro passo ("Ligar o convite" para o administrador, "Ver o convite" para os outros)', async () => {
    const desligado = { ...CONFIG, indicacoes_ativas: false }
    let { w } = await montar(() => panorama(), { config: desligado })
    expect(w.findAll('[data-passo]').map((p) => p.attributes('data-passo'))).toEqual(['convite', 'esperando', 'sem_oferta'])
    expect(textos(w.get('[data-passo="convite"]'))).toBe(
      'O convite de indicação está desligado: quem dá nota 9 ou 10 não recebe o pedido para indicar. Ligar o convite',
    )
    w.unmount()
    ;({ w } = await montar(() => panorama(), { config: desligado, permissoes: ['crescimento.ver'] }))
    expect(textos(w.get('[data-passo="convite"]'))).toMatch(/Ver o convite$/)
    // sem contatos.ver, o nome da empresa não é link
    expect(w.get('[data-fa]').find('a').exists()).toBe(false)
    w.unmount()
    // configuração ainda não chegou (ou falhou): não fala no convite
    ;({ w } = await montar(() => panorama(), { config: null }))
    expect(w.find('[data-passo="convite"]').exists()).toBe(false)
  })

  it('período sem movimento: o aviso, "Ver os últimos 12 meses" e os vazios de quem indica e do depoimento', async () => {
    const parado = panorama({
      receita: { total: 0, indicacoes: 0, ofertas: 0, anterior: 3000 },
      indicacoes: { promotores: 0, recebidas: 0, novas: 0, em_contato: 0, clientes: 0, nao_avancou: 0, abordadas: 0, esperando_contato: 0 },
      ofertas: { feitas: 0, aceitas: 0, recusadas: 0, sem_resposta: 0, aguardando: 0, prontas: 0, sem_oferta: 0 },
      fas: [],
      depoimentos: { aprovados: 0, pendentes: 0, destaque: null },
    })
    const { w, chamadas } = await montar(() => parado)
    expect(textos(w.get('[data-receita]'))).toBe('R$ 0 /mês R$ 0,00 por mês')
    expect(t(w.get('[data-origem]').text())).toBe('Nenhuma indicação virou cliente e nenhuma oferta foi aceita no período.')
    expect(t(w.get('[data-variacao]').text())).toBe('R$ 3 mil a menos que nos 90 dias anteriores')
    expect(w.get('[data-variacao]').classes()).toContain('text-atencao')
    expect(w.find('[data-trilha]').exists()).toBe(false)
    expect(textos(w.get('[data-sem-movimento]'))).toContain('Nenhum promotor, indicação ou oferta nos últimos 90 dias.')
    expect(w.find('[data-proximos-passos]').exists()).toBe(false)
    expect(t(w.get('[data-fas-vazio]').text())).toContain('Ninguém indicou outra empresa nos últimos 90 dias.')
    expect(w.find('[data-legenda]').exists()).toBe(false)
    expect(w.find('[data-depoimento-vazio]').exists()).toBe(true)
    expect(textos(w.get('[data-depoimento-destaque]'))).not.toContain('aprovados')

    const ver = w.findAll('button').find((b) => t(b.text()) === 'Ver os últimos 12 meses')!
    await ver.trigger('click')
    await flushPromises()
    expect(consulta(pedidos(chamadas).at(-1))).toEqual(intervaloPanorama('365', hojeIso()))
    expect((w.get('input[type="radio"][value="365"]').element as HTMLInputElement).checked).toBe(true)
    // em 12 meses, sem o botão
    expect(w.findAll('button').some((b) => t(b.text()) === 'Ver os últimos 12 meses')).toBe(false)
  })

  it('conta que ainda não começou: como funciona e os botões certos para cada um', async () => {
    const novo = () => panorama({ tem_historico: false, fas: [], depoimentos: { aprovados: 0, pendentes: 0, destaque: null } })
    let { w } = await montar(novo, { config: { ...CONFIG, indicacoes_ativas: false } })
    expect(w.find('[data-panorama-principal]').exists()).toBe(false)
    expect(w.find('[data-fas]').exists()).toBe(false)
    const comecar = w.get('[data-comecar]')
    expect(t(comecar.get('h3').text())).toBe('Aqui aparece o que seus clientes felizes trazem')
    expect(comecar.findAll('ol[aria-label="Como funciona"] li')).toHaveLength(4)
    expect(comecar.findAll('a').map((a) => [t(a.text()), a.attributes('href')])).toEqual([
      ['Ligar o convite de indicação', '/configuracoes/crescimento'],
      ['Enviar uma pesquisa', '/envios'],
    ])
    w.unmount()
    // sem poder configurar nem enviar: o pedido ao administrador e nenhum botão
    ;({ w } = await montar(novo, { config: { ...CONFIG, indicacoes_ativas: false }, permissoes: ['crescimento.ver'] }))
    expect(w.get('[data-comecar]').findAll('a')).toHaveLength(0)
    expect(t(w.get('[data-pedir-admin]').text())).toBe('O convite de indicação está desligado. Peça a um administrador para ligar em Configurações › Crescimento.')
    w.unmount()
    // convite ligado: só "Enviar uma pesquisa", como botão principal
    ;({ w } = await montar(novo))
    const links = w.get('[data-comecar]').findAll('a')
    expect(links.map((a) => t(a.text()))).toEqual(['Enviar uma pesquisa'])
    expect(links[0]!.classes()).toContain('bg-marca-forte')
    expect(w.find('[data-pedir-admin]').exists()).toBe(false)
  })

  it('erro: o aviso com "Tentar de novo"; depois, recarregar() atualiza sem piscar e uma falha nela não apaga a tela', async () => {
    let vez = 0
    const { w, chamadas } = await montar(() => {
      vez += 1
      if (vez === 1 || vez === 4) return new Response(JSON.stringify({ erro: { codigo: 'erro', mensagem: 'Falhou aqui.' } }), { status: 500 })
      return vez === 2 ? panorama() : panorama({ receita: { total: 30000, indicacoes: 30000, ofertas: 0, anterior: 8700 } })
    })
    expect(t(w.text())).toContain('Não deu para carregar o panorama')
    const tentar = w.findAll('button').find((b) => t(b.text()) === 'Tentar de novo')!
    await tentar.trigger('click')
    await flushPromises()
    expect(textos(w.get('[data-receita]'))).toContain('R$ 23,7 mil')

    const vm = w.vm as unknown as { recarregar: () => Promise<void> }
    const pronto = vm.recarregar()
    expect(w.get('[data-panorama-principal]').classes()).not.toContain('opacity-60')
    await pronto
    await flushPromises()
    expect(textos(w.get('[data-receita]'))).toContain('R$ 30 mil')
    expect(t(w.get('[aria-live="polite"]').text())).toBe('') // recarga silenciosa não fala
    await vm.recarregar()
    await flushPromises()
    expect(pedidos(chamadas)).toHaveLength(4)
    expect(textos(w.get('[data-receita]'))).toContain('R$ 30 mil')
    expect(t(w.text())).not.toContain('Não deu para carregar')
  })
})
