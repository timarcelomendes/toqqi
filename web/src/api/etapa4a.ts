// Endpoints da etapa 4a: respostas (lista, análise, registro à mão), planos de ação e painel.
import { api, baixarArquivo } from './cliente'
import type {
  Acao,
  ConfigAcoes,
  DadosAnaliseResposta,
  DadosEdicaoAcao,
  DadosNovaAcao,
  DadosRegistroResposta,
  FiltrosAcoes,
  FiltrosPainel,
  FiltrosRespostas,
  Id,
  Pagina,
  PaginaRespostas,
  Painel,
  QuadroAcoes,
  RespostaDetalhe,
  RespostaItem,
  SituacaoAcao,
  TemaResposta,
} from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

/** Os mesmos filtros da lista, sem a página (para o CSV). */
function semPagina<T extends { pagina?: number; por_pagina?: number }>(f: T): Omit<T, 'pagina' | 'por_pagina'> {
  const { pagina: _p, por_pagina: _pp, ...resto } = f
  return resto
}

export const respostasApi = {
  /** Lista paginada + métricas calculadas sobre o mesmo filtro (todas as páginas). */
  listar: (filtros: FiltrosRespostas = {}, sinal?: AbortSignal) =>
    api.get<PaginaRespostas>('/respostas', { query: { ...filtros }, sinal }),
  obter: (id: Id, sinal?: AbortSignal) => api.get<RespostaDetalhe>(`/respostas/${seg(id)}`, { sinal }),
  temas: () => api.get<TemaResposta[]>('/respostas/temas'),
  /** Registrar à mão (contato, nota 0–10, canal, data, comentário). */
  registrar: (dados: DadosRegistroResposta) => api.post<RespostaItem>('/respostas', dados),
  /** Analisar: só os campos que mudaram. */
  analisar: (id: Id, dados: DadosAnaliseResposta) => api.patch<RespostaItem>(`/respostas/${seg(id)}`, dados),
  arquivar: (id: Id) => api.post<RespostaItem>(`/respostas/${seg(id)}/arquivar`),
  restaurar: (id: Id) => api.post<RespostaItem>(`/respostas/${seg(id)}/restaurar`),
  /** Só perfil admin. Apaga também as ações ligadas à resposta. */
  excluir: (id: Id) => api.delete(`/respostas/${seg(id)}`),
  baixarCsv: (filtros: FiltrosRespostas = {}) => baixarArquivo('/respostas.csv', 'respostas.csv', { ...semPagina(filtros) }),
}

export type FiltrosListaAcoes = FiltrosAcoes & { situacao?: SituacaoAcao | ''; pagina?: number; por_pagina?: number }

export const acoesApi = {
  /** As três colunas (até 300 abertas por coluna; as 15 concluídas mais recentes) e os totais. */
  quadro: (filtros: FiltrosAcoes = {}, sinal?: AbortSignal) => api.get<QuadroAcoes>('/acoes/quadro', { query: { ...filtros }, sinal }),
  /** Lista paginada (ex.: "ver todas as concluídas"). */
  listar: (filtros: FiltrosListaAcoes = {}, sinal?: AbortSignal) => api.get<Pagina<Acao>>('/acoes', { query: { ...filtros }, sinal }),
  obter: (id: Id) => api.get<Acao>(`/acoes/${seg(id)}`),
  criar: (dados: DadosNovaAcao) => api.post<Acao>('/acoes', dados),
  /** Mover de coluna = mudar a situação. Concluir exige responsável e o que foi feito (422 com campos). */
  atualizar: (id: Id, dados: DadosEdicaoAcao) => api.patch<Acao>(`/acoes/${seg(id)}`, dados),
  excluir: (id: Id) => api.delete(`/acoes/${seg(id)}`),
  configuracao: () => api.get<ConfigAcoes>('/acoes/configuracao'),
  salvarConfiguracao: (dados: Partial<ConfigAcoes>) => api.put<ConfigAcoes>('/acoes/configuracao', dados),
}

export const painelApi = {
  obter: (filtros: FiltrosPainel = {}, sinal?: AbortSignal) => api.get<Painel>('/painel', { query: { ...filtros }, sinal }),
  /** Mesmo CSV de /respostas.csv, com os filtros do painel. */
  baixarCsv: (filtros: FiltrosPainel = {}) => baixarArquivo('/painel/exportar.csv', 'respostas-do-painel.csv', { ...filtros }),
}
