import { createRouter, createWebHistory, type RouteLocationNormalized, type RouteRecordRaw } from 'vue-router'
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
    /** Só para o perfil administrador da conta. */
    admin?: boolean
    /** Trocar só os parâmetros desta rota (ex.: abrir e fechar o painel de uma ação) não rola a página. */
    manterRolagem?: boolean
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
      { path: 'contatos/importar', name: 'importar', component: () => import('@/modulos/importacao/ImportacaoView.vue'), meta: { titulo: 'Importar planilha', permissao: 'importacao.usar' } },
      { path: 'contatos/:id', name: 'contato', component: () => import('@/modulos/contatos/ContatoView.vue'), meta: { titulo: 'Contato', permissao: 'contatos.ver' } },
      { path: 'envios', name: 'envios', component: () => import('@/modulos/envios/EnviosView.vue'), meta: { titulo: 'Envios', permissao: 'envios.ver' } },
      { path: 'formularios', name: 'formularios', component: () => import('@/modulos/formularios/FormulariosView.vue'), meta: { titulo: 'Formulários', permissao: 'formularios.ver' } },
      { path: 'formularios/:id', name: 'formulario', component: () => import('@/modulos/formularios/EditorFormularioView.vue'), meta: { titulo: 'Formulário', permissao: 'formularios.ver' } },
      { path: 'respostas', name: 'respostas', component: () => import('@/modulos/respostas/RespostasView.vue'), meta: { titulo: 'Respostas', permissao: 'respostas.ver' } },
      // Um registro só (com :id opcional): abrir e fechar o painel de uma ação não recria a tela.
      { path: 'planos-de-acao/:id?', name: 'planos-de-acao', component: () => import('@/modulos/acoes/PlanosAcaoView.vue'), meta: { titulo: 'Planos de ação', permissao: 'acoes.ver', manterRolagem: true } },
      // Etapa 4b: uma tela com 7 abas; a aba e os filtros ficam no endereço (/relatorios/temas?periodo=30).
      { path: 'relatorios', redirect: (to) => ({ path: '/relatorios/empresas', query: to.query }) },
      { path: 'relatorios/:aba', name: 'relatorios', component: () => import('@/modulos/relatorios/RelatoriosView.vue'), meta: { titulo: 'Relatórios', permissao: 'relatorios.ver' } },
      { path: 'assinatura', name: 'assinatura', component: emConstrucao, meta: { titulo: 'Assinatura' } },
      { path: 'minha-conta', name: 'minha-conta', component: () => import('@/modulos/conta/MinhaContaView.vue'), meta: { titulo: 'Minha conta' } },
      { path: 'equipe', name: 'equipe', component: () => import('@/modulos/equipe/EquipeView.vue'), meta: { titulo: 'Equipe', permissao: 'equipe.gerenciar' } },
      {
        path: 'configuracoes',
        // Leva para a primeira seção que o perfil pode ver.
        redirect: () => {
          const sessao = useSessaoStore()
          if (sessao.pode('configuracoes.gerenciar')) return '/configuracoes/empresa'
          if (sessao.pode('envios.ver')) return '/configuracoes/envios'
          if (sessao.pode('acoes.ver')) return '/configuracoes/acoes'
          return '/inicio'
        },
      },
      { path: 'configuracoes/empresa', name: 'config-empresa', component: () => import('@/modulos/configuracoes/EmpresaView.vue'), meta: { titulo: 'Dados da empresa', permissao: 'configuracoes.gerenciar' } },
      { path: 'configuracoes/seguranca', name: 'seguranca', component: () => import('@/modulos/configuracoes/SegurancaView.vue'), meta: { titulo: 'Segurança', permissao: 'configuracoes.gerenciar' } },
      { path: 'configuracoes/envios', name: 'config-envios', component: () => import('@/modulos/configuracoes/ConfigEnviosView.vue'), meta: { titulo: 'Configurações de envio', permissao: 'envios.ver' } },
      { path: 'configuracoes/acoes', name: 'config-acoes', component: () => import('@/modulos/configuracoes/ConfigAcoesView.vue'), meta: { titulo: 'Configurações dos planos de ação', permissao: 'acoes.ver' } },
      { path: 'configuracoes/ia', name: 'config-ia', component: () => import('@/modulos/configuracoes/IaView.vue'), meta: { titulo: 'Inteligência artificial', permissao: 'configuracoes.gerenciar' } },
      { path: 'integracoes', name: 'integracoes', component: () => import('@/modulos/integracoes/IntegracoesView.vue'), meta: { titulo: 'Integrações', admin: true } },
      { path: 'auditoria', name: 'auditoria', component: () => import('@/modulos/auditoria/AuditoriaView.vue'), meta: { titulo: 'Auditoria', permissao: 'auditoria.ver' } },
      { path: 'plataforma', name: 'plataforma', component: () => import('@/modulos/plataforma/PlataformaView.vue'), meta: { titulo: 'Plataforma', superadmin: true } },
    ],
  },
  { path: '/:caminho(.*)*', name: 'nao-encontrada', component: () => import('@/modulos/geral/NaoEncontradaView.vue'), meta: { titulo: 'Página não encontrada' } },
]

/**
 * Rolagem ao navegar: voltar e avançar devolvem a posição salva; mudar só a query (filtros, página, o painel
 * "Analisar") não rola; outra página vai para o topo. Numa rota com `manterRolagem`, trocar só os parâmetros também
 * não rola. (A paginação leva a tela ao começo da lista por conta própria: ver `Paginacao`.)
 */
export function rolagemAoNavegar(
  to: Pick<RouteLocationNormalized, 'path' | 'name' | 'meta'>,
  from: Pick<RouteLocationNormalized, 'path' | 'name'>,
  salvo: { left: number; top: number } | null,
): false | { left?: number; top: number } {
  if (salvo) return salvo
  if (to.path === from.path) return false
  if (to.name && to.name === from.name && to.meta.manterRolagem) return false
  return { top: 0 }
}

type Posicao = { left: number; top: number }

/**
 * Voltar e avançar: a tela monta e busca os dados de novo, então a página ainda está curta quando a navegação
 * termina e o navegador cortaria a posição salva. Espera a página crescer até caber a posição (no máximo
 * `limiteMs`); se a pessoa rolar, tocar ou usar o teclado nesse meio-tempo, não mexe mais na rolagem.
 */
export function quandoCouber(salvo: Posicao, limiteMs = 2000): Promise<Posicao | false> {
  return new Promise((resolve) => {
    const inicio = Date.now()
    let mexeu = false
    const marcar = () => (mexeu = true)
    const EVENTOS = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const
    for (const e of EVENTOS) window.addEventListener(e, marcar, { passive: true })
    const fim = (r: Posicao | false) => {
      for (const e of EVENTOS) window.removeEventListener(e, marcar)
      resolve(r)
    }
    const tentar = () => {
      if (mexeu) return fim(false)
      const cabe = document.documentElement.scrollHeight - window.innerHeight >= salvo.top
      if (cabe || Date.now() - inicio >= limiteMs) return fim(salvo)
      setTimeout(tentar, 50)
    }
    tentar()
  })
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: rotas,
  scrollBehavior: (to, from, salvo) => {
    const destino = rolagemAoNavegar(to, from, salvo)
    return salvo && destino === salvo ? quandoCouber(salvo) : destino
  },
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
  if (to.meta.admin && !sessao.admin) {
    avisar.atencao('Só um administrador da sua empresa pode abrir essa página.')
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
