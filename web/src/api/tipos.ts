// Tipos do contrato da API (docs/api-etapa-1.md e docs/api-etapa-2.md).
import type { Contexto, Pergunta, Tema } from '@/pesquisa/tipos'

export type Perfil = 'admin' | 'gestor' | 'consulta'
export type SituacaoUsuario = 'ativo' | 'pendente' | 'bloqueado'

/** Permissões conhecidas. O tipo aceita outras strings para não quebrar se a API crescer. */
export type Permissao =
  | 'painel.ver'
  | 'painel.exportar'
  | 'contatos.ver'
  | 'contatos.editar'
  | 'contatos.excluir'
  | 'importacao.usar'
  | 'envios.ver'
  | 'envios.disparar'
  | 'formularios.ver'
  | 'formularios.editar'
  | 'respostas.ver'
  | 'respostas.editar'
  | 'acoes.ver'
  | 'acoes.tratar'
  | 'acoes.excluir'
  | 'relatorios.ver'
  | 'equipe.gerenciar'
  | 'configuracoes.gerenciar'
  | 'assinatura.gerenciar'
  | 'auditoria.ver'
  | 'zona_risco.usar'
  | (string & {})

export interface Usuario {
  id: number | string
  nome: string
  email: string
  cargo: string | null
  perfil: Perfil
  situacao: SituacaoUsuario
  email_confirmado: boolean
  ultimo_acesso: string | null
  superadmin: boolean
}

export interface Conta {
  id: number | string
  nome: string
  plano: string | null
  situacao: string
  teste_ate: string | null
}

export interface DadosSessao {
  usuario: Usuario
  conta: Conta
  permissoes: Permissao[]
}

export interface Sessao extends DadosSessao {
  token: string
  expira_em: string
}

export interface Mensagem {
  mensagem: string
}

export interface RegrasSenha {
  minimo: number
  maximo: number
  exige: string[]
}

export interface SessaoAparelho {
  id: number | string
  aparelho: string
  ip: string | null
  criada_em: string
  ultimo_uso: string | null
  atual: boolean
}

export interface ItemCatalogoPermissao {
  chave: Permissao
  rotulo: string
  grupo: string
  somente_admin: boolean
}

export interface PermissoesEquipe {
  catalogo: ItemCatalogoPermissao[]
  gestor: Permissao[]
  consulta: Permissao[]
}

export interface Seguranca {
  sessao_minutos: number
  dominios: string[]
}

export type Gravidade = 'info' | 'sucesso' | 'atencao' | 'erro'

export interface ItemAuditoria {
  id: number | string
  criado_em: string
  evento: string
  rotulo: string
  gravidade: Gravidade
  usuario: { id: number | string; nome: string } | null
  /** O contrato não fixa o formato: pode vir texto ou objeto. */
  detalhe: string | Record<string, unknown> | null
  ip: string | null
}

export interface PaginaAuditoria {
  itens: ItemAuditoria[]
  total: number
  pagina: number
  por_pagina: number
}

export interface ContaPlataforma {
  id: number | string
  nome: string
  plano: string | null
  situacao: string
  teste_ate: string | null
  usuarios: number
  criada_em: string
}

// ───────────────────────── Etapa 2 (docs/api-etapa-2.md) ─────────────────────────

export type {
  CondicaoPergunta,
  Contexto,
  FormatoTexto,
  GrupoNota,
  ModoTema,
  Pergunta,
  Tema,
  TipoPergunta,
} from '@/pesquisa/tipos'

export type Id = number | string

export interface Pagina<T> {
  itens: T[]
  total: number
  pagina: number
  por_pagina: number
}

export interface Referencia {
  id: Id
  nome: string
}

export type TipoCadastro = 'grupos' | 'segmentos' | 'perfis' | 'cargos'

export interface ItemCadastro {
  id: Id
  nome: string
  em_uso: number
}

export interface Responsavel {
  id: Id
  nome: string
  funcao: string | null
  email: string | null
  foto_url: string | null
  teams_webhook: string | null
  empresas: number
}

export interface DadosResponsavel {
  nome: string
  funcao?: string | null
  email?: string | null
  foto_url?: string | null
  teams_webhook?: string | null
}

export interface Empresa {
  id: Id
  nome: string
  documento: string | null
  grupo: Referencia | null
  segmento: Referencia | null
  responsavel: Referencia | null
  valor_mensal: number | string | null
  cliente_desde: string | null
  codigo_externo: string | null
  ativa: boolean
  contatos: number
  criada_em: string
}

