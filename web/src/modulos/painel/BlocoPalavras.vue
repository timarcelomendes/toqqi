<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Type } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'

defineProps<{ palavras: Painel['palavras']; consulta: Record<string, string>; podeVerRespostas: boolean }>()
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-palavras">
    <header>
      <h2 id="t-palavras" class="text-base font-bold text-texto">Palavras mais citadas</h2>
      <p class="text-sm text-texto-suave">As que mais aparecem nos comentários, contando uma vez por resposta.</p>
    </header>
    <ul v-if="palavras.length" class="flex flex-wrap gap-2">
      <li v-for="p in palavras" :key="p.palavra">
        <component
          :is="podeVerRespostas ? RouterLink : 'span'"
          :to="podeVerRespostas ? { path: '/respostas', query: { ...consulta, busca: p.palavra } } : undefined"
          class="inline-flex min-h-10 items-center gap-2 rounded-xl border border-borda bg-superficie px-3 text-sm"
          :class="podeVerRespostas ? 'hover:border-borda-forte hover:bg-superficie-2' : ''"
        >
          <span class="font-semibold text-texto">{{ p.palavra }}</span>
          <span class="rounded-md bg-superficie-2 px-1.5 text-xs font-semibold tabular-nums text-texto-suave">
            {{ formatarNumero(p.total) }}<span class="sr-only"> {{ p.total === 1 ? 'resposta' : 'respostas' }}</span>
          </span>
        </component>
      </li>
    </ul>
    <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
      <Type class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
      <p class="text-texto-suave">Ainda não há comentários suficientes neste período.</p>
    </div>
  </section>
</template>
