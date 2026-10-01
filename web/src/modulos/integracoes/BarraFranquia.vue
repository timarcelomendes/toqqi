<script setup lang="ts">
// Barra da franquia mensal do WhatsApp automático: verde, amarela a partir de 80% e vermelha quando acaba.
import { computed } from 'vue'
import type { FranquiaWhatsapp } from '@/api/tipos'
import { estadoFranquia } from './logica'

const props = defineProps<{ franquia: FranquiaWhatsapp }>()
const e = computed(() => estadoFranquia(props.franquia))
const cor = computed(() => ({ ok: 'bg-sucesso', atencao: 'bg-atencao', esgotada: 'bg-erro' })[e.value.nivel])
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-baseline justify-between gap-2 text-sm">
      <span class="font-semibold text-texto">{{ e.resumo }}</span>
      <span class="tabular-nums" :class="e.nivel === 'ok' ? 'text-texto-fraco' : e.nivel === 'atencao' ? 'font-semibold text-atencao' : 'font-semibold text-erro'">
        {{ e.percentual }}%
      </span>
    </div>
    <div
      class="h-2.5 w-full overflow-hidden rounded-full bg-superficie-2"
      role="progressbar"
      :aria-valuenow="e.usadas"
      aria-valuemin="0"
      :aria-valuemax="e.limite"
      :aria-valuetext="`${e.resumo} (${e.percentual}%)`"
      aria-label="Franquia de WhatsApp usada no mês"
    >
      <div class="h-full rounded-full transition-[width] duration-500" :class="cor" :style="{ width: `${e.percentual}%` }" />
    </div>
  </div>
</template>
