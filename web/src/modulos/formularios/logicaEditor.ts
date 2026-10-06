// Lógica dos formulários, só do editor (docs/api-etapa-5l.md §5.1 e §5.3): operadores por tipo de pergunta, rótulos em
// português, valores iniciais, a frase de uma condição (`descreverGrupo`), quem usa cada pergunta e o que acontece com
// as condições ao renomear ou excluir uma opção. O motor (o que a página pública roda) fica em src/pesquisa/logica.ts.
import { faixa, gruposDoTipo, respondivel } from '@/pesquisa/logica'
import type { Condicao, Final, Grupo, Operador, Pergunta, Regra, ValorCondicao } from '@/pesquisa/tipos'

export const MAX_CONDICOES = 10
export const MAX_REGRAS = 10
export const MAX_FINAIS = 10
export const FIM = 'fim'

/** Operadores sem valor. */
export const SEM_VALOR: Operador[] = ['respondida', 'nao_respondida']
const COMPARACOES: Operador[] = ['igual', 'diferente', 'menor', 'menor_igual', 'maior', 'maior_igual', 'entre']
const TEXTO: Operador[] = ['contem', 'nao_contem', 'igual', 'diferente', 'comeca_com', 'termina_com']

const TEM_GRUPO = ['nps', 'csat', 'estrelas']

export function ehNota(p: Pick<Pergunta, 'tipo'>): boolean {
  return ['nps', 'csat', 'estrelas', 'escala'].includes(p.tipo)
}
export function ehTextoNumero(p: Pick<Pergunta, 'tipo' | 'formato'>): boolean {
  return p.tipo === 'texto_curto' && p.formato === 'numero'
}

/** Os operadores que valem para a pergunta-fonte (§2.2), na ordem do menu (o mais usado primeiro). */
export function operadoresDaFonte(fonte: Pick<Pergunta, 'tipo' | 'formato'> | null | undefined): Operador[] {
  if (!fonte) return []
  if (ehNota(fonte)) return [...(TEM_GRUPO.includes(fonte.tipo) ? (['grupo_e'] as Operador[]) : []), ...COMPARACOES, ...SEM_VALOR]
  switch (fonte.tipo) {
    case 'escolha_unica':
      return ['um_de', 'nenhum_de', ...SEM_VALOR]
    case 'escolha_multipla':
      return ['inclui_algum', 'inclui_todos', 'nao_inclui_nenhum', ...SEM_VALOR]
    case 'sim_nao':
      return ['igual', ...SEM_VALOR]
    case 'data':
      return [...COMPARACOES, ...SEM_VALOR]
    case 'texto_curto':
      return ehTextoNumero(fonte) ? [...COMPARACOES, ...SEM_VALOR] : [...TEXTO, ...SEM_VALOR]
    case 'comentario':
      return [...TEXTO, ...SEM_VALOR]
    default:
      return []
  }
}

/** Os operadores em português (§5.3). */
export const ROTULOS_OPERADOR: Record<Operador, string> = {
  igual: 'é',
  diferente: 'não é',
  menor: 'é menor que',
  menor_igual: 'é no máximo',
  maior: 'é maior que',
  maior_igual: 'é pelo menos',
  entre: 'está entre',
  grupo_e: 'está no grupo',
  respondida: 'foi respondida',
  nao_respondida: 'não foi respondida',
  um_de: 'é uma de',
  nenhum_de: 'não é nenhuma de',
  inclui_algum: 'inclui alguma de',
  inclui_todos: 'inclui todas',
  nao_inclui_nenhum: 'não inclui nenhuma de',
  contem: 'contém',
  nao_contem: 'não contém',
  comeca_com: 'começa com',
  termina_com: 'termina com',
}
const ROTULOS_DATA: Partial<Record<Operador, string>> = { menor: 'antes de', maior: 'depois de', menor_igual: 'até', maior_igual: 'a partir de' }

export function rotuloOperador(op: Operador, fonte?: Pick<Pergunta, 'tipo'> | null): string {
  return (fonte?.tipo === 'data' ? ROTULOS_DATA[op] : undefined) ?? ROTULOS_OPERADOR[op] ?? op
}

function hojeIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Um valor inicial que já faz sentido para o operador (o editor troca o valor ao trocar a pergunta ou a comparação). */
export function valorPadrao(fonte: Pergunta, op: Operador): ValorCondicao | undefined {
  if (SEM_VALOR.includes(op)) return undefined
  if (ehNota(fonte)) {
    const { min, max } = faixa(fonte)
    if (op === 'grupo_e') return [gruposDoTipo(fonte.tipo)[0]?.valor ?? 'detrator']
    if (fonte.tipo === 'nps') return op === 'entre' ? [0, 6] : ({ menor: 7, menor_igual: 6, maior: 8, maior_igual: 9 } as Record<string, number>)[op] ?? 10
    if (fonte.tipo === 'csat' || fonte.tipo === 'estrelas') return op === 'entre' ? [1, 2] : ({ menor: 3, menor_igual: 2, maior: 3, maior_igual: 4 } as Record<string, number>)[op] ?? 5
    const meio = Math.floor((min + max) / 2)
    return op === 'entre' ? [min, meio] : meio
  }
  switch (fonte.tipo) {
    case 'escolha_unica':
    case 'escolha_multipla':
      return (fonte.opcoes ?? []).filter((o) => o.trim()).slice(0, 1)
    case 'sim_nao':
      return true
    case 'data':
      return op === 'entre' ? [hojeIso(), hojeIso()] : hojeIso()
    default:
      return ehTextoNumero(fonte) ? (op === 'entre' ? [0, 10] : 0) : ''
  }
}

/** Condição nova com a pergunta-fonte: a 1ª comparação do menu e o valor inicial dela. */
export function condicaoPadrao(fonte: Pergunta, op?: Operador): Condicao {
  const o = op ?? operadoresDaFonte(fonte)[0] ?? 'respondida'
  const valor = valorPadrao(fonte, o)
  return valor === undefined ? { fonte: fonte.id, op: o } : { fonte: fonte.id, op: o, valor }
}

/** O valor continua servindo depois de trocar a comparação? (ex.: "é" → "não é" mantém o número) */
export function valorServe(fonte: Pergunta, op: Operador, valor: ValorCondicao | undefined): boolean {
  if (SEM_VALOR.includes(op)) return true
  if (valor === undefined) return false
  if (op === 'entre') return Array.isArray(valor) && valor.length === 2
  if (op === 'grupo_e' || ['um_de', 'nenhum_de', 'inclui_algum', 'inclui_todos', 'nao_inclui_nenhum'].includes(op)) return Array.isArray(valor)
  if (fonte.tipo === 'sim_nao') return typeof valor === 'boolean'
  if (ehNota(fonte) || ehTextoNumero(fonte)) return typeof valor === 'number'
  return typeof valor === 'string'
}

// ── Números, nomes e títulos ────────────────────────────────────────────────

/** P1, P2… só para perguntas (conteúdo e quebra não contam). */
export function numerosDasPerguntas(itens: readonly Pergunta[]): Map<string, number> {
  const mapa = new Map<string, number>()
  let n = 0
  for (const p of itens) if (respondivel(p.tipo)) mapa.set(p.id, ++n)
  return mapa
}

/** O título com as citações como "[resposta de P2]" (e "[resposta apagada]" quando a pergunta não existe mais). */
export function textoComCitacoes(texto: string | null | undefined, numeros: ReadonlyMap<string, number>): string {
  if (!texto) return ''
  return texto.replace(/\{\{([A-Za-z0-9_-]{1,32})\}\}/g, (_m, id: string) => {
    const n = numeros.get(id)
    return n ? `[resposta de P${n}]` : '[resposta apagada]'
  })
}

/** O texto de um HTML, sem tags, para nomes curtos (blocos de conteúdo e finais). */
export function textoSemTags(html: string | null | undefined): string {
  if (!html) return ''
  return html
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim()
}

export function cortar(texto: string, max: number): string {
  const t = texto.trim()
  return t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t
}

/** Nome de um item para listas e menus: "P3 · Título" ou "Conteúdo · nome interno (ou o começo do texto)". */
export function nomeDoItem(p: Pergunta, numeros: ReadonlyMap<string, number>, max = 60): string {
  if (p.tipo === 'conteudo') {
    const nome = p.titulo?.trim() || textoSemTags(p.html)
    return `Conteúdo · ${cortar(textoComCitacoes(nome, numeros), max) || 'sem texto'}`
  }
  if (p.tipo === 'quebra_pagina') return 'Quebra de página'
  const n = numeros.get(p.id)
  const titulo = cortar(textoComCitacoes(p.titulo, numeros), max) || 'Pergunta sem título'
  return n ? `P${n} · ${titulo}` : titulo
}

