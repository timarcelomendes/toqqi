<script setup lang="ts">
// A resposta do assistente montada só com nós de texto (nunca HTML): parágrafos com as quebras de linha e as linhas
// que começam com "- " como lista.
import { computed } from 'vue'
import { blocosDoTexto } from './logica'

const props = defineProps<{ texto: string }>()
const blocos = computed(() => blocosDoTexto(props.texto))
</script>

<template>
  <div class="flex flex-col gap-2" data-texto>
    <template v-for="(b, i) in blocos" :key="i">
      <ul v-if="b.tipo === 'lista'" class="flex list-disc flex-col gap-1 pl-5 marker:text-texto-fraco">
        <li v-for="(item, j) in b.itens" :key="j">{{ item }}</li>
      </ul>
      <p v-else class="whitespace-pre-line">{{ b.linhas.join('\n') }}</p>
    </template>
  </div>
</template>
