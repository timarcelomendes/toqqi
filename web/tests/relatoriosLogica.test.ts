import { describe, expect, it } from 'vitest'
import type { SemanaTemas } from '@/api/tipos'
import { somarDias } from '@/utils/periodo'
import {
  ABAS_RELATORIO,
  ABA_PADRAO,
  agruparPorMes,
  comunsParaApi,
  consultaDaAba,
  consultaRespostas,
  contarFiltrosDaAba,
  corDoTema,
  descreverTempoCliente,
  ehAba,
  ehQuadrante,
  empresasParaApi,
  entregasParaApi,
  escalaContagem,
  escalaLog,
  filtrosDaQuery,
  filtrosPadrao,
  formatarMoedaCurta,
  gruposParaApi,
  mesDaData,
  mesesCompletos,
  mesmaBusca,
  nomeDoCampo,
  numero,
  partesMoedaCurta,
  partesSentimento,
  periodoParaApi,
  posicionarRotulos,
  queryDosFiltros,
  rotuloAba,
  rotuloSemana,
  seriesSemanais,
  type FiltrosRelatorioTela,
} from '@/modulos/relatorios/logica'

const HOJE = '2026-10-01'
const f = (aba: Parameters<typeof filtrosPadrao>[0], extra: Partial<FiltrosRelatorioTela> = {}): FiltrosRelatorioTela => ({ ...filtrosPadrao(aba), ...extra })

describe('abas', () => {
  it('são 7, na ordem do contrato, com Empresas como padrão', () => {
    expect(ABAS_RELATORIO.map((a) => a.valor)).toEqual(['empresas', 'grupos', 'temas', 'entregas', 'responsaveis', 'operacao', 'historico'])
    expect(ABA_PADRAO).toBe('empresas')
    expect(ehAba('temas')).toBe(true)
    expect(ehAba('vendas')).toBe(false)
    expect(ehAba(undefined)).toBe(false)
    expect(rotuloAba('historico')).toBe('Histórico de uma empresa')
  })
})

