import { describe, expect, it } from 'vitest'
import type { Acao, QuadroAcoes } from '@/api/tipos'
import {
  LIMITE_CONCLUIDAS,
  MENSAGENS_CONCLUIR,
  acharNoQuadro,
  calcularSeloPrazo,
  colocarNoQuadro,
  compararAbertas,
  contarFiltrosQuadro,
  destinos,
  edicaoDaAcao,
  faltasParaConcluir,
  filtrosQuadroDaQuery,
  filtrosQuadroParaApi,
  moverNoQuadro,
  mudancasAcao,
  normalizarQuadro,
  ordenarColuna,
  podeMover,
  prioridadeSugerida,
  queryDosFiltrosQuadro,
  removerDoQuadro,
  seloPrazo,
  tituloSugerido,
  validarEdicaoAcao,
} from '@/modulos/acoes/logica'

const HOJE = '2026-10-01'

function acao(id: number, extra: Partial<Acao> = {}): Acao {
  return {
    id,
    titulo: `Ação ${id}`,
    descricao: '',
    resolucao: null,
    situacao: 'a_fazer',
    prioridade: 'media',
    prazo: null,
    prazo_selo: null,
    empresa: { id: 1, nome: 'Mercado Bom Preço' },
    contato: null,
    responsavel: { id: 7, nome: 'Carla', email: 'carla@x.com', foto_url: null },
    resposta: null,
    origem: 'manual',
    grupo: null,
    tipo_nota: null,
    nota: null,
    criada_em: '2026-09-20T10:00:00-03:00',
    atualizada_em: '2026-09-20T10:00:00-03:00',
    iniciada_em: null,
    concluida_em: null,
    criado_por: null,
    concluida_por: null,
    ...extra,
  }
}

function quadro(acoes: Acao[], totais?: Partial<QuadroAcoes['totais']>): QuadroAcoes {
  return normalizarQuadro(
    {
      colunas: {
        a_fazer: acoes.filter((a) => a.situacao === 'a_fazer'),
        em_andamento: acoes.filter((a) => a.situacao === 'em_andamento'),
        concluida: acoes.filter((a) => a.situacao === 'concluida'),
      },
      totais: totais as QuadroAcoes['totais'],
    },
    HOJE,
  )
}

describe('selo de prazo', () => {
  it('segue a regra do contrato: vencido, hoje, amanhã ou nada', () => {
    expect(calcularSeloPrazo('2026-09-30', 'a_fazer', HOJE)).toBe('vencido')
    expect(calcularSeloPrazo('2026-10-01', 'em_andamento', HOJE)).toBe('hoje')
    expect(calcularSeloPrazo('2026-10-02', 'a_fazer', HOJE)).toBe('amanha')
    expect(calcularSeloPrazo('2026-10-03', 'a_fazer', HOJE)).toBeNull()
    expect(calcularSeloPrazo(null, 'a_fazer', HOJE)).toBeNull()
    // Concluída nunca tem selo, mesmo com prazo no passado.
    expect(calcularSeloPrazo('2026-01-01', 'concluida', HOJE)).toBeNull()
    // Aceita data com hora.
    expect(calcularSeloPrazo('2026-10-01T00:00:00', 'a_fazer', HOJE)).toBe('hoje')
  })

  it('amanhã atravessa o fim do mês e do ano', () => {
    expect(calcularSeloPrazo('2026-11-01', 'a_fazer', '2026-10-31')).toBe('amanha')
    expect(calcularSeloPrazo('2027-01-01', 'a_fazer', '2026-12-31')).toBe('amanha')
  })

  it('rótulos em português simples, com a data dd/mm/aaaa quando não é urgente', () => {
    expect(seloPrazo({ prazo: '2026-09-28', situacao: 'a_fazer', prazo_selo: 'vencido' })).toMatchObject({ rotulo: 'Prazo vencido', tom: 'erro' })
    expect(seloPrazo({ prazo: '2026-10-01', situacao: 'a_fazer', prazo_selo: 'hoje' })?.rotulo).toBe('Vence hoje')
    expect(seloPrazo({ prazo: '2026-10-02', situacao: 'a_fazer', prazo_selo: 'amanha' })?.rotulo).toBe('Vence amanhã')
    expect(seloPrazo({ prazo: '2026-10-20', situacao: 'a_fazer', prazo_selo: null })).toMatchObject({ tipo: 'data', rotulo: 'Até 20/10/2026' })
    expect(seloPrazo({ prazo: '2026-10-20', situacao: 'concluida', prazo_selo: null })).toBeNull()
    expect(seloPrazo({ prazo: null, situacao: 'a_fazer', prazo_selo: null })).toBeNull()
  })

  it('usa o selo da API; só calcula quando a API não mandou', () => {
    // A API é a fonte da verdade.
    expect(seloPrazo({ prazo: '2026-10-20', situacao: 'a_fazer', prazo_selo: 'vencido' }, HOJE)?.rotulo).toBe('Prazo vencido')
    expect(seloPrazo({ prazo: '2026-09-20', situacao: 'a_fazer' }, HOJE)?.rotulo).toBe('Prazo vencido')
  })
})

