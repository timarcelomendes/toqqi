<script setup lang="ts">
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { Gauge } from 'lucide-vue-next'
import type { GrupoNota, Painel } from '@/api/tipos'
import { plural } from '@/utils/formatos'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { faixaNps, formatarNps, tomNps } from './logica'

const props = defineProps<{
  nps: Painel['nps']
  periodo: string
  linkGrupo?: (g: GrupoNota) => RouteLocationRaw | undefined
}>()

const faixa = computed(() => faixaNps(props.nps.faixa, props.nps.valor))
const corValor = computed(
  () => ({ sucesso: 'text-sucesso', atencao: 'text-atencao', erro: 'text-erro' })[tomNps(props.nps.valor) as 'sucesso' | 'atencao' | 'erro'] ?? 'text-texto',
)
const decisores = computed(() => props.nps.decisores ?? { valor: null, total: 0 })
</script>

<template>
  <section class="cartao p-5 sm:p-6" aria-labelledby="t-cartao-nps">
    <div v-if="nps.total > 0" class="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:gap-10">
      <!-- O número -->
      <div class="flex flex-col gap-3">
        <header class="flex items-baseline justify-between gap-3 md:block">
          <h2 id="t-cartao-nps" class="text-base font-bold text-texto">NPS</h2>
          <p class="text-sm text-texto-fraco">{{ periodo }}</p>
        </header>
        <p class="text-7xl font-extrabold leading-none tracking-tight" :class="corValor">
          <span class="sr-only">NPS </span>{{ formatarNps(nps.valor) }}
        </p>
        <div class="flex flex-wrap items-center gap-2">
          <Etiqueta v-if="faixa" :tom="faixa.tom" ponto>{{ faixa.rotulo }}</Etiqueta>
          <span class="text-xs text-texto-fraco">numa escala de −100 a 100</span>
        </div>
      </div>

      <!-- Os grupos e os totais -->
      <div class="flex flex-col justify-center gap-5">
        <BarraGrupos
          :detratores="nps.detratores"
          :neutros="nps.neutros"
          :promotores="nps.promotores"
          :pct="nps.pct"
          :link-grupo="linkGrupo"
        />
        <div class="flex flex-col gap-1 border-t border-borda pt-4 text-sm text-texto-suave sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <p><strong class="font-semibold text-texto">{{ plural(nps.total, 'resposta', 'respostas') }}</strong> de NPS</p>
          <p v-if="decisores.total > 0">
            NPS dos decisores:
            <strong class="font-semibold text-texto">{{ formatarNps(decisores.valor) }}</strong>
            <span class="text-texto-fraco"> ({{ plural(decisores.total, 'resposta', 'respostas') }})</span>
          </p>
          <p v-else class="text-texto-fraco">Nenhum decisor respondeu no período.</p>
        </div>
      </div>
    </div>

    <template v-else>
      <header class="mb-4 flex items-baseline justify-between gap-3">
        <h2 id="t-cartao-nps" class="text-base font-bold text-texto">NPS</h2>
        <p class="text-sm text-texto-fraco">{{ periodo }}</p>
      </header>
      <div class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4">
        <Gauge class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
        <div class="text-sm">
          <p class="font-semibold text-texto">Nenhuma resposta de NPS neste período</p>
          <p class="text-texto-suave">Escolha um período maior ou envie a pesquisa para mais clientes. O número aparece assim que chegarem respostas.</p>
        </div>
      </div>
    </template>
  </section>
</template>
