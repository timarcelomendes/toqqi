<script setup lang="ts">
defineProps<{ titulo: string; descricao?: string }>()
</script>

<template>
  <!-- O texto não encolhe abaixo de 18rem: com muitos botões (Respostas em 1024 px), eles descem para a linha de baixo -->
  <header class="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
    <div class="min-w-0 sm:flex-[1_1_18rem]">
      <h1 class="titulo-pagina">{{ titulo }}</h1>
      <p v-if="descricao" class="mt-1.5 max-w-2xl text-[0.95rem] text-texto-suave">{{ descricao }}</p>
    </div>
    <div v-if="$slots.acoes" class="flex shrink-0 flex-wrap gap-2">
      <slot name="acoes" />
    </div>
  </header>
</template>
