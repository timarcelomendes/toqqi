<script setup lang="ts">
// Até 3 imagens num feedback ou numa mensagem: colar um print (Ctrl+V / ⌘V, com `colar` ligado), arrastar ou escolher.
// Cada imagem vira PNG ou JPG de até 1 MB no navegador (`imagens.ts`) e aparece em miniatura, com o botão de tirar.
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { ImagePlus, LoaderCircle, X } from 'lucide-vue-next'
import type { ArquivoFeedback } from '@/api/feedback'
import { MAX_IMAGENS, tamanhoArquivo } from './logica'
import { imagensDaColagem, prepararImagem } from './imagens'

export interface ImagemEscolhida extends ArquivoFeedback {
  id: string
  url: string
}

const props = withDefaults(defineProps<{ colar?: boolean; desabilitado?: boolean; maximo?: number }>(), {
  colar: true,
  desabilitado: false,
  maximo: MAX_IMAGENS,
})
const imagens = defineModel<ImagemEscolhida[]>({ default: () => [] })
const id = useId()
const erro = ref<string | null>(null)
const preparando = ref(0)
const arrastando = ref(false)
let contador = 0

const cabe = computed(() => props.maximo - imagens.value.length - preparando.value)
const atalho = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.userAgent) ? '⌘V' : 'Ctrl+V'

function criarUrl(b: Blob): string {
  try {
    return URL.createObjectURL(b)
  } catch {
    return ''
  }
}

async function adicionar(arquivos: Blob[]) {
  if (props.desabilitado || !arquivos.length) return
  erro.value = null
  const vagas = Math.max(0, cabe.value)
  if (arquivos.length > vagas) erro.value = vagas ? `Cabem só mais ${vagas === 1 ? '1 imagem' : `${vagas} imagens`}.` : `Até ${props.maximo} imagens.`
  for (const a of arquivos.slice(0, vagas)) {
    preparando.value++
    try {
      const pronto = await prepararImagem(a, ++contador)
      imagens.value = [...imagens.value, { ...pronto, id: `img-${contador}`, url: criarUrl(pronto.blob) }]
    } catch (e) {
      erro.value = e instanceof Error ? e.message : 'Não conseguimos usar esta imagem.'
    } finally {
      preparando.value--
    }
  }
}

function escolher(e: Event) {
  const alvo = e.target as HTMLInputElement
  void adicionar(Array.from(alvo.files ?? []))
  alvo.value = ''
}

function soltar(e: DragEvent) {
  arrastando.value = false
  void adicionar(Array.from(e.dataTransfer?.files ?? []).filter((f) => f.type.startsWith('image/')))
}

function tirar(i: ImagemEscolhida) {
  imagens.value = imagens.value.filter((x) => x.id !== i.id)
  erro.value = null
}

// Colar um print em qualquer lugar da janela (com o campo de texto em foco também): só itens de imagem; texto colado
// segue normal.
function aoColar(e: ClipboardEvent) {
  if (!props.colar || props.desabilitado) return
  const achadas = imagensDaColagem(e)
  if (!achadas.length) return
  e.preventDefault()
  void adicionar(achadas)
}
onMounted(() => window.addEventListener('paste', aoColar))
onBeforeUnmount(() => window.removeEventListener('paste', aoColar))

// As URLs das miniaturas saem com as imagens (tiradas, enviadas ou o campo fechado).
watch(imagens, (agora, antes) => {
  const ficam = new Set(agora.map((i) => i.url))
  for (const i of antes ?? []) if (i.url && !ficam.has(i.url)) URL.revokeObjectURL(i.url)
})
onBeforeUnmount(() => {
  for (const i of imagens.value) if (i.url) URL.revokeObjectURL(i.url)
})
</script>

<template>
  <div class="flex flex-col gap-2" data-campo-imagens>
    <p :id="`${id}-rotulo`" class="text-sm font-semibold text-texto">
      Imagens <span class="font-normal text-texto-fraco">(opcional, até {{ maximo }})</span>
    </p>
    <ul v-if="imagens.length || preparando" class="grid grid-cols-3 gap-2" :aria-labelledby="`${id}-rotulo`">
      <li v-for="i in imagens" :key="i.id" class="group relative aspect-[4/3] overflow-hidden rounded-xl border border-borda bg-superficie-2" data-imagem-escolhida>
        <img v-if="i.url" :src="i.url" :alt="i.nome" class="size-full object-cover" />
        <span class="absolute inset-x-0 bottom-0 truncate bg-slate-950/55 px-2 py-0.5 text-[0.7rem] font-medium text-white">
          {{ i.nome }} · {{ tamanhoArquivo(i.blob.size) }}
        </span>
        <button
          type="button"
          class="absolute right-1 top-1 flex size-7 items-center justify-center rounded-full bg-slate-950/70 text-white hover:bg-slate-950 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-white"
          :aria-label="`Tirar a imagem ${i.nome}`"
          :disabled="desabilitado"
          data-tirar-imagem
          @click="tirar(i)"
        >
          <X class="size-4" aria-hidden="true" />
        </button>
      </li>
      <li v-for="n in preparando" :key="`p-${n}`" class="flex aspect-[4/3] items-center justify-center rounded-xl border border-dashed border-borda-forte text-texto-fraco">
        <LoaderCircle class="size-5 animate-spin" aria-hidden="true" />
        <span class="sr-only">Preparando a imagem…</span>
      </li>
    </ul>
    <label
      v-if="cabe > 0"
      class="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed px-4 py-3 text-sm transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-foco"
      :class="[
        arrastando ? 'border-marca bg-marca-suave text-marca-texto' : 'border-borda-forte text-texto-suave hover:border-texto-fraco hover:bg-superficie-2',
        desabilitado ? 'pointer-events-none opacity-60' : '',
      ]"
      data-soltar-imagens
      @dragover.prevent="arrastando = true"
      @dragleave="arrastando = false"
      @drop.prevent="soltar"
    >
      <ImagePlus class="size-5 shrink-0" aria-hidden="true" />
      <span>
        <span class="font-semibold text-texto">Escolha uma imagem</span> ou arraste para cá<span v-if="colar" class="hidden sm:inline">. Também dá para colar um print com {{ atalho }}</span>.
      </span>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif,image/heic,image/heif"
        multiple
        class="sr-only"
        :disabled="desabilitado"
        data-entrada-imagens
        @change="escolher"
      />
    </label>
    <p v-if="erro" class="text-sm font-medium text-erro" role="alert" data-erro-imagens>{{ erro }}</p>
  </div>
</template>
