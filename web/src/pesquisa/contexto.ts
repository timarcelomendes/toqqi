import { CAMPOS_CONTEXTO, type Contexto } from './tipos'

export type CanalPublico = 'link' | 'qr' | 'widget'

export interface ParametrosPublicos {
  nota: number | null
  canal: CanalPublico
  referencia: string | null
  contexto: Contexto
  embed: boolean
}

const CANAIS: CanalPublico[] = ['link', 'qr', 'widget']
const LIMITE_VALOR = 200

/** Lê ?nota=, ?canal=, ?ref=, ?embed=1 e os campos de contexto (pedido, nota_fiscal...). */
export function lerParametros(busca: string | URLSearchParams): ParametrosPublicos {
  const q = typeof busca === 'string' ? new URLSearchParams(busca) : busca
  const notaTexto = q.get('nota')
  const nota = notaTexto !== null && /^\d{1,2}$/.test(notaTexto.trim()) ? Number(notaTexto) : null
  const canalBruto = (q.get('canal') ?? '').toLowerCase() as CanalPublico
  const contexto: Contexto = {}
  for (const c of CAMPOS_CONTEXTO) {
    const v = q.get(c)?.trim()
    if (v) contexto[c] = v.slice(0, LIMITE_VALOR)
  }
  const ref = q.get('ref')?.trim()
  return {
    nota,
    canal: CANAIS.includes(canalBruto) ? canalBruto : 'link',
    referencia: ref ? ref.slice(0, LIMITE_VALOR) : null,
    contexto,
    embed: q.get('embed') === '1',
  }
}

export interface ValoresLinkContexto extends Contexto {
  referencia?: string
  canal?: CanalPublico | ''
}

/**
 * Monta o link público com contexto: `${base}/f/${codigo}?pedido=123&rota=Sul`.
 * Campos vazios ficam de fora; a ordem segue a lista de campos de contexto.
 */
export function montarLinkComContexto(base: string, codigo: string, valores: ValoresLinkContexto = {}): string {
  const url = `${base.replace(/\/+$/, '')}/f/${encodeURIComponent(codigo)}`
  const q = new URLSearchParams()
  if (valores.canal) q.set('canal', valores.canal)
  for (const c of CAMPOS_CONTEXTO) {
    const v = valores[c]?.trim()
    if (v) q.set(c, v)
  }
  const ref = valores.referencia?.trim()
  if (ref) q.set('ref', ref)
  const qs = q.toString()
  return qs ? `${url}?${qs}` : url
}
