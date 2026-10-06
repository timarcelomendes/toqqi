// Confere o formulário no editor com as mesmas regras da API (docs/api-etapa-5l.md §2.6), para os problemas
// aparecerem antes de o rascunho voltar do servidor. As chaves e as mensagens seguem as da API
// (`perguntas.<i>.<campo>`, `perguntas.<i>.logica`, `finais.<i>.<campo>`, `tema.<campo>` e `perguntas`); cada problema
// também diz o item e, na lógica, a regra e a condição, para o painel e as linhas do construtor.
import { dataValida, faixa, gruposDoTipo, indicePrincipal, numeroDoTexto, respondivel, RE_CITACAO } from '@/pesquisa/logica'
import { TEMA_PADRAO } from '@/pesquisa/tipos'
import type { Condicao, Final, Grupo, Pergunta, Tema } from '@/api/tipos'
import { ehNota, ehTextoNumero, FIM, MAX_CONDICOES, MAX_FINAIS, MAX_REGRAS, operadoresDaFonte, SEM_VALOR, textoSemTags } from './logicaEditor'

export const LIMITE_PERGUNTAS = 60
export const LIMITE_CONTEUDOS = 30
export const LIMITE_ITENS = 120
export const LIMITE_HTML = 20000
export const MSG_HTML_GRANDE = 'Este conteúdo está grande demais (máx. 20.000 caracteres).'
export const MSG_URL = 'Use um endereço https:// (até 500 caracteres).'
const MSG_NOTA_PRINCIPAL = 'A nota principal sempre aparece; tire a condição dela.'
const MSG_ANTES_DA_PRINCIPAL = 'Perguntas antes da nota principal não podem pular (a nota principal não pode ficar de fora).'

export type AlvoProblema =
  | { tipo: 'item'; id: string; indice: number }
  | { tipo: 'final'; id: string; indice: number }
  | { tipo: 'tema' }
  | { tipo: 'formulario' }

export interface Problema {
  chave: string
  mensagem: string
  /** Aviso (citação que vai sair vazia): aparece, mas não impede publicar. */
  aviso?: boolean
  alvo: AlvoProblema
  /** O campo do item (titulo, opcoes, logica, html, botao.url...). */
  campo?: string
  /** Na lógica: onde (mostrar ou regra N) e a condição (1, 2…). */
  logica?: { onde: 'mostrar_se' | 'pular'; regra?: number; condicao?: number }
}

export interface DocumentoValidar {
  perguntas: Pergunta[]
  tema?: Tema
  finais?: Final[]
}

export interface OpcoesValidar {
  nome?: string
  /** Formulário padrão: a nota principal não muda de tipo (regra de hoje, 409 `formulario_padrao`). */
  padrao?: 'nps' | 'csat' | null
}

const texto = (v: unknown) => (typeof v === 'string' ? v.trim() : '')

function urlHttps(url: string): boolean {
  if (!url || url.length > 500 || !url.startsWith('https://') || /[\s\u0000-\u001f]/.test(url)) return false
  try {
    const u = new URL(url)
    return u.protocol === 'https:' && !!u.hostname
  } catch {
    return false
  }
}

/** O HTML não mostra nada (sem texto, imagem nem linha), como `sem_conteudo` da API. */
export function htmlVazio(html: string | null | undefined): boolean {
  if (!html) return true
  if (/<img|<hr/i.test(html)) return false
  return !textoSemTags(html)
}

