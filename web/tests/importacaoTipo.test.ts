import { afterEach, describe, expect, it, vi } from 'vitest'
import { importacaoApi } from '@/api'
import type { CampoImportacao } from '@/api/tipos'
import { corpoParaTipo, pendenciasMapeamento, tipoDaQuery, TIPOS_IMPORTACAO } from '@/modulos/importacao/mapeamento'
import { montarConfigAcoes, validarConfigAcoes } from '@/modulos/configuracoes/configAcoes'

const camposRespostas: CampoImportacao[] = [
  { chave: 'email', rotulo: 'E-mail', obrigatorio: true },
  { chave: 'data', rotulo: 'Data da resposta', obrigatorio: true },
  { chave: 'nota', rotulo: 'Nota', obrigatorio: true },
  { chave: 'empresa', rotulo: 'Empresa', obrigatorio: false },
  { chave: 'comentario', rotulo: 'Comentário', obrigatorio: false },
]

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('importar: contatos ou respostas antigas', () => {
  it('?tipo=respostas escolhe respostas; o resto, contatos', () => {
    expect(tipoDaQuery('respostas')).toBe('respostas')
    expect(tipoDaQuery(['respostas'])).toBe('respostas')
    expect(tipoDaQuery('contatos')).toBe('contatos')
    expect(tipoDaQuery(undefined)).toBe('contatos')
    expect(tipoDaQuery('qualquer')).toBe('contatos')
    expect(TIPOS_IMPORTACAO.respostas.titulo).toBe('Importar respostas antigas')
  })

  it('respostas: só as colunas obrigatórias da API (e-mail, data, nota); sem chave nem "e-mail ou telefone"', () => {
    expect(pendenciasMapeamento({ A: 'email', B: 'data', C: 'nota' }, camposRespostas, null, 'respostas')).toEqual([])
    expect(pendenciasMapeamento({ A: 'email', B: 'data' }, camposRespostas, null, 'respostas')).toEqual(['Falta indicar a coluna de “Nota”.'])
    expect(pendenciasMapeamento({ A: 'nota', B: 'nota', C: 'email', D: 'data' }, camposRespostas, null, 'respostas')).toEqual(['“Nota” foi escolhido em mais de uma coluna.'])
    // Contatos continuam com as regras de antes.
    expect(pendenciasMapeamento({ A: 'nome' }, [], null)).toContain('Escolha como reconhecer quem já está cadastrado.')
  })

  it('o corpo de respostas leva só mapeamento e "atualizar"; o de contatos leva a chave e o grupo', () => {
    const m = { 'E-mail': 'email', Obs: '', Nota: 'nota' }
    expect(corpoParaTipo('respostas', m, { chave: null, atualizar_existentes: false, grupo_id: 3 })).toEqual({
      mapeamento: { 'E-mail': 'email', Nota: 'nota' },
      atualizar_existentes: false,
    })
    expect(corpoParaTipo('contatos', m, { chave: 'email', atualizar_existentes: true, grupo_id: 3 })).toEqual({
      mapeamento: { 'E-mail': 'email', Nota: 'nota' },
      chave: 'email',
      atualizar_existentes: true,
      grupo_id: 3,
    })
    expect(corpoParaTipo('contatos', m, { chave: null, atualizar_existentes: true })).toBeNull()
    expect(corpoParaTipo('contatos', m, { chave: 'email', atualizar_existentes: true, grupo_id: '' })).not.toHaveProperty('grupo_id')
  })

  it('a análise manda o campo "tipo" junto do arquivo', async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ id: 'a1', tipo: 'respostas', colunas: [], mapeamento_sugerido: {}, total_linhas: 0, amostra: [], campos: [] }), { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    await importacaoApi.analisar(new File(['email;data;nota'], 'antigas.csv', { type: 'text/csv' }), 'respostas')
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/importacao/analisar')
    const corpo = init.body as FormData
    expect(corpo.get('tipo')).toBe('respostas')
    expect((corpo.get('arquivo') as File).name).toBe('antigas.csv')
  })

  it('o modelo de respostas é pedido com ?tipo=respostas', async () => {
    const fetch = vi.fn(async () => new Response('email;empresa;data;nota;comentario\n', { status: 200, headers: { 'Content-Type': 'text/csv' } }))
    vi.stubGlobal('fetch', fetch)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    await importacaoApi.baixarModelo('respostas')
    expect(String((fetch.mock.calls[0] as unknown as [string])[0])).toContain('/importacao/modelo?tipo=respostas')
    expect(clique).toHaveBeenCalled()
  })
})

describe('configurações dos planos de ação', () => {
  it('prazos de 1 a 90 dias, inteiros', () => {
    expect(validarConfigAcoes({ prazo_detrator: '2', prazo_neutro: '5', prazo_promotor: '90' })).toEqual({})
    const erros = validarConfigAcoes({ prazo_detrator: '0', prazo_neutro: '91', prazo_promotor: '2,5' })
    expect(Object.keys(erros).sort()).toEqual(['prazo_detrator', 'prazo_neutro', 'prazo_promotor'])
    expect(erros.prazo_detrator).toBe('Use um número de dias de 1 a 90.')
    expect(validarConfigAcoes({ prazo_detrator: '', prazo_neutro: '5', prazo_promotor: '7' })).toHaveProperty('prazo_detrator')
  })

  it('monta o corpo com números e a chave de promotor', () => {
    expect(montarConfigAcoes({ prazo_detrator: ' 3 ', prazo_neutro: '5', prazo_promotor: '7' }, true)).toEqual({
      prazo_detrator: 3,
      prazo_neutro: 5,
      prazo_promotor: 7,
      acao_promotor: true,
    })
  })
})
