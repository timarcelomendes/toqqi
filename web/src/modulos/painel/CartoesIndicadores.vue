<script setup lang="ts">
// Três números do período: variação do NPS, CSAT e taxa de resposta.
import { computed } from 'vue'
import { AlertTriangle, Minus, TrendingDown, TrendingUp } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { formatarNumero, plural } from '@/utils/formatos'
import { descreverIntervalo } from '@/utils/periodo'
import { descreverVariacao, formatarMedia2, formatarNps, formatarVariacao, tomCsat } from './logica'

const props = defineProps<{
  variacao: Painel['variacao']
  periodo: Painel['periodo']
  csat: Painel['csat']
  taxa: Painel['taxa_resposta']
}>()

const COR_TEXTO = { sucesso: 'text-sucesso', atencao: 'text-atencao', erro: 'text-erro', neutro: 'text-texto', marca: 'text-texto', info: 'text-texto' } as const

const temPeriodo = computed(() => !!(props.periodo?.de || props.periodo?.ate))
const direcao = computed(() => {
  const v = props.variacao?.valor ?? 0
  return Math.round(v) > 0 ? 'sobe' : Math.round(v) < 0 ? 'desce' : 'igual'
})
const anterior = computed(() => (props.periodo?.anterior ? descreverIntervalo(props.periodo.anterior.de, props.periodo.anterior.ate) : null))
const corCsat = computed(() => COR_TEXTO[tomCsat(props.csat?.percentual)])
</script>

<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
    <!-- Variação -->
    <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-variacao">
      <h2 id="t-variacao" class="text-sm font-semibold text-texto-suave">Variação do NPS</h2>
      <template v-if="variacao">
        <p class="flex items-center gap-2">
          <span
            class="flex size-8 items-center justify-center rounded-lg"
            :class="direcao === 'sobe' ? 'bg-sucesso-suave text-sucesso' : direcao === 'desce' ? 'bg-erro-suave text-erro' : 'bg-superficie-2 text-texto-suave'"
            aria-hidden="true"
          >
            <TrendingUp v-if="direcao === 'sobe'" class="size-4" />
            <TrendingDown v-else-if="direcao === 'desce'" class="size-4" />
            <Minus v-else class="size-4" />
          </span>
          <span class="text-4xl font-extrabold leading-none text-texto" :title="`O NPS ${descreverVariacao(variacao.valor)}`">{{ formatarVariacao(variacao.valor) }}</span>
        </p>
        <p class="text-sm text-texto-suave">{{ Math.abs(Math.round(variacao.valor)) === 1 ? 'ponto' : 'pontos' }} sobre o período anterior</p>
        <p class="text-xs text-texto-fraco">
          Antes: <strong class="font-semibold text-texto-suave">{{ formatarNps(variacao.anterior) }}</strong><template v-if="anterior">, {{ anterior }}</template>
        </p>
      </template>
      <template v-else>
        <p class="text-4xl font-extrabold leading-none text-texto-fraco" aria-hidden="true">—</p>
        <p class="text-sm text-texto-suave">
          {{ temPeriodo ? 'Faltam respostas de NPS neste período ou no anterior para comparar.' : 'Escolha um período para comparar com o anterior.' }}
        </p>
      </template>
    </section>

    <!-- CSAT -->
    <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-csat">
      <h2 id="t-csat" class="text-sm font-semibold text-texto-suave">Satisfação (CSAT)</h2>
      <template v-if="csat && csat.total > 0 && csat.percentual !== null">
        <p class="text-4xl font-extrabold leading-none" :class="corCsat">{{ formatarNumero(csat.percentual) }}%</p>
        <p class="text-sm text-texto-suave">deram nota 4 ou 5</p>
        <p class="text-xs text-texto-fraco">
          Média <strong class="font-semibold text-texto-suave">{{ formatarMedia2(csat.media) }}</strong> de 5 · {{ plural(csat.total, 'resposta', 'respostas') }}
        </p>
      </template>
      <template v-else>
        <p class="text-4xl font-extrabold leading-none text-texto-fraco" aria-hidden="true">—</p>
        <p class="text-sm text-texto-suave">Nenhuma resposta de satisfação (nota de 1 a 5) no período.</p>
      </template>
    </section>

    <!-- Taxa de resposta -->
    <section class="cartao flex flex-col gap-2 p-5" aria-labelledby="t-taxa">
      <h2 id="t-taxa" class="text-sm font-semibold text-texto-suave">Taxa de resposta</h2>
      <template v-if="taxa && taxa.percentual !== null && taxa.convidados > 0">
        <p class="text-4xl font-extrabold leading-none text-texto">{{ formatarNumero(taxa.percentual) }}%</p>
        <p class="text-sm text-texto-suave">
          {{ formatarNumero(taxa.responderam) }} de {{ plural(taxa.convidados, 'contato', 'contatos') }} {{ taxa.responderam === 1 ? 'respondeu' : 'responderam' }}
        </p>
        <p class="text-xs text-texto-fraco">Conta só quem recebeu a pesquisa no período.</p>
        <p v-if="taxa.amostra_pequena" class="mt-1 flex items-start gap-1.5 rounded-lg bg-atencao-suave px-2.5 py-2 text-xs text-atencao">
          <AlertTriangle class="mt-px size-3.5 shrink-0" aria-hidden="true" />
          <span><strong class="font-semibold">Amostra pequena:</strong> menos de 20% responderam; os números podem não mostrar o que todos pensam.</span>
        </p>
      </template>
      <template v-else>
        <p class="text-4xl font-extrabold leading-none text-texto-fraco" aria-hidden="true">—</p>
        <p class="text-sm text-texto-suave">Nenhuma pesquisa saiu no período, então não dá para calcular.</p>
      </template>
    </section>
  </div>
</template>
