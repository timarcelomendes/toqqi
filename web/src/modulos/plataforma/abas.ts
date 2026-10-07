// Abas da Plataforma (etapa 5h, docs/api-etapa-5h.md §5): Visão geral (/plataforma), Contas (/plataforma/contas),
// Parâmetros (/plataforma/parametros), Erros (/plataforma/erros) e Feedback (/plataforma/feedback; docs/api-feedback.md),
// nesta ordem.

export type AbaPlataforma = 'visao' | 'contas' | 'parametros' | 'erros' | 'feedback'

export const ABAS_PLATAFORMA: { valor: AbaPlataforma; rotulo: string }[] = [
  { valor: 'visao', rotulo: 'Visão geral' },
  { valor: 'contas', rotulo: 'Contas' },
  { valor: 'parametros', rotulo: 'Parâmetros' },
  { valor: 'erros', rotulo: 'Erros' },
  { valor: 'feedback', rotulo: 'Feedback' },
]

const COM_ENDERECO: AbaPlataforma[] = ['contas', 'parametros', 'erros', 'feedback']

function ehAbaComEndereco(v: unknown): v is AbaPlataforma {
  return COM_ENDERECO.includes(v as AbaPlataforma)
}

/**
 * A aba do endereço: o parâmetro `:aba` da rota (contas, parametros, erros, feedback) ou, sem ele, o último pedaço do caminho
 * (uma rota fixa como /plataforma/contas); o resto (/plataforma), a Visão geral.
 */
export function abaPlataformaDaRota(param: unknown, caminho = ''): AbaPlataforma {
  const v = Array.isArray(param) ? param[0] : param
  if (ehAbaComEndereco(v)) return v
  const ultimo = caminho.replace(/\/+$/, '').split('/').pop()
  return ehAbaComEndereco(ultimo) ? ultimo : 'visao'
}

/** O endereço de cada aba. */
export function caminhoDaAba(aba: AbaPlataforma): string {
  return aba === 'visao' ? '/plataforma' : `/plataforma/${aba}`
}
