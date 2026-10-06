<script setup lang="ts">
// Uma condição do construtor de lógica, em frase (docs/api-etapa-5l.md §5.3): [pergunta ▾] [comparação ▾] [valor].
// O valor muda conforme o tipo: número, faixa "entre", grupos (Detratores 0 a 6…), opções (várias), sim/não, texto
// ou data. Trocar a pergunta ou a comparação põe um valor que faz sentido.
import { computed, useId } from 'vue'
import { X } from 'lucide-vue-next'
import type { Condicao, Operador, Pergunta } from '@/api/tipos'
import { faixa, gruposDoTipo } from '@/pesquisa/logica'
import { ehNota, ehTextoNumero, nomeDoItem, numerosDasPerguntas, operadoresDaFonte, rotuloOperador, SEM_VALOR, valorPadrao, valorServe } from '../logicaEditor'
import SelecaoCompacta from './SelecaoCompacta.vue'

const props = defineProps<{
  condicao: Condicao
  /** As perguntas que podem ser fonte aqui. */
  fontes: Pergunta[]
  /** Todos os itens (para os números e para achar a fonte). */
  itens: Pergunta[]
  numero: number
  erro?: string | null
  /** "Pular": a frase da regra (para o leitor de tela). */
  contexto?: string
}>()
const emit = defineEmits<{ remover: [] }>()
const id = `cond-${useId()}`

const numeros = computed(() => numerosDasPerguntas(props.itens))
const fonte = computed(() => props.itens.find((p) => p.id === props.condicao.fonte) ?? null)
/** A fonte atual some da lista quando não vale mais aqui (ex.: foi movida para depois): ela continua escolhida, marcada. */
const opcoesFonte = computed(() => {
  const lista = props.fontes.map((p) => ({ valor: p.id, rotulo: nomeDoItem(p, numeros.value, 60) }))
  if (props.condicao.fonte && !lista.some((o) => o.valor === props.condicao.fonte))
    lista.unshift({ valor: props.condicao.fonte, rotulo: fonte.value ? `${nomeDoItem(fonte.value, numeros.value, 50)} (não vale aqui)` : 'Pergunta apagada' })
  return lista
})
const operadores = computed(() => {
  const ops = operadoresDaFonte(fonte.value)
  return ops.includes(props.condicao.op) || !props.condicao.op ? ops : [props.condicao.op, ...ops]
})
const semValor = computed(() => SEM_VALOR.includes(props.condicao.op))
const nota = computed(() => !!fonte.value && ehNota(fonte.value))
const notas = computed(() => {
  if (!fonte.value) return []
  const { min, max } = faixa(fonte.value)
  return Array.from({ length: max - min + 1 }, (_, i) => min + i)
})
const contexto = computed(() => (props.contexto ? `${props.contexto}, condição ${props.numero}` : `condição ${props.numero}`))

function trocarFonte(novo: string) {
  const f = props.itens.find((p) => p.id === novo)
  if (!f) return
  const ops = operadoresDaFonte(f)
  const op = ops.includes(props.condicao.op) && props.condicao.fonte && fonte.value?.tipo === f.tipo ? props.condicao.op : ops[0]!
  props.condicao.fonte = novo
  props.condicao.op = op
  aplicarValor(valorPadrao(f, op))
}

function trocarOperador(op: Operador) {
  props.condicao.op = op
  if (!fonte.value) return
  if (!valorServe(fonte.value, op, props.condicao.valor)) aplicarValor(valorPadrao(fonte.value, op))
  else if (SEM_VALOR.includes(op)) aplicarValor(undefined)
}

function aplicarValor(v: Condicao['valor']) {
  if (v === undefined) delete props.condicao.valor
  else props.condicao.valor = v
}

const lista = computed<(string | number)[]>(() => (Array.isArray(props.condicao.valor) ? props.condicao.valor : []))
function alternar(v: string) {
  const atual = lista.value.map(String)
  props.condicao.valor = atual.includes(v) ? atual.filter((x) => x !== v) : [...atual, v]
  // Mantém a ordem das opções (ou dos grupos).
  const ordem = fonte.value?.tipo && ehNota(fonte.value) ? gruposDoTipo(fonte.value.tipo).map((g) => g.valor as string) : (fonte.value?.opcoes ?? [])
  props.condicao.valor = (props.condicao.valor as string[]).slice().sort((a, b) => ordem.indexOf(a) - ordem.indexOf(b))
}

