<script setup lang="ts">
// Os problemas do item no topo da edição (docs/api-etapa-5l.md §5.3); os da lógica também aparecem em cada linha.
import { computed } from 'vue'
import { AlertTriangle, CircleAlert } from 'lucide-vue-next'
import type { Problema } from '../validacaoFormulario'

const props = defineProps<{ problemas: Problema[] }>()
const erros = computed(() => props.problemas.filter((p) => !p.aviso))
const avisos = computed(() => props.problemas.filter((p) => p.aviso))
</script>

<template>
  <div v-if="problemas.length" class="flex flex-col gap-2" data-problemas-item>
    <div v-if="erros.length" class="flex gap-2.5 rounded-xl border border-erro/25 bg-erro-suave p-3 text-sm">
      <CircleAlert class="mt-0.5 size-4 shrink-0 text-erro" aria-hidden="true" />
      <div class="min-w-0">
        <p class="font-semibold text-erro">{{ erros.length === 1 ? 'Este item precisa de um ajuste' : `Este item precisa de ${erros.length} ajustes` }}</p>
        <ul class="mt-0.5 list-disc pl-4 text-texto-suave">
          <li v-for="(p, i) in erros" :key="i">{{ p.mensagem }}</li>
        </ul>
      </div>
    </div>
    <div v-if="avisos.length" class="flex gap-2.5 rounded-xl border border-atencao/25 bg-atencao-suave p-3 text-sm">
      <AlertTriangle class="mt-0.5 size-4 shrink-0 text-atencao" aria-hidden="true" />
      <ul class="min-w-0 text-texto-suave">
        <li v-for="(p, i) in avisos" :key="i">{{ p.mensagem }}</li>
      </ul>
    </div>
  </div>
</template>
