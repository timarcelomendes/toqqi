<script setup lang="ts">
import { useId } from 'vue'

defineProps<{ titulo: string; descricao?: string }>()
const id = `secao-${useId()}`
</script>

<template>
  <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" :aria-labelledby="id">
    <div>
      <h2 :id="id" class="text-base font-bold text-texto">{{ titulo }}</h2>
      <p v-if="descricao" class="mt-1 text-sm text-texto-suave">{{ descricao }}</p>
      <slot name="lateral" />
    </div>
    <div class="md:col-span-2">
      <slot />
    </div>
  </section>
</template>
