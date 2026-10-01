<script setup lang="ts">
// Situação de uma ação ("A fazer", "Em andamento", "Concluída") e o selo do prazo quando ainda está aberta.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { AcaoDaResposta } from '@/api/tipos'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { SITUACOES_ACAO, seloPrazo } from './logica'

const props = withDefaults(defineProps<{ acao: AcaoDaResposta; link?: boolean; compacto?: boolean }>(), { link: false, compacto: false })

const situacao = computed(() => SITUACOES_ACAO[props.acao.situacao] ?? { rotulo: props.acao.situacao, tom: 'neutro' as const })
const selo = computed(() => seloPrazo(props.acao))
</script>

<template>
  <component
    :is="link ? RouterLink : 'span'"
    :to="link ? `/planos-de-acao/${acao.id}` : undefined"
    class="inline-flex max-w-full flex-wrap items-center gap-1"
    :class="link ? 'rounded-lg hover:opacity-80' : ''"
    :title="link ? 'Abrir a ação' : undefined"
  >
    <Etiqueta :tom="situacao.tom">{{ situacao.rotulo }}</Etiqueta>
    <Etiqueta v-if="selo && selo.tipo !== 'data'" :tom="selo.tom" ponto>{{ selo.rotulo }}</Etiqueta>
    <span v-else-if="selo && !compacto" class="text-xs text-texto-fraco">{{ selo.rotulo }}</span>
  </component>
</template>
