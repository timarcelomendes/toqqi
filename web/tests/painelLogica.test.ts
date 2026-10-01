import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  chavePassosOcultos,
  completarMeses,
  descreverVariacao,
  dominioNps,
  escala,
  faixaDoNps,
  faixaNps,
  formatarMedia1,
  formatarMedia2,
  formatarMes,
  formatarNps,
  formatarVariacao,
  montarPassos,
  mostrarPassos,
  ocultarPassos,
  passosOcultos,
  tomCsat,
  tomNotaMedia,
  tomNps,
} from '@/modulos/painel/logica'
import { dataIsoValida, descreverIntervalo, erroIntervalo, erroPeriodoEscolhido, intervaloDoPeriodo, rotuloPeriodo, somarDias } from '@/utils/periodo'

describe('faixa do NPS → rótulo e cor', () => {
  it('limites: ≥ 75 excelente, ≥ 50 muito bom, ≥ 0 pode melhorar, < 0 crítico', () => {
    expect([100, 75, 74, 50, 49, 0, -1, -100].map(faixaDoNps)).toEqual([
      'excelente',
      'excelente',
      'muito_bom',
      'muito_bom',
      'pode_melhorar',
      'pode_melhorar',
      'critico',
      'critico',
    ])
    expect(faixaDoNps(null)).toBeNull()
  })

  it('cores: verde ≥ 50, âmbar de 0 a 49, vermelho < 0', () => {
    expect(faixaNps('excelente')).toEqual({ chave: 'excelente', rotulo: 'Excelente', tom: 'sucesso' })
    expect(faixaNps('muito_bom')?.tom).toBe('sucesso')
    expect(faixaNps('pode_melhorar')).toMatchObject({ rotulo: 'Pode melhorar', tom: 'atencao' })
    expect(faixaNps('critico')).toMatchObject({ rotulo: 'Crítico', tom: 'erro' })
    expect([50, 49, 0, -1].map(tomNps)).toEqual(['sucesso', 'atencao', 'atencao', 'erro'])
  })

  it('usa a faixa da API; sem ela (ou desconhecida), calcula pelo valor', () => {
    expect(faixaNps(null, 62)?.chave).toBe('muito_bom')
    expect(faixaNps('inventada', -5)?.chave).toBe('critico')
    expect(faixaNps('constructor', 80)?.chave).toBe('excelente')
    expect(faixaNps(null, null)).toBeNull()
  })

  it('CSAT: verde ≥ 80%, âmbar ≥ 60%; nota média pelos grupos do NPS', () => {
    expect([80, 79, 60, 59].map(tomCsat)).toEqual(['sucesso', 'atencao', 'atencao', 'erro'])
    expect([6.9, 7, 8.9, 9, '9.5'].map(tomNotaMedia)).toEqual(['erro', 'atencao', 'atencao', 'sucesso', 'sucesso'])
    expect(tomNotaMedia(null)).toBe('neutro')
  })
})

describe('números com sinal e meses', () => {
  it('NPS e variação com o sinal de menos tipográfico', () => {
    expect(formatarNps(45)).toBe('45')
    expect(formatarNps(-12)).toBe('−12')
    expect(formatarNps(null)).toBe('—')
    expect(formatarVariacao(8)).toBe('+8')
    expect(formatarVariacao(-5)).toBe('−5')
    expect(formatarVariacao(0)).toBe('0')
    expect(descreverVariacao(1)).toBe('subiu 1 ponto')
    expect(descreverVariacao(-7)).toBe('caiu 7 pontos')
    expect(descreverVariacao(0.2)).toBe('ficou igual')
  })

  it('médias com vírgula', () => {
    expect(formatarMedia1(6.44)).toBe('6,4')
    expect(formatarMedia2('4.2')).toBe('4,20')
    expect(formatarMedia2(null)).toBe('—')
  })

  it('meses curtos e longos', () => {
    expect(formatarMes('2026-05')).toBe('mai/26')
    expect(formatarMes('2026-03', 'longo')).toBe('março de 2026')
    expect(formatarMes('2026-13')).toBe('2026-13')
  })
})

describe('escala do gráfico de evolução', () => {
  it('passo conforme a amplitude, com zero incluído quando cruza', () => {
    expect(dominioNps([32, 45, 51])).toMatchObject({ min: 30, max: 60, passo: 10, ticks: [30, 40, 50, 60] })
    expect(dominioNps([-10, 20])).toMatchObject({ min: -10, max: 20, ticks: [-10, 0, 10, 20] })
    expect(dominioNps([-80, 90])).toMatchObject({ min: -100, max: 100, passo: 50 })
  })

  it('valor único ganha folga; nunca passa de −100 a 100', () => {
    expect(dominioNps([60])).toMatchObject({ min: 50, max: 70 })
    expect(dominioNps([100])).toMatchObject({ min: 90, max: 100 })
    expect(dominioNps([-100])).toMatchObject({ min: -100, max: -90 })
    expect(dominioNps([])).toMatchObject({ min: 0, max: 100 })
  })

  it('escala linear (o y cresce para cima)', () => {
    const y = escala([0, 100], [200, 0])
    expect(y(0)).toBe(200)
    expect(y(50)).toBe(100)
    expect(y(100)).toBe(0)
  })

  it('meses sem dados entre o primeiro e o último viram buraco (NPS vazio), virando o ano', () => {
    const r = completarMeses([
      { mes: '2026-02', nps: 10, total: 5 },
      { mes: '2025-11', nps: 30, total: 8 },
    ])
    expect(r.map((p) => p.mes)).toEqual(['2025-11', '2025-12', '2026-01', '2026-02'])
    expect(r.map((p) => p.nps)).toEqual([30, null, null, 10])
    expect(r[1]).toEqual({ mes: '2025-12', nps: null, total: 0 })
  })

  it('sem buraco, um mês só ou mês inválido: fica como está', () => {
    const seguidos = [
      { mes: '2026-08', nps: 1, total: 1 },
      { mes: '2026-09', nps: 2, total: 2 },
    ]
    expect(completarMeses(seguidos)).toEqual(seguidos)
    expect(completarMeses([{ mes: '2026-09', nps: 2, total: 2 }])).toHaveLength(1)
    expect(completarMeses([{ mes: 'xx', nps: 2, total: 2 }, ...seguidos])).toEqual(seguidos)
  })
})

