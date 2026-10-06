<script setup lang="ts">
// Edição de um bloco de conteúdo (docs/api-etapa-5l.md §5.3): nome interno (opcional), o texto em Visual ou HTML,
// imagens, "Inserir" (variáveis e respostas anteriores) e a lógica (só "Quando mostrar").
import { computed } from 'vue'
import { FileText } from 'lucide-vue-next'
import type { Id, Pergunta } from '@/api/tipos'
import { respondivel } from '@/pesquisa/logica'
import Campo from '@/components/ui/Campo.vue'
import { usarEditor } from './documento'
import CabecalhoEdicao from './CabecalhoEdicao.vue'
import EditorHtml from './EditorHtml.vue'
import ProblemasDoItem from './ProblemasDoItem.vue'
import SecaoLogica from './SecaoLogica.vue'

const props = defineProps<{ item: Pergunta; indice: number; podeEditar: boolean; nomeEmpresa: string; formularioId: Id; prefixoImagens: string | null }>()
const emit = defineEmits<{ duplicar: []; excluir: [] }>()
const editor = usarEditor()

const itens = computed(() => editor.doc.perguntas)
const anteriores = computed(() => itens.value.slice(0, props.indice).filter((x) => respondivel(x.tipo)))
const problemas = computed(() => editor.problemas.value.filter((x) => 'id' in x.alvo && x.alvo.id === props.item.id))
const erro = (campo: string) => problemas.value.find((x) => x.campo === campo && !x.aviso)?.mensagem ?? null
const aviso = (campo: string) => problemas.value.find((x) => x.campo === campo && x.aviso)?.mensagem ?? null
</script>

<template>
  <div class="flex flex-col gap-5" :data-editor-conteudo="item.id">
    <CabecalhoEdicao :icone="FileText" rotulo="Conteúdo" detalhe="Texto formatado, imagens e avisos. Não tem resposta." :pode-editar="podeEditar" @duplicar="emit('duplicar')" @excluir="emit('excluir')" />
    <ProblemasDoItem :problemas="problemas" />
    <Campo
      :model-value="item.titulo ?? ''"
      rotulo="Nome interno"
      opcional
      maxlength="120"
      placeholder="Ex.: Aviso de privacidade"
      dica="Só a sua equipe vê, na estrutura do formulário."
      :erro="erro('titulo')"
      data-campo="titulo"
      @update:model-value="(v: string) => (item.titulo = v)"
    />
    <EditorHtml
      v-model:html="item.html"
      v-model:modo="item.modo"
      :id-item="item.id"
      rotulo="Conteúdo"
      :formulario-id="formularioId"
      :prefixo-imagens="prefixoImagens"
      :pode-editar="podeEditar"
      :citaveis="anteriores"
      :itens="itens"
      :nome-empresa="nomeEmpresa"
      :erro="erro('html')"
      :aviso="aviso('html')"
    />
    <SecaoLogica :item="item" :indice="indice" />
  </div>
</template>
