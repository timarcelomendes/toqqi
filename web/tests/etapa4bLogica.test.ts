import { describe, expect, it } from 'vitest'
import { consultaPico, partesPico, textoPico, variacaoMencoes } from '@/modulos/painel/logica'
import { OPCOES_SENTIMENTO, SITUACOES_IA, analisada, ehFiltroSentimento, ehSentimento, mostrarFiltrosIa, rotuloSentimento } from '@/modulos/respostas/ia'
import {
  FILTROS_PADRAO,
  contarFiltrosAtivos,
  contextoNoFiltro,
  filtrosDaQuery,
  filtrosParaApi,
  queryDosFiltros,
  type FiltrosTela,
} from '@/modulos/respostas/logica'

const HOJE = '2026-10-01'

describe('picos de reclamação (painel)', () => {
  const pico = { tema: 'prazo_entrega', rotulo: 'Prazo e entrega', reclamacoes: 7, media_anterior: 1.5, de: '2026-09-25', ate: '2026-10-01' }

  it('o texto do contrato', () => {
    expect(textoPico(pico)).toBe('Pico de reclamações em Prazo e entrega: 7 nos últimos 7 dias; a média era 1,5 por semana')
    expect(partesPico(pico)).toEqual({ titulo: 'Pico de reclamações em Prazo e entrega', detalhe: '7 nos últimos 7 dias; a média era 1,5 por semana' })
  })

  it('média zero nas 4 semanas anteriores', () => {
    expect(partesPico({ ...pico, reclamacoes: 3, media_anterior: 0 }).detalhe).toBe('3 nos últimos 7 dias; antes, não havia nenhuma')
  })

  it('"Ver respostas" leva às reclamações do tema nos 7 dias, de empresas ativas', () => {
    expect(consultaPico(pico)).toEqual({ tema: 'prazo_entrega', reclamacao: 'true', so_ativos: 'true', de: '2026-09-25', ate: '2026-10-01' })
  })

  it('variação das menções contra o período anterior', () => {
    expect(variacaoMencoes(9)).toEqual({ texto: '+9', direcao: 'sobe', descricao: '9 menções a mais que no período anterior' })
    expect(variacaoMencoes(-1)).toEqual({ texto: '−1', direcao: 'desce', descricao: '1 menção a menos que no período anterior' })
    expect(variacaoMencoes(0)?.direcao).toBe('igual')
    expect(variacaoMencoes(null)).toBeNull()
    expect(variacaoMencoes(undefined)).toBeNull()
  })
})

describe('análise da IA nas respostas', () => {
  it('sentimentos com nome e cor (a cor nunca fala sozinha)', () => {
    expect(ehSentimento('misto')).toBe(true)
    expect(ehSentimento('sem_analise')).toBe(false)
    expect(ehFiltroSentimento('sem_analise')).toBe(true)
    expect(ehFiltroSentimento('bravo')).toBe(false)
    expect(rotuloSentimento('negativo')).toBe('Negativo')
    expect(rotuloSentimento(null)).toBe('—')
    expect(OPCOES_SENTIMENTO.map((o) => o.valor)).toEqual(['negativo', 'misto', 'neutro', 'positivo', 'sem_analise'])
  })

  it('situações que não são "analisada" têm título e texto', () => {
    expect(SITUACOES_IA.pendente.titulo).toBe('Aguardando análise')
    expect(SITUACOES_IA.falhou.titulo).toBe('Não foi possível analisar')
    expect(SITUACOES_IA.limite.titulo).toBe('Limite do mês atingido')
    expect(analisada({ situacao: 'analisada', sentimento: 'positivo', resumo: 'x', temas: [], em: null })).toBe(true)
    expect(analisada({ situacao: 'pendente', sentimento: null, resumo: null, temas: null, em: null })).toBe(false)
    expect(analisada(null)).toBe(false)
  })

  it('filtros de IA só com a IA ativa, com análises na lista ou já ligados no endereço', () => {
    expect(mostrarFiltrosIa({})).toBe(false)
    expect(mostrarFiltrosIa({ iaAtiva: true })).toBe(true)
    expect(mostrarFiltrosIa({ iaAtiva: false, temAnalise: true })).toBe(true)
    expect(mostrarFiltrosIa({ iaAtiva: false, filtroLigado: true })).toBe(true)
  })
})

describe('filtros novos de Respostas (sentimento, reclamação, contexto da entrega)', () => {
  it('lê e escreve no endereço', () => {
    const f = filtrosDaQuery({ sentimento: 'negativo', reclamacao: 'true', motorista: ' Josué Almeida ', rota: 'Rota Sul 3', filial: '', transportadora: 'x'.repeat(200) })
    expect(f.sentimento).toBe('negativo')
    expect(f.reclamacao).toBe(true)
    expect(f.motorista).toBe('Josué Almeida')
    expect(f.rota).toBe('Rota Sul 3')
    expect(f.transportadora).toHaveLength(120)
    expect(queryDosFiltros({ ...FILTROS_PADRAO, sentimento: 'sem_analise', reclamacao: true, filial: 'Campinas' })).toEqual({
      sentimento: 'sem_analise',
      reclamacao: 'true',
      filial: 'Campinas',
    })
    expect(filtrosDaQuery({ sentimento: 'furioso', reclamacao: 'sim' })).toMatchObject({ sentimento: '', reclamacao: false })
  })

  it('vão para a API', () => {
    const f: FiltrosTela = { ...FILTROS_PADRAO, sentimento: 'misto', reclamacao: true, motorista: ' Josué ', tema: 'prazo_entrega' }
    expect(filtrosParaApi(f, HOJE)).toEqual({ arquivadas: 'false', pagina: 1, sentimento: 'misto', reclamacao: true, motorista: 'Josué', tema: 'prazo_entrega' })
  })

  it('sentimento e "só reclamações" contam na área Filtros; o contexto aparece em chips', () => {
    expect(contarFiltrosAtivos({ ...FILTROS_PADRAO, sentimento: 'negativo', reclamacao: true, rota: 'Sul' })).toBe(2)
    expect(contextoNoFiltro({ motorista: 'Josué', rota: '', filial: ' Campinas ', transportadora: '' })).toEqual([
      { campo: 'motorista', rotulo: 'Motorista', valor: 'Josué' },
      { campo: 'filial', rotulo: 'Filial', valor: 'Campinas' },
    ])
  })
})
