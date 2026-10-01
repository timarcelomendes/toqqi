<script setup lang="ts">
// A nota da resposta num quadradinho com a cor da categoria (e o nome dela para quem usa leitor de tela).
import { computed } from 'vue'
import type { GrupoNota, TipoNota } from '@/api/tipos'
import { rotuloCategoria, tomCategoria } from './logica'

const props = withDefaults(
  defineProps<{ nota: number | null | undefined; grupo?: GrupoNota | string | null; tipo?: TipoNota | null; tamanho?: 'sm' | 'md' | 'lg' }>(),
  { grupo: null, tipo: null, tamanho: 'md' },
)

const COR = {
  sucesso: 'bg-sucesso-suave text-sucesso ring-sucesso/25',
  atencao: 'bg-atencao-suave text-atencao ring-atencao/25',
  erro: 'bg-erro-suave text-erro ring-erro/25',
} as const
const cor = computed(() =>
  typeof props.nota === 'number' ? (COR[tomCategoria(props.grupo, props.nota, props.tipo) as keyof typeof COR] ?? 'bg-superficie-2 text-texto-suave ring-borda') : 'bg-superficie-2 text-texto-fraco ring-borda',
)
const tamanhos = { sm: 'size-8 text-sm', md: 'size-10 text-base', lg: 'size-14 text-2xl' }
const descricao = computed(() => {
  if (typeof props.nota !== 'number') return 'Sem nota'
  const escala = props.tipo === 'csat' ? ' de 5' : props.tipo === 'nps' ? ' de 10' : ''
  return `Nota ${props.nota}${escala}${props.grupo ? `, ${rotuloCategoria(props.grupo).toLowerCase()}` : ''}`
})
</script>

<template>
  <span class="inline-flex shrink-0 items-center justify-center rounded-xl font-extrabold ring-1 ring-inset" :class="[cor, tamanhos[tamanho]]" :title="descricao">
    <span aria-hidden="true">{{ typeof nota === 'number' ? nota : '—' }}</span>
    <span class="sr-only">{{ descricao }}</span>
  </span>
</template>
