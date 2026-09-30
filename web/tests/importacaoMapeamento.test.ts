import { describe, expect, it } from 'vitest'
import {
  camposDuplicados,
  chavesPossiveis,
  escolherChave,
  exemplosDaColuna,
  faltaEmailOuTelefone,
  mapeamentoInicial,
  mapeamentoParaEnvio,
  obrigatoriosFaltando,
  pendenciasMapeamento,
  validarArquivo,
} from '@/modulos/importacao/mapeamento'
import type { CampoImportacao } from '@/api/tipos'

const campos: CampoImportacao[] = [
  { chave: 'nome', rotulo: 'Nome', obrigatorio: true },
  { chave: 'email', rotulo: 'E-mail', obrigatorio: false },
  { chave: 'telefone', rotulo: 'Telefone', obrigatorio: false },
  { chave: 'empresa', rotulo: 'Empresa', obrigatorio: false },
  { chave: 'codigo_externo', rotulo: 'Código', obrigatorio: false },
]

describe('validarArquivo', () => {
  it('aceita .csv/.xlsx/.xls até 5 MB', () => {
    expect(validarArquivo({ name: 'clientes.XLSX', size: 1000 })).toBeNull()
    expect(validarArquivo({ name: 'clientes.csv', size: 5 * 1024 * 1024 })).toBeNull()
    expect(validarArquivo({ name: 'clientes.pdf', size: 10 })).toMatch(/\.csv/)
    expect(validarArquivo({ name: 'clientes.csv', size: 5 * 1024 * 1024 + 1 })).toMatch(/5 MB/)
    expect(validarArquivo({ name: 'vazio.csv', size: 0 })).toMatch(/vazio/)
  })
})

describe('mapeamento', () => {
  it('usa a sugestão, ignora campo desconhecido e não repete campo', () => {
    const m = mapeamentoInicial(
      ['Nome', 'E-mail', 'Email 2', 'Celular', 'Obs'],
      { Nome: 'nome', 'E-mail': 'email', 'Email 2': 'email', Celular: 'telefone', Obs: 'inexistente' },
      campos,
    )
    expect(m).toEqual({ Nome: 'nome', 'E-mail': 'email', 'Email 2': '', Celular: 'telefone', Obs: '' })
  })

  it('aponta duplicados, obrigatórios faltando e a regra e-mail ou telefone', () => {
    const m = { A: 'email', B: 'email', C: '' }
    expect(camposDuplicados(m)).toEqual(['email'])
    expect(obrigatoriosFaltando(m, campos).map((c) => c.chave)).toEqual(['nome'])
    expect(faltaEmailOuTelefone({ A: 'nome' })).toBe(true)
    expect(faltaEmailOuTelefone({ A: 'nome', B: 'telefone' })).toBe(false)
  })

  it('chave: só as mapeadas, na ordem e-mail > código > telefone, mantendo a escolha válida', () => {
    const m = { A: 'telefone', B: 'codigo_externo' }
    expect(chavesPossiveis(m)).toEqual(['codigo_externo', 'telefone'])
    expect(escolherChave(m, null)).toBe('codigo_externo')
    expect(escolherChave(m, 'telefone')).toBe('telefone')
    expect(escolherChave(m, 'email')).toBe('codigo_externo')
    expect(escolherChave({ A: 'nome' }, 'email')).toBeNull()
  })

  it('envia só colunas importadas', () => {
    expect(mapeamentoParaEnvio({ A: 'nome', B: '', C: 'email' })).toEqual({ A: 'nome', C: 'email' })
  })

  it('pendências em texto simples', () => {
    expect(pendenciasMapeamento({ A: 'nome', B: 'email' }, campos, 'email')).toEqual([])
    const p = pendenciasMapeamento({ A: 'empresa' }, campos, null)
    expect(p).toHaveLength(3)
    expect(p.join(' ')).toMatch(/Nome/)
  })
})

describe('exemplosDaColuna', () => {
  it('lê amostra como objeto ou como lista e pula vazios', () => {
    const colunas = ['Nome', 'Email']
    expect(
      exemplosDaColuna({ colunas, amostra: [{ linha: 2, valores: { Nome: 'Ana', Email: '' } }, { linha: 3, valores: { Nome: 'Bia' } }] }, 'Nome'),
    ).toEqual(['Ana', 'Bia'])
    expect(exemplosDaColuna({ colunas, amostra: [{ linha: 2, valores: ['Ana', 'a@x.com'] }, { linha: 3, valores: ['Bia', null] }] }, 'Email')).toEqual(['a@x.com'])
  })
})
