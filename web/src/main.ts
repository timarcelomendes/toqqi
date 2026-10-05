import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { configurarCliente } from '@/api'
import { avisar } from '@/composables/avisos'
import { router } from '@/router'
import { useSessaoStore } from '@/stores/sessao'
import { instalarAvisoDeErros } from '@/utils/erros'
// Fonte servida pelo próprio site (sem Google Fonts: o navegador não manda o IP a terceiros). Só latin, pesos 400–800.
import '@fontsource/plus-jakarta-sans/latin-400.css'
import '@fontsource/plus-jakarta-sans/latin-500.css'
import '@fontsource/plus-jakarta-sans/latin-600.css'
import '@fontsource/plus-jakarta-sans/latin-700.css'
import '@fontsource/plus-jakarta-sans/latin-800.css'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const sessao = useSessaoStore(pinia)

// Etapa 5h: erros do app vão para Plataforma › Erros (com a conta da sessão, quando há uma).
instalarAvisoDeErros(app, { obterToken: () => sessao.token })

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