/** Valida o documento todo. Devolve a lista de problemas (erros e avisos). */
export function validarDocumento(doc: DocumentoValidar, opcoes: OpcoesValidar = {}): Problema[] {
  const problemas: Problema[] = []
  const itens = doc.perguntas ?? []
  const finais = doc.finais ?? []
  const tema = { ...TEMA_PADRAO, ...(doc.tema ?? {}) }
  const add = (p: Problema) => problemas.push(p)
  const formulario = (mensagem: string) => add({ chave: 'perguntas', mensagem, alvo: { tipo: 'formulario' } })

  if (opcoes.nome !== undefined && !opcoes.nome.trim()) add({ chave: 'nome', mensagem: 'Dê um nome para o formulário.', alvo: { tipo: 'formulario' } })

  // Limites (§1.6)
  const respondiveis = itens.filter((p) => respondivel(p.tipo))
  if (itens.length > LIMITE_ITENS) formulario(`Use no máximo ${LIMITE_ITENS} itens (perguntas, blocos de conteúdo e quebras).`)
  if (respondiveis.length > LIMITE_PERGUNTAS) formulario(`Use no máximo ${LIMITE_PERGUNTAS} perguntas.`)
  if (itens.filter((p) => p.tipo === 'conteudo').length > LIMITE_CONTEUDOS) formulario(`Use no máximo ${LIMITE_CONTEUDOS} blocos de conteúdo.`)

  const ip = indicePrincipal(itens)
  const principal = ip >= 0 ? itens[ip]! : null
  if (opcoes.padrao && (principal ? (principal.tipo === 'nps' ? 'nps' : 'csat') : null) !== opcoes.padrao) {
    formulario(`Este é o formulário padrão de ${opcoes.padrao.toUpperCase()}: a nota principal precisa continuar sendo ${opcoes.padrao === 'nps' ? 'NPS' : 'CSAT (carinhas ou estrelas)'}.`)
  }
  const posicao = new Map(itens.map((p, i) => [p.id, i]))
  const ids = new Set<string>()

  itens.forEach((p, i) => {
    const alvo: AlvoProblema = { tipo: 'item', id: p.id, indice: i }
    const erro = (campo: string, mensagem: string, extra: Partial<Problema> = {}) =>
      add({ chave: `perguntas.${i}.${campo}`, mensagem, alvo, campo, ...extra })
    if (ids.has(p.id)) erro('id', 'Identificador repetido.')
    ids.add(p.id)

    // Campos do item
    if (p.tipo === 'conteudo') {
      if (texto(p.titulo).length > 120) erro('titulo', 'Use no máximo 120 caracteres.')
      if ((p.html ?? '').length > LIMITE_HTML) erro('html', MSG_HTML_GRANDE)
      else if (htmlVazio(p.html)) erro('html', 'Escreva o conteúdo do bloco.')
    } else if (p.tipo !== 'quebra_pagina') {
      const titulo = texto(p.titulo)
      if (!titulo) erro('titulo', 'Escreva o título da pergunta.')
      else if (titulo.length > 300) erro('titulo', 'Use no máximo 300 caracteres.')
      if (texto(p.descricao).length > 1000) erro('descricao', 'Use no máximo 1000 caracteres.')
    }
    if (p.tipo === 'escolha_unica' || p.tipo === 'escolha_multipla') {
      const lista = (p.opcoes ?? []).map((o) => o.trim())
      if (lista.some((o) => o.length > 200)) erro('opcoes', 'Cada opção pode ter no máximo 200 caracteres.')
      else if (lista.some((o) => !o)) erro('opcoes', 'Preencha todas as opções.')
      else if (new Set(lista.map((o) => o.toLocaleLowerCase('pt-BR'))).size !== lista.length) erro('opcoes', 'Há opções repetidas.')
      else if (lista.length < 2 || lista.length > 30) erro('opcoes', 'Use de 2 a 30 opções.')
      if (p.tipo === 'escolha_multipla' && p.max_selecoes !== null && p.max_selecoes !== undefined) {
        const n = Math.max(lista.length, 2)
        if (!Number.isInteger(p.max_selecoes) || p.max_selecoes < 2 || p.max_selecoes > n) erro('max_selecoes', `O máximo de opções precisa ficar entre 2 e ${n}.`)
      }
    }
    if (p.tipo === 'escala') {
      const min = p.min ?? 1
      const max = p.max ?? 5
      if (min !== 0 && min !== 1) erro('min', 'O mínimo da escala deve ser 0 ou 1.')
      else if (max > 10 || max <= min + 1) erro('max', `O fim da escala vai de ${min + 2} a 10.`)
    }
    if ((p.tipo === 'texto_curto' || p.tipo === 'comentario') && texto(p.placeholder).length > 120) erro('placeholder', 'Use no máximo 120 caracteres.')
    for (const r of ['rotulo_min', 'rotulo_max'] as const) if (texto(p[r]).length > 60) erro(r, 'Use no máximo 60 caracteres.')

    // Formato antigo (condicao): as mensagens e a chave de antes (§2.8)
    if (p.condicao && !p.logica?.mostrar_se) {
      if (!principal || i <= ip) erro('condicao', 'A condição só pode ser usada em perguntas depois da nota principal.')
      else if (p.condicao.tipo === 'grupo') {
        const validos = new Set(gruposDoTipo(principal.tipo).map((g) => g.valor))
        if (!p.condicao.grupos?.length || p.condicao.grupos.some((g) => !validos.has(g))) erro('condicao', `Escolha grupos válidos: ${[...validos].join(', ')}.`)
      } else if (p.condicao.tipo === 'nota') {
        const { min, max } = faixa(principal)
        const v = p.condicao.valor
        if (typeof v !== 'number' || v < min || v > max) erro('condicao', `A nota da condição deve ficar entre ${min} e ${max}.`)
      }
    }

    // Lógica (§2.6, itens 1 a 5)
    const lg = p.logica
    if (!lg || p.tipo === 'quebra_pagina') return
    if (lg.mostrar_se) {
      if (i === ip) erro('logica', MSG_NOTA_PRINCIPAL, { logica: { onde: 'mostrar_se' } })
      else validarGrupo(lg.mostrar_se, 'mostrar_se', i, undefined, (mensagem, condicao) => erro('logica', mensagem, { logica: { onde: 'mostrar_se', condicao } }))
    }
    const regras = lg.pular ?? []
    if (!regras.length) return
    if (p.tipo === 'conteudo') erro('logica', 'Blocos de conteúdo não podem pular; a regra fica na pergunta.', { logica: { onde: 'pular' } })
    else if (ip >= 0 && i < ip) erro('logica', MSG_ANTES_DA_PRINCIPAL, { logica: { onde: 'pular' } })
    if (regras.length > MAX_REGRAS) erro('logica', `Use no máximo ${MAX_REGRAS} regras em cada pergunta.`, { logica: { onde: 'pular' } })
    regras.forEach((regra, r) => {
      const n = r + 1
      const naRegra = (mensagem: string, condicao?: number) => erro('logica', mensagem, { logica: { onde: 'pular', regra: n, condicao } })
      if (!regra.se) naRegra(`Adicione pelo menos uma condição à regra ${n}.`)
      else validarGrupo(regra.se, 'pular', i, n, naRegra)
      const para = regra.para
      if (para === FIM) return
      const j = para ? posicao.get(para) : undefined
      if (!para) naRegra(`Escolha para onde a regra ${n} manda.`)
      else if (j === undefined) naRegra(`A regra ${n} manda para um item que não existe mais.`)
      else if (j <= i) naRegra(`A regra ${n} manda para uma pergunta que vem antes desta (só dá para pular para frente).`)
      else if (itens[j]!.tipo === 'quebra_pagina') naRegra(`A regra ${n} manda para uma quebra de página; escolha uma pergunta ou o fim.`)
    })
  })

  // Citações (§2.7): avisos, não bloqueiam
  const anteriores = new Set<string>()
  itens.forEach((p, i) => {
    const campos = p.tipo === 'conteudo' ? (['html'] as const) : (['titulo', 'descricao'] as const)
    for (const campo of campos) {
      const ruim = citacaoForaDoLugar(p[campo], anteriores)
      if (ruim) add({ chave: `perguntas.${i}.${campo}`, mensagem: `A citação {{${ruim}}} não aponta para uma pergunta anterior; ela vai sair vazia.`, aviso: true, alvo: { tipo: 'item', id: p.id, indice: i }, campo })
    }
    if (respondivel(p.tipo)) anteriores.add(p.id)
  })

  // Finais (§2.6, item 6)
  if (finais.length > MAX_FINAIS) add({ chave: 'finais', mensagem: `Use no máximo ${MAX_FINAIS} finais.`, alvo: { tipo: 'formulario' } })
  finais.forEach((f, j) => {
    const alvo: AlvoProblema = { tipo: 'final', id: f.id, indice: j }
    const erro = (campo: string, mensagem: string, extra: Partial<Problema> = {}) => add({ chave: `finais.${j}.${campo}`, mensagem, alvo, campo, ...extra })
    const nome = texto(f.nome)
    if (!nome) erro('nome', 'Dê um nome ao final (só a sua equipe vê).')
    else if (nome.length > 60) erro('nome', 'Use no máximo 60 caracteres.')
    const titulo = texto(f.titulo)
    if (!titulo) erro('titulo', 'Escreva o título do final.')
    else if (titulo.length > 120) erro('titulo', 'Use no máximo 120 caracteres.')
    if ((f.html ?? '').length > LIMITE_HTML) erro('html', MSG_HTML_GRANDE)
    if (f.botao) {
      const t = texto(f.botao.texto)
      const u = texto(f.botao.url)
      if (t || u) {
        if (!t) erro('botao.texto', 'Escreva o texto do botão.')
        else if (t.length > 40) erro('botao.texto', 'Use no máximo 40 caracteres.')
        if (!urlHttps(u)) erro('botao.url', MSG_URL)
      }
    }
    if (f.mostrar_se) validarGrupo(f.mostrar_se, 'final', -1, undefined, (mensagem, condicao) => add({ chave: `finais.${j}.mostrar_se`, mensagem, alvo, campo: 'mostrar_se', logica: { onde: 'mostrar_se', condicao } }))
    for (const campo of ['titulo', 'html'] as const) {
      const ruim = citacaoForaDoLugar(f[campo], new Set(itens.filter((p) => respondivel(p.tipo)).map((p) => p.id)))
      if (ruim) add({ chave: `finais.${j}.${campo}`, mensagem: `A citação {{${ruim}}} não aponta para uma pergunta do formulário; ela vai sair vazia.`, aviso: true, alvo, campo })
    }
  })

  // Tema
  const daTema = (campo: string, mensagem: string) => add({ chave: `tema.${campo}`, mensagem, alvo: { tipo: 'tema' }, campo })
  if (!/^#[0-9a-fA-F]{6}$/.test(tema.cor ?? '')) daTema('cor', 'Use uma cor no formato #rrggbb.')
  const logo = texto(tema.logo_url)
  if (logo && (logo.length > 500 || !/^https?:\/\//i.test(logo))) daTema('logo_url', MSG_URL)
  const limites: Record<string, number> = { titulo_abertura: 120, texto_abertura: 1000, texto_botao: 40, titulo_final: 120, texto_final: 1000 }
  for (const [campo, max] of Object.entries(limites)) if (texto((tema as unknown as Record<string, unknown>)[campo]).length > max) daTema(campo, `Use no máximo ${max} caracteres.`)

  return problemas

  // ── condições ──
  function validarGrupo(grupo: Grupo, modo: 'mostrar_se' | 'pular' | 'final', pos: number, regra: number | undefined, erro: (m: string, condicao?: number) => void) {
    const condicoes = Array.isArray(grupo.condicoes) ? grupo.condicoes : []
    if (!condicoes.length) erro(regra ? `Adicione pelo menos uma condição à regra ${regra}.` : 'Adicione pelo menos uma condição.')
    if (condicoes.length > MAX_CONDICOES) erro(`Use no máximo ${MAX_CONDICOES} condições em cada grupo.`)
    condicoes.forEach((c, k) => {
      const n = k + 1
      const rotulo = regra ? `Na regra ${regra}, a condição ${n}` : `A condição ${n}`
      const escolha = (o: string) => erro(regra ? `Na regra ${regra}, escolha ${o} da condição ${n}.` : `Escolha ${o} da condição ${n}.`, n)
      if (!c.fonte) return escolha('a pergunta')
      const j = posicao.get(c.fonte)
      if (j === undefined) return erro(`${rotulo} usa uma pergunta que não existe mais.`, n)
      const fonte = itens[j]!
      if (fonte.tipo === 'conteudo') return erro(`${rotulo} usa um bloco de conteúdo (só perguntas servem de condição).`, n)
      if (fonte.tipo === 'quebra_pagina') return erro(`${rotulo} usa uma quebra de página (só perguntas servem de condição).`, n)
      if (modo === 'mostrar_se' && j === pos) return erro(`${rotulo} usa esta mesma pergunta (só as anteriores servem de condição).`, n)
      if (modo !== 'final' && j > pos) return erro(`${rotulo} usa uma pergunta que vem depois desta.`, n)
      if (!c.op) return escolha('a comparação')
      if (!operadoresDaFonte(fonte).includes(c.op)) return erro(`${rotulo} usa uma comparação que não vale para este tipo de pergunta.`, n)
      if (SEM_VALOR.includes(c.op)) return
      const problema = problemaDoValor(fonte, c, rotulo)
      if (problema) erro(problema, n)
    })
  }
}

/** O 1º `{{ID}}` do texto que não está em `validos` (ou null). */
function citacaoForaDoLugar(t: string | null | undefined, validos: ReadonlySet<string>): string | null {
  if (!t || !t.includes('{{')) return null
  for (const m of t.matchAll(RE_CITACAO)) if (!validos.has(m[1]!)) return m[1]!
  return null
}

const inteiro = (v: unknown): v is number => typeof v === 'number' && Number.isInteger(v)
const numero = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

/** A mensagem do valor da condição (§2.6, item 2), ou null. As mesmas da API. */
export function problemaDoValor(fonte: Pergunta, c: Condicao, rotulo: string): string | null {
  const v = c.valor
  if (ehNota(fonte)) {
    const { min, max } = faixa(fonte)
    if (c.op === 'grupo_e') {
      const validos = gruposDoTipo(fonte.tipo).map((g) => g.valor as string)
      return Array.isArray(v) && v.length && v.every((g) => validos.includes(String(g))) ? null : `${rotulo} precisa de grupos válidos: ${validos.join(', ')}.`
    }
    if (c.op === 'entre') {
      const ok = Array.isArray(v) && v.length === 2 && inteiro(v[0]) && inteiro(v[1]) && min <= v[0] && v[0] <= v[1] && v[1] <= max
      return ok ? null : `${rotulo} precisa de dois números de ${min} a ${max}, o primeiro menor ou igual ao segundo.`
    }
    return inteiro(v) && v >= min && v <= max ? null : `${rotulo} precisa de um número inteiro de ${min} a ${max}.`
  }
  if (fonte.tipo === 'escolha_unica' || fonte.tipo === 'escolha_multipla') {
    if (!Array.isArray(v) || !v.length || !v.every((x) => typeof x === 'string')) return `${rotulo} precisa de pelo menos uma opção.`
    const faltando = (v as string[]).find((x) => !(fonte.opcoes ?? []).includes(x.trim()))
    return faltando !== undefined ? `${rotulo} usa a opção '${faltando}', que não existe mais.` : null
  }
  if (fonte.tipo === 'sim_nao') return typeof v === 'boolean' ? null : `${rotulo} precisa de Sim ou Não.`
  if (fonte.tipo === 'data') {
    if (c.op === 'entre') {
      const ok = Array.isArray(v) && v.length === 2 && v.every((x) => typeof x === 'string' && dataValida(x)) && String(v[0]) <= String(v[1])
      return ok ? null : `${rotulo} precisa de duas datas válidas, a primeira antes da segunda (ou igual).`
    }
    return typeof v === 'string' && dataValida(v) ? null : `${rotulo} precisa de uma data válida (AAAA-MM-DD).`
  }
  if (ehTextoNumero(fonte)) {
    if (c.op === 'entre') return Array.isArray(v) && v.length === 2 && numero(v[0]) && numero(v[1]) && v[0] <= v[1] ? null : `${rotulo} precisa de dois números, o primeiro menor ou igual ao segundo.`
    return numero(v) ? null : `${rotulo} precisa de um número.`
  }
  const t = typeof v === 'string' ? v.trim() : ''
  return t.length >= 1 && t.length <= 200 ? null : `${rotulo} precisa de um texto de 1 a 200 caracteres.`
}

/** Só os erros (sem os avisos), como {chave: mensagem} (a primeira de cada chave, como a API). */
export function mapaDeProblemas(problemas: readonly Problema[], comAvisos = false): Record<string, string> {
  const mapa: Record<string, string> = {}
  for (const p of problemas) if ((comAvisos || !p.aviso) && !(p.chave in mapa)) mapa[p.chave] = p.mensagem
  return mapa
}

/**
 * Compatível com o editor antigo: confere as perguntas e o nome, com as chaves da API (`perguntas.<indice>.<campo>`).
 * Só os erros.
 */
export function validarFormulario(perguntas: Pergunta[], nome?: string): Record<string, string> {
  return mapaDeProblemas(validarDocumento({ perguntas }, { nome }))
}

/** Separa os erros por índice de pergunta: {0: {titulo: '...'}}. */
export function errosPorPergunta(erros: Record<string, string>): Record<number, Record<string, string>> {
  const saida: Record<number, Record<string, string>> = {}
  for (const [chave, msg] of Object.entries(erros)) {
    const m = chave.match(/^perguntas\.(\d+)(?:\.(.+))?$/)
    if (!m) continue
    const i = Number(m[1])
    ;(saida[i] ??= {})[m[2] ?? '_'] = msg
  }
  return saida
}

/**
 * Problemas que vieram do servidor (`problemas` do rascunho ou `campos` do 422 ao publicar), no formato do painel.
 * As chaves apontam para o índice no documento que foi enviado: aqui viram o id do item (ou do final).
 */
export function problemasDoServidor(campos: Record<string, string>, doc: DocumentoValidar, avisos?: Record<string, string> | null): Problema[] {
  const saida: Problema[] = []
  for (const [chave, mensagem] of Object.entries(campos ?? {})) {
    const aviso = avisos?.[chave] === mensagem || /^A citação \{\{/.test(mensagem)
    let m = /^perguntas\.(\d+)(?:\.(.+))?$/.exec(chave)
    if (m) {
      const i = Number(m[1])
      const item = doc.perguntas[i]
      if (item) {
        const campo = m[2] ?? undefined
        const rm = /regra (\d+)/.exec(mensagem)
        const cm = /condição (\d+)/.exec(mensagem)
        saida.push({
          chave,
          mensagem,
          aviso,
          alvo: { tipo: 'item', id: item.id, indice: i },
          campo,
          ...(campo === 'logica' ? { logica: { onde: rm ? 'pular' : item.logica?.mostrar_se ? 'mostrar_se' : 'pular', regra: rm ? Number(rm[1]) : undefined, condicao: cm ? Number(cm[1]) : undefined } } : {}),
        })
        continue
      }
    }
    m = /^finais\.(\d+)(?:\.(.+))?$/.exec(chave)
    if (m) {
      const j = Number(m[1])
      const f = doc.finais?.[j]
      if (f) {
        const cm = /condição (\d+)/.exec(mensagem)
        saida.push({ chave, mensagem, aviso, alvo: { tipo: 'final', id: f.id, indice: j }, campo: m[2], ...(m[2] === 'mostrar_se' ? { logica: { onde: 'mostrar_se', condicao: cm ? Number(cm[1]) : undefined } } : {}) })
        continue
      }
    }
    if (chave.startsWith('tema')) saida.push({ chave, mensagem, aviso, alvo: { tipo: 'tema' }, campo: chave.split('.')[1] })
    else saida.push({ chave, mensagem, aviso, alvo: { tipo: 'formulario' } })
  }
  return saida
}

/** Junta os problemas do site e do servidor sem repetir (mesma chave e mensagem). */
export function juntarProblemas(...listas: readonly Problema[][]): Problema[] {
  const vistos = new Set<string>()
  const saida: Problema[] = []
  for (const lista of listas)
    for (const p of lista) {
      const k = `${p.alvo.tipo}:${'id' in p.alvo ? p.alvo.id : ''}:${p.chave}:${p.mensagem}`
      if (vistos.has(k)) continue
      vistos.add(k)
      saida.push(p)
    }
  return saida
}

/** O número de cada condição com problema numa lógica (para marcar a linha no construtor). */
export function errosDaLogica(problemas: readonly Problema[], onde: 'mostrar_se' | 'pular', regra?: number): Map<number, string> & { geral: string[] } {
  const mapa = new Map<number, string>() as Map<number, string> & { geral: string[] }
  mapa.geral = []
  for (const p of problemas) {
    if (!p.logica || p.logica.onde !== onde || (onde === 'pular' && p.logica.regra !== regra)) continue
    if (p.logica.condicao) {
      if (!mapa.has(p.logica.condicao)) mapa.set(p.logica.condicao, p.mensagem)
    } else mapa.geral.push(p.mensagem)
  }
  return mapa
}

/** `numeroDoTexto` para o campo de número das condições ("1.250,5" → 1250.5). */
export { numeroDoTexto }
