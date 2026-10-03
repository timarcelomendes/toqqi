// Endpoints da etapa 5f (docs/api-etapa-5f.md): Configurações › Dados da conta (exportar todos os dados e a Zona de
// risco), "Exportar CSV" em Contatos e Empresas e os grupos da Auditoria (o filtro `grupo` vai em `auditoriaApi.listar`).
// O dia da exclusão automática de uma conta encerrada vem na sessão (`conta.cobranca.exclusao_em`) e na Plataforma.
import { api, baixarArquivo } from './cliente'
import type { FiltrosContatos, FiltrosEmpresas } from './etapa2'
import type { GrupoAuditoria, OpcaoZonaRisco, ResultadoZonaRisco, ZonaRisco } from './tipos'

/** Os filtros da lista sem a paginação (o CSV leva todas as linhas). */
function semPagina<T extends { pagina?: number; por_pagina?: number }>(f: T): Omit<T, 'pagina' | 'por_pagina'> {
  const { pagina: _p, por_pagina: _pp, ...resto } = f
  return resto
}

export const dadosContaApi = {
  /**
   * `GET /conta/exportacao.zip` (só administrador; vale também com a conta encerrada): um .zip com um CSV por assunto,
   * baixado como os outros arquivos. 409 `exportacao_em_andamento`; 429 (5 por hora por usuário). O nome vem da API
   * (`toqqi-{conta}-{AAAA-MM-DD}.zip`).
   */
  baixarTudo: () => baixarArquivo('/conta/exportacao.zip', 'toqqi-dados.zip'),
  /** Contagens do que cada opção apaga e do que sempre fica. */
  zonaDeRisco: (sinal?: AbortSignal) => api.get<ZonaRisco>('/conta/zona-de-risco', { sinal }),
  /**
   * Apaga de vez (uma transação: tudo ou nada). Confirmação diferente de APAGAR → 422 no campo `confirmacao`; outra em
   * andamento → 409 `zona_em_andamento`; tempo esgotado → 503 `zona_indisponivel` (nada apagado); 429 (5 por hora).
   */
  apagar: (opcao: OpcaoZonaRisco, confirmacao: string) =>
    api.post<ResultadoZonaRisco>('/conta/zona-de-risco', { opcao, confirmacao }),
}

export const exportacaoListasApi = {
  /** `contatos.ver` e `painel.exportar`: os filtros e a ordem de GET /contatos, sem paginação (`contatos-{data}.csv`). */
  baixarContatos: (f: FiltrosContatos = {}) => baixarArquivo('/contatos.csv', 'contatos.csv', { ...semPagina(f) }),
  /** `contatos.ver` e `painel.exportar`: os filtros e a ordem de GET /empresas, sem paginação (`empresas-{data}.csv`). */
  baixarEmpresas: (f: FiltrosEmpresas = {}) => baixarArquivo('/empresas.csv', 'empresas.csv', { ...semPagina(f) }),
}

export const gruposAuditoriaApi = {
  /** `auditoria.ver`. Os grupos de eventos, na ordem da API (`[{chave, rotulo}]`). */
  listar: (sinal?: AbortSignal) => api.get<GrupoAuditoria[]>('/auditoria/grupos', { sinal }),
}
