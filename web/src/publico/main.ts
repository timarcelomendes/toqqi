// Entrada leve das páginas públicas (/r/:token e /f/:codigo), servida por responder.html.
// Não importa Pinia, router, o layout do app nem lucide: só Vue, o cliente fetch e a pesquisa.
import { createApp } from 'vue'
import PublicoApp from './PublicoApp.vue'
import './publico.css'

createApp(PublicoApp).mount('#app')
