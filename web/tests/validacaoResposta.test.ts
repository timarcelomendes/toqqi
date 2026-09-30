import { describe, expect, it } from 'vitest'
import { dataValida, validarPerguntas, validarResposta } from '@/pesquisa/validacao'
import type { Pergunta } from '@/pesquisa/tipos'

const p = (tipo: Pergunta['tipo'], extra: Partial<Pergunta> = {}): Pergunta => ({ id: 'x', tipo, titulo: 'T', obrigatoria: false, ...extra })

describe('obrigatória', () => {
  it('reclama só quando é obrigatória e está vazia', () => {
    expect(validarResposta(p('comentario', { obrigatoria: true }), '   ')).toMatch(/Responda/)
    expect(validarResposta(p('comentario'), '')).toBeNull()
    expect(validarResposta(p('nps', { obrigatoria: true }), undefined)).toMatch(/Escolha/)
    expect(validarResposta(p('escolha_multipla', { obrigatoria: true, opcoes: ['a', 'b'] }), [])).toMatch(/pelo menos uma/)
    expect(validarResposta(p('sim_nao', { obrigatoria: true }), false)).toBeNull()
  })
})

describe('faixas de nota', () => {
  it('NPS 0–10, CSAT/estrelas 1–5, escala min–max, só inteiros', () => {
    expect(validarResposta(p('nps'), 0)).toBeNull()
    expect(validarResposta(p('nps'), 11)).not.toBeNull()
    expect(validarResposta(p('nps'), 7.5)).not.toBeNull()
    expect(validarResposta(p('csat'), 0)).not.toBeNull()
    expect(validarResposta(p('estrelas'), 5)).toBeNull()
    expect(validarResposta(p('escala', { min: 0, max: 7 }), 7)).toBeNull()
    expect(validarResposta(p('escala', { min: 1, max: 7 }), 0)).not.toBeNull()
  })
})

describe('formatos de texto curto', () => {
  it('e-mail', () => {
    expect(validarResposta(p('texto_curto', { formato: 'email' }), 'maria@empresa.com.br')).toBeNull()
    expect(validarResposta(p('texto_curto', { formato: 'email' }), 'maria@empresa')).toMatch(/e-mail/)
  })
  it('telefone com pelo menos 8 dígitos', () => {
    expect(validarResposta(p('texto_curto', { formato: 'telefone' }), '(11) 9123-4567')).toBeNull()
    expect(validarResposta(p('texto_curto', { formato: 'telefone' }), '1234-567')).toMatch(/telefone/)
  })
  it('número (aceita vírgula ou ponto)', () => {
    expect(validarResposta(p('texto_curto', { formato: 'numero' }), '12,5')).toBeNull()
    expect(validarResposta(p('texto_curto', { formato: 'numero' }), '-3')).toBeNull()
    expect(validarResposta(p('texto_curto', { formato: 'numero' }), '12a')).toMatch(/números/)
  })
  it('limites de tamanho', () => {
    expect(validarResposta(p('texto_curto'), 'a'.repeat(301))).toMatch(/300/)
    expect(validarResposta(p('comentario'), 'a'.repeat(4001))).toMatch(/4000/)
  })
})

describe('opções, sim/não e data', () => {
  it('opção precisa existir', () => {
    const q = p('escolha_unica', { opcoes: ['Preço', 'Prazo'] })
    expect(validarResposta(q, 'Preço')).toBeNull()
    expect(validarResposta(q, 'Outro')).not.toBeNull()
    const m = p('escolha_multipla', { opcoes: ['A', 'B'] })
    expect(validarResposta(m, ['A', 'B'])).toBeNull()
    expect(validarResposta(m, ['A', 'C'])).not.toBeNull()
  })
  it('sim/não é booleano', () => {
    expect(validarResposta(p('sim_nao'), true)).toBeNull()
    expect(validarResposta(p('sim_nao'), 'sim')).not.toBeNull()
  })
  it('data AAAA-MM-DD existente', () => {
    expect(dataValida('2026-02-28')).toBe(true)
    expect(dataValida('2026-02-30')).toBe(false)
    expect(dataValida('28/02/2026')).toBe(false)
    expect(validarResposta(p('data'), '2026-13-01')).not.toBeNull()
  })
})

it('validarPerguntas devolve só as com erro', () => {
  const lista = [
    { ...p('nps', { obrigatoria: true }), id: 'a' },
    { ...p('comentario'), id: 'b' },
  ]
  expect(validarPerguntas(lista, {})).toEqual({ a: expect.any(String) })
  expect(validarPerguntas(lista, { a: 9 })).toEqual({})
})
