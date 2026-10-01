<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { AlertTriangle, ArrowRight, CheckCircle2, CircleDollarSign, UserRound } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { diasAte, formatarData } from '@/utils/datas'
import { formatarMoeda, formatarNumero, plural } from '@/utils/formatos'
import Botao from '@/components/ui/Botao.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { formatarNps, tomNps } from './logica'

const props = defineProps<{ atencao: Painel['atencao'] }>()
const sessao = useSessaoStore()
const podeVerAcoes = computed(() => sessao.pode('acoes.ver'))
const empresas = computed(() => props.atencao?.empresas ?? [])
const receita = computed(() => props.atencao?.receita_em_risco ?? { valor: 0, empresas: 0, sem_valor: 0 })
const abertas = computed(() => props.atencao?.acoes_abertas ?? 0)
const vencidas = computed(() => props.atencao?.acoes_vencidas ?? 0)
const emDia = computed(() => props.atencao?.tudo_em_dia || (!abertas.value && !empresas.value.length))

/** "há 3 dias", "hoje", "ontem". */
function haQuanto(data: string | null): string {
  const d = diasAte(data)
  if (d === null) return ''
  const dias = -d
  if (dias <= 0) return 'hoje'
  if (dias === 1) return 'ontem'
  return `há ${formatarNumero(dias)} dias`
}
</script>

<template>
  <section class="cartao flex flex-col gap-5 p-5 sm:p-6" aria-labelledby="t-atencao">
    <header class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div class="flex flex-col gap-2">
        <h2 id="t-atencao" class="text-base font-bold text-texto">Precisa de atenção</h2>
        <div class="flex flex-wrap gap-2 text-sm">
          <component
            :is="podeVerAcoes ? RouterLink : 'span'"
            :to="podeVerAcoes ? '/planos-de-acao' : undefined"
            class="inline-flex min-h-10 items-center rounded-xl bg-superficie-2 px-3 font-semibold text-texto"
            :class="podeVerAcoes ? 'hover:bg-borda' : ''"
          >
            {{ plural(abertas, 'ação aberta', 'ações abertas') }}
          </component>
          <component
            :is="podeVerAcoes && vencidas ? RouterLink : 'span'"
            :to="podeVerAcoes && vencidas ? { path: '/planos-de-acao', query: { so_vencidas: 'true' } } : undefined"
            class="inline-flex min-h-10 items-center gap-1.5 rounded-xl px-3 font-semibold"
            :class="vencidas ? 'bg-erro-suave text-erro' : 'bg-superficie-2 text-texto-suave'"
          >
            <AlertTriangle v-if="vencidas" class="size-4" aria-hidden="true" />
            {{ plural(vencidas, 'vencida', 'vencidas') }}
          </component>
        </div>
      </div>

      <div class="flex items-start gap-3 rounded-xl border border-borda p-3.5 md:max-w-sm">
        <CircleDollarSign class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
        <div class="min-w-0 text-sm">
          <p class="font-semibold text-texto-suave">Receita em risco</p>
          <p class="text-xl font-extrabold text-texto">
            {{ formatarMoeda(receita.valor, 'R$ 0,00') }}<span class="text-sm font-semibold text-texto-fraco"> por mês</span>
          </p>
          <p class="text-xs text-texto-fraco">
            <template v-if="receita.empresas">Contrato mensal de {{ plural(receita.empresas, 'empresa', 'empresas') }} com detrator no período.</template>
            <template v-else>Nenhuma empresa teve detrator no período.</template>
          </p>
          <p v-if="receita.sem_valor" class="mt-1 text-xs text-atencao">
            {{ receita.sem_valor === 1 ? '1 delas não tem' : `${formatarNumero(receita.sem_valor)} delas não têm` }} o valor do contrato cadastrado.
            <RouterLink v-if="sessao.pode('contatos.ver')" to="/contatos?aba=empresas" class="link">Completar em Empresas</RouterLink>
          </p>
        </div>
      </div>
    </header>

    <div v-if="emDia" class="flex items-start gap-3 rounded-xl bg-sucesso-suave p-4">
      <CheckCircle2 class="mt-0.5 size-5 shrink-0 text-sucesso" aria-hidden="true" />
      <div class="text-sm">
        <p class="font-semibold text-texto">Tudo em dia</p>
        <p class="text-texto-suave">Nenhuma ação aberta. Quando um cliente der nota baixa, ele aparece aqui para você tratar.</p>
      </div>
    </div>

    <template v-else>
      <ol class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" aria-label="Empresas com ações abertas, as mais urgentes primeiro">
        <li v-for="e in empresas" :key="String(e.empresa.id)" class="flex flex-col gap-2 rounded-xl border p-4" :class="e.acoes_vencidas ? 'border-erro/35' : 'border-borda'">
          <div class="flex items-start justify-between gap-3">
            <p class="min-w-0 font-semibold leading-snug text-texto">{{ e.empresa.nome }}</p>
            <Etiqueta v-if="e.nps !== null && e.nps !== undefined" :tom="tomNps(e.nps)" class="shrink-0">NPS {{ formatarNps(e.nps) }}</Etiqueta>
          </div>
          <p class="text-xs text-texto-suave">
            {{ plural(e.acoes_abertas, 'ação aberta', 'ações abertas') }}<template v-if="e.acoes_vencidas">
              · <strong class="font-semibold text-erro">{{ plural(e.acoes_vencidas, 'vencida', 'vencidas') }}</strong></template
            ><template v-if="e.desde"><br />Aberta desde {{ formatarData(e.desde) }} ({{ haQuanto(e.desde) }})</template>
          </p>
          <p class="flex items-center gap-1 text-xs text-texto-fraco">
            <UserRound class="size-3.5 shrink-0" aria-hidden="true" />
            <span class="truncate">{{ e.responsavel?.nome ?? 'Sem responsável' }}</span>
          </p>
          <p v-if="e.ultimo_comentario_detrator" class="line-clamp-2 border-l-2 border-erro/40 pl-2.5 text-sm italic text-texto-suave">
            “{{ e.ultimo_comentario_detrator }}”
          </p>
          <div v-if="podeVerAcoes && e.acao_id !== null && e.acao_id !== undefined" class="mt-auto pt-1">
            <Botao tamanho="sm" variante="secundario" class="!h-10" :para="`/planos-de-acao/${e.acao_id}`">
              Tratar <ArrowRight class="size-4" aria-hidden="true" /><span class="sr-only"> a ação mais urgente de {{ e.empresa.nome }}</span>
            </Botao>
          </div>
        </li>
      </ol>
      <p v-if="podeVerAcoes && abertas" class="-mt-1 text-sm">
        <RouterLink to="/planos-de-acao" class="link inline-flex min-h-10 items-center gap-1">Ver todas no quadro de ações <ArrowRight class="size-4" aria-hidden="true" /></RouterLink>
      </p>
    </template>
  </section>
</template>
