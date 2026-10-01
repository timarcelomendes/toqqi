<script setup lang="ts">
// Texto pronto para copiar (comando, endereço, modelo de mensagem).
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'

withDefaults(defineProps<{ texto: string; rotulo?: string; quebrar?: boolean }>(), { rotulo: 'Copiar' })
</script>

<template>
  <div class="relative min-w-0 rounded-xl border border-borda bg-superficie-2">
    <div class="flex items-center justify-between gap-2 border-b border-borda px-3 py-1.5">
      <span class="truncate text-xs font-semibold text-texto-fraco"><slot name="titulo" /></span>
      <BotaoCopiar :texto="texto" :rotulo="rotulo" variante="fantasma" tamanho="sm" />
    </div>
    <pre
      class="overflow-x-auto px-3.5 py-3 font-mono text-[0.8rem] leading-relaxed text-texto"
      :class="quebrar ? 'whitespace-pre-wrap break-words' : ''"
    ><code>{{ texto }}</code></pre>
  </div>
</template>
