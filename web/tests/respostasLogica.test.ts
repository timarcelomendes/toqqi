import { describe, expect, it } from 'vitest'
import {
  FILTROS_PADRAO,
  TEMAS_PADRAO,
  categoriaDaNota,
  categoriasDoTipo,
  contarFiltrosAtivos,
  edicaoInicial,
  faixaDaNota,
  filtrosDaQuery,
  filtrosParaApi,
  mesmaBusca,
  mesmosFiltros,
  mudancasAnalise,
  notasDaCategoria,
  queryDosFiltros,
  rotuloTema,
  textoExclusao,
  tomCategoria,
  validarAnalise,
  validarRegistro,
  type FiltrosTela,
} from '@/modulos/respostas/logica'

const HOJE = '2026-10-01'

describe('categorias (grupo da nota)', () => {
  it('NPS 0–6 detrator, 7–8 neutro, 9–10 promotor; CSAT 1–2, 3, 4–5', () => {
    expect([0, 6, 7, 8, 9, 10].map((n) => categoriaDaNota('nps', n))).toEqual(['detrator', 'detrator', 'neutro', 'neutro', 'promotor', 'promotor'])
    expect([1, 2, 3, 4, 5].map((n) => categoriaDaNota('csat', n))).toEqual(['insatisfeito', 'insatisfeito', 'neutro', 'satisfeito', 'satisfeito'])
    expect(notasDaCategoria('csat', 'neutro')).toBe('nota 3')
    expect(notasDaCategoria('nps', 'detrator')).toBe('notas 0 a 6')
  })

  it('cor pela categoria; sem categoria, pela nota e o tipo', () => {
    expect(tomCategoria('detrator')).toBe('erro')
    expect(tomCategoria('neutro')).toBe('atencao')
    expect(tomCategoria('satisfeito')).toBe('sucesso')
    expect(tomCategoria(null, 2, 'csat')).toBe('erro')
    expect(tomCategoria(null, 9, 'nps')).toBe('sucesso')
    expect(tomCategoria('toString')).toBe('neutro')
  })

  it('o filtro de categoria acompanha o tipo', () => {
    expect(categoriasDoTipo('nps')).toEqual(['detrator', 'neutro', 'promotor'])
    expect(categoriasDoTipo('csat')).toEqual(['insatisfeito', 'neutro', 'satisfeito'])
    expect(categoriasDoTipo('')).toHaveLength(5)
    expect(faixaDaNota('csat')).toEqual({ min: 1, max: 5 })
    expect(faixaDaNota(null)).toBeNull()
  })

  it('rótulo do tema, com a lista padrão do contrato', () => {
    expect(TEMAS_PADRAO.map((t) => t.chave)).toEqual(['prazo_entrega', 'produto_avarias', 'atendimento', 'preco_condicoes', 'comunicacao', 'sistema_pedidos'])
    expect(rotuloTema('preco_condicoes')).toBe('Preço e condições')
    expect(rotuloTema('outro')).toBe('outro')
  })
})

