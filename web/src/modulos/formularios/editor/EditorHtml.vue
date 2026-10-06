<script setup lang="ts">
// Texto formatado de um bloco de conteúdo ou de um final (docs/api-etapa-5l.md §5.3): abas "Visual" (TipTap, carregado
// só quando abre) e "HTML" (código, com a prévia já limpa embaixo). O que a limpeza tira aparece num aviso
// ("Removemos por segurança: …"). HTML que o Visual não representa (tabela, div…) fica na aba HTML, sem perder nada.
import { computed, defineAsyncComponent, h, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { ShieldCheck } from 'lucide-vue-next'
import type { Id, Pergunta } from '@/api/tipos'
import { avisoRemocao, limparHtmlComRelatorio } from '@/pesquisa/html'
import { escaparHtml } from '@/pesquisa/logica'
import { renderizarVariaveisHtml } from '@/pesquisa/variaveis'
import BlocoHtml from '@/pesquisa/BlocoHtml.vue'
import { numerosDasPerguntas } from '../logicaEditor'
import BotoesImagem from './BotoesImagem.vue'
import MenuInserir from './MenuInserir.vue'
import { partesSoNoHtml } from './htmlVisual'

const EditorVisual = defineAsyncComponent({
  loader: () => import('./EditorVisual.vue'),
  loadingComponent: { render: () => h('div', { class: 'h-48 animate-pulse rounded-xl bg-superficie-2', 'aria-hidden': 'true' }) },
  delay: 100,
})

const props = withDefaults(
  defineProps<{
    /** O id do item ou do final (marca `data-editor-html`: a resposta do servidor não mexe aqui enquanto há foco). */
    idItem: string
    rotulo: string
    formularioId: Id
    prefixoImagens: string | null
    podeEditar: boolean
    citaveis: Pergunta[]
    itens: Pergunta[]
    nomeEmpresa: string
    erro?: string | null
    aviso?: string | null
    placeholder?: string
  }>(),
  { erro: null, aviso: null, placeholder: undefined },
)
const html = defineModel<string | null | undefined>('html', { default: '' })
const modo = defineModel<'visual' | 'html' | undefined>('modo', { default: 'visual' })

const id = `html-${useId()}`
const textarea = ref<HTMLTextAreaElement | null>(null)
const visual = ref<{ inserirTexto: (t: string) => void; inserirImagem: (i: { src: string; alt?: string; width?: number | null; height?: number | null }) => void } | null>(null)
const imagens = ref<InstanceType<typeof BotoesImagem> | null>(null)

/** Partes que só a aba HTML edita: com elas, o Visual fica desligado (e o bloco, em `modo: 'html'`). */
const soNoHtml = computed(() => partesSoNoHtml(html.value))
const aba = computed<'visual' | 'html'>(() => (soNoHtml.value.length ? 'html' : (modo.value ?? 'visual')))
const avisoVisual = ref(false)

function irPara(a: 'visual' | 'html') {
  if (a === 'visual' && soNoHtml.value.length) {
    avisoVisual.value = true
    modo.value = 'html'
    return
  }
  avisoVisual.value = false
  modo.value = a
}

// ── o que a limpeza tira (aviso) ──
const removido = ref<string[]>([])
let espera: ReturnType<typeof setTimeout> | undefined
let pedido = 0
watch(
  [html, () => props.prefixoImagens],
  () => {
    clearTimeout(espera)
    espera = setTimeout(async () => {
      const meu = ++pedido
      try {
        const r = await limparHtmlComRelatorio(html.value ?? '', props.prefixoImagens)
        if (meu === pedido) removido.value = r.removido
      } catch {
        /* sem o limpador, sem aviso (a prévia mostra só o texto) */
      }
    }, 250)
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(espera))

/** A prévia da aba HTML: variáveis de exemplo e citações como "[resposta de P2]" (escapadas); o BlocoHtml limpa. */
const numeros = computed(() => numerosDasPerguntas(props.itens))
const previa = computed(() => {
  const comCitacoes = (html.value ?? '').replace(/\{\{([A-Za-z0-9_-]{1,32})\}\}/g, (_m, pid: string) => {
    const n = numeros.value.get(pid)
    return escaparHtml(n ? `[resposta de P${n}]` : '[resposta apagada]')
  })
  return renderizarVariaveisHtml(comCitacoes, { empresa: props.nomeEmpresa, nome: 'Maria', referencia: 'Pedido 12345' })
})

// ── inserir (variáveis, citações e imagens) onde está o cursor ──
async function inserirNoCodigo(trecho: string) {
  const el = textarea.value
  const atual = html.value ?? ''
  const ini = el?.selectionStart ?? atual.length
  const fim = el?.selectionEnd ?? atual.length
  html.value = atual.slice(0, ini) + trecho + atual.slice(fim)
  await nextTick()
  el?.focus()
  el?.setSelectionRange(ini + trecho.length, ini + trecho.length)
}

function inserir(trecho: string) {
  if (aba.value === 'visual' && visual.value) visual.value.inserirTexto(trecho)
  else void inserirNoCodigo(trecho)
}

function inserirImagem(img: { src: string; alt: string; width?: number | null; height?: number | null }) {
  if (aba.value === 'visual' && visual.value) return visual.value.inserirImagem(img)
  const medidas = `${img.width && img.width <= 2000 ? ` width="${img.width}"` : ''}${img.height && img.height <= 2000 ? ` height="${img.height}"` : ''}`
  void inserirNoCodigo(`<p><img src="${escaparHtml(img.src)}" alt="${escaparHtml(img.alt)}"${medidas}></p>`)
}

const tamanho = computed(() => (html.value ?? '').length)
</script>

<template>
  <div class="flex flex-col gap-2" :data-editor-html="idItem">
    <div class="flex flex-wrap items-end justify-between gap-2">
      <div>
        <p :id="`${id}-rotulo`" class="text-sm font-semibold text-texto">{{ rotulo }}</p>
      </div>
      <div class="flex items-center gap-2">
        <div class="flex rounded-xl border border-borda-forte p-0.5" role="tablist" :aria-labelledby="`${id}-rotulo`">
          <button
            type="button"
            role="tab"
            :aria-selected="aba === 'visual'"
            :aria-controls="`${id}-painel`"
            :aria-disabled="soNoHtml.length ? 'true' : undefined"
            class="h-8 rounded-[0.6rem] px-3 text-xs font-semibold transition-colors"
            :class="[aba === 'visual' ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto', soNoHtml.length ? 'cursor-not-allowed opacity-60' : '']"
            data-aba-visual
            @click="irPara('visual')"
          >
            Visual
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="aba === 'html'"
            :aria-controls="`${id}-painel`"
            class="h-8 rounded-[0.6rem] px-3 text-xs font-semibold transition-colors"
            :class="aba === 'html' ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto'"
            data-aba-html
            @click="irPara('html')"
          >
            HTML
          </button>
        </div>
        <MenuInserir v-if="podeEditar" :rotulo="`Inserir em ${rotulo}`" :citaveis="citaveis" :itens="itens" @inserir="inserir" />
      </div>
    </div>

    <p v-if="soNoHtml.length" class="rounded-lg bg-info-suave px-3 py-2 text-sm text-texto-suave" :role="avisoVisual ? 'status' : undefined" data-so-no-html>
      Parte deste HTML só pode ser editada na aba HTML ({{ soNoHtml.join(', ') }}). O Visual fica desligado para não perder nada.
    </p>

    <div :id="`${id}-painel`" role="tabpanel">
      <EditorVisual
        v-if="aba === 'visual'"
        ref="visual"
        :model-value="html ?? ''"
        :rotulo="rotulo"
        :editavel="podeEditar"
        :placeholder="placeholder"
        @update:model-value="(v: string) => (html = v)"
        @imagem="imagens?.escolherArquivo()"
      />
      <template v-else>
        <label :for="`${id}-codigo`" class="sr-only">{{ rotulo }} em HTML</label>
        <textarea
          :id="`${id}-codigo`"
          ref="textarea"
          :value="html ?? ''"
          :readonly="!podeEditar"
          rows="10"
          spellcheck="false"
          wrap="soft"
          class="w-full resize-y rounded-xl border bg-superficie px-3.5 py-3 font-mono text-[0.85rem] leading-relaxed text-texto focus:outline-none focus:ring-3"
          :class="erro ? 'border-erro focus:ring-erro/20' : 'border-borda-forte focus:border-marca focus:ring-marca/20'"
          placeholder="<p>Escreva o HTML aqui.</p>"
          data-campo="html"
          @input="html = ($event.target as HTMLTextAreaElement).value"
        />
        <p class="mt-1 text-right text-xs tabular-nums" :class="tamanho > 20000 ? 'font-semibold text-erro' : 'text-texto-fraco'">{{ tamanho.toLocaleString('pt-BR') }} de 20.000 caracteres</p>
        <div class="mt-2 rounded-xl border border-dashed border-borda-forte bg-white p-4 text-slate-900" data-previa-html>
          <p class="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Prévia (já limpa)</p>
          <BlocoHtml v-if="previa.trim()" :html="previa" :prefixo-imagens="prefixoImagens" />
          <p v-else class="text-sm text-slate-500">Nada para mostrar ainda.</p>
        </div>
      </template>
    </div>

    <p v-if="removido.length" class="rounded-lg border border-atencao/30 bg-atencao-suave px-3 py-2 text-sm font-medium text-texto" role="status" data-aviso-removido>
      {{ avisoRemocao(removido) }}
    </p>
    <p v-if="erro" class="text-sm font-medium text-erro">{{ erro }}</p>
    <p v-else-if="aviso" class="text-sm font-medium text-atencao">{{ aviso }}</p>

    <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <BotoesImagem v-if="podeEditar" ref="imagens" :formulario-id="formularioId" @imagem="inserirImagem" />
    </div>
    <p class="flex gap-2 text-xs text-texto-fraco">
      <ShieldCheck class="mt-px size-3.5 shrink-0" aria-hidden="true" />
      Por segurança, scripts, estilos, formulários e conteúdo de outros sites são removidos. Imagens: envie aqui ou use o banco de imagens.
    </p>
  </div>
</template>
