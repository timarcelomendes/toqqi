<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ titulo: string; descricao?: string; icone?: Component; tom?: 'marca' | 'sucesso' | 'erro' }>()
</script>

<template>
  <div class="mb-6">
    <div
      v-if="icone"
      class="mb-4 flex size-12 items-center justify-center rounded-2xl"
      :class="{
        'bg-marca-suave text-marca-texto': !tom || tom === 'marca',
        'bg-sucesso-suave text-sucesso': tom === 'sucesso',
        'bg-erro-suave text-erro': tom === 'erro',
      }"
    >
      <component :is="icone" class="size-6" aria-hidden="true" />
    </div>
    <h1 class="text-2xl font-bold tracking-tight text-texto">{{ titulo }}</h1>
    <p v-if="descricao" class="mt-1.5 text-[0.95rem] leading-relaxed text-texto-suave">{{ descricao }}</p>
    <slot />
  </div>
</template>
