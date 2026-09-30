import { reactive, ref } from 'vue'
import { ApiError, mensagemDoErro } from '@/api'

/**
 * Estado comum de formulário: enviando, erro geral e erros por campo vindos da API (422/409).
 */
export function useFormulario() {
  const enviando = ref(false)
  const erroGeral = ref<string | null>(null)
  const codigoErro = ref<string | null>(null)
  const erros = reactive<Record<string, string>>({})

  function limpar() {
    erroGeral.value = null
    codigoErro.value = null
    for (const k of Object.keys(erros)) delete erros[k]
  }

  /** Executa `acao`; em erro, preenche os campos e a mensagem geral. Retorna o resultado ou undefined. */
  async function executar<T>(acao: () => Promise<T>): Promise<T | undefined> {
    if (enviando.value) return undefined
    limpar()
    enviando.value = true
    try {
      return await acao()
    } catch (e) {
      if (e instanceof ApiError) {
        codigoErro.value = e.codigo
        Object.assign(erros, e.campos)
        // Se o erro só tem campos, a mensagem geral ainda ajuda leitores de tela a perceber.
        erroGeral.value = e.mensagem
      } else {
        erroGeral.value = mensagemDoErro(e)
      }
      return undefined
    } finally {
      enviando.value = false
    }
  }

  return { enviando, erroGeral, codigoErro, erros, limpar, executar }
}
