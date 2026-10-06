// Pedidos de acesso esperando aprovação: o número ao lado de Equipe no menu (GET /equipe/pendentes, só para quem
// gerencia a equipe). A barra lateral lê ao abrir o app e a cada troca de página (no máximo uma vez a cada 60 s); a
// tela Equipe acerta o número na hora, pela própria lista, quando aprova, bloqueia ou exclui alguém.
import { ref } from 'vue'
import { equipeApi } from '@/api'

export const INTERVALO_PEDIDOS_MS = 60_000

const total = ref(0)
let lidoEm = 0
let lendo: Promise<void> | null = null

export function usarPedidosAcesso() {
  /** Relê o número (sem permissão, zera). `forcar` ignora o intervalo de 60 s. Falhou: fica o último número. */
  function atualizar(podeVer: boolean, forcar = false): Promise<void> {
    if (!podeVer) {
      total.value = 0
      return Promise.resolve()
    }
    if (lendo) return lendo
    if (!forcar && lidoEm && Date.now() - lidoEm < INTERVALO_PEDIDOS_MS) return Promise.resolve()
    lendo = equipeApi
      .pendentes()
      .then((r) => {
        total.value = Math.max(0, r.total)
        lidoEm = Date.now()
      })
      .catch(() => {
        /* sem o número novo, fica o último */
      })
      .finally(() => {
        lendo = null
      })
    return lendo
  }

  /** O número que a tela Equipe já sabe (contado na lista). */
  function definir(n: number) {
    total.value = Math.max(0, n)
    lidoEm = Date.now()
  }

  return { total, atualizar, definir }
}

/** Texto para leitores de tela e para a dica do menu recolhido. */
export function textoPedidos(n: number): string {
  return n === 1 ? '1 pedido de acesso' : `${n} pedidos de acesso`
}

/** Só para os testes. */
export function limparPedidosAcesso() {
  total.value = 0
  lidoEm = 0
  lendo = null
}
