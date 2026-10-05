<script setup lang="ts">
// "Resumo da IA" no modo exemplo (etapa 5h): o mesmo cartão do painel, com as três frases do exemplo e o botão de gerar
// desligado (no modo exemplo, a IA não gera nada e nada gasta a cota).
import { ArrowRight, Sparkles, ThumbsUp, TriangleAlert } from 'lucide-vue-next'
import { PARTES_RESUMO } from '@/modulos/ia/logica'
import Botao from '@/components/ui/Botao.vue'
import { RESUMO_IA_EXEMPLO } from './exemplo'

defineProps<{ periodo: string }>()

const ICONES = { melhorar: TriangleAlert, funciona: ThumbsUp, proximo_passo: ArrowRight } as const
const CORES = { melhorar: 'text-atencao', funciona: 'text-sucesso', proximo_passo: 'text-marca-texto' } as const
</script>

<template>
  <section class="cartao p-5 sm:p-6" aria-labelledby="t-resumo-ia-exemplo" data-resumo-ia-exemplo>
    <header class="flex items-start gap-3">
      <span class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto" aria-hidden="true">
        <Sparkles class="size-5" />
      </span>
      <div class="min-w-0 flex-1">
        <h2 id="t-resumo-ia-exemplo" class="text-base font-bold text-texto">Resumo da IA</h2>
        <p class="text-sm text-texto-fraco">{{ periodo }}</p>
      </div>
    </header>
    <dl class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
      <div v-for="p in PARTES_RESUMO" :key="p.chave" class="flex min-w-0 flex-col gap-1.5 rounded-xl bg-superficie-2 p-4">
        <dt class="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide" :class="CORES[p.chave]">
          <component :is="ICONES[p.chave]" class="size-4 shrink-0" aria-hidden="true" />
          {{ p.rotulo }}
        </dt>
        <dd class="break-words text-sm leading-relaxed text-texto">{{ RESUMO_IA_EXEMPLO[p.chave] }}</dd>
      </div>
    </dl>
    <footer class="mt-4 flex flex-col gap-3 border-t border-borda pt-4 sm:flex-row sm:items-center sm:justify-between">
      <p class="text-xs text-texto-fraco">No modo exemplo, o resumo não é gerado.</p>
      <Botao variante="secundario" desabilitado class="self-start sm:self-auto">
        <Sparkles class="size-4" aria-hidden="true" /> Gerar de novo
      </Botao>
    </footer>
  </section>
</template>
