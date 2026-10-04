// Regras puras de Plataforma › Parâmetros (etapa 5g, docs/api-etapa-5g.md §2 e §7), sem Vue: o catálogo de chaves
// (rótulo, tipo e limites), o formato de cada valor, o formulário (texto digitado ↔ valor da API), a validação igual à da
// API, o que mudou, as linhas do diálogo de confirmação (com as contas atingidas) e as do histórico.
import type {
  GrupoParametros,
  GrupoParametrosPlataforma,
  ImpactoParametro,
  MudancaParametro,
  PreviaParametros,
  ValorParametro,
} from '@/api/tipos'
import { formatarDataHora } from '@/utils/datas'
import { formatarDecimal, formatarMoeda, formatarNumero, lerMoeda } from '@/utils/formatos'

// ── Grupos, planos e níveis ─────────────────────────────────────────────────

export const GRUPOS_PARAMETROS: { valor: GrupoParametros; rotulo: string }[] = [
  { valor: 'planos', rotulo: 'Planos' },
  { valor: 'ia', rotulo: 'IA' },
  { valor: 'whatsapp', rotulo: 'WhatsApp automático' },
  { valor: 'teste', rotulo: 'Teste e cortesia' },
]

export function rotuloGrupo(grupo: string): string {
  return GRUPOS_PARAMETROS.find((g) => g.valor === grupo)?.rotulo ?? grupo
}

export function ehGrupoParametros(v: unknown): v is GrupoParametros {
  return GRUPOS_PARAMETROS.some((g) => g.valor === v)
}

const PLANOS = [
  { chave: 'essencial', nome: 'Essencial' },
  { chave: 'profissional', nome: 'Profissional' },
  { chave: 'empresa', nome: 'Empresa' },
] as const

export const OPCOES_PLANO = PLANOS.map((p) => ({ valor: p.chave as string, rotulo: p.nome }))

const NIVEIS = [
  { chave: 'rapido', nome: 'Rápido' },
  { chave: 'equilibrado', nome: 'Equilibrado' },
  { chave: 'detalhado', nome: 'Mais detalhado' },
] as const

