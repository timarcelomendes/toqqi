<script setup lang="ts">
// O risco de uma conta (docs/api-plataforma-risco.md), igual na coluna Risco e embaixo do nome (telas menores que
// 1024 px, sem a coluna: `embaixo`, com a palavra "risco" no texto). Médio e alto: o selo colorido com a nota; baixo: a
// nota em cinza; sem sinal: "Nenhum sinal". Embaixo, os motivos com os pontos de cada um. Conta da equipe (algum
// administrador em SUPERADMIN_EMAILS): "Conta da equipe, sem nota", escrito (antes era só um "—", com a explicação na
// dica do mouse: com só contas da equipe na lista, parecia que a nota não tinha aparecido).
import type { ContaPlataforma } from '@/api'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { NIVEIS, detalheSinal, suspeita, textoSinal } from './risco'

defineProps<{ conta: ContaPlataforma; embaixo?: boolean }>()
</script>

<template>
  <div v-if="conta.risco" :class="embaixo ? 'mt-2' : 'min-w-44 max-w-64'" :data-risco="embaixo ? undefined : ''" :data-risco-embaixo="embaixo ? '' : undefined">
    <Etiqueta v-if="suspeita(conta)" :tom="NIVEIS[conta.risco.nivel].tom" data-nivel
      >{{ embaixo ? `Risco ${NIVEIS[conta.risco.nivel].rotulo.toLowerCase()}` : NIVEIS[conta.risco.nivel].rotulo }}
      <span class="tabular-nums">{{ conta.risco.pontos }}</span><span class="sr-only"> de 100 pontos</span></Etiqueta
    >
    <p v-else-if="conta.risco.sinais.length" class="text-texto-fraco tabular-nums" :class="embaixo ? 'text-xs' : ''" data-nivel>
      {{ embaixo ? 'Risco baixo' : 'Baixo' }} {{ conta.risco.pontos }}<span class="sr-only"> de 100 pontos</span>
    </p>
    <p v-else class="text-texto-fraco" :class="embaixo ? 'text-xs' : ''" data-nivel>{{ embaixo ? 'Nenhum sinal de risco' : 'Nenhum sinal' }}</p>
    <ul v-if="conta.risco.sinais.length" class="mt-1.5 space-y-1 text-xs leading-snug" :class="suspeita(conta) ? 'text-texto-suave' : 'text-texto-fraco'">
      <li v-for="(sinal, i) in conta.risco.sinais" :key="i" class="flex gap-1.5" data-sinal>
        <span class="w-6 shrink-0 text-right font-semibold tabular-nums text-texto-fraco" aria-hidden="true">+{{ sinal.pontos }}</span>
        <span class="min-w-0 [overflow-wrap:anywhere]"
          >{{ textoSinal(sinal) }}<span class="sr-only"> ({{ sinal.pontos }} pontos)</span
          ><span v-if="detalheSinal(sinal)" class="mt-0.5 block text-texto-fraco">{{ detalheSinal(sinal) }}</span></span
        >
      </li>
    </ul>
  </div>
  <p v-else class="text-texto-fraco" :class="embaixo ? 'mt-2 text-xs' : ''" title="As contas da equipe Toqqi não recebem nota de risco" data-risco-equipe>
    {{ embaixo ? 'Conta da equipe, sem nota de risco' : 'Conta da equipe, sem nota' }}
  </p>
</template>
