// Endpoints da etapa 3a: envios por e-mail, fila, histórico, lembretes, robô e descadastros.
import { api, requisitar } from './cliente'
import type {
  ConfigEnvios,
  ContatoEnvio,
  Descadastro,
  Envio,
  Id,
  Mensagem,
  Pagina,
  PreCondicoes,
  ResultadoDisparo,
  ResultadoTarefa,
  ResumoEnvios,
  SituacaoContato,
  WhatsappContato,
  CanalEnvio,
  TipoEnvio,
  SituacaoEnvio,
} from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

/** Filtros da fila (GET /envios/contatos); os mesmos vão em `filtros` do disparo para toda a fila. */
export interface FiltrosFila {
  situacao?: SituacaoContato | ''
  busca?: string
  grupo_id?: Id | ''
  responsavel_id?: Id | ''
  empresa_id?: Id | ''
  proximo_de?: string
  proximo_ate?: string
  ultimo_de?: string
  ultimo_ate?: string
  lembrete?: 'hoje' | 'amanha' | ''
  mostrar_inativos?: boolean
  pagina?: number
  por_pagina?: number
}

export type PedidoDisparo = (
  | { contato_ids: Id[]; toda_fila?: never }
  | { toda_fila: true; contato_ids?: never; filtros?: Omit<FiltrosFila, 'pagina' | 'por_pagina'> }
) & { ignorar_descanso?: boolean }

export interface FiltrosHistorico {
  de?: string
  ate?: string
  tipo?: TipoEnvio | ''
  canal?: CanalEnvio | ''
  situacao?: SituacaoEnvio | ''
  busca?: string
  contato_id?: Id | ''
  pagina?: number
}

export const enviosApi = {
  preCondicoes: () => api.get<PreCondicoes>('/envios/pre-condicoes'),
  configuracao: () => api.get<ConfigEnvios>('/envios/configuracao'),
  salvarConfiguracao: (dados: Partial<ConfigEnvios>) => api.put<ConfigEnvios>('/envios/configuracao', dados),
  enviarTeste: () => api.post<Mensagem>('/envios/configuracao/teste'),
  resumo: () => api.get<ResumoEnvios>('/envios/resumo'),
  contatos: (filtros: FiltrosFila = {}, sinal?: AbortSignal) =>
    api.get<Pagina<ContatoEnvio>>('/envios/contatos', { query: { ...filtros }, sinal }),
  disparar: (pedido: PedidoDisparo) => api.post<ResultadoDisparo>('/envios/disparar', pedido),
  tentarDeNovo: (envioId: Id) => api.post<unknown>(`/envios/${seg(envioId)}/tentar-de-novo`),
  historico: (filtros: FiltrosHistorico = {}, sinal?: AbortSignal) =>
    api.get<Pagina<Envio>>('/envios/historico', { query: { ...filtros }, sinal }),
  previaLembretes: () => api.get<{ hoje: number; amanha: number }>('/envios/lembretes/previa'),
  executarLembretes: () => api.post<ResultadoTarefa>('/envios/lembretes/executar'),
  executarRobo: () => api.post<ResultadoTarefa>('/envios/robo/executar'),
  descadastros: (filtros: { busca?: string; pagina?: number } = {}, sinal?: AbortSignal) =>
    api.get<Pagina<Descadastro>>('/envios/descadastros', { query: { ...filtros }, sinal }),
  registrarDescadastro: (dados: { email: string; motivo?: string }) => api.post<unknown>('/envios/descadastros', dados),
}

/** Abre o convite pelo WhatsApp: cria o convite e devolve o endereço wa.me com a mensagem pronta. */
export const whatsappApi = {
  criar: (contatoId: Id, formularioId?: Id) =>
    api.post<WhatsappContato>(`/contatos/${seg(contatoId)}/whatsapp`, formularioId !== undefined ? { formulario_id: formularioId } : {}),
}

export const plataformaContasApi = {
  /** DELETE com corpo: o nome digitado confirma a exclusão. */
  excluir: (id: Id, confirmar_nome: string) =>
    requisitar<void>(`/plataforma/contas/${seg(id)}`, { metodo: 'DELETE', corpo: { confirmar_nome } }),
}
