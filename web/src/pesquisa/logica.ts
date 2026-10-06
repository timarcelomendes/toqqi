// Motor da lógica dos formulários (docs/api-etapa-5l.md §2). Vai na página pública: sem dependências. A API tem o mesmo
// motor em Python (api/toqqi/modulos/formularios/logica.py) e os dois passam pelos mesmos casos de
// docs/casos-logica-5l.json (tests/formulariosLogica.test.ts). O que é só do editor (frases em português, operadores
// por tipo) fica em src/modulos/formularios/logicaEditor.ts.
import type {
  Condicao,
  CondicaoPergunta,
  Final,
  Grupo,
  GrupoNota,
  Pergunta,
  Regra,
  Respostas,
  TipoPergunta,
  ValorResposta,
} from './tipos'

/** Tipos que podem ser a "nota principal" do formulário. */
export const TIPOS_NOTA: TipoPergunta[] = ['nps', 'csat', 'estrelas']

/** Itens que não recebem resposta: bloco de conteúdo e quebra de página. */
export const TIPOS_NAO_RESPONDIVEIS: TipoPergunta[] = ['conteudo', 'quebra_pagina']

/** O item é uma pergunta (recebe resposta)? Conteúdo e quebra de página não são. */
export function respondivel(tipo: TipoPergunta | string | null | undefined): boolean {
  return !!tipo && !TIPOS_NAO_RESPONDIVEIS.includes(tipo as TipoPergunta)
}

/**
 * Nota principal: 1ª pergunta `nps`; senão a 1ª `csat`/`estrelas`; senão nenhuma (personalizado).
 * Devolve o índice na lista (ou -1).
 */
export function indicePrincipal(perguntas: Pergunta[]): number {
  const nps = perguntas.findIndex((p) => p.tipo === 'nps')
  if (nps >= 0) return nps
  return perguntas.findIndex((p) => p.tipo === 'csat' || p.tipo === 'estrelas')
}

export function perguntaPrincipal(perguntas: Pergunta[]): Pergunta | null {
  const i = indicePrincipal(perguntas)
  return i >= 0 ? perguntas[i]! : null
}

export function tipoPrincipal(perguntas: Pergunta[]): 'nps' | 'csat' | 'personalizado' {
  const p = perguntaPrincipal(perguntas)
  if (!p) return 'personalizado'
  return p.tipo === 'nps' ? 'nps' : 'csat'
}

/** Faixa de valores de uma pergunta de nota/escala. */
export function faixa(p: Pick<Pergunta, 'tipo' | 'min' | 'max'>): { min: number; max: number } {
  switch (p.tipo) {
    case 'nps':
      return { min: 0, max: 10 }
    case 'csat':
    case 'estrelas':
      return { min: 1, max: 5 }
    case 'escala':
      return { min: p.min ?? 1, max: p.max ?? 5 }
    default:
      return { min: 0, max: 0 }
  }
}

/** Grupo de uma nota. NPS: 0–6 detrator, 7–8 neutro, 9–10 promotor. CSAT/estrelas: 1–2 insatisfeito, 3 neutro, 4–5 satisfeito. */
export function grupoDaNota(tipo: TipoPergunta, nota: number): GrupoNota | null {
  if (tipo === 'nps') return nota <= 6 ? 'detrator' : nota <= 8 ? 'neutro' : 'promotor'
  if (tipo === 'csat' || tipo === 'estrelas') return nota <= 2 ? 'insatisfeito' : nota === 3 ? 'neutro' : 'satisfeito'
  return null
}

