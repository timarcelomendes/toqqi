<script setup lang="ts">
// Busca de empresa (combobox acessível) com opção de criar na hora.
// Sem acesso aos contatos (contatos.ver), não busca nada: mostra o valor atual, com um aviso curto.
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { Building2, LoaderCircle, Plus, Search, X } from 'lucide-vue-next'
import { ApiError, empresasApi, mensagemDoErro, type Empresa, type Referencia } from '@/api'
import { useSessaoStore } from '@/stores/sessao'

const props = withDefaults(
  defineProps<{
    rotulo: string
    podeCriar?: boolean
    erro?: string | null
    placeholder?: string
    rotuloOculto?: boolean
    opcional?: boolean
    /** Outra fonte para a busca (ex.: Relatórios, para quem não vê os contatos). Sem ela, usa a lista de empresas. */
    fonte?: (termo: string, sinal: AbortSignal) => Promise<Referencia[]>
  }>(),
  { placeholder: 'Digite para buscar', fonte: undefined },
)
const modelo = defineModel<Referencia | null>({ required: true })
const emit = defineEmits<{ criada: [Empresa] }>()

const id = `empresa-${useId()}`
const sessao = useSessaoStore()
/** A lista de empresas pede contatos.ver: sem ela (e sem outra fonte), o campo só mostra o valor (e deixa limpar). */
const podeBuscar = computed(() => !!props.fonte || sessao.pode('contatos.ver'))
/** Texto quando não há empresa: nos filtros ("Todas") vale o próprio placeholder. */
const textoVazio = computed(() => (props.placeholder === 'Todas' ? 'Todas' : 'Nenhuma'))
const texto = ref(modelo.value?.nome ?? '')
const aberto = ref(false)
const buscando = ref(false)
const criando = ref(false)
const resultados = ref<Referencia[]>([])
const ativo = ref(-1)
const erroLocal = ref<string | null>(null)
const raiz = ref<HTMLElement | null>(null)
let temporizador: ReturnType<typeof setTimeout> | null = null
let controle: AbortController | null = null

watch(modelo, (m) => {
  texto.value = m?.nome ?? ''
})

const termo = computed(() => texto.value.trim())
const podeOferecerCriar = computed(
  () =>
    props.podeCriar &&
    termo.value.length >= 2 &&
    !resultados.value.some((r) => r.nome.toLocaleLowerCase('pt-BR') === termo.value.toLocaleLowerCase('pt-BR')),
)
const opcoes = computed(() => [
  ...resultados.value.map((r) => ({ tipo: 'empresa' as const, ref: r })),
  ...(podeOferecerCriar.value ? [{ tipo: 'criar' as const, ref: null }] : []),
])

async function buscar() {
  if (!podeBuscar.value) return
  controle?.abort()
  controle = new AbortController()
  buscando.value = true
  try {
    resultados.value = props.fonte
      ? await props.fonte(termo.value, controle.signal)
      : (await empresasApi.listar({ busca: termo.value, por_pagina: 8, ativa: 'todas' }, controle.signal)).itens.map((e) => ({ id: e.id, nome: e.nome }))
    ativo.value = resultados.value.length ? 0 : podeOferecerCriar.value ? 0 : -1
  } catch (e) {
    if (!(e instanceof DOMException)) resultados.value = []
  } finally {
    buscando.value = false
  }
}

function aoDigitar() {
  aberto.value = true
  erroLocal.value = null
  if (modelo.value && texto.value !== modelo.value.nome) modelo.value = null
  if (temporizador) clearTimeout(temporizador)
  temporizador = setTimeout(buscar, 250)
}

function escolher(r: Referencia) {
  modelo.value = r
  texto.value = r.nome
  aberto.value = false
}

async function criar() {
  if (!termo.value || criando.value) return
  criando.value = true
  erroLocal.value = null
  try {
    const e = await empresasApi.criar({ nome: termo.value })
    emit('criada', e)
    escolher({ id: e.id, nome: e.nome })
  } catch (e) {
    erroLocal.value = e instanceof ApiError && e.codigo === 'nome_em_uso' ? 'Já existe uma empresa com esse nome. Escolha na lista.' : mensagemDoErro(e)
  } finally {
    criando.value = false
  }
}

function selecionarAtivo() {
  const o = opcoes.value[ativo.value]
  if (!o) return
  if (o.tipo === 'criar') criar()
  else escolher(o.ref)
}

