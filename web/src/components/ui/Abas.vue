<script setup lang="ts" generic="T extends string">
import { nextTick, ref, useId } from 'vue'

const props = defineProps<{ abas: { valor: T; rotulo: string }[]; rotulo: string }>()
const modelo = defineModel<T>({ required: true })
const id = useId()
const botoes = ref<HTMLButtonElement[]>([])

function idAba(v: T) {
  return `aba-${id}-${v}`
}
function idPainel(v: T) {
  return `painel-${id}-${v}`
}

async function mover(delta: number) {
  const i = props.abas.findIndex((a) => a.valor === modelo.value)
  const n = (i + delta + props.abas.length) % props.abas.length
  modelo.value = props.abas[n]!.valor
  await nextTick()
  botoes.value[n]?.focus()
}

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'ArrowRight') mover(1)
  else if (e.key === 'ArrowLeft') mover(-1)
  else return
  e.preventDefault()
}

defineExpose({ idAba, idPainel })
</script>

<template>
  <div>
    <div role="tablist" :aria-label="rotulo" class="flex gap-1 overflow-x-auto shadow-[inset_0_-1px_0_var(--color-borda)]" @keydown="aoTeclar">
      <button
        v-for="a in abas"
        :id="idAba(a.valor)"
        :key="a.valor"
        ref="botoes"
        type="button"
        role="tab"
        :aria-selected="modelo === a.valor"
        :aria-controls="idPainel(a.valor)"
        :tabindex="modelo === a.valor ? 0 : -1"
        class="shrink-0 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors"
        :class="modelo === a.valor ? 'border-marca text-texto' : 'border-transparent text-texto-fraco hover:text-texto'"
        @click="modelo = a.valor"
      >
        {{ a.rotulo }}
      </button>
    </div>
    <div :id="idPainel(modelo)" role="tabpanel" :aria-labelledby="idAba(modelo)" tabindex="0" class="pt-6 focus:outline-none">
      <slot :aba="modelo" />
    </div>
  </div>
</template>