/** Grupos possíveis para o tipo da nota principal, na ordem de exibição. */
export function gruposDoTipo(tipo: TipoPergunta | null | undefined): { valor: GrupoNota; rotulo: string }[] {
  if (tipo === 'nps')
    return [
      { valor: 'detrator', rotulo: 'Detratores (0 a 6)' },
      { valor: 'neutro', rotulo: 'Neutros (7 e 8)' },
      { valor: 'promotor', rotulo: 'Promotores (9 e 10)' },
    ]
  if (tipo === 'csat' || tipo === 'estrelas')
    return [
      { valor: 'insatisfeito', rotulo: 'Insatisfeitos (1 e 2)' },
      { valor: 'neutro', rotulo: 'Neutros (3)' },
      { valor: 'satisfeito', rotulo: 'Satisfeitos (4 e 5)' },
    ]
  return []
}

// ── Texto e números (§2.1) ──────────────────────────────────────────────────

/** NFD, sem marcas combinantes (acentos), minúsculas, sem espaços nas pontas e com os repetidos juntados. */
export function norm(s: string): string {
  return s
    .normalize('NFD')
    .replace(/\p{Mn}/gu, '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ')
}

// Sinal, dígitos e no máximo um ponto decimal (o mesmo padrão do motor da API): sem expoente, sem "inf"/"nan".
const RE_NUMERO = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/

/**
 * Número de um texto (`texto_curto` com formato número): com vírgula, tira os pontos e troca a vírgula por ponto
 * ("1.250,5" → 1250.5); sem vírgula, usa como está ("12.5" → 12.5). Sem número: null (a condição é falsa).
 */
export function numeroDoTexto(texto: string): number | null {
  if (typeof texto !== 'string') return null
  let t = texto.trim()
  if (t.includes(',')) t = t.replace(/\./g, '').replace(/,/g, '.')
  return RE_NUMERO.test(t) ? Number(t) : null
}

/** AAAA-MM-DD de um dia que existe. */
export function dataValida(v: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return false
  const [a, m, d] = v.split('-').map(Number) as [number, number, number]
  const dt = new Date(Date.UTC(a, m - 1, d))
  return dt.getUTCFullYear() === a && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d
}

// ── Condições (§2.2 e §2.3) ─────────────────────────────────────────────────

export type ItensPorId = ReadonlyMap<string, Pergunta>

/** Itens por id (id repetido, que a validação recusa: vale o último, como no motor da API). */
export function indexar(itens: readonly Pergunta[]): Map<string, Pergunta> {
  const mapa = new Map<string, Pergunta>()
  for (const it of itens) if (it && typeof it.id === 'string') mapa.set(it.id, it)
  return mapa
}

/**
 * A resposta conta? Vazia (null, texto em branco, lista vazia) ou inválida para o tipo (nota fora da faixa, opção que
 * não existe, data que não existe...) conta como sem resposta (§2.3).
 */
export function respostaValida(item: Pick<Pergunta, 'tipo' | 'min' | 'max' | 'opcoes'>, v: unknown): boolean {
  if (v === undefined || v === null) return false
  switch (item.tipo) {
    case 'nps':
    case 'csat':
    case 'estrelas':
    case 'escala': {
      if (typeof v !== 'number' || !Number.isInteger(v)) return false
      const { min, max } = faixa(item)
      return v >= min && v <= max
    }
    case 'texto_curto':
    case 'comentario':
      return typeof v === 'string' && v.trim() !== ''
    // Sem a lista de opções no item, qualquer texto conta (como no motor da API).
    case 'escolha_unica':
      return typeof v === 'string' && v !== '' && (!Array.isArray(item.opcoes) || item.opcoes.includes(v))
    case 'escolha_multipla':
      return Array.isArray(v) && v.length > 0 && v.every((x) => typeof x === 'string' && (!Array.isArray(item.opcoes) || item.opcoes.includes(x)))
    case 'sim_nao':
      return typeof v === 'boolean'
    case 'data':
      return typeof v === 'string' && dataValida(v)
    default:
      return false
  }
}