describe('filtros ↔ endereço (URL)', () => {
  it('sem nada no endereço vale o padrão', () => {
    expect(filtrosDaQuery({})).toEqual(FILTROS_PADRAO)
    expect(queryDosFiltros({ ...FILTROS_PADRAO })).toEqual({})
  })

  it('lê todos os filtros da tela', () => {
    const f = filtrosDaQuery({
      busca: ' atraso ',
      periodo: '30',
      data_por: 'entrada',
      categoria: 'detrator',
      tipo_nota: 'nps',
      grupo_id: '2',
      empresa_id: '14',
      tema: 'prazo_entrega',
      perfil_id: '1',
      arquivadas: 'todas',
      so_ativos: 'true',
      contato_id: '101',
      pagina: '3',
    })
    expect(f).toEqual({
      busca: 'atraso',
      periodo: '30',
      de: '',
      ate: '',
      data_por: 'entrada',
      categoria: 'detrator',
      tipo_nota: 'nps',
      grupo_id: '2',
      empresa_id: '14',
      tema: 'prazo_entrega',
      perfil_id: '1',
      arquivadas: 'todas',
      so_ativos: true,
      contato_id: '101',
      pagina: 3,
    })
  })

  it('"só empresas ativas" (como no painel): fica no endereço, vai para a API e conta como filtro', () => {
    const f: FiltrosTela = { ...FILTROS_PADRAO, so_ativos: true }
    expect(queryDosFiltros(f)).toEqual({ so_ativos: 'true' })
    expect(filtrosDaQuery({ so_ativos: 'true' }).so_ativos).toBe(true)
    expect(filtrosDaQuery({ so_ativos: 'sim' }).so_ativos).toBe(false)
    expect(filtrosParaApi(f, HOJE)).toEqual({ arquivadas: 'false', pagina: 1, so_ativos: true })
    expect(contarFiltrosAtivos(f)).toBe(1)
    // Padrão: desligado (a lista mostra todas as respostas).
    expect(FILTROS_PADRAO.so_ativos).toBe(false)
  })

  it('ida e volta: o que vai para o endereço volta igual', () => {
    const f: FiltrosTela = { ...FILTROS_PADRAO, busca: 'boleto', periodo: 'personalizado', de: '2026-08-01', ate: '2026-08-31', categoria: 'neutro', contato_id: '5', pagina: 2 }
    const q = queryDosFiltros(f)
    expect(q).toEqual({ busca: 'boleto', de: '2026-08-01', ate: '2026-08-31', categoria: 'neutro', contato_id: '5', pagina: '2' })
    expect(filtrosDaQuery(q)).toEqual(f)
  })

  it('ignora o que não vale (sem quebrar a tela)', () => {
    const f = filtrosDaQuery({ categoria: 'constructor', tipo_nota: 'abc', arquivadas: 'talvez', pagina: '-2', de: '2026-02-30', grupo_id: '1; drop', tema: 'Tema!' })
    expect(f).toEqual(FILTROS_PADRAO)
  })

  it('busca de até 100 caracteres (o limite da API): o que passa é cortado', () => {
    const longa = 'boleto '.repeat(30)
    expect(filtrosDaQuery({ busca: longa }).busca.length).toBeLessThanOrEqual(100)
    expect(filtrosParaApi({ ...FILTROS_PADRAO, busca: 'y'.repeat(150) }, HOJE).busca).toHaveLength(100)
  })

  it('aceita o formato do Vue Router (listas e null)', () => {
    expect(filtrosDaQuery({ categoria: ['promotor', 'detrator'], busca: null }).categoria).toBe('promotor')
  })

  it('a data de um lado só também conta como período personalizado', () => {
    expect(filtrosDaQuery({ de: '2026-09-01' })).toMatchObject({ periodo: 'personalizado', de: '2026-09-01', ate: '' })
  })

  it('"escolher as datas" com as datas apagadas continua escolhendo (não volta sozinho para "tudo")', () => {
    const f: FiltrosTela = { ...FILTROS_PADRAO, periodo: 'personalizado' }
    expect(queryDosFiltros(f)).toEqual({ periodo: 'personalizado' })
    expect(filtrosDaQuery(queryDosFiltros(f))).toEqual(f)
    expect(filtrosParaApi(f, HOJE)).toEqual({ arquivadas: 'false', pagina: 1 })
  })

  it('para a API: período vira datas de São Paulo, "entrada" só com período', () => {
    const base = { ...FILTROS_PADRAO }
    expect(filtrosParaApi(base, HOJE)).toEqual({ arquivadas: 'false', pagina: 1 })
    expect(filtrosParaApi({ ...base, periodo: '7' }, HOJE)).toEqual({ arquivadas: 'false', pagina: 1, de: '2026-09-25', ate: HOJE })
    expect(filtrosParaApi({ ...base, data_por: 'entrada' }, HOJE)).not.toHaveProperty('data_por')
    expect(filtrosParaApi({ ...base, periodo: '90', data_por: 'entrada', contato_id: '9', tema: 'atendimento' }, HOJE)).toMatchObject({
      de: '2026-07-04',
      data_por: 'entrada',
      contato_id: '9',
      tema: 'atendimento',
    })
  })

  it('conta só os filtros escondidos em "Filtros"', () => {
    expect(contarFiltrosAtivos({ ...FILTROS_PADRAO, busca: 'x', periodo: '30', contato_id: '1' })).toBe(0)
    expect(contarFiltrosAtivos({ ...FILTROS_PADRAO, categoria: 'detrator', grupo_id: 2, arquivadas: 'true' })).toBe(3)
  })

  it('1 e "1" são o mesmo filtro; mudar só a página não é outra busca', () => {
    const a = { ...FILTROS_PADRAO, grupo_id: 1 }
    const b = { ...FILTROS_PADRAO, grupo_id: '1' }
    expect(mesmosFiltros(a, b)).toBe(true)
    expect(mesmaBusca({ ...a, pagina: 4 }, b)).toBe(true)
    expect(mesmaBusca({ ...a, categoria: 'neutro' }, b)).toBe(false)
  })
})

