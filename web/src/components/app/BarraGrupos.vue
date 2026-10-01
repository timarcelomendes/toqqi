<script setup lang="ts">
// Barra empilhada dos três grupos da nota (detratores → neutros → promotores), com legenda escrita.
// Cores de status (vermelho/âmbar/verde) sempre com o nome e o número ao lado: a cor nunca fala sozinha.
import { computed, ref } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import type { GrupoNota } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'

type Chave = 'detratores' | 'neutros' | 'promotores'

const props = withDefaults(
  defineProps<{
    tipo?: 'nps' | 'csat'
    detratores: number
    neutros: number
    promotores: number
    /** Porcentagens prontas da API (uma casa). Sem elas, calculamos pelas quantidades. */
    pct?: { detratores: number; neutros: number; promotores: number } | null
    legenda?: 'completa' | 'compacta'
    /** Link de cada grupo (ex.: lista de respostas filtrada). */
    linkGrupo?: (g: GrupoNota) => RouteLocationRaw | undefined
  }>(),
  { tipo: 'nps', legenda: 'completa', pct: null, linkGrupo: undefined },
)

const ROTULOS: Record<'nps' | 'csat', Record<Chave, { nome: string; um: string; notas: string; grupo: GrupoNota }>> = {
  nps: {
    detratores: { nome: 'Detratores', um: 'detrator', notas: 'notas 0 a 6', grupo: 'detrator' },
    neutros: { nome: 'Neutros', um: 'neutro', notas: 'notas 7 e 8', grupo: 'neutro' },
    promotores: { nome: 'Promotores', um: 'promotor', notas: 'notas 9 e 10', grupo: 'promotor' },
  },
  csat: {
    detratores: { nome: 'Insatisfeitos', um: 'insatisfeito', notas: 'notas 1 e 2', grupo: 'insatisfeito' },
    neutros: { nome: 'Neutros', um: 'neutro', notas: 'nota 3', grupo: 'neutro' },
    promotores: { nome: 'Satisfeitos', um: 'satisfeito', notas: 'notas 4 e 5', grupo: 'satisfeito' },
  },
}
const CORES: Record<Chave, string> = {
  detratores: 'bg-grafico-detrator',
  neutros: 'bg-grafico-neutro',
  promotores: 'bg-grafico-promotor',
}

const total = computed(() => Math.max(0, props.detratores) + Math.max(0, props.neutros) + Math.max(0, props.promotores))

function pctDe(k: Chave, qtd: number): number {
  const p = props.pct?.[k]
  if (typeof p === 'number' && Number.isFinite(p)) return p
  return total.value ? Math.round((qtd / total.value) * 1000) / 10 : 0
}

const grupos = computed(() =>
  (['detratores', 'neutros', 'promotores'] as Chave[]).map((k) => {
    const qtd = Math.max(0, props[k])
    return {
      chave: k,
      ...ROTULOS[props.tipo][k],
      qtd,
      pct: pctDe(k, qtd),
      fracao: total.value ? qtd / total.value : 0,
      cor: CORES[k],
      link: props.linkGrupo?.(ROTULOS[props.tipo][k].grupo),
    }
  }),
)
const visiveis = computed(() => grupos.value.filter((g) => g.qtd > 0))

function formatarPct(v: number): string {
  return `${v.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`
}

const resumo = computed(() =>
  total.value ? grupos.value.map((g) => `${g.nome}: ${formatarPct(g.pct)} (${formatarNumero(g.qtd)})`).join('; ') : 'Sem respostas',
)

// Dica ao passar o mouse (os mesmos números já estão escritos na legenda).
const ativo = ref<Chave | null>(null)
const posicao = ref(0)
const barra = ref<HTMLElement | null>(null)
function mostrar(k: Chave, e: PointerEvent) {
  const r = barra.value?.getBoundingClientRect()
  if (!r) return
  ativo.value = k
  posicao.value = Math.min(Math.max(e.clientX - r.left, 60), Math.max(60, r.width - 60))
}
const dica = computed(() => grupos.value.find((g) => g.chave === ativo.value) ?? null)
</script>

<template>
  <div class="flex flex-col gap-3">
    <div ref="barra" class="relative" @pointerleave="ativo = null">
      <div class="flex h-3.5 w-full gap-0.5" role="img" :aria-label="resumo">
        <template v-if="total">
          <div
            v-for="(g, i) in visiveis"
            :key="g.chave"
            class="h-full min-w-1 transition-opacity"
            :class="[g.cor, i === 0 ? 'rounded-l-[4px]' : '', i === visiveis.length - 1 ? 'rounded-r-[4px]' : '', ativo && ativo !== g.chave ? 'opacity-55' : '']"
            :style="{ flexGrow: g.fracao, flexBasis: 0 }"
            @pointerenter="mostrar(g.chave, $event)"
            @pointermove="mostrar(g.chave, $event)"
          />
        </template>
        <div v-else class="h-full w-full rounded-[4px] bg-superficie-2" />
      </div>
      <div
        v-if="dica"
        class="pointer-events-none absolute bottom-full z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-borda bg-superficie px-2.5 py-1.5 text-xs shadow-lg"
        :style="{ left: `${posicao}px` }"
        aria-hidden="true"
      >
        <span class="font-bold text-texto">{{ formatarPct(dica.pct) }}</span>
        <span class="text-texto-suave"> · {{ formatarNumero(dica.qtd) }} {{ dica.qtd === 1 ? dica.um : dica.nome.toLowerCase() }}</span>
      </div>
    </div>

    <!-- Legenda completa: três colunas quando cabe; em espaço estreito (celular), uma linha por grupo. -->
    <div v-if="legenda === 'completa'" class="@container">
      <ul class="grid grid-cols-1 text-sm @sm:grid-cols-3 @sm:gap-2">
        <li v-for="g in grupos" :key="g.chave" class="min-w-0">
          <component
            :is="g.link ? RouterLink : 'div'"
            :to="g.link"
            class="-mx-1 flex min-h-10 flex-wrap items-center gap-x-2 rounded-lg px-1 @sm:-my-1 @sm:min-h-0 @sm:flex-col @sm:flex-nowrap @sm:items-stretch @sm:py-1"
            :class="g.link ? 'hover:bg-superficie-2' : ''"
          >
            <span class="flex items-center gap-1.5 font-semibold text-texto-suave">
              <span class="size-2.5 shrink-0 rounded-[3px]" :class="g.cor" aria-hidden="true" />
              {{ g.nome }}
            </span>
            <span class="order-last ml-auto text-base font-bold text-texto @sm:order-none @sm:ml-0 @sm:text-lg">{{ formatarPct(g.pct) }}</span>
            <span class="text-xs text-texto-fraco">{{ formatarNumero(g.qtd) }} · {{ g.notas }}</span>
          </component>
        </li>
      </ul>
    </div>
    <ul v-else class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      <li v-for="g in grupos" :key="g.chave">
        <component
          :is="g.link ? RouterLink : 'span'"
          :to="g.link"
          class="inline-flex min-h-6 items-center gap-1.5 rounded-md text-texto-suave"
          :class="g.link ? 'hover:text-texto hover:underline' : ''"
        >
          <span class="size-2.5 shrink-0 rounded-[3px]" :class="g.cor" aria-hidden="true" />
          <strong class="font-semibold text-texto">{{ formatarNumero(g.qtd) }}</strong>
          {{ g.qtd === 1 ? g.um : g.nome.toLowerCase() }}
          <span class="text-texto-fraco">({{ formatarPct(g.pct) }})</span>
        </component>
      </li>
    </ul>
  </div>
</template>
