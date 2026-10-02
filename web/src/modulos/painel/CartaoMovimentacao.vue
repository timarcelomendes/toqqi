<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { ArrowRight, ChevronDown, TrendingDown, TrendingUp } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import { tomNotaNps } from '@/utils/rotulos'
import Etiqueta from '@/components/ui/Etiqueta.vue'

const props = defineProps<{ movimentacao: Painel['movimentacao'] }>()
const sessao = useSessaoStore()
const aberto = ref(false)
const id = useId()

const itens = computed(() => props.movimentacao?.itens ?? [])
const COR_NOTA = { sucesso: 'bg-sucesso-suave text-sucesso', atencao: 'bg-atencao-suave text-atencao', erro: 'bg-erro-suave text-erro' } as const
function corNota(n: number) {
  return COR_NOTA[tomNotaNps(n) as keyof typeof COR_NOTA] ?? 'bg-superficie-2 text-texto-suave'
}
</script>

<template>
  <section class="cartao flex flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-movimentacao">
    <header>
      <h2 id="t-movimentacao" class="text-base font-bold text-texto">Quem mudou de lado</h2>
      <p class="text-sm text-texto-suave">Última nota de cada contato comparada com a anterior.</p>
    </header>

    <div class="flex items-center gap-3 rounded-xl bg-sucesso-suave p-3.5" data-resgatados>
      <span class="w-11 shrink-0 text-center text-4xl font-extrabold leading-none tabular-nums text-sucesso">{{ formatarNumero(movimentacao?.resgatados ?? 0) }}</span>
      <div class="flex min-w-0 flex-col gap-1">
        <p class="flex flex-wrap items-center gap-1" aria-hidden="true">
          <Etiqueta tom="erro">detrator</Etiqueta><ArrowRight class="size-3.5 text-sucesso" /><Etiqueta tom="sucesso">promotor</Etiqueta>
        </p>
        <p class="text-sm text-texto-suave">
          {{ movimentacao?.resgatados === 1 ? 'resgatado' : 'resgatados' }}<span class="sr-only">: eram detratores e agora deram 9 ou 10</span>
        </p>
      </div>
    </div>
    <div class="flex items-center gap-3 rounded-xl bg-erro-suave p-3.5" data-deixaram>
      <span class="w-11 shrink-0 text-center text-4xl font-extrabold leading-none tabular-nums text-erro">{{ formatarNumero(movimentacao?.deixaram_de_ser_promotores ?? 0) }}</span>
      <div class="flex min-w-0 flex-col gap-1">
        <p class="flex flex-wrap items-center gap-1" aria-hidden="true">
          <Etiqueta tom="sucesso">promotor</Etiqueta><ArrowRight class="size-3.5 text-erro" /><Etiqueta tom="atencao">8 ou menos</Etiqueta>
        </p>
        <p class="text-sm text-texto-suave">
          {{ movimentacao?.deixaram_de_ser_promotores === 1 ? 'deixou de ser promotor' : 'deixaram de ser promotores' }}<span class="sr-only">: davam 9 ou 10 e agora deram 8 ou menos</span>
        </p>
      </div>
    </div>

    <template v-if="itens.length">
      <button
        type="button"
        class="-ml-3 inline-flex min-h-11 w-fit items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-marca-texto hover:bg-marca-suave"
        :aria-expanded="aberto"
        :aria-controls="`${id}-lista`"
        @click="aberto = !aberto"
      >
        {{ aberto ? 'Esconder a lista' : itens.length === 1 ? 'Ver a pessoa' : `Ver as ${formatarNumero(itens.length)} pessoas` }}
        <ChevronDown class="size-4 transition-transform" :class="aberto ? 'rotate-180' : ''" aria-hidden="true" />
      </button>
      <ul v-show="aberto" :id="`${id}-lista`" class="divide-y divide-borda rounded-xl border border-borda">
        <li v-for="(m, i) in itens" :key="`${m.contato.id}-${i}`" class="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <p class="flex items-center gap-1.5 text-sm font-semibold text-texto">
              <TrendingUp v-if="m.tipo === 'resgatado'" class="size-4 shrink-0 text-sucesso" aria-hidden="true" />
              <TrendingDown v-else class="size-4 shrink-0 text-erro" aria-hidden="true" />
              <RouterLink v-if="sessao.pode('contatos.ver')" :to="`/contatos/${m.contato.id}`" class="truncate hover:underline">{{ m.contato.nome }}</RouterLink>
              <span v-else class="truncate">{{ m.contato.nome }}</span>
            </p>
            <p class="truncate text-xs text-texto-fraco">
              {{ m.tipo === 'resgatado' ? 'Resgatado' : 'Deixou de ser promotor' }}<template v-if="m.empresa"> · {{ m.empresa.nome }}</template>
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2 text-xs text-texto-fraco">
            <span class="flex flex-col items-center" aria-hidden="true">
              <span class="flex size-8 items-center justify-center rounded-lg text-sm font-bold" :class="corNota(m.nota_anterior)">{{ m.nota_anterior }}</span>
              <span>{{ formatarData(m.data_anterior) }}</span>
            </span>
            <ArrowRight class="size-4 text-texto-fraco" aria-hidden="true" />
            <span class="flex flex-col items-center" aria-hidden="true">
              <span class="flex size-8 items-center justify-center rounded-lg text-sm font-bold" :class="corNota(m.nota_atual)">{{ m.nota_atual }}</span>
              <span>{{ formatarData(m.data_atual) }}</span>
            </span>
            <span class="sr-only">Nota {{ m.nota_anterior }} em {{ formatarData(m.data_anterior) }}, depois nota {{ m.nota_atual }} em {{ formatarData(m.data_atual) }}.</span>
          </div>
        </li>
      </ul>
    </template>
    <p v-else class="text-sm text-texto-fraco">Ninguém mudou de grupo neste período.</p>
  </section>
</template>
