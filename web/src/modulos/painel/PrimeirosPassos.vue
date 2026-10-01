<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, CheckCircle2, Circle, X } from 'lucide-vue-next'
import type { PassoInicial } from './logica'

const props = defineProps<{ passos: PassoInicial[] }>()
const emit = defineEmits<{ ocultar: [] }>()
const feitos = computed(() => props.passos.filter((p) => p.feito).length)
</script>

<template>
  <section class="cartao p-5 sm:p-6" aria-labelledby="t-passos">
    <div class="flex items-start justify-between gap-3">
      <div>
        <h2 id="t-passos" class="text-base font-bold text-texto">Primeiros passos</h2>
        <p class="text-sm text-texto-suave">{{ feitos }} de {{ passos.length }} feitos. Siga a ordem para ver o painel ganhar vida.</p>
      </div>
      <button
        type="button"
        class="-mr-2 -mt-1 inline-flex h-10 shrink-0 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto"
        @click="emit('ocultar')"
      >
        <X class="size-4" aria-hidden="true" /> Ocultar
      </button>
    </div>
    <div
      class="mt-3 h-2 overflow-hidden rounded-full bg-superficie-2"
      role="progressbar"
      :aria-valuenow="feitos"
      aria-valuemin="0"
      :aria-valuemax="passos.length"
      aria-label="Progresso dos primeiros passos"
    >
      <div class="h-full rounded-full bg-marca transition-all" :style="{ width: `${(feitos / Math.max(1, passos.length)) * 100}%` }" />
    </div>
    <ol class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <li
        v-for="(p, i) in passos"
        :key="p.chave"
        class="relative flex gap-3 rounded-xl border p-3.5"
        :class="p.feito ? 'border-borda bg-superficie-2/60' : p.para ? 'border-borda-forte hover:bg-superficie-2' : 'border-borda-forte'"
      >
        <CheckCircle2 v-if="p.feito" class="mt-0.5 size-5 shrink-0 text-sucesso" aria-hidden="true" />
        <Circle v-else class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
        <div class="min-w-0">
          <p class="text-sm font-semibold" :class="p.feito ? 'text-texto-fraco' : 'text-texto'">
            {{ i + 1 }}. {{ p.titulo }} <span class="sr-only">{{ p.feito ? '(feito)' : '(a fazer)' }}</span>
          </p>
          <p class="text-xs text-texto-suave">{{ p.descricao }}</p>
          <!-- O cartão todo é clicável (alvo grande no celular); a seta fica grudada na última palavra. -->
          <RouterLink v-if="!p.feito && p.para" :to="p.para" class="link mt-1.5 inline-block text-sm after:absolute after:inset-0 after:rounded-xl">
            {{ p.acao }}&nbsp;<ArrowRight class="inline size-3.5 align-[-0.15em]" aria-hidden="true" />
          </RouterLink>
        </div>
      </li>
    </ol>
  </section>
</template>
