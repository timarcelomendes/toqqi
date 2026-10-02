/** Regras da página do site (rota "/"), sem DOM, para os testes. */

/** 262399.99 → "R$ 262.399,99" (sempre com centavos, como no painel). */
export function formatarReais(valor: number): string {
  return 'R$ ' + valor.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** Passo seguinte do "Como funciona" (1 → 2 → 3 → 4 → 1). */
export function proximoPasso(atual: number, total = 4): number {
  return (atual % total) + 1
}

/** Valor do contador em `k` (0 a 1) com desaceleração no fim; termina exatamente em `fim`. */
export function valorContador(fim: number, k: number): number {
  if (k >= 1) return fim
  if (k <= 0) return 0
  return Math.round(fim * (1 - Math.pow(1 - k, 3)))
}

export interface SessaoGuardada {
  token?: unknown
  expira_em?: unknown
}

/**
 * Quem já entrou neste navegador vê "Abrir o Toqqi" em vez de "Entrar". Lê o mesmo item que o app guarda
 * (`toqqi.sessao`, stores/sessao.ts) só para decidir o rótulo; nada é enviado.
 */
export function temSessao(bruto: string | null, agora = Date.now()): boolean {
  if (!bruto) return false
  try {
    const dados = JSON.parse(bruto) as SessaoGuardada
    if (!dados || typeof dados.token !== 'string' || !dados.token) return false
    if (typeof dados.expira_em === 'string') {
      const fim = Date.parse(dados.expira_em)
      if (!Number.isNaN(fim) && fim <= agora) return false
    }
    return true
  } catch {
    return false
  }
}

export interface FalaConversa {
  pergunta: string
  status: string[]
  consultou: string
  resposta: string
}

/** A conversa de exemplo do ToqqiAI (dados fictícios, os mesmos do resto da página). */
export const CONVERSA: FalaConversa[] = [
  {
    pergunta: 'Por que o NPS caiu em setembro?',
    status: ['Consultando a evolução mensal…', 'Lendo os comentários de setembro…'],
    consultou: 'Consultou: evolução mensal · comentários',
    resposta:
      'O NPS de setembro foi 14, contra 43 em julho. A queda vem quase toda de Prazo e entrega: 6 reclamações entre 28 e 30/09, todas citando a transportadora nova.',
  },
  {
    pergunta: 'Quais clientes grandes estão em risco?',
    status: ['Buscando as empresas…', 'Conferindo os indicadores…'],
    consultou: 'Consultou: empresas · indicadores',
    resposta:
      'Duas empresas acima da mediana de valor têm NPS negativo: Pequi Marista (R$ 52.000/mês, com o Felipe) e Embalagens Meia Ponte (R$ 31.200/mês, com a Carla). A Embalagens deu nota 4 e reclamou da entrega.',
  },
  {
    pergunta: 'Como mudo o prazo dos planos de ação?',
    status: ['Procurando na Ajuda…'],
    consultou: 'Consultou: Ajuda',
    resposta:
      'Em Configurações › Planos de ação, no campo “Prazo para tratar”, informe os dias de detrator, neutro e promotor (de 1 a 90) e clique em “Salvar alterações”. O botão “Prazos automáticos”, na tela Planos de ação, leva direto até lá.',
  },
]

export const COTA_EXEMPLO = 500
