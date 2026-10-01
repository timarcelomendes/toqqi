<script setup lang="ts">
// NPS por recorte (segmento, grupo de empresas, tempo como cliente, valor do contrato): uma linha por item com o nome,
// o NPS (número e faixa), a barra empilhada detratores → neutros → promotores e o total. Os números de cada grupo da
// nota estão na dica da barra, no texto para leitor de tela e na tabela (alternar com "Ver em tabela").
import type { NpsResumo } from '@/api/tipos'
import { formatarNumero, plural } from '@/utils/formatos'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import { formatarNps } from '@/modulos/painel/logica'
import SeloNps from './SeloNps.vue'

export interface LinhaNps {
  chave: string
  rotulo: string
  empresas: number
  nps: NpsResumo
}

withDefaults(defineProps<{ linhas: LinhaNps[]; emTabela?: boolean; titulo: string; /** Nome da primeira coluna da tabela (ex.: "Segmento"). */ dimensao: string; vazio?: string }>(), {
  emTabela: false,
  vazio: 'Nenhuma resposta de NPS neste recorte.',
})
</script>

<template>
  <p v-if="!linhas.length" class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">{{ vazio }}</p>

  <ul v-else-if="!emTabela" class="flex flex-col gap-4">
    <li v-for="l in linhas" :key="l.chave" class="flex flex-col gap-1.5">
      <div class="flex items-start justify-between gap-3">
        <span class="min-w-0 break-words text-sm font-semibold text-texto">{{ l.rotulo }}</span>
        <SeloNps :nps="l.nps" class="shrink-0" />
      </div>
      <BarraGrupos v-if="l.nps.total" legenda="nenhuma" :detratores="l.nps.detratores" :neutros="l.nps.neutros" :promotores="l.nps.promotores" />
      <div v-else class="h-3.5 rounded-[4px] bg-superficie-2" aria-hidden="true" />
      <p class="text-xs text-texto-fraco">
        {{ plural(l.empresas, 'empresa', 'empresas') }} · {{ plural(l.nps.total, 'resposta', 'respostas') }}
      </p>
    </li>
  </ul>

  <div v-else class="overflow-x-auto rounded-xl border border-borda">
    <table class="w-full text-sm">
      <caption class="sr-only">{{ titulo }}</caption>
      <thead class="bg-superficie-2">
        <tr>
          <th scope="col" class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco">{{ dimensao }}</th>
          <th scope="col" class="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">NPS</th>
          <th scope="col" class="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Detratores</th>
          <th scope="col" class="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Neutros</th>
          <th scope="col" class="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Promotores</th>
          <th scope="col" class="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-texto-fraco">Empresas</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in linhas" :key="l.chave" class="border-t border-borda">
          <th scope="row" class="px-3 py-2 text-left font-medium text-texto">{{ l.rotulo }}</th>
          <td class="px-3 py-2 text-right font-semibold tabular-nums text-texto">{{ formatarNps(l.nps.valor) }}</td>
          <td class="px-3 py-2 text-right tabular-nums text-texto-suave">{{ formatarNumero(l.nps.detratores) }}</td>
          <td class="px-3 py-2 text-right tabular-nums text-texto-suave">{{ formatarNumero(l.nps.neutros) }}</td>
          <td class="px-3 py-2 text-right tabular-nums text-texto-suave">{{ formatarNumero(l.nps.promotores) }}</td>
          <td class="px-3 py-2 text-right tabular-nums text-texto-suave">{{ formatarNumero(l.empresas) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