function compararNumero(x: number, op: Condicao['op'], valor: unknown): boolean {
  if (op === 'entre') {
    if (!Array.isArray(valor) || valor.length !== 2) return false
    const [a, b] = valor as unknown[]
    return typeof a === 'number' && typeof b === 'number' && x >= a && x <= b
  }
  if (typeof valor !== 'number') return false
  switch (op) {
    case 'igual':
      return x === valor
    case 'diferente':
      return x !== valor
    case 'menor':
      return x < valor
    case 'menor_igual':
      return x <= valor
    case 'maior':
      return x > valor
    case 'maior_igual':
      return x >= valor
    default:
      return false
  }
}

function compararTexto(x: string, op: Condicao['op'], valor: unknown): boolean {
  if (typeof valor !== 'string') return false
  const a = norm(x)
  const b = norm(valor)
  switch (op) {
    case 'contem':
      return a.includes(b)
    case 'nao_contem':
      return !a.includes(b)
    case 'igual':
      return a === b
    case 'diferente':
      return a !== b
    case 'comeca_com':
      return a.startsWith(b)
    case 'termina_com':
      return a.endsWith(b)
    default:
      return false
  }
}

/** Datas AAAA-MM-DD comparadas como texto. */
function compararData(x: string, op: Condicao['op'], valor: unknown): boolean {
  if (op === 'entre') {
    if (!Array.isArray(valor) || valor.length !== 2) return false
    const [a, b] = valor as unknown[]
    return typeof a === 'string' && typeof b === 'string' && x >= a && x <= b
  }
  if (typeof valor !== 'string') return false
  switch (op) {
    case 'igual':
      return x === valor
    case 'diferente':
      return x !== valor
    case 'menor':
      return x < valor
    case 'menor_igual':
      return x <= valor
    case 'maior':
      return x > valor
    case 'maior_igual':
      return x >= valor
    default:
      return false
  }
}

/** A lista da condição (opções, grupos); vazia ou de outro tipo = a condição é falsa. */
const lista = (valor: unknown): unknown[] | null => (Array.isArray(valor) && valor.length ? valor : null)

/**
 * Uma condição com os valores do caminho até aqui. Fonte sem resposta (não respondida, fora do caminho, com valor
 * inválido ou que não existe): só `nao_respondida` vale; todo outro operador é falso, inclusive os negativos.
 */
export function avaliarCondicao(c: Condicao, valores: Respostas, itensPorId: ItensPorId): boolean {
  if (!c || typeof c !== 'object') return false
  const item = itensPorId.get(c.fonte)
  const v: unknown = item && respondivel(item.tipo) ? valores[c.fonte] : undefined
  const respondida = !!item && respondivel(item.tipo) && respostaValida(item, v)
  if (c.op === 'respondida') return respondida
  if (c.op === 'nao_respondida') return !respondida
  if (!respondida || !item) return false
  const valor = c.valor
  switch (item.tipo) {
    case 'nps':
    case 'csat':
    case 'estrelas':
    case 'escala': {
      if (c.op === 'grupo_e') {
        const g = grupoDaNota(item.tipo, v as number)
        return !!g && !!lista(valor)?.includes(g)
      }
      return compararNumero(v as number, c.op, valor)
    }
    case 'texto_curto':
      if (item.formato === 'numero') {
        const n = numeroDoTexto(v as string)
        return n !== null && compararNumero(n, c.op, valor)
      }
      return compararTexto(v as string, c.op, valor)
    case 'comentario':
      return compararTexto(v as string, c.op, valor)
    case 'escolha_unica': {
      const alvo = lista(valor)
      if (!alvo) return false
      if (c.op === 'um_de') return alvo.includes(v)
      if (c.op === 'nenhum_de') return !alvo.includes(v)
      return false
    }
    case 'escolha_multipla': {
      const marcadas = v as string[]
      const alvo = lista(valor)
      if (!alvo) return false
      if (c.op === 'inclui_algum') return alvo.some((o) => marcadas.includes(o as string))
      if (c.op === 'inclui_todos') return alvo.every((o) => marcadas.includes(o as string))
      if (c.op === 'nao_inclui_nenhum') return !alvo.some((o) => marcadas.includes(o as string))
      return false
    }
    case 'sim_nao':
      return c.op === 'igual' && typeof valor === 'boolean' && v === valor
    case 'data':
      return compararData(v as string, c.op, valor)
    default:
      return false
  }
}

