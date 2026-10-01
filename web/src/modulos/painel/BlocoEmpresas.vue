<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Building2 } from 'lucide-vue-next'
import type { EmpresaNps, Painel } from '@/api/tipos'
import { plural } from '@/utils/formatos'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { formatarNps, tomNps } from './logica'

defineProps<{ empresas: Painel['empresas']; consulta: Record<string, string>; podeVerRespostas: boolean }>()

const listas: { chave: 'menor' | 'maior'; titulo: string; descricao: string }[] = [
  { chave: 'menor', titulo: 'Menor NPS', descricao: 'Onde a satisfação está mais baixa.' },
  { chave: 'maior', titulo: 'Maior NPS', descricao: 'Quem está mais satisfeito.' },
]

function chave(e: EmpresaNps) {
  return String(e.empresa.id)
}
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-empresas">
    <header>
      <h2 id="t-empresas" class="text-base font-bold text-texto">Empresas</h2>
      <p class="text-sm text-texto-suave">Só entram empresas com 3 ou mais respostas de NPS no período.</p>
    </header>
    <div v-if="empresas.menor.length || empresas.maior.length" class="grid grid-cols-1 gap-5 md:grid-cols-2">
      <div v-for="l in listas" :key="l.chave" class="min-w-0">
        <h3 class="text-sm font-bold text-texto">{{ l.titulo }}</h3>
        <p class="mb-2 text-xs text-texto-fraco">{{ l.descricao }}</p>
        <ol v-if="empresas[l.chave].length" class="flex flex-col divide-y divide-borda rounded-xl border border-borda">
          <li v-for="e in empresas[l.chave]" :key="chave(e)">
            <component
              :is="podeVerRespostas ? RouterLink : 'div'"
              :to="podeVerRespostas ? { path: '/respostas', query: { ...consulta, empresa_id: String(e.empresa.id) } } : undefined"
              class="flex min-h-12 items-center gap-3 px-3.5 py-2"
              :class="podeVerRespostas ? 'hover:bg-superficie-2' : ''"
            >
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-semibold text-texto">{{ e.empresa.nome }}</span>
                <span class="block text-xs text-texto-fraco">{{ plural(e.respostas, 'resposta', 'respostas') }}</span>
              </span>
              <Etiqueta :tom="tomNps(e.nps)" class="shrink-0">NPS {{ formatarNps(e.nps) }}</Etiqueta>
            </component>
          </li>
        </ol>
        <p v-else class="rounded-xl bg-superficie-2 p-3 text-sm text-texto-fraco">Nenhuma empresa nesta lista.</p>
      </div>
    </div>
    <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
      <Building2 class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
      <p class="text-texto-suave">Nenhuma empresa com 3 ou mais respostas de NPS neste período.</p>
    </div>
  </section>
</template>
