import { createRouter, createWebHistory, type RouteLocationNormalized, type RouteRecordRaw } from 'vue-router'
import type { Permissao } from '@/api/tipos'
import { avisar } from '@/composables/avisos'
import { redirecionarAceite } from '@/modulos/geral/legal/aceite'
import { useSessaoStore } from '@/stores/sessao'

declare module 'vue-router' {
  interface RouteMeta {
    titulo?: string
    /** Página só para quem NÃO está logado (entrar, cadastro...). */
    visitante?: boolean
    /** Página que exige estar logado. */
    logado?: boolean
    permissao?: Permissao
    /** Basta uma destas permissões (ex.: Configurações › Crescimento, que também abre para quem vê o Crescimento). */
    algumaPermissao?: Permissao[]
    superadmin?: boolean
    /** Só para o perfil administrador da conta. */
    admin?: boolean
    /** Trocar só os parâmetros desta rota (ex.: abrir e fechar o painel de uma ação) não rola a página. */
    manterRolagem?: boolean
    /** A tela leva à seção da âncora sozinha (ex.: /privacidade#cookies): o router não rola quando há âncora. */
    ancoras?: boolean
    /** Etapa 5l: a tela usa a largura toda (o editor de formulário, em 3 colunas). */
    larguraTotal?: boolean
  }
}

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
      { path: 'termos', name: 'termos', component: () => import('@/modulos/geral/DocumentoLegalView.vue'), props: { tipo: 'termos' }, meta: { titulo: 'Termos de uso', ancoras: true } },
      // Aceite dos termos e da política (docs/api-aceite-lgpd.md §3): bloqueia o app até aceitar; fora do AppLayout.
      { path: 'aceite', name: 'aceite', component: () => import('@/modulos/geral/AceiteView.vue'), meta: { titulo: 'Termos e privacidade', logado: true } },
      { path: 'privacidade', name: 'privacidade', component: () => import('@/modulos/geral/DocumentoLegalView.vue'), props: { tipo: 'privacidade' }, meta: { titulo: 'Política de privacidade', ancoras: true } },
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
      { path: 'contatos/empresas/:id', name: 'empresa', component: () => import('@/modulos/contatos/EmpresaView.vue'), meta: { titulo: 'Empresa', permissao: 'contatos.ver' } },
      { path: 'contatos/:id', name: 'contato', component: () => import('@/modulos/contatos/ContatoView.vue'), meta: { titulo: 'Contato', permissao: 'contatos.ver' } },
      { path: 'envios', name: 'envios', component: () => import('@/modulos/envios/EnviosView.vue'), meta: { titulo: 'Envios', permissao: 'envios.ver' } },
      { path: 'formularios', name: 'formularios', component: () => import('@/modulos/formularios/FormulariosView.vue'), meta: { titulo: 'Formulários', permissao: 'formularios.ver' } },
      { path: 'formularios/:id', name: 'formulario', component: () => import('@/modulos/formularios/EditorFormularioView.vue'), meta: { titulo: 'Formulário', permissao: 'formularios.ver', larguraTotal: true } },
      { path: 'respostas', name: 'respostas', component: () => import('@/modulos/respostas/RespostasView.vue'), meta: { titulo: 'Respostas', permissao: 'respostas.ver' } },
      // Um registro só (com :id opcional): abrir e fechar o painel de uma ação não recria a tela.
      { path: 'planos-de-acao/:id?', name: 'planos-de-acao', component: () => import('@/modulos/acoes/PlanosAcaoView.vue'), meta: { titulo: 'Planos de ação', permissao: 'acoes.ver', manterRolagem: true } },
      // Etapa 4b: uma tela com 7 abas; a aba e os filtros ficam no endereço (/relatorios/temas?periodo=30).
      { path: 'relatorios', redirect: (to) => ({ path: '/relatorios/empresas', query: to.query }) },
      { path: 'relatorios/:aba', name: 'relatorios', component: () => import('@/modulos/relatorios/RelatoriosView.vue'), meta: { titulo: 'Relatórios', permissao: 'relatorios.ver' } },
      // Etapa 5c: Crescimento com as abas Indicações e Oportunidades; a aba e os filtros ficam no endereço.
      { path: 'crescimento', redirect: (to) => ({ path: '/crescimento/indicacoes', query: to.query }) },
      { path: 'crescimento/:aba', name: 'crescimento', component: () => import('@/modulos/crescimento/CrescimentoView.vue'), meta: { titulo: 'Crescimento', permissao: 'crescimento.ver' } },
      // Etapa 5a: planos, fatura em aberto, trocar de plano, dados de cobrança, cancelar e histórico.
      { path: 'assinatura', name: 'assinatura', component: () => import('@/modulos/assinatura/AssinaturaView.vue'), meta: { titulo: 'Assinatura', permissao: 'assinatura.gerenciar' } },
      // Etapa 5b: tópicos e seções da ajuda (/ajuda/contatos#importar-planilha); trocar de tópico não rola a página (a tela cuida).
      { path: 'ajuda/:topico?', name: 'ajuda', component: () => import('@/modulos/ajuda/AjudaView.vue'), meta: { titulo: 'Ajuda', manterRolagem: true } },
      { path: 'minha-conta', name: 'minha-conta', component: () => import('@/modulos/conta/MinhaContaView.vue'), meta: { titulo: 'Minha conta' } },
      // Feedback (docs/api-feedback.md): o que a pessoa mandou para a equipe Toqqi e cada conversa (link do e-mail).
      { path: 'feedback', name: 'feedbacks', component: () => import('@/modulos/feedback/FeedbacksView.vue'), meta: { titulo: 'Seus feedbacks' } },
      { path: 'feedback/:id(\\d+)', name: 'feedback', component: () => import('@/modulos/feedback/FeedbackView.vue'), meta: { titulo: 'Feedback' } },
      { path: 'equipe', name: 'equipe', component: () => import('@/modulos/equipe/EquipeView.vue'), meta: { titulo: 'Equipe', permissao: 'equipe.gerenciar' } },
      {
        path: 'configuracoes',
        // Leva para a primeira seção que o perfil pode ver.
        redirect: () => {
          const sessao = useSessaoStore()
          if (sessao.pode('configuracoes.gerenciar')) return '/configuracoes/empresa'
          if (sessao.pode('envios.ver')) return '/configuracoes/envios'
          if (sessao.pode('acoes.ver')) return '/configuracoes/acoes'
          if (sessao.pode('crescimento.ver')) return '/configuracoes/crescimento'
          return '/inicio'
        },
      },
      { path: 'configuracoes/empresa', name: 'config-empresa', component: () => import('@/modulos/configuracoes/EmpresaView.vue'), meta: { titulo: 'Dados da empresa', permissao: 'configuracoes.gerenciar' } },
      { path: 'configuracoes/seguranca', name: 'seguranca', component: () => import('@/modulos/configuracoes/SegurancaView.vue'), meta: { titulo: 'Segurança', permissao: 'configuracoes.gerenciar' } },
      { path: 'configuracoes/envios', name: 'config-envios', component: () => import('@/modulos/configuracoes/ConfigEnviosView.vue'), meta: { titulo: 'Configurações de envio', permissao: 'envios.ver' } },
      { path: 'configuracoes/acoes', name: 'config-acoes', component: () => import('@/modulos/configuracoes/ConfigAcoesView.vue'), meta: { titulo: 'Configurações dos planos de ação', permissao: 'acoes.ver' } },
      // Etapa 5c: alterar pede configuracoes.gerenciar; quem vê o Crescimento abre para consultar.
      {
        path: 'configuracoes/crescimento',
        name: 'config-crescimento',
        component: () => import('@/modulos/configuracoes/ConfigCrescimentoView.vue'),
        meta: { titulo: 'Configurações de crescimento', algumaPermissao: ['configuracoes.gerenciar', 'crescimento.ver'] },
      },
      { path: 'configuracoes/ia', name: 'config-ia', component: () => import('@/modulos/configuracoes/IaView.vue'), meta: { titulo: 'Inteligência artificial', permissao: 'configuracoes.gerenciar' } },
      // Etapa 5f: exportar todos os dados e a Zona de risco. Só administrador; livre com o aceite pendente (ROTAS_LIVRES).
      { path: 'configuracoes/dados-da-conta', name: 'config-dados', component: () => import('@/modulos/configuracoes/DadosContaView.vue'), meta: { titulo: 'Dados da conta', admin: true } },
      { path: 'integracoes', name: 'integracoes', component: () => import('@/modulos/integracoes/IntegracoesView.vue'), meta: { titulo: 'Integrações', admin: true } },
      // Etapa 5e: abas "Atividades" (/auditoria) e "E-mails enviados" (/auditoria/emails; /auditoria?aba=emails também abre).
      {
        path: 'auditoria/:aba(atividades|emails)?',
        name: 'auditoria',
        component: () => import('@/modulos/auditoria/AuditoriaView.vue'),
        meta: { titulo: 'Auditoria', permissao: 'auditoria.ver', manterRolagem: true },
      },
      // Etapa 5h: abas "Visão geral" (/plataforma), "Contas" (/plataforma/contas), "Parâmetros" (/plataforma/parametros),
      // "Erros" (/plataforma/erros) e "Feedback" (/plataforma/feedback); só superadmin.
      {
        path: 'plataforma/:aba(contas|parametros|erros|feedback)?',
        name: 'plataforma',
        component: () => import('@/modulos/plataforma/PlataformaView.vue'),
        meta: { titulo: 'Plataforma', superadmin: true, manterRolagem: true },
      },
      // Feedback: um feedback na Plataforma (link dos e-mails da equipe).
      {
        path: 'plataforma/feedback/:id(\\d+)',
        name: 'plataforma-feedback',
        component: () => import('@/modulos/plataforma/FeedbackPlataformaView.vue'),
        meta: { titulo: 'Feedback', superadmin: true },
      },
    ],
  },
  { path: '/:caminho(.*)*', name: 'nao-encontrada', component: () => import('@/modulos/geral/NaoEncontradaView.vue'), meta: { titulo: 'Página não encontrada' } },
]

