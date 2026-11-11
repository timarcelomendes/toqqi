// Etapa 5j: conectores (RD Station CRM, Omie, Bling; Pipedrive e HubSpot em 10/11/2026).
import { api } from './cliente'

export interface ResumoSincronizacao {
  empresas_novas: number
  empresas_existentes: number
  contatos_novos: number
  contatos_existentes: number
  sem_email_ou_telefone: number
  limite_do_plano: boolean
  cortado: boolean
}

export interface ConectorRd {
  conectado: boolean
  pesquisar_ao_ganhar?: boolean
  aviso_cadastrado?: boolean
  sincronizado_em?: string | null
  resumo?: ResumoSincronizacao | null
  erro?: string | null
  conectado_em?: string
}

export type ChaveCrm = 'pipedrive' | 'hubspot'

/** Pipedrive e HubSpot. `aviso_cadastrado` só no Pipedrive; `consultado_em` (última consulta da tarefa) só no HubSpot. */
export interface ConectorCrm extends ConectorRd {
  consultado_em?: string | null
}

export interface ConectorOmie {
  conectado: boolean
  pesquisar_ao_faturar?: boolean
  /** O endereço para cadastrar no Omie (portal do desenvolvedor › aplicativo › webhooks). */
  url_aviso?: string | null
  eventos?: string[]
  sincronizado_em?: string | null
  resumo?: (ResumoSincronizacao & { inativos: number }) | null
  erro?: string | null
}

export interface ConectorBling {
  /** O aplicativo do Toqqi no Bling está configurado (sem ele, "indisponível"). */
  disponivel: boolean
  conectado: boolean
  pesquisar_ao_faturar?: boolean
  sincronizando?: boolean
  eventos?: string[]
  sincronizado_em?: string | null
  resumo?: (ResumoSincronizacao & { inativos: number }) | null
  erro?: string | null
}

/** Um passo do teste de homologação do Bling. `intervalo_ms`: desde o fim do pedido anterior (o Bling aceita até 2 s). */
export interface PassoHomologacao {
  passo: string
  metodo: string
  status: number
  ms: number
  intervalo_ms: number | null
  renovou: boolean
}

export interface HomologacaoBling {
  ok: boolean
  passos: PassoHomologacao[]
  erro: string | null
  total_ms: number | null
}

export const conectoresApi = {
  ver: () =>
    api.get<{ rdstation_crm: ConectorRd; omie: ConectorOmie; bling: ConectorBling; pipedrive: ConectorCrm; hubspot: ConectorCrm }>('/integracoes/conectores'),
  autorizarBling: () => api.post<{ url: string }>('/integracoes/conectores/bling/autorizar'),
  alterarBling: (pesquisar_ao_faturar: boolean) => api.patch<ConectorBling>('/integracoes/conectores/bling', { pesquisar_ao_faturar }),
  sincronizarBling: () => api.post<ConectorBling>('/integracoes/conectores/bling/sincronizar'),
  desconectarBling: () => api.delete('/integracoes/conectores/bling'),
  /** Liga à conta a instalação feita pela loja do Bling (/conectar/bling?instalacao=). */
  ligarInstalacaoBling: (instalacao: string) => api.post<ConectorBling & { movido?: boolean }>('/integracoes/conectores/bling/instalacao', { instalacao }),
  conectarOmie: (app_key: string, app_secret: string, pesquisar_ao_faturar: boolean) =>
    api.put<ConectorOmie>('/integracoes/conectores/omie', { app_key, app_secret, pesquisar_ao_faturar }),
  alterarOmie: (pesquisar_ao_faturar: boolean) => api.patch<ConectorOmie>('/integracoes/conectores/omie', { pesquisar_ao_faturar }),
  sincronizarOmie: () => api.post<ResumoSincronizacao & { inativos: number }>('/integracoes/conectores/omie/sincronizar'),
  desconectarOmie: () => api.delete('/integracoes/conectores/omie'),
  conectarRd: (token: string, pesquisar_ao_ganhar: boolean) =>
    api.put<ConectorRd>('/integracoes/conectores/rdstation-crm', { token, pesquisar_ao_ganhar }),
  alterarRd: (pesquisar_ao_ganhar: boolean) => api.patch<ConectorRd>('/integracoes/conectores/rdstation-crm', { pesquisar_ao_ganhar }),
  sincronizarRd: () => api.post<ResumoSincronizacao>('/integracoes/conectores/rdstation-crm/sincronizar'),
  desconectarRd: () => api.delete('/integracoes/conectores/rdstation-crm'),
  conectarCrm: (chave: ChaveCrm, token: string, pesquisar_ao_ganhar: boolean) =>
    api.put<ConectorCrm>(`/integracoes/conectores/${chave}`, { token, pesquisar_ao_ganhar }),
  alterarCrm: (chave: ChaveCrm, pesquisar_ao_ganhar: boolean) => api.patch<ConectorCrm>(`/integracoes/conectores/${chave}`, { pesquisar_ao_ganhar }),
  sincronizarCrm: (chave: ChaveCrm) => api.post<ResumoSincronizacao>(`/integracoes/conectores/${chave}/sincronizar`),
  desconectarCrm: (chave: ChaveCrm) => api.delete(`/integracoes/conectores/${chave}`),
}
