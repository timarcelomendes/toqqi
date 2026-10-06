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
  DocumentoFormulario,
  Empresa,
  Formulario,
  FormularioResumo,
  Id,
  ImagemConteudo,
  MarcoEmpresa,
  ItemCadastro,
  LinkPesquisa,
  Mensagem,
  ModeloFormulario,
  MotivoPerda,
  Pagina,
  Pergunta,
  Responsavel,
  Resposta,
  RespostaRascunho,
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
  /** Etapa 5i: filtra pela faixa da saúde (só ativas) e ordena. */
  saude?: 'saudavel' | 'atencao' | 'risco' | 'sem_dados' | ''
  ordem?: 'nome' | 'saude' | 'renovacao'
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
  /** Etapa 5i: "Marcar como perdida" (desativa os contatos ativos da empresa). */
  perder: (id: Id, dados: { perdida_em?: string; motivo_perda: MotivoPerda; motivo_detalhe?: string | null }) =>
    api.post<Empresa & { contatos_desativados: number }>(`/empresas/${seg(id)}/perda`, dados),
  /** Corrige a data, o motivo ou o detalhe da perda (os contatos não mudam). */
  corrigirPerda: (id: Id, dados: { perdida_em?: string; motivo_perda?: MotivoPerda; motivo_detalhe?: string | null }) =>
    api.patch<Empresa>(`/empresas/${seg(id)}/perda`, dados),
  /** Etapa 5i: "Voltou a ser cliente" (reativa os contatos que a perda desativou). */
  voltar: (id: Id, dados: { valor_mensal?: number | null; renovacao_em?: string | null; reativar_contatos?: boolean }) =>
    api.post<Empresa & { contatos_reativados: number }>(`/empresas/${seg(id)}/retorno`, dados),
  /** Etapa 5i: linha do tempo (entrada, valor mensal, perda e retorno). */
  historico: (id: Id) => api.get<{ itens: MarcoEmpresa[] }>(`/empresas/${seg(id)}/historico`),
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
  criar: (dados: { nome: string; modelo?: string; perguntas?: Pergunta[]; tema?: Tema; finais?: DocumentoFormulario['finais'] }) =>
    api.post<Formulario>('/formularios', dados),
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
  /**
   * Etapa 5l: grava o rascunho (o que está no ar só muda ao publicar). `rev` diferente do servidor → 409
   * `rascunho_desatualizado` (com `rev`, `salvo_em` e `salvo_por_nome` no `erro`); 422 só para o estrutural.
   */
  salvarRascunho: (id: Id, dados: DocumentoFormulario & { rev: number }) =>
    api.put<RespostaRascunho>(`/formularios/${seg(id)}/rascunho`, dados),
  /** Etapa 5l: publica o rascunho (422 com `campos`; 409 `sem_rascunho` ou `rascunho_desatualizado`). Devolve o formulário. */
  publicar: (id: Id, rev: number) => api.post<Formulario>(`/formularios/${seg(id)}/publicar`, { rev }),
  /** Etapa 5l: descarta o rascunho (204); o editor volta ao publicado. */
  descartarRascunho: (id: Id) => api.delete(`/formularios/${seg(id)}/rascunho`),
  /** Etapa 5l: imagem de um bloco de conteúdo ou final (multipart `arquivo`, PNG/JPEG até 1 MB) → {url, largura, altura}. */
  enviarImagem: (id: Id, arquivo: File) => {
    const corpo = new FormData()
    corpo.append('arquivo', arquivo)
    return api.post<ImagemConteudo>(`/formularios/${seg(id)}/imagens`, corpo)
  },
}
