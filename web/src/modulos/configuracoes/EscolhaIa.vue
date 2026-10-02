<script setup lang="ts">
// Uma escolha entre poucas opções com rótulo e descrição, em cartões (Configurações › IA: modelo e estilo). São rádios
// nativos: o Tab entra na opção escolhida e as setas trocam (cada troca é salva por quem usa, no `update:modelValue`).
import { useId } from 'vue'
import { CircleCheck, Circle } from 'lucide-vue-next'
import type { OpcaoIa } from '@/api'

defineProps<{
  legenda: string
  opcoes: readonly OpcaoIa[]
  desabilitado?: boolean
}>()
const modelo = defineModel<string>({ required: true })
const nome = `escolha-ia-${useId()}`
</script>

<template>
  <fieldset class="m-0 min-w-0 border-0 p-0" :disabled="desabilitado">
    <legend class="mb-2 text-sm font-semibold text-texto">{{ legenda }}</legend>
    <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
      <label
        v-for="o in opcoes"
        :key="o.valor"
        class="relative flex min-w-0 gap-2.5 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
        :class="[
          modelo === o.valor ? 'border-marca bg-marca-suave' : 'border-borda-forte',
          desabilitado ? 'cursor-not-allowed' : 'cursor-pointer',
          desabilitado && modelo !== o.valor ? 'opacity-60' : '',
          !desabilitado && modelo !== o.valor ? 'hover:bg-superficie-2' : '',
        ]"
        :data-opcao="o.valor"
      >
        <input v-model="modelo" type="radio" :name="nome" :value="o.valor" class="sr-only" />
        <CircleCheck v-if="modelo === o.valor" class="mt-0.5 size-4 shrink-0 text-marca-texto" aria-hidden="true" />
        <Circle v-else class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
        <!-- O espaço entre o rótulo e a descrição separa as duas no nome lido pelo leitor de tela. -->
        <span class="flex min-w-0 flex-col gap-0.5">
          <span class="text-sm font-bold text-texto">{{ o.rotulo }}</span>{{ ' ' }}<span class="text-xs text-texto-suave">{{ o.descricao }}</span>
        </span>
      </label>
    </div>
  </fieldset>
</template>
