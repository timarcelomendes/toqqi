// Regras puras de Configurações › Crescimento (etapa 5c): padrões, limites, conferência antes de salvar e a prévia do
// convite (como na pesquisa) e da oferta (balão do WhatsApp) com valores de exemplo.
import type { ConfigCrescimento, ConviteIndicacao } from '@/api/tipos'
import { renderizarVariaveis } from '@/pesquisa/variaveis'
import { textoOferta, type ValoresOferta } from '@/modulos/crescimento/logica'

export const LIMITES_CRESCIMENTO = {
  titulo_convite: 120,
  texto_convite: 500,
  recompensa: 300,
  texto_oferta: 1000,
} as const

/** Os padrões da API (sem linha no banco). */
export const PADRAO_CRESCIMENTO: Readonly<ConfigCrescimento> = Object.freeze({
  indicacoes_ativas: false,
  titulo_convite: 'Que bom que você gostou!',
  texto_convite: 'Conhece outra empresa que ganharia com a {empresa}? Indique e a gente entra em contato com cuidado.',
  recompensa: null,
  texto_oferta:
    'Olá, {nome}! Aqui é {representante}, da {empresa}. Obrigado pela ótima avaliação! Preparei uma condição especial para a {empresa_cliente}. Posso te contar?',
})

/** Exemplo no campo da recompensa (vazio por padrão). */
export const EXEMPLO_RECOMPENSA = 'Se a indicação virar cliente, você ganha 10% no próximo pedido.'

/** Pronta para salvar: textos aparados, recompensa vazia vira null. */
export function normalizarConfigCrescimento(c: ConfigCrescimento): ConfigCrescimento {
  return {
    indicacoes_ativas: !!c.indicacoes_ativas,
    titulo_convite: (c.titulo_convite ?? '').trim(),
    texto_convite: (c.texto_convite ?? '').trim(),
    recompensa: (c.recompensa ?? '').trim() || null,
    texto_oferta: (c.texto_oferta ?? '').trim(),
  }
}

/** Erros por campo (mesmas chaves da API). */
export function validarConfigCrescimento(c: ConfigCrescimento): Record<string, string> {
  const e: Record<string, string> = {}
  const n = normalizarConfigCrescimento(c)
  if (!n.titulo_convite) e.titulo_convite = 'Escreva o título do convite.'
  else if (n.titulo_convite.length > LIMITES_CRESCIMENTO.titulo_convite) e.titulo_convite = `Use até ${LIMITES_CRESCIMENTO.titulo_convite} caracteres.`
  if (!n.texto_convite) e.texto_convite = 'Escreva o texto do convite.'
  else if (n.texto_convite.length > LIMITES_CRESCIMENTO.texto_convite) e.texto_convite = `Use até ${LIMITES_CRESCIMENTO.texto_convite} caracteres.`
  if ((n.recompensa ?? '').length > LIMITES_CRESCIMENTO.recompensa) e.recompensa = `Use até ${LIMITES_CRESCIMENTO.recompensa} caracteres.`
  if (!n.texto_oferta) e.texto_oferta = 'Escreva o texto da oferta.'
  else if (n.texto_oferta.length > LIMITES_CRESCIMENTO.texto_oferta) e.texto_oferta = `Use até ${LIMITES_CRESCIMENTO.texto_oferta} caracteres.`
  return e
}

/** O cartão do convite como o cliente vê ({empresa} = a conta, {nome} = primeiro nome de quem respondeu). */
export function previaConvite(c: Pick<ConfigCrescimento, 'titulo_convite' | 'texto_convite' | 'recompensa'>, v: { empresa: string; nome: string }): ConviteIndicacao {
  return {
    titulo: renderizarVariaveis(c.titulo_convite, v),
    texto: renderizarVariaveis(c.texto_convite, v),
    recompensa: renderizarVariaveis(c.recompensa, v) || null,
  }
}

/** O texto da oferta como abre no WhatsApp. */
export function previaOferta(c: Pick<ConfigCrescimento, 'texto_oferta'>, v: ValoresOferta): string {
  return textoOferta(c.texto_oferta, v)
}
