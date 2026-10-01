// Regras puras de Configurações › Empresa (sem Vue): máscaras, o que vai para a API, validação com as mesmas
// mensagens do servidor e o preenchimento do endereço pelo CEP (ViaCEP).
import type { DadosEmpresaConta, DadosEmpresaContaIn } from '@/api/tipos'
import { formatarDocumento, telefoneParaCampo } from '@/utils/formatos'
import { apenasDigitos, emailValido, formatarTelefone } from '@/utils/validacao'

export const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA',
  'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
] as const
export type Uf = (typeof UFS)[number]

/** Limites do servidor (os campos também têm maxlength). */
export const LIMITES = {
  nome: 120,
  razao_social: 200,
  site: 200,
  logradouro: 150,
  numero: 20,
  complemento: 80,
  bairro: 80,
  cidade: 80,
  email_contato: 254,
} as const

/** As mesmas mensagens do servidor (422 `campos`). */
export const MENSAGENS = {
  nome: 'Informe o nome da empresa.',
  documento: 'CNPJ ou CPF inválido. Confira os números.',
  telefone: 'Informe o telefone com DDD (10 a 13 dígitos).',
  telefoneZero: 'Informe o telefone com DDD, sem o zero da operadora.',
  email_contato: 'Informe um e-mail válido, como nome@empresa.com.br.',
  site: 'Informe um site válido, como www.suaempresa.com.br.',
  cep: 'Informe o CEP com 8 números, como 01310-100.',
  uf: 'Escolha um estado (UF) da lista.',
} as const

/** O que a tela edita: tudo como texto, com as máscaras. */
export interface FormEmpresa {
  nome: string
  razao_social: string
  documento: string
  telefone: string
  email_contato: string
  site: string
  cep: string
  logradouro: string
  numero: string
  complemento: string
  bairro: string
  cidade: string
  uf: string
}

export const CAMPOS_EMPRESA = [
  'nome',
  'razao_social',
  'documento',
  'telefone',
  'email_contato',
  'site',
  'cep',
  'logradouro',
  'numero',
  'complemento',
  'bairro',
  'cidade',
  'uf',
] as const satisfies readonly (keyof FormEmpresa)[]

// ── Máscaras ────────────────────────────────────────────────────────────────

/** CEP enquanto digita: 01310-100. */
export function formatarCep(v: string | null | undefined): string {
  const d = apenasDigitos(v ?? '').slice(0, 8)
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d
}

/** CNPJ (ou CPF) enquanto digita. */
export const mascaraDocumento = (v: string) => formatarDocumento(v)

/**
 * Telefone enquanto digita: (11) 91234-5678. Começando com "+", fica como número com código do país (+351912345678),
 * sem a máscara brasileira (que cortaria os dígitos a mais).
 */
export function mascaraTelefone(v: string): string {
  if (v.trim().startsWith('+')) return `+${apenasDigitos(v).slice(0, 13)}`
  return formatarTelefone(v)
}

/** Telefone salvo (só dígitos, com o 55) → campo: brasileiro com máscara; de outro país, com "+" e sem cortar nada. */
export function telefoneDoCampo(v: string | null | undefined): string {
  const d = apenasDigitos(v ?? '')
  if (d.length > 11 && !(d.startsWith('55') && d.length <= 13)) return `+${d}`
  return telefoneParaCampo(d)
}

// ── Dados ↔ tela ────────────────────────────────────────────────────────────

/** Dados da API → campos da tela (com máscaras; null vira vazio). */
export function formDosDados(d: Partial<DadosEmpresaConta> | null | undefined): FormEmpresa {
  return {
    nome: d?.nome ?? '',
    razao_social: d?.razao_social ?? '',
    documento: formatarDocumento(d?.documento ?? ''),
    telefone: telefoneDoCampo(d?.telefone),
    email_contato: d?.email_contato ?? '',
    site: d?.site ?? '',
    cep: formatarCep(d?.cep ?? ''),
    logradouro: d?.logradouro ?? '',
    numero: d?.numero ?? '',
    complemento: d?.complemento ?? '',
    bairro: d?.bairro ?? '',
    cidade: d?.cidade ?? '',
    uf: d?.uf ?? '',
  }
}