// ── Frases (descreverGrupo) ─────────────────────────────────────────────────

const NOME_FONTE: Record<string, string> = { nps: 'NPS', csat: 'CSAT' }

function dataBr(v: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : v
}

function valorLegivel(fonte: Pergunta | undefined, v: unknown): string {
  if (typeof v === 'boolean') return v ? 'Sim' : 'Não'
  if (typeof v === 'string' && fonte?.tipo === 'data') return dataBr(v)
  if (typeof v === 'string' && (fonte?.tipo === 'texto_curto' || fonte?.tipo === 'comentario') && !ehTextoNumero(fonte)) return `“${v}”`
  return String(v)
}

function juntar(itens: string[], conector: string): string {
  if (itens.length <= 1) return itens[0] ?? ''
  return `${itens.slice(0, -1).join(', ')} ${conector} ${itens[itens.length - 1]}`
}

/** Como a pergunta aparece na frase: "NPS", "CSAT" ou o título entre aspas. */
export function nomeNaFrase(fonte: Pergunta | undefined, numeros?: ReadonlyMap<string, number>): string {
  if (!fonte) return '“pergunta apagada”'
  const fixo = NOME_FONTE[fonte.tipo]
  if (fixo) return fixo
  const titulo = cortar(textoComCitacoes(fonte.titulo, numeros ?? new Map()), 50) || 'Pergunta sem título'
  return `“${titulo}”`
}

export function descreverCondicao(c: Condicao, porId: ReadonlyMap<string, Pergunta>, numeros?: ReadonlyMap<string, number>): string {
  const fonte = porId.get(c.fonte)
  const nome = nomeNaFrase(fonte, numeros)
  if (c.op === 'grupo_e') {
    const grupos = Array.isArray(c.valor) ? c.valor.map(String) : []
    return `${nome} é ${juntar(grupos, 'ou') || '?'}`
  }
  const rotulo = rotuloOperador(c.op, fonte)
  if (SEM_VALOR.includes(c.op)) return `${nome} ${rotulo}`
  const v = c.valor
  if (c.op === 'entre' && Array.isArray(v) && v.length === 2) return `${nome} ${rotulo} ${valorLegivel(fonte, v[0])} e ${valorLegivel(fonte, v[1])}`
  if (Array.isArray(v)) return `${nome} ${rotulo} ${juntar(v.map((x) => valorLegivel(fonte, x)), c.op === 'inclui_todos' ? 'e' : 'ou') || '?'}`
  return `${nome} ${rotulo} ${v === undefined || v === '' ? '?' : valorLegivel(fonte, v)}`
}

/** A condição em português: "NPS é detrator ou neutro" (todas: " e "; qualquer: " ou "). Sem condição: "Sempre". */
export function descreverGrupo(grupo: Grupo | null | undefined, itens: readonly Pergunta[]): string {
  if (!grupo?.condicoes?.length) return 'Sempre'
  const porId = new Map(itens.map((p) => [p.id, p]))
  const numeros = numerosDasPerguntas(itens)
  return grupo.condicoes.map((c) => descreverCondicao(c, porId, numeros)).join(grupo.juncao === 'qualquer' ? ' ou ' : ' e ')
}

/** "Mostrar se: NPS é detrator ou neutro". */
export function descreverMostrarSe(grupo: Grupo | null | undefined, itens: readonly Pergunta[]): string {
  return grupo?.condicoes?.length ? `Mostrar se: ${descreverGrupo(grupo, itens)}` : ''
}

/** "Se “É cliente?” é Não → ir para “Comentário”" (ou "→ ir para o fim"). */
export function descreverRegra(regra: Regra, itens: readonly Pergunta[]): string {
  const numeros = numerosDasPerguntas(itens)
  const destino = regra.para === FIM ? 'o fim' : itens.find((p) => p.id === regra.para)
  const para = typeof destino === 'string' ? destino : destino ? `“${cortar(nomeDoItem(destino, numeros, 50).replace(/^P\d+ · /, ''), 50)}”` : '“item apagado”'
  return `Se ${descreverGrupo(regra.se, itens)} → ir para ${para}`
}

