import { describe, expect, it } from 'vitest'
import type { Pico } from '@/api/tipos'
import {
  acoesManchete,
  arcoNps,
  barrasDivergentes,
  consultaDosFiltros,
  dataPorExtenso,
  descreverTema,
  diasNoIntervalo,
  estadoTom,
  extremosSerie,
  filtrosDaConsulta,
  formatarMoedaCurta,
  igualAo,
  partesPico,
  picosValemParaFiltros,
  tituloEvolucao12m,
  montarManchete,
  montarPassos,
  nuvemPalavras,
  pctCarteira,
  pontoNoArco,
  reguaNps,
  resumoTom,
  textoDasPartes,
  textoPeriodoAnterior,
  tituloNps,
  type EntradaManchete,
} from '@/modulos/painel/logica'

const PICO: Pico = { tema: 'prazo_entrega', rotulo: 'Prazo e entrega', reclamacoes: 6, media_anterior: 0.3, de: '2026-09-26', ate: '2026-10-02' }

function entrada(extra: Partial<EntradaManchete> = {}): EntradaManchete {
  return {
    nps: { total: 31, detratores: 9 },
    variacao: null,
    diasAnteriores: 90,
    picos: [],
    atencao: { acoes_abertas: 0, acoes_vencidas: 0, receita_em_risco: { valor: 0, empresas: 0 } },
    ...extra,
  }
}
const titulo = (e: EntradaManchete) => textoDasPartes(montarManchete(e).titulo)
const apoio = (e: EntradaManchete) => textoDasPartes(montarManchete(e).apoio)

