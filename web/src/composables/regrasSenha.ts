import { ref } from 'vue'
import { authApi, type RegrasSenha } from '@/api'
import { REGRAS_PADRAO } from '@/utils/senha'

const regras = ref<RegrasSenha>(REGRAS_PADRAO)
let pedido: Promise<void> | null = null

/** Regras de senha da API (GET /auth/regras-senha), buscadas uma vez e reaproveitadas. */
export function useRegrasSenha() {
  if (!pedido) {
    pedido = authApi
      .regrasSenha()
      .then((r) => {
        if (r && typeof r.minimo === 'number' && Array.isArray(r.exige)) regras.value = r
      })
      .catch(() => {
        pedido = null // tenta de novo na próxima vez; enquanto isso vale o padrão
      })
  }
  return regras
}
