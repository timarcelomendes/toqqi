import { describe, expect, it } from 'vitest'
import { criarPergunta, duplicarPergunta, mover } from '@/modulos/formularios/tiposPergunta'
import { errosPorPergunta, validarFormulario } from '@/modulos/formularios/validacaoFormulario'
import type { Pergunta } from '@/api/tipos'

const p = (id: string, tipo: Pergunta['tipo'], extra: Partial<Pergunta> = {}): Pergunta => ({ id, tipo, titulo: 'T', obrigatoria: false, ...extra })

describe('validarFormulario', () => {
  it('aceita um formulário simples', () => {
    expect(validarFormulario([p('a', 'nps'), p('b', 'comentario', { condicao: { tipo: 'grupo', grupos: ['detrator'] } })], 'NPS')).toEqual({})
  })

  it('marca título vazio, opções ruins e escala fora da faixa com chaves da API', () => {
    const erros = validarFormulario([
      p('a', 'nps', { titulo: ' ' }),
      p('b', 'escolha_unica', { opcoes: ['Sim', 'sim'] }),
      p('c', 'escolha_multipla', { opcoes: ['Só uma'] }),
      p('d', 'escala', { min: 1, max: 2 }),
    ])
    expect(Object.keys(erros).sort()).toEqual(['perguntas.0.titulo', 'perguntas.1.opcoes', 'perguntas.2.opcoes', 'perguntas.3.max'])
  })

  it('condição antes da nota principal ou sem grupos é erro', () => {
    const erros = validarFormulario([
      p('a', 'comentario', { condicao: { tipo: 'nota', operador: '<=', valor: 6 } }),
      p('b', 'nps'),
      p('c', 'comentario', { condicao: { tipo: 'grupo', grupos: [] } }),
      p('d', 'comentario', { condicao: { tipo: 'nota', operador: '>=', valor: 11 } }),
    ])
    expect(Object.keys(erros).sort()).toEqual(['perguntas.0.condicao', 'perguntas.2.condicao', 'perguntas.3.condicao'])
  })

  it('agrupa erros por pergunta', () => {
    expect(errosPorPergunta({ 'perguntas.2.titulo': 'x', 'perguntas.2': 'y', nome: 'z' })).toEqual({ 2: { titulo: 'x', _: 'y' } })
  })
})

describe('ajudantes do editor', () => {
  it('cria e duplica com ids únicos', () => {
    const a = criarPergunta('nps', [])
    const b = duplicarPergunta(a, [a])
    expect(a.id).not.toBe(b.id)
    expect(b.titulo).toContain('(cópia)')
    expect(a.obrigatoria).toBe(true)
  })

  it('move itens sem mudar a lista original', () => {
    const l = ['a', 'b', 'c', 'd']
    expect(mover(l, 0, 2)).toEqual(['b', 'c', 'a', 'd'])
    expect(mover(l, 3, 0)).toEqual(['d', 'a', 'b', 'c'])
    expect(l).toEqual(['a', 'b', 'c', 'd'])
  })
})