/**
 * `todas`: todas as condições valem; `qualquer`: alguma vale. Grupo null ou ausente vale como verdadeiro, e o grupo sem
 * condições também (o publicado nunca tem: a validação recusa), como no motor da API.
 */
export function avaliarGrupo(grupo: Grupo | null | undefined, valores: Respostas, itensPorId: ItensPorId): boolean {
  if (!grupo || typeof grupo !== 'object') return true
  const condicoes = Array.isArray(grupo.condicoes) ? grupo.condicoes : []
  if (!condicoes.length) return true
  const vale = (c: Condicao) => avaliarCondicao(c, valores, itensPorId)
  return grupo.juncao === 'qualquer' ? condicoes.some(vale) : condicoes.every(vale)
}

// ── Formato antigo (§2.8) ───────────────────────────────────────────────────

/** `condicao` antiga → `logica.mostrar_se`, com a fonte na nota principal. */
export function converterCondicaoLegada(condicao: CondicaoPergunta | null | undefined, idPrincipal: string | null | undefined): Grupo | null {
  if (!condicao || !idPrincipal) return null
  if (condicao.tipo === 'grupo') {
    if (!Array.isArray(condicao.grupos)) return null
    return { juncao: 'todas', condicoes: [{ fonte: idPrincipal, op: 'grupo_e', valor: [...condicao.grupos] }] }
  }
  if (condicao.tipo === 'nota') {
    const op = condicao.operador === '<=' ? 'menor_igual' : condicao.operador === '>=' ? 'maior_igual' : null
    return op ? { juncao: 'todas', condicoes: [{ fonte: idPrincipal, op, valor: condicao.valor }] } : null
  }
  return null
}

/** O `mostrar_se` do item; sem ele, a `condicao` antiga convertida (o que a API faz na entrada). */
export function mostrarSeDoItem(item: Pergunta, idPrincipal: string | null): Grupo | null {
  const g = item.logica?.mostrar_se
  if (g) return g
  return item.condicao ? converterCondicaoLegada(item.condicao, idPrincipal) : null
}

// ── Caminho e final (§2.4 e §2.5) ───────────────────────────────────────────

export interface Percurso {
  /** Ids dos itens no caminho, em ordem, sem as quebras de página. */
  ids: string[]
  /** Só as respostas das perguntas que estão no caminho. */
  valores: Respostas
}

/**
 * Percorre os itens uma vez, para frente: item escondido não entra nem dispara regras; depois de cada pergunta vale a
 * 1ª regra de pular verdadeira ("fim" para; um id leva até ele). Destino que não existe ou que não está à frente é
 * ignorado (não há laço).
 */
export function percorrer(itens: readonly Pergunta[], respostas: Respostas): Percurso {
  const lista = Array.isArray(itens) ? itens : []
  const porId = indexar(lista)
  const ip = indicePrincipal(lista as Pergunta[])
  const idPrincipal = ip >= 0 ? lista[ip]!.id : null
  const posicao = new Map<string, number>()
  lista.forEach((it, i) => {
    if (it && typeof it.id === 'string') posicao.set(it.id, i)
  })
  const ids: string[] = []
  const valores: Respostas = {}
  let i = 0
  while (i < lista.length) {
    const it = lista[i]!
    if (!it || typeof it.id !== 'string' || it.tipo === 'quebra_pagina') {
      i++
      continue
    }
    if (!avaliarGrupo(mostrarSeDoItem(it, idPrincipal), valores, porId)) {
      i++
      continue
    }
    ids.push(it.id)
    // Leitura direta (não `hasOwnProperty`): com as respostas reativas do Vue, a leitura é o que o caminho acompanha.
    const valor = respondivel(it.tipo) ? respostas[it.id] : undefined
    if (valor !== undefined) valores[it.id] = valor as ValorResposta
    const regras: Regra[] = Array.isArray(it.logica?.pular) ? it.logica!.pular! : []
    const regra = regras.find((r) => r && avaliarGrupo(r.se, valores, porId))
    if (regra) {
      if (regra.para === 'fim') break
      const j = posicao.get(regra.para)
      if (j !== undefined && j > i) {
        i = j
        continue
      }
    }
    i++
  }
  return { ids, valores }
}

