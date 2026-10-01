<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { ArrowRight, ChevronDown, TrendingDown, TrendingUp } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import { tomNotaNps } from '@/utils/rotulos'

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
  <section class="cartao @container flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-movimentacao">
    <header>
      <h2 id="t-movimentacao" class="text-base font-bold text-texto">Movimentação</h2>
      <p class="text-sm text-texto-suave">Quem mudou de grupo, comparando a última nota com a anterior.</p>
    </header>

    <div class="grid grid-cols-1 gap-3 @lg:grid-cols-2">
      <div class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4">
        <span class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-sucesso-suave text-sucesso" aria-hidden="true"><TrendingUp class="size-5" /></span>
        <div class="min-w-0">
          <p class="text-3xl font-extrabold leading-none text-texto">{{ formatarNumero(movimentacao?.resgatados ?? 0) }}</p>
          <p class="mt-1 text-sm font-semibold text-texto">{{ movimentacao?.resgatados === 1 ? 'resgatado' : 'resgatados' }}</p>
          <p class="text-xs text-texto-fraco">Eram detratores e agora deram 9 ou 10.</p>
        </div>
      </div>
      <div class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4">
        <span class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-erro-suave text-erro" aria-hidden="true"><TrendingDown class="size-5" /></span>
        <div class="min-w-0">
          <p class="text-3xl font-extrabold leading-none text-texto">{{ formatarNumero(movimentacao?.deixaram_de_ser_promotores ?? 0) }}</p>
          <p class="mt-1 text-sm font-semibold text-texto">deixaram de ser promotores</p>
          <p class="text-xs text-texto-fraco">Davam 9 ou 10 e agora deram 8 ou menos.</p>
        </div>
      </div>
    </div>

    <template v-if="itens.length">
      <button
        type="button"
        class="inline-flex h-10 w-fit items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-marca-texto hover:bg-marca-suave"
        :aria-expanded="aberto"
        :aria-controls="`${id}-lista`"
        @click="aberto = !aberto"
      >
        <ChevronDown class="size-4 transition-transform" :class="aberto ? 'rotate-180' : ''" aria-hidden="true" />
        {{ aberto ? 'Esconder o que mudou' : `Ver o que mudou (${formatarNumero(itens.length)})` }}
      </button>
      <ul v-show="aberto" :id="`${id}-lista`" class="-mt-1 divide-y divide-borda rounded-xl border border-borda">
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