describe('manchete "O que mudou": regras na ordem de prioridade', () => {
  it('1. pico de reclamações (com a queda antes quando a variação é ≤ −5)', () => {
    expect(titulo(entrada({ picos: [PICO] }))).toBe('6 reclamações de Prazo e entrega em 7 dias, quando a média era 0,3 por semana.')
    expect(titulo(entrada({ picos: [PICO], variacao: { valor: -11, anterior: 34 } }))).toBe(
      'O NPS caiu 11 pontos. 6 reclamações de Prazo e entrega em 7 dias, quando a média era 0,3 por semana.',
    )
    // Queda de menos de 5 pontos não entra.
    expect(titulo(entrada({ picos: [PICO], variacao: { valor: -4, anterior: 34 } }))).toMatch(/^6 reclamações/)
    // Sem média antes.
    expect(titulo(entrada({ picos: [{ ...PICO, media_anterior: 0 }] }))).toBe('6 reclamações de Prazo e entrega em 7 dias, quando antes não havia nenhuma.')
    // O pico é destacado (parte com ênfase de alerta).
    expect(montarManchete(entrada({ picos: [PICO] })).titulo.find((p) => p.enfase === 'alerta')?.texto).toBe('6 reclamações de Prazo e entrega')
  })

  it('1. com vários picos, a manchete fala do maior e lista os outros', () => {
    const outro = { ...PICO, tema: 'atendimento', rotulo: 'Atendimento', reclamacoes: 4 }
    const m = montarManchete(entrada({ picos: [outro, PICO] }))
    expect(m.regra).toBe(1)
    expect(m.pico?.tema).toBe('prazo_entrega')
    expect(m.outrosPicos).toEqual(['Atendimento'])
  })

  it('2. queda de 5 pontos ou mais', () => {
    expect(titulo(entrada({ variacao: { valor: -5, anterior: 30 } }))).toBe('O NPS caiu 5 pontos em relação aos 90 dias antes.')
    expect(titulo(entrada({ variacao: { valor: -12.4, anterior: 30 }, diasAnteriores: null }))).toBe('O NPS caiu 12 pontos em relação ao período anterior.')
    expect(montarManchete(entrada({ variacao: { valor: -5, anterior: 30 } })).regra).toBe(2)
  })

  it('3. alta de 5 pontos ou mais', () => {
    expect(titulo(entrada({ variacao: { valor: 8, anterior: 20 }, diasAnteriores: 30 }))).toBe('O NPS subiu 8 pontos em relação aos 30 dias antes.')
    expect(montarManchete(entrada({ variacao: { valor: 5, anterior: 20 } })).regra).toBe(3)
  })

  it('4. receita em risco: sem plano aberto, ou com planos abertos e vencidos', () => {
    const risco = { receita_em_risco: { valor: 265200, empresas: 8 } }
    expect(titulo(entrada({ atencao: { acoes_abertas: 0, acoes_vencidas: 0, ...risco } }))).toBe(
      '8 empresas tiveram detrator no período, somando R$ 265,2 mil por mês em contrato. Nenhuma tem plano de ação aberto.',
    )
    expect(titulo(entrada({ atencao: { acoes_abertas: 3, acoes_vencidas: 1, ...risco } }))).toBe(
      '8 empresas tiveram detrator no período, somando R$ 265,2 mil por mês em contrato. 3 planos abertos, 1 vencido.',
    )
    expect(titulo(entrada({ atencao: { acoes_abertas: 1, acoes_vencidas: 0, receita_em_risco: { valor: '48000.00', empresas: 1 } } }))).toBe(
      '1 empresa teve detrator no período, somando R$ 48 mil por mês em contrato. 1 plano aberto, nenhum vencido.',
    )
    const m = montarManchete(entrada({ atencao: { acoes_abertas: 0, acoes_vencidas: 0, ...risco } }))
    expect(m.regra).toBe(4)
    expect(m.titulo.find((p) => p.enfase === 'forte')?.texto).toBe('R$ 265,2 mil por mês')
    // Receita zero (empresas sem valor) não vale.
    expect(montarManchete(entrada({ atencao: { acoes_abertas: 0, acoes_vencidas: 0, receita_em_risco: { valor: 0, empresas: 3 } } })).regra).toBe(5)
  })

  it('5. nada disso: tudo estável (ou, sem anterior, o total de respostas)', () => {
    expect(titulo(entrada({ variacao: { valor: 3, anterior: 20 } }))).toBe('Tudo estável: o NPS variou +3 pontos.')
    expect(titulo(entrada({ variacao: { valor: -1, anterior: 20 } }))).toBe('Tudo estável: o NPS variou −1 ponto.')
    expect(titulo(entrada({ variacao: { valor: 0, anterior: 20 } }))).toBe('Tudo estável: o NPS ficou igual.')
    expect(titulo(entrada())).toBe('31 respostas de NPS no período.')
    expect(titulo(entrada({ nps: { total: 1, detratores: 0 } }))).toBe('1 resposta de NPS no período.')
    expect(titulo(entrada({ nps: { total: 0, detratores: 0 } }))).toBe('Nenhuma resposta de NPS no período.')
    expect(montarManchete(entrada()).apoio).toBeNull()
  })

  it('a linha de apoio é a regra seguinte que vale (sem repetir a queda já dita com o pico)', () => {
    const risco = { acoes_abertas: 0, acoes_vencidas: 0, receita_em_risco: { valor: 265200, empresas: 8 } }
    // Pico + queda + receita: a queda vai na manchete; o apoio é a receita.
    expect(apoio(entrada({ picos: [PICO], variacao: { valor: -11, anterior: 34 }, atencao: risco }))).toMatch(/^8 empresas tiveram detrator/)
    // Pico + alta: o apoio é a alta.
    expect(apoio(entrada({ picos: [PICO], variacao: { valor: 9, anterior: 10 }, atencao: risco }))).toBe('O NPS subiu 9 pontos em relação aos 90 dias antes.')
    // Queda + receita: o apoio é a receita.
    expect(apoio(entrada({ variacao: { valor: -7, anterior: 10 }, atencao: risco }))).toMatch(/^8 empresas/)
    // Só pico: sem apoio ("tudo estável" não serve de apoio).
    expect(montarManchete(entrada({ picos: [PICO] })).apoio).toBeNull()
  })
})

