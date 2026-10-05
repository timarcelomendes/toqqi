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

export const conectoresApi = {
  ver: () => api.get<{ rdstation_crm: ConectorRd }>('/integracoes/conectores'),
  conectarRd: (token: string, pesquisar_ao_ganhar: boolean) =>
    api.put<ConectorRd>('/integracoes/conectores/rdstation-crm', { token, pesquisar_ao_ganhar }),
  alterarRd: (pesquisar_ao_ganhar: boolean) => api.patch<ConectorRd>('/integracoes/conectores/rdstation-crm', { pesquisar_ao_ganhar }),
  sincronizarRd: () => api.post<ResumoSincronizacao>('/integracoes/conectores/rdstation-crm/sincronizar'),
  desconectarRd: () => api.delete('/integracoes/conectores/rdstation-crm'),
}
