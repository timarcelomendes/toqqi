import type { RegrasSenha } from '@/api/tipos'

export const REGRAS_PADRAO: RegrasSenha = { minimo: 8, maximo: 70, exige: ['maiuscula', 'numero', 'simbolo'] }

export interface ItemRegra {
  chave: string
  rotulo: string
  ok: boolean
}

const TESTES: Record<string, { rotulo: string; teste: (s: string) => boolean }> = {
  maiuscula: { rotulo: 'Uma letra maiúscula', teste: (s) => /\p{Lu}/u.test(s) },
  minuscula: { rotulo: 'Uma letra minúscula', teste: (s) => /\p{Ll}/u.test(s) },
  numero: { rotulo: 'Um número', teste: (s) => /\p{Nd}/u.test(s) },
  simbolo: { rotulo: 'Um símbolo (ex.: ! @ # $ %)', teste: (s) => /[^\p{L}\p{Nd}\s]/u.test(s) },
  letra: { rotulo: 'Uma letra', teste: (s) => /\p{L}/u.test(s) },
}

/** Lista cada regra com o estado atual (cumprida ou não). Regras desconhecidas são ignoradas. */
export function verificarSenha(senha: string, regras: RegrasSenha = REGRAS_PADRAO): ItemRegra[] {
  const itens: ItemRegra[] = [
    { chave: 'minimo', rotulo: `Pelo menos ${regras.minimo} caracteres`, ok: senha.length >= regras.minimo },
  ]
  for (const chave of regras.exige) {
    const t = TESTES[chave]
    if (t) itens.push({ chave, rotulo: t.rotulo, ok: t.teste(senha) })
  }
  if (senha.length > regras.maximo) {
    itens.push({ chave: 'maximo', rotulo: `No máximo ${regras.maximo} caracteres`, ok: false })
  }
  return itens
}

export function senhaValida(senha: string, regras: RegrasSenha = REGRAS_PADRAO): boolean {
  return verificarSenha(senha, regras).every((i) => i.ok)
}

function sortear(conjunto: string): string {
  const n = new Uint32Array(1)
  crypto.getRandomValues(n)
  return conjunto[n[0]! % conjunto.length]!
}

/** Gera uma senha forte que cumpre as regras (sem caracteres confusos como O/0, l/1). */
export function gerarSenhaForte(regras: RegrasSenha = REGRAS_PADRAO, tamanho = 14): string {
  const mai = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  const min = 'abcdefghijkmnpqrstuvwxyz'
  const num = '23456789'
  const sim = '!@#$%&*?-_+='
  const todos = mai + min + num + sim
  const alvo = Math.min(Math.max(tamanho, regras.minimo), regras.maximo)
  const chars = [sortear(mai), sortear(min), sortear(num), sortear(sim)]
  while (chars.length < alvo) chars.push(sortear(todos))
  // Embaralha (Fisher–Yates)
  for (let i = chars.length - 1; i > 0; i--) {
    const n = new Uint32Array(1)
    crypto.getRandomValues(n)
    const j = n[0]! % (i + 1)
    ;[chars[i], chars[j]] = [chars[j]!, chars[i]!]
  }
  return chars.join('')
}