/** Esforço de raciocínio: vazio não manda `reasoning` à OpenAI. */
export const ESFORCOS = ['', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh'] as const
export const OPCOES_ESFORCO = ESFORCOS.map((e) => ({ valor: e as string, rotulo: e || 'Sem raciocínio' }))

export const OPCOES_EXCLUSAO = [
  { valor: 'ligada', rotulo: 'Ligada: avisa e exclui' },
  { valor: 'simular', rotulo: 'Simular: só conta e registra no log' },
]

// ── Catálogo ────────────────────────────────────────────────────────────────

export type TipoCampo = 'dinheiro' | 'contatos' | 'inteiro' | 'modelo' | 'esforco' | 'plano' | 'exclusao'

export interface CampoParametro {
  chave: string
  grupo: GrupoParametros
  tipo: TipoCampo
  /** Rótulo dentro do fieldset ("Preço por mês", "Essencial"). */
  rotulo: string
  /** Nome completo, no diálogo e no histórico ("Preço do Essencial"). */
  nome: string
  min?: number
  max?: number
  /**
   * Como uma mudança pesa nas contas: `contatos` e `uso` (cota, teto, franquia) pedem confirmação quando diminuem;
   * `analises`, quando aumenta.
   */
  peso?: 'contatos' | 'uso' | 'analises'
}

function campo(c: CampoParametro): CampoParametro {
  return c
}

const DE_PLANO = (p: { chave: string; nome: string }) => `do ${p.nome}`

/** Todas as chaves do §2, na ordem da tela. */
export const CAMPOS: CampoParametro[] = [
  ...PLANOS.flatMap((p) => [
    campo({ chave: `planos.${p.chave}.preco`, grupo: 'planos', tipo: 'dinheiro', rotulo: 'Preço por mês', nome: `Preço ${DE_PLANO(p)}`, min: 5, max: 99_999.99 }),
    campo({ chave: `planos.${p.chave}.contatos`, grupo: 'planos', tipo: 'contatos', rotulo: 'Contatos ativos', nome: `Contatos ${DE_PLANO(p)}`, min: 1, max: 1_000_000, peso: 'contatos' }),
  ]),
  ...[...PLANOS, { chave: 'cortesia', nome: 'Cortesia' }].map((p) =>
    campo({
      chave: `ia.cota.${p.chave}`,
      grupo: 'ia',
      tipo: 'inteiro',
      rotulo: p.nome,
      nome: p.chave === 'cortesia' ? 'Cota de IA da cortesia' : `Cota de IA ${DE_PLANO(p)}`,
      min: 0,
      max: 100_000,
      peso: 'uso',
    }),
  ),
  ...NIVEIS.flatMap((n) => [
    campo({ chave: `ia.modelo.${n.chave}`, grupo: 'ia', tipo: 'modelo', rotulo: 'Modelo', nome: `Modelo do nível ${n.nome}` }),
    campo({ chave: `ia.esforco.${n.chave}`, grupo: 'ia', tipo: 'esforco', rotulo: 'Esforço', nome: `Esforço do nível ${n.nome}` }),
    campo({ chave: `ia.analises.${n.chave}`, grupo: 'ia', tipo: 'inteiro', rotulo: 'Análises por uso', nome: `Análises por uso do nível ${n.nome}`, min: 1, max: 10, peso: 'analises' }),
  ]),
  ...[...PLANOS, { chave: 'cortesia', nome: 'Cortesia' }, { chave: 'teste', nome: 'Teste' }].map((p) =>
    campo({
      chave: `ia.teto.${p.chave}`,
      grupo: 'ia',
      tipo: 'inteiro',
      rotulo: p.nome,
      nome: p.chave === 'cortesia' ? 'Teto de IA da cortesia' : p.chave === 'teste' ? 'Teto de IA do teste' : `Teto de IA ${DE_PLANO(p)}`,
      min: 0,
      max: 1_000_000,
      peso: 'uso',
    }),
  ),
  ...[...PLANOS, { chave: 'cortesia', nome: 'Cortesia' }, { chave: 'teste', nome: 'Teste' }].map((p) =>
    campo({
      chave: `whatsapp.franquia.${p.chave}`,
      grupo: 'whatsapp',
      tipo: 'inteiro',
      rotulo: p.nome,
      nome: p.chave === 'cortesia' ? 'Franquia de WhatsApp da cortesia' : p.chave === 'teste' ? 'Franquia de WhatsApp do teste' : `Franquia de WhatsApp ${DE_PLANO(p)}`,
      min: 0,
      max: 100_000,
      peso: 'uso',
    }),
  ),
  campo({ chave: 'teste.dias', grupo: 'teste', tipo: 'inteiro', rotulo: 'Dias de teste', nome: 'Dias de teste', min: 1, max: 90 }),
  campo({ chave: 'teste.plano', grupo: 'teste', tipo: 'plano', rotulo: 'Plano do teste', nome: 'Plano do teste' }),
  campo({ chave: 'teste.exclusao_automatica', grupo: 'teste', tipo: 'exclusao', rotulo: 'Exclusão automática das contas encerradas', nome: 'Exclusão automática' }),
]

const POR_CHAVE = new Map(CAMPOS.map((c) => [c.chave, c]))

export function campoDaChave(chave: string): CampoParametro | null {
  return POR_CHAVE.get(chave) ?? null
}

export function camposDoGrupo(grupo: string): CampoParametro[] {
  return CAMPOS.filter((c) => c.grupo === grupo)
}

// ── Como cada grupo aparece na tela ─────────────────────────────────────────

export interface BlocoParametros {
  /** Legenda do fieldset. */
  legenda: string
  chaves: string[]
  /** Fieldsets de dentro (os níveis de modelo). */
  blocos?: BlocoParametros[]
}

export interface LayoutGrupo {
  descricao: string
  blocos: BlocoParametros[]
  /** Os fieldsets lado a lado em telas largas, com os campos um embaixo do outro (os planos). */
  ladoALado?: boolean
  nota: string | null
}

export const LAYOUT_GRUPOS: Record<GrupoParametros, LayoutGrupo> = {
  planos: {
    descricao: 'Preço e limite de contatos ativos de cada plano.',
    blocos: PLANOS.map((p) => ({ legenda: p.nome, chaves: [`planos.${p.chave}.preco`, `planos.${p.chave}.contatos`] })),
    ladoALado: true,
    nota: 'O preço novo vale para assinaturas novas e trocas de plano. Quem já assina continua com o valor contratado.',
  },
  ia: {
    descricao: 'Cotas, modelos e tetos de segurança da inteligência artificial.',
    blocos: [
      { legenda: 'Análises por mês (cota do plano)', chaves: ['essencial', 'profissional', 'empresa', 'cortesia'].map((p) => `ia.cota.${p}`) },
      {
        legenda: 'Níveis de modelo',
        chaves: [],
        blocos: NIVEIS.map((n) => ({ legenda: n.nome, chaves: [`ia.modelo.${n.chave}`, `ia.esforco.${n.chave}`, `ia.analises.${n.chave}`] })),
      },
      {
        legenda: 'Teto de segurança por mês (análise dos comentários e passos das ações)',
        chaves: ['essencial', 'profissional', 'empresa', 'cortesia', 'teste'].map((p) => `ia.teto.${p}`),
      },
    ],
    nota: 'Ao salvar um modelo ou esforço novo, o Toqqi faz uma chamada curta à OpenAI para conferir.',
  },
  whatsapp: {
    descricao: 'Franquia do WhatsApp automático de cada plano.',
    blocos: [{ legenda: 'Mensagens por mês', chaves: ['essencial', 'profissional', 'empresa', 'cortesia', 'teste'].map((p) => `whatsapp.franquia.${p}`) }],
    nota: null,
  },
  teste: {
    descricao: 'O teste grátis das contas novas e a exclusão das contas encerradas.',
    blocos: [{ legenda: 'Teste grátis e exclusão', chaves: ['teste.dias', 'teste.plano', 'teste.exclusao_automatica'] }],
    nota: 'Cota, teto e franquia da cortesia e do teste ficam em IA e WhatsApp automático.',
  },
}

// ── Formato dos valores ─────────────────────────────────────────────────────

const centavos = (v: ValorParametro | undefined): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? Math.round(n * 100) : null
}

