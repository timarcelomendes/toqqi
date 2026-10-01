// Endpoints da etapa 2: cadastros, responsáveis, empresas, contatos, importação e formulários.
import { api, baixarArquivo } from './cliente'
import type {
  AnaliseImportacao,
  ConferenciaImportacao,
  Contato,
  ContatoDetalhe,
  Contexto,
  CorpoImportacao,
  CorpoImportacaoRespostas,
  DadosContato,
  DadosEmpresa,
  DadosFormulario,
  DadosResponsavel,
  Empresa,
  Formulario,
  FormularioResumo,
  Id,
  ItemCadastro,
  LinkPesquisa,
  Mensagem,
  ModeloFormulario,
  Pagina,
  Pergunta,
  Responsavel,
  Resposta,
  ResultadoImportacao,
  Resultados,
  Tema,
  TipoCadastro,
  TipoImportacao,
} from './tipos'

const seg = (v: Id) => encodeURIComponent(String(v))

export const cadastrosApi = {
  listar: (tipo: TipoCadastro) => api.get<ItemCadastro[]>(`/cadastros/${tipo}`),
  criar: (tipo: TipoCadastro, nome: string) => api.post<ItemCadastro>(`/cadastros/${tipo}`, { nome }),
  renomear: (tipo: TipoCadastro, id: Id, nome: string) => api.patch<ItemCadastro>(`/cadastros/${tipo}/${seg(id)}`, { nome }),
  excluir: (tipo: TipoCadastro, id: Id) => api.delete(`/cadastros/${tipo}/${seg(id)}`),
}

export const responsaveisApi = {
  listar: () => api.get<Responsavel[]>('/responsaveis'),
  criar: (dados: DadosResponsavel) => api.post<Responsavel>('/responsaveis', dados),
  atualizar: (id: Id, dados: Partial<DadosResponsavel>) => api.patch<Responsavel>(`/responsaveis/${seg(id)}`, dados),
  excluir: (id: Id) => api.delete(`/responsaveis/${seg(id)}`),
  testarTeams: (id: Id) => api.post<Mensagem>(`/responsaveis/${seg(id)}/testar-teams`),
}

export interface FiltrosEmpresas {
  busca?: string
  grupo_id?: Id | ''
  segmento_id?: Id | ''
  responsavel_id?: Id | ''
  ativa?: 'true' | 'false' | 'todas'
  pagina?: number
  por_pagina?: number
}

export const empresasApi = {
  listar: (filtros: FiltrosEmpresas = {}, sinal?: AbortSignal) =>
    api.get<Pagina<Empresa>>('/empresas', { query: { ...filtros }, sinal }),
  obter: (id: Id) => api.get<Empresa>(`/empresas/${seg(id)}`),
  criar: (dados: DadosEmpresa) => api.post<Empresa>('/empresas', dados),
  atualizar: (id: Id, dados: Partial<DadosEmpresa>) => api.patch<Empresa>(`/empresas/${seg(id)}`, dados),
  excluir: (id: Id) => api.delete(`/empresas/${seg(id)}`),
}

export interface FiltrosContatos {
  busca?: string
  empresa_id?: Id | ''
  grupo_id?: Id | ''
  responsavel_id?: Id | ''
  perfil_id?: Id | ''
  ativo?: 'true' | 'false' | 'todos'
  pagina?: number
  por_pagina?: number
}

export interface PedidoLinkPesquisa {
  formulario_id?: Id
  contexto?: Contexto
  assunto?: string
}

export const contatosApi = {
  listar: (filtros: FiltrosContatos = {}, sinal?: AbortSignal) =>
    api.get<Pagina<Contato>>('/contatos', { query: { ...filtros }, sinal }),
  obter: (id: Id) => api.get<ContatoDetalhe>(`/contatos/${seg(id)}`),
  criar: (dados: DadosContato) => api.post<Contato>('/contatos', dados),
  atualizar: (id: Id, dados: Partial<DadosContato>) => api.patch<Contato>(`/contatos/${seg(id)}`, dados),
  excluir: (id: Id) => api.delete(`/contatos/${seg(id)}`),
  linkPesquisa: (id: Id, dados: PedidoLinkPesquisa) => api.post<LinkPesquisa>(`/contatos/${seg(id)}/link-pesquisa`, dados),
}

/** Etapa 4a: o mesmo fluxo importa contatos (padrão) ou respostas antigas, conforme o `tipo`. */
export const importacaoApi = {
  baixarModelo: (tipo: TipoImportacao = 'contatos') =>
    baixarArquivo('/importacao/modelo', tipo === 'respostas' ? 'modelo-respostas.csv' : 'modelo-contatos.csv', { tipo }),
  analisar: (arquivo: File, tipo: TipoImportacao = 'contatos') => {
    const corpo = new FormData()
    corpo.append('arquivo', arquivo)
    corpo.append('tipo', tipo)
    return api.post<AnaliseImportacao>('/importacao/analisar', corpo)
  },
  /** O tipo vem da análise; para respostas o corpo leva só mapeamento e atualizar_existentes. */
  conferir: (id: Id, corpo: CorpoImportacao | CorpoImportacaoRespostas) =>
    api.post<ConferenciaImportacao>(`/importacao/${seg(id)}/conferir`, corpo),
  importar: (id: Id, corpo: (CorpoImportacao | CorpoImportacaoRespostas) & { ignorar_com_problema: boolean }) =>
    api.post<ResultadoImportacao>(`/importacao/${seg(id)}/importar`, corpo),
}

export interface Periodo {
  de?: string
  ate?: string
}

export const formulariosApi = {
  listar: () => api.get<FormularioResumo[]>('/formularios'),
  modelos: () => api.get<ModeloFormulario[]>('/formularios/modelos'),
  criar: (dados: { nome: string; modelo?: string; perguntas?: Pergunta[]; tema?: Tema }) => api.post<Formulario>('/formularios', dados),
  obter: (id: Id) => api.get<Formulario>(`/formularios/${seg(id)}`),
  atualizar: (id: Id, dados: DadosFormulario) => api.patch<Formulario>(`/formularios/${seg(id)}`, dados),
  duplicar: (id: Id) => api.post<Formulario>(`/formularios/${seg(id)}/duplicar`),
  /** Com respostas, a API arquiva em vez de apagar. */
  excluir: (id: Id) => api.delete<unknown>(`/formularios/${seg(id)}`),
  definirPadrao: (id: Id, uso: 'nps' | 'csat') => api.post<Formulario | undefined>(`/formularios/${seg(id)}/padrao`, { uso }),
  novoCodigo: (id: Id) => api.post<Partial<Formulario> | undefined>(`/formularios/${seg(id)}/novo-codigo`),
  resultados: (id: Id, periodo: Periodo = {}) => api.get<Resultados>(`/formularios/${seg(id)}/resultados`, { query: { ...periodo } }),
  respostas: (id: Id, periodo: Periodo & { pagina?: number } = {}) =>
    api.get<Pagina<Resposta>>(`/formularios/${seg(id)}/respostas`, { query: { ...periodo } }),
  baixarRespostasCsv: (id: Id, periodo: Periodo = {}) =>
    baixarArquivo(`/formularios/${seg(id)}/respostas.csv`, 'respostas.csv', { ...periodo }),
}
