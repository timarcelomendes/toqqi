<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ArrowDown, ArrowUp, Plus, X } from 'lucide-vue-next'
import { mover } from '../tiposPergunta'

const props = defineProps<{ erro?: string | null; rotuloPergunta: string }>()
const opcoes = defineModel<string[]>({ required: true })
const campos = ref<HTMLInputElement[]>([])
const anuncio = ref('')

const repetidas = computed(() => {
  const vistos = new Map<string, number>()
  const rep = new Set<number>()
  opcoes.value.forEach((o, i) => {
    const k = o.trim().toLocaleLowerCase('pt-BR')
    if (!k) return
    if (vistos.has(k)) {
      rep.add(i)
      rep.add(vistos.get(k)!)
    } else vistos.set(k, i)
  })
  return rep
})

async function focar(i: number) {
  await nextTick()
  campos.value[i]?.focus()
}

function atualizar(i: number, v: string) {
  const nova = [...opcoes.value]
  nova[i] = v
  opcoes.value = nova
}

function adicionar(depois = opcoes.value.length - 1) {
  if (opcoes.value.length >= 30) return
  const nova = [...opcoes.value]
  nova.splice(depois + 1, 0, '')
  opcoes.value = nova
  focar(depois + 1)
}

function remover(i: number) {
  opcoes.value = opcoes.value.filter((_, j) => j !== i)
  anuncio.value = 'Opção removida.'
  focar(Math.max(0, i - 1))
}

function moverOpcao(i: number, d: number) {
  const j = i + d
  if (j < 0 || j >= opcoes.value.length) return
  opcoes.value = mover(opcoes.value, i, j)
  anuncio.value = `Opção movida para a posição ${j + 1}.`
  focar(j)
}

function aoTeclar(e: KeyboardEvent, i: number) {
  if (e.key === 'Enter') {
    e.preventDefault()
    adicionar(i)
  } else if (e.key === 'Backspace' && !opcoes.value[i] && opcoes.value.length > 1) {
    e.preventDefault()
    remover(i)
  }
}

/** Colar várias linhas cria uma opção por linha. */
function aoColar(e: ClipboardEvent, i: number) {
  const texto = e.clipboardData?.getData('text') ?? ''
  const linhas = texto.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  if (linhas.length < 2) return
  e.preventDefault()
  const nova = [...opcoes.value]
  const atual = nova[i]?.trim() ? [nova[i]!] : []
  nova.splice(i, 1, ...atual, ...linhas)
  opcoes.value = nova.slice(0, 30)
  anuncio.value = `${linhas.length} opções coladas.`
}
</script>

<template>
  <fieldset class="flex flex-col gap-2">
    <legend class="mb-1 text-sm font-semibold text-texto">Opções <span class="font-normal text-texto-fraco">({{ opcoes.length }} de 30)</span></legend>
    <ol class="flex flex-col gap-1.5">
      <li v-for="(o, i) in opcoes" :key="i" class="flex items-center gap-1">
        <span class="w-6 shrink-0 text-right text-xs tabular-nums text-texto-fraco" aria-hidden="true">{{ i + 1 }}.</span>
        <input
          ref="campos"
          :value="o"
          maxlength="200"
          :aria-label="`Opção ${i + 1} de ${props.rotuloPergunta}`"
          :aria-invalid="repetidas.has(i) || !o.trim() ? 'true' : undefined"
          class="h-10 min-w-0 flex-1 rounded-lg border bg-superficie px-3 text-sm text-texto focus:outline-none focus:ring-3"
          :class="repetidas.has(i) ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20'"
          placeholder="Escreva a opção"
          @input="atualizar(i, ($event.target as HTMLInputElement).value)"
          @keydown="aoTeclar($event, i)"
          @paste="aoColar($event, i)"
        />
        <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 disabled:opacity-30" :disabled="i === 0" :aria-label="`Subir opção ${i + 1}`" @click="moverOpcao(i, -1)">
          <ArrowUp class="size-4" aria-hidden="true" />
        </button>
        <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 disabled:opacity-30" :disabled="i === opcoes.length - 1" :aria-label="`Descer opção ${i + 1}`" @click="moverOpcao(i, 1)">
          <ArrowDown class="size-4" aria-hidden="true" />
        </button>
        <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-erro-suave hover:text-erro" :aria-label="`Remover opção ${i + 1}`" @click="remover(i)">
          <X class="size-4" aria-hidden="true" />
        </button>
      </li>
    </ol>
    <button v-if="opcoes.length < 30" type="button" class="link inline-flex w-fit items-center gap-1 text-sm" @click="adicionar()">
      <Plus class="size-4" aria-hidden="true" /> Adicionar opção
    </button>
    <p class="text-xs text-texto-fraco">Dica: cole uma lista (uma opção por linha) para criar várias de uma vez.</p>
    <p v-if="erro" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
  </fieldset>
</template>
