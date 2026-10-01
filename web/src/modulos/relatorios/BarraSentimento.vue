<script setup lang="ts">
// Barra do sentimento das respostas analisadas pela IA (positivo, neutro, misto — quando há — e negativo), com os
// nomes e as quantidades escritos na legenda (a cor nunca fala sozinha). As cores são as mesmas dos selos de
// sentimento (`SENTIMENTOS`). "Sem análise" fica fora da barra, em texto.
import { computed } from 'vue'
import { formatarNumero, plural } from '@/utils/formatos'
import { SENTIMENTOS } from '@/modulos/respostas/ia'
import { partesSentimento } from './logica'

const props = withDefaults(
  defineProps<{
    positivo: number
    neutro: number
    negativo: number
    misto?: number
    semAnalise?: number
    /** Só a barra (linhas de tabela); os números ficam no texto para leitor de tela. */
    compacta?: boolean
  }>(),
  { misto: 0, semAnalise: 0, compacta: false },
)

const partes = computed(() =>
  partesSentimento({ positivo: props.positivo, neutro: props.neutro, misto: props.misto, negativo: props.negativo }).map((p) => ({
    ...p,
    rotulo: SENTIMENTOS[p.chave].rotulo,
    cor: SENTIMENTOS[p.chave].barra,
  })),
)
const total = computed(() => partes.value.reduce((a, p) => a + p.qtd, 0))
const visiveis = computed(() => partes.value.filter((p) => p.qtd > 0))
const resumo = computed(() =>
  total.value
    ? `Sentimento: ${partes.value.map((p) => `${p.rotulo.toLowerCase()} ${formatarNumero(p.qtd)}`).join('; ')}${props.semAnalise ? `; sem análise ${formatarNumero(props.semAnalise)}` : ''}`
    : props.semAnalise
      ? `Nenhuma análise da IA; ${formatarNumero(props.semAnalise)} sem análise`
      : 'Sem comentários',
)
</script>

<template>
  <div class="flex min-w-0 flex-col gap-1.5">
    <div class="flex w-full gap-0.5" :class="compacta ? 'h-2' : 'h-3'" role="img" :aria-label="resumo" :title="compacta ? resumo : undefined">
      <template v-if="total">
        <div
          v-for="(p, i) in visiveis"
          :key="p.chave"
          class="h-full min-w-1"
          :class="[p.cor, i === 0 ? 'rounded-l-[4px]' : '', i === visiveis.length - 1 ? 'rounded-r-[4px]' : '']"
          :style="{ flexGrow: p.fracao, flexBasis: 0 }"
        />
      </template>
      <div v-else class="h-full w-full rounded-[4px] bg-superficie-2" />
    </div>
    <ul v-if="!compacta" class="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-hidden="true">
      <li v-for="p in partes" :key="p.chave" class="inline-flex items-center gap-1.5 text-texto-suave">
        <span class="size-2.5 shrink-0 rounded-[3px]" :class="p.cor" />
        <strong class="font-semibold text-texto">{{ formatarNumero(p.qtd) }}</strong> {{ p.rotulo.toLowerCase() }}
      </li>
      <li v-if="semAnalise" class="text-texto-fraco">{{ plural(semAnalise, 'sem análise', 'sem análise') }}</li>
    </ul>
  </div>
</template>
