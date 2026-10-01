<script setup lang="ts">
// Busca de contato (combobox acessível): digite o nome, o e-mail ou a empresa e escolha na lista.
// Sem acesso aos contatos (contatos.ver), não busca nada: mostra o contato já escolhido, com um aviso curto.
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { LoaderCircle, Search, UserRound, X } from 'lucide-vue-next'
import { contatosApi, type Id, type Referencia } from '@/api'
import { useSessaoStore } from '@/stores/sessao'

export interface ContatoEscolhido {
  id: Id
  nome: string
  email?: string | null
  empresa?: Referencia | null
}

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{ rotulo: string; erro?: string | null; placeholder?: string; dica?: string; obrigatorio?: boolean }>(),
  { placeholder: 'Digite o nome, o e-mail ou a empresa', erro: null, dica: undefined },
)
const modelo = defineModel<ContatoEscolhido | null>({ required: true })

const id = `contato-${useId()}`
const sessao = useSessaoStore()
const podeBuscar = computed(() => sessao.pode('contatos.ver'))
const texto = ref(modelo.value?.nome ?? '')
const aberto = ref(false)
const buscando = ref(false)
const erroBusca = ref<string | null>(null)
const resultados = ref<ContatoEscolhido[]>([])
const ativo = ref(-1)
const raiz = ref<HTMLElement | null>(null)
const entrada = ref<HTMLInputElement | null>(null)
let temporizador: ReturnType<typeof setTimeout> | null = null
let controle: AbortController | null = null

watch(modelo, (m) => {
  texto.value = m?.nome ?? ''
})

const termo = computed(() => texto.value.trim())

async function buscar() {
  if (!podeBuscar.value) return
  controle?.abort()
  controle = new AbortController()
  buscando.value = true
  erroBusca.value = null
  try {
    const r = await contatosApi.listar({ busca: termo.value, por_pagina: 8, ativo: 'todos' }, controle.signal)
    resultados.value = r.itens.map((c) => ({ id: c.id, nome: c.nome, email: c.email, empresa: c.empresa }))
    ativo.value = resultados.value.length ? 0 : -1
  } catch (e) {
    if (e instanceof DOMException) return
    resultados.value = []
    erroBusca.value = 'Não deu para buscar os contatos agora. Tente de novo.'
  } finally {
    buscando.value = false
  }
}

function aoDigitar() {
  aberto.value = true
  if (modelo.value && texto.value !== modelo.value.nome) modelo.value = null
  if (temporizador) clearTimeout(temporizador)
  temporizador = setTimeout(buscar, 250)
}

function escolher(c: ContatoEscolhido) {
  modelo.value = c
  texto.value = c.nome
  aberto.value = false
}

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    if (!aberto.value) {
      aberto.value = true
      buscar()
    } else ativo.value = Math.min(resultados.value.length - 1, ativo.value + 1)
  } else if (e.key === 'ArrowUp') ativo.value = Math.max(0, ativo.value - 1)
  else if (e.key === 'Enter') {
    if (!aberto.value) return
    const c = resultados.value[ativo.value]
    if (c) escolher(c)
  } else if (e.key === 'Escape') {
    if (!aberto.value) return
    e.stopPropagation()
    aberto.value = false
  } else return
  e.preventDefault()
}

function limpar() {
  modelo.value = null
  texto.value = ''
  resultados.value = []
  entrada.value?.focus()
}

function aoFocar() {
  if (!modelo.value) {
    aberto.value = true
    buscar()
  }
}

function cliqueFora(e: MouseEvent) {
  if (raiz.value && !raiz.value.contains(e.target as Node)) {
    aberto.value = false
    if (!modelo.value) texto.value = ''
  }
}
document.addEventListener('mousedown', cliqueFora)
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', cliqueFora)
  controle?.abort()
  if (temporizador) clearTimeout(temporizador)
})

defineExpose({ focar: () => entrada.value?.focus() })
</script>