const inteiroDe = (v: ValorParametro | undefined): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

export function nomePlano(chave: string): string {
  return PLANOS.find((p) => p.chave === chave)?.nome ?? (chave ? chave.charAt(0).toUpperCase() + chave.slice(1) : '—')
}

/** O valor como aparece no diálogo e no histórico: "R$ 149,00", "1.500", "sem limite", "Profissional", "Ligada". */
export function formatarValor(chave: string, v: ValorParametro | undefined): string {
  const c = campoDaChave(chave)
  if (!c) return v === null || v === undefined || v === '' ? '—' : String(v)
  switch (c.tipo) {
    case 'dinheiro':
      return formatarMoeda(v)
    case 'contatos':
      return v === null ? 'sem limite' : formatarNumero(inteiroDe(v))
    case 'inteiro':
      return formatarNumero(inteiroDe(v))
    case 'esforco':
      return v ? String(v) : 'sem raciocínio'
    case 'plano':
      return v ? nomePlano(String(v)) : '—'
    case 'exclusao':
      return v === 'ligada' ? 'Ligada' : v === 'simular' ? 'Simular' : v ? String(v) : '—'
    default:
      return v === null || v === undefined || v === '' ? '—' : String(v)
  }
}

/** Mesmo valor para a API? (dinheiro pelos centavos: "149.9" = "149.90" = 149.9). */
export function mesmoValor(chave: string, a: ValorParametro | undefined, b: ValorParametro | undefined): boolean {
  const c = campoDaChave(chave)
  if (c?.tipo === 'dinheiro') return centavos(a) === centavos(b)
  if (c?.tipo === 'contatos' || c?.tipo === 'inteiro') return inteiroDe(a) === inteiroDe(b)
  return (a ?? null) === (b ?? null)
}

