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

/**
 * Troca {empresa}, {nome}, {assunto} e {referencia} no texto.
 * {nome} vazio leva junto a vírgula e o espaço antes: "Olá, {nome}!" → "Olá!".
 * No começo do texto, leva a vírgula depois: "{nome}, tudo bem?" → "Tudo bem?".
 */
export function renderizarVariaveis(texto: string | null | undefined, vars: Partial<Variaveis> = {}): string {
  if (!texto) return ''
  const nome = primeiroNome(vars.nome)
  let saida = texto
  if (nome) {
    saida = saida.replace(/\{nome\}/g, nome)
  } else {
    // No começo: "{nome}, tudo bem?" → "tudo bem?" (com maiúscula).
    saida = saida.replace(/^\s*\{nome\}\s*,?\s*(\S?)/, (_m, c: string) => c.toUpperCase())
    saida = saida.replace(/,?[ \t]*\{nome\}/g, '')
  }
  saida = saida
    .replace(/\{empresa\}/g, (vars.empresa ?? '').trim())
    .replace(/\{assunto\}/g, (vars.assunto ?? '').trim() || ASSUNTO_PADRAO)
    .replace(/\{referencia\}/g, (vars.referencia ?? '').trim())
  // Espaços repetidos que sobram de variáveis vazias.
  return saida.replace(/[ \t]{2,}/g, ' ').replace(/ ([!?.,;:])/g, '$1').trim()
}
