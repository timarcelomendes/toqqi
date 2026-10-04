// Endpoints da etapa 5g (docs/api-etapa-5g.md): Plataforma › Parâmetros (só superadmin) e o preço que a tela mostrou ao
// assinar e ao trocar de plano (em `assinaturaApi`, etapa5a.ts). Os números públicos (GET /publico/planos) ficam em
// `publicoApi.planos` (publico.ts), que o site da raiz também usa sem carregar o app.
import { api } from './cliente'
import type {
  GrupoParametros,
  GrupoParametrosPlataforma,
  PaginaHistoricoParametros,
  ParametrosPlataforma,
  PreviaParametros,
  ValorParametro,
} from './tipos'

export interface FiltrosHistoricoParametros {
  /** Vazio = todos os grupos (grupo desconhecido → 422 no campo `grupo`). */
  grupo?: GrupoParametros | ''
  pagina?: number
  por_pagina?: number
}

const seg = (v: string) => encodeURIComponent(v)

export const parametrosApi = {
  /** Os quatro grupos, na ordem (planos, ia, whatsapp, teste), com valores, padrões, origens e a `versao`. */
  obter: (sinal?: AbortSignal) => api.get<ParametrosPlataforma>('/plataforma/parametros', { sinal }),
  /**
   * O que mudaria, se precisa de confirmação e as contas atingidas. Mesma validação do PUT (422 `dados_invalidos` com
   * `campos` pela chave); não testa o modelo.
   */
  previa: (grupo: GrupoParametros, valores: Record<string, ValorParametro>) =>
    api.post<PreviaParametros>(`/plataforma/parametros/${seg(grupo)}/previa`, { valores }),
  /**
   * Salva o grupo (todas as chaves dele). 422 nos campos (no grupo `ia`, também a recusa da OpenAI no
   * `ia.modelo.{nivel}`); 409 `confirmacao_necessaria` sem `confirmar` quando a prévia pede; 409 `parametros_alterados`
   * quando a `versao` mudou; 503 `teste_ia_indisponivel` (nada salvo). 200 com o grupo (e `testados` no `ia`).
   */
  salvar: (grupo: GrupoParametros, corpo: { versao: number; valores: Record<string, ValorParametro>; confirmar: boolean }) =>
    api.put<GrupoParametrosPlataforma>(`/plataforma/parametros/${seg(grupo)}`, corpo),
  /** Mais novos primeiro (`por_pagina` padrão 20, até 100). */
  historico: (filtros: FiltrosHistoricoParametros = {}, sinal?: AbortSignal) =>
    api.get<PaginaHistoricoParametros>('/plataforma/parametros/historico', { query: { ...filtros }, sinal }),
}