export interface DadosEmpresa {
  nome: string
  documento?: string | null
  grupo_id?: Id | null
  segmento_id?: Id | null
  responsavel_id?: Id | null
  valor_mensal?: number | null
  cliente_desde?: string | null
  codigo_externo?: string | null
  ativa?: boolean
}

export type SituacaoContato =
  | 'na_fila'
  | 'aguardando'
  | 'respondeu'
  | 'nao_saiu'
  | 'saiu_da_lista'
  | 'inativo'
  | 'nunca_enviado'

export interface Contato {
  id: Id
  codigo: string
  nome: string
  email: string | null
  telefone: string | null
  empresa: Referencia | null
  cargo: Referencia | null
  perfil: Referencia | null
  codigo_externo: string | null
  recebe_pesquisas: boolean
  ativo: boolean
  situacao: SituacaoContato
  ultimo_envio: string | null
  proximo_envio: string | null
  ultima_nota: number | null
  criado_em: string
}

export interface ItemHistorico {
  tipo: 'resposta' | (string & {})
  data: string
  nota: number | null
  grupo: string | null
  comentario: string | null
  /** O contrato não fixa: pode vir o nome ou {id, nome}. */
  formulario: string | Referencia | null
}

export interface ContatoDetalhe extends Contato {
  historico: ItemHistorico[]
}

export interface DadosContato {
  nome: string
  email?: string | null
  telefone?: string | null
  empresa_id?: Id | null
  cargo_id?: Id | null
  perfil_id?: Id | null
  codigo_externo?: string | null
  recebe_pesquisas?: boolean
  ativo?: boolean
}

export interface LinkPesquisa {
  link: string
  token: string
  expira_em: string | null
}

// Importação
export type ChaveImportacao = 'email' | 'codigo_externo' | 'telefone'

export interface CampoImportacao {
  chave: string
  rotulo: string
  obrigatorio: boolean
}

export interface AnaliseImportacao {
  id: Id
  colunas: string[]
  mapeamento_sugerido: Record<string, string | null>
  total_linhas: number
  amostra: { linha: number; valores: Record<string, unknown> | unknown[] }[]
  campos: CampoImportacao[]
}

export interface CorpoImportacao {
  mapeamento: Record<string, string>
  chave: ChaveImportacao
  atualizar_existentes: boolean
  grupo_id?: Id
}

export interface ProblemaImportacao {
  linha: number
  motivo: string
}

export interface ConferenciaImportacao {
  prontas: number
  com_problema: number
  novos: number
  atualizados: number
  problemas: ProblemaImportacao[]
  avisos: string[]
}

export interface ResultadoImportacao {
  novos: number
  atualizados: number
  ignorados: number
  /** O contrato não fixa: pode vir a lista ou só a quantidade. */
  problemas: ProblemaImportacao[] | number
}

// Formulários
export type TipoFormulario = 'nps' | 'csat' | 'personalizado'

export interface FormularioResumo {
  id: Id
  nome: string
  descricao: string | null
  tipo_principal: TipoFormulario
  tema?: Tema
  ativo: boolean
  publico: boolean
  codigo_publico: string
  padrao_nps: boolean
  padrao_csat: boolean
  respostas: number
  atualizado_em: string
}

export interface Formulario extends FormularioResumo {
  perguntas: Pergunta[]
  tema: Tema
}

export interface DadosFormulario {
  nome?: string
  descricao?: string | null
  perguntas?: Pergunta[]
  tema?: Tema
  ativo?: boolean
  publico?: boolean
}

export interface ModeloFormulario {
  chave: string
  nome: string
  descricao: string
  perguntas: Pergunta[]
  tema: Tema
}

export interface ResultadoPergunta {
  id: string
  tipo: string
  titulo: string
  respostas: number
  distribuicao?: Record<string, number>
  media?: number | null
  opcoes?: Record<string, number>
  textos?: { texto: string; data: string }[]
}

export interface Resultados {
  total: number
  nps?: { valor: number; promotores: number; neutros: number; detratores: number } | null
  csat?: { percentual: number; media: number } | null
  perguntas: ResultadoPergunta[]
}

export type CanalResposta = 'email' | 'whatsapp' | 'link' | 'qr' | 'widget' | 'api' | 'importacao' | 'manual'

export interface Resposta {
  id: Id
  formulario: Referencia
  contato: { id: Id; nome: string; email: string | null } | null
  empresa: Referencia | null
  canal: CanalResposta
  nota: number | null
  tipo_nota: 'nps' | 'csat' | null
  grupo: string | null
  comentario: string | null
  respostas: Record<string, unknown>
  contexto: Contexto
  referencia: string | null
  criada_em: string
}
