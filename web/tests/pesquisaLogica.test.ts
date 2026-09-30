import { describe, expect, it } from 'vitest'
import {
  condicaoAtende,
  grupoDaNota,
  indicePrincipal,
  paginasVisiveis,
  perguntasVisiveis,
  podeTerCondicao,
  respostasParaEnvio,
  tipoPrincipal,
} from '@/pesquisa/logica'
import type { Pergunta } from '@/pesquisa/tipos'

const p = (id: string, tipo: Pergunta['tipo'], extra: Partial<Pergunta> = {}): Pergunta => ({ id, tipo, titulo: id, obrigatoria: false, ...extra })

describe('nota principal', () => {
  it('é a 1ª NPS; senão a 1ª CSAT/estrelas; senão nenhuma', () => {
    expect(indicePrincipal([p('a', 'texto_curto'), p('b', 'csat'), p('c', 'nps')])).toBe(2)
    expect(indicePrincipal([p('a', 'estrelas'), p('b', 'csat')])).toBe(0)
    expect(indicePrincipal([p('a', 'comentario')])).toBe(-1)
    expect(tipoPrincipal([p('a', 'estrelas')])).toBe('csat')
    expect(tipoPrincipal([p('a', 'nps')])).toBe('nps')
    expect(tipoPrincipal([p('a', 'sim_nao')])).toBe('personalizado')
  })

  it('só aceita condição depois da nota principal', () => {
    const lista = [p('a', 'texto_curto'), p('b', 'nps'), p('c', 'comentario')]
    expect(podeTerCondicao(0, lista)).toBe(false)
    expect(podeTerCondicao(1, lista)).toBe(false)
    expect(podeTerCondicao(2, lista)).toBe(true)
    expect(podeTerCondicao(1, [p('x', 'comentario'), p('y', 'comentario')])).toBe(false)
  })
})

describe('grupos', () => {
  it('NPS: 0–6 detrator, 7–8 neutro, 9–10 promotor', () => {
    expect([0, 6, 7, 8, 9, 10].map((n) => grupoDaNota('nps', n))).toEqual(['detrator', 'detrator', 'neutro', 'neutro', 'promotor', 'promotor'])
  })
  it('CSAT/estrelas: 1–2 insatisfeito, 3 neutro, 4–5 satisfeito', () => {
    expect([1, 2, 3, 4, 5].map((n) => grupoDaNota('csat', n))).toEqual(['insatisfeito', 'insatisfeito', 'neutro', 'satisfeito', 'satisfeito'])
    expect(grupoDaNota('estrelas', 3)).toBe('neutro')
    expect(grupoDaNota('escala', 3)).toBeNull()
  })
})

describe('condições', () => {
  const nps = p('n', 'nps')
  it('sem condição sempre aparece', () => {
    expect(condicaoAtende(null, nps, undefined)).toBe(true)
  })
  it('com condição e sem nota fica escondida', () => {
    expect(condicaoAtende({ tipo: 'grupo', grupos: ['detrator'] }, nps, null)).toBe(false)
    expect(condicaoAtende({ tipo: 'nota', operador: '<=', valor: 6 }, null, 3)).toBe(false)
  })
  it('por grupo', () => {
    const c = { tipo: 'grupo' as const, grupos: ['detrator' as const, 'neutro' as const] }
    expect(condicaoAtende(c, nps, 6)).toBe(true)
    expect(condicaoAtende(c, nps, 8)).toBe(true)
    expect(condicaoAtende(c, nps, 9)).toBe(false)
    expect(condicaoAtende({ tipo: 'grupo', grupos: ['satisfeito'] }, p('c', 'csat'), 4)).toBe(true)
  })
  it('por nota ≤ e ≥ (limites incluídos)', () => {
    expect(condicaoAtende({ tipo: 'nota', operador: '<=', valor: 6 }, nps, 6)).toBe(true)
    expect(condicaoAtende({ tipo: 'nota', operador: '<=', valor: 6 }, nps, 7)).toBe(false)
    expect(condicaoAtende({ tipo: 'nota', operador: '>=', valor: 9 }, nps, 9)).toBe(true)
    expect(condicaoAtende({ tipo: 'nota', operador: '>=', valor: 9 }, nps, 0)).toBe(false)
  })
})

describe('perguntas e páginas visíveis', () => {
  const lista = [
    p('nota', 'nps'),
    p('motivo_ruim', 'comentario', { condicao: { tipo: 'grupo', grupos: ['detrator'] } }),
    p('q1', 'quebra_pagina'),
    p('elogio', 'comentario', { condicao: { tipo: 'nota', operador: '>=', valor: 9 } }),
    p('q2', 'quebra_pagina'),
    p('email', 'texto_curto', { formato: 'email' }),
  ]

  it('esconde o que não bate com a nota', () => {
    expect(perguntasVisiveis(lista, {}).map((x) => x.id)).toEqual(['nota', 'email'])
    expect(perguntasVisiveis(lista, { nota: 3 }).map((x) => x.id)).toEqual(['nota', 'motivo_ruim', 'email'])
    expect(perguntasVisiveis(lista, { nota: 10 }).map((x) => x.id)).toEqual(['nota', 'elogio', 'email'])
  })

  it('páginas vazias somem', () => {
    expect(paginasVisiveis(lista, { nota: 3 }).map((pg) => pg.map((x) => x.id))).toEqual([['nota', 'motivo_ruim'], ['email']])
    expect(paginasVisiveis(lista, { nota: 10 }).map((pg) => pg.map((x) => x.id))).toEqual([['nota'], ['elogio'], ['email']])
  })

  it('envia só respostas visíveis e preenchidas (texto sem espaços sobrando)', () => {
    const r = respostasParaEnvio(lista, { nota: 10, motivo_ruim: 'ficou escondida', elogio: '  Ótimo  ', email: '' })
    expect(r).toEqual({ nota: 10, elogio: 'Ótimo' })
  })
})
