<script setup lang="ts">
// Palavras que mais aparecem, como nuvem: o tamanho segue a contagem (4 níveis). A cor só fala do tom quando a API
// manda o tom da palavra (negativo em `marca-texto`, positivo em `sucesso`); sem ele, segue o tamanho. A contagem fica
// escrita para leitor de tela e na dica; com respostas.ver, cada palavra abre as respostas que a citam.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Type } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { nuvemPalavras } from './logica'

const props = defineProps<{ palavras: Painel['palavras']; consulta: Record<string, string>; podeVerRespostas: boolean }>()
const nuvem = computed(() => nuvemPalavras(props.palavras))
const comTom = computed(() => (props.palavras ?? []).some((p) => p.tom === 'negativo' || p.tom === 'positivo'))
const TAMANHO = { 4: 'text-3xl font-extrabold', 3: 'text-2xl font-bold', 2: 'text-lg font-bold', 1: 'text-sm font-semibold' } as const
</script>

<template>
  <section class="cartao flex flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-palavras">
    <header>
      <h2 id="t-palavras" class="text-base font-bold text-texto">Palavras que mais aparecem</h2>
      <p class="text-sm text-texto-suave">
        Maior = em mais comentários.<template v-if="comTom"> Em coral, as de comentários negativos; em verde, as de positivos.</template>
      </p>
    </header>
    <ul v-if="nuvem.length" class="flex flex-wrap items-baseline gap-x-3 gap-y-1 leading-tight" data-nuvem>
      <li v-for="p in nuvem" :key="p.palavra">
        <component
          :is="podeVerRespostas ? RouterLink : 'span'"
          :to="podeVerRespostas ? { path: '/respostas', query: { ...consulta, busca: p.palavra } } : undefined"
          class="inline-flex min-h-11 items-center rounded-lg px-0.5 sm:min-h-9"
          :class="[TAMANHO[p.nivel], p.cor, podeVerRespostas ? 'hover:underline' : '']"
          :title="`${p.total} ${p.total === 1 ? 'comentário' : 'comentários'}`"
          :data-nivel="p.nivel"
        >
          {{ p.palavra }}<span class="sr-only">: {{ p.total }} {{ p.total === 1 ? 'comentário' : 'comentários' }}</span>
        </component>
      </li>
    </ul>
    <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
      <Type class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
      <p class="text-texto-suave">Ainda não há comentários suficientes neste período.</p>
    </div>
  </section>
</template>
