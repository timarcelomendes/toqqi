<script setup lang="ts">
import logo from '@/assets/logo.svg'

withDefaults(defineProps<{ tamanho?: 'sm' | 'md' | 'lg' }>(), { tamanho: 'md' })
</script>

<template>
  <span class="inline-flex items-center gap-2" role="img" aria-label="toqqi">
    <img
      :src="logo"
      alt=""
      aria-hidden="true"
      :class="{ sm: 'size-7', md: 'size-9', lg: 'size-11' }[tamanho]"
    />
    <span
      aria-hidden="true"
      class="whitespace-nowrap pb-[0.2em] font-extrabold lowercase leading-none tracking-[-0.04em] text-texto"
      :class="{ sm: 'text-xl', md: 'text-2xl', lg: 'text-3xl' }[tamanho]"
      >to<svg
        class="inline-block text-marca"
        style="width: 1.175em; height: 1.125em; vertical-align: -0.579em; margin: 0 0.03em 0 0.05em"
        viewBox="0 0 142 136"
        fill="none"
        stroke="currentColor"
        focusable="false"
      >
        <circle cx="33" cy="33" r="24.5" stroke-width="18" />
        <path d="M57.5 33 V92" stroke-width="18" />
        <circle cx="109" cy="33" r="24.5" stroke-width="18" />
        <path d="M133.5 33 V92" stroke-width="18" />
        <path d="M18 112 Q70 140 122 112" stroke-width="15" stroke-linecap="round" /></svg
      >i</span
    >
  </span>
</template>