// ── Fontes e destinos ───────────────────────────────────────────────────────

/** Perguntas que podem ser fonte: no `mostrar_se`, as anteriores; no `pular`, as anteriores e a própria; nos finais, todas. */
export function fontesPara(itens: readonly Pergunta[], onde: 'mostrar_se' | 'pular' | 'final', indice = -1): Pergunta[] {
  return itens.filter((p, i) => respondivel(p.tipo) && (onde === 'final' || i < indice || (onde === 'pular' && i === indice)))
}

/** Para onde uma regra de pular pode mandar: itens depois deste (sem quebra de página). */
export function destinosPara(itens: readonly Pergunta[], indice: number): Pergunta[] {
  return itens.filter((p, i) => i > indice && p.tipo !== 'quebra_pagina')
}

// ── Quem usa cada item (excluir, mover, trocar o tipo) ──────────────────────

export interface Uso {
  tipo: 'item' | 'final'
  id: string
  /** Onde: condição de mostrar, condição de uma regra, ou destino de uma regra. */
  onde: 'mostrar_se' | 'pular' | 'destino'
}

const condicoesDoGrupo = (g: Grupo | null | undefined): Condicao[] => (g && Array.isArray(g.condicoes) ? g.condicoes : [])

/** Os itens e finais cuja lógica usa o item `id` (como fonte de condição ou destino de regra). */
export function quemUsa(id: string, itens: readonly Pergunta[], finais: readonly Final[]): Uso[] {
  const usos: Uso[] = []
  for (const p of itens) {
    if (p.id === id) continue
    if (condicoesDoGrupo(p.logica?.mostrar_se).some((c) => c.fonte === id)) usos.push({ tipo: 'item', id: p.id, onde: 'mostrar_se' })
    const regras = p.logica?.pular ?? []
    if (regras.some((r) => condicoesDoGrupo(r.se).some((c) => c.fonte === id))) usos.push({ tipo: 'item', id: p.id, onde: 'pular' })
    if (regras.some((r) => r.para === id)) usos.push({ tipo: 'item', id: p.id, onde: 'destino' })
  }
  for (const f of finais) if (condicoesDoGrupo(f.mostrar_se).some((c) => c.fonte === id)) usos.push({ tipo: 'final', id: f.id, onde: 'mostrar_se' })
  return usos
}

/** Limpa a lógica do item: grupo sem condição vira "sempre"; regra sem condição sai; lógica vazia sai. */
function arrumarLogica(p: Pergunta) {
  if (!p.logica) return
  if (p.logica.mostrar_se && !condicoesDoGrupo(p.logica.mostrar_se).length) p.logica.mostrar_se = null
  if (p.logica.pular) p.logica.pular = p.logica.pular.filter((r) => condicoesDoGrupo(r.se).length > 0)
  if (!p.logica.mostrar_se && !p.logica.pular?.length) delete p.logica
}

/**
 * Tira da lógica tudo o que usa o item `id`: as condições com ele de fonte e as regras que mandam para ele. A condição
 * que ficar sem nada sai; o grupo que ficar vazio vira "sempre"; a regra sem condição sai. Devolve quantas mudanças.
 */
export function removerReferencias(id: string, itens: Pergunta[], finais: Final[]): number {
  let n = 0
  const tirar = (g: Grupo | null | undefined) => {
    if (!g || !Array.isArray(g.condicoes)) return
    const antes = g.condicoes.length
    g.condicoes = g.condicoes.filter((c) => c.fonte !== id)
    n += antes - g.condicoes.length
  }
  for (const p of itens) {
    if (!p.logica) continue
    tirar(p.logica.mostrar_se)
    for (const r of p.logica.pular ?? []) tirar(r.se)
    if (p.logica.pular) {
      const antes = p.logica.pular.length
      p.logica.pular = p.logica.pular.filter((r) => r.para !== id)
      n += antes - p.logica.pular.length
    }
    arrumarLogica(p)
  }
  for (const f of finais) {
    tirar(f.mostrar_se)
    if (f.mostrar_se && !condicoesDoGrupo(f.mostrar_se).length) f.mostrar_se = null
  }
  return n
}

