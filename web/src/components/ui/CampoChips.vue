<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { X } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    rotulo: string
    placeholder?: string
    dica?: string
    erro?: string | null
    /** Erros por item (índice → mensagem). */
    errosItens?: Record<number, string>
    /** Normaliza o texto antes de adicionar. */
    normalizar?: (v: string) => string
    /** Validação local; retorna mensagem de erro ou null. */
    validar?: (v: string) => string | null
  }>(),
  { placeholder: 'Digite e aperte Enter' },
)

const itens = defineModel<string[]>({ required: true })
const texto = ref('')
const erroLocal = ref<string | null>(null)
const id = `chips-${useId()}`
const entrada = ref<HTMLInputElement | null>(null)
const anuncio = ref('')

const erroMostrado = computed(() => erroLocal.value ?? props.erro ?? null)

function adicionar(): boolean {
  const partes = texto.value.split(/[\s,;]+/).map((p) => (props.normalizar ? props.normalizar(p) : p.trim())).filter(Boolean)
  if (!partes.length) return false
  const novos = [...itens.value]
  for (const p of partes) {
    const msg = props.validar?.(p) ?? null
    if (msg) {
      erroLocal.value = msg
      texto.value = p
      return false
    }
    if (!novos.includes(p)) novos.push(p)
  }
  itens.value = novos
  anuncio.value = `${partes.join(', ')} adicionado.`
  texto.value = ''
  erroLocal.value = null
  return true
}

function remover(i: number) {
  const item = itens.value[i]
  itens.value = itens.value.filter((_, j) => j !== i)
  anuncio.value = `${item} removido.`
  entrada.value?.focus()
}

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',' || e.key === ';' || (e.key === ' ' && texto.value.trim())) {
    e.preventDefault()
    adicionar()
  } else if (e.key === 'Backspace' && !texto.value && itens.value.length) {
    remover(itens.value.length - 1)
  }
}

defineExpose({ adicionar, pendente: () => texto.value.trim() })
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label :for="id" class="text-sm font-semibold text-texto">{{ rotulo }}</label>
    <div
      class="flex min-h-11 flex-wrap items-center gap-1.5 rounded-xl border bg-superficie p-1.5 transition-colors focus-within:ring-3"
      :class="erroMostrado ? 'border-erro focus-within:ring-erro/20' : 'border-borda-forte focus-within:border-marca focus-within:ring-marca/20'"
      @click="entrada?.focus()"
    >
      <ul v-if="itens.length" class="contents" :aria-label="`${rotulo}: itens`">
        <li
          v-for="(item, i) in itens"
          :key="item"
          class="flex items-center gap-1 rounded-lg py-1 pl-2.5 pr-1 text-sm font-medium"
          :class="errosItens?.[i] ? 'bg-erro-suave text-erro ring-1 ring-erro/40' : 'bg-superficie-2 text-texto'"
          :title="errosItens?.[i]"
        >
          {{ item }}
          <button
            type="button"
            class="flex size-6 items-center justify-center rounded-md text-texto-fraco hover:bg-borda hover:text-texto"
            :aria-label="`Remover ${item}`"
            @click.stop="remover(i)"
          >
            <X class="size-3.5" aria-hidden="true" />
          </button>
        </li>
      </ul>
      <input
        :id="id"
        ref="entrada"
        v-model="texto"
        type="text"
        inputmode="url"
        autocapitalize="off"
        autocomplete="off"
        spellcheck="false"
        :placeholder="itens.length ? '' : placeholder"
        :aria-invalid="erroMostrado ? 'true' : undefined"
        :aria-describedby="[erroMostrado ? `${id}-erro` : '', dica ? `${id}-dica` : ''].join(' ').trim() || undefined"
        class="h-8 min-w-[10rem] flex-1 bg-transparent px-2 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 focus:outline-none"
        @keydown="aoTeclar"
        @blur="adicionar"
      />
    </div>
    <p v-if="erroMostrado" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erroMostrado }}</p>
    <ul v-if="errosItens && Object.keys(errosItens).length" class="text-sm text-erro">
      <li v-for="(msg, i) in errosItens" :key="i"><strong>{{ itens[Number(i)] }}</strong>: {{ msg }}</li>
    </ul>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
  </div>
</template>
