import type { CondicaoPergunta, GrupoNota, Pergunta, Respostas, TipoPergunta } from './tipos'

/** Tipos que podem ser a "nota principal" do formulário. */
export const TIPOS_NOTA: TipoPergunta[] = ['nps', 'csat', 'estrelas']

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

/**
 * Avalia a condição de uma pergunta. Sem condição: sempre aparece.
 * Com condição e sem nota principal respondida: fica escondida.
 */
export function condicaoAtende(
  condicao: CondicaoPergunta | null | undefined,
  principal: Pergunta | null,
  nota: number | null | undefined,
): boolean {
  if (!condicao) return true
  if (!principal || typeof nota !== 'number' || Number.isNaN(nota)) return false
  if (condicao.tipo === 'grupo') {
    const g = grupoDaNota(principal.tipo, nota)
    return !!g && (condicao.grupos ?? []).includes(g)
  }
  if (condicao.tipo === 'nota') {
    return condicao.operador === '<=' ? nota <= condicao.valor : nota >= condicao.valor
  }
  return true
}

/** Nota principal já respondida (ou null). */
export function notaPrincipal(perguntas: Pergunta[], respostas: Respostas): number | null {
  const p = perguntaPrincipal(perguntas)
  if (!p) return null
  const v = respostas[p.id]
  return typeof v === 'number' ? v : null
}

/** A pergunta aparece para quem responde, com as respostas atuais? */
export function perguntaVisivel(p: Pergunta, perguntas: Pergunta[], respostas: Respostas): boolean {
  if (p.tipo === 'quebra_pagina') return true
  return condicaoAtende(p.condicao, perguntaPrincipal(perguntas), notaPrincipal(perguntas, respostas))
}

/** Perguntas visíveis (sem quebras de página). */
export function perguntasVisiveis(perguntas: Pergunta[], respostas: Respostas): Pergunta[] {
  const principal = perguntaPrincipal(perguntas)
  const nota = notaPrincipal(perguntas, respostas)
  return perguntas.filter((p) => p.tipo !== 'quebra_pagina' && condicaoAtende(p.condicao, principal, nota))
}

/** Divide em páginas pelas quebras e tira perguntas escondidas e páginas vazias. */
export function paginasVisiveis(perguntas: Pergunta[], respostas: Respostas): Pergunta[][] {
  const principal = perguntaPrincipal(perguntas)
  const nota = notaPrincipal(perguntas, respostas)
  const paginas: Pergunta[][] = [[]]
  for (const p of perguntas) {
    if (p.tipo === 'quebra_pagina') {
      paginas.push([])
      continue
    }
    if (condicaoAtende(p.condicao, principal, nota)) paginas[paginas.length - 1]!.push(p)
  }
  return paginas.filter((pg) => pg.length > 0)
}

/** Só as respostas das perguntas visíveis e preenchidas (o que vai para a API). */
export function respostasParaEnvio(perguntas: Pergunta[], respostas: Respostas): Respostas {
  const saida: Respostas = {}
  for (const p of perguntasVisiveis(perguntas, respostas)) {
    const v = respostas[p.id]
    if (v === undefined || v === null) continue
    if (typeof v === 'string' && !v.trim()) continue
    if (Array.isArray(v) && !v.length) continue
    saida[p.id] = typeof v === 'string' ? v.trim() : v
  }
  return saida
}

/** A condição pode ser usada nesta posição? Só depois da nota principal. */
export function podeTerCondicao(indice: number, perguntas: Pergunta[]): boolean {
  const ip = indicePrincipal(perguntas)
  return ip >= 0 && indice > ip
}
