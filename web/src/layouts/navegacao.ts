import type { Component } from 'vue'
import {
  BarChart3,
  CircleQuestionMark,
  ClipboardList,
  CreditCard,
  FileText,
  History,
  Home,
  MessageSquareText,
  Plug,
  Send,
  ShieldCheck,
  Sprout,
  Building2,
  Users,
  UsersRound,
} from 'lucide-vue-next'
import type { Permissao } from '@/api/tipos'

export interface ItemNavegacao {
  rotulo: string
  para: string
  icone: Component
  permissao?: Permissao
  superadmin?: boolean
  /** Só para o perfil administrador da conta. */
  admin?: boolean
  /** Marca o item como ativo em qualquer página que comece com este caminho (padrão: `para`). */
  prefixo?: string
  /** Ainda não existe nesta etapa. */
  emBreve?: boolean
  /** Número ao lado do item (ex.: pedidos de acesso esperando aprovação, em Equipe). */
  contador?: 'pedidosAcesso'
}

export const navegacaoPrincipal: ItemNavegacao[] = [
  { rotulo: 'Início', para: '/inicio', icone: Home },
  { rotulo: 'Contatos', para: '/contatos', icone: UsersRound, permissao: 'contatos.ver' },
  { rotulo: 'Envios', para: '/envios', icone: Send, permissao: 'envios.ver' },
  { rotulo: 'Formulários', para: '/formularios', icone: FileText, permissao: 'formularios.ver' },
  { rotulo: 'Respostas', para: '/respostas', icone: MessageSquareText, permissao: 'respostas.ver' },
  { rotulo: 'Planos de ação', para: '/planos-de-acao', icone: ClipboardList, permissao: 'acoes.ver' },
  // Etapa 5c: indicações dos promotores e oportunidades de oferta.
  { rotulo: 'Crescimento', para: '/crescimento/indicacoes', prefixo: '/crescimento', icone: Sprout, permissao: 'crescimento.ver' },
  { rotulo: 'Relatórios', para: '/relatorios/empresas', prefixo: '/relatorios', icone: BarChart3, permissao: 'relatorios.ver' },
]

export const navegacaoAdministracao: ItemNavegacao[] = [
  { rotulo: 'Equipe', para: '/equipe', icone: Users, permissao: 'equipe.gerenciar', contador: 'pedidosAcesso' },
  { rotulo: 'Configurações', para: '/configuracoes/empresa', prefixo: '/configuracoes', icone: ShieldCheck, permissao: 'configuracoes.gerenciar' },
  { rotulo: 'Integrações', para: '/integracoes', icone: Plug, admin: true },
  { rotulo: 'Assinatura', para: '/assinatura', icone: CreditCard, permissao: 'assinatura.gerenciar' },
  { rotulo: 'Auditoria', para: '/auditoria', icone: History, permissao: 'auditoria.ver' },
  { rotulo: 'Plataforma', para: '/plataforma', icone: Building2, superadmin: true },
]

/** Etapa 5b: no rodapé da barra, acima de "Recolher menu" (para todos os logados). */
export const navegacaoRodape: ItemNavegacao[] = [{ rotulo: 'Ajuda', para: '/ajuda', icone: CircleQuestionMark }]

/**
 * O item fica marcado na própria página e nas de dentro (ex.: /contatos/123 marca Contatos).
 * "Importar respostas antigas" (/contatos/importar?tipo=respostas) marca Respostas, de onde a pessoa veio.
 */
export function itemAtivo(i: ItemNavegacao, caminho: string, query: Record<string, unknown>, ativoNoLink: boolean): boolean {
  const tipo = Array.isArray(query.tipo) ? query.tipo[0] : query.tipo
  if (caminho === '/contatos/importar' && tipo === 'respostas') return i.para === '/respostas'
  return ativoNoLink || caminho.startsWith(`${i.prefixo ?? i.para}/`)
}

export function filtrarNavegacao(
  itens: ItemNavegacao[],
  pode: (p: Permissao) => boolean,
  superadmin: boolean,
  admin = false,
): ItemNavegacao[] {
  return itens.filter((i) => (i.superadmin ? superadmin : i.admin ? admin : !i.permissao || pode(i.permissao)))
}
