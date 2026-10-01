import { api } from './cliente'
import type {
  ContaPlataforma,
  DadosSessao,
  Gravidade,
  Mensagem,
  PaginaAuditoria,
  Perfil,
  Permissao,
  PermissoesEquipe,
  RegrasSenha,
  Seguranca,
  Sessao,
  SessaoAparelho,
  SituacaoUsuario,
  Usuario,
} from './tipos'

export * from './tipos'
export { ApiError, mensagemDoErro } from './erros'
export { API_URL, baixarArquivo, configurarCliente, salvarBlob } from './cliente'
export * from './etapa2'
export * from './etapa3'
export * from './etapa3b'
export * from './etapa4a'
export * from './empresa'

const publico = { autenticar: false } as const

export const authApi = {
  cadastrar: (dados: {
    empresa: string
    nome: string
    email: string
    senha: string
    telefone?: string
    aceite_termos: true
  }) => api.post<Mensagem>('/auth/cadastro', dados, publico),
  entrar: (dados: { email: string; senha: string; lembrar: boolean }) =>
    api.post<Sessao>('/auth/entrar', dados, publico),
  confirmarEmail: (token: string) => api.post<Mensagem>('/auth/confirmar-email', { token }, publico),
  reenviarConfirmacao: (email: string) => api.post<Mensagem>('/auth/reenviar-confirmacao', { email }, publico),
  esqueciSenha: (email: string) => api.post<Mensagem>('/auth/esqueci-senha', { email }, publico),
  redefinirSenha: (token: string, senha: string) =>
    api.post<Mensagem>('/auth/redefinir-senha', { token, senha }, publico),
  pedirAcesso: (dados: { nome: string; email: string; senha: string }) =>
    api.post<Mensagem>('/auth/pedir-acesso', dados, publico),
  regrasSenha: () => api.get<RegrasSenha>('/auth/regras-senha', publico),
  /** Não aciona o tratamento global: se a sessão já caiu, sair continua valendo. */
  sair: () => api.post<void>('/auth/sair', undefined, { semTratamentoGlobal: true }),
}

export const euApi = {
  obter: () => api.get<DadosSessao>('/eu'),
  atualizar: (dados: { nome?: string; cargo?: string | null }) => api.patch<Usuario>('/eu', dados),
  trocarSenha: (senha_atual: string, senha_nova: string) =>
    api.post<Mensagem | undefined>('/eu/senha', { senha_atual, senha_nova }),
  sessoes: () => api.get<SessaoAparelho[]>('/eu/sessoes'),
  encerrarSessao: (id: SessaoAparelho['id']) => api.delete(`/eu/sessoes/${encodeURIComponent(String(id))}`),
  encerrarOutras: () => api.post<void>('/eu/sessoes/encerrar-outras'),
}

export const equipeApi = {
  listar: () => api.get<Usuario[]>('/equipe'),
  criar: (dados: { nome: string; email: string; cargo?: string; perfil: Perfil; senha: string }) =>
    api.post<Usuario>('/equipe', dados),
  atualizar: (
    id: Usuario['id'],
    dados: { nome?: string; cargo?: string | null; perfil?: Perfil; situacao?: SituacaoUsuario },
  ) => api.patch<Usuario>(`/equipe/${encodeURIComponent(String(id))}`, dados),
  excluir: (id: Usuario['id']) => api.delete(`/equipe/${encodeURIComponent(String(id))}`),
  reenviarConfirmacao: (id: Usuario['id']) =>
    api.post<Mensagem | undefined>(`/equipe/${encodeURIComponent(String(id))}/reenviar-confirmacao`),
  permissoes: () => api.get<PermissoesEquipe>('/equipe/permissoes'),
  salvarPermissoes: (dados: { gestor: Permissao[]; consulta: Permissao[] }) =>
    api.put<PermissoesEquipe>('/equipe/permissoes', dados),
}

export const contaApi = {
  seguranca: () => api.get<Seguranca>('/conta/seguranca'),
  salvarSeguranca: (dados: Seguranca) => api.put<Seguranca>('/conta/seguranca', dados),
}

export interface FiltrosAuditoria {
  de?: string
  ate?: string
  gravidade?: Gravidade | ''
  busca?: string
  pagina?: number
}

export const auditoriaApi = {
  listar: (filtros: FiltrosAuditoria, sinal?: AbortSignal) =>
    api.get<PaginaAuditoria>('/auditoria', { query: { ...filtros }, sinal }),
}

export const plataformaApi = {
  contas: () => api.get<ContaPlataforma[]>('/plataforma/contas'),
  criarConta: (dados: {
    empresa: string
    admin_nome: string
    admin_email: string
    admin_senha: string
    situacao: 'teste' | 'cortesia'
  }) => api.post<unknown>('/plataforma/contas', dados),
  estenderTeste: (id: ContaPlataforma['id'], dias = 14) =>
    api.post<ContaPlataforma>(`/plataforma/contas/${encodeURIComponent(String(id))}/estender-teste`, { dias }),
  cortesia: (id: ContaPlataforma['id']) =>
    api.post<ContaPlataforma>(`/plataforma/contas/${encodeURIComponent(String(id))}/cortesia`),
}