describe('filtros ↔ endereço (URL)', () => {
  it('sem nada no endereço: 90 dias, só empresas ativas; no histórico, todo o período', () => {
    const e = filtrosDaQuery('empresas', {})
    expect(e.periodo).toBe('90')
    expect(e.so_ativos).toBe(true)
    expect(e.ordem).toBe('prioridade')
    expect(filtrosDaQuery('historico', {}).periodo).toBe('tudo')
    expect(filtrosDaQuery('entregas', {}).ordem).toBe('respostas')
    expect(filtrosDaQuery('entregas', {}).dimensao).toBe('motorista')
    for (const a of ABAS_RELATORIO) expect(queryDosFiltros(a.valor, filtrosDaQuery(a.valor, {}))).toEqual({})
  })

  it('lê os filtros de Empresas (e ignora o que não vale)', () => {
    const q = {
      periodo: '30',
      grupo_id: '2',
      so_ativos: 'false',
      segmento_id: '0',
      responsavel_id: '7',
      faixa_valor: '10k_50k',
      tempo_cliente: 'mais_1a',
      busca: '  Mercado  ',
      respostas: 'sem',
      quadrante: 'proteger',
      ordem: 'valor',
      pagina: '3',
    }
    expect(filtrosDaQuery('empresas', q)).toEqual({
      ...filtrosPadrao('empresas'),
      periodo: '30',
      grupo_id: '2',
      so_ativos: false,
      segmento_id: '0',
      responsavel_id: '7',
      faixa_valor: '10k_50k',
      tempo_cliente: 'mais_1a',
      busca: 'Mercado',
      respostas: 'sem',
      quadrante: 'proteger',
      ordem: 'valor',
      pagina: 3,
    })
    const ruim = filtrosDaQuery('empresas', { periodo: '45', faixa_valor: 'caro', tempo_cliente: 'x', respostas: 'talvez', quadrante: 'meio', ordem: 'aleatoria', pagina: '-2', grupo_id: 'a b' })
    expect(ruim).toEqual(filtrosPadrao('empresas'))
  })

  it('cada aba só lê os filtros dela', () => {
    const q = { quadrante: 'manter', dimensao: 'rota', empresa_id: '14', segmento_id: '3', busca: 'x' }
    const temas = filtrosDaQuery('temas', q)
    expect(temas.quadrante).toBe('')
    expect(temas.dimensao).toBe('motorista')
    expect(temas.empresa_id).toBe('')
    expect(temas.segmento_id).toBe('')
    expect(filtrosDaQuery('grupos', q).segmento_id).toBe('3')
    expect(filtrosDaQuery('grupos', q).busca).toBe('')
    expect(filtrosDaQuery('entregas', q).dimensao).toBe('rota')
    expect(filtrosDaQuery('historico', q).empresa_id).toBe('14')
    // E não escreve no endereço o que não é da aba.
    expect(queryDosFiltros('temas', { ...temas, quadrante: 'manter', empresa_id: '14' })).toEqual({})
  })

  it('datas escolhidas viram "personalizado"; só as válidas', () => {
    const e = filtrosDaQuery('empresas', { de: '2026-07-01', ate: '2026-02-31' })
    expect(e.periodo).toBe('personalizado')
    expect(e.de).toBe('2026-07-01')
    expect(e.ate).toBe('')
    expect(queryDosFiltros('empresas', e)).toEqual({ de: '2026-07-01' })
    expect(queryDosFiltros('empresas', f('empresas', { periodo: 'personalizado' }))).toEqual({ periodo: 'personalizado' })
  })

  it('escreve só o que foge do padrão da aba', () => {
    expect(queryDosFiltros('historico', f('historico', { periodo: '90', empresa_id: 14 }))).toEqual({ periodo: '90', empresa_id: '14' })
    expect(queryDosFiltros('empresas', f('empresas', { periodo: 'tudo', so_ativos: false, busca: '  bom ', pagina: 2 }))).toEqual({
      periodo: 'tudo',
      so_ativos: 'false',
      busca: 'bom',
      pagina: '2',
    })
    expect(queryDosFiltros('entregas', f('entregas', { dimensao: 'filial', ordem: 'nps' }))).toEqual({ dimensao: 'filial', ordem: 'nps' })
  })

  it('ida e volta pelo endereço dá os mesmos filtros', () => {
    const original = f('empresas', { periodo: '365', grupo_id: '3', segmento_id: '0', quadrante: 'crescer', ordem: 'nome', pagina: 4, busca: 'Sol' })
    expect(filtrosDaQuery('empresas', queryDosFiltros('empresas', original))).toEqual({ ...original, grupo_id: '3' })
  })

  it('"mesma busca" ignora a página (para voltar à página 1 quando um filtro muda)', () => {
    expect(mesmaBusca('empresas', f('empresas', { pagina: 3 }), f('empresas'))).toBe(true)
    expect(mesmaBusca('empresas', f('empresas', { quadrante: 'manter' }), f('empresas'))).toBe(false)
    // Filtro de outra aba não conta.
    expect(mesmaBusca('temas', f('temas', { quadrante: 'manter' }), f('temas'))).toBe(true)
  })

  it('trocar de aba leva grupo e "só ativas"; o período só se a pessoa escolheu um', () => {
    const naoEscolheu = f('empresas', { grupo_id: '2', so_ativos: false, quadrante: 'manter' })
    expect(consultaDaAba('temas', 'empresas', naoEscolheu)).toEqual({ grupo_id: '2', so_ativos: 'false' })
    // O histórico abre com todo o período quando o período não foi escolhido...
    expect(consultaDaAba('historico', 'empresas', naoEscolheu, { empresa_id: 14 })).toEqual({ grupo_id: '2', so_ativos: 'false', empresa_id: '14' })
    // ...e com o período escolhido quando foi.
    expect(consultaDaAba('historico', 'empresas', f('empresas', { periodo: '30' }), { empresa_id: 14 })).toEqual({ periodo: '30', empresa_id: '14' })
    const datas = f('temas', { periodo: 'personalizado', de: '2026-08-01', ate: '2026-08-31' })
    expect(consultaDaAba('operacao', 'temas', datas)).toEqual({ de: '2026-08-01', ate: '2026-08-31' })
    // Saindo do histórico sem escolher o período, a outra aba volta aos 90 dias.
    expect(consultaDaAba('empresas', 'historico', f('historico', { empresa_id: 14 }))).toEqual({})
  })

  it('conta só os filtros da área "Filtros" da aba', () => {
    expect(contarFiltrosDaAba('empresas', f('empresas', { segmento_id: '0', quadrante: 'manter', busca: 'x', ordem: 'nome' }))).toBe(2)
    expect(contarFiltrosDaAba('grupos', f('grupos', { faixa_valor: 'sem_valor', quadrante: 'manter' }))).toBe(1)
    expect(contarFiltrosDaAba('temas', f('temas', { segmento_id: '3' }))).toBe(0)
  })
})

