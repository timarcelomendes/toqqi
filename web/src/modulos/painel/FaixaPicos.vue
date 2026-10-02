<script setup lang="ts">
// Picos de reclamação: um aviso por tema que passou do normal nos últimos 7 dias (3 ou mais reclamações e o dobro
// da média das 4 semanas antes), com o atalho para as respostas. Usado em Relatórios › Temas (no Início, desde o
// painel v2, o pico vira a manchete "O que mudou").
import { TrendingUp } from 'lucide-vue-next'
import type { Pico } from '@/api/tipos'
import Botao from '@/components/ui/Botao.vue'
import { consultaPico, partesPico } from './logica'

defineProps<{ picos: Pico[]; podeVerRespostas: boolean }>()
</script>

<template>
  <section v-if="picos.length" class="flex flex-col gap-2" aria-label="Picos de reclamações">
    <div
      v-for="p in picos"
      :key="p.tema"
      class="flex flex-col gap-3 rounded-cartao border border-atencao/30 bg-atencao-suave p-4 sm:flex-row sm:items-center"
      data-pico
    >
      <span class="flex size-9 shrink-0 items-center justify-center rounded-xl bg-superficie text-atencao" aria-hidden="true">
        <TrendingUp class="size-5" />
      </span>
      <p class="min-w-0 flex-1 text-sm text-texto">
        <strong class="font-semibold">{{ partesPico(p).titulo }}:</strong> {{ partesPico(p).detalhe }}.
      </p>
      <Botao v-if="podeVerRespostas" variante="secundario" tamanho="sm" class="!h-10 shrink-0 self-start sm:self-auto" :para="{ path: '/respostas', query: consultaPico(p) }">
        Ver respostas<span class="sr-only"> com reclamação de {{ p.rotulo }}</span>
      </Botao>
    </div>
  </section>
</template>
