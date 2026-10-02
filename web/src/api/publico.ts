// Endpoints das páginas públicas (sem login). Importado pela entrada leve `responder.html`:
// não pode puxar Pinia, router nem o resto do app.
import { api } from './cliente'
import type { CanalPublico } from '@/pesquisa/contexto'
import type { Contexto, DadosIndicacao, FormularioPublico, Respostas, TelaFinal, Variaveis } from '@/pesquisa/tipos'

export interface DescadastroPublico {
  email_mascarado: string
  empresa: string
  descadastrado: boolean
}

export interface PesquisaPublica {
  formulario: FormularioPublico
  variaveis: Partial<Variaveis>
  ja_respondido?: boolean
}

const publico = { autenticar: false, semTratamentoGlobal: true } as const
const seg = (v: string) => encodeURIComponent(v)

export const publicoApi = {
  convite: (token: string) => api.get<PesquisaPublica>(`/publico/convites/${seg(token)}`, publico),
  /** Etapa 5c: a tela final pode trazer `indicacao` (convite para indicar outra empresa). */
  responderConvite: (token: string, respostas: Respostas) =>
    api.post<TelaFinal | undefined>(`/publico/convites/${seg(token)}/responder`, { respostas }, publico),
  /**
   * Etapa 5c: indicação feita no cartão da tela final (201 `{mensagem}`). 409 `limite_indicacoes` na 4ª e 409
   * `indicacao_indisponivel` quando a pesquisa não aceita mais (ex.: as indicações foram desligadas); 422 com
   * campos. A mesma pessoa indicada de novo (indicação ainda aberta) também volta 201, sem dizer que já existe.
   */
  indicar: (token: string, dados: DadosIndicacao) =>
    api.post<{ mensagem?: string } | undefined>(`/publico/convites/${seg(token)}/indicacoes`, dados, publico),
  formulario: (codigo: string) => api.get<PesquisaPublica>(`/publico/formularios/${seg(codigo)}`, publico),
  responderFormulario: (
    codigo: string,
    dados: { respostas: Respostas; canal?: CanalPublico; referencia?: string; contexto?: Contexto },
  ) => api.post<TelaFinal | undefined>(`/publico/formularios/${seg(codigo)}/responder`, dados, publico),
  descadastro: (token: string) => api.get<DescadastroPublico>(`/publico/descadastro/${seg(token)}`, publico),
  /** Sair da lista (com motivo opcional) ou, com `voltar`, voltar a receber. */
  alterarDescadastro: (token: string, corpo: { motivo?: string } | { voltar: true }) =>
    api.post<{ descadastrado: boolean }>(`/publico/descadastro/${seg(token)}`, corpo, publico),
}
