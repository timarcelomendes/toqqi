// Etapa 5j: conectores (RD Station CRM).
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

export const conectoresApi = {
  ver: () => api.get<{ rdstation_crm: ConectorRd; omie: ConectorOmie; bling: ConectorBling }>('/integracoes/conectores'),
  autorizarBling: () => api.post<{ url: string }>('/integracoes/conectores/bling/autorizar'),
  alterarBling: (pesquisar_ao_faturar: boolean) => api.patch<ConectorBling>('/integracoes/conectores/bling', { pesquisar_ao_faturar }),
  sincronizarBling: () => api.post<ConectorBling>('/integracoes/conectores/bling/sincronizar'),
  desconectarBling: () => api.delete('/integracoes/conectores/bling'),
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
}
