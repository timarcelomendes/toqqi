<script setup lang="ts">
// Caixa "Análise da IA" do painel Analisar: resumo, sentimento geral, temas com o sentimento de cada um e quando foi feita.
// Sem análise pronta, diz em que pé está: na fila, não deu certo ou limite do mês.
import { computed } from 'vue'
import { AlertTriangle, Clock, Sparkles } from 'lucide-vue-next'
import type { AnaliseIa, TemaResposta } from '@/api/tipos'
import { formatarDataHora } from '@/utils/datas'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { SENTIMENTOS, SENTIMENTOS_TEMA, SITUACOES_IA, analisada, ehSentimento } from './ia'
import { TEMAS_PADRAO, rotuloTema } from './logica'

const props = withDefaults(defineProps<{ ia: AnaliseIa; temas?: TemaResposta[] }>(), { temas: () => TEMAS_PADRAO })

const pronta = computed(() => analisada(props.ia))
const sentimento = computed(() => (ehSentimento(props.ia.sentimento) ? SENTIMENTOS[props.ia.sentimento] : null))
const situacao = computed(() => (props.ia.situacao !== 'analisada' ? (SITUACOES_IA[props.ia.situacao] ?? null) : null))
const temasIa = computed(() =>
  (props.ia.temas ?? []).map((t) => {
    const s = SENTIMENTOS_TEMA[t.sentimento] ?? { rotulo: t.sentimento, tom: 'neutro' as const }
    return { chave: t.tema, tema: rotuloTema(t.tema, props.temas), sentimento: s.rotulo, tom: s.tom }
  }),
)
</script>

<template>
  <section class="rounded-xl border border-borda p-4" aria-labelledby="t-analise-ia" data-analise-ia>
    <h3 id="t-analise-ia" class="mb-2 flex items-center gap-1.5 text-sm font-bold uppercase tracking-wide text-texto-fraco">
      <Sparkles class="size-4" aria-hidden="true" /> Análise da IA
    </h3>

    <div v-if="pronta" class="flex flex-col gap-3 text-sm">
      <p v-if="ia.resumo" class="text-[0.95rem] text-texto">{{ ia.resumo }}</p>
      <p v-if="sentimento" class="flex flex-wrap items-center gap-2">
        <span class="text-texto-fraco">Sentimento:</span>
        <Etiqueta :tom="sentimento.tom" ponto>{{ sentimento.rotulo }}</Etiqueta>
      </p>
      <div>
        <p class="text-texto-fraco">Temas citados</p>
        <ul v-if="temasIa.length" class="mt-1.5 flex flex-wrap gap-1.5">
          <li v-for="t in temasIa" :key="t.chave">
            <Etiqueta :tom="t.tom">{{ t.tema }} · {{ t.sentimento }}</Etiqueta>
          </li>
        </ul>
        <p v-else class="mt-0.5 text-texto-suave">Nenhum dos 6 temas aparece neste comentário.</p>
      </div>
      <p v-if="ia.em" class="text-xs text-texto-fraco">Analisado em {{ formatarDataHora(ia.em) }}. A IA lê só o texto do cliente, as opções que ele marcou e a nota.</p>
    </div>

    <div v-else-if="situacao" class="flex items-start gap-2.5 text-sm">
      <Clock v-if="ia.situacao === 'pendente'" class="mt-0.5 size-4 shrink-0 text-info" aria-hidden="true" />
      <AlertTriangle v-else class="mt-0.5 size-4 shrink-0 text-atencao" aria-hidden="true" />
      <div>
        <p class="font-semibold text-texto">{{ situacao.titulo }}</p>
        <p class="text-texto-suave">{{ situacao.texto }}</p>
      </div>
    </div>
  </section>
</template>