describe('o que vai para a API', () => {
  it('filtros comuns: datas do período (São Paulo), grupo e "só ativas" sempre explícito', () => {
    expect(comunsParaApi(f('empresas'), HOJE)).toEqual({ de: somarDias(HOJE, -89), ate: HOJE, so_ativos: true })
    expect(comunsParaApi(f('empresas', { periodo: 'tudo', so_ativos: false, grupo_id: 5 }), HOJE)).toEqual({ so_ativos: false, grupo_id: 5 })
    expect(comunsParaApi(f('empresas', { periodo: '7' }), HOJE)).toEqual({ de: '2026-09-25', ate: HOJE, so_ativos: true })
  })

  it('Empresas: todos os filtros, a ordem e 50 por página', () => {
    const r = empresasParaApi(
      f('empresas', { periodo: 'tudo', segmento_id: '0', responsavel_id: 7, faixa_valor: 'ate_2k', tempo_cliente: 'sem_data', busca: ' Bom ', respostas: 'com', quadrante: 'corrigir', ordem: 'cobertura', pagina: 2 }),
      HOJE,
    )
    expect(r).toEqual({
      so_ativos: true,
      ordem: 'cobertura',
      pagina: 2,
      por_pagina: 50,
      segmento_id: '0',
      responsavel_id: 7,
      faixa_valor: 'ate_2k',
      tempo_cliente: 'sem_data',
      busca: 'Bom',
      respostas: 'com',
      quadrante: 'corrigir',
    })
    expect(empresasParaApi(f('empresas', { busca: 'x'.repeat(150) }), HOJE).busca).toHaveLength(100)
  })

  it('Grupos, Entregas e Histórico', () => {
    expect(gruposParaApi(f('grupos', { periodo: 'tudo', segmento_id: 2, faixa_valor: '2k_10k', tempo_cliente: '3_6m' }), HOJE)).toEqual({
      so_ativos: true,
      segmento_id: 2,
      faixa_valor: '2k_10k',
      tempo_cliente: '3_6m',
    })
    expect(entregasParaApi(f('entregas', { periodo: 'tudo', dimensao: 'transportadora', busca: ' Vale ', ordem: 'csat', pagina: 3 }), HOJE)).toEqual({
      so_ativos: true,
      dimensao: 'transportadora',
      ordem: 'csat',
      pagina: 3,
      por_pagina: 50,
      busca: 'Vale',
    })
    expect(periodoParaApi(f('historico'), HOJE)).toEqual({})
    expect(periodoParaApi(f('historico', { periodo: '30', grupo_id: 3 }), HOJE)).toEqual({ de: '2026-09-02', ate: HOJE })
  })

  it('links para Respostas levam as datas, o grupo e "só ativas" (que lá é desligado por padrão)', () => {
    expect(consultaRespostas(f('temas', { grupo_id: 4 }), HOJE)).toEqual({ de: somarDias(HOJE, -89), ate: HOJE, grupo_id: '4', so_ativos: 'true' })
    expect(consultaRespostas(f('temas', { periodo: 'tudo', so_ativos: false }), HOJE)).toEqual({})
  })
})

describe('quadrantes e tempo como cliente', () => {
  it('quadrante válido no endereço', () => {
    expect(ehQuadrante('crescer')).toBe(true)
    expect(ehQuadrante('subir')).toBe(false)
  })

  it('meses completos, como o age() do banco', () => {
    expect(mesesCompletos('2026-07-01', '2026-10-01')).toBe(3)
    expect(mesesCompletos('2026-07-02', '2026-10-01')).toBe(2)
    expect(mesesCompletos('2025-10-01', '2026-10-01')).toBe(12)
  })

  it('tempo como cliente em palavras', () => {
    expect(descreverTempoCliente('2026-09-15', HOJE)).toBe('menos de 1 mês')
    expect(descreverTempoCliente('2026-09-01', HOJE)).toBe('1 mês')
    expect(descreverTempoCliente('2026-02-01', HOJE)).toBe('8 meses')
    expect(descreverTempoCliente('2025-10-01', HOJE)).toBe('1 ano')
    expect(descreverTempoCliente('2024-07-01', HOJE)).toBe('2 anos e 3 meses')
    expect(descreverTempoCliente('2025-09-01', HOJE)).toBe('1 ano e 1 mês')
    expect(descreverTempoCliente('2026-12-10', HOJE)).toBe('a partir de 10/12/2026')
    expect(descreverTempoCliente(null, HOJE)).toBeNull()
    expect(descreverTempoCliente('31/12/2020', HOJE)).toBeNull()
  })
})

