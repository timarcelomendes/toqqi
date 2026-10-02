<script setup lang="ts">
// Primeiros passos em uma linha: 4 marcadores de progresso, "Primeiros passos: X de 4.", o próximo passo e o atalho
// (só se o perfil puder abrir). "Ocultar" esconde neste navegador.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowRight, X } from 'lucide-vue-next'
import type { PassoInicial } from './logica'

const props = defineProps<{ passos: PassoInicial[] }>()
const emit = defineEmits<{ ocultar: [] }>()
const feitos = computed(() => props.passos.filter((p) => p.feito).length)
const proximo = computed(() => props.passos.find((p) => !p.feito) ?? null)
</script>

<template>
  <section class="cartao flex flex-col gap-3 px-5 py-3.5 sm:flex-row sm:items-center sm:gap-4" aria-labelledby="t-passos">
    <h2 id="t-passos" class="sr-only">Primeiros passos</h2>
    <ol class="flex shrink-0 gap-1.5" aria-label="Progresso dos primeiros passos">
      <li v-for="(p, i) in passos" :key="p.chave" class="h-1.5 w-7 rounded-full" :class="p.feito ? 'bg-marca' : 'bg-borda'">
        <span class="sr-only">{{ i + 1 }}. {{ p.titulo }}: {{ p.feito ? 'feito' : 'a fazer' }}</span>
      </li>
    </ol>
    <p class="min-w-0 flex-1 text-sm text-texto-suave">
      <strong class="font-bold text-texto">Primeiros passos: {{ feitos }} de {{ passos.length }}.</strong>
      <template v-if="proximo"> Próximo: {{ proximo.proximo }}</template>
    </p>
    <div class="flex shrink-0 items-center gap-1">
      <RouterLink v-if="proximo?.para" :to="proximo.para" class="link inline-flex min-h-11 items-center gap-1 px-1 text-sm" data-proximo-passo>
        {{ proximo.acao }} <ArrowRight class="size-4" aria-hidden="true" />
      </RouterLink>
      <button
        type="button"
        class="ml-auto inline-flex min-h-11 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto sm:ml-0"
        @click="emit('ocultar')"
      >
        <X class="size-4" aria-hidden="true" /> Ocultar
      </button>
    </div>
  </section>
</template>