describe('primeiros passos', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('os 4 passos reais da API, aceitando sim/não ou contagem', () => {
    const passos = montarPassos({ contatos: 12, envios_ligados: true, primeiro_envio: 0, primeira_resposta: false }, () => true)
    expect(passos.map((p) => [p.chave, p.feito])).toEqual([
      ['contatos', true],
      ['envios_ligados', true],
      ['primeiro_envio', false],
      ['primeira_resposta', false],
    ])
    expect(passos[2]).toMatchObject({ para: '/envios' })
  })

  it('o atalho respeita o perfil de quem vê', () => {
    const soContatos = montarPassos({}, (p) => p === 'contatos.ver')
    expect(soContatos[0]).toMatchObject({ para: '/contatos' })
    expect(soContatos[1]!.para).toBeUndefined()
    expect(montarPassos({}, () => false).every((p) => !p.para)).toBe(true)
  })

  it('esconder fica guardado no navegador, por conta', () => {
    expect(passosOcultos(7)).toBe(false)
    expect(ocultarPassos(7)).toBe(true)
    expect(localStorage.getItem(chavePassosOcultos(7))).toBe('1')
    expect(passosOcultos(7)).toBe(true)
    expect(passosOcultos(8)).toBe(false)
    ocultarPassos(7, false)
    expect(passosOcultos(7)).toBe(false)
  })

  it('sem armazenamento (navegador bloqueado), não quebra', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('bloqueado')
    })
    expect(passosOcultos(7)).toBe(false)
    expect(ocultarPassos(7)).toBe(false)
  })

  it('o bloco some quando tudo está feito ou quando a pessoa escondeu', () => {
    const faltando = montarPassos({ contatos: true }, () => true)
    const tudo = montarPassos({ contatos: true, envios_ligados: true, primeiro_envio: true, primeira_resposta: true }, () => true)
    expect(mostrarPassos(faltando, false)).toBe(true)
    expect(mostrarPassos(faltando, true)).toBe(false)
    expect(mostrarPassos(tudo, false)).toBe(false)
  })
})

describe('período (dias de São Paulo, com o primeiro e o último dia)', () => {
  it('presets contam hoje', () => {
    expect(intervaloDoPeriodo('7', {}, '2026-10-01')).toEqual({ de: '2026-09-25', ate: '2026-10-01' })
    expect(intervaloDoPeriodo('90', {}, '2026-10-01')).toEqual({ de: '2026-07-04', ate: '2026-10-01' })
    expect(intervaloDoPeriodo('365', {}, '2026-10-01')).toEqual({ de: '2025-10-02', ate: '2026-10-01' })
    expect(intervaloDoPeriodo('tudo', {}, '2026-10-01')).toEqual({})
    expect(intervaloDoPeriodo('personalizado', { de: '2026-09-01', ate: 'xx' }, '2026-10-01')).toEqual({ de: '2026-09-01' })
  })

  it('soma dias atravessando mês e ano bissexto', () => {
    expect(somarDias('2028-02-28', 1)).toBe('2028-02-29')
    expect(somarDias('2026-01-01', -1)).toBe('2025-12-31')
    expect(dataIsoValida('2026-02-30')).toBe(false)
    expect(dataIsoValida('2026-02-28')).toBe(true)
  })

  it('erros e textos das datas escolhidas', () => {
    expect(erroIntervalo('2026-09-10', '2026-09-01')).toBe('A data inicial precisa ser antes da final.')
    expect(erroIntervalo('2026-09-01', '')).toBeNull()
    expect(descreverIntervalo('2026-09-01', '2026-09-30')).toBe('de 01/09/2026 a 30/09/2026')
    expect(descreverIntervalo(null, null)).toBe('desde o começo')
    expect(rotuloPeriodo('90')).toBe('Últimos 90 dias')
    expect(rotuloPeriodo('personalizado', { de: '2026-09-01' })).toBe('Desde 01/09/2026')
  })

  it('"Escolher as datas" pede as duas, válidas e na ordem (senão a tela não busca)', () => {
    expect(erroPeriodoEscolhido('2026-09-01', '2026-09-30')).toBeNull()
    expect(erroPeriodoEscolhido('2026-09-01', '2026-09-01')).toBeNull()
    expect(erroPeriodoEscolhido('2026-09-10', '2026-09-01')).toBe('A data inicial precisa ser antes da final.')
    expect(erroPeriodoEscolhido('2026-09-01', '')).toBe('Escolha a data final.')
    expect(erroPeriodoEscolhido('', '2026-09-01')).toBe('Escolha a data inicial.')
    expect(erroPeriodoEscolhido('', '')).toBe('Escolha a data inicial e a final.')
    expect(erroPeriodoEscolhido('2026-02-30', '2026-03-01')).toBe('Confira a data inicial.')
  })
})
