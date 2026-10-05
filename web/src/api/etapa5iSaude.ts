// Etapa 5i: saúde da conta (nota 0–100 por empresa, com os porquês), a carteira por saúde no Início e as renovações.
import { api } from './cliente'
import type { Id, Referencia, ValorDecimal } from './tipos'

export type FaixaSaude = 'saudavel' | 'atencao' | 'risco' | 'sem_dados'
export type TomPorque = 'positivo' | 'neutro' | 'negativo'

/** O resumo que vem em cada item de GET /empresas (null: pausada, perdida ou sem permissão de números). */
export interface SaudeResumo {
  faixa: FaixaSaude
  nota: number | null
  destaque: boolean
  porque: string | null
}

export interface SaudeEmpresa {
  faixa: FaixaSaude
  nota: number | null
  criterios: { criterio: string; rotulo: string; pontos: number; maximo: number; texto: string | null; tom: TomPorque }[]
  porques: { texto: string; tom: TomPorque }[]
  renovacao: { em: string; dias: number } | null
  destaque: boolean
}

export interface CarteiraSaude {
  faixas: Record<FaixaSaude, { empresas: number; receita: ValorDecimal }>
  empresas: number
  receita: ValorDecimal
  sem_valor: number
  renovacoes_em_risco: {
    empresas: number
    receita: ValorDecimal
    primeira: { empresa: Referencia; renovacao_em: string; dias: number; valor_mensal: ValorDecimal | null } | null
  }
}

export interface RenovacaoProxima {
  empresa: Referencia
  renovacao_em: string
  dias: number
  valor_mensal: ValorDecimal | null
  responsavel: Referencia | null
  saude: { faixa: FaixaSaude; nota: number | null; porques: { texto: string; tom: TomPorque }[] }
  destaque: boolean
}

export const saudeApi = {
  empresa: (id: Id) => api.get<{ empresa_id: Id; saude: SaudeEmpresa | null }>(`/empresas/${encodeURIComponent(String(id))}/saude`),
  carteira: (grupo_id?: Id | '', sinal?: AbortSignal) =>
    api.get<CarteiraSaude>('/painel/saude', { query: grupo_id ? { grupo_id } : {}, sinal }),
  renovacoes: (grupo_id?: Id | '', sinal?: AbortSignal) =>
    api.get<{ itens: RenovacaoProxima[]; resumo: { empresas: number; receita: ValorDecimal } }>('/relatorios/renovacoes', {
      query: grupo_id ? { grupo_id } : {},
      sinal,
    }),
}
