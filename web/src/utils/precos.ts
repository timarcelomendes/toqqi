/**
 * Etapa 5k (docs/api-etapa-5k.md §2 e §3): o valor de cada fatura de um contrato — a mesma conta de
 * `api/toqqi/core/planos.py` (`preco_personalizado` e `valor_contrato`), em centavos inteiros para não errar no
 * arredondamento. A API confere: o valor mostrado vai em `preco` e, se mudou, volta 409 `preco_mudou`.
 * Usado na tela Assinatura e no site da raiz (sem dependências do app).
 */

export type Ciclo = 'mensal' | 'anual'
export type Forma = 'pix' | 'qualquer'
type Decimal = number | string

export interface Descontos {
  pix: number
  anual: number
}

export interface Tabela {
  base: Decimal
  faixas: { ate: number | null; preco: Decimal }[]
  ia: { cota: number; preco: Decimal }[]
  contatos_min: number
  contatos_max: number
  passo: number
}

/** Os padrões do código (para o HTML do site e antes de a API responder). */
export const DESCONTOS_PADRAO: Descontos = { pix: 3, anual: 10 }
export const TABELA_PADRAO: Tabela = {
  base: 99,
  faixas: [{ ate: 1500, preco: 18 }, { ate: 10000, preco: 11 }, { ate: null, preco: 6 }],
  ia: [{ cota: 100, preco: 0 }, { cota: 500, preco: 30 }, { cota: 2000, preco: 120 }, { cota: 5000, preco: 250 }],
  contatos_min: 100,
  contatos_max: 100000,
  passo: 100,
}

/** "149.00" | 149 → 14900 (centavos); inválido → NaN. */
export function centavos(v: Decimal): number {
  const n = typeof v === 'number' ? v : Number(String(v).trim())
  return Number.isFinite(n) ? Math.round(n * 100) : Number.NaN
}

/** Contatos válidos no Personalizado: múltiplo do passo, entre o mínimo e o máximo. */
export function contatosValidos(n: number, t: Tabela = TABELA_PADRAO): boolean {
  return Number.isInteger(n) && n >= t.contatos_min && n <= t.contatos_max && n % t.passo === 0
}

/** Arredonda para o passo e para dentro da faixa (o campo da calculadora). */
export function ajustarContatos(n: number, t: Tabela = TABELA_PADRAO): number {
  if (!Number.isFinite(n)) return t.contatos_min
  const arredondado = Math.round(n / t.passo) * t.passo
  return Math.min(t.contatos_max, Math.max(t.contatos_min, arredondado))
}

/**
 * Por mês, em centavos: base + cada 100 contatos pelo preço da faixa em que cai + o pacote do ToqqiAI. Fora da
 * tabela → NaN.
 */
export function precoPersonalizado(contatos: number, cotaIa: number, t: Tabela = TABELA_PADRAO): number {
  const pacote = t.ia.find((p) => p.cota === cotaIa)
  if (!contatosValidos(contatos, t) || !pacote) return Number.NaN
  let total = centavos(t.base)
  const centenas = contatos / t.passo
  let antes = 0
  for (const faixa of t.faixas) {
    const ate = faixa.ate === null ? null : faixa.ate / t.passo
    const nesta = ate === null ? centenas - antes : Math.max(0, Math.min(centenas, ate) - antes)
    total += nesta * centavos(faixa.preco)
    if (ate === null || centenas <= ate) break
    antes = ate
  }
  return total + centavos(pacote.preco)
}

/** Valor de cada fatura, em centavos: mensal = preço; mensal com Pix = − pix%; anual = 12 × preço − anual%. */
export function valorFatura(porMes: number, ciclo: Ciclo, forma: Forma, d: Descontos = DESCONTOS_PADRAO): number {
  if (!Number.isFinite(porMes)) return Number.NaN
  const meio = (x: number) => Math.floor((x + 50) / 100) // ÷ 100 com meio para cima (inteiros)
  if (ciclo === 'anual') return meio(porMes * 12 * (100 - d.anual))
  if (forma === 'pix') return meio(porMes * (100 - d.pix))
  return porMes
}

/** 14453 → "144.53" (o formato que a API espera em `preco`). */
export function paraApi(c: number): string {
  return (c / 100).toFixed(2)
}

/** 14453 → "R$ 144,53"; 14900 → "R$ 149" (`semCentavosRedondos`). */
export function reais(c: number, semCentavosRedondos = false): string {
  if (!Number.isFinite(c)) return '—'
  const inteiro = c % 100 === 0 && semCentavosRedondos
  return 'R$ ' + (c / 100).toLocaleString('pt-BR', {
    minimumFractionDigits: inteiro ? 0 : 2, maximumFractionDigits: inteiro ? 0 : 2,
  })
}

/** Comentários lidos pela IA por mês no Personalizado: 3 por contato, no mínimo 1.000 (a regra da API). */
export function tetoPersonalizado(contatos: number): number {
  return Math.max(1000, 3 * contatos)
}

/** "Personalizado (2.000 contatos, 500 perguntas)" — o mesmo nome da API. */
export function nomePersonalizado(contatos: number, cotaIa: number): string {
  const n = (x: number) => x.toLocaleString('pt-BR')
  return `Personalizado (${n(contatos)} contatos, ${n(cotaIa)} perguntas)`
}
