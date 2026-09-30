<script setup lang="ts">
import { useId } from 'vue'

defineProps<{
  rotulo: string
  descricao?: string
  desabilitado?: boolean
  rotuloOculto?: boolean
}>()
const modelo = defineModel<boolean>({ default: false })
const id = `interruptor-${useId()}`
</script>

<template>
  <div class="flex items-start justify-between gap-4">
    <div class="min-w-0" :class="{ 'sr-only': rotuloOculto }">
      <label :id="`${id}-rotulo`" :for="id" class="cursor-pointer text-sm font-semibold text-texto">{{ rotulo }}</label>
      <p v-if="descricao" :id="`${id}-desc`" class="text-sm text-texto-fraco">{{ descricao }}</p>
    </div>
    <button
      :id="id"
      type="button"
      role="switch"
      :aria-checked="modelo"
      :aria-labelledby="`${id}-rotulo`"
      :aria-describedby="descricao ? `${id}-desc` : undefined"
      :disabled="desabilitado"
      class="relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco disabled:cursor-not-allowed disabled:opacity-55"
      :class="modelo ? 'bg-marca-forte' : 'bg-borda-forte'"
      @click="modelo = !modelo"
    >
      <span class="inline-block size-5 rounded-full bg-white shadow transition-transform" :class="modelo ? 'translate-x-6' : 'translate-x-1'" aria-hidden="true" />
    </button>
  </div>
</template>
