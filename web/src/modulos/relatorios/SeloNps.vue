<script setup lang="ts">
// NPS de um bloco: o número (na cor da faixa) e o nome da faixa escrito; sem respostas, "Sem respostas".
import { computed } from 'vue'
import type { NpsResumo } from '@/api/tipos'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { faixaNps, formatarNps, tomNps } from '@/modulos/painel/logica'

const props = withDefaults(defineProps<{ nps: NpsResumo | null | undefined; compacto?: boolean; semRespostas?: string }>(), {
  compacto: false,
  semRespostas: 'Sem respostas',
})

const tem = computed(() => !!props.nps && props.nps.total > 0 && typeof props.nps.valor === 'number')
const faixa = computed(() => (tem.value ? faixaNps(props.nps!.faixa, props.nps!.valor) : null))
const COR = { sucesso: 'text-sucesso', atencao: 'text-atencao', erro: 'text-erro' } as const
const cor = computed(() => (tem.value ? (COR[tomNps(props.nps!.valor) as keyof typeof COR] ?? 'text-texto') : 'text-texto'))
</script>

<template>
  <span v-if="tem" class="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
    <span class="text-base font-bold tabular-nums" :class="cor"><span class="sr-only">NPS </span>{{ formatarNps(nps!.valor) }}</span>
    <Etiqueta v-if="faixa && !compacto" :tom="faixa.tom">{{ faixa.rotulo }}</Etiqueta>
    <span v-else-if="faixa" class="sr-only">{{ faixa.rotulo }}</span>
  </span>
  <span v-else class="text-sm text-texto-fraco">{{ semRespostas }}</span>
</template>
