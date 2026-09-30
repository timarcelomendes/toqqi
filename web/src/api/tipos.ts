// Tipos do contrato da API da etapa 1 (docs/api-etapa-1.md).

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
