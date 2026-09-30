<script setup lang="ts">
import { Moon, Sun } from 'lucide-vue-next'
import { useTema } from '@/composables/tema'

const { tema, alternar } = useTema()
</script>

<template>
  <button
    type="button"
    class="flex size-10 items-center justify-center rounded-xl text-texto-suave transition-colors hover:bg-superficie-2 hover:text-texto"
    :aria-label="tema === 'escuro' ? 'Usar tema claro' : 'Usar tema escuro'"
    :title="tema === 'escuro' ? 'Usar tema claro' : 'Usar tema escuro'"
    @click="alternar"
  >
    <Sun v-if="tema === 'escuro'" class="size-5" aria-hidden="true" />
    <Moon v-else class="size-5" aria-hidden="true" />
  </button>
</template>
