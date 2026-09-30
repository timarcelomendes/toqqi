import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import type { Permissao } from '@/api/tipos'
import { avisar } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'

declare module 'vue-router' {
  interface RouteMeta {
    titulo?: string
    /** Página só para quem NÃO está logado (entrar, cadastro...). */
    visitante?: boolean
    /** Página que exige estar logado. */
    logado?: boolean
    permissao?: Permissao
    superadmin?: boolean
  }
}

const emConstrucao = () => import('@/modulos/geral/EmConstrucaoView.vue')

const rotas: RouteRecordRaw[] = [
  { path: '/', redirect: '/inicio' },
  {
    path: '/',
    component: () => import('@/layouts/AcessoLayout.vue'),
    children: [
      { path: 'entrar', name: 'entrar', component: () => import('@/modulos/acesso/EntrarView.vue'), meta: { titulo: 'Entrar', visitante: true } },
      { path: 'cadastro', name: 'cadastro', component: () => import('@/modulos/acesso/CadastroView.vue'), meta: { titulo: 'Criar conta', visitante: true } },
      { path: 'confirmar-email', name: 'confirmar-email', component: () => import('@/modulos/acesso/ConfirmarEmailView.vue'), meta: { titulo: 'Confirmar e-mail' } },
      { path: 'esqueci-senha', name: 'esqueci-senha', component: () => import('@/modulos/acesso/EsqueciSenhaView.vue'), meta: { titulo: 'Esqueci a senha', visitante: true } },
      { path: 'redefinir-senha', name: 'redefinir-senha', component: () => import('@/modulos/acesso/RedefinirSenhaView.vue'), meta: { titulo: 'Nova senha' } },
      { path: 'pedir-acesso', name: 'pedir-acesso', component: () => import('@/modulos/acesso/PedirAcessoView.vue'), meta: { titulo: 'Pedir acesso', visitante: true } },
      { path: 'termos', name: 'termos', component: () => import('@/modulos/geral/DocumentoLegalView.vue'), props: { tipo: 'termos' }, meta: { titulo: 'Termos de uso' } },
      { path: 'privacidade', name: 'privacidade', component: () => import('@/modulos/geral/DocumentoLegalView.vue'), props: { tipo: 'privacidade' }, meta: { titulo: 'Política de privacidade' } },
    ],
  },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    meta: { logado: true },
    children: [
      { path: 'inicio', name: 'inicio', component: () => import('@/modulos/inicio/InicioView.vue'), meta: { titulo: 'Início' } },
      { path: 'contatos', name: 'contatos', component: () => import('@/modulos/contatos/ContatosView.vue'), meta: { titulo: 'Contatos', permissao: 'contatos.ver' } },
      { path: 'contatos/importar', name: 'importar', component: () => import('@/modulos/importacao/ImportacaoView.vue'), meta: { titulo: 'Importar contatos', permissao: 'importacao.usar' } },
      { path: 'contatos/:id', name: 'contato', component: () => import('@/modulos/contatos/ContatoView.vue'), meta: { titulo: 'Contato', permissao: 'contatos.ver' } },
      { path: 'envios', name: 'envios', component: emConstrucao, meta: { titulo: 'Envios', permissao: 'envios.ver' } },
      { path: 'formularios', name: 'formularios', component: () => import('@/modulos/formularios/FormulariosView.vue'), meta: { titulo: 'Formulários', permissao: 'formularios.ver' } },
      { path: 'formularios/:id', name: 'formulario', component: () => import('@/modulos/formularios/EditorFormularioView.vue'), meta: { titulo: 'Formulário', permissao: 'formularios.ver' } },
      { path: 'respostas', name: 'respostas', component: emConstrucao, meta: { titulo: 'Respostas', permissao: 'respostas.ver' } },
      { path: 'planos-de-acao', name: 'planos-de-acao', component: emConstrucao, meta: { titulo: 'Planos de ação', permissao: 'acoes.ver' } },
      { path: 'relatorios', name: 'relatorios', component: emConstrucao, meta: { titulo: 'Relatórios', permissao: 'relatorios.ver' } },
      { path: 'assinatura', name: 'assinatura', component: emConstrucao, meta: { titulo: 'Assinatura' } },
      { path: 'minha-conta', name: 'minha-conta', component: () => import('@/modulos/conta/MinhaContaView.vue'), meta: { titulo: 'Minha conta' } },
      { path: 'equipe', name: 'equipe', component: () => import('@/modulos/equipe/EquipeView.vue'), meta: { titulo: 'Equipe', permissao: 'equipe.gerenciar' } },
      { path: 'configuracoes', redirect: '/configuracoes/seguranca' },
      { path: 'configuracoes/seguranca', name: 'seguranca', component: () => import('@/modulos/configuracoes/SegurancaView.vue'), meta: { titulo: 'Segurança', permissao: 'configuracoes.gerenciar' } },
      { path: 'auditoria', name: 'auditoria', component: () => import('@/modulos/auditoria/AuditoriaView.vue'), meta: { titulo: 'Auditoria', permissao: 'auditoria.ver' } },
      { path: 'plataforma', name: 'plataforma', component: () => import('@/modulos/plataforma/PlataformaView.vue'), meta: { titulo: 'Plataforma', superadmin: true } },
    ],
  },
  { path: '/:caminho(.*)*', name: 'nao-encontrada', component: () => import('@/modulos/geral/NaoEncontradaView.vue'), meta: { titulo: 'Página não encontrada' } },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: rotas,
  scrollBehavior: (_to, _from, salvo) => salvo ?? { top: 0 },
})

router.beforeEach(async (to) => {
  const sessao = useSessaoStore()
  await sessao.inicializar()

  if (to.meta.logado && !sessao.logado) {
    return { name: 'entrar', query: to.fullPath !== '/inicio' ? { voltar: to.fullPath } : {} }
  }
  if (to.meta.visitante && sessao.logado) return { name: 'inicio' }
  if (to.meta.superadmin && !sessao.superadmin) {
    avisar.atencao('Esta área é só para a equipe da plataforma Toqqi.')
    return { name: 'inicio' }
  }
  if (to.meta.permissao && !sessao.pode(to.meta.permissao)) {
    avisar.atencao('Seu perfil não tem acesso a essa página. Fale com um administrador da sua empresa.')
    return { name: 'inicio' }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.titulo ? `${to.meta.titulo} · Toqqi` : 'Toqqi'
})