describe('manchete: o pico só vale quando vale para os filtros', () => {
  it('período que termina hoje e sem grupo: vale; período passado ou grupo filtrado: não', () => {
    const hoje = '2026-10-02'
    expect(picosValemParaFiltros({ ate: hoje, grupo_id: '' }, hoje)).toBe(true)
    expect(picosValemParaFiltros({ ate: undefined, grupo_id: '' }, hoje)).toBe(true) // todo o período
    expect(picosValemParaFiltros({ ate: '2026-09-30', grupo_id: '' }, hoje)).toBe(false)
    expect(picosValemParaFiltros({ ate: hoje, grupo_id: 3 }, hoje)).toBe(false)
  })

  it('com picosValem = false a manchete pula a regra 1 e segue para a 2 (sem botão do pico)', () => {
    const e = entrada({ picos: [PICO], picosValem: false, variacao: { valor: -11, anterior: 34 } })
    const m = montarManchete(e)
    expect(m.regra).toBe(2)
    expect(m.pico).toBeNull()
    expect(m.outrosPicos).toEqual([])
    expect(titulo(e)).not.toContain('reclamações')
    const o = { podeVerRespostas: true, podeVerAcoes: true, toqqiAI: false, consultaNps: {} }
    expect(acoesManchete(e, m, o).some((a) => a.tipo === 'pico')).toBe(false)
    // sem variação: segue para a receita / tudo estável, nunca o pico
    expect(montarManchete(entrada({ picos: [PICO], picosValem: false, variacao: null })).regra).not.toBe(1)
    // com picosValem = true, o pico volta
    expect(montarManchete({ ...e, picosValem: true }).regra).toBe(1)
  })

  it('média anterior abaixo de 0,05: "quando antes não havia nenhuma"', () => {
    expect(titulo(entrada({ picos: [{ ...PICO, media_anterior: 0.04 }] }))).toContain(', quando antes não havia nenhuma.')
    expect(titulo(entrada({ picos: [{ ...PICO, media_anterior: 0.05 }] }))).toContain('quando a média era 0,1 por semana')
    expect(partesPico({ ...PICO, media_anterior: 0.01 }).detalhe).toBe('6 nos últimos 7 dias; antes, não havia nenhuma')
  })
})

describe('botões da manchete', () => {
  const o = { podeVerRespostas: true, podeVerAcoes: true, toqqiAI: true, consultaNps: { de: '2026-07-05', ate: '2026-10-02', tipo_nota: 'nps' } }

  it('pico → "Ver as N reclamações"; detratores sem plano → "Ver os detratores"; ToqqiAI se disponível', () => {
    const e = entrada({ picos: [PICO] })
    const acoes = acoesManchete(e, montarManchete(e), o)
    expect(acoes.map((a) => a.rotulo)).toEqual(['Ver as 6 reclamações', 'Ver os detratores', 'Perguntar ao ToqqiAI'])
    expect(acoes[0]!.para).toEqual({ path: '/respostas', query: { tema: 'prazo_entrega', reclamacao: 'true', so_ativos: 'true', de: PICO.de, ate: PICO.ate } })
    expect(acoes[1]!.para).toEqual({ path: '/respostas', query: { ...o.consultaNps, categoria: 'detrator' } })
    expect(acoes[2]!.para).toBeUndefined()
  })

  it('com planos abertos, leva aos planos (aos vencidos, se houver)', () => {
    const e = entrada({ atencao: { acoes_abertas: 3, acoes_vencidas: 2, receita_em_risco: { valor: 1000, empresas: 2 } } })
    expect(acoesManchete(e, montarManchete(e), o).map((a) => [a.rotulo, a.para?.query])).toEqual([
      ['Ver os 2 planos vencidos', { so_vencidas: 'true' }],
      ['Perguntar ao ToqqiAI', undefined],
    ])
    const sem = entrada({ atencao: { acoes_abertas: 3, acoes_vencidas: 0, receita_em_risco: { valor: 1000, empresas: 2 } } })
    expect(acoesManchete(sem, montarManchete(sem), o)[0]).toMatchObject({ rotulo: 'Ver os planos de ação', para: { path: '/planos-de-acao' } })
  })

  it('cada botão só para quem pode; sem detratores, nada de detratores', () => {
    const e = entrada({ picos: [PICO] })
    expect(acoesManchete(e, montarManchete(e), { ...o, podeVerRespostas: false, toqqiAI: false })).toEqual([])
    const planos = entrada({ atencao: { acoes_abertas: 3, acoes_vencidas: 0, receita_em_risco: { valor: 1000, empresas: 2 } } })
    expect(acoesManchete(planos, montarManchete(planos), { ...o, podeVerAcoes: false, toqqiAI: false })).toEqual([])
    const limpo = entrada({ nps: { total: 10, detratores: 0 } })
    expect(acoesManchete(limpo, montarManchete(limpo), o).map((a) => a.tipo)).toEqual(['toqqiai'])
  })
})

