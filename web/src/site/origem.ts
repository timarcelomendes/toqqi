/**
 * Etapa 5i: de onde veio quem se cadastra. O site da raiz guarda os `utm_*` do primeiro link da visita em
 * `sessionStorage['toqqi.origem']` e o cadastro manda junto (a API limpa de novo e grava em `contas.origem`).
 * Mesma limpeza de `api/toqqi/core/planos.py` (`limpar_origem`): só as 3 chaves; minúsculas; espaços e "+" viram "-";
 * descarta o que não casar com ^[a-z0-9._-]{1,60}$, tiver "@" ou 6+ dígitos seguidos (e-mail, telefone).
 */
export type Origem = Partial<Record<'utm_source' | 'utm_medium' | 'utm_campaign', string>>

const CHAVES = ['utm_source', 'utm_medium', 'utm_campaign'] as const
const CHAVE_SESSAO = 'toqqi.origem'
const VALOR = /^[a-z0-9._-]{1,60}$/

export function limparOrigem(bruta: unknown): Origem | null {
  if (!bruta || typeof bruta !== 'object') return null
  const limpa: Origem = {}
  for (const chave of CHAVES) {
    const valor = (bruta as Record<string, unknown>)[chave]
    if (typeof valor !== 'string') continue
    const v = valor.trim().toLowerCase().replace(/[\s+]+/g, '-')
    if (v.includes('@') || /\d{6,}/.test(v) || !VALOR.test(v)) continue
    limpa[chave] = v
  }
  return Object.keys(limpa).length ? limpa : null
}

/** A origem do endereço (`?utm_source=…`), já limpa; null sem nenhuma válida. */
export function origemDoEndereco(busca: string): Origem | null {
  const p = new URLSearchParams(busca)
  return limparOrigem(Object.fromEntries(CHAVES.filter((c) => p.has(c)).map((c) => [c, p.get(c)])))
}

/** Guarda a origem do endereço, só se a visita ainda não tiver uma (vale o primeiro link). */
export function guardarOrigem(busca: string = window.location.search): void {
  try {
    if (sessionStorage.getItem(CHAVE_SESSAO)) return
    const o = origemDoEndereco(busca)
    if (o) sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(o))
  } catch {
    /* sem armazenamento: o cadastro vai sem origem */
  }
}

/** A origem para o cadastro: a guardada na visita ou, sem ela, a do próprio endereço do cadastro. */
export function origemParaCadastro(busca: string = window.location.search): Origem | null {
  try {
    const guardada = limparOrigem(JSON.parse(sessionStorage.getItem(CHAVE_SESSAO) || 'null'))
    if (guardada) return guardada
  } catch {
    /* armazenamento bloqueado ou valor estragado */
  }
  return origemDoEndereco(busca)
}

export function apagarOrigem(): void {
  try {
    sessionStorage.removeItem(CHAVE_SESSAO)
  } catch {
    /* nada a apagar */
  }
}
