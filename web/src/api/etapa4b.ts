// Endpoints da etapa 4b (docs/api-etapa-4b.md): relatórios (7 abas e os CSV) e Configurações › IA.
// Os filtros das respostas (sentimento, reclamação, contexto) e os picos do painel usam os módulos da 4a.
import { api, baixarArquivo } from './cliente'
import type {
  ConfigIa,
  DadosConfigIa,
  EmpresaDaCarteira,
  FiltrosRelatorio,
  FiltrosRelatorioEmpresas,
  FiltrosRelatorioEntregas,
  FiltrosRelatorioGrupos,
  HistoricoEmpresa,
  Id,
  RelatorioDesfecho,
  RelatorioEmpresas,
  RelatorioEntregas,
  RelatorioGrupos,
  RelatorioOperacao,
  RelatorioResponsaveis,
  RelatorioTemas,
  ResultadoAnalisarRecentes,
} from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

/** Os mesmos filtros da lista, sem a página (para o CSV, que leva todas as linhas). */
function semPagina<T extends { pagina?: number; por_pagina?: number }>(f: T): Omit<T, 'pagina' | 'por_pagina'> {
  const { pagina: _p, por_pagina: _pp, ...resto } = f
  return resto
}

/** Só o período (o histórico de uma empresa não usa grupo nem "só ativas"). */
function periodo(f: FiltrosRelatorio): { de?: string; ate?: string } {
  return { ...(f.de ? { de: f.de } : {}), ...(f.ate ? { ate: f.ate } : {}) }
}

export const relatoriosApi = {
  empresas: (f: FiltrosRelatorioEmpresas = {}, sinal?: AbortSignal) =>
    api.get<RelatorioEmpresas>('/relatorios/empresas', { query: { ...f }, sinal }),
  baixarEmpresas: (f: FiltrosRelatorioEmpresas = {}) => baixarArquivo('/relatorios/empresas.csv', 'relatorio-empresas.csv', { ...semPagina(f) }),

  grupos: (f: FiltrosRelatorioGrupos = {}, sinal?: AbortSignal) => api.get<RelatorioGrupos>('/relatorios/grupos', { query: { ...f }, sinal }),

  temas: (f: FiltrosRelatorio = {}, sinal?: AbortSignal) => api.get<RelatorioTemas>('/relatorios/temas', { query: { ...f }, sinal }),

  entregas: (f: FiltrosRelatorioEntregas = {}, sinal?: AbortSignal) =>
    api.get<RelatorioEntregas>('/relatorios/entregas', { query: { ...f }, sinal }),
  baixarEntregas: (f: FiltrosRelatorioEntregas = {}) =>
    baixarArquivo('/relatorios/entregas.csv', `relatorio-${f.dimensao ?? 'motorista'}.csv`, { ...semPagina(f) }),

  responsaveis: (f: FiltrosRelatorio = {}, sinal?: AbortSignal) =>
    api.get<RelatorioResponsaveis>('/relatorios/responsaveis', { query: { ...f }, sinal }),
  /** Empresas de uma carteira (0 = sem responsável). */
  empresasDoResponsavel: (responsavelId: Id, f: FiltrosRelatorio = {}, sinal?: AbortSignal) =>
    api.get<EmpresaDaCarteira[]>(`/relatorios/responsaveis/${seg(responsavelId)}/empresas`, { query: { ...f }, sinal }),
  baixarResponsaveis: (f: FiltrosRelatorio = {}) => baixarArquivo('/relatorios/responsaveis.csv', 'relatorio-responsaveis.csv', { ...f }),

  /** Etapa 5i: perdidas, motivos, o que diziam antes de sair e a retenção da receita. */
  desfecho: (f: FiltrosRelatorio & { segmento_id?: Id; responsavel_id?: Id; faixa_valor?: string; tempo_cliente?: string } = {}, sinal?: AbortSignal) =>
    api.get<RelatorioDesfecho>('/relatorios/desfecho', { query: { ...f }, sinal }),
  operacao: (f: FiltrosRelatorio = {}, sinal?: AbortSignal) => api.get<RelatorioOperacao>('/relatorios/operacao', { query: { ...f }, sinal }),
  baixarSemResposta: (f: FiltrosRelatorio = {}) =>
    baixarArquivo('/relatorios/operacao/sem-resposta.csv', 'contatos-sem-resposta.csv', { ...f }),

  /** 404 se a empresa não é da conta. */
  historico: (empresaId: Id, f: FiltrosRelatorio = {}, sinal?: AbortSignal) =>
    api.get<HistoricoEmpresa>(`/relatorios/historico/${seg(empresaId)}`, { query: periodo(f), sinal }),
  baixarHistorico: (empresaId: Id, f: FiltrosRelatorio = {}) =>
    baixarArquivo(`/relatorios/historico/${seg(empresaId)}.csv`, `historico-empresa-${empresaId}.csv`, periodo(f)),
}

export const iaApi = {
  obter: () => api.get<ConfigIa>('/conta/ia'),
  /** Desligar cancela as análises pendentes da conta. */
  salvar: (analise_respostas: boolean) => api.put<ConfigIa>('/conta/ia', { analise_respostas }),
  /**
   * Etapa 5d: só os campos que mudaram (modelo, estilo, passos_acoes ou analise_respostas). Devolve o estado inteiro;
   * 422 `dados_invalidos` sem nenhum campo ou com valor fora da lista. Desligar os passos cancela os pendentes da conta.
   */
  atualizar: (dados: DadosConfigIa) => api.put<ConfigIa>('/conta/ia', dados),
  /** Põe na fila os comentários dos últimos 90 dias sem análise (409 `ia_indisponivel`). */
  analisarRecentes: () => api.post<ResultadoAnalisarRecentes>('/conta/ia/analisar-recentes'),
}
