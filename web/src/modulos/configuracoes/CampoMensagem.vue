<script setup lang="ts">
// Campo de texto de mensagem com botões que inserem {nome}, {empresa}... onde está o cursor.
import { computed, nextTick, ref, useId } from 'vue'
import { inserirNoCursor, type VariavelMensagem } from './mensagens'

const props = withDefaults(
  defineProps<{
    rotulo: string
    variaveis: VariavelMensagem[]
    multilinha?: boolean
    linhas?: number
    erro?: string | null
    dica?: string
    maximo?: number
    placeholder?: string
  }>(),
  { linhas: 5, maximo: 2000 },
)
const modelo = defineModel<string>({ default: '' })
const id = `cm-${useId()}`
const el = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)
const descritoPor = computed(
  () => [props.erro ? `${id}-erro` : '', props.dica ? `${id}-dica` : '', `${id}-contagem`].filter(Boolean).join(' ') || undefined,
)
const perto = computed(() => modelo.value.length > props.maximo * 0.9)

async function inserir(v: VariavelMensagem) {
  const alvo = el.value
  const r = inserirNoCursor(modelo.value ?? '', v.texto, alvo?.selectionStart, alvo?.selectionEnd)
  modelo.value = r.texto
  await nextTick()
  alvo?.focus()
  alvo?.setSelectionRange(r.cursor, r.cursor)
}

const classes =
  'w-full rounded-xl border bg-superficie px-3.5 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 transition-colors focus:outline-none focus:ring-3 disabled:cursor-not-allowed disabled:bg-superficie-2 disabled:text-texto-suave'
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-end justify-between gap-2">
      <label :for="id" class="text-sm font-semibold text-texto">{{ rotulo }}</label>
      <span :id="`${id}-contagem`" class="text-xs tabular-nums" :class="perto ? 'text-atencao' : 'text-texto-fraco'">
        <span class="sr-only">Caracteres usados: </span>{{ modelo.length }}/{{ maximo }}
      </span>
    </div>
    <textarea
      v-if="multilinha"
      :id="id"
      ref="el"
      v-model="modelo"
      :rows="linhas"
      :maxlength="maximo"
      :placeholder="placeholder"
      :aria-invalid="erro ? 'true' : undefined"
      :aria-describedby="descritoPor"
      :class="[classes, 'resize-y py-2.5 leading-relaxed', erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20']"
    />
    <input
      v-else
      :id="id"
      ref="el"
      v-model="modelo"
      type="text"
      :maxlength="maximo"
      :placeholder="placeholder"
      :aria-invalid="erro ? 'true' : undefined"
      :aria-describedby="descritoPor"
      :class="[classes, 'h-11', erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20']"
    />
    <div class="flex flex-wrap items-center gap-1.5" role="group" :aria-label="`Inserir informação em ${rotulo}`">
      <span class="text-xs text-texto-fraco">Inserir:</span>
      <button
        v-for="v in variaveis"
        :key="v.chave"
        type="button"
        class="rounded-md bg-superficie-2 px-2 py-1 font-mono text-xs font-semibold text-texto-suave transition-colors hover:bg-borda hover:text-texto disabled:cursor-not-allowed disabled:opacity-60"
        :title="v.rotulo"
        :aria-label="`Inserir ${v.texto}: ${v.rotulo}`"
        @click="inserir(v)"
      >
        {{ v.texto }}
      </button>
    </div>
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
  </div>
</template>
