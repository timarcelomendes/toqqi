<script setup lang="ts">
import type { Tom } from '@/utils/rotulos'

withDefaults(defineProps<{ tom?: Tom; ponto?: boolean }>(), { tom: 'neutro' })

const cores: Record<Tom, string> = {
  neutro: 'bg-superficie-2 text-texto-suave ring-borda-forte/60',
  marca: 'bg-marca-suave text-marca-texto ring-marca/25',
  sucesso: 'bg-sucesso-suave text-sucesso ring-sucesso/25',
  atencao: 'bg-atencao-suave text-atencao ring-atencao/25',
  erro: 'bg-erro-suave text-erro ring-erro/25',
  info: 'bg-info-suave text-info ring-info/25',
}
</script>

<template>
  <span class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset" :class="cores[tom]">
    <span v-if="ponto" class="size-1.5 rounded-full bg-current" aria-hidden="true" />
    <slot />
  </span>
</template>
