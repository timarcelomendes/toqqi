import type { Gravidade, Perfil, SituacaoUsuario } from '@/api/tipos'

export type Tom = 'neutro' | 'marca' | 'sucesso' | 'atencao' | 'erro' | 'info'

export const PERFIS: Record<Perfil, { rotulo: string; descricao: string; tom: Tom }> = {
  admin: { rotulo: 'Administrador', descricao: 'Pode tudo, inclusive equipe e configurações.', tom: 'marca' },
  gestor: { rotulo: 'Gestor', descricao: 'Trabalha no dia a dia com o que você liberar.', tom: 'info' },
  consulta: { rotulo: 'Consulta', descricao: 'Só olha: ideal para quem acompanha resultados.', tom: 'neutro' },
}

export const SITUACOES_USUARIO: Record<SituacaoUsuario, { rotulo: string; tom: Tom }> = {
  ativo: { rotulo: 'Ativo', tom: 'sucesso' },
  pendente: { rotulo: 'Pendente de aprovação', tom: 'atencao' },
  bloqueado: { rotulo: 'Bloqueado', tom: 'erro' },
}

export const GRAVIDADES: Record<Gravidade, { rotulo: string; tom: Tom }> = {
  info: { rotulo: 'Informação', tom: 'info' },
  sucesso: { rotulo: 'Sucesso', tom: 'sucesso' },
  atencao: { rotulo: 'Atenção', tom: 'atencao' },
  erro: { rotulo: 'Erro', tom: 'erro' },
}

/** Situação da conta: o contrato não lista os valores; conhecidos aqui, o resto aparece como veio. */
const SITUACOES_CONTA: Record<string, { rotulo: string; tom: Tom }> = {
  teste: { rotulo: 'Em teste', tom: 'info' },
  cortesia: { rotulo: 'Cortesia', tom: 'marca' },
  ativa: { rotulo: 'Ativa', tom: 'sucesso' },
  ativo: { rotulo: 'Ativa', tom: 'sucesso' },
  expirada: { rotulo: 'Teste encerrado', tom: 'atencao' },
  vencida: { rotulo: 'Vencida', tom: 'atencao' },
  suspensa: { rotulo: 'Suspensa', tom: 'erro' },
  bloqueada: { rotulo: 'Bloqueada', tom: 'erro' },
  cancelada: { rotulo: 'Cancelada', tom: 'neutro' },
}

export function situacaoConta(valor: string | null | undefined): { rotulo: string; tom: Tom } {
  if (!valor) return { rotulo: '—', tom: 'neutro' }
  return SITUACOES_CONTA[valor] ?? { rotulo: valor.charAt(0).toUpperCase() + valor.slice(1), tom: 'neutro' }
}

export function iniciais(nome: string | null | undefined): string {
  const partes = (nome ?? '').trim().split(/\s+/).filter(Boolean)
  if (!partes.length) return '?'
  const primeira = partes[0]!.charAt(0)
  const ultima = partes.length > 1 ? partes[partes.length - 1]!.charAt(0) : ''
  return (primeira + ultima).toUpperCase()
}
