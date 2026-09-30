<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { AlertCircle, ArrowDown, ArrowUp, ChevronDown, Copy, GitBranch, GripVertical, Plus, Trash2 } from 'lucide-vue-next'
import type { Pergunta, TipoPergunta } from '@/api/tipos'
import { confirmar } from '@/composables/confirmacao'
import { indicePrincipal } from '@/pesquisa/logica'
import { renderizarVariaveis } from '@/pesquisa/variaveis'
import Botao from '@/components/ui/Botao.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Modal from '@/components/ui/Modal.vue'
import { criarPergunta, duplicarPergunta, INFO_TIPO, mover, TIPOS_PERGUNTA } from '../tiposPergunta'
import { LIMITE_PERGUNTAS } from '../validacaoFormulario'
import EditorPergunta from './EditorPergunta.vue'

const props = defineProps<{
  /** Erros por índice de pergunta. */
  erros: Record<number, Record<string, string>>
  podeEditar: boolean
  nomeEmpresa: string
}>()
const perguntas = defineModel<Pergunta[]>({ required: true })
const selecionada = defineModel<string | null>('selecionada', { default: null })

const escolherTipoAberto = ref(false)
const anuncio = ref('')
const arrastando = ref<number | null>(null)
const alvo = ref<number | null>(null)
const alcaAtiva = ref<number | null>(null)
const lista = ref<HTMLElement | null>(null)

const ip = computed(() => indicePrincipal(perguntas.value))
const totalPerguntas = computed(() => perguntas.value.filter((p) => p.tipo !== 'quebra_pagina').length)
const tituloVisivel = (p: Pergunta) =>
  renderizarVariaveis(p.titulo, { empresa: props.nomeEmpresa, nome: 'Maria' }) || (p.tipo === 'quebra_pagina' ? 'Quebra de página' : 'Pergunta sem título')

async function focarItem(id: string) {
  await nextTick()
  lista.value?.querySelector<HTMLElement>(`[data-item="${id}"] [data-cabeca]`)?.focus()
}

function alternar(p: Pergunta) {
  selecionada.value = selecionada.value === p.id ? null : p.id
}

function adicionar(tipo: TipoPergunta) {
  escolherTipoAberto.value = false
  const nova = criarPergunta(tipo, perguntas.value)
  const i = perguntas.value.findIndex((p) => p.id === selecionada.value)
  const pos = i >= 0 ? i + 1 : perguntas.value.length
  const lista = [...perguntas.value]
  lista.splice(pos, 0, nova)
  perguntas.value = lista
  selecionada.value = nova.id
  anuncio.value = `${INFO_TIPO[tipo].rotulo} adicionada na posição ${pos + 1}.`
  focarItem(nova.id)
}

function moverPara(de: number, para: number) {
  if (para < 0 || para >= perguntas.value.length || de === para) return
  const id = perguntas.value[de]!.id
  perguntas.value = mover(perguntas.value, de, para)
  anuncio.value = `Pergunta movida para a posição ${para + 1} de ${perguntas.value.length}.`
  return id
}

async function moverBotao(i: number, d: number, e: Event) {
  moverPara(i, i + d)
  await nextTick()
  // Mantém o foco no mesmo botão, que agora está na nova posição.
  const botao = (e.currentTarget as HTMLElement | null)?.dataset.acao
  const novo = lista.value?.querySelectorAll<HTMLElement>('[data-item]')[i + d]
  const alvoBotao = novo?.querySelector<HTMLElement>(`[data-acao="${botao}"]:not([disabled])`) ?? novo?.querySelector<HTMLElement>('[data-cabeca]')
  alvoBotao?.focus()
}

function duplicar(i: number) {
  const copia = duplicarPergunta(perguntas.value[i]!, perguntas.value)
  const l = [...perguntas.value]
  l.splice(i + 1, 0, copia)
  perguntas.value = l
  selecionada.value = copia.id
  anuncio.value = 'Pergunta duplicada.'
  focarItem(copia.id)
}

