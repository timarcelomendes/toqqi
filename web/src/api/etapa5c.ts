// Endpoints da etapa 5c (docs/api-etapa-5c.md): Crescimento (indicações, oportunidades, ofertas e o resumo) e
// Configurações › Crescimento. A indicação pública, feita na tela final da pesquisa, fica em `publicoApi` (página leve).
import { api, baixarArquivo } from './cliente'
import type {
  ConfigCrescimento,
  DadosEdicaoIndicacao,
  DadosNovaIndicacao,
  DadosNovaOferta,
  DadosResultadoOferta,
  FiltrosIndicacoes,
  FiltrosOportunidades,
  Id,
  Indicacao,
  Oferta,
  Oportunidade,
  Pagina,
  PaginaIndicacoes,
  ResumoCrescimento,
} from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

/** Os mesmos filtros da lista, sem a página (o CSV leva todas as linhas). */
function semPagina<T extends { pagina?: number; por_pagina?: number }>(f: T): Omit<T, 'pagina' | 'por_pagina'> {
  const { pagina: _p, por_pagina: _pp, ...resto } = f
  return resto
}

export const crescimentoApi = {
  /** Mais novas primeiro, com o `resumo` por situação (mesmo período e responsável). */
  indicacoes: (f: FiltrosIndicacoes = {}, sinal?: AbortSignal) => api.get<PaginaIndicacoes>('/crescimento/indicacoes', { query: { ...f }, sinal }),
  /** Registro à mão ("veio por telefone"): 201 com a indicação. */
  registrarIndicacao: (dados: DadosNovaIndicacao) => api.post<Indicacao>('/crescimento/indicacoes', dados),
  /** 'cliente' pede `valor_mensal` (422 sem ele); outras situações limpam o valor. */
  atualizarIndicacao: (id: Id, dados: DadosEdicaoIndicacao) => api.patch<Indicacao | undefined>(`/crescimento/indicacoes/${seg(id)}`, dados),
  /** Pedido da pessoa indicada (LGPD): 204. */
  excluirIndicacao: (id: Id) => api.delete(`/crescimento/indicacoes/${seg(id)}`),
  /** Pede painel.exportar. */
  baixarIndicacoes: (f: FiltrosIndicacoes = {}) => baixarArquivo('/crescimento/indicacoes.csv', 'indicacoes.csv', { ...semPagina(f) }),

  oportunidades: (f: FiltrosOportunidades = {}, sinal?: AbortSignal) =>
    api.get<Pagina<Oportunidade>>('/crescimento/oportunidades', { query: { ...f }, sinal }),
  /** Pede painel.exportar. O contrato pede só a lista; grupo e responsável vão junto (a API ignora o que não usa). */
  baixarOportunidades: (f: FiltrosOportunidades = {}) =>
    baixarArquivo('/crescimento/oportunidades.csv', `oportunidades-${f.lista ?? 'pode_crescer'}.csv`, { ...semPagina(f) }),

  /** Registrada quando a oferta abre no WhatsApp (ou no e-mail). 201 com a oferta. */
  registrarOferta: (dados: DadosNovaOferta) => api.post<Oferta>('/crescimento/ofertas', dados),
  registrarResultado: (id: Id, dados: DadosResultadoOferta) => api.patch<Oferta | undefined>(`/crescimento/ofertas/${seg(id)}`, dados),

  /** Padrão: últimos 90 dias. */
  resumo: (f: { de?: string; ate?: string } = {}, sinal?: AbortSignal) =>
    api.get<ResumoCrescimento>('/crescimento/resumo', { query: { ...f }, sinal }),

  /** Também com crescimento.ver (a tela usa o texto da oferta e sabe se o convite está ligado). */
  configuracao: (sinal?: AbortSignal) => api.get<ConfigCrescimento>('/crescimento/configuracao', { sinal }),
  /** Só configuracoes.gerenciar. */
  salvarConfiguracao: (dados: ConfigCrescimento) => api.put<ConfigCrescimento>('/crescimento/configuracao', dados),
}
