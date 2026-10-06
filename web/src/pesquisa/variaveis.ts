import { escaparHtml } from './logica'
import type { Variaveis } from './tipos'

export const ASSUNTO_PADRAO = 'o nosso atendimento'

export const VARIAVEIS_DISPONIVEIS: { chave: keyof Variaveis; rotulo: string; exemplo: string }[] = [
  { chave: 'empresa', rotulo: 'Nome da sua empresa', exemplo: '{empresa}' },
  { chave: 'nome', rotulo: 'Primeiro nome do cliente', exemplo: '{nome}' },
  { chave: 'assunto', rotulo: 'Assunto (padrão: "o nosso atendimento")', exemplo: '{assunto}' },
  { chave: 'referencia', rotulo: 'Referência (ex.: número do pedido)', exemplo: '{referencia}' },
]

function primeiroNome(nome: string | null | undefined): string {
  return (nome ?? '').trim().split(/\s+/)[0] ?? ''
}

/** `{nome}` e afins, sem pegar o miolo de uma citação `{{id}}` (etapa 5l). */
const variavel = (nome: string) => new RegExp(`(?<!\\{)\\{${nome}\\}(?!\\})`, 'g')
const RE_NOME = variavel('nome')
const RE_EMPRESA = variavel('empresa')
const RE_ASSUNTO = variavel('assunto')
const RE_REFERENCIA = variavel('referencia')

/**
 * Troca {empresa}, {nome}, {assunto} e {referencia} no texto. Citações `{{id}}` ficam como estão.
 * {nome} vazio leva junto a vírgula e o espaço antes: "Olá, {nome}!" → "Olá!".
 * No começo do texto, leva a vírgula depois: "{nome}, tudo bem?" → "Tudo bem?".
 */
export function renderizarVariaveis(texto: string | null | undefined, vars: Partial<Variaveis> = {}): string {
  if (!texto) return ''
  const nome = primeiroNome(vars.nome)
  let saida = texto
  if (nome) {
    saida = saida.replace(RE_NOME, nome)
  } else {
    // No começo: "{nome}, tudo bem?" → "tudo bem?" (com maiúscula).
    saida = saida.replace(/^\s*\{nome\}(?!\})\s*,?\s*(\S?)/, (_m, c: string) => c.toUpperCase())
    saida = saida.replace(/,?[ \t]*(?<!\{)\{nome\}(?!\})/g, '')
  }
  saida = saida
    .replace(RE_EMPRESA, (vars.empresa ?? '').trim())
    .replace(RE_ASSUNTO, (vars.assunto ?? '').trim() || ASSUNTO_PADRAO)
    .replace(RE_REFERENCIA, (vars.referencia ?? '').trim())
  // Espaços repetidos que sobram de variáveis vazias.
  return saida.replace(/[ \t]{2,}/g, ' ').replace(/ ([!?.,;:])/g, '$1').trim()
}

/**
 * As variáveis num HTML (prévia do editor; na página pública a API já mandou trocado): o valor entra escapado e os
 * espaços ficam como estão (como o `renderizar_html` da API). Citações `{{id}}` ficam para o `citarHtml`.
 */
export function renderizarVariaveisHtml(html: string | null | undefined, vars: Partial<Variaveis> = {}): string {
  if (!html) return ''
  return html
    .replace(RE_NOME, escaparHtml(primeiroNome(vars.nome)))
    .replace(RE_EMPRESA, escaparHtml((vars.empresa ?? '').trim()))
    .replace(RE_ASSUNTO, escaparHtml((vars.assunto ?? '').trim() || ASSUNTO_PADRAO))
    .replace(RE_REFERENCIA, escaparHtml((vars.referencia ?? '').trim()))
}
