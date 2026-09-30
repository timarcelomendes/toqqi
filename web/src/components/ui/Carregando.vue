<script setup lang="ts">
withDefaults(defineProps<{ linhas?: number; rotulo?: string }>(), { linhas: 3, rotulo: 'Carregando…' })
</script>

<template>
  <div role="status" :aria-label="rotulo" class="flex flex-col gap-3">
    <div v-for="i in linhas" :key="i" class="flex items-center gap-3">
      <div class="size-9 shrink-0 animate-pulse rounded-full bg-superficie-2" />
      <div class="flex flex-1 flex-col gap-2">
        <div class="h-3 animate-pulse rounded bg-superficie-2" :style="{ width: `${70 - ((i * 17) % 35)}%` }" />
        <div class="h-3 w-1/3 animate-pulse rounded bg-superficie-2" />
      </div>
    </div>
    <span class="sr-only">{{ rotulo }}</span>
  </div>
</template>