describe('números', () => {
  it('decimal da API como número', () => {
    expect(numero(12.5)).toBe(12.5)
    expect(numero('1250.00')).toBe(1250)
    expect(numero('')).toBeNull()
    expect(numero(null)).toBeNull()
    expect(numero('abc')).toBeNull()
  })

  it('dinheiro curto', () => {
    expect(formatarMoedaCurta(850)).toBe('R$ 850')
    expect(formatarMoedaCurta('2500.00')).toBe('R$ 2,5 mil')
    expect(formatarMoedaCurta(10000)).toBe('R$ 10 mil')
    expect(formatarMoedaCurta(1_200_000)).toBe('R$ 1,2 mi')
    expect(formatarMoedaCurta(-3400)).toBe('−R$ 3,4 mil')
    expect(formatarMoedaCurta(null)).toBe('—')
    expect(partesMoedaCurta('572680.00')).toEqual({ numero: '572,7', sufixo: 'mil', negativo: false })
    expect(partesMoedaCurta(0)).toEqual({ numero: '0', sufixo: '', negativo: false })
    expect(partesMoedaCurta(null)).toBeNull()
  })
})

describe('escalas dos gráficos', () => {
  it('escala logarítmica do valor: começa e termina em 1, 2 ou 5 × 10ⁿ', () => {
    const e = escalaLog([800, 4300, 120000])
    expect(e.min).toBe(500)
    expect(e.max).toBe(200000)
    expect(e.pos(500)).toBe(0)
    expect(e.pos(200000)).toBe(1)
    expect(e.pos(5000)).toBeGreaterThan(e.pos(800))
    expect(e.pos(0)).toBe(0)
    // Muitas marcas: só as potências de 10.
    expect(e.ticks).toEqual([1000, 10000, 100000])
    expect(escalaLog([1500, 3000]).ticks).toEqual([1000, 2000, 5000])
  })

  it('escala logarítmica sem dados ou com um valor só', () => {
    const vazio = escalaLog([])
    expect([vazio.min, vazio.max]).toEqual([1000, 100000])
    const um = escalaLog([2000])
    expect(um.min).toBeLessThan(2000)
    expect(um.max).toBeGreaterThan(2000)
  })

  it('eixo de contagens com passos redondos', () => {
    expect(escalaContagem(0)).toEqual({ max: 1, ticks: [0, 1] })
    expect(escalaContagem(3)).toEqual({ max: 3, ticks: [0, 1, 2, 3] })
    expect(escalaContagem(7)).toEqual({ max: 8, ticks: [0, 2, 4, 6, 8] })
    expect(escalaContagem(38)).toEqual({ max: 40, ticks: [0, 10, 20, 30, 40] })
    expect(escalaContagem(240)).toEqual({ max: 250, ticks: [0, 50, 100, 150, 200, 250] })
  })
})