describe('ordem do quadro', () => {
  it('abertas: vencidas primeiro, depois prazo (vazio no fim), prioridade e criação', () => {
    const lista = [
      acao(1, { prazo: null, prioridade: 'alta' }),
      acao(2, { prazo: '2026-10-10', prioridade: 'baixa' }),
      acao(3, { prazo: '2026-10-10', prioridade: 'alta' }),
      acao(4, { prazo: '2026-09-25' }),
      acao(5, { prazo: '2026-10-05' }),
      acao(6, { prazo: '2026-10-10', prioridade: 'alta', criada_em: '2026-09-01T10:00:00-03:00' }),
    ]
    expect([...lista].sort(compararAbertas(HOJE)).map((a) => a.id)).toEqual([4, 5, 6, 3, 2, 1])
  })

  it('concluídas: a mais recente primeiro e no máximo 15', () => {
    const lista = Array.from({ length: 20 }, (_, i) =>
      acao(i + 1, { situacao: 'concluida', concluida_em: `2026-09-${String(i + 1).padStart(2, '0')}T12:00:00Z` }),
    )
    const col = ordenarColuna('concluida', lista, HOJE)
    expect(col).toHaveLength(LIMITE_CONCLUIDAS)
    expect(col[0]!.id).toBe(20)
    expect(col[14]!.id).toBe(6)
  })

  it('"Mover para" oferece as outras duas colunas', () => {
    expect(destinos('a_fazer').map((d) => d.situacao)).toEqual(['em_andamento', 'concluida'])
    expect(destinos('concluida').map((d) => d.rotulo)).toEqual(['A fazer', 'Em andamento'])
  })
})

describe('concluir exige responsável e o que foi feito', () => {
  it('diz o que falta, com as mensagens do servidor', () => {
    expect(faltasParaConcluir({ responsavel: null, resolucao: '' })).toEqual(MENSAGENS_CONCLUIR)
    expect(faltasParaConcluir({ responsavel: { id: 1 }, resolucao: '   ' })).toEqual({ resolucao: MENSAGENS_CONCLUIR.resolucao })
    expect(faltasParaConcluir({ responsavel_id: null, resolucao: 'Liguei.' })).toEqual({ responsavel_id: MENSAGENS_CONCLUIR.responsavel_id })
    expect(faltasParaConcluir({ responsavel_id: 3, resolucao: 'Liguei.' })).toEqual({})
  })

  it('mover para Concluído sem o que falta não é permitido; as outras colunas, sim', () => {
    const semResolucao = acao(1)
    const r = podeMover(semResolucao, 'concluida')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(Object.keys(r.faltas)).toEqual(['resolucao'])
    expect(podeMover(semResolucao, 'em_andamento').ok).toBe(true)
    expect(podeMover(acao(2, { resolucao: 'Resolvido por telefone.' }), 'concluida').ok).toBe(true)
    expect(podeMover(acao(3, { responsavel: null, resolucao: 'Feito' }), 'concluida').ok).toBe(false)
  })
})