describe('medidor semicircular', () => {
  it('−100 à esquerda, 0 no topo, 100 à direita; fora da escala fica na ponta', () => {
    expect(pontoNoArco(-100, 110, 110, 90)).toEqual({ x: 20, y: 110 })
    expect(pontoNoArco(0, 110, 110, 90)).toEqual({ x: 110, y: 20 })
    expect(pontoNoArco(100, 110, 110, 90)).toEqual({ x: 200, y: 110 })
    expect(pontoNoArco(250, 110, 110, 90)).toEqual(pontoNoArco(100, 110, 110, 90))
    expect(pontoNoArco(-300, 110, 110, 90)).toEqual(pontoNoArco(-100, 110, 110, 90))
    // nas pontas, o arco desenha as faixas sem buraco: −100 e 100 caem nos extremos do semicírculo
    expect(arcoNps(-100, 100, 110, 110, 90)).toBe('M20,110 A90,90 0 0 1 200,110')
    // 50 fica a 45° do topo, à direita.
    const p = pontoNoArco(50, 110, 110, 90)
    expect(p.x).toBeCloseTo(173.64, 1)
    expect(p.y).toBeCloseTo(46.36, 1)
  })

  it('o arco de cada faixa vai de um valor ao outro', () => {
    expect(arcoNps(-100, 0, 110, 110, 90)).toBe('M20,110 A90,90 0 0 1 110,20')
    expect(arcoNps(50, 100, 110, 110, 90)).toBe('M173.64,46.36 A90,90 0 0 1 200,110')
  })
})

describe('régua das empresas (−100 a 100, do zero até o valor)', () => {
  it('negativo cresce para a esquerda do meio, positivo para a direita', () => {
    expect(reguaNps(-33)).toEqual({ inicio: 33.5, largura: 16.5, sinal: 'negativo' })
    expect(reguaNps(67)).toEqual({ inicio: 50, largura: 33.5, sinal: 'positivo' })
    expect(reguaNps(0)).toEqual({ inicio: 50, largura: 0, sinal: 'zero' })
    expect(reguaNps(-100)).toEqual({ inicio: 0, largura: 50, sinal: 'negativo' })
    expect(reguaNps(140)).toEqual({ inicio: 50, largura: 50, sinal: 'positivo' })
    expect(reguaNps(null)).toEqual({ inicio: 50, largura: 0, sinal: 'zero' })
  })
})

