// Etapa 5l (docs/api-etapa-5l.md §2): os casos compartilhados da lógica (docs/casos-logica-5l.json), os mesmos que a
// API roda no motor em Python. Todos os casos de caminho, finais, formato antigo e citações, com o motor do site.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  avaliarGrupo,
  caminho,
  citar,
  citarHtml,
  converterCondicaoLegada,
  escolherFinal,
  formatarResposta,
  indexar,
  norm,
  numeroDoTexto,
  paginasVisiveis,
  respostasParaEnvio,
} from '@/pesquisa/logica'
import type { CondicaoPergunta, Final, Grupo, Pergunta, Respostas } from '@/pesquisa/tipos'

interface Casos {
  versao: number
  caminho: { nome: string; itens: Pergunta[]; respostas: Respostas; caminho: string[] }[]
  finais: { nome: string; itens: Pergunta[]; finais: Final[]; respostas: Respostas; final: string | null }[]
  legado: { nome: string; principal: string; condicao: CondicaoPergunta; mostrar_se: Grupo }[]
  citacoes: { nome: string; item: Pergunta; valor: unknown; texto: string }[]
}

// Caminho relativo a este arquivo de teste (web/tests → docs/ na raiz do repositório).
const arquivo = resolve(__dirname, '../../docs/casos-logica-5l.json')
const casos = JSON.parse(readFileSync(arquivo, 'utf8')) as Casos

describe('casos compartilhados (docs/casos-logica-5l.json)', () => {
  it('o arquivo tem todos os grupos de casos', () => {
    expect(casos.versao).toBe(1)
    expect(casos.caminho.length).toBeGreaterThan(0)
    expect(casos.finais.length).toBeGreaterThan(0)
    expect(casos.legado.length).toBeGreaterThan(0)
    expect(casos.citacoes.length).toBeGreaterThan(0)
  })

  describe('caminho', () => {
    it.each(casos.caminho.map((c) => [c.nome, c] as const))('%s', (_nome, c) => {
      expect(caminho(c.itens, c.respostas)).toEqual(c.caminho)
    })
  })

  describe('finais', () => {
    it.each(casos.finais.map((c) => [c.nome, c] as const))('%s', (_nome, c) => {
      expect(escolherFinal(c.finais, c.itens, c.respostas)).toBe(c.final)
    })
  })

  describe('formato antigo (condicao → logica.mostrar_se)', () => {
    it.each(casos.legado.map((c) => [c.nome, c] as const))('%s', (_nome, c) => {
      expect(converterCondicaoLegada(c.condicao, c.principal)).toEqual(c.mostrar_se)
    })
  })

  describe('citações', () => {
    it.each(casos.citacoes.map((c) => [c.nome, c] as const))('%s', (_nome, c) => {
      expect(formatarResposta(c.item, c.valor)).toBe(c.texto)
      // A mesma coisa por {{id}} num título, com a pergunta no caminho.
      const respostas: Respostas = c.valor === null ? {} : { [c.item.id]: c.valor as never }
      expect(citar(`[{{${c.item.id}}}]`, [c.item], respostas)).toBe(`[${c.texto}]`)
    })
  })
})

// ── Além do JSON: as regras de §2 que os casos não cobrem ─────────────────────

const p = (id: string, tipo: Pergunta['tipo'], extra: Partial<Pergunta> = {}): Pergunta => ({ id, tipo, titulo: id, obrigatoria: false, ...extra })
const g = (...condicoes: Grupo['condicoes']): Grupo => ({ juncao: 'todas', condicoes })

describe('normalização de texto e número (§2.1)', () => {
  it('norm: sem acento, minúsculas, pontas aparadas e espaços juntados', () => {
    expect(norm('  São   PAULO\t ')).toBe('sao paulo')
    expect(norm('Ação Çedilha')).toBe('acao cedilha')
  })
  it('numeroDoTexto: vírgula decimal com ponto de milhar; sem vírgula, como está', () => {
    expect(numeroDoTexto('1.250,5')).toBe(1250.5)
    expect(numeroDoTexto('12.5')).toBe(12.5)
    expect(numeroDoTexto(' -3 ')).toBe(-3)
    expect(numeroDoTexto('1,2,3')).toBeNull()
    expect(numeroDoTexto('12a')).toBeNull()
    expect(numeroDoTexto('')).toBeNull()
    // como no motor da API: sem expoente, sem inf/nan
    expect(numeroDoTexto('1e3')).toBeNull()
    expect(numeroDoTexto('nan')).toBeNull()
  })
})

