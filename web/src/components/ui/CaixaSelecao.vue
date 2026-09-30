<script setup lang="ts">
import { useId } from 'vue'
import { Check } from 'lucide-vue-next'

defineProps<{
  rotulo: string
  descricao?: string
  desabilitado?: boolean
  rotuloOculto?: boolean
}>()
const modelo = defineModel<boolean>({ default: false })
const id = `caixa-${useId()}`
</script>

<template>
  <div class="flex items-start gap-3">
    <span class="relative mt-0.5 flex size-5 shrink-0">
      <input
        :id="id"
        v-model="modelo"
        type="checkbox"
        :disabled="desabilitado"
        :aria-describedby="descricao ? `${id}-desc` : undefined"
        class="peer size-5 cursor-pointer appearance-none rounded-md border-2 border-borda-forte bg-superficie transition-colors checked:border-marca-forte checked:bg-marca-forte focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco disabled:cursor-not-allowed disabled:opacity-50"
      />
      <Check
        class="pointer-events-none absolute inset-0 m-auto size-3.5 text-white opacity-0 peer-checked:opacity-100"
        :stroke-width="3.5"
        aria-hidden="true"
      />
    </span>
    <div class="min-w-0" :class="{ 'sr-only': rotuloOculto }">
      <label :for="id" class="cursor-pointer text-sm font-medium text-texto" :class="{ 'cursor-not-allowed opacity-70': desabilitado }">
        <slot>{{ rotulo }}</slot>
      </label>
      <p v-if="descricao" :id="`${id}-desc`" class="text-sm text-texto-fraco">{{ descricao }}</p>
    </div>
  </div>
</template>
