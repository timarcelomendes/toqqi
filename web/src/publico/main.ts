// Entrada leve das páginas públicas (/r/:token, /f/:codigo e /sair/:token), servida por responder.html.
// Não importa Pinia, router, o layout do app nem lucide: só Vue, o cliente fetch e a página da vez.
import { createApp } from 'vue'
import PublicoApp from './PublicoApp.vue'
import './publico.css'

if (window.location.pathname.startsWith('/sair/')) {
  // Descadastro: carregado à parte, para não pesar na pesquisa (o caminho mais usado).
  import('./PaginaDescadastro.vue').then(({ default: PaginaDescadastro }) => createApp(PaginaDescadastro).mount('#app'))
} else {
  createApp(PublicoApp).mount('#app')
}
