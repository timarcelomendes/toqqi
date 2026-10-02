<script setup lang="ts">
// Empresas: onde cuidar e onde crescer. Duas colunas ("Cuidar primeiro" = menor NPS, "Mais satisfeitas" = maior), cada
// linha com o nome, "N respostas · R$ X mil/mês" (quando há valor), a régua −100 a 100 (marca no zero e barra do zero
// até o valor, vermelha ou verde) e o NPS escrito. Com respostas.ver, a linha abre as respostas da empresa.
import { RouterLink } from 'vue-router'
import { Building2 } from 'lucide-vue-next'
import type { EmpresaNps, Painel } from '@/api/tipos'
import { plural } from '@/utils/formatos'
import { formatarMoedaCurta, formatarNps, reguaNps } from './logica'

defineProps<{ empresas: Painel['empresas']; consulta: Record<string, string>; podeVerRespostas: boolean }>()

const listas: { chave: 'menor' | 'maior'; titulo: string; cor: string }[] = [
  { chave: 'menor', titulo: 'Cuidar primeiro', cor: 'text-erro' },
  { chave: 'maior', titulo: 'Mais satisfeitas', cor: 'text-sucesso' },
]

function valor(e: EmpresaNps): string | null {
  const v = e.valor_mensal
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? `${formatarMoedaCurta(n)}/mês` : null
}
function corNps(nps: number) {
  return nps < 0 ? 'text-erro' : nps > 0 ? 'text-sucesso' : 'text-texto-suave'
}
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-empresas">
    <header>
      <h2 id="t-empresas" class="text-base font-bold text-texto">Empresas: onde cuidar e onde crescer</h2>
      <p class="text-sm text-texto-suave">Com 3 ou mais respostas de NPS no período. A barra vai de −100 a 100.</p>
    </header>
    <div v-if="empresas.menor.length || empresas.maior.length" class="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">
      <div v-for="l in listas" :key="l.chave" class="min-w-0">
        <h3 class="mb-1 text-xs font-bold uppercase tracking-wider" :class="l.cor">{{ l.titulo }}</h3>
        <ol v-if="empresas[l.chave].length" class="-mx-2 flex flex-col" :data-lista="l.chave">
          <li v-for="e in empresas[l.chave]" :key="String(e.empresa.id)">
            <component
              :is="podeVerRespostas ? RouterLink : 'div'"
              :to="podeVerRespostas ? { path: '/respostas', query: { ...consulta, empresa_id: String(e.empresa.id) } } : undefined"
              class="grid min-h-12 grid-cols-[minmax(0,1fr)_5rem_2.5rem] items-center gap-3 rounded-xl px-2 py-1.5 sm:grid-cols-[minmax(0,1fr)_7.5rem_2.75rem]"
              :class="podeVerRespostas ? 'group hover:bg-superficie-2' : ''"
            >
              <span class="min-w-0">
                <span class="block truncate text-sm font-semibold text-texto group-hover:underline">{{ e.empresa.nome }}</span>
                <span class="block truncate text-xs text-texto-fraco">{{ plural(e.respostas, 'resposta', 'respostas') }}<template v-if="valor(e)"> · {{ valor(e) }}</template></span>
              </span>
              <span class="relative h-2 rounded-full bg-superficie-2" aria-hidden="true" data-regua>
                <span
                  v-if="reguaNps(e.nps).largura > 0"
                  class="absolute inset-y-0"
                  :class="reguaNps(e.nps).sinal === 'negativo' ? 'rounded-l-full bg-grafico-detrator' : 'rounded-r-full bg-grafico-promotor'"
                  :style="{ left: `${reguaNps(e.nps).inicio}%`, width: `${reguaNps(e.nps).largura}%` }"
                />
                <span class="absolute -inset-y-1 left-1/2 w-0.5 -translate-x-1/2 rounded-full bg-texto-fraco" />
              </span>
              <span class="text-right text-sm font-extrabold tabular-nums" :class="corNps(e.nps)"><span class="sr-only">NPS </span>{{ formatarNps(e.nps) }}</span>
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
