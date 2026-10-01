// Busca dos dados de uma aba de Relatórios: recarrega quando os filtros da API mudam (com uma pequena espera),
// cancela o pedido anterior e mantém os números na tela (mais apagados) enquanto o novo chega.
import { onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { ApiError, mensagemDoErro } from '@/api'

export interface CargaRelatorio<T> {
  dados: Ref<T | null>
  /** Primeira carga (sem nada na tela ainda). */
  carregando: Ref<boolean>
  /** Recarga com os números antigos ainda na tela. */
  atualizando: Ref<boolean>
  erro: Ref<string | null>
  /** Status HTTP do erro (ex.: 404 no histórico de uma empresa que não é da conta); 0 sem conexão. */
  statusErro: Ref<number | null>
  carregar: () => Promise<void>
}

/**
 * @param buscar faz o pedido (com o sinal para cancelar)
 * @param chave o que, mudando, pede os dados de novo (ex.: os filtros da API em JSON)
 * @param pronto falso enquanto falta algo para buscar (ex.: datas escolhidas incompletas): a tela fica como está
 */
export function usarRelatorio<T>(buscar: (sinal: AbortSignal) => Promise<T>, chave: () => string, pronto: () => boolean = () => true): CargaRelatorio<T> {
  const dados = ref<T | null>(null) as Ref<T | null>
  const carregando = ref(true)
  const atualizando = ref(false)
  const erro = ref<string | null>(null)
  const statusErro = ref<number | null>(null)
  let controle: AbortController | null = null
  let pedido = 0
  let atraso: ReturnType<typeof setTimeout> | null = null

  async function carregar() {
    if (!pronto()) {
      carregando.value = false
      return
    }
    controle?.abort()
    controle = new AbortController()
    const meu = ++pedido
    if (dados.value) atualizando.value = true
    else carregando.value = true
    erro.value = null
    statusErro.value = null
    try {
      const r = await buscar(controle.signal)
      if (meu === pedido) dados.value = r
    } catch (e) {
      if (meu !== pedido || (e instanceof DOMException && e.name === 'AbortError')) return
      erro.value = mensagemDoErro(e)
      statusErro.value = e instanceof ApiError ? e.status : null
    } finally {
      // Só o pedido mais recente mexe no "carregando": um cancelado não apaga o estado do novo.
      if (meu === pedido) {
        carregando.value = false
        atualizando.value = false
      }
    }
  }

  watch(chave, () => {
    if (atraso) clearTimeout(atraso)
    atraso = setTimeout(carregar, 200)
  })
  onMounted(carregar)
  onBeforeUnmount(() => {
    controle?.abort()
    if (atraso) clearTimeout(atraso)
  })

  return { dados, carregando, atualizando, erro, statusErro, carregar }
}
