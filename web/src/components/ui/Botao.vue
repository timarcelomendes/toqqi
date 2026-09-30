<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import { LoaderCircle } from 'lucide-vue-next'

type Variante = 'primario' | 'secundario' | 'fantasma' | 'perigo' | 'perigo-suave'
type Tamanho = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variante?: Variante
    tamanho?: Tamanho
    tipo?: 'button' | 'submit' | 'reset'
    carregando?: boolean
    desabilitado?: boolean
    bloco?: boolean
    /** Se informado, vira um link do router. */
    para?: RouteLocationRaw
    /** Botão só com ícone: informe o texto para leitores de tela. */
    somenteIcone?: string
  }>(),
  { variante: 'primario', tamanho: 'md', tipo: 'button' },
)

const classes = computed(() => {
  const base =
    'relative inline-flex items-center justify-center gap-2 font-semibold whitespace-nowrap rounded-xl transition-colors duration-150 select-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco disabled:cursor-not-allowed disabled:opacity-55 aria-disabled:cursor-not-allowed aria-disabled:opacity-55'
  const tamanhos: Record<Tamanho, string> = props.somenteIcone
    ? { sm: 'size-8', md: 'size-10', lg: 'size-12' }
    : { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4 text-sm', lg: 'h-12 px-6 text-base' }
  const variantes: Record<Variante, string> = {
    primario: 'bg-marca-forte text-white hover:bg-marca-hover shadow-sm',
    secundario: 'bg-superficie text-texto border border-borda-forte hover:bg-superficie-2',
    fantasma: 'text-texto-suave hover:bg-superficie-2 hover:text-texto',
    perigo: 'bg-red-700 text-white hover:bg-red-800 shadow-sm',
    'perigo-suave': 'text-erro hover:bg-erro-suave',
  }
  return [base, tamanhos[props.tamanho], variantes[props.variante], props.bloco ? 'w-full' : '']
})

const inativo = computed(() => props.desabilitado || props.carregando)
</script>

<template>
  <RouterLink v-if="para && !inativo" :to="para" :class="classes" :aria-label="somenteIcone">
    <slot />
  </RouterLink>
  <button
    v-else
    :type="tipo"
    :class="classes"
    :disabled="inativo"
    :aria-busy="carregando || undefined"
    :aria-label="somenteIcone"
    :title="somenteIcone"
  >
    <LoaderCircle v-if="carregando" class="size-4 animate-spin" aria-hidden="true" />
    <slot />
  </button>
</template>