async function remover(i: number) {
  const p = perguntas.value[i]!
  const ok = await confirmar({
    titulo: 'Apagar esta pergunta?',
    mensagem: `“${tituloVisivel(p)}” sai do formulário. As respostas antigas dela continuam guardadas. Você ainda pode descartar as alterações antes de salvar.`,
    confirmar: 'Apagar',
    perigo: true,
  })
  if (!ok) return
  perguntas.value = perguntas.value.filter((_, j) => j !== i)
  if (selecionada.value === p.id) selecionada.value = null
  anuncio.value = 'Pergunta apagada.'
}

// Arrastar e soltar (só pela alça, para não atrapalhar a seleção de texto).
function aoIniciarArraste(e: DragEvent, i: number) {
  if (alcaAtiva.value !== i) {
    e.preventDefault()
    return
  }
  arrastando.value = i
  e.dataTransfer?.setData('text/plain', String(i))
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}
function aoPassar(e: DragEvent, i: number) {
  if (arrastando.value === null) return
  e.preventDefault()
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  alvo.value = e.clientY < r.top + r.height / 2 ? i : i + 1
}
function aoSoltar() {
  if (arrastando.value !== null && alvo.value !== null) {
    const de = arrastando.value
    const para = alvo.value > de ? alvo.value - 1 : alvo.value
    moverPara(de, para)
  }
  finalizarArraste()
}
function finalizarArraste() {
  arrastando.value = null
  alvo.value = null
  alcaAtiva.value = null
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <EstadoVazio v-if="!perguntas.length" class="cartao" titulo="Nenhuma pergunta ainda" descricao="Comece por uma nota de 0 a 10 (NPS) ou por carinhas de satisfação (CSAT).">
      <Botao v-if="podeEditar" @click="escolherTipoAberto = true"><Plus class="size-4" aria-hidden="true" /> Adicionar pergunta</Botao>
    </EstadoVazio>

    <ol v-else ref="lista" class="flex flex-col gap-2" aria-label="Perguntas do formulário" @dragend="finalizarArraste">
      <li
        v-for="(p, i) in perguntas"
        :key="p.id"
        :data-item="p.id"
        class="relative"
        :draggable="podeEditar && alcaAtiva === i"
        @dragstart="aoIniciarArraste($event, i)"
        @dragover="aoPassar($event, i)"
        @drop.prevent="aoSoltar"
      >
        <div v-if="alvo === i && arrastando !== null" class="absolute -top-1.5 left-0 right-0 h-1 rounded-full bg-marca" aria-hidden="true" />
        <div v-if="alvo === i + 1 && i === perguntas.length - 1 && arrastando !== null" class="absolute -bottom-1.5 left-0 right-0 h-1 rounded-full bg-marca" aria-hidden="true" />

        <div
          class="cartao overflow-hidden transition-shadow"
          :class="[
            selecionada === p.id ? 'ring-2 ring-marca' : '',
            arrastando === i ? 'opacity-50' : '',
            erros[i] ? 'border-erro' : '',
            p.tipo === 'quebra_pagina' ? 'border-dashed bg-superficie-2/50' : '',
          ]"
        >
          <div class="flex items-center gap-1 p-2 pr-3">
            <span
              v-if="podeEditar"
              class="flex size-8 shrink-0 cursor-grab items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 active:cursor-grabbing"
              title="Arraste para mudar a ordem"
              aria-hidden="true"
              @pointerdown="alcaAtiva = i"
              @pointerup="alcaAtiva = null"
            >
              <GripVertical class="size-4" />
            </span>
            <button
              type="button"
              data-cabeca
              class="flex min-w-0 flex-1 items-center gap-3 rounded-lg p-1.5 text-left hover:bg-superficie-2/60"
              :aria-expanded="selecionada === p.id"
              :aria-controls="`painel-${p.id}`"
              @click="alternar(p)"
            >
              <span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-superficie-2 text-texto-suave" aria-hidden="true">
                <component :is="INFO_TIPO[p.tipo]?.icone" class="size-4" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-semibold text-texto">
                  <span class="text-texto-fraco">{{ i + 1 }}.</span> {{ tituloVisivel(p) }}
                </span>
                <span class="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-texto-fraco">
                  {{ INFO_TIPO[p.tipo]?.rotulo ?? p.tipo }}
                  <Etiqueta v-if="i === ip" tom="marca">Nota principal</Etiqueta>
                  <Etiqueta v-if="p.obrigatoria && p.tipo !== 'quebra_pagina'" tom="neutro">Obrigatória</Etiqueta>
                  <Etiqueta v-if="p.condicao" tom="info"><GitBranch class="size-3" aria-hidden="true" /> Com condição</Etiqueta>
                  <span v-if="erros[i]" class="inline-flex items-center gap-1 font-semibold text-erro"><AlertCircle class="size-3.5" aria-hidden="true" /> Precisa de ajuste</span>
                </span>
              </span>
              <ChevronDown class="size-4 shrink-0 text-texto-fraco transition-transform" :class="{ 'rotate-180': selecionada === p.id }" aria-hidden="true" />
            </button>
            <div v-if="podeEditar" class="flex shrink-0 items-center">
              <button type="button" data-acao="subir" class="hidden size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-30 sm:flex" :disabled="i === 0" :aria-label="`Subir pergunta ${i + 1}`" @click="moverBotao(i, -1, $event)">
                <ArrowUp class="size-4" aria-hidden="true" />
              </button>
              <button type="button" data-acao="descer" class="hidden size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-30 sm:flex" :disabled="i === perguntas.length - 1" :aria-label="`Descer pergunta ${i + 1}`" @click="moverBotao(i, 1, $event)">
                <ArrowDown class="size-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          <div v-if="selecionada === p.id" :id="`painel-${p.id}`" class="border-t border-borda p-4 sm:p-5">
            <fieldset :disabled="!podeEditar" class="min-w-0">
              <EditorPergunta :pergunta="p" :indice="i" :perguntas="perguntas" :erros="erros[i]" />
            </fieldset>
            <div v-if="podeEditar" class="mt-5 flex flex-wrap gap-2 border-t border-borda pt-4">
              <Botao variante="secundario" tamanho="sm" data-acao="subir" class="sm:hidden" :desabilitado="i === 0" @click="moverBotao(i, -1, $event)"><ArrowUp class="size-4" aria-hidden="true" /> Subir</Botao>
              <Botao variante="secundario" tamanho="sm" data-acao="descer" class="sm:hidden" :desabilitado="i === perguntas.length - 1" @click="moverBotao(i, 1, $event)"><ArrowDown class="size-4" aria-hidden="true" /> Descer</Botao>
              <Botao variante="secundario" tamanho="sm" @click="duplicar(i)"><Copy class="size-4" aria-hidden="true" /> Duplicar</Botao>
              <Botao variante="perigo-suave" tamanho="sm" @click="remover(i)"><Trash2 class="size-4" aria-hidden="true" /> Apagar</Botao>
            </div>
          </div>
        </div>
      </li>
    </ol>

    <div v-if="podeEditar && perguntas.length" class="flex flex-wrap items-center gap-3">
      <Botao variante="secundario" :desabilitado="totalPerguntas >= LIMITE_PERGUNTAS" @click="escolherTipoAberto = true">
        <Plus class="size-4" aria-hidden="true" /> Adicionar pergunta
      </Botao>
      <p class="text-sm text-texto-fraco">{{ totalPerguntas }} de {{ LIMITE_PERGUNTAS }} perguntas</p>
    </div>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>

    <Modal v-model:aberto="escolherTipoAberto" titulo="Que tipo de pergunta?" :descricao="selecionada ? 'Ela entra logo depois da pergunta aberta.' : 'Ela entra no fim do formulário.'" tamanho="lg">
      <ul class="grid gap-2 sm:grid-cols-2">
        <li v-for="t in TIPOS_PERGUNTA" :key="t.tipo">
          <button type="button" class="flex h-full w-full items-start gap-3 rounded-xl border border-borda-forte p-3 text-left transition-colors hover:border-marca hover:bg-marca-suave" @click="adicionar(t.tipo)">
            <span class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-superficie-2 text-marca-texto" aria-hidden="true">
              <component :is="t.icone" class="size-5" />
            </span>
            <span class="min-w-0">
              <span class="block text-sm font-bold text-texto">{{ t.rotulo }}</span>
              <span class="block text-xs text-texto-suave">{{ t.descricao }}</span>
            </span>
          </button>
        </li>
      </ul>
    </Modal>
  </div>
</template>
