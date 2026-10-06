<script setup lang="ts">
// <select> compacto do construtor de lógica (o mesmo visual da Selecao, mais baixo e sem rótulo visível).
import { ChevronDown } from 'lucide-vue-next'

defineOptions({ inheritAttrs: false })
defineProps<{ rotulo: string; valor: string | number | null | undefined; desabilitado?: boolean }>()
const emit = defineEmits<{ escolher: [valor: string] }>()
</script>

<template>
  <div class="relative h-10 min-w-0" :class="$attrs.class">
    <select
      v-bind="{ ...$attrs, class: undefined }"
      :value="valor ?? ''"
      :aria-label="rotulo"
      :disabled="desabilitado"
      class="h-10 w-full min-w-0 appearance-none rounded-lg border border-borda-forte bg-superficie pl-3 pr-8 text-sm text-texto focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20 disabled:cursor-not-allowed disabled:opacity-60"
      @change="emit('escolher', ($event.target as HTMLSelectElement).value)"
    >
      <slot />
    </select>
    <ChevronDown class="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-texto-fraco" aria-hidden="true" />
  </div>
</template>
