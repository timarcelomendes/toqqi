<script setup lang="ts">
// Escolha da nota (0 a 10 no NPS, 1 a 5 no CSAT): botões grandes, com a cor da categoria na nota escolhida.
// São rádios de verdade: setas do teclado trocam a nota, e o leitor de tela anuncia o grupo.
import { computed, useId } from 'vue'
import type { TipoNota } from '@/api/tipos'
import { CATEGORIAS, categoriaDaNota, notasDaCategoria } from './logica'

const props = withDefaults(
  defineProps<{ rotulo: string; tipo?: TipoNota; erro?: string | null; dica?: string; desabilitado?: boolean }>(),
  { tipo: 'nps', erro: null, dica: undefined },
)
const modelo = defineModel<number | null>({ default: null })
const id = `nota-${useId()}`

const notas = computed(() => (props.tipo === 'csat' ? [1, 2, 3, 4, 5] : [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
const grupoEscolhido = computed(() => (modelo.value === null ? null : categoriaDaNota(props.tipo, modelo.value)))

const COR = {
  erro: 'border-erro bg-erro-suave text-erro ring-2 ring-erro/30',
  atencao: 'border-atencao bg-atencao-suave text-atencao ring-2 ring-atencao/30',
  sucesso: 'border-sucesso bg-sucesso-suave text-sucesso ring-2 ring-sucesso/30',
} as const
function classe(n: number) {
  if (modelo.value !== n) return 'border-borda-forte bg-superficie text-texto hover:bg-superficie-2'
  const g = categoriaDaNota(props.tipo, n)
  return COR[CATEGORIAS[g].tom as keyof typeof COR]
}
</script>

<template>
  <fieldset class="flex min-w-0 flex-col gap-1.5" :aria-describedby="[erro ? `${id}-erro` : '', dica ? `${id}-dica` : ''].join(' ').trim() || undefined" :disabled="desabilitado">
    <legend class="mb-1.5 text-sm font-semibold text-texto">{{ rotulo }}</legend>
    <div class="grid gap-1.5" :class="tipo === 'csat' ? 'grid-cols-5' : 'grid-cols-6 sm:grid-cols-11'">
      <label
        v-for="n in notas"
        :key="n"
        class="relative flex h-11 cursor-pointer items-center justify-center rounded-xl border text-base font-bold transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
        :class="[classe(n), desabilitado ? 'cursor-not-allowed opacity-60' : '']"
      >
        <input v-model="modelo" type="radio" :name="id" :value="n" class="sr-only" :aria-invalid="erro ? 'true' : undefined" />
        {{ n }}
        <span class="sr-only">({{ CATEGORIAS[categoriaDaNota(tipo, n)].rotulo.toLowerCase() }})</span>
      </label>
    </div>
    <div class="flex justify-between text-xs text-texto-fraco" aria-hidden="true">
      <span>{{ tipo === 'csat' ? 'Muito insatisfeito' : 'Nada provável' }}</span>
      <span>{{ tipo === 'csat' ? 'Muito satisfeito' : 'Muito provável' }}</span>
    </div>
    <p v-if="grupoEscolhido" class="text-sm text-texto-suave" aria-live="polite">
      Nota {{ modelo }}: <strong class="font-semibold text-texto">{{ CATEGORIAS[grupoEscolhido].rotulo.toLowerCase() }}</strong
      ><span class="text-texto-fraco"> ({{ notasDaCategoria(tipo, grupoEscolhido) }})</span>
    </p>
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
  </fieldset>
</template>
