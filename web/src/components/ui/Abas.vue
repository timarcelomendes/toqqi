<script setup lang="ts" generic="T extends string">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

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

// Com muitas abas (lista rolável no celular), a aba ativa fica sempre à vista: rola só a lista, nunca a página.
const lista = ref<HTMLElement | null>(null)
function mostrarAtiva() {
  const l = lista.value
  const el = botoes.value[props.abas.findIndex((a) => a.valor === modelo.value)]
  if (!l || !el || l.scrollWidth <= l.clientWidth) return
  const r = el.getBoundingClientRect()
  const rl = l.getBoundingClientRect()
  if (r.left < rl.left + 24) l.scrollLeft -= rl.left - r.left + 32
  else if (r.right > rl.right - 24) l.scrollLeft += r.right - rl.right + 32
  medir()
}

// A borda que tem mais abas escondidas fica esmaecida (sinal de que a lista rola para o lado).
const sobra = ref({ esq: false, dir: false })
function medir() {
  const l = lista.value
  if (!l) return
  const esq = l.scrollLeft > 1
  const dir = l.scrollLeft + l.clientWidth < l.scrollWidth - 1
  if (esq !== sobra.value.esq || dir !== sobra.value.dir) sobra.value = { esq, dir }
}
const mascara = computed(() => {
  const { esq, dir } = sobra.value
  if (!esq && !dir) return undefined
  const g = `linear-gradient(to right, ${esq ? 'transparent, #000 2rem' : '#000'}, ${dir ? '#000 calc(100% - 2rem), transparent' : '#000'})`
  return { maskImage: g, WebkitMaskImage: g }
})
let observador: ResizeObserver | null = null
watch(modelo, () => nextTick(mostrarAtiva))
onMounted(() => {
  mostrarAtiva()
  medir()
  if (typeof ResizeObserver !== 'undefined' && lista.value) {
    observador = new ResizeObserver(medir)
    observador.observe(lista.value)
  }
})
onBeforeUnmount(() => observador?.disconnect())

defineExpose({ idAba, idPainel })
</script>

<template>
  <div>
    <div
      ref="lista"
      role="tablist"
      :aria-label="rotulo"
      class="flex gap-1 overflow-x-auto shadow-[inset_0_-1px_0_var(--color-borda)]"
      :style="mascara"
      @keydown="aoTeclar"
      @scroll.passive="medir"
    >
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
