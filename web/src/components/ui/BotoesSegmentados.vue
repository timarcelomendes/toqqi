<script setup lang="ts" generic="T extends string">
// Escolha de uma opção entre poucas, todas à vista, com cara de botões lado a lado (ex.: Motorista / Rota / Filial).
// São rádios nativos: o Tab entra na opção escolhida e as setas trocam a opção (sem código de teclado próprio).
// Cores (13/10/2026, pedido do Marcelo): trilho cinza e a opção escolhida em destaque (clara e com sombra no tema
// claro, mais clara que o trilho no escuro); as outras em texto médio, legível. O selo opcional ("10% off") fica em
// verde, a cor de economia, nas duas.
import { useId } from 'vue'

withDefaults(
  defineProps<{
    /** `selo`: destaque curto ao lado do nome (ex.: "10% off"); o leitor de tela ouve "Anual, 10% off". */
    opcoes: readonly { valor: T; rotulo: string; selo?: string }[]
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
    <div class="flex flex-wrap gap-1 rounded-xl bg-slate-200/70 p-1 dark:bg-superficie-2" data-trilho>
      <label v-for="o in opcoes" :key="o.valor" class="relative flex" :class="bloco ? 'flex-1 sm:flex-none' : ''">
        <input v-model="modelo" type="radio" :name="nome" :value="o.valor" class="peer sr-only" :disabled="desabilitado" />
        <span
          class="flex h-9 w-full cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3.5 text-sm font-semibold text-texto-suave transition-[color,background-color,box-shadow] hover:bg-superficie/50 hover:text-texto peer-checked:bg-superficie peer-checked:text-texto peer-checked:shadow-sm peer-checked:ring-1 peer-checked:ring-black/5 peer-disabled:cursor-not-allowed peer-disabled:opacity-60 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-foco dark:hover:bg-borda-forte/50 dark:peer-checked:bg-borda-forte dark:peer-checked:ring-0"
        >
          {{ o.rotulo }}
          <template v-if="o.selo">
            <span class="sr-only">, </span>
            <span class="rounded-full bg-sucesso-suave px-2 py-0.5 text-xs font-bold text-sucesso" data-selo>{{ o.selo }}</span>
          </template>
        </span>
      </label>
    </div>
  </fieldset>
</template>
