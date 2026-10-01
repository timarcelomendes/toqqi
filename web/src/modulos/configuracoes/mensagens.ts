// Regras puras das Configurações de envio: variáveis dos textos, inserção no cursor,
// prévia do e-mail e conferência antes de salvar. Sem Vue, para testar com facilidade.
import type { ConfigEnvios, TipoFormulario } from '@/api/tipos'

export type ChaveVariavel = 'nome' | 'empresa' | 'empresa_cliente' | 'link' | 'nota'

export interface VariavelMensagem {
  chave: ChaveVariavel
  texto: string
  rotulo: string
}

export const VARIAVEIS: Record<ChaveVariavel, VariavelMensagem> = {
  nome: { chave: 'nome', texto: '{nome}', rotulo: 'Primeiro nome do cliente' },
  empresa: { chave: 'empresa', texto: '{empresa}', rotulo: 'Nome da sua empresa' },
  empresa_cliente: { chave: 'empresa_cliente', texto: '{empresa_cliente}', rotulo: 'Empresa do cliente' },
  link: { chave: 'link', texto: '{link}', rotulo: 'Link da pesquisa' },
  nota: { chave: 'nota', texto: '{nota}', rotulo: 'Nota que o cliente deu' },
}

/** Quais variáveis cada texto aceita (o contrato: {link} só no WhatsApp, {nota} só no agradecimento). */
export const VARIAVEIS_EMAIL: VariavelMensagem[] = [VARIAVEIS.nome, VARIAVEIS.empresa, VARIAVEIS.empresa_cliente]
export const VARIAVEIS_WHATSAPP: VariavelMensagem[] = [...VARIAVEIS_EMAIL, VARIAVEIS.link]
export const VARIAVEIS_AGRADECIMENTO: VariavelMensagem[] = [VARIAVEIS.nome, VARIAVEIS.empresa, VARIAVEIS.nota]

export const LIMITE_ASSUNTO = 150
export const LIMITE_TEXTO = 2000
export const DIAS_LEMBRETES_PADRAO = [3, 7, 15]

/**
 * Insere `trecho` no lugar da seleção (ou do cursor) e devolve o texto novo e onde o cursor fica.
 * Sem posição conhecida, coloca no fim.
 */
export function inserirNoCursor(
  texto: string,
  trecho: string,
  inicio?: number | null,
  fim?: number | null,
): { texto: string; cursor: number } {
  const tam = texto.length
  const ini = Math.min(Math.max(inicio ?? tam, 0), tam)
  const fi = Math.min(Math.max(fim ?? ini, ini), tam)
  return { texto: texto.slice(0, ini) + trecho + texto.slice(fi), cursor: ini + trecho.length }
}

export interface ValoresExemplo {
  nome?: string | null
  empresa?: string | null
  empresa_cliente?: string | null
  link?: string | null
  nota?: string | number | null
}

/**
 * Troca as variáveis como a plataforma faz: {nome} é o primeiro nome e, se vazio, leva junto a
 * vírgula e o espaço antes ("Olá, {nome}!" → "Olá!"). Variáveis desconhecidas ficam como estão.
 */
export function renderizarMensagem(texto: string | null | undefined, v: ValoresExemplo = {}): string {
  if (!texto) return ''
  const nome = (v.nome ?? '').trim().split(/\s+/)[0] ?? ''
  let s = texto
  if (nome) s = s.replace(/\{nome\}/g, nome)
  else {
    s = s.replace(/^\s*\{nome\}\s*,?\s*(\S?)/, (_m, c: string) => c.toUpperCase())
    s = s.replace(/,?[ \t]*\{nome\}/g, '')
  }
  s = s
    .replace(/\{empresa_cliente\}/g, (v.empresa_cliente ?? '').trim())
    .replace(/\{empresa\}/g, (v.empresa ?? '').trim())
    .replace(/\{link\}/g, (v.link ?? '').trim())
    .replace(/\{nota\}/g, v.nota === null || v.nota === undefined ? '' : String(v.nota).trim())
  return s
    .split('\n')
    .map((l) => l.replace(/[ \t]{2,}/g, ' ').replace(/ ([!?.,;:])/g, '$1').trimEnd())
    .join('\n')
    .trim()
}