/** Ids dos itens no caminho, em ordem, sem as quebras de página. */
export function caminho(itens: readonly Pergunta[], respostas: Respostas): string[] {
  return percorrer(itens, respostas).ids
}

/** Id do 1º final cuja condição vale com as respostas do caminho; null = final padrão do tema. */
export function escolherFinal(
  finais: readonly Pick<Final, 'id' | 'mostrar_se'>[] | null | undefined,
  itens: readonly Pergunta[],
  respostas: Respostas,
): string | null {
  if (!finais?.length) return null
  const { valores } = percorrer(itens, respostas)
  const porId = indexar(itens)
  for (const f of finais) if (avaliarGrupo(f.mostrar_se ?? null, valores, porId)) return f.id
  return null
}

// ── Citações (§2.7) ─────────────────────────────────────────────────────────

/** `{{ID}}`: a resposta de uma pergunta anterior. */
export const RE_CITACAO = /\{\{([A-Za-z0-9_-]{1,32})\}\}/g

const LIMITE_CITACAO = 200

function juntarComE(itens: string[]): string {
  if (itens.length <= 1) return itens[0] ?? ''
  return `${itens.slice(0, -1).join(', ')} e ${itens[itens.length - 1]}`
}

/**
 * A resposta em texto, como entra numa citação: número; a opção; "A, B e C"; "Sim"/"Não"; DD/MM/AAAA; texto aparado e
 * cortado em 200 com "…". Sem resposta (ou inválida): "".
 */
export function formatarResposta(item: Pergunta | null | undefined, valor: unknown): string {
  if (!item || !respondivel(item.tipo) || !respostaValida(item, valor)) return ''
  switch (item.tipo) {
    case 'nps':
    case 'csat':
    case 'estrelas':
    case 'escala':
      return String(valor)
    case 'escolha_unica':
      return valor as string
    case 'escolha_multipla':
      return juntarComE(valor as string[])
    case 'sim_nao':
      return valor ? 'Sim' : 'Não'
    case 'data': {
      const [a, m, d] = (valor as string).split('-')
      return `${d}/${m}/${a}`
    }
    default: {
      const t = (valor as string).trim()
      const letras = Array.from(t)
      return letras.length > LIMITE_CITACAO ? `${letras.slice(0, LIMITE_CITACAO).join('')}…` : t
    }
  }
}

/** Escapa `& < > " '` (o valor citado entra no HTML como texto). */
export function escaparHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}

/** Troca as citações com valores já calculados (os do caminho). Para muitos textos de uma vez, sem refazer o caminho. */
export function citarComValores(texto: string | null | undefined, itensPorId: ItensPorId, valores: Respostas, html = false): string {
  if (!texto) return ''
  if (!texto.includes('{{')) return texto
  return texto.replace(RE_CITACAO, (_m, id: string) => {
    const s = formatarResposta(itensPorId.get(id), valores[id])
    return html ? escaparHtml(s) : s
  })
}

/** Citações num texto puro (títulos, descrições): `{{ID}}` vira a resposta; fora do caminho ou sem resposta, "". */
export function citar(texto: string | null | undefined, itens: readonly Pergunta[], respostas: Respostas): string {
  if (!texto) return ''
  if (!texto.includes('{{')) return texto
  return citarComValores(texto, indexar(itens), percorrer(itens, respostas).valores)
}

/** Citações num HTML: o valor entra escapado (depois, o HTML todo passa pelo `limparHtml`). */
export function citarHtml(html: string | null | undefined, itens: readonly Pergunta[], respostas: Respostas): string {
  if (!html) return ''
  if (!html.includes('{{')) return html
  return citarComValores(html, indexar(itens), percorrer(itens, respostas).valores, true)
}