function aoTeclar(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    if (!aberto.value) {
      aberto.value = true
      buscar()
    } else ativo.value = Math.min(opcoes.value.length - 1, ativo.value + 1)
  } else if (e.key === 'ArrowUp') ativo.value = Math.max(0, ativo.value - 1)
  else if (e.key === 'Enter') {
    if (!aberto.value) return
    selecionarAtivo()
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
</script>

<template>
  <div v-if="!podeBuscar" class="flex flex-col gap-1.5">
    <span :id="`${id}-rotulo`" class="text-sm font-semibold text-texto" :class="{ 'sr-only': rotuloOculto }">
      {{ rotulo }} <span v-if="opcional" class="font-normal text-texto-fraco">(opcional)</span>
    </span>
    <div
      role="group"
      :aria-labelledby="`${id}-rotulo`"
      :aria-describedby="`${id}-sem-acesso`"
      class="flex min-h-11 items-center gap-2 rounded-xl border border-borda bg-superficie-2 pl-3 pr-1.5 text-[0.95rem]"
    >
      <Building2 class="size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
      <span class="min-w-0 flex-1 truncate" :class="modelo ? 'text-texto' : 'text-texto-fraco'">{{ modelo?.nome ?? textoVazio }}</span>
      <button
        v-if="modelo"
        type="button"
        class="flex size-8 shrink-0 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie hover:text-texto"
        :aria-label="`Limpar ${rotulo.toLowerCase()}`"
        @click="limpar"
      >
        <X class="size-4" aria-hidden="true" />
      </button>
    </div>
    <p :id="`${id}-sem-acesso`" class="text-xs text-texto-fraco">Seu perfil não tem acesso à lista de empresas.</p>
    <p v-if="erro" class="text-sm font-medium text-erro">{{ erro }}</p>
  </div>
  <div v-else ref="raiz" class="relative flex flex-col gap-1.5">
    <label :for="id" class="text-sm font-semibold text-texto" :class="{ 'sr-only': rotuloOculto }">
      {{ rotulo }} <span v-if="opcional" class="font-normal text-texto-fraco">(opcional)</span>
    </label>
    <div class="relative flex items-center">
      <span class="pointer-events-none absolute left-3 flex text-texto-fraco">
        <Building2 v-if="modelo" class="size-4" aria-hidden="true" />
        <Search v-else class="size-4" aria-hidden="true" />
      </span>
      <input
        :id="id"
        v-model="texto"
        type="text"
        role="combobox"
        autocomplete="off"
        :aria-expanded="aberto"
        :aria-controls="`${id}-lista`"
        aria-autocomplete="list"
        :aria-activedescendant="aberto && ativo >= 0 ? `${id}-op-${ativo}` : undefined"
        :aria-invalid="erro || erroLocal ? 'true' : undefined"
        :aria-describedby="erro || erroLocal ? `${id}-erro` : undefined"
        :placeholder="placeholder"
        class="h-11 w-full rounded-xl border bg-superficie pl-10 pr-10 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 focus:outline-none focus:ring-3"
        :class="erro || erroLocal ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20'"
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
    <ul
      v-show="aberto && (opcoes.length || buscando || termo)"
      :id="`${id}-lista`"
      role="listbox"
      :aria-label="rotulo"
      class="absolute left-0 right-0 top-full z-40 mt-1 max-h-64 overflow-y-auto rounded-xl border border-borda bg-superficie p-1.5 shadow-lg"
    >
      <li v-if="buscando && !opcoes.length" class="flex items-center gap-2 px-3 py-2 text-sm text-texto-fraco">
        <LoaderCircle class="size-4 animate-spin" aria-hidden="true" /> Buscando…
      </li>
      <li v-else-if="!opcoes.length" class="px-3 py-2 text-sm text-texto-fraco">Nenhuma empresa encontrada.</li>
      <li
        v-for="(o, i) in opcoes"
        :id="`${id}-op-${i}`"
        :key="o.tipo === 'empresa' ? String(o.ref.id) : 'criar'"
        role="option"
        :aria-selected="i === ativo"
        class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm"
        :class="i === ativo ? 'bg-superficie-2 text-texto' : 'text-texto-suave'"
        @mousedown.prevent="o.tipo === 'criar' ? criar() : escolher(o.ref)"
        @mousemove="ativo = i"
      >
        <template v-if="o.tipo === 'empresa'">
          <Building2 class="size-4 shrink-0 text-texto-fraco" aria-hidden="true" /> {{ o.ref.nome }}
        </template>
        <template v-else>
          <LoaderCircle v-if="criando" class="size-4 animate-spin" aria-hidden="true" />
          <Plus v-else class="size-4 text-marca-texto" aria-hidden="true" />
          <span class="font-semibold text-marca-texto">Criar empresa “{{ termo }}”</span>
        </template>
      </li>
    </ul>
    <p v-if="erro || erroLocal" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erroLocal ?? erro }}</p>
  </div>
</template>