describe('mudanças no quadro', () => {
  it('mover troca de coluna, grava as datas e acerta os totais', () => {
    const q = quadro([acao(1, { prazo: '2026-09-20' }), acao(2)], { a_fazer: 2, em_andamento: 0, concluida: 30, vencidas: 1 })
    const andamento = moverNoQuadro(q, 1, 'em_andamento', '2026-10-01T12:00:00Z', HOJE)
    expect(andamento.colunas.a_fazer.map((a) => a.id)).toEqual([2])
    expect(andamento.colunas.em_andamento[0]).toMatchObject({ id: 1, situacao: 'em_andamento', iniciada_em: '2026-10-01T12:00:00Z', prazo_selo: 'vencido' })
    expect(andamento.totais).toEqual({ a_fazer: 1, em_andamento: 1, concluida: 30, vencidas: 1 })

    const feita = moverNoQuadro(andamento, 1, 'concluida', '2026-10-01T13:00:00Z', HOJE)
    expect(feita.colunas.concluida[0]).toMatchObject({ id: 1, concluida_em: '2026-10-01T13:00:00Z', prazo_selo: null })
    // A vencida concluída sai da conta de vencidas.
    expect(feita.totais).toEqual({ a_fazer: 1, em_andamento: 0, concluida: 31, vencidas: 0 })

    const reaberta = moverNoQuadro(feita, 1, 'a_fazer', undefined, HOJE)
    expect(reaberta.colunas.a_fazer[0]).toMatchObject({ id: 1, concluida_em: null, concluida_por: null, prazo_selo: 'vencido' })
    expect(reaberta.totais).toEqual({ a_fazer: 2, em_andamento: 0, concluida: 30, vencidas: 1 })
    // O quadro original não muda.
    expect(q.colunas.a_fazer).toHaveLength(2)
  })

  it('mover para a mesma coluna não faz nada', () => {
    const q = quadro([acao(1)])
    expect(moverNoQuadro(q, 1, 'a_fazer', undefined, HOJE)).toBe(q)
    expect(moverNoQuadro(q, 99, 'concluida', undefined, HOJE)).toBe(q)
  })

  it('desfazer um movimento que deu erro volta a ação e os totais', () => {
    const original = acao(1)
    const q = quadro([original], { a_fazer: 1, em_andamento: 0, concluida: 0, vencidas: 0 })
    const movido = moverNoQuadro(q, 1, 'em_andamento', '2026-10-01T12:00:00Z', HOJE)
    const otimista = acharNoQuadro(movido, 1)
    const desfeito = colocarNoQuadro(movido, original, otimista, HOJE)
    expect(desfeito.colunas.a_fazer.map((a) => a.id)).toEqual([1])
    expect(desfeito.colunas.em_andamento).toHaveLength(0)
    expect(desfeito.totais).toEqual(q.totais)
  })

  it('ação nova entra na coluna certa e soma no total; excluir tira e desconta', () => {
    const q = quadro([acao(1)], { a_fazer: 1, em_andamento: 0, concluida: 0, vencidas: 0 })
    const comNova = colocarNoQuadro(q, acao(2, { prazo: '2026-09-01' }), null, HOJE)
    expect(comNova.colunas.a_fazer.map((a) => a.id)).toEqual([2, 1])
    expect(comNova.totais).toMatchObject({ a_fazer: 2, vencidas: 1 })
    const semEla = removerDoQuadro(comNova, 2, undefined, HOJE)
    expect(semEla.totais).toMatchObject({ a_fazer: 1, vencidas: 0 })
  })

  it('editar uma concluída antiga (fora do quadro) não soma de novo no total', () => {
    const antiga = acao(50, { situacao: 'concluida', concluida_em: '2026-01-01T00:00:00Z', resolucao: 'Ok' })
    const q = quadro([], { a_fazer: 0, em_andamento: 0, concluida: 40, vencidas: 0 })
    const editada = colocarNoQuadro(q, { ...antiga, titulo: 'Novo título' }, antiga, HOJE)
    expect(editada.totais.concluida).toBe(40)
  })

  it('normaliza o que a API mandar faltando', () => {
    const q = normalizarQuadro({ colunas: { a_fazer: [acao(1, { prazo: '2026-09-01' })] } as QuadroAcoes['colunas'] }, HOJE)
    expect(q.colunas.em_andamento).toEqual([])
    expect(q.totais).toEqual({ a_fazer: 1, em_andamento: 0, concluida: 0, vencidas: 1 })
  })
})

describe('edição no painel', () => {
  it('manda só o que mudou; vazio vira null nos opcionais', () => {
    const a = acao(1, { prazo: '2026-10-10', resolucao: 'Antes' })
    const e = edicaoDaAcao(a)
    expect(mudancasAcao(a, e)).toEqual({})
    expect(mudancasAcao(a, { ...e, titulo: '  Ligar para o cliente ' })).toEqual({ titulo: 'Ligar para o cliente' })
    expect(mudancasAcao(a, { ...e, prazo: '', resolucao: '', responsavel_id: '' })).toEqual({ prazo: null, resolucao: null, responsavel_id: null })
    expect(mudancasAcao(a, { ...e, responsavel_id: '7' })).toEqual({})
    expect(mudancasAcao(a, { ...e, empresa: null, situacao: 'em_andamento', prioridade: 'alta' })).toEqual({
      empresa_id: null,
      situacao: 'em_andamento',
      prioridade: 'alta',
    })
  })

  it('concluir sem o que falta mostra os erros antes de enviar', () => {
    const a = acao(1, { responsavel: null })
    expect(validarEdicaoAcao({ ...edicaoDaAcao(a), situacao: 'concluida' }, a)).toEqual(MENSAGENS_CONCLUIR)
    expect(validarEdicaoAcao({ ...edicaoDaAcao(a), titulo: ' ' }, a)).toEqual({ titulo: 'Dê um título para a ação.' })
  })

  it('numa ação já concluída, mudar só o título não exige de novo', () => {
    const a = acao(1, { situacao: 'concluida', responsavel: null, resolucao: null })
    expect(validarEdicaoAcao({ ...edicaoDaAcao(a), titulo: 'Outro' }, a)).toEqual({})
  })
})

