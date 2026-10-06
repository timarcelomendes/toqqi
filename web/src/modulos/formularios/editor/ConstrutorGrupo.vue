<script setup lang="ts">
// Grupo de condições do construtor (docs/api-etapa-5l.md §5.3): "Mostrar quando todas / qualquer uma destas condições
// valerem", as linhas em frase, "+ Condição" (até 10) e remover a linha. Mexe no grupo que recebe (o documento).
import { computed } from 'vue'
import { Plus } from 'lucide-vue-next'
import type { Grupo, Juncao, Pergunta } from '@/api/tipos'
import { condicaoPadrao, MAX_CONDICOES } from '../logicaEditor'
import LinhaCondicao from './LinhaCondicao.vue'
import SelecaoCompacta from './SelecaoCompacta.vue'

const props = defineProps<{
  grupo: Grupo
  fontes: Pergunta[]
  itens: Pergunta[]
  /** O começo da frase: "Mostrar quando", "Se", "Mostrar este final quando". */
  prefixo: string
  /** Erros por número da condição (1, 2…). */
  erros?: Map<number, string>
  /** Para o leitor de tela (ex.: "regra 2"). */
  contexto?: string
}>()
const emit = defineEmits<{ vazio: [] }>()

const condicoes = computed(() => props.grupo.condicoes)

function adicionar() {
  if (condicoes.value.length >= MAX_CONDICOES) return
  // A nova condição usa a mesma pergunta da última (o caso mais comum: "nota é X ou Y"); sem nenhuma, a mais próxima.
  const ultima = condicoes.value[condicoes.value.length - 1]
  const fonte = props.fontes.find((p) => p.id === ultima?.fonte) ?? props.fontes[props.fontes.length - 1]
  if (!fonte) return
  props.grupo.condicoes.push(condicaoPadrao(fonte))
}

function remover(i: number) {
  props.grupo.condicoes.splice(i, 1)
  if (!props.grupo.condicoes.length) emit('vazio')
}

function trocarJuncao(v: string) {
  props.grupo.juncao = (v === 'qualquer' ? 'qualquer' : 'todas') as Juncao
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div v-if="condicoes.length > 1" class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-texto-suave">
      <span>{{ prefixo }}</span>
      <SelecaoCompacta class="w-40" :valor="grupo.juncao" :rotulo="`${prefixo}: todas ou qualquer uma das condições`" data-juncao @escolher="trocarJuncao">
        <option value="todas">todas</option>
        <option value="qualquer">qualquer uma</option>
      </SelecaoCompacta>
      <span>destas condições valerem:</span>
    </div>
    <p v-else class="text-sm text-texto-suave">{{ prefixo }} esta condição valer:</p>
    <ol class="flex flex-col gap-2">
      <li v-for="(c, i) in condicoes" :key="i" class="relative">
        <span v-if="i > 0" class="mb-1 block pl-1 text-xs font-bold uppercase tracking-wide text-texto-fraco" aria-hidden="true">{{ grupo.juncao === 'qualquer' ? 'ou' : 'e' }}</span>
        <LinhaCondicao :condicao="c" :fontes="fontes" :itens="itens" :numero="i + 1" :erro="erros?.get(i + 1)" :contexto="contexto" @remover="remover(i)" />
      </li>
    </ol>
    <div>
      <button
        type="button"
        class="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-marca-texto hover:bg-marca-suave disabled:opacity-50"
        :disabled="condicoes.length >= MAX_CONDICOES || !fontes.length"
        data-adicionar-condicao
        @click="adicionar"
      >
        <Plus class="size-4" aria-hidden="true" /> Condição
      </button>
    </div>
  </div>
</template>
