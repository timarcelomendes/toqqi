<script setup lang="ts">
// Etapa 5i: selo da saúde da conta (ícone + texto + nota; a cor nunca é a única pista).
import { computed } from 'vue'
import { CircleAlert, CircleCheck, CircleDashed, TriangleAlert } from 'lucide-vue-next'
import type { FaixaSaude } from '@/api'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { infoFaixa } from './logica'

const props = defineProps<{ faixa: FaixaSaude; nota: number | null }>()
const ICONES = { risco: CircleAlert, atencao: TriangleAlert, saudavel: CircleCheck, sem_dados: CircleDashed }
const info = computed(() => infoFaixa(props.faixa))
</script>

<template>
  <Etiqueta :tom="info.tom">
    <component :is="ICONES[faixa]" class="size-3.5" aria-hidden="true" />
    {{ info.rotulo }}<template v-if="nota !== null"> · {{ nota }}</template>
  </Etiqueta>
</template>
