<script setup lang="ts">
// Selo do sentimento geral do comentário, pela IA (só quando a resposta já foi analisada). A palavra vai escrita: a cor só reforça.
import { computed } from 'vue'
import type { AnaliseIa } from '@/api/tipos'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { SENTIMENTOS, analisada, ehSentimento } from './ia'

const props = defineProps<{ ia: AnaliseIa | null | undefined }>()
const sentimento = computed(() => (analisada(props.ia) && ehSentimento(props.ia.sentimento) ? SENTIMENTOS[props.ia.sentimento] : null))
</script>

<template>
  <Etiqueta v-if="sentimento" :tom="sentimento.tom" ponto title="Sentimento do comentário, pela análise da IA" data-sentimento>
    <span class="sr-only">Sentimento pela IA: </span>{{ sentimento.rotulo }}
  </Etiqueta>
</template>