describe('temas', () => {
  const semanas: SemanaTemas[] = [
    { inicio: '2026-09-14', fim: '2026-09-20', respostas: 10, temas: { prazo_entrega: { mencoes: 4, reclamacoes: 3 }, atendimento: { mencoes: 2, reclamacoes: 0 } } },
    { inicio: '2026-09-21', fim: '2026-09-27', respostas: 8, temas: { prazo_entrega: { mencoes: 1, reclamacoes: 1 } } },
  ]

  it('uma série por tema, com zero nas semanas sem o tema', () => {
    expect(seriesSemanais(semanas, 'mencoes', ['prazo_entrega', 'atendimento', 'comunicacao'])).toEqual([
      { tema: 'prazo_entrega', valores: [4, 1], total: 5 },
      { tema: 'atendimento', valores: [2, 0], total: 2 },
      { tema: 'comunicacao', valores: [0, 0], total: 0 },
    ])
    expect(seriesSemanais(semanas, 'reclamacoes', ['prazo_entrega'])[0]!.valores).toEqual([3, 1])
    expect(rotuloSemana(semanas[0]!)).toBe('14/09 a 20/09')
  })

  it('cor fixa por tema (segue o tema, não a posição)', () => {
    expect(corDoTema('prazo_entrega').traco).toBe('stroke-grafico-tema-1')
    expect(corDoTema('sistema_pedidos').fundo).toBe('bg-grafico-tema-6')
    expect(corDoTema('outro').preenchimento).toBe('fill-texto-fraco')
  })

  it('partes da barra de sentimento: misto só quando há; fração entre as analisadas', () => {
    const p = partesSentimento({ positivo: 2, neutro: 1, negativo: 1 })
    expect(p.map((x) => x.chave)).toEqual(['positivo', 'neutro', 'negativo'])
    expect(p[0]!.fracao).toBe(0.5)
    expect(partesSentimento({ positivo: 1, neutro: 0, misto: 1, negativo: 2 }).map((x) => [x.chave, x.fracao])).toEqual([
      ['positivo', 0.25],
      ['neutro', 0],
      ['misto', 0.25],
      ['negativo', 0.5],
    ])
    expect(partesSentimento({ positivo: 0, neutro: 0, negativo: -3 }).every((x) => x.fracao === 0 && x.qtd === 0)).toBe(true)
  })
})

describe('nomes ao lado dos pontos', () => {
  const area = { esq: 0, dir: 300, topo: 0, base: 200 }

  it('à direita quando cabe; à esquerda na borda direita', () => {
    const [a, b] = posicionarRotulos(
      [
        { x: 50, y: 100, texto: 'Prazo' },
        { x: 290, y: 40, texto: 'Atendimento' },
      ],
      area,
    )
    expect(a).toEqual({ x: 60, y: 104, ancora: 'start' })
    expect(b!.ancora).toBe('end')
    expect(b!.x).toBe(280)
  })

  it('não põe um nome por cima do outro', () => {
    const [a, b] = posicionarRotulos(
      [
        { x: 50, y: 100, texto: 'Comunicação' },
        { x: 52, y: 104, texto: 'Sistema e pedidos' },
      ],
      area,
    )
    expect(a!.ancora).toBe('start')
    // Perto da borda esquerda, o segundo nome vai para a linha de baixo (à direita), sem cobrir o primeiro.
    expect(b).toEqual({ x: 62, y: 122, ancora: 'start' })
  })

  it('centrado acima, empurrado para dentro da área, quando os lados não servem', () => {
    const [a] = posicionarRotulos([{ x: 10, y: 100, texto: 'Preço e condições' }], { esq: 0, dir: 120, topo: 0, base: 200 })
    expect(a!.ancora).toBe('middle')
    expect(a!.x).toBeCloseTo(56.1)
    expect(a!.y).toBe(88)
  })
})

describe('histórico de uma empresa', () => {
  it('mês da resposta no horário de Brasília', () => {
    expect(mesDaData('2026-10-01T01:30:00Z')).toBe('2026-09')
    expect(mesDaData('2026-10-01T12:00:00-03:00')).toBe('2026-10')
    expect(mesDaData('2026-08-15')).toBe('2026-08')
    expect(mesDaData('ontem')).toBe('')
    expect(mesDaData(null)).toBe('')
  })

  it('linha do tempo em blocos por mês, na ordem em que veio', () => {
    const itens = [
      { id: 1, data: '2026-09-20T10:00:00-03:00' },
      { id: 2, data: '2026-09-02T10:00:00-03:00' },
      { id: 3, data: '2026-08-30T10:00:00-03:00' },
      { id: 4, data: '2026-06-01T10:00:00-03:00' },
    ]
    expect(agruparPorMes(itens).map((g) => [g.mes, g.itens.map((x) => x.id)])).toEqual([
      ['2026-09', [1, 2]],
      ['2026-08', [3]],
      ['2026-06', [4]],
    ])
    expect(agruparPorMes([])).toEqual([])
  })

  it('cargo e perfil vêm como nome (ou {id, nome})', () => {
    expect(nomeDoCampo('Gerente de compras')).toBe('Gerente de compras')
    expect(nomeDoCampo({ nome: ' Decisor ' })).toBe('Decisor')
    expect(nomeDoCampo(null)).toBe('')
  })
})