// ── Formulário ──────────────────────────────────────────────────────────────

/** O que está nos campos: texto digitado por chave e a caixa "Sem limite" dos contatos. */
export interface FormParametros {
  textos: Record<string, string>
  semLimite: Record<string, boolean>
}

/** Texto do campo para um valor da API ("149.9" → "149,90"; 1500 → "1500"; null → ""). */
export function textoDoCampo(chave: string, v: ValorParametro | undefined): string {
  const c = campoDaChave(chave)
  if (v === null || v === undefined) return ''
  if (c?.tipo === 'dinheiro') return formatarDecimal(v)
  return String(v)
}

export function formDe(dados: Pick<GrupoParametrosPlataforma, 'grupo' | 'valores'>): FormParametros {
  const form: FormParametros = { textos: {}, semLimite: {} }
  for (const c of camposDoGrupo(dados.grupo)) {
    const v = dados.valores[c.chave]
    form.textos[c.chave] = textoDoCampo(c.chave, v)
    if (c.tipo === 'contatos') form.semLimite[c.chave] = v === null
  }
  return form
}

/** Põe o padrão no campo ("Usar o padrão"). */
export function aplicarPadrao(form: FormParametros, chave: string, padrao: ValorParametro | undefined): void {
  const c = campoDaChave(chave)
  form.textos[chave] = textoDoCampo(chave, padrao)
  if (c?.tipo === 'contatos') form.semLimite[chave] = padrao === null
}

/** Milhar com ponto ("1.500", "1.000.000"), como em `lerMoeda`. */
const MILHAR = /^[1-9]\d{0,2}(?:\.\d{3})+$/

/** Número inteiro digitado: "1500" ou "1.500". Outra coisa (vírgula, sinal, letras, vazio) → null. */
export function lerInteiro(texto: string): number | null {
  const t = texto.trim()
  if (/^\d{1,9}$/.test(t)) return Number(t)
  if (MILHAR.test(t)) return Number(t.replace(/\./g, ''))
  return null
}

/** Casas decimais do que foi digitado, com as regras de `lerMoeda` (vírgula decimal; ponto com 3 dígitos = milhar). */
export function casasDecimais(texto: string): number {
  const t = texto.replace(/[^\d,.-]/g, '')
  if (t.includes(',')) return (t.split(',')[1] ?? '').length
  if (MILHAR.test(t)) return 0
  const i = t.lastIndexOf('.')
  return i < 0 ? 0 : t.length - i - 1
}

/** As mensagens da API (core/parametros.py), para a tela dizer o mesmo antes de enviar. */
export const MENSAGENS_PARAMETROS = {
  preco: 'Use um valor entre R$ 5,00 e R$ 99.999,99.',
  precoVazio: 'Informe o preço.',
  precoCasas: 'Use no máximo 2 casas decimais.',
  contatos: 'Use um número inteiro de 1 a 1.000.000, ou marque “Sem limite”.',
  modelo: 'Informe o nome do modelo (até 100 caracteres: letras, números, ponto, hífen, dois-pontos ou sublinhado).',
  esforco: 'Escolha um esforço da lista (ou “Sem raciocínio”).',
  plano: 'Escolha um dos planos: Essencial, Profissional ou Empresa.',
  exclusao: 'Escolha “ligada” ou “simular”.',
} as const

/** "Use um número inteiro de 0 a 100.000." */
export function mensagemInteiro(min: number, max: number): string {
  return `Use um número inteiro de ${formatarNumero(min)} a ${formatarNumero(max)}.`
}

const MODELO = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$/

