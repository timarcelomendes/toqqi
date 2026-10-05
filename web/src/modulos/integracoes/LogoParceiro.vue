<script setup lang="ts">
// Logo de um sistema parceiro (RD Station CRM, Omie): o arquivo oficial em /parceiros/<chave>.svg, colocado a partir
// do kit de marca do parceiro (public/parceiros/LEIA-ME.txt). Sem o arquivo, um quadrado neutro com as iniciais.
import { ref } from 'vue'

defineProps<{ chave: string; nome: string; iniciais: string }>()
const falhou = ref(false)
</script>

<template>
  <span class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-borda bg-white">
    <img v-if="!falhou" :src="`/parceiros/${chave}.svg`" :alt="`Logo do ${nome}`" class="size-8 object-contain" @error="falhou = true" />
    <span v-else class="text-sm font-extrabold text-slate-700" aria-hidden="true">{{ iniciais }}</span>
  </span>
</template>
