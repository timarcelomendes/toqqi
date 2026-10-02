<script setup lang="ts" generic="C">
// Rodapé do resumo e do parecer (etapa 5d): quando, por quem e com qual modelo foi gerado; depois de gerar, quantas
// análises da cota restam no mês.
import { textoCota, textoGerado } from './logica'
import type { GeracaoIa } from './usarGeracaoIa'

defineProps<{ geracao: GeracaoIa<C> }>()
</script>

<template>
  <div v-if="geracao.item && !geracao.gerando && !geracao.erroLeitura" class="flex min-w-0 flex-col gap-0.5 text-xs text-texto-fraco" data-meta>
    <p data-gerado>{{ textoGerado(geracao.item) }}</p>
    <p v-if="geracao.cota" data-restam>{{ textoCota(geracao.cota) }}</p>
  </div>
</template>
