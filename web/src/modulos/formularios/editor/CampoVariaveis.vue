<script setup lang="ts">
// Campo de texto do editor com o menu "Inserir" (variáveis e, etapa 5l, respostas anteriores `{{id}}`), contador e a
// linha "Assim aparece:" (variáveis de exemplo e citações como "[resposta de P2]"). O texto entra onde está o cursor.
import { computed, nextTick, ref, useId } from 'vue'
import type { Pergunta } from '@/api/tipos'
import { renderizarVariaveis } from '@/pesquisa/variaveis'
import { numerosDasPerguntas, textoComCitacoes } from '../logicaEditor'
import MenuInserir from './MenuInserir.vue'

const props = withDefaults(
  defineProps<{
    rotulo: string
    multilinha?: boolean
    erro?: string | null
    /** Aviso (não impede publicar): citação que vai sair vazia. */
    aviso?: string | null
    dica?: string
    opcional?: boolean
    maximo?: number
    placeholder?: string
    semVariaveis?: boolean
    /** Perguntas que podem ser citadas (sem elas, o menu só tem variáveis). */
    citaveis?: Pergunta[]
    /** Todos os itens (números P1, P2… na linha "Assim aparece:"). */
    itens?: Pergunta[]
    /** Mostra a linha "Assim aparece:" (com {empresa} = este nome). */
    nomeEmpresa?: string
    contador?: boolean
    /** `data-campo` do campo (o painel de problemas leva o foco até ele). */
    campo?: string
  }>(),
  { maximo: 500, citaveis: undefined, itens: undefined, nomeEmpresa: undefined, contador: false, campo: undefined },
)
const modelo = defineModel<string | null | undefined>({ default: '' })
const id = `cv-${useId()}`
const el = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)
const descritoPor = computed(
  () => [props.erro ? `${id}-erro` : '', props.aviso ? `${id}-aviso` : '', props.dica ? `${id}-dica` : '', previa.value ? `${id}-previa` : ''].filter(Boolean).join(' ') || undefined,
)
const tamanho = computed(() => (modelo.value ?? '').length)
const comMenu = computed(() => !props.semVariaveis || (props.citaveis?.length ?? 0) > 0)

/** "Assim aparece:" só quando muda algo (tem variável ou citação). */
const previa = computed(() => {
  if (props.nomeEmpresa === undefined) return ''
  const t = modelo.value ?? ''
  if (!/\{/.test(t)) return ''
  const numeros = numerosDasPerguntas(props.itens ?? props.citaveis ?? [])
  return renderizarVariaveis(textoComCitacoes(t, numeros), { empresa: props.nomeEmpresa, nome: 'Maria', referencia: 'Pedido 12345' })
})

async function inserir(trecho: string) {
  const alvo = el.value
  const atual = modelo.value ?? ''
  const ini = alvo?.selectionStart ?? atual.length
  const fim = alvo?.selectionEnd ?? atual.length
  const novo = (atual.slice(0, ini) + trecho + atual.slice(fim)).slice(0, props.maximo)
  modelo.value = novo
  await nextTick()
  alvo?.focus()
  const pos = Math.min(ini + trecho.length, novo.length)
  alvo?.setSelectionRange(pos, pos)
}

function aoDigitar(e: Event) {
  modelo.value = (e.target as HTMLInputElement).value
}

defineExpose({ focar: () => el.value?.focus() })

const classes =
  'w-full rounded-xl border bg-superficie px-3.5 text-[0.95rem] text-texto placeholder:text-texto-fraco/80 transition-colors focus:outline-none focus:ring-3 disabled:cursor-not-allowed disabled:bg-superficie-2'
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-end justify-between gap-2">
      <label :for="id" class="text-sm font-semibold text-texto">
        {{ rotulo }} <span v-if="opcional" class="font-normal text-texto-fraco">(opcional)</span>
      </label>
      <div class="flex items-center gap-1">
        <span v-if="contador" class="text-xs tabular-nums" :class="tamanho > maximo * 0.9 ? 'text-atencao' : 'text-texto-fraco'" aria-hidden="true">{{ tamanho }}/{{ maximo }}</span>
        <MenuInserir v-if="comMenu" :rotulo="`Inserir em ${rotulo}`" :citaveis="citaveis ?? []" :itens="itens ?? []" :sem-variaveis="semVariaveis" @inserir="inserir" />
      </div>
    </div>
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
      :data-campo="campo"
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
      :data-campo="campo"
      :class="[classes, 'h-11', erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20']"
      @input="aoDigitar"
    />
    <p v-if="previa" :id="`${id}-previa`" class="text-xs text-texto-fraco" data-assim-aparece>
      <span class="font-semibold">Assim aparece:</span> {{ previa }}
    </p>
    <p v-if="erro" :id="`${id}-erro`" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-else-if="aviso" :id="`${id}-aviso`" class="text-sm font-medium text-atencao">{{ aviso }}</p>
    <p v-if="dica" :id="`${id}-dica`" class="text-sm text-texto-fraco">{{ dica }}</p>
  </div>
</template>