/** Lê um campo do formulário: o valor para a API ou a mensagem de erro (as regras do §2, campo a campo). */
export function lerCampo(form: FormParametros, chave: string): { valor: ValorParametro } | { erro: string } {
  const c = campoDaChave(chave)
  const texto = form.textos[chave] ?? ''
  if (!c) return { valor: texto }
  switch (c.tipo) {
    case 'dinheiro': {
      if (!texto.trim()) return { erro: MENSAGENS_PARAMETROS.precoVazio }
      const n = lerMoeda(texto)
      if (n === null) return { erro: MENSAGENS_PARAMETROS.preco }
      if (casasDecimais(texto) > 2) return { erro: MENSAGENS_PARAMETROS.precoCasas }
      if (n < (c.min ?? 0) || n > (c.max ?? Number.MAX_SAFE_INTEGER)) return { erro: MENSAGENS_PARAMETROS.preco }
      return { valor: n.toFixed(2) }
    }
    case 'contatos':
    case 'inteiro': {
      if (c.tipo === 'contatos' && form.semLimite[chave]) return { valor: null }
      const n = lerInteiro(texto)
      const min = c.min ?? 0
      const max = c.max ?? Number.MAX_SAFE_INTEGER
      if (n === null || n < min || n > max) return { erro: c.tipo === 'contatos' ? MENSAGENS_PARAMETROS.contatos : mensagemInteiro(min, max) }
      return { valor: n }
    }
    case 'modelo': {
      const t = texto.trim()
      return MODELO.test(t) ? { valor: t } : { erro: MENSAGENS_PARAMETROS.modelo }
    }
    case 'esforco':
      return (ESFORCOS as readonly string[]).includes(texto) ? { valor: texto } : { erro: MENSAGENS_PARAMETROS.esforco }
    case 'plano':
      return PLANOS.some((p) => p.chave === texto) ? { valor: texto } : { erro: MENSAGENS_PARAMETROS.plano }
    case 'exclusao':
      return texto === 'ligada' || texto === 'simular' ? { valor: texto } : { erro: MENSAGENS_PARAMETROS.exclusao }
  }
}

/** Contatos para comparar: null (sem limite) é o maior. */
const limiteComparavel = (v: ValorParametro | undefined) => (v === null ? Number.POSITIVE_INFINITY : (inteiroDe(v) ?? Number.NaN))

/**
 * O corpo do PUT e os erros por chave. Leva todas as chaves do grupo que a API mandou (as que a tela não conhece vão com
 * o valor atual) e confere a ordem dos planos: preços crescentes e limites de contatos que não diminuem.
 */
export function lerFormulario(
  dados: Pick<GrupoParametrosPlataforma, 'grupo' | 'valores'>,
  form: FormParametros,
): { valores: Record<string, ValorParametro>; erros: Record<string, string> } {
  const valores: Record<string, ValorParametro> = { ...dados.valores }
  const erros: Record<string, string> = {}
  for (const c of camposDoGrupo(dados.grupo)) {
    const r = lerCampo(form, c.chave)
    if ('erro' in r) erros[c.chave] = r.erro
    else valores[c.chave] = r.valor
  }
  if (dados.grupo === 'planos') {
    for (let i = 1; i < PLANOS.length; i++) {
      const menor = PLANOS[i - 1]!
      const maior = PLANOS[i]!
      const kMenor = `planos.${menor.chave}.preco`
      const kMaior = `planos.${maior.chave}.preco`
      if (!erros[kMenor] && !erros[kMaior] && (centavos(valores[kMaior]) ?? 0) <= (centavos(valores[kMenor]) ?? 0)) {
        erros[kMaior] = `O preço do ${maior.nome} precisa ser maior que o do ${menor.nome}.`
      }
      const cMenor = `planos.${menor.chave}.contatos`
      const cMaior = `planos.${maior.chave}.contatos`
      if (!erros[cMenor] && !erros[cMaior] && limiteComparavel(valores[cMaior]) < limiteComparavel(valores[cMenor])) {
        erros[cMaior] = `O limite do ${maior.nome} não pode ser menor que o do ${menor.nome}.`
      }
    }
  }
  return { valores, erros }
}