describe('registrar resposta', () => {
  const ok = { contatoId: 3, nota: 7, data: HOJE, comentario: '' }

  it('aceita o que está certo', () => {
    expect(validarRegistro(ok, HOJE)).toEqual({})
    expect(validarRegistro({ ...ok, data: '' }, HOJE)).toEqual({})
  })

  it('explica cada problema com as chaves da API', () => {
    expect(validarRegistro({ ...ok, contatoId: null }, HOJE)).toHaveProperty('contato_id')
    expect(validarRegistro({ ...ok, nota: null }, HOJE)).toHaveProperty('nota')
    expect(validarRegistro({ ...ok, nota: 11 }, HOJE)).toHaveProperty('nota')
    expect(validarRegistro({ ...ok, nota: 7.5 }, HOJE)).toHaveProperty('nota')
    expect(validarRegistro({ ...ok, data: '2026-10-02' }, HOJE).data).toBe('A data não pode ser depois de hoje.')
    expect(validarRegistro({ ...ok, data: '1999-12-31' }, HOJE).data).toContain('2000')
    expect(validarRegistro({ ...ok, comentario: 'x'.repeat(4001) }, HOJE)).toHaveProperty('comentario')
  })
})

describe('analisar', () => {
  const resposta = {
    nota: 3,
    tipo_nota: 'nps' as const,
    comentario: 'Atrasou.',
    o_que_faltou: null,
    o_que_combinamos: null,
    temas: ['prazo_entrega'],
  }

  it('sem mudança, não manda nada', () => {
    expect(mudancasAnalise(resposta, edicaoInicial(resposta))).toEqual({})
  })

  it('manda só o que mudou; texto apagado vira null', () => {
    const e = { ...edicaoInicial(resposta), nota: 6, o_que_faltou: '  Avisar antes. ', comentario: '' }
    expect(mudancasAnalise(resposta, e)).toEqual({ nota: 6, o_que_faltou: 'Avisar antes.', comentario: null })
  })

  it('temas só vão quando mudam, na ordem da lista (mandar temas marca como escolha manual)', () => {
    const e = { ...edicaoInicial(resposta), temas: ['comunicacao', 'prazo_entrega'] }
    expect(mudancasAnalise(resposta, e)).toEqual({ temas: ['prazo_entrega', 'comunicacao'] })
    const mesmaOrdemDiferente = { ...edicaoInicial({ ...resposta, temas: ['comunicacao', 'prazo_entrega'] }), temas: ['prazo_entrega', 'comunicacao'] }
    expect(mudancasAnalise({ ...resposta, temas: ['comunicacao', 'prazo_entrega'] }, mesmaOrdemDiferente)).toEqual({})
  })

  it('resposta sem nota (formulário personalizado) nunca manda nota', () => {
    const semNota = { ...resposta, nota: null, tipo_nota: null }
    expect(mudancasAnalise(semNota, { ...edicaoInicial(semNota), nota: 5 })).toEqual({})
  })

  it('a nota respeita a faixa do tipo', () => {
    expect(validarAnalise({ ...edicaoInicial(resposta), nota: 10 }, 'nps')).toEqual({})
    expect(validarAnalise({ ...edicaoInicial(resposta), nota: 0 }, 'csat').nota).toBe('Escolha uma nota de 1 a 5.')
    expect(validarAnalise({ ...edicaoInicial(resposta), o_que_combinamos: 'x'.repeat(2001) }, 'nps')).toHaveProperty('o_que_combinamos')
  })
})

describe('excluir de vez', () => {
  const r = { contato: { id: 1, nome: 'Ana Souza', email: null, perfil: null }, nota: 3, data: '2026-09-29T14:00:00-03:00' }

  it('a confirmação diz quantas ações somem junto', () => {
    expect(textoExclusao(r, 0).mensagem).toContain('Nenhuma ação está ligada a ela')
    expect(textoExclusao(r, 1).mensagem).toContain('e a ação ligada a ela serão apagadas de vez')
    const varias = textoExclusao(r, 3)
    expect(varias.mensagem).toContain('e as 3 ações ligadas a ela serão apagadas de vez')
    expect(varias.mensagem).toContain('(nota 3, de 29/09/2026)')
    expect(varias.mensagem).toContain('Não dá para desfazer')
    expect(varias.titulo).toBe('Excluir a resposta de Ana Souza?')
    expect(varias.confirmar).toBe('Excluir resposta e ações')
    // A última nota do contato só muda se esta for a mais recente dele: o texto não afirma que muda.
    expect(varias.mensagem).toContain('Se esta for a resposta mais recente do contato, a última nota dele passa a ser a da resposta anterior.')
    expect(varias.mensagem).not.toContain('volta a ser')
  })

  it('resposta sem contato', () => {
    const t = textoExclusao({ contato: null, nota: null, data: '' }, 0)
    expect(t.titulo).toBe('Excluir a resposta de cliente sem cadastro?')
    expect(t.mensagem).not.toContain('última nota')
  })
})
