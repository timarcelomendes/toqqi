<script setup lang="ts" generic="T extends string">
// Escolha de uma opção entre poucas, todas à vista, com cara de botões lado a lado (ex.: Motorista / Rota / Filial).
// São rádios nativos: o Tab entra na opção escolhida e as setas trocam a opção (sem código de teclado próprio).
import { useId } from 'vue'

withDefaults(
  defineProps<{
    opcoes: readonly { valor: T; rotulo: string }[]
    /** Nome do grupo para leitores de tela (legenda do fieldset). */
    rotulo: string
    /** Ocupa a largura toda no celular (as opções dividem o espaço). */
    bloco?: boolean
    desabilitado?: boolean
  }>(),
  { bloco: false, desabilitado: false },
)
const modelo = defineModel<T>({ required: true })
const nome = `segmentado-${useId()}`
</script>

<template>
  <fieldset class="m-0 min-w-0 border-0 p-0" :class="bloco ? 'w-full sm:w-fit' : 'w-fit'">
    <legend class="sr-only">{{ rotulo }}</legend>
    <div class="flex flex-wrap rounded-xl border border-borda-forte p-0.5">
      <label v-for="o in opcoes" :key="o.valor" class="relative flex" :class="bloco ? 'flex-1 sm:flex-none' : ''">
        <input v-model="modelo" type="radio" :name="nome" :value="o.valor" class="peer sr-only" :disabled="desabilitado" />
        <span
          class="flex h-10 w-full cursor-pointer items-center justify-center whitespace-nowrap rounded-[0.6rem] px-4 text-sm font-semibold text-texto-fraco transition-colors hover:text-texto peer-disabled:cursor-not-allowed peer-disabled:opacity-60 peer-checked:bg-marca-suave peer-checked:text-marca-texto peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-foco"
        >
          {{ o.rotulo }}
        </span>
      </label>
    </div>
  </fieldset>
</template>
