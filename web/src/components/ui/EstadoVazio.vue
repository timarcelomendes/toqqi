<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ titulo: string; descricao?: string; icone?: Component }>()
</script>

<template>
  <div class="flex flex-col items-center px-6 py-12 text-center">
    <div v-if="icone" class="mb-4 flex size-14 items-center justify-center rounded-2xl bg-marca-suave text-marca-texto">
      <component :is="icone" class="size-7" aria-hidden="true" />
    </div>
    <h3 class="text-base font-bold text-texto">{{ titulo }}</h3>
    <p v-if="descricao" class="mt-1 max-w-md text-sm text-texto-suave">{{ descricao }}</p>
    <div v-if="$slots.default" class="mt-5"><slot /></div>
  </div>
</template>
