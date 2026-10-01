import type { Component } from 'vue'
import {
  BarChart3,
  ClipboardList,
  FileText,
  History,
  Home,
  MessageSquareText,
  Send,
  ShieldCheck,
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
  /** Marca o item como ativo em qualquer página que comece com este caminho (padrão: `para`). */
  prefixo?: string
  /** Ainda não existe nesta etapa. */
  emBreve?: boolean
}

export const navegacaoPrincipal: ItemNavegacao[] = [
  { rotulo: 'Início', para: '/inicio', icone: Home },
  { rotulo: 'Contatos', para: '/contatos', icone: UsersRound, permissao: 'contatos.ver' },
  { rotulo: 'Envios', para: '/envios', icone: Send, permissao: 'envios.ver' },
  { rotulo: 'Formulários', para: '/formularios', icone: FileText, permissao: 'formularios.ver' },
  { rotulo: 'Respostas', para: '/respostas', icone: MessageSquareText, permissao: 'respostas.ver', emBreve: true },
  { rotulo: 'Planos de ação', para: '/planos-de-acao', icone: ClipboardList, permissao: 'acoes.ver', emBreve: true },
  { rotulo: 'Relatórios', para: '/relatorios', icone: BarChart3, permissao: 'relatorios.ver', emBreve: true },
]

export const navegacaoAdministracao: ItemNavegacao[] = [
  { rotulo: 'Equipe', para: '/equipe', icone: Users, permissao: 'equipe.gerenciar' },
  { rotulo: 'Configurações', para: '/configuracoes/seguranca', prefixo: '/configuracoes', icone: ShieldCheck, permissao: 'configuracoes.gerenciar' },
  { rotulo: 'Auditoria', para: '/auditoria', icone: History, permissao: 'auditoria.ver' },
  { rotulo: 'Plataforma', para: '/plataforma', icone: Building2, superadmin: true },
]

export function filtrarNavegacao(
  itens: ItemNavegacao[],
  pode: (p: Permissao) => boolean,
  superadmin: boolean,
): ItemNavegacao[] {
  return itens.filter((i) => (i.superadmin ? superadmin : !i.permissao || pode(i.permissao)))
}
