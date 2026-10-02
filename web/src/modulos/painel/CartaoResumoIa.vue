<script setup lang="ts">
// Painel (etapa 5d, docs/api-etapa-5d.md §6.1): "Resumo da IA" logo abaixo do NPS. Lê o resumo salvo para os filtros dos
// números na tela, de novo a cada troca de filtro; some sem IA na plataforma. Gerar gasta 1 análise da cota do plano e
// a conta espera 30 s para gerar outro.
import { ArrowRight, Sparkles, ThumbsUp, TriangleAlert } from 'lucide-vue-next'
import { resumoIaApi, type FiltrosGeracaoIa } from '@/api'
import BotaoGerarIa from '@/modulos/ia/BotaoGerarIa.vue'
import ConteudoGeracaoIa from '@/modulos/ia/ConteudoGeracaoIa.vue'
import MetaGeracaoIa from '@/modulos/ia/MetaGeracaoIa.vue'
import { PARTES_RESUMO, TEXTOS_RESUMO, falarResumo, normalizarResumo } from '@/modulos/ia/logica'
import { usarGeracaoIa } from '@/modulos/ia/usarGeracaoIa'

const props = defineProps<{
  /** Os filtros dos números na tela (período, grupo, só ativas). */
  filtros: FiltrosGeracaoIa
  /** Rótulo do período, como no cartão do NPS. */
  periodo: string
}>()

const geracao = usarGeracaoIa({
  obter: resumoIaApi.obter,
  gerar: resumoIaApi.gerar,
  conteudo: normalizarResumo,
  filtros: () => props.filtros,
  textos: TEXTOS_RESUMO,
  falar: falarResumo,
})

const ICONES = { melhorar: TriangleAlert, funciona: ThumbsUp, proximo_passo: ArrowRight } as const
const CORES = { melhorar: 'text-atencao', funciona: 'text-sucesso', proximo_passo: 'text-marca-texto' } as const
</script>

<template>
  <section v-if="geracao.visivel" class="cartao p-5 sm:p-6" aria-labelledby="t-resumo-ia" data-resumo-ia>
    <header class="flex items-start gap-3">
      <span class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto" aria-hidden="true">
        <Sparkles class="size-5" />
      </span>
      <div class="min-w-0 flex-1">
        <h2 id="t-resumo-ia" tabindex="-1" class="text-base font-bold text-texto focus:outline-none">Resumo da IA</h2>
        <p class="text-sm text-texto-fraco">{{ periodo }}</p>
      </div>
    </header>

    <div class="mt-4 transition-opacity" :class="geracao.lendo && !geracao.atual ? 'opacity-60' : ''" :aria-busy="(geracao.lendo && !geracao.atual) || undefined">
      <ConteudoGeracaoIa :geracao="geracao" titulo="t-resumo-ia">
        <template #item="{ conteudo }">
          <dl class="grid grid-cols-1 gap-3 md:grid-cols-3" data-frases>
            <template v-for="p in PARTES_RESUMO" :key="p.chave">
              <div v-if="conteudo[p.chave]" class="flex min-w-0 flex-col gap-1.5 rounded-xl bg-superficie-2 p-4">
                <dt class="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide" :class="CORES[p.chave]">
                  <component :is="ICONES[p.chave]" class="size-4 shrink-0" aria-hidden="true" />
                  {{ p.rotulo }}
                </dt>
                <dd class="break-words text-sm leading-relaxed text-texto">{{ conteudo[p.chave] }}</dd>
              </div>
            </template>
          </dl>
        </template>
      </ConteudoGeracaoIa>
    </div>

    <footer
      v-if="geracao.mostrarBotao || (geracao.item && !geracao.erroLeitura)"
      class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      :class="geracao.item ? 'border-t border-borda pt-4' : ''"
    >
      <MetaGeracaoIa :geracao="geracao" />
      <!-- Sem resumo, o botão fica à esquerda: à direita, no pé da tela, ele cairia sob o botão flutuante do assistente -->
      <BotaoGerarIa :geracao="geracao" class="self-start" :class="geracao.item ? 'sm:ml-auto sm:self-auto' : ''" />
    </footer>

    <!-- Para leitores de tela: o resumo gerado (inteiro) e o fim da espera (os avisos de erro já são regiões vivas) -->
    <p class="sr-only" aria-live="polite" aria-atomic="true" data-anuncio>{{ geracao.anuncio }}</p>
  </section>
</template>
