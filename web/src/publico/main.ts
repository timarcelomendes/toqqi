// Entrada leve das páginas públicas (/r/:token, /f/:codigo, /sair/:token e /sair), servida por responder.html.
// Não importa Pinia, router, o layout do app nem lucide: só Vue, o cliente fetch e a página da vez.
// Etapa 5h: os erros da página vão para Plataforma › Erros (sem login; o token do link nunca vai: o local é /r/:token).
import { createApp } from 'vue'
import { instalarAvisoDeErros } from '@/utils/erros'
import PublicoApp from './PublicoApp.vue'
import { ehPedirLink } from './descadastro'
import './publico.css'

const aviso = instalarAvisoDeErros()

if (ehPedirLink(window.location.pathname)) {
  // /sair sem token: pedir por e-mail o link de cada empresa (para sair ou voltar a receber).
  import('./PaginaPedirLink.vue').then(({ default: PaginaPedirLink }) => {
    const app = createApp(PaginaPedirLink)
    aviso.ligarApp(app)
    app.mount('#app')
  })
} else if (window.location.pathname.startsWith('/sair/')) {
  // Descadastro: carregado à parte, para não pesar na pesquisa (o caminho mais usado).
  import('./PaginaDescadastro.vue').then(({ default: PaginaDescadastro }) => {
    const app = createApp(PaginaDescadastro)
    aviso.ligarApp(app)
    app.mount('#app')
  })
} else {
  const app = createApp(PublicoApp)
  aviso.ligarApp(app)
  app.mount('#app')
}
