<script setup lang="ts">
// Prioridade da ação em três botões (rádios): Alta, Média, Baixa.
import { useId } from 'vue'
import type { PrioridadeAcao } from '@/api/tipos'
import { PRIORIDADES } from './logica'

withDefaults(defineProps<{ rotulo?: string; erro?: string | null; desabilitado?: boolean }>(), { rotulo: 'Prioridade', erro: null })
const modelo = defineModel<PrioridadeAcao>({ required: true })
const id = `prioridade-${useId()}`
const ordem: PrioridadeAcao[] = ['alta', 'media', 'baixa']
const COR: Record<PrioridadeAcao, string> = {
  alta: 'border-erro bg-erro-suave text-erro',
  media: 'border-atencao bg-atencao-suave text-atencao',
  baixa: 'border-borda-forte bg-superficie-2 text-texto',
}
</script>

<template>
  <fieldset class="flex min-w-0 flex-col gap-1.5" :disabled="desabilitado" :aria-describedby="erro ? `${id}-erro` : undefined">
    <legend class="mb-1.5 text-sm font-semibold text-texto">{{ rotulo }}</legend>
    <div class="grid grid-cols-3 gap-1.5">
      <label
        v-for="p in ordem"
        :key="p"
        class="flex h-11 cursor-pointer items-center justify-center rounded-xl border text-sm font-semibold transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
        :class="[modelo === p ? COR[p] : 'border-borda-forte bg-superficie text-texto-suave hover:bg-superficie-2', desabilitado ? 'cursor-not-allowed opacity-60' : '']"
      >
        <input v-model="modelo" type="radio" :name="id" :value="p" class="sr-only" />
        {{ PRIORIDADES[p].rotulo }}
      </label>
    </div>
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
  </fieldset>
</template>
