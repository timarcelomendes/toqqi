<script setup lang="ts">
import type { Component } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

defineProps<{ para?: RouteLocationRaw; icone?: Component; perigo?: boolean }>()
defineEmits<{ click: [] }>()
const classe =
  'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm font-medium outline-none hover:bg-superficie-2 focus-visible:bg-superficie-2'
</script>

<template>
  <RouterLink v-if="para" :to="para" role="menuitem" tabindex="-1" :class="[classe, 'text-texto']">
    <component :is="icone" v-if="icone" class="size-4 text-texto-fraco" aria-hidden="true" />
    <slot />
  </RouterLink>
  <button v-else type="button" role="menuitem" tabindex="-1" :class="[classe, perigo ? 'text-erro' : 'text-texto']" @click="$emit('click')">
    <component :is="icone" v-if="icone" class="size-4" :class="perigo ? '' : 'text-texto-fraco'" aria-hidden="true" />
    <slot />
  </button>
</template>
