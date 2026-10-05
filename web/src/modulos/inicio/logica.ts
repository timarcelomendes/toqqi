// Regras puras do primeiro dia no Início (etapa 5h, docs/api-etapa-5h.md §1), sem Vue: quando trocar o painel pelo
// "Comece por aqui", o passo em destaque, as cores da marca (sugestões, formato e contraste do texto) e o modo exemplo
// no endereço. Os textos dos planos para os detratores e do tom ficam em `painel/logica.ts`.
import type { Painel } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'
import type { PassoInicial } from '@/modulos/painel/logica'

// ── Comece por aqui ─────────────────────────────────────────────────────────

/** Conta sem nenhuma resposta (a importada conta): o Início troca o painel pelo "Comece por aqui". */
export function semRespostas(pp: Partial<Painel['primeiros_passos']> | null | undefined): boolean {
  return !!pp && !pp.primeira_resposta
}

/** O próximo passo a fazer (o primeiro não feito), que fica em destaque; null com todos feitos. */
export function proximoPasso(passos: PassoInicial[]): PassoInicial | null {
  return passos.find((p) => !p.feito) ?? null
}

/** "1 de 4 feitos". */
export function progressoPassos(passos: PassoInicial[]): { feitos: number; total: number; texto: string } {
  const feitos = passos.filter((p) => p.feito).length
  return { feitos, total: passos.length, texto: `${feitos} de ${passos.length} feitos` }
}

// ── Sua marca nas pesquisas ─────────────────────────────────────────────────

/** A cor dos formulários enquanto a conta não escolhe a dela (a dos modelos). */
export const COR_DOS_MODELOS = '#1F6FEB'

/** As 8 sugestões da paleta (todas com texto branco legível em cima, 4,5:1 ou mais). */
export const CORES_MARCA: { cor: string; nome: string }[] = [
  { cor: '#D63A18', nome: 'Coral' },
  { cor: '#B45309', nome: 'Âmbar' },
  { cor: '#047857', nome: 'Verde' },
  { cor: '#0E7490', nome: 'Petróleo' },
  { cor: '#2563EB', nome: 'Azul' },
  { cor: '#7C3AED', nome: 'Roxo' },
  { cor: '#BE185D', nome: 'Magenta' },
  { cor: '#334155', nome: 'Grafite' },
]

/** A mesma mensagem da API (422 `cor`). */
export const MENSAGEM_COR = 'Use uma cor no formato #RRGGBB, como #D63A18.'

/** "#d63a18", " D63A18 " → "#D63A18"; fora do formato #RRGGBB (o # pode faltar) → null. */
export function normalizarCor(v: string | null | undefined): string | null {
  const t = (v ?? '').trim()
  const m = /^#?([0-9a-fA-F]{6})$/.exec(t)
  return m ? `#${m[1]!.toUpperCase()}` : null
}

function canal(c: number): number {
  const x = c / 255
  return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
}

/** Luminância relativa (WCAG) de #RRGGBB. */
export function luminancia(cor: string): number {
  const n = normalizarCor(cor) ?? '#000000'
  const [r, g, b] = [1, 3, 5].map((i) => canal(parseInt(n.slice(i, i + 2), 16))) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** Contraste (WCAG) entre duas cores, de 1 a 21. */
export function contraste(a: string, b: string): number {
  const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number]
  return (claro + 0.05) / (escuro + 0.05)
}

/** O texto em cima da cor (como nos e-mails): branco com 4,5:1 ou mais; senão, quase preto. */
export function corDoTexto(cor: string): '#FFFFFF' | '#111827' {
  return contraste(cor, '#FFFFFF') >= 4.5 ? '#FFFFFF' : '#111827'
}

/** O cartão conta como feito com logo ou cor própria. */
export function marcaFeita(m: { cor: string | null; tem_logo: boolean } | null | undefined): boolean {
  return !!m && (m.tem_logo || !!m.cor)
}

/** O aviso depois de salvar a cor. */
export function textoCorSalva(formularios: number): string {
  if (!formularios) return 'Cor salva: os e-mails das pesquisas já usam a nova cor.'
  return `Cor salva: os e-mails e ${formularios === 1 ? '1 formulário' : `${formatarNumero(formularios)} formulários`} já usam a nova cor.`
}

// ── Modo exemplo ────────────────────────────────────────────────────────────

type ValorConsulta = string | null | (string | null)[] | undefined

/** `?exemplo=1` no endereço abre o Início direto no modo exemplo. */
export function exemploNaConsulta(v: ValorConsulta): boolean {
  const x = Array.isArray(v) ? v[0] : v
  return x === '1'
}
