// Endpoints da etapa 3b: chave de integração, webhooks de saída e WhatsApp automático (API oficial da Meta).
import { api } from './cliente'
import type {
  ChaveGerada,
  ChaveIntegracao,
  ConexaoWhatsapp,
  EntregaWebhook,
  EventoWebhook,
  Id,
  Mensagem,
  Pagina,
  ResultadoTesteWebhook,
  Webhook,
  WebhookCriado,
  WhatsappIntegracao,
} from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

export const chaveIntegracaoApi = {
  obter: () => api.get<ChaveIntegracao>('/integracoes/chave'),
  /** Gera (ou troca) a chave. A anterior para de valer na hora. */
  gerar: () => api.post<ChaveGerada>('/integracoes/chave'),
  revogar: () => api.delete('/integracoes/chave'),
}

export const webhooksApi = {
  listar: () => api.get<Webhook[]>('/integracoes/webhooks'),
  criar: (dados: { url: string; eventos: EventoWebhook[] }) => api.post<WebhookCriado>('/integracoes/webhooks', dados),
  atualizar: (id: Id, dados: { url?: string; eventos?: EventoWebhook[]; ativo?: boolean }) =>
    api.patch<Webhook>(`/integracoes/webhooks/${seg(id)}`, dados),
  excluir: (id: Id) => api.delete(`/integracoes/webhooks/${seg(id)}`),
  novoSegredo: (id: Id) => api.post<{ segredo: string }>(`/integracoes/webhooks/${seg(id)}/novo-segredo`),
  testar: (id: Id) => api.post<ResultadoTesteWebhook>(`/integracoes/webhooks/${seg(id)}/testar`),
  /** O contrato devolve uma lista simples; aceitamos também o formato paginado. */
  entregas: (id: Id, pagina = 1, sinal?: AbortSignal) =>
    api.get<EntregaWebhook[] | Pagina<EntregaWebhook>>(`/integracoes/webhooks/${seg(id)}/entregas`, { query: { pagina }, sinal }),
}

export const whatsappAutomaticoApi = {
  obter: () => api.get<WhatsappIntegracao>('/integracoes/whatsapp'),
  conectar: (dados: ConexaoWhatsapp) => api.put<WhatsappIntegracao>('/integracoes/whatsapp', dados),
  atualizar: (dados: { ativo?: boolean; excedente_ativo?: boolean }) => api.patch<WhatsappIntegracao>('/integracoes/whatsapp', dados),
  desconectar: () => api.delete('/integracoes/whatsapp'),
  enviarTeste: (telefone: string) => api.post<Mensagem | undefined>('/integracoes/whatsapp/teste', { telefone }),
}