function numeroDe(v: string): number | undefined {
  if (v.trim() === '') return undefined
  const n = Number(v.replace(',', '.'))
  return Number.isFinite(n) ? n : undefined
}

function trocarParte(i: 0 | 1, v: number | string | undefined) {
  const atual = Array.isArray(props.condicao.valor) && props.condicao.valor.length === 2 ? [...props.condicao.valor] : [undefined, undefined]
  atual[i] = v as never
  props.condicao.valor = atual as (number | string)[]
}

const classeEntrada = 'h-10 w-full min-w-0 rounded-lg border border-borda-forte bg-superficie px-3 text-sm text-texto focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20'
const classeChip = (ligado: boolean) =>
  `rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors ${ligado ? 'border-marca-forte bg-marca-forte text-white' : 'border-borda-forte bg-superficie text-texto-suave hover:bg-superficie-2'}`
</script>

<template>
  <div
    class="@container rounded-xl border bg-superficie p-2.5"
    :class="erro ? 'border-erro/60' : 'border-borda'"
    :data-condicao="numero"
    role="group"
    :aria-label="`Condição ${numero}`"
    :aria-describedby="erro ? `${id}-erro` : undefined"
  >
    <div class="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
      <SelecaoCompacta :valor="condicao.fonte" :rotulo="`Pergunta da ${contexto}`" data-fonte @escolher="trocarFonte">
        <option v-if="!condicao.fonte" value="" disabled>Escolha a pergunta</option>
        <option v-for="o in opcoesFonte" :key="o.valor" :value="o.valor">{{ o.rotulo }}</option>
      </SelecaoCompacta>
      <button
        type="button"
        class="flex size-10 items-center justify-center rounded-lg text-texto-fraco hover:bg-erro-suave hover:text-erro"
        :aria-label="`Remover a ${contexto}`"
        data-remover-condicao
        @click="emit('remover')"
      >
        <X class="size-4" aria-hidden="true" />
      </button>
      <!-- Lado a lado só quando a própria condição tem largura (a coluna do meio é estreita em 1280 px) -->
      <div class="col-span-2 grid gap-2 @md:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]">
        <SelecaoCompacta :valor="condicao.op" :rotulo="`Comparação da ${contexto}`" :desabilitado="!fonte" data-operador @escolher="(v) => trocarOperador(v as Operador)">
          <option v-for="op in operadores" :key="op" :value="op">{{ rotuloOperador(op, fonte) }}</option>
        </SelecaoCompacta>

        <!-- Valor -->
        <div v-if="!semValor && fonte" class="min-w-0" data-valor>
          <!-- Grupos da nota (NPS, CSAT, estrelas) -->
          <div v-if="condicao.op === 'grupo_e'" class="flex flex-wrap items-center gap-1.5 py-1" role="group" :aria-label="`Grupos da ${contexto}`">
            <button
              v-for="g in gruposDoTipo(fonte.tipo)"
              :key="g.valor"
              type="button"
              :aria-pressed="lista.includes(g.valor)"
              :class="classeChip(lista.includes(g.valor))"
              :data-grupo-valor="g.valor"
              @click="alternar(g.valor)"
            >
              {{ g.rotulo }}
            </button>
          </div>
          <!-- Opções (uma ou várias) -->
          <div v-else-if="fonte.tipo === 'escolha_unica' || fonte.tipo === 'escolha_multipla'" class="flex flex-wrap items-center gap-1.5 py-1" role="group" :aria-label="`Opções da ${contexto}`">
            <button
              v-for="o in (fonte.opcoes ?? []).filter((x) => x.trim())"
              :key="o"
              type="button"
              :aria-pressed="lista.includes(o)"
              :class="classeChip(lista.includes(o))"
              :data-opcao-valor="o"
              @click="alternar(o)"
            >
              {{ o }}
            </button>
            <span v-if="!(fonte.opcoes ?? []).some((x) => x.trim())" class="text-xs text-texto-fraco">A pergunta ainda não tem opções.</span>
          </div>
          <!-- Sim ou não -->
          <div v-else-if="fonte.tipo === 'sim_nao'" class="flex gap-1.5 py-1" role="radiogroup" :aria-label="`Resposta da ${contexto}`">
            <button v-for="o in [{ v: true, t: 'Sim' }, { v: false, t: 'Não' }]" :key="o.t" type="button" role="radio" :aria-checked="condicao.valor === o.v" :class="classeChip(condicao.valor === o.v)" @click="condicao.valor = o.v">
              {{ o.t }}
            </button>
          </div>
          <!-- Nota: número ou faixa -->
          <div v-else-if="nota" class="flex items-center gap-2">
            <template v-if="condicao.op === 'entre'">
              <SelecaoCompacta class="flex-1" :valor="lista[0]" :rotulo="`Menor nota da ${contexto}`" @escolher="(v) => trocarParte(0, Number(v))">
                <option v-for="n in notas" :key="n" :value="n">{{ n }}</option>
              </SelecaoCompacta>
              <span class="text-sm text-texto-suave">e</span>
              <SelecaoCompacta class="flex-1" :valor="lista[1]" :rotulo="`Maior nota da ${contexto}`" @escolher="(v) => trocarParte(1, Number(v))">
                <option v-for="n in notas" :key="n" :value="n">{{ n }}</option>
              </SelecaoCompacta>
            </template>
            <SelecaoCompacta v-else class="flex-1" :valor="typeof condicao.valor === 'number' ? condicao.valor : ''" :rotulo="`Nota da ${contexto}`" data-valor-nota @escolher="(v) => (condicao.valor = Number(v))">
              <option v-for="n in notas" :key="n" :value="n">{{ n }}</option>
            </SelecaoCompacta>
          </div>
          <!-- Data -->
          <div v-else-if="fonte.tipo === 'data'" class="flex items-center gap-2">
            <template v-if="condicao.op === 'entre'">
              <input type="date" :value="lista[0] ?? ''" :class="classeEntrada" :aria-label="`Primeira data da ${contexto}`" @change="trocarParte(0, ($event.target as HTMLInputElement).value)" />
              <span class="text-sm text-texto-suave">e</span>
              <input type="date" :value="lista[1] ?? ''" :class="classeEntrada" :aria-label="`Última data da ${contexto}`" @change="trocarParte(1, ($event.target as HTMLInputElement).value)" />
            </template>
            <input v-else type="date" :value="typeof condicao.valor === 'string' ? condicao.valor : ''" :class="classeEntrada" :aria-label="`Data da ${contexto}`" @change="condicao.valor = ($event.target as HTMLInputElement).value" />
          </div>
          <!-- Número (resposta curta de número) -->
          <div v-else-if="ehTextoNumero(fonte)" class="flex items-center gap-2">
            <template v-if="condicao.op === 'entre'">
              <input type="number" step="any" :value="lista[0] ?? ''" :class="classeEntrada" :aria-label="`Menor número da ${contexto}`" @input="trocarParte(0, numeroDe(($event.target as HTMLInputElement).value))" />
              <span class="text-sm text-texto-suave">e</span>
              <input type="number" step="any" :value="lista[1] ?? ''" :class="classeEntrada" :aria-label="`Maior número da ${contexto}`" @input="trocarParte(1, numeroDe(($event.target as HTMLInputElement).value))" />
            </template>
            <input v-else type="number" step="any" :value="typeof condicao.valor === 'number' ? condicao.valor : ''" :class="classeEntrada" :aria-label="`Número da ${contexto}`" @input="aplicarValor(numeroDe(($event.target as HTMLInputElement).value))" />
          </div>
          <!-- Texto -->
          <input
            v-else
            type="text"
            maxlength="200"
            :value="typeof condicao.valor === 'string' ? condicao.valor : ''"
            :class="classeEntrada"
            placeholder="Escreva o texto"
            :aria-label="`Texto da ${contexto}`"
            @input="condicao.valor = ($event.target as HTMLInputElement).value"
          />
        </div>
      </div>
    </div>
    <p v-if="erro" :id="`${id}-erro`" class="mt-1.5 text-sm font-medium text-erro" data-erro-condicao>{{ erro }}</p>
  </div>
</template>