const vazioParaNull = (v: string) => {
  const t = v.trim()
  return t ? t : null
}
const digitosOuNull = (v: string) => apenasDigitos(v) || null

/** Tela → corpo de PUT /conta/dados: sem espaços nas pontas, vazios como null, documento/telefone/CEP só com dígitos. */
export function corpoDoForm(f: FormEmpresa): DadosEmpresaContaIn {
  return {
    nome: f.nome.trim(),
    razao_social: vazioParaNull(f.razao_social),
    documento: digitosOuNull(f.documento),
    telefone: digitosOuNull(f.telefone),
    email_contato: vazioParaNull(f.email_contato),
    site: vazioParaNull(f.site),
    cep: digitosOuNull(f.cep),
    logradouro: vazioParaNull(f.logradouro),
    numero: vazioParaNull(f.numero),
    complemento: vazioParaNull(f.complemento),
    bairro: vazioParaNull(f.bairro),
    cidade: vazioParaNull(f.cidade),
    uf: vazioParaNull(f.uf)?.toUpperCase() ?? null,
  }
}

/**
 * Mudou algo de verdade? Compara o que iria para a API (máscara ou espaço a mais não contam).
 * Telefone com ou sem o 55 conta como o mesmo número.
 */
export function mesmosDados(a: FormEmpresa, b: FormEmpresa): boolean {
  const norm = (f: FormEmpresa) => {
    const c = corpoDoForm(f)
    return { ...c, telefone: c.telefone && c.telefone.length <= 11 ? `55${c.telefone}` : c.telefone }
  }
  return JSON.stringify(norm(a)) === JSON.stringify(norm(b))
}

// ── Validação (as mesmas regras e mensagens do servidor) ────────────────────

export function cpfValido(d: string): boolean {
  if (!/^\d{11}$/.test(d) || /^(\d)\1{10}$/.test(d)) return false
  for (const n of [9, 10]) {
    let soma = 0
    for (let i = 0; i < n; i++) soma += Number(d[i]) * (n + 1 - i)
    if (((soma * 10) % 11) % 10 !== Number(d[n])) return false
  }
  return true
}

export function cnpjValido(d: string): boolean {
  if (!/^\d{14}$/.test(d) || /^(\d)\1{13}$/.test(d)) return false
  for (const n of [12, 13]) {
    const pesos = [...Array.from({ length: n - 8 }, (_, i) => n - 7 - i), 9, 8, 7, 6, 5, 4, 3, 2]
    let soma = 0
    for (let i = 0; i < n; i++) soma += Number(d[i]) * pesos[i]!
    const dv = 11 - (soma % 11)
    if ((dv >= 10 ? 0 : dv) !== Number(d[n])) return false
  }
  return true
}

/** CPF ou CNPJ com os dígitos verificadores certos (aceita a máscara). */
export function documentoValido(v: string): boolean {
  const d = apenasDigitos(v)
  return d.length === 11 ? cpfValido(d) : d.length === 14 ? cnpjValido(d) : false
}

/** Mesma regra do telefone dos contatos: com DDD; 10 ou 11 dígitos ganham o 55; no fim, 12 ou 13 dígitos. */
export function erroTelefone(v: string): string | null {
  let d = apenasDigitos(v)
  if (!d) return null
  if (d.length === 10 || d.length === 11) {
    if (d.startsWith('0')) return MENSAGENS.telefoneZero
    d = `55${d}`
  }
  return d.length >= 12 && d.length <= 13 ? null : MENSAGENS.telefone
}