describe('barras divergentes dos temas', () => {
  it('reclamações à esquerda, demais menções à direita, escala comum ao maior lado', () => {
    const b = barrasDivergentes([
      { chave: 'prazo_entrega', rotulo: 'Prazo e entrega', mencoes: 13, reclamacoes: 8 },
      { chave: 'atendimento', rotulo: 'Atendimento', mencoes: 2, reclamacoes: 0 },
      { chave: 'preco_condicoes', rotulo: 'Preço', mencoes: 4 },
    ])
    expect(b.map((x) => [x.reclamacoes, x.outras])).toEqual([
      [8, 5],
      [0, 2],
      [0, 4],
    ])
    expect(b[0]!.esquerda).toBe(1)
    expect(b[0]!.direita).toBeCloseTo(5 / 8)
    expect(b[2]!.direita).toBe(0.5)
  })

  it('não quebra com reclamações acima das menções nem com zero', () => {
    const b = barrasDivergentes([{ chave: 'x', rotulo: 'X', mencoes: 2, reclamacoes: 5 }, { chave: 'y', rotulo: 'Y', mencoes: 0, reclamacoes: 0 }])
    expect(b[0]).toMatchObject({ reclamacoes: 2, outras: 0, esquerda: 1, direita: 0 })
    expect(b[1]).toMatchObject({ esquerda: 0, direita: 0 })
  })

  it('a frase do leitor de tela', () => {
    expect(descreverTema({ rotulo: 'Prazo e entrega', mencoes: 13, reclamacoes: 8, nota_media: 6.2, variacao: 9 })).toBe(
      'Prazo e entrega: 13 menções, 8 reclamações, nota média 6,2, 9 menções a mais que no período anterior',
    )
    expect(descreverTema({ rotulo: 'Atendimento', mencoes: 1, reclamacoes: 1, nota_media: null, variacao: null })).toBe('Atendimento: 1 menção, 1 reclamação')
  })
})

describe('nuvem de palavras', () => {
  it('4 tamanhos pela contagem em relação à mais citada', () => {
    const n = nuvemPalavras([
      { palavra: 'entrega', total: 20 },
      { palavra: 'pedido', total: 15 },
      { palavra: 'chegou', total: 10 },
      { palavra: 'nova', total: 5 },
      { palavra: 'pouco', total: 4 },
    ])
    expect(n.map((p) => p.nivel)).toEqual([4, 4, 3, 2, 1])
  })

  it('sem o tom da palavra, a cor segue o tamanho (não inventa); com o tom, negativo coral e positivo verde', () => {
    const sem = nuvemPalavras([{ palavra: 'entrega', total: 20 }, { palavra: 'pouco', total: 2 }])
    expect(sem.map((p) => p.cor)).toEqual(['text-texto', 'text-texto-suave'])
    const com = nuvemPalavras([
      { palavra: 'atrasou', total: 20, tom: 'negativo' },
      { palavra: 'bom', total: 2, tom: 'positivo' },
      { palavra: 'preço', total: 2, tom: 'neutro' },
    ])
    expect(com.map((p) => p.cor)).toEqual(['text-marca-texto', 'text-sucesso', 'text-texto-suave'])
  })

  it('ignora vazias e corta no limite', () => {
    expect(nuvemPalavras([{ palavra: ' ', total: 3 }, { palavra: 'a', total: 0 }])).toEqual([])
    expect(nuvemPalavras(Array.from({ length: 30 }, (_, i) => ({ palavra: `p${i}`, total: 30 - i })), 20)).toHaveLength(20)
  })
})