describe('sem resposta (§2.3)', () => {
  const itens = [p('s', 'sim_nao'), p('c', 'comentario'), p('m', 'escolha_multipla', { opcoes: ['A', 'B'] })]
  const porId = indexar(itens)

  it('todo operador é falso sem resposta, inclusive diferente, nao_contem e nao_inclui_nenhum', () => {
    const condicoes: Grupo['condicoes'] = [
      { fonte: 'c', op: 'nao_contem', valor: 'x' },
      { fonte: 'c', op: 'diferente', valor: 'x' },
      { fonte: 'm', op: 'nao_inclui_nenhum', valor: ['A'] },
    ]
    for (const cond of condicoes) {
      expect(avaliarGrupo(g(cond), {}, porId)).toBe(false)
      expect(avaliarGrupo(g({ fonte: cond.fonte, op: 'nao_respondida' }), {}, porId)).toBe(true)
    }
  })

  it('valor inválido conta como sem resposta (texto em branco, opção que não existe, tipo errado)', () => {
    expect(avaliarGrupo(g({ fonte: 'c', op: 'nao_respondida' }), { c: '   ' }, porId)).toBe(true)
    expect(avaliarGrupo(g({ fonte: 'm', op: 'respondida' }), { m: ['Z'] }, porId)).toBe(false)
    expect(avaliarGrupo(g({ fonte: 's', op: 'respondida' }), { s: 'sim' }, porId)).toBe(false)
  })

  it('fonte que não existe: só nao_respondida vale', () => {
    expect(avaliarGrupo(g({ fonte: 'sumiu', op: 'nao_respondida' }), {}, porId)).toBe(true)
    expect(avaliarGrupo(g({ fonte: 'sumiu', op: 'igual', valor: true }), {}, porId)).toBe(false)
  })

  it('grupo null, ausente ou sem condições vale como verdadeiro (todas e qualquer)', () => {
    expect(avaliarGrupo(null, {}, porId)).toBe(true)
    expect(avaliarGrupo(undefined, {}, porId)).toBe(true)
    expect(avaliarGrupo({ juncao: 'todas', condicoes: [] }, {}, porId)).toBe(true)
    expect(avaliarGrupo({ juncao: 'qualquer', condicoes: [] }, {}, porId)).toBe(true)
  })

  it('lista vazia na condição de opções é falsa (mesmo nos negativos)', () => {
    const valores = { m: ['A'] }
    expect(avaliarGrupo(g({ fonte: 'm', op: 'nao_inclui_nenhum', valor: [] }), valores, porId)).toBe(false)
    expect(avaliarGrupo(g({ fonte: 'm', op: 'inclui_todos', valor: [] }), valores, porId)).toBe(false)
  })
})

describe('caminho: proteções', () => {
  it('regra que manda para trás ou para item que não existe é ignorada (sem laço)', () => {
    const se = g({ fonte: 'b', op: 'respondida' })
    const itens = [p('a', 'comentario'), p('b', 'comentario', { logica: { pular: [{ id: 'r1', se, para: 'a' }, { id: 'r2', se, para: 'x' }] } }), p('c', 'comentario')]
    expect(caminho(itens, { b: 'oi' })).toEqual(['a', 'b', 'c'])
  })

  it('a condição antiga (condicao) é convertida na hora, com a fonte na nota principal', () => {
    const itens = [p('n', 'nps'), p('ruim', 'comentario', { condicao: { tipo: 'grupo', grupos: ['detrator'] } })]
    expect(caminho(itens, { n: 3 })).toEqual(['n', 'ruim'])
    expect(caminho(itens, { n: 9 })).toEqual(['n'])
    // logica.mostrar_se ganha da condição antiga
    const comAs2 = [itens[0]!, { ...itens[1]!, logica: { mostrar_se: g({ fonte: 'n', op: 'grupo_e', valor: ['promotor'] }) } }]
    expect(caminho(comAs2, { n: 9 })).toEqual(['n', 'ruim'])
  })
})

describe('citações em HTML e páginas', () => {
  it('citarHtml escapa o valor; citar mantém o texto', () => {
    const itens = [p('c', 'comentario'), p('h', 'conteudo', { html: '<p>Você disse: {{c}}</p>' })]
    const r = { c: '<img src=x onerror=alert(1)> & "aspas"' }
    expect(citarHtml('<p>{{c}}</p>', itens, r)).toBe('<p>&lt;img src=x onerror=alert(1)&gt; &amp; &quot;aspas&quot;</p>')
    expect(citar('Você disse: {{c}}', itens, r)).toBe('Você disse: <img src=x onerror=alert(1)> & "aspas"')
    expect(citar('{{desconhecida}}!', itens, r)).toBe('!')
    expect(citar('{{h}}', itens, r)).toBe('')
  })

  it('citação de pergunta fora do caminho sai vazia', () => {
    const itens = [
      p('s', 'sim_nao', { logica: { pular: [{ id: 'r1', se: g({ fonte: 's', op: 'igual', valor: false }), para: 'fim' }] } }),
      p('nome', 'texto_curto'),
    ]
    expect(citar('Oi {{nome}}', itens, { s: false, nome: 'Ana' })).toBe('Oi ')
    expect(citar('Oi {{nome}}', itens, { s: true, nome: 'Ana' })).toBe('Oi Ana')
  })

  it('páginas agrupam o caminho; envio leva só o caminho (conteúdo nunca vira resposta)', () => {
    const itens = [
      p('n', 'nps'),
      p('c1', 'conteudo', { html: '<p>Oi</p>' }),
      p('q', 'quebra_pagina'),
      p('ruim', 'comentario', { logica: { mostrar_se: g({ fonte: 'n', op: 'menor_igual', valor: 6 }) } }),
      p('q2', 'quebra_pagina'),
      p('fim', 'sim_nao'),
    ]
    expect(paginasVisiveis(itens, { n: 9 }).map((pg) => pg.map((x) => x.id))).toEqual([['n', 'c1'], ['fim']])
    expect(paginasVisiveis(itens, { n: 3 }).map((pg) => pg.map((x) => x.id))).toEqual([['n', 'c1'], ['ruim'], ['fim']])
    expect(respostasParaEnvio(itens, { n: 9, ruim: 'escondida', c1: 'x' as never, fim: true })).toEqual({ n: 9, fim: true })
  })
})
