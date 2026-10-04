// Etapa 5g: os dias do teste grátis vêm de `teste.dias` (Plataforma › Parâmetros), lidos de GET /publico/planos (sem
// login, com cache de 60 s no navegador). Enquanto carrega ou se falhar, vale o padrão do código (14).
import { onMounted, ref, type Ref } from 'vue'
import { publicoApi } from '@/api/publico'
import type { PlanosPublicos } from '@/api/tipos'

export const DIAS_TESTE_PADRAO = 14

/** `teste.dias` da resposta, se for um número inteiro positivo; senão, null. */
export function diasDoTeste(r: Partial<PlanosPublicos> | null | undefined): number | null {
  const n = r?.teste?.dias
  return typeof n === 'number' && Number.isInteger(n) && n > 0 ? n : null
}

/** Os dias do teste para a tela: 14 até a resposta chegar (e se ela falhar). */
export function usarDiasTeste(): Ref<number> {
  const dias = ref(DIAS_TESTE_PADRAO)
  onMounted(async () => {
    try {
      dias.value = diasDoTeste(await publicoApi.planos()) ?? DIAS_TESTE_PADRAO
    } catch {
      /* fica o padrão */
    }
  })
  return dias
}