describe('tom dos comentários', () => {
  const TOM = { analisados: 24, com_comentario: 24, total_respostas: 31, negativo: 11, misto: 3, neutro: 2, positivo: 8, anterior: { analisados: 25, negativo: 7 } }

  it('% de negativos, variação em pontos, partes da barra e quantos comentaram', () => {
    const r = resumoTom(TOM)!
    expect(r.pctNegativo).toBe(46)
    expect(r.pctNegativoAnterior).toBe(28)
    expect(r.variacao).toBe(18)
    expect(r.pctComentario).toBe(77)
    expect(r.partes.map((p) => [p.chave, p.qtd])).toEqual([
      ['negativo', 11],
      ['misto', 3],
      ['neutro', 2],
      ['positivo', 8],
    ])
    expect(r.partes.reduce((a, p) => a + p.fracao, 0)).toBeCloseTo(1)
  })

  it('sem anterior (ou sem análises nele), sem variação', () => {
    expect(resumoTom({ ...TOM, anterior: null })!.variacao).toBeNull()
    expect(resumoTom({ ...TOM, anterior: { analisados: 0, negativo: 0 } })!.pctNegativoAnterior).toBeNull()
    expect(resumoTom(undefined)).toBeNull()
  })

  it('estados: dados, sem comentários, analisando (pendentes na fila) ou convite para ligar', () => {
    expect(estadoTom(TOM)).toBe('dados')
    expect(estadoTom({ ...TOM, pendentes: 3 })).toBe('dados')
    expect(estadoTom({ analisados: 0, com_comentario: 0, pendentes: 0 })).toBe('sem_comentarios')
    expect(estadoTom({ analisados: 0, com_comentario: 5, pendentes: 2 })).toBe('analisando')
    expect(estadoTom({ analisados: 0, com_comentario: 5, pendentes: 0 })).toBe('ligar')
    // servidor antigo, sem `pendentes`
    expect(estadoTom({ analisados: 0, com_comentario: 5 })).toBe('ligar')
  })
})

describe('evolução de 12 meses: menor e maior mês', () => {
  it('marca o menor e o maior (empate: o mais recente); meses vazios não contam', () => {
    expect(extremosSerie([{ nps: 50 }, { nps: -36 }, { nps: null }, { nps: 57 }, { nps: 57 }, { nps: -33 }])).toEqual({ menor: 1, maior: 4 })
    expect(extremosSerie([{ nps: 10 }, { nps: 10 }])).toEqual({ menor: null, maior: null })
    expect(extremosSerie([{ nps: null }])).toEqual({ menor: null, maior: null })
  })
})

describe('textos e formatos do painel v2', () => {
  it('moeda curta', () => {
    expect(formatarMoedaCurta(850)).toBe('R$ 850')
    expect(formatarMoedaCurta(48000)).toBe('R$ 48 mil')
    expect(formatarMoedaCurta(265200)).toBe('R$ 265,2 mil')
    expect(formatarMoedaCurta('48750.50')).toBe('R$ 48,8 mil')
    expect(formatarMoedaCurta(1_234_000)).toBe('R$ 1,2 mi')
    expect(formatarMoedaCurta(null)).toBe('—')
  })

  it('moeda curta perto de mil e de um milhão: arredonda antes de escolher a unidade', () => {
    expect(formatarMoedaCurta(999.4)).toBe('R$ 999')
    expect(formatarMoedaCurta(999.6)).toBe('R$ 1 mil')
    expect(formatarMoedaCurta('999.50')).toBe('R$ 1 mil')
    expect(formatarMoedaCurta(1000)).toBe('R$ 1 mil')
    expect(formatarMoedaCurta(1049)).toBe('R$ 1 mil')
    expect(formatarMoedaCurta(1050)).toBe('R$ 1,1 mil')
    expect(formatarMoedaCurta(999_940)).toBe('R$ 999,9 mil')
    expect(formatarMoedaCurta(999_950)).toBe('R$ 1 mi')
    expect(formatarMoedaCurta(-999.6)).toBe('−R$ 1 mil')
  })

  it('variação zero e título da evolução', () => {
    expect(igualAo('os 34 dias antes')).toBe('Igual aos 34 dias antes')
    expect(igualAo('o período anterior')).toBe('Igual ao período anterior')
    expect(tituloEvolucao12m('2026-10', '2026-10-02')).toBe('NPS nos últimos 12 meses')
    expect(tituloEvolucao12m('2026-03', '2026-10-02')).toBe('NPS em 12 meses até março de 2026')
    expect(tituloEvolucao12m(null, '2026-10-02')).toBe('NPS nos últimos 12 meses')
  })

  it('% da carteira', () => {
    expect(pctCarteira(265200, 552500)).toBe(48)
    expect(pctCarteira(10, 100000)).toBe(1)
    expect(pctCarteira(1000, null)).toBeNull()
    expect(pctCarteira(0, 1000)).toBeNull()
  })

  it('data por extenso, títulos e o período anterior', () => {
    expect(dataPorExtenso('2026-10-02')).toBe('Sexta, 2 de outubro')
    expect(dataPorExtenso('2026-02-30')).toBe('')
    expect(diasNoIntervalo('2026-04-06', '2026-07-04')).toBe(90)
    expect(diasNoIntervalo('2026-07-04', '2026-04-06')).toBeNull()
    expect(textoPeriodoAnterior({ de: '2026-04-06', ate: '2026-07-04' })).toBe('os 90 dias antes')
    expect(textoPeriodoAnterior(null)).toBe('o período anterior')
    expect(tituloNps('90', 'Últimos 90 dias')).toBe('NPS dos últimos 90 dias')
    expect(tituloNps('365', 'Últimos 12 meses')).toBe('NPS dos últimos 12 meses')
    expect(tituloNps('tudo', 'Todo o período')).toBe('NPS de todo o período')
    expect(tituloNps('personalizado', 'De 01/07/2026 a 29/09/2026')).toBe('NPS · De 01/07/2026 a 29/09/2026')
  })

  it('o próximo passo de cada um dos primeiros passos', () => {
    expect(montarPassos({}, () => true).map((p) => p.proximo)[1]).toBe('ligue os envios para as pesquisas saírem sozinhas.')
  })
})

