// Endpoints da etapa 5a (docs/api-etapa-5a.md): assinatura e cobrança pelo Asaas.
// O aviso do topo das telas vem na sessão (`conta.cobranca`, em GET /eu e no login); a Plataforma usa `plataformaApi`.
import { api } from './cliente'
import type { DadosCobranca, EstadoAssinatura, PlanoAssinatura } from './tipos'

export const assinaturaApi = {
  /** Os 3 planos, na ordem (qualquer usuário logado). */
  planos: () => api.get<PlanoAssinatura[]>('/assinatura/planos'),
  obter: (sinal?: AbortSignal) => api.get<EstadoAssinatura>('/assinatura', { sinal }),
  /**
   * Cria a assinatura no Asaas (a primeira fatura vence no último dia do teste ou amanhã). 409 `ja_assinada` e
   * `cortesia`; 422 `limite_do_plano` e `cobranca_recusada` (com campos); 503 `cobranca_indisponivel`.
   */
  assinar: (dados: DadosCobranca & { plano: PlanoAssinatura['chave'] }) => api.post<EstadoAssinatura>('/assinatura', dados),
  /** Também muda o valor das faturas em aberto. 409 `sem_assinatura`; 422 `limite_do_plano`. */
  trocarPlano: (plano: PlanoAssinatura['chave']) => api.put<EstadoAssinatura>('/assinatura/plano', { plano }),
  alterarDados: (dados: DadosCobranca) => api.put<EstadoAssinatura>('/assinatura/dados', dados),
  /** Remove a assinatura no Asaas (com as faturas em aberto); o uso segue até o fim do período pago. */
  cancelar: () => api.post<EstadoAssinatura>('/assinatura/cancelar'),
}
