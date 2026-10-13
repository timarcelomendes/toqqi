// Etapa 5g: os dias do teste grátis vêm de `teste.dias` (Plataforma › Parâmetros), lidos de GET /publico/planos (sem
// login, com cache de 60 s no navegador). Enquanto carrega ou se falhar, vale o padrão do código (14).
// Plano Grátis (docs/api-plano-gratis.md): da mesma resposta, os números do Grátis (`gratis`), onde a conta fica depois
// do teste se não assinar; enquanto carrega ou se falhar, os padrões (100 contatos e 200 envios por e-mail por mês).
import { onMounted, ref, type Ref } from 'vue'
import { publicoApi } from '@/api/publico'
import type { PlanosPublicos } from '@/api/tipos'
import { LIMITES_PADRAO, resumoDosLimites } from '@/modulos/assinatura/gratis'

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

export interface GratisPublico {
  contatos: number
  envios_mes: number
}

const inteiroPositivo = (n: unknown): n is number => typeof n === 'number' && Number.isInteger(n) && n > 0

/** Os números do Grátis da resposta, se vieram certos; senão, null. */
export function gratisDoPublico(r: Partial<PlanosPublicos> | null | undefined): GratisPublico | null {
  const g = r?.gratis
  return g && inteiroPositivo(g.contatos) && inteiroPositivo(g.envios_mes) ? { contatos: g.contatos, envios_mes: g.envios_mes } : null
}

/** "Depois do teste, se não assinar, a conta continua no plano Grátis: até 100 contatos e 200 envios por e-mail por mês." */
export function textoDepoisDoTeste(g: GratisPublico | null | undefined): string {
  return `Depois do teste, se não assinar, a conta continua no plano Grátis: ${resumoDosLimites(g ?? LIMITES_PADRAO)}.`
}

/** Os dias do teste e os números do Grátis, de uma consulta só (os padrões até a resposta chegar ou se ela falhar). */
export function usarTesteEGratis(): { dias: Ref<number>; gratis: Ref<GratisPublico> } {
  const dias = ref(DIAS_TESTE_PADRAO)
  const gratis = ref<GratisPublico>({ contatos: LIMITES_PADRAO.contatos, envios_mes: LIMITES_PADRAO.envios_mes })
  onMounted(async () => {
    try {
      const r = await publicoApi.planos()
      dias.value = diasDoTeste(r) ?? DIAS_TESTE_PADRAO
      gratis.value = gratisDoPublico(r) ?? gratis.value
    } catch {
      /* ficam os padrões */
    }
  })
  return { dias, gratis }
}