/** Parágrafos do e-mail: separados por linha em branco (quebras simples ficam dentro do parágrafo). */
export function paragrafos(texto: string): string[] {
  return texto
    .split(/\n[ \t]*\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
}

export type CorNota = 'vermelho' | 'amarelo' | 'verde'

/** NPS: 0–6 vermelho, 7–8 amarelo, 9–10 verde. */
export function corNotaNps(n: number): CorNota {
  return n <= 6 ? 'vermelho' : n <= 8 ? 'amarelo' : 'verde'
}

/** CSAT/estrelas (1–5): 1–2 vermelho, 3 amarelo, 4–5 verde. */
export function corNotaCsat(n: number): CorNota {
  return n <= 2 ? 'vermelho' : n === 3 ? 'amarelo' : 'verde'
}

export type BlocoNota =
  | { tipo: 'nps'; botoes: { nota: number; cor: CorNota }[]; rotuloMin: string; rotuloMax: string }
  | { tipo: 'csat'; botoes: { nota: number; cor: CorNota }[] }
  | { tipo: 'botao'; texto: string }

export function blocoNota(tipo: TipoFormulario | null | undefined): BlocoNota {
  if (tipo === 'csat') return { tipo: 'csat', botoes: [1, 2, 3, 4, 5].map((nota) => ({ nota, cor: corNotaCsat(nota) })) }
  if (tipo === 'personalizado') return { tipo: 'botao', texto: 'Responder pesquisa' }
  return {
    tipo: 'nps',
    botoes: Array.from({ length: 11 }, (_, nota) => ({ nota, cor: corNotaNps(nota) })),
    rotuloMin: 'Nada provável',
    rotuloMax: 'Muito provável',
  }
}

export interface PreviaEmail {
  de: string
  /** Logo do cabeçalho: o do formulário dos convites, senão o da empresa; null = e-mail sem cabeçalho. */
  logo: string | null
  responderPara: string | null
  assunto: string
  paragrafos: string[]
  bloco: BlocoNota
  rodape: string
  descadastro: string
}

/** Monta a prévia do convite ou do lembrete com valores de exemplo. */
export function montarPreviaEmail(
  config: Pick<ConfigEnvios, 'remetente_nome' | 'responder_para' | 'assunto_convite' | 'texto_convite' | 'assunto_lembrete' | 'texto_lembrete'>,
  qual: 'convite' | 'lembrete',
  tipoFormulario: TipoFormulario | null | undefined,
  exemplo: ValoresExemplo,
  logo: string | null = null,
): PreviaEmail {
  const empresa = (exemplo.empresa ?? '').trim()
  const remetente = (config.remetente_nome ?? '').trim() || empresa || 'Sua empresa'
  const assunto = qual === 'convite' ? config.assunto_convite : config.assunto_lembrete
  const texto = qual === 'convite' ? config.texto_convite : config.texto_lembrete
  return {
    de: `${remetente} via Toqqi`,
    logo: logo || null,
    responderPara: (config.responder_para ?? '').trim() || null,
    assunto: renderizarMensagem(assunto, exemplo),
    paragrafos: paragrafos(renderizarMensagem(texto, exemplo)),
    bloco: blocoNota(tipoFormulario),
    rodape: `Você recebeu esta pesquisa porque é cliente de ${empresa || 'sua empresa'}.`,
    descadastro: 'Não quero mais receber pesquisas',
  }
}

/** Ajusta a lista de dias ao número de lembretes, mantendo o que já existe e sempre crescente (1–30). */
export function ajustarDiasLembretes(dias: number[], quantidade: number): number[] {
  const n = Math.max(0, Math.min(3, Math.trunc(quantidade)))
  const saida: number[] = []
  for (let i = 0; i < n; i++) {
    const anterior = saida[i - 1] ?? 0
    const atual = dias[i]
    let d = typeof atual === 'number' && Number.isFinite(atual) ? atual : (DIAS_LEMBRETES_PADRAO[i] ?? anterior + 1)
    if (d <= anterior) d = anterior + 1
    saida.push(Math.min(30, d))
  }
  return saida
}

function inteiroEntre(v: unknown, min: number, max: number): boolean {
  return typeof v === 'number' && Number.isInteger(v) && v >= min && v <= max
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * Confere a configuração antes de salvar (as mesmas regras da API, para avisar na hora).
 * Devolve erros por campo, com as mesmas chaves que a API usa em `campos`.
 */
export function validarConfig(c: ConfigEnvios): Record<string, string> {
  const e: Record<string, string> = {}
  if (!inteiroEntre(c.intervalo_dias, 30, 365)) e.intervalo_dias = 'Use um número entre 30 e 365 dias.'
  if (!inteiroEntre(c.descanso_dias, 0, 180)) e.descanso_dias = 'Use um número entre 0 e 180 dias.'
  if (!inteiroEntre(c.lembretes, 0, 3)) e.lembretes = 'Escolha de 0 a 3 lembretes.'
  else {
    const dias = c.dias_lembretes ?? []
    if (dias.length !== c.lembretes) e.dias_lembretes = 'Informe o dia de cada lembrete.'
    else if (dias.some((d) => !inteiroEntre(d, 1, 30))) e.dias_lembretes = 'Cada lembrete precisa ser entre 1 e 30 dias depois do convite.'
    else if (dias.some((d, i) => i > 0 && d <= dias[i - 1]!)) e.dias_lembretes = 'Cada lembrete precisa vir depois do anterior.'
  }
  const hora = /^([01]\d|2[0-3]):[0-5]\d$/
  if (!hora.test(c.janela_inicio ?? '')) e.janela_inicio = 'Informe um horário, por exemplo 08:00.'
  if (!hora.test(c.janela_fim ?? '')) e.janela_fim = 'Informe um horário, por exemplo 18:00.'
  else if (!e.janela_inicio && c.janela_fim <= c.janela_inicio) e.janela_fim = 'O fim precisa ser depois do início.'
  if (c.responder_para && c.responder_para.trim() && !EMAIL.test(c.responder_para.trim())) e.responder_para = 'Confira o e-mail.'
  if (c.remetente_nome && c.remetente_nome.length > 100) e.remetente_nome = 'Use até 100 caracteres.'
  for (const k of ['assunto_convite', 'assunto_lembrete'] as const) {
    const v = (c[k] ?? '').trim()
    if (!v) e[k] = 'Escreva o assunto.'
    else if (v.length > LIMITE_ASSUNTO) e[k] = `Use até ${LIMITE_ASSUNTO} caracteres.`
  }
  for (const k of ['texto_convite', 'texto_lembrete', 'texto_whatsapp'] as const) {
    const v = (c[k] ?? '').trim()
    if (!v) e[k] = 'Escreva o texto.'
    else if (v.length > LIMITE_TEXTO) e[k] = `Use até ${LIMITE_TEXTO} caracteres.`
  }
  if (!e.texto_whatsapp && !(c.texto_whatsapp ?? '').includes('{link}')) {
    e.texto_whatsapp = 'Inclua {link}: é por ele que a pessoa abre a pesquisa.'
  }
  if (c.agradecimento_ativo) {
    for (const g of ['promotor', 'neutro', 'detrator'] as const) {
      const v = (c.agradecimento?.[g] ?? '').trim()
      if (!v) e[`agradecimento.${g}`] = 'Escreva o texto.'
      else if (v.length > LIMITE_TEXTO) e[`agradecimento.${g}`] = `Use até ${LIMITE_TEXTO} caracteres.`
    }
  }
  return e
}

/** A API pode mandar "dias_lembretes.1" ou "agradecimento[promotor]": normaliza para a chave que a tela usa. */
export function normalizarCampos(campos: Record<string, string>): Record<string, string> {
  const saida: Record<string, string> = {}
  for (const [k, msg] of Object.entries(campos)) {
    let chave = k.replace(/\[(\w+)\]/g, '.$1')
    if (chave.startsWith('dias_lembretes')) chave = 'dias_lembretes'
    saida[chave] ??= msg
  }
  return saida
}
