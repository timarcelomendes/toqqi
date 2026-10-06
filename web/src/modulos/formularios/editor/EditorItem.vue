<script setup lang="ts">
// A coluna de edição: mostra o editor do que está selecionado na estrutura (pergunta, conteúdo, quebra de página,
// final ou final padrão).
import { computed } from 'vue'
import { MousePointerClick, Plus, SeparatorHorizontal } from 'lucide-vue-next'
import type { Id } from '@/api/tipos'
import { respondivel } from '@/pesquisa/logica'
import { FOCO_FINAL_PADRAO } from '@/pesquisa/tipos'
import Botao from '@/components/ui/Botao.vue'
import { usarEditor } from './documento'
import CabecalhoEdicao from './CabecalhoEdicao.vue'
import EditorConteudo from './EditorConteudo.vue'
import EditorFinal from './EditorFinal.vue'
import EditorFinalPadrao from './EditorFinalPadrao.vue'
import EditorPergunta from './EditorPergunta.vue'

defineProps<{ podeEditar: boolean; nomeEmpresa: string; formularioId: Id; prefixoImagens: string | null }>()
const emit = defineEmits<{ adicionar: []; duplicar: []; excluir: [id: string]; selecionar: [id: string] }>()
const editor = usarEditor()

const id = computed(() => editor.selecionado.value)
const indice = computed(() => editor.doc.perguntas.findIndex((p) => p.id === id.value))
const item = computed(() => (indice.value >= 0 ? editor.doc.perguntas[indice.value]! : null))
const indiceFinal = computed(() => editor.doc.finais.findIndex((f) => f.id === id.value))
const final = computed(() => (indiceFinal.value >= 0 ? editor.doc.finais[indiceFinal.value]! : null))
const paginaDaQuebra = computed(() => editor.doc.perguntas.slice(0, indice.value + 1).filter((p) => p.tipo === 'quebra_pagina').length + 1)
</script>

<template>
  <div class="cartao p-4 sm:p-6" data-edicao>
    <fieldset :disabled="!podeEditar" class="min-w-0">
      <EditorPergunta v-if="item && respondivel(item.tipo)" :key="item.id" :item="item" :indice="indice" :pode-editar="podeEditar" :nome-empresa="nomeEmpresa" @duplicar="emit('duplicar')" @excluir="emit('excluir', item.id)" />
      <EditorConteudo
        v-else-if="item?.tipo === 'conteudo'"
        :key="`c-${item.id}`"
        :item="item"
        :indice="indice"
        :pode-editar="podeEditar"
        :nome-empresa="nomeEmpresa"
        :formulario-id="formularioId"
        :prefixo-imagens="prefixoImagens"
        @duplicar="emit('duplicar')"
        @excluir="emit('excluir', item.id)"
      />
      <div v-else-if="item?.tipo === 'quebra_pagina'" class="flex flex-col gap-4">
        <CabecalhoEdicao :icone="SeparatorHorizontal" :rotulo="`Quebra de página · começa a página ${paginaDaQuebra}`" :pode-editar="podeEditar" sem-duplicar @excluir="emit('excluir', item.id)" />
        <p class="text-sm text-texto-suave">
          A quebra divide a pesquisa em páginas quando o modo é <strong class="text-texto">Em páginas</strong> (na aba Aparência). No modo uma pergunta por vez, ela não muda nada.
        </p>
      </div>
      <EditorFinal
        v-else-if="final"
        :key="`f-${final.id}`"
        :final="final"
        :indice="indiceFinal"
        :pode-editar="podeEditar"
        :nome-empresa="nomeEmpresa"
        :formulario-id="formularioId"
        :prefixo-imagens="prefixoImagens"
        @duplicar="emit('duplicar')"
        @excluir="emit('excluir', final.id)"
      />
      <EditorFinalPadrao v-else-if="id === FOCO_FINAL_PADRAO" :pode-editar="podeEditar" :nome-empresa="nomeEmpresa" />
      <div v-else class="flex flex-col items-center gap-3 py-12 text-center" data-nada-selecionado>
        <span class="flex size-12 items-center justify-center rounded-2xl bg-superficie-2 text-texto-fraco" aria-hidden="true"><MousePointerClick class="size-6" /></span>
        <p class="font-semibold text-texto">Escolha um item na estrutura para editar</p>
        <p class="max-w-sm text-sm text-texto-suave">Ou adicione uma pergunta, um bloco de conteúdo ou uma quebra de página.</p>
        <Botao v-if="podeEditar" variante="secundario" @click="emit('adicionar')"><Plus class="size-4" aria-hidden="true" /> Adicionar</Botao>
      </div>
    </fieldset>
  </div>
</template>