/** O campo está diferente do valor salvo? (texto que não dá para ler conta como mudança: "Salvar" mostra o erro). */
export function campoMudou(dados: Pick<GrupoParametrosPlataforma, 'valores'>, form: FormParametros, chave: string): boolean {
  const r = lerCampo(form, chave)
  if ('erro' in r) return (form.textos[chave] ?? '') !== textoDoCampo(chave, dados.valores[chave]) || !!form.semLimite[chave] !== (dados.valores[chave] === null)
  return !mesmoValor(chave, r.valor, dados.valores[chave])
}

export function chavesAlteradas(dados: Pick<GrupoParametrosPlataforma, 'grupo' | 'valores'>, form: FormParametros): string[] {
  return camposDoGrupo(dados.grupo)
    .filter((c) => campoMudou(dados, form, c.chave))
    .map((c) => c.chave)
}

/** O campo difere do padrão (mostra "Usar o padrão")? */
export function difereDoPadrao(form: FormParametros, chave: string, padrao: ValorParametro | undefined): boolean {
  const r = lerCampo(form, chave)
  return 'erro' in r || !mesmoValor(chave, r.valor, padrao)
}

/** Ao salvar, o Toqqi testa o modelo na OpenAI ("Testando o modelo…") se um modelo ou esforço mudou. */
export function testaModelo(chaves: string[]): boolean {
  return chaves.some((k) => k.startsWith('ia.modelo.') || k.startsWith('ia.esforco.'))
}

// ── Textos do cartão ────────────────────────────────────────────────────────

/** "Alterado em 03/10/2026 às 14:32 por marcelo@toqqi.com" ou "Nunca alterado: valem os padrões." */
export function textoAlterado(g: Pick<GrupoParametrosPlataforma, 'alterado_em' | 'alterado_por'>): string {
  if (!g.alterado_em) return 'Nunca alterado: valem os padrões.'
  return `Alterado em ${formatarDataHora(g.alterado_em)}${g.alterado_por ? ` por ${g.alterado_por}` : ''}`
}

/** "Padrão: R$ 149,00, do código." (ligado ao campo por aria-describedby). */
export function textoPadrao(chave: string, padrao: ValorParametro | undefined, origem: string | undefined): string {
  const valor = campoDaChave(chave)?.tipo === 'contatos' && padrao === null ? 'sem limite' : formatarValor(chave, padrao)
  if (origem === 'codigo') return `Padrão: ${valor}, do código.`
  if (origem === 'ambiente') return `Padrão: ${valor}, da variável de ambiente.`
  if (origem === 'banco') return `Padrão: ${valor}. O valor em uso foi salvo aqui.`
  return `Padrão: ${valor}.`
}

// ── Diálogo de confirmação e histórico ──────────────────────────────────────

/** "Preço do Essencial: R$ 149,00 → R$ 159,00" (uma linha do histórico). */
export function linhaMudanca(m: MudancaParametro): string {
  const c = campoDaChave(m.chave)
  return `${c?.nome ?? m.chave}: ${formatarValor(m.chave, m.de)} → ${formatarValor(m.chave, m.para)}`
}

/** "Alfa, Beta e Gama" (todas) ou "Alfa, Beta…" (há mais contas que exemplos). */
export function listaNomes(nomes: string[], total: number): string {
  if (!nomes.length) return ''
  if (total > nomes.length) return `${nomes.join(', ')}…`
  return nomes.length === 1 ? nomes[0]! : `${nomes.slice(0, -1).join(', ')} e ${nomes[nomes.length - 1]}`
}

const contasTexto = (n: number) => (n === 1 ? '1 conta' : `${formatarNumero(n)} contas`)