/**
 * Rolagem ao navegar: voltar e avançar devolvem a posição salva; mudar só a query (filtros, página, o painel
 * "Analisar") não rola; outra página vai para o topo. Numa rota com `manterRolagem`, trocar só os parâmetros também
 * não rola. Numa rota com `ancoras` e endereço com âncora, a tela rola até a seção sozinha. (A paginação leva a tela ao começo da lista por conta própria: ver `Paginacao`.)
 */
export function rolagemAoNavegar(
  to: Pick<RouteLocationNormalized, 'path' | 'name' | 'meta'> & { hash?: string },
  from: Pick<RouteLocationNormalized, 'path' | 'name'>,
  salvo: { left: number; top: number } | null,
): false | { left?: number; top: number } {
  if (salvo) return salvo
  if (to.path === from.path) return false
  if (to.hash && to.meta.ancoras) return false
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
  // Aceite pendente: o app fica atrás da tela "Antes de continuar" (termos, privacidade e links de e-mail ficam livres).
  const aceite = redirecionarAceite(to, { logado: sessao.logado, aceite: sessao.usuario?.aceite })
  if (aceite) return aceite
  if (to.meta.superadmin && !sessao.superadmin) {
    avisar.atencao('Esta área é só para a equipe da plataforma Toqqi.')
    return { name: 'inicio' }
  }
  if (to.meta.admin && !sessao.admin) {
    avisar.atencao('Só um administrador da sua empresa pode abrir essa página.')
    return { name: 'inicio' }
  }
  if ((to.meta.permissao && !sessao.pode(to.meta.permissao)) || (to.meta.algumaPermissao && !to.meta.algumaPermissao.some((p) => sessao.pode(p)))) {
    avisar.atencao('Seu perfil não tem acesso a essa página. Fale com um administrador da sua empresa.')
    return { name: 'inicio' }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.titulo ? `${to.meta.titulo} · Toqqi` : 'Toqqi'
})
