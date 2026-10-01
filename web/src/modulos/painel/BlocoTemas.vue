<script setup lang="ts">
// Assuntos mais citados nos comentários de NPS: barra = quantas vezes aparece; ao lado, a nota média de quem citou.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Tags } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { formatarMedia1, tomNotaMedia } from './logica'

const props = defineProps<{ temas: Painel['temas']; consulta: Record<string, string>; podeVerRespostas: boolean }>()
const maior = computed(() => Math.max(1, ...props.temas.map((t) => t.mencoes)))
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-temas">
    <header>
      <h2 id="t-temas" class="text-base font-bold text-texto">Assuntos mais citados</h2>
      <p class="text-sm text-texto-suave">Do que falam os comentários de NPS e a nota média de quem falou.</p>
    </header>
    <ol v-if="temas.length" class="-mx-2 flex flex-col gap-1">
      <li v-for="t in temas" :key="t.chave">
        <component
          :is="podeVerRespostas ? RouterLink : 'div'"
          :to="podeVerRespostas ? { path: '/respostas', query: { ...consulta, tema: t.chave } } : undefined"
          class="flex flex-col gap-1.5 rounded-xl px-2 py-2"
          :class="podeVerRespostas ? 'group hover:bg-superficie-2' : ''"
        >
          <span class="flex items-center justify-between gap-3">
            <span class="min-w-0 truncate text-sm font-semibold text-texto group-hover:underline">{{ t.rotulo }}</span>
            <Etiqueta v-if="t.nota_media !== null && t.nota_media !== undefined" :tom="tomNotaMedia(t.nota_media)" class="shrink-0">
              nota média {{ formatarMedia1(t.nota_media) }}
            </Etiqueta>
          </span>
          <span class="flex items-center gap-2" aria-hidden="true">
            <span class="h-2 flex-1">
              <span class="block h-full rounded-r-[4px] bg-grafico-serie" :style="{ width: `${Math.max(2, (t.mencoes / maior) * 100)}%` }" />
            </span>
            <span class="w-10 shrink-0 text-right text-xs font-semibold tabular-nums text-texto-suave">{{ formatarNumero(t.mencoes) }}</span>
          </span>
          <span class="sr-only">{{ formatarNumero(t.mencoes) }} {{ t.mencoes === 1 ? 'menção' : 'menções' }}</span>
        </component>
      </li>
    </ol>
    <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
      <Tags class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
      <p class="text-texto-suave">Nenhum assunto encontrado nos comentários deste período.</p>
    </div>
  </section>
</template>