/** Site aceito pelo servidor: sem esquema vira https://; só http/https; domínio com ponto; até 200 caracteres. */
export function siteValido(v: string): boolean {
  const t = v.trim()
  if (!t || /\s/.test(t)) return false
  const completo = t.includes('://') ? t : `https://${t}`
  if (completo.length > LIMITES.site) return false
  let url: URL
  try {
    url = new URL(completo)
  } catch {
    return false
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return false
  if (url.username || url.password) return false
  const host = url.hostname.toLowerCase()
  // A mesma regra de domínio do servidor: com ponto e terminação só de letras (o navegador já converte acentos
  // para punycode, como o servidor faz com o "idna").
  return /^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(host)
}

/** Erros por campo antes de enviar (o servidor confere de novo; o que ele disser também aparece no campo). */
export function validarEmpresa(f: FormEmpresa): Partial<Record<keyof FormEmpresa, string>> {
  const e: Partial<Record<keyof FormEmpresa, string>> = {}
  const nome = f.nome.trim()
  if (nome.length < 2) e.nome = MENSAGENS.nome
  else if (nome.length > LIMITES.nome) e.nome = `Use no máximo ${LIMITES.nome} caracteres.`
  if (apenasDigitos(f.documento) && !documentoValido(f.documento)) e.documento = MENSAGENS.documento
  const tel = erroTelefone(f.telefone)
  if (tel) e.telefone = tel
  if (f.email_contato.trim() && !emailValido(f.email_contato)) e.email_contato = MENSAGENS.email_contato
  if (f.site.trim() && !siteValido(f.site)) e.site = MENSAGENS.site
  const cep = apenasDigitos(f.cep)
  if ((cep || f.cep.trim()) && cep.length !== 8) e.cep = MENSAGENS.cep
  if (f.uf && !(UFS as readonly string[]).includes(f.uf.toUpperCase())) e.uf = MENSAGENS.uf
  for (const campo of ['razao_social', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade'] as const) {
    if (f[campo].trim().length > LIMITES[campo]) e[campo] = `Use no máximo ${LIMITES[campo]} caracteres.`
  }
  return e
}

// ── Endereço pelo CEP (ViaCEP) ──────────────────────────────────────────────

export interface EnderecoCep {
  logradouro: string
  bairro: string
  cidade: string
  uf: string
}

export const TEMPO_LIMITE_CEP = 4000

/**
 * Busca o endereço do CEP no ViaCEP (https://viacep.com.br/ws/{cep}/json/). Qualquer problema (CEP que não existe,
 * sem internet, demora de mais de ~4 s) devolve null: a pessoa segue preenchendo à mão, sem aviso.
 */
export async function buscarCep(
  cep: string,
  opcoes: { fetch?: typeof fetch; tempoLimite?: number; sinal?: AbortSignal } = {},
): Promise<EnderecoCep | null> {
  const d = apenasDigitos(cep)
  if (d.length !== 8) return null
  const controle = new AbortController()
  const tempo = setTimeout(() => controle.abort(), opcoes.tempoLimite ?? TEMPO_LIMITE_CEP)
  const cancelar = () => controle.abort()
  opcoes.sinal?.addEventListener('abort', cancelar)
  try {
    const buscar = opcoes.fetch ?? globalThis.fetch
    const r = await buscar(`https://viacep.com.br/ws/${d}/json/`, { signal: controle.signal })
    if (!r.ok) return null
    const j = (await r.json()) as Record<string, unknown> | null
    if (!j || typeof j !== 'object' || j.erro === true || j.erro === 'true') return null
    const texto = (v: unknown) => (typeof v === 'string' ? v.trim() : '')
    const uf = texto(j.uf).toUpperCase()
    return {
      logradouro: texto(j.logradouro),
      bairro: texto(j.bairro),
      cidade: texto(j.localidade),
      uf: (UFS as readonly string[]).includes(uf) ? uf : '',
    }
  } catch {
    return null
  } finally {
    clearTimeout(tempo)
    opcoes.sinal?.removeEventListener('abort', cancelar)
  }
}

/** Põe o endereço do CEP só nos campos vazios (o que a pessoa já escreveu fica). Devolve os campos preenchidos. */
export function preencherEndereco(f: FormEmpresa, e: EnderecoCep): (keyof EnderecoCep)[] {
  const preenchidos: (keyof EnderecoCep)[] = []
  for (const campo of ['logradouro', 'bairro', 'cidade', 'uf'] as const) {
    if (!f[campo].trim() && e[campo]) {
      f[campo] = e[campo]
      preenchidos.push(campo)
    }
  }
  return preenchidos
}
