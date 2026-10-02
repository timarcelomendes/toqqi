// Regras puras da Ajuda (sem Vue): leitura defensiva do conteúdo, texto sem acento, busca nas seções e o trecho de
// cada resultado. O conteúdo vem de GET /ajuda (docs/api-etapa-5b.md §3.1) e é texto puro.
import type { BlocoAjuda, ConteudoAjuda, SecaoAjuda, TopicoAjuda } from '@/api/tipos'

/** Sem acento e em minúsculas ("Importação" → "importacao"). */
export function semAcento(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

const ehTexto = (v: unknown): v is string => typeof v === 'string' && v.trim() !== ''
const textos = (v: unknown): string[] => (Array.isArray(v) ? v.filter(ehTexto) : [])

function lerBloco(b: unknown): BlocoAjuda | null {
  if (!b || typeof b !== 'object') return null
  const { tipo, texto, itens } = b as Record<string, unknown>
  if ((tipo === 'paragrafo' || tipo === 'dica') && ehTexto(texto)) return { tipo, texto }
  if (tipo === 'passos' || tipo === 'lista') {
    const lista = textos(itens)
    return lista.length ? { tipo, itens: lista } : null
  }
  return null // tipo que esta tela ainda não conhece
}

function lerSecao(s: unknown): SecaoAjuda | null {
  if (!s || typeof s !== 'object') return null
  const r = s as Record<string, unknown>
  if (!ehTexto(r.id) || !ehTexto(r.titulo)) return null
  return {
    id: r.id,
    titulo: r.titulo,
    somente_admin: r.somente_admin === true,
    atalho: ehTexto(r.atalho) ? r.atalho : null,
    palavras: textos(r.palavras),
    blocos: (Array.isArray(r.blocos) ? r.blocos : []).map(lerBloco).filter((b): b is BlocoAjuda => !!b),
  }
}

/**
 * O conteúdo como a tela usa: tópicos e seções sem id ou título ficam de fora, assim como blocos de tipo desconhecido
 * (o conteúdo está sendo escrito; um item malformado não derruba a tela). Ids repetidos: vale o primeiro.
 */
export function lerConteudo(bruto: unknown): ConteudoAjuda {
  const r = bruto && typeof bruto === 'object' ? (bruto as Record<string, unknown>) : {}
  const topicos: TopicoAjuda[] = []
  const idsTopicos = new Set<string>()
  for (const t of Array.isArray(r.topicos) ? r.topicos : []) {
    if (!t || typeof t !== 'object') continue
    const tt = t as Record<string, unknown>
    if (!ehTexto(tt.id) || !ehTexto(tt.titulo) || idsTopicos.has(tt.id)) continue
    idsTopicos.add(tt.id)
    const idsSecoes = new Set<string>()
    const secoes: SecaoAjuda[] = []
    for (const s of Array.isArray(tt.secoes) ? tt.secoes : []) {
      const secao = lerSecao(s)
      if (!secao || idsSecoes.has(secao.id)) continue
      idsSecoes.add(secao.id)
      secoes.push(secao)
    }
    topicos.push({ id: tt.id, titulo: tt.titulo, resumo: ehTexto(tt.resumo) ? tt.resumo : '', secoes })
  }
  return { versao: typeof r.versao === 'number' ? r.versao : 1, topicos }
}

/** O texto de um bloco numa linha só (passos numerados), para a busca e o trecho dos resultados. */
export function textoDoBloco(b: BlocoAjuda): string {
  if (b.tipo === 'passos') return b.itens.map((item, i) => `${i + 1}. ${item}`).join(' ')
  if (b.tipo === 'lista') return b.itens.join(' ')
  return b.texto
}

/** Palavras que não ajudam a achar nada ("como", "para"...). */
const VAZIAS = new Set([
  'como', 'para', 'que', 'uma', 'umas', 'uns', 'com', 'por', 'pelo', 'pela', 'dos', 'das', 'nos', 'nas', 'meu', 'meus',
  'minha', 'minhas', 'seu', 'seus', 'sua', 'suas', 'onde', 'qual', 'quais', 'quando', 'faco', 'posso', 'pode', 'sobre',
  'isso', 'esse', 'essa', 'este', 'esta', 'tem', 'ter', 'sao', 'nao',
])

/**
 * O texto como a busca compara: sem acento, em minúsculas, sem o hífen no meio da palavra ("e-mail" → "email") e com os
 * plurais "ões" e "ens" no singular ("Notificações" → "notificacao", "mensagens" → "mensagem").
 */
export function paraBusca(texto: string): string {
  return semAcento(texto)
    .replace(/([a-z0-9])-(?=[a-z0-9])/g, '$1')
    .replace(/oes(?![a-z0-9])/g, 'ao')
    .replace(/ens(?![a-z0-9])/g, 'em')
}

/** Finais tirados para chegar à raiz, com o tamanho mínimo que a raiz precisa ter. */
const FINAIS: [string, number][] = [
  ['acao', 4],
  ['mento', 4],
  ['ar', 4],
  ['er', 4],
  ['ir', 4],
  ['a', 5],
  ['e', 5],
  ['o', 5],
]

/**
 * Raiz simples de uma palavra já como `paraBusca`: sem o "s" do plural, sem "-ação"/"-mento", sem o "-ar/-er/-ir" dos
 * verbos ou sem a vogal final. Assim "importação", "importar" e "importados" se acham ("import"), e "planilhas" acha
 * "planilha". A raiz nunca fica curta demais ("conta" continua "conta").
 */
export function raiz(palavra: string): string {
  const r = palavra.length >= 5 && palavra.endsWith('s') ? palavra.slice(0, -1) : palavra
  for (const [final, minimo] of FINAIS) {
    if (r.endsWith(final) && r.length - final.length >= minimo) return r.slice(0, -final.length)
  }
  return r
}

/**
 * As raízes das palavras do termo: as de 3 letras ou mais que dizem algo; se não sobrar nenhuma, as de 2 letras (como
 * "ia"), que valem só como palavra inteira.
 */
export function palavrasDaBusca(termo: string): string[] {
  const todas = paraBusca(termo).split(/[^a-z0-9]+/).filter(Boolean)
  const boas = todas.filter((p) => p.length >= 3 && !VAZIAS.has(p)).map(raiz)
  const lista = boas.length ? boas : todas.filter((p) => p.length === 2)
  return [...new Set(lista)]
}

/** A raiz no começo de uma palavra do texto ("import" acha "importar", mas "paga" não acha "apagar"); 2 letras, só a palavra inteira. */
function contem(texto: string, palavra: string): boolean {
  const fim = palavra.length >= 3 ? '' : '(?![a-z0-9])'
  return new RegExp(`(?:^|[^a-z0-9])${palavra}${fim}`).test(texto)
}

export interface ResultadoAjuda {
  topico: TopicoAjuda
  secao: SecaoAjuda
  /** O começo do bloco que tem a palavra procurada (ou do primeiro), cortado em ~180 caracteres. */
  trecho: string
}

function cortar(texto: string, maximo = 180): string {
  if (texto.length <= maximo) return texto
  const corte = texto.slice(0, maximo)
  const espaco = corte.lastIndexOf(' ')
  return `${(espaco > maximo * 0.6 ? corte.slice(0, espaco) : corte).replace(/[\s,;:.]+$/, '')}…`
}

/**
 * Procura em todos os tópicos, sem acento e sem diferenciar maiúsculas, pela raiz das palavras ("importação" acha
 * "Importar uma planilha"): palavra no título da seção ou nas palavras-chave vale 3, no texto dos blocos vale 1. Primeiro as seções com mais palavras do termo, depois as de mais pontos, e na
 * ordem do conteúdo quando empatam.
 */
export function buscarNaAjuda(conteudo: ConteudoAjuda, termo: string, limite = 20): ResultadoAjuda[] {
  const palavras = palavrasDaBusca(termo)
  if (!palavras.length) return []
  const achados: (ResultadoAjuda & { acertos: number; pontos: number; ordem: number })[] = []
  let ordem = 0
  for (const topico of conteudo.topicos) {
    for (const secao of topico.secoes) {
      ordem++
      const forte = paraBusca(`${secao.titulo} ${secao.palavras.join(' ')}`)
      const blocos = secao.blocos.map((b) => paraBusca(textoDoBloco(b)))
      let acertos = 0
      let pontos = 0
      for (const p of palavras) {
        const noForte = contem(forte, p)
        const noTexto = blocos.some((b) => contem(b, p))
        if (noForte || noTexto) acertos++
        pontos += (noForte ? 3 : 0) + (noTexto ? 1 : 0)
      }
      if (!acertos) continue
      const i = blocos.findIndex((b) => palavras.some((p) => contem(b, p)))
      const bloco = secao.blocos[i >= 0 ? i : 0]
      achados.push({ topico, secao, trecho: bloco ? cortar(textoDoBloco(bloco)) : '', acertos, pontos, ordem })
    }
  }
  achados.sort((a, b) => b.acertos - a.acertos || b.pontos - a.pontos || a.ordem - b.ordem)
  return achados.slice(0, limite).map(({ topico, secao, trecho }) => ({ topico, secao, trecho }))
}
