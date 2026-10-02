<script setup lang="ts">
// Ícone do ToqqiAI (o assistente de IA do Toqqi): o símbolo da marca, os dois "q" como olhos (hastes retas) e o sorriso
// solto abaixo, com a geometria de design-system/marca/toqqi-simbolo.svg (design-system/README.md §1, "ToqqiAI").
// - `simbolo` (padrão): só o traço, em currentColor, para usar como ícone de linha no lugar de um lucide (size-4, size-5).
//   O traço é um pouco mais grosso que o do arquivo oficial (22/19 em vez de 20/17) para continuar legível a 16 px; o
//   viewBox enquadra só o símbolo, com a metade do traço de folga, sem cortar nem distorcer.
// - `selo`: o ícone do app (quadrado arredondado coral #FF5A36 com o símbolo branco), igual a toqqi-icone.svg.
// Decorativo por padrão (aria-hidden); com `rotulo`, vira role="img" com esse nome.
import { computed } from 'vue'

const props = withDefaults(defineProps<{ variante?: 'simbolo' | 'selo'; rotulo?: string }>(), { variante: 'simbolo', rotulo: '' })

const acessivel = computed(() =>
  props.rotulo ? { role: 'img', 'aria-label': props.rotulo } : { 'aria-hidden': 'true' as const },
)
</script>

<template>
  <svg
    v-if="variante === 'selo'"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 48 48"
    fill="none"
    focusable="false"
    class="shrink-0"
    v-bind="acessivel"
    data-icone-toqqiai="selo"
  >
    <rect width="48" height="48" rx="11" fill="#FF5A36" />
    <g transform="translate(9.1 9.7) scale(0.21)" stroke="#FFFFFF" fill="none">
      <circle cx="33" cy="33" r="24.5" stroke-width="20" />
      <path d="M57.5 33 V92" stroke-width="20" />
      <circle cx="109" cy="33" r="24.5" stroke-width="20" />
      <path d="M133.5 33 V92" stroke-width="20" />
      <path d="M18 112 Q70 140 122 112" stroke-width="17" stroke-linecap="round" />
    </g>
  </svg>
  <svg
    v-else
    xmlns="http://www.w3.org/2000/svg"
    viewBox="-2.5 -2.5 147 138"
    fill="none"
    stroke="currentColor"
    focusable="false"
    class="shrink-0"
    v-bind="acessivel"
    data-icone-toqqiai="simbolo"
  >
    <circle cx="33" cy="33" r="24.5" stroke-width="22" />
    <path d="M57.5 33 V92" stroke-width="22" />
    <circle cx="109" cy="33" r="24.5" stroke-width="22" />
    <path d="M133.5 33 V92" stroke-width="22" />
    <path d="M18 112 Q70 140 122 112" stroke-width="19" stroke-linecap="round" />
  </svg>
</template>