<template>
  <div v-if="!podeBuscar" class="flex flex-col gap-1.5" :class="$attrs.class">
    <span :id="`${id}-rotulo`" class="text-sm font-semibold text-texto">{{ rotulo }}</span>
    <div
      role="group"
      :aria-labelledby="`${id}-rotulo`"
      :aria-describedby="`${id}-sem-acesso`"
      class="flex min-h-11 items-center gap-2 rounded-xl border border-borda bg-superficie-2 px-3 text-[0.95rem]"
    >
      <UserRound class="size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
      <span class="min-w-0 flex-1 truncate" :class="modelo ? 'text-texto' : 'text-texto-fraco'">{{ modelo?.nome ?? 'Nenhum' }}</span>
    </div>
    <p :id="`${id}-sem-acesso`" class="text-xs text-texto-fraco">Seu perfil não tem acesso à lista de contatos.</p>
    <p v-if="erro" class="text-sm font-medium text-erro">{{ erro }}</p>
  </div>
  <div v-else ref="raiz" class="relative flex flex-col gap-1.5" :class="$attrs.class">
    <label :for="id" class="text-sm font-semibold text-texto">{{ rotulo }}</label>
    <div class="relative flex items-center">
      <span class="pointer-events-none absolute left-3 flex text-texto-fraco">
        <UserRound v-if="modelo" class="size-4" aria-hidden="true" />
        <Search v-else class="size-4" aria-hidden="true" />
      </span>
      <input
        v-bind="{ ...$attrs, class: undefined }"
        :id="id"
        ref="entrada"
        v-model="texto"
        type="text"
        role="combobox"
        autocomplete="off"
        :required="obrigatorio"
        :aria-expanded="aberto"
        :aria-controls="`${id}-lista`"
        aria-autocomplete="list"
        :aria-activedescendant="aberto && ativo >= 0 ? `${id}-op-${ativo}` : undefined"
        :aria-invalid="erro ? 'true' : undefined"
        :aria-describedby="[erro ? `${id}-erro` : '', dica ? `${id}-dica` : ''].join(' ').trim() || undefined"
        :placeholder="placeholder"
        class="h-11 w-full rounded-xl border bg-superficie pl-10 pr-10 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 focus:outline-none focus:ring-3"
        :class="erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20'"
        @input="aoDigitar"
        @keydown="aoTeclar"
        @focus="aoFocar"
      />
      <button
        v-if="texto"
        type="button"
        class="absolute right-1.5 flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto"
        :aria-label="`Limpar ${rotulo.toLowerCase()}`"
        @click="limpar"
      >
        <X class="size-4" aria-hidden="true" />
      </button>
    </div>
    <p v-if="modelo && (modelo.email || modelo.empresa)" class="truncate text-xs text-texto-fraco">
      {{ [modelo.email, modelo.empresa?.nome].filter(Boolean).join(' · ') }}
    </p>
    <ul
      v-show="aberto"
      :id="`${id}-lista`"
      role="listbox"
      :aria-label="rotulo"
      class="absolute left-0 right-0 top-[4.6rem] z-40 max-h-64 overflow-y-auto rounded-xl border border-borda bg-superficie p-1.5 shadow-lg"
    >
      <li v-if="buscando && !resultados.length" class="flex items-center gap-2 px-3 py-2 text-sm text-texto-fraco">
        <LoaderCircle class="size-4 animate-spin" aria-hidden="true" /> Buscando…
      </li>
      <li v-else-if="erroBusca" class="px-3 py-2 text-sm text-erro">{{ erroBusca }}</li>
      <li v-else-if="!resultados.length" class="px-3 py-2 text-sm text-texto-fraco">
        Nenhum contato encontrado. Cadastre o contato antes em Contatos.
      </li>
      <li
        v-for="(c, i) in resultados"
        :id="`${id}-op-${i}`"
        :key="String(c.id)"
        role="option"
        :aria-selected="i === ativo"
        class="flex min-h-11 cursor-pointer flex-col justify-center rounded-lg px-3 py-1.5 text-sm"
        :class="i === ativo ? 'bg-superficie-2' : ''"
        @mousedown.prevent="escolher(c)"
        @mousemove="ativo = i"
      >
        <span class="font-semibold text-texto">{{ c.nome }}</span>
        <span v-if="c.email || c.empresa" class="truncate text-xs text-texto-fraco">{{ [c.email, c.empresa?.nome].filter(Boolean).join(' · ') }}</span>
      </li>
    </ul>
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
  </div>
</template>
