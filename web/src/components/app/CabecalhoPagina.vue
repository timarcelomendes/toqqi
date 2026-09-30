<script setup lang="ts">
defineProps<{ titulo: string; descricao?: string }>()
</script>

<template>
  <header class="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
    <div class="min-w-0">
      <h1 class="titulo-pagina">{{ titulo }}</h1>
      <p v-if="descricao" class="mt-1.5 max-w-2xl text-[0.95rem] text-texto-suave">{{ descricao }}</p>
    </div>
    <div v-if="$slots.acoes" class="flex shrink-0 flex-wrap gap-2">
      <slot name="acoes" />
    </div>
  </header>
</template>
