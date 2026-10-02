// Endpoints da etapa 5d (docs/api-etapa-5d.md): resumo do painel e parecer dos relatórios, sob demanda (cada geração
// gasta 1 análise da cota do plano; se falhar, a API devolve). Os passos das ações vêm na própria ação (`acoesApi`);
// modelo, estilo e "Sugerir passos nas ações" ficam em `iaApi.atualizar` (Configurações › IA).
import { api } from './cliente'
import type {
  ConteudoParecerIa,
  ConteudoResumoIa,
  CorpoGeracaoIa,
  EstadoGeracaoIa,
  FiltrosGeracaoIa,
  ResultadoGeracaoIa,
} from './tipos'

/** Os filtros na query do GET (o cliente tira os vazios). */
function query(f: FiltrosGeracaoIa): Record<string, string | number | boolean | undefined> {
  return { de: f.de, ate: f.ate, grupo_id: f.grupo_id === '' ? undefined : f.grupo_id, so_ativos: f.so_ativos }
}

/** Corpo do POST: os quatro filtros, null no que não foi escolhido; o grupo vai como número quando é um número. */
export function corpoGeracaoIa(f: FiltrosGeracaoIa): CorpoGeracaoIa {
  const g = f.grupo_id
  const grupo = g === undefined || g === null || g === '' ? null : typeof g === 'string' && /^\d{1,15}$/.test(g) ? Number(g) : g
  return { de: f.de || null, ate: f.ate || null, grupo_id: grupo, so_ativos: f.so_ativos !== false }
}

export const resumoIaApi = {
  /** `painel.ver`. O salvo para os mesmos filtros do painel, a disponibilidade, a cota e a espera de 30 s. */
  obter: (f: FiltrosGeracaoIa = {}, sinal?: AbortSignal) =>
    api.get<EstadoGeracaoIa<ConteudoResumoIa>>('/painel/resumo-ia', { query: query(f), sinal }),
  /**
   * 409 `ia_indisponivel`, `conta_pausada`, `sem_dados` e `cota_esgotada`; 429 `aguarde` (30 s desde a última geração na
   * conta, ou outra em andamento); 503 `ia_indisponivel` (a análise volta para a cota).
   */
  gerar: (f: FiltrosGeracaoIa) => api.post<ResultadoGeracaoIa<ConteudoResumoIa>>('/painel/resumo-ia', corpoGeracaoIa(f)),
}

export const parecerIaApi = {
  /** `relatorios.ver`. Os filtros comuns dos relatórios (período, grupo, só ativas). */
  obter: (f: FiltrosGeracaoIa = {}, sinal?: AbortSignal) =>
    api.get<EstadoGeracaoIa<ConteudoParecerIa>>('/relatorios/parecer-ia', { query: query(f), sinal }),
  /** Mesmos erros do resumo do painel. */
  gerar: (f: FiltrosGeracaoIa) => api.post<ResultadoGeracaoIa<ConteudoParecerIa>>('/relatorios/parecer-ia', corpoGeracaoIa(f)),
}