// ── Página pública ──────────────────────────────────────────────────────────

/** Itens no caminho (perguntas e conteúdo, sem as quebras), com as respostas atuais. */
export function perguntasVisiveis(perguntas: Pergunta[], respostas: Respostas): Pergunta[] {
  const porId = indexar(perguntas)
  return caminho(perguntas, respostas).map((id) => porId.get(id)!)
}

export interface PaginaDoCaminho {
  /** Número da página no formulário (0 = antes da 1ª quebra), mesmo se outras páginas estiverem vazias. */
  numero: number
  itens: Pergunta[]
}

/** O caminho agrupado pelas quebras de página; páginas sem item no caminho somem. */
export function paginasDoCaminho(perguntas: Pergunta[], ids: readonly string[]): PaginaDoCaminho[] {
  const naRota = new Set(ids)
  const paginas: PaginaDoCaminho[] = [{ numero: 0, itens: [] }]
  for (const p of perguntas) {
    if (p.tipo === 'quebra_pagina') {
      paginas.push({ numero: paginas.length, itens: [] })
      continue
    }
    if (naRota.has(p.id)) paginas[paginas.length - 1]!.itens.push(p)
  }
  return paginas.filter((pg) => pg.itens.length > 0)
}

/** Divide o caminho em páginas pelas quebras (páginas vazias somem). */
export function paginasVisiveis(perguntas: Pergunta[], respostas: Respostas): Pergunta[][] {
  return paginasDoCaminho(perguntas, caminho(perguntas, respostas)).map((pg) => pg.itens)
}

/** Só as respostas das perguntas do caminho, preenchidas (texto sem espaços sobrando): o que vai para a API. */
export function respostasParaEnvio(perguntas: Pergunta[], respostas: Respostas): Respostas {
  const porId = indexar(perguntas)
  const saida: Respostas = {}
  for (const id of caminho(perguntas, respostas)) {
    if (!respondivel(porId.get(id)?.tipo)) continue
    const v = respostas[id]
    if (v === undefined || v === null) continue
    if (typeof v === 'string' && !v.trim()) continue
    if (Array.isArray(v) && !v.length) continue
    saida[id] = typeof v === 'string' ? v.trim() : v
  }
  return saida
}

// ── Compatibilidade (formato antigo) ────────────────────────────────────────

/**
 * Avalia uma condição antiga. Sem condição: sempre aparece. Com condição e sem nota principal respondida: fica
 * escondida.
 */
export function condicaoAtende(
  condicao: CondicaoPergunta | null | undefined,
  principal: Pergunta | null,
  nota: number | null | undefined,
): boolean {
  if (!condicao) return true
  if (!principal || typeof nota !== 'number' || Number.isNaN(nota)) return false
  const grupo = converterCondicaoLegada(condicao, principal.id)
  return avaliarGrupo(grupo, { [principal.id]: nota }, new Map([[principal.id, principal]]))
}

/** Nota principal já respondida (ou null). */
export function notaPrincipal(perguntas: Pergunta[], respostas: Respostas): number | null {
  const p = perguntaPrincipal(perguntas)
  if (!p) return null
  const v = respostas[p.id]
  return typeof v === 'number' ? v : null
}

/** O item aparece para quem responde, com as respostas atuais? (A quebra de página sempre "aparece".) */
export function perguntaVisivel(p: Pergunta, perguntas: Pergunta[], respostas: Respostas): boolean {
  if (p.tipo === 'quebra_pagina') return true
  return caminho(perguntas, respostas).includes(p.id)
}

/** A condição antiga pode ser usada nesta posição? Só depois da nota principal. */
export function podeTerCondicao(indice: number, perguntas: Pergunta[]): boolean {
  const ip = indicePrincipal(perguntas)
  return ip >= 0 && indice > ip
}
