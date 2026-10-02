<script setup lang="ts">
// Um e-mail em coluna estreita: a linha quebra depois do "@" e dos pontos (<wbr> entre as partes, sem v-html) e só
// em último caso no meio de uma parte (overflow-wrap: anywhere), em vez do break-all, que corta no meio da palavra.
import { computed } from 'vue'
import { partesEmail } from '@/utils/formatos'

const props = defineProps<{ email: string }>()
const partes = computed(() => partesEmail(props.email))
</script>

<template>
  <span class="[overflow-wrap:anywhere]" data-email>{{ partes[0] }}<template v-for="(parte, i) in partes.slice(1)" :key="i"><wbr />{{ parte }}</template></span>
</template>
