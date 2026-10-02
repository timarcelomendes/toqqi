<script setup lang="ts">
// Medidor semicircular do NPS (−100 a 100): as três faixas em tons suaves (detrator < 0, neutro 0 a 49, promotor ≥ 50),
// o marcador no valor e o número grande no centro. O número está escrito; para leitor de tela, o SVG tem o rótulo.
import { computed } from 'vue'
import { FAIXAS_MEDIDOR, arcoNps, formatarNps, pontoNoArco } from './logica'

const props = defineProps<{ valor: number; faixa?: string | null }>()

const CX = 110
const CY = 110
const R = 90
const faixas = FAIXAS_MEDIDOR.map((f) => ({ ...f, d: arcoNps(f.de, f.ate, CX, CY, R) }))
const marcador = computed(() => pontoNoArco(props.valor, CX, CY, R))
const rotulo = computed(() => `NPS ${formatarNps(props.valor)} numa escala de −100 a 100${props.faixa ? `, faixa ${props.faixa}` : ''}`)
</script>

<template>
  <svg viewBox="0 0 220 130" class="block h-auto w-full max-w-60" role="img" :aria-label="rotulo" data-medidor>
    <path
      v-for="(f, i) in faixas"
      :key="f.de"
      :d="f.d"
      :class="f.cor"
      stroke-opacity="0.5"
      stroke-width="16"
      fill="none"
      :stroke-linecap="i === 1 ? 'butt' : 'round'"
    />
    <circle :cx="marcador.x" :cy="marcador.y" r="10" class="fill-superficie stroke-texto" stroke-width="4" data-marcador />
    <text :x="CX" y="98" text-anchor="middle" class="fill-texto text-[46px] font-extrabold tabular-nums" aria-hidden="true">{{ formatarNps(valor) }}</text>
    <text x="20" y="128" text-anchor="middle" class="fill-texto-fraco text-[10px]" aria-hidden="true">−100</text>
    <text x="200" y="128" text-anchor="middle" class="fill-texto-fraco text-[10px]" aria-hidden="true">100</text>
  </svg>
</template>