describe('filtros do quadro ↔ endereço', () => {
  it('busca de até 100 caracteres (o limite da API): o que passa é cortado', () => {
    const longa = 'x'.repeat(150)
    expect(filtrosQuadroDaQuery({ busca: longa }).busca).toHaveLength(100)
    expect(filtrosQuadroParaApi({ ...filtrosQuadroDaQuery({}), busca: longa }, HOJE).busca).toHaveLength(100)
  })

  it('o atalho do painel (?so_vencidas=true) liga o filtro', () => {
    const f = filtrosQuadroDaQuery({ so_vencidas: 'true' })
    expect(f.so_vencidas).toBe(true)
    expect(filtrosQuadroParaApi(f, HOJE)).toEqual({ so_vencidas: true })
  })

  it('ida e volta sem perder nada; valores inválidos são ignorados', () => {
    const q = { busca: 'boleto', categoria: 'detrator', tipo_nota: 'nps', responsavel_id: '0', empresa_id: '12', grupo_id: '3', periodo: '30', so_vencidas: 'true' }
    const f = filtrosQuadroDaQuery(q)
    expect(queryDosFiltrosQuadro(f)).toEqual(q)
    expect(contarFiltrosQuadro(f)).toBe(6)
    expect(filtrosQuadroParaApi(f, HOJE)).toMatchObject({ responsavel_id: '0', de: '2026-09-02', ate: HOJE })
    expect(filtrosQuadroDaQuery({ categoria: 'constructor', tipo_nota: 'xyz', empresa_id: 'a b', periodo: 'sempre' })).toMatchObject({
      categoria: '',
      tipo_nota: '',
      empresa_id: '',
      periodo: 'tudo',
    })
  })

  it('datas escolhidas viram período personalizado', () => {
    const f = filtrosQuadroDaQuery({ de: '2026-09-01', ate: '2026-09-15' })
    expect(f.periodo).toBe('personalizado')
    expect(filtrosQuadroParaApi(f, HOJE)).toEqual({ de: '2026-09-01', ate: '2026-09-15' })
  })
})

describe('ação a partir de uma resposta', () => {
  it('sugere o mesmo título e a mesma prioridade da ação automática', () => {
    expect(tituloSugerido({ nota: 3, tipo_nota: 'nps', grupo: 'detrator', empresa: { nome: 'Mercado X' } })).toBe('[Detrator NPS 3] Ação requerida: Mercado X')
    expect(tituloSugerido({ nota: 8, tipo_nota: 'nps', grupo: 'neutro', empresa: null, contato: { nome: 'Ana' } })).toBe('[Neutro NPS 8] Ação requerida: Ana')
    expect(tituloSugerido({ nota: 1, tipo_nota: 'csat', grupo: 'insatisfeito' })).toBe('[CSAT 1] Cliente insatisfeito: cliente sem cadastro')
    expect(tituloSugerido({ nota: 2, tipo_nota: 'csat', grupo: 'insatisfeito', empresa: { nome: 'Mercado X' } })).toBe('[CSAT 2] Cliente insatisfeito: Mercado X')
    expect(tituloSugerido({ nota: 3, tipo_nota: 'csat', grupo: 'neutro', empresa: { nome: 'Mercado X' } })).toBe('[CSAT 3] Ação requerida: Mercado X')
    expect(tituloSugerido({ nota: 5, tipo_nota: 'csat', grupo: 'satisfeito', contato: { nome: 'Ana' } })).toBe('[CSAT 5] Ação requerida: Ana')
    expect(prioridadeSugerida('detrator')).toBe('alta')
    expect(prioridadeSugerida('insatisfeito')).toBe('alta')
    expect(prioridadeSugerida('neutro')).toBe('media')
    expect(prioridadeSugerida('promotor')).toBe('baixa')
  })
})
