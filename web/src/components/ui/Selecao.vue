<script setup lang="ts" generic="T extends string | number">
import { computed, useId } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

const props = defineProps<{
  rotulo: string
  opcoes: { valor: T; rotulo: string }[]
  erro?: string | null
  dica?: string
  desabilitado?: boolean
  rotuloOculto?: boolean
  /** Texto de uma opção vazia inicial (ex.: "Todas"). */
  vazio?: string
}>()

const modelo = defineModel<T | ''>({ required: true })
const id = `selecao-${useId()}`
const descritoPor = computed(() => [props.erro ? `${id}-erro` : null, props.dica ? `${id}-dica` : null].filter(Boolean).join(' ') || undefined)
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label :for="id" class="text-sm font-semibold text-texto" :class="{ 'sr-only': rotuloOculto }">{{ rotulo }}</label>
    <div class="relative">
      <select
        :id="id"
        v-model="modelo"
        :disabled="desabilitado"
        :aria-invalid="erro ? 'true' : undefined"
        :aria-describedby="descritoPor"
        class="h-11 w-full appearance-none rounded-xl border bg-superficie pl-3.5 pr-10 text-[0.95rem] text-texto transition-colors focus:outline-none focus:ring-3 disabled:cursor-not-allowed disabled:bg-superficie-2"
        :class="erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20'"
      >
        <option v-if="vazio !== undefined" value="">{{ vazio }}</option>
        <option v-for="o in opcoes" :key="String(o.valor)" :value="o.valor">{{ o.rotulo }}</option>
      </select>
      <ChevronDown class="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-texto-fraco" aria-hidden="true" />
    </div>
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
  </div>
</template>
