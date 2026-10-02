<script setup lang="ts">
// Medidor de uso (X de Y): a barra cheia mostra quanto já foi usado; a cor muda perto do limite.
// Genérico (limites, cotas). O texto com os números fica sempre visível ao lado (a barra não fala sozinha).
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    valor: number
    maximo: number
    /** Nome do medidor para leitores de tela (ex.: "Análises usadas neste mês"). */
    rotulo: string
    /** Texto para leitores de tela (padrão: "X de Y"). */
    texto?: string
    /** A partir de qual fração muda para atenção (padrão 0,9). No limite, vira erro. */
    alerta?: number
    /** Barra mais fina, para cabeçalhos compactos (ex.: a cota no painel do assistente). */
    fino?: boolean
  }>(),
  { alerta: 0.9 },
)

const fracao = computed(() => (props.maximo > 0 ? Math.min(1, Math.max(0, props.valor / props.maximo)) : 0))
const cor = computed(() =>
  props.maximo > 0 && props.valor >= props.maximo ? 'bg-erro' : fracao.value >= props.alerta ? 'bg-atencao' : 'bg-grafico-serie',
)
</script>

<template>
  <div
    role="meter"
    :aria-label="rotulo"
    aria-valuemin="0"
    :aria-valuemax="Math.max(0, maximo)"
    :aria-valuenow="Math.min(Math.max(0, valor), Math.max(0, maximo))"
    :aria-valuetext="texto ?? `${valor} de ${maximo}`"
    class="w-full overflow-hidden rounded-full bg-borda-forte"
    :class="fino ? 'h-1.5' : 'h-2.5'"
  >
    <div class="h-full rounded-full transition-[width] duration-300" :class="cor" :style="{ width: `${fracao * 100}%` }" />
  </div>
</template>
