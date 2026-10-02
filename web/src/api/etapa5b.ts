// Endpoints da etapa 5b (docs/api-etapa-5b.md): Ajuda e assistente. A cota do plano também vem em GET /conta/ia (`iaApi`).
import { api } from './cliente'
import type { ConteudoAjuda, EstadoAssistente, MensagemHistorico, RespostaAssistente } from './tipos'

export const ajudaApi = {
  /** O conteúdo inteiro, para qualquer usuário logado (a API manda com cache de 5 minutos). */
  obter: (sinal?: AbortSignal) => api.get<ConteudoAjuda>('/ajuda', { sinal }),
}

export const assistenteApi = {
  /** Se está disponível (e o motivo, quando não), a cota do mês e 3 perguntas de exemplo conforme as permissões. */
  estado: (sinal?: AbortSignal) => api.get<EstadoAssistente>('/assistente', { sinal }),
  /**
   * Gasta 1 análise da cota (devolvida se falhar). `historico`: as últimas 8 mensagens. 409 `conta_pausada` e
   * `cota_esgotada`; 429 `limite_perguntas`; 503 `ia_indisponivel`.
   */
  perguntar: (pergunta: string, historico: MensagemHistorico[], sinal?: AbortSignal) =>
    api.post<RespostaAssistente>('/assistente/perguntar', { pergunta, historico }, { sinal }),
}
