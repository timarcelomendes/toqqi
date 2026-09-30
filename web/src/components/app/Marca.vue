<script setup lang="ts">
import logo from '@/assets/logo.svg'

withDefaults(defineProps<{ tamanho?: 'sm' | 'md' | 'lg' }>(), { tamanho: 'md' })
</script>

<template>
  <span class="inline-flex items-center gap-2" aria-label="toqqi">
    <img
      :src="logo"
      alt=""
      aria-hidden="true"
      :class="{ sm: 'size-7', md: 'size-9', lg: 'size-11' }[tamanho]"
    />
    <span
      aria-hidden="true"
      class="font-extrabold lowercase tracking-[-0.04em] text-texto"
      :class="{ sm: 'text-xl', md: 'text-2xl', lg: 'text-3xl' }[tamanho]"
    >toqqi</span>
  </span>
</template>