const OPS_OPCAO: Operador[] = ['um_de', 'nenhum_de', 'inclui_algum', 'inclui_todos', 'nao_inclui_nenhum']

function cadaCondicaoDaFonte(fonteId: string, itens: readonly Pergunta[], finais: readonly Final[], fn: (c: Condicao) => void) {
  const grupos: (Grupo | null | undefined)[] = []
  for (const p of itens) {
    grupos.push(p.logica?.mostrar_se)
    for (const r of p.logica?.pular ?? []) grupos.push(r.se)
  }
  for (const f of finais) grupos.push(f.mostrar_se)
  for (const g of grupos) for (const c of condicoesDoGrupo(g)) if (c.fonte === fonteId && OPS_OPCAO.includes(c.op) && Array.isArray(c.valor)) fn(c)
}

/** Quantas condições usam a opção `opcao` da pergunta `fonteId`. */
export function usosDaOpcao(fonteId: string, opcao: string, itens: readonly Pergunta[], finais: readonly Final[]): number {
  let n = 0
  cadaCondicaoDaFonte(fonteId, itens, finais, (c) => {
    if ((c.valor as (string | number)[]).includes(opcao)) n++
  })
  return n
}

/** Renomear uma opção atualiza as condições que usam a opção. Devolve quantas mudaram. */
export function renomearOpcao(fonteId: string, antiga: string, nova: string, itens: Pergunta[], finais: Final[]): number {
  if (antiga === nova) return 0
  let n = 0
  cadaCondicaoDaFonte(fonteId, itens, finais, (c) => {
    const lista = c.valor as string[]
    if (lista.includes(antiga)) {
      c.valor = lista.map((o) => (o === antiga ? nova : o))
      n++
    }
  })
  return n
}

/**
 * Excluir uma opção usada: ela sai das condições; a condição que ficar sem opção sai (e o grupo que ficar vazio vira
 * "sempre"; a regra sem condição sai). Devolve quantas condições mudaram.
 */
export function removerOpcao(fonteId: string, opcao: string, itens: Pergunta[], finais: Final[]): number {
  let n = 0
  cadaCondicaoDaFonte(fonteId, itens, finais, (c) => {
    const lista = c.valor as string[]
    if (lista.includes(opcao)) {
      c.valor = lista.filter((o) => o !== opcao)
      n++
    }
  })
  if (!n) return 0
  const vazia = (c: Condicao) => c.fonte === fonteId && OPS_OPCAO.includes(c.op) && Array.isArray(c.valor) && !c.valor.length
  const limpar = (g: Grupo | null | undefined) => {
    if (g && Array.isArray(g.condicoes)) g.condicoes = g.condicoes.filter((c) => !vazia(c))
  }
  for (const p of itens) {
    if (!p.logica) continue
    limpar(p.logica.mostrar_se)
    for (const r of p.logica.pular ?? []) limpar(r.se)
    arrumarLogica(p)
  }
  for (const f of finais) {
    limpar(f.mostrar_se)
    if (f.mostrar_se && !condicoesDoGrupo(f.mostrar_se).length) f.mostrar_se = null
  }
  return n
}

/** Condições que usam a pergunta e deixam de valer com o tipo novo (operador que não existe nele). */
export function condicoesQueDeixamDeValer(fonteId: string, novo: Pick<Pergunta, 'tipo' | 'formato'>, itens: readonly Pergunta[], finais: readonly Final[]): number {
  const ops = operadoresDaFonte(novo)
  let n = 0
  const ver = (g: Grupo | null | undefined) => {
    for (const c of condicoesDoGrupo(g)) if (c.fonte === fonteId && !ops.includes(c.op)) n++
  }
  for (const p of itens) {
    ver(p.logica?.mostrar_se)
    for (const r of p.logica?.pular ?? []) ver(r.se)
  }
  for (const f of finais) ver(f.mostrar_se)
  return n
}

/** Quantas condições e regras um item tem (o ícone de lógica na lista). */
export function temLogica(p: Pergunta): boolean {
  return !!(p.logica?.mostrar_se?.condicoes?.length || p.logica?.pular?.length)
}
