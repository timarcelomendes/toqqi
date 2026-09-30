<script setup lang="ts">
// Campo de texto com botões para inserir {empresa}, {nome}, {assunto} e {referencia} onde está o cursor.
import { computed, nextTick, ref, useId } from 'vue'
import { VARIAVEIS_DISPONIVEIS } from '@/pesquisa/variaveis'

const props = withDefaults(
  defineProps<{
    rotulo: string
    multilinha?: boolean
    erro?: string | null
    dica?: string
    opcional?: boolean
    maximo?: number
    placeholder?: string
    semVariaveis?: boolean
  }>(),
  { maximo: 500 },
)
const modelo = defineModel<string | null | undefined>({ default: '' })
const id = `cv-${useId()}`
const el = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)
const descritoPor = computed(() => [props.erro ? `${id}-erro` : '', props.dica ? `${id}-dica` : ''].filter(Boolean).join(' ') || undefined)

async function inserir(variavel: string) {
  const alvo = el.value
  const atual = modelo.value ?? ''
  const ini = alvo?.selectionStart ?? atual.length
  const fim = alvo?.selectionEnd ?? atual.length
  modelo.value = atual.slice(0, ini) + variavel + atual.slice(fim)
  await nextTick()
  alvo?.focus()
  alvo?.setSelectionRange(ini + variavel.length, ini + variavel.length)
}

function aoDigitar(e: Event) {
  modelo.value = (e.target as HTMLInputElement).value
}

const classes =
  'w-full rounded-xl border bg-superficie px-3.5 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 transition-colors focus:outline-none focus:ring-3 disabled:cursor-not-allowed disabled:bg-superficie-2'
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label :for="id" class="text-sm font-semibold text-texto">
      {{ rotulo }} <span v-if="opcional" class="font-normal text-texto-fraco">(opcional)</span>
    </label>
    <textarea
      v-if="multilinha"
      :id="id"
      ref="el"
      :value="modelo ?? ''"
      rows="3"
      :maxlength="maximo"
      :placeholder="placeholder"
      :aria-invalid="erro ? 'true' : undefined"
      :aria-describedby="descritoPor"
      :class="[classes, 'resize-y py-2.5', erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20']"
      @input="aoDigitar"
    />
    <input
      v-else
      :id="id"
      ref="el"
      type="text"
      :value="modelo ?? ''"
      :maxlength="maximo"
      :placeholder="placeholder"
      :aria-invalid="erro ? 'true' : undefined"
      :aria-describedby="descritoPor"
      :class="[classes, 'h-11', erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20']"
      @input="aoDigitar"
    />
    <div v-if="!semVariaveis" class="flex flex-wrap items-center gap-1.5" role="group" :aria-label="`Inserir variável em ${rotulo}`">
      <span class="text-xs text-texto-fraco">Inserir:</span>
      <button
        v-for="v in VARIAVEIS_DISPONIVEIS"
        :key="v.chave"
        type="button"
        class="rounded-md bg-superficie-2 px-2 py-0.5 font-mono text-xs font-semibold text-texto-suave hover:bg-borda hover:text-texto"
        :title="v.rotulo"
        :aria-label="`Inserir ${v.exemplo}: ${v.rotulo}`"
        @click="inserir(v.exemplo)"
      >
        {{ v.exemplo }}
      </button>
    </div>
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
  </div>
</template>