describe('filtros no endereço', () => {
  it('lê o endereço; o inválido fica no padrão', () => {
    expect(filtrosDaConsulta({})).toEqual({ periodo: '90', de: '', ate: '', grupo_id: '', so_ativos: true })
    expect(filtrosDaConsulta({ periodo: '30', grupo_id: '7', so_ativos: 'false' })).toEqual({ periodo: '30', de: '', ate: '', grupo_id: 7, so_ativos: false })
    expect(filtrosDaConsulta({ periodo: 'xx', grupo_id: 'abc', so_ativos: 'talvez' })).toEqual({ periodo: '90', de: '', ate: '', grupo_id: '', so_ativos: true })
    expect(filtrosDaConsulta({ periodo: 'personalizado', de: '2026-09-01', ate: '2026-13-01' })).toMatchObject({ periodo: '90', de: '', ate: '' })
    // "Escolher as datas" sem as duas datas válidas, ou trocadas, volta ao padrão (nunca fica sem o que buscar)
    expect(filtrosDaConsulta({ periodo: 'personalizado' })).toEqual({ periodo: '90', de: '', ate: '', grupo_id: '', so_ativos: true })
    expect(filtrosDaConsulta({ periodo: 'personalizado', de: '2026-09-01' }).periodo).toBe('90')
    expect(filtrosDaConsulta({ periodo: 'personalizado', de: '2026-09-30', ate: '2026-09-01', grupo_id: '3' })).toEqual({ periodo: '90', de: '', ate: '', grupo_id: 3, so_ativos: true })
    expect(filtrosDaConsulta({ periodo: 'personalizado', de: '2026-09-01', ate: '2026-09-01' })).toMatchObject({ periodo: 'personalizado', de: '2026-09-01', ate: '2026-09-01' })
    // Datas só valem com "Escolher as datas".
    expect(filtrosDaConsulta({ periodo: '7', de: '2026-09-01' }).de).toBe('')
  })

  it('escreve só o que difere do padrão, e volta igual', () => {
    expect(consultaDosFiltros(filtrosDaConsulta({}))).toEqual({})
    const q = { periodo: 'personalizado', de: '2026-09-01', ate: '2026-09-30', grupo_id: '3', so_ativos: 'false' }
    expect(consultaDosFiltros(filtrosDaConsulta(q))).toEqual(q)
  })
})
