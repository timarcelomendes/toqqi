import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { configurarCliente } from '@/api'
import { avisar } from '@/composables/avisos'
import { router } from '@/router'
import { useSessaoStore } from '@/stores/sessao'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const sessao = useSessaoStore(pinia)

configurarCliente({
  obterToken: () => sessao.token,
  aoSessaoInvalida: (erro) => {
    sessao.limpar(erro.mensagem)
    const atual = router.currentRoute.value
    // Na primeira navegação (atual ainda vazio), quem redireciona é o guard do router.
    if (atual.matched.length && atual.meta.logado) {
      router.push({ name: 'entrar', query: { voltar: atual.fullPath } })
    }
  },
  aoSemPermissao: (erro) => avisar.atencao(erro.mensagem),
})

app.use(router)
app.mount('#app')
