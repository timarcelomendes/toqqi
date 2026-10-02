<script setup lang="ts">
// Início, durante o teste grátis e antes de assinar: quanto falta, o plano do teste e o caminho para os planos.
// Só para quem cuida da assinatura; nos últimos dias quem avisa é a faixa do topo (AvisoCobranca), então o cartão sai.
import { computed } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import { cartaoDoTeste } from '@/modulos/assinatura/logica'
import Botao from '@/components/ui/Botao.vue'

const sessao = useSessaoStore()
const cartao = computed(() => cartaoDoTeste(sessao.conta, sessao.pode('assinatura.gerenciar')))
</script>

<template>
  <section
    v-if="cartao"
    class="mb-6 flex flex-col gap-4 rounded-cartao border border-coral-200 bg-marca-suave p-5 sm:flex-row sm:items-center sm:gap-6 dark:border-coral-900"
    aria-labelledby="cartao-teste-titulo"
    data-cartao-teste
  >
    <span class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-superficie text-marca-texto" aria-hidden="true">
      <Sparkles class="size-5" />
    </span>
    <div class="min-w-0 flex-1">
      <h2 id="cartao-teste-titulo" class="text-base font-bold text-texto">Seu teste grátis vai até {{ cartao.data }} (faltam {{ cartao.dias }} dias)</h2>
      <p class="mt-1 text-sm text-texto-suave">
        <template v-if="cartao.plano !== '—'">Você está testando o plano {{ cartao.plano }}, com tudo liberado. </template>
        Assinar agora não encurta o teste: a primeira fatura vence no último dia dele.
      </p>
    </div>
    <Botao para="/assinatura" variante="secundario" class="self-start sm:self-auto">Ver planos</Botao>
  </section>
</template>