/** A mudança diminui o que as contas têm? (limite, cota, teto, franquia menores ou mais análises por uso). */
export function diminui(m: MudancaParametro): boolean {
  const c = campoDaChave(m.chave)
  if (!c?.peso) return false
  if (c.peso === 'analises') return (inteiroDe(m.para) ?? 0) > (inteiroDe(m.de) ?? 0)
  if (c.peso === 'contatos') return limiteComparavel(m.para) < limiteComparavel(m.de)
  return (inteiroDe(m.para) ?? 0) < (inteiroDe(m.de) ?? 0)
}

/** O que a mudança faz nas contas (frase depois de "de → para"), ou null. */
export function textoImpacto(m: MudancaParametro, impacto: ImpactoParametro | undefined): string | null {
  const c = campoDaChave(m.chave)
  if (!c) return null
  if (c.tipo === 'dinheiro') return 'Vale para assinaturas novas e trocas de plano.'
  if (c.tipo === 'exclusao' && m.para === 'ligada' && m.de !== 'ligada') {
    return 'Na próxima rodada (9h), contas encerradas há 90 dias passam a ser avisadas e excluídas de vez.'
  }
  if (!diminui(m) || !impacto) return null
  const n = impacto.contas
  const valor = formatarValor(m.chave, m.para)
  if (c.peso === 'contatos') {
    if (n <= 0) return `Nenhuma conta tem mais de ${valor} contatos ativos.`
    const nomes = listaNomes(impacto.exemplos.map((e) => e.nome), n)
    const quem = `${contasTexto(n)} ${n === 1 ? 'tem' : 'têm'} mais de ${valor} contatos ativos${nomes ? ` (${nomes})` : ''}`
    return n === 1
      ? `${quem}: fica com eles, mas não cadastra, importa nem reativa contatos.`
      : `${quem}: ficam com eles, mas não cadastram, importam nem reativam contatos.`
  }
  if (c.peso === 'uso') {
    if (n <= 0) return `Nenhuma conta usou ${valor} ou mais neste mês.`
    return `${contasTexto(n)} já ${n === 1 ? 'usou' : 'usaram'} ${valor} ou mais neste mês.`
  }
  // Análises por uso que aumentam.
  if (n <= 0) return 'Nenhuma conta usa este nível.'
  return `${contasTexto(n)} ${n === 1 ? 'usa' : 'usam'} este nível.`
}

export const AVISO_DIMINUI = 'Vale na hora para todas as contas, inclusive quem já assina. Os Termos prometem aviso com antecedência razoável.'

export interface Confirmacao {
  titulo: string
  linhas: { chave: string; texto: string }[]
  /** Algo diminui: vale na hora para todas as contas. */
  aviso: string | null
}

/** O diálogo "Confirmar as mudanças em Planos?": uma linha por mudança, com o impacto, e o aviso se algo diminui. */
export function textoConfirmacao(rotulo: string, previa: Pick<PreviaParametros, 'mudancas' | 'impactos'>): Confirmacao {
  const impactos = new Map((previa.impactos ?? []).map((i) => [i.chave, i]))
  const linhas = previa.mudancas.map((m) => {
    const impacto = textoImpacto(m, impactos.get(m.chave))
    return { chave: m.chave, texto: `${linhaMudanca(m)}.${impacto ? ` ${impacto}` : ''}` }
  })
  return {
    titulo: `Confirmar as mudanças em ${rotulo}?`,
    linhas,
    aviso: previa.mudancas.some(diminui) ? AVISO_DIMINUI : null,
  }
}

// ── Abas da Plataforma ──────────────────────────────────────────────────────

export type AbaPlataforma = 'contas' | 'parametros'

export const ABAS_PLATAFORMA: { valor: AbaPlataforma; rotulo: string }[] = [
  { valor: 'contas', rotulo: 'Contas' },
  { valor: 'parametros', rotulo: 'Parâmetros' },
]

/** /plataforma/parametros abre "Parâmetros"; o resto (/plataforma, /plataforma/contas), "Contas". */
export function abaPlataformaDaRota(param: unknown): AbaPlataforma {
  const v = Array.isArray(param) ? param[0] : param
  return v === 'parametros' ? 'parametros' : 'contas'
}
