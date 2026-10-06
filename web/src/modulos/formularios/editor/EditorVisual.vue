<script setup lang="ts">
// Aba "Visual" do conteúdo (docs/api-etapa-5l.md §5.3): TipTap (StarterKit + Link + Image + TextAlign + Placeholder),
// carregado só no editor (componente assíncrono). Barra: negrito, itálico, sublinhado, título (H2/H3), listas, citação,
// link, alinhamento, linha horizontal, imagem e desfazer. O HTML que sai já está dentro da lista permitida; a API e a
// prévia limpam de novo. Dentro do texto, Ctrl+Z é o desfazer do próprio TipTap.
import { onBeforeUnmount, ref, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import TextAlign from '@tiptap/extension-text-align'
import { Placeholder } from '@tiptap/extensions'
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  Heading2,
  Heading3,
  ImagePlus,
  Italic,
  Link2,
  List,
  ListOrdered,
  Minus,
  Quote,
  Redo2,
  Underline,
  Undo2,
} from 'lucide-vue-next'
import { REL_LINK } from '@/pesquisa/html'
import { enderecoDeLinkValido } from './htmlVisual'
import { tecla } from './textos'

const props = withDefaults(defineProps<{ rotulo: string; editavel?: boolean; placeholder?: string }>(), { editavel: true, placeholder: 'Escreva o texto aqui…' })
const modelo = defineModel<string>({ default: '' })
const emit = defineEmits<{ imagem: [] }>()

/** O HTML do TipTap; documento vazio vira "" (e não "<p></p>"). */
function htmlDe(e: { isEmpty: boolean; getHTML: () => string }): string {
  return e.isEmpty ? '' : e.getHTML()
}

const editor = useEditor({
  content: modelo.value || '',
  editable: props.editavel,
  extensions: [
    StarterKit.configure({
      heading: { levels: [2, 3, 4] },
      link: {
        openOnClick: false,
        autolink: true,
        defaultProtocol: 'https',
        HTMLAttributes: { target: '_blank', rel: REL_LINK },
        isAllowedUri: (url: string) => enderecoDeLinkValido(url),
      },
    }),
    Image.configure({ inline: false, allowBase64: false }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
    Placeholder.configure({ placeholder: props.placeholder }),
  ],
  editorProps: {
    attributes: {
      class: 'bloco-html min-h-40 px-4 py-3 focus:outline-none',
      role: 'textbox',
      'aria-multiline': 'true',
      'aria-label': props.rotulo,
      'data-campo': 'html',
    },
  },
  onUpdate: ({ editor: e }) => {
    const html = htmlDe(e)
    if (html !== modelo.value) modelo.value = html
  },
})

// Mudança de fora (desfazer do formulário, a aba HTML, o servidor): o TipTap acompanha sem disparar outra mudança.
watch(modelo, (v) => {
  const e = editor.value
  if (!e || htmlDe(e) === (v ?? '')) return
  e.commands.setContent(v || '', { emitUpdate: false })
})
watch(
  () => props.editavel,
  (v) => editor.value?.setEditable(v),
)
onBeforeUnmount(() => editor.value?.destroy())

// ── link ──
const linkAberto = ref(false)
const endereco = ref('')
const erroLink = ref<string | null>(null)

function abrirLink() {
  const e = editor.value
  if (!e) return
  endereco.value = (e.getAttributes('link').href as string | undefined) ?? ''
  erroLink.value = null
  linkAberto.value = true
}

function aplicarLink() {
  const e = editor.value
  if (!e) return
  const url = endereco.value.trim()
  if (!url) return tirarLink()
  if (!enderecoDeLinkValido(url)) {
    erroLink.value = 'Use um endereço que comece com https://, mailto: ou tel:.'
    return
  }
  const cadeia = e.chain().focus().extendMarkRange('link')
  if (e.state.selection.empty && !e.isActive('link')) cadeia.insertContent({ type: 'text', text: url, marks: [{ type: 'link', attrs: { href: url } }] }).run()
  else cadeia.setLink({ href: url }).run()
  linkAberto.value = false
}

function tirarLink() {
  editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
  linkAberto.value = false
}

/** Insere texto onde está o cursor (variáveis e citações do menu "Inserir"). */
function inserirTexto(texto: string) {
  editor.value?.chain().focus().insertContent(texto).run()
}

/** Insere uma imagem (já enviada para a plataforma) onde está o cursor. */
function inserirImagem(img: { src: string; alt?: string; width?: number | null; height?: number | null }) {
  const attrs: { src: string; alt: string; width?: number; height?: number } = { src: img.src, alt: img.alt ?? '' }
  if (img.width && img.width <= 2000) attrs.width = img.width
  if (img.height && img.height <= 2000) attrs.height = img.height
  editor.value?.chain().focus().setImage(attrs).run()
}

defineExpose({ inserirTexto, inserirImagem, focar: () => editor.value?.commands.focus() })

type Botao = { rotulo: string; icone: unknown; ativo?: () => boolean; acao: () => void; atalho?: string }
const grupos: Botao[][] = [
  [
    { rotulo: 'Negrito', icone: Bold, atalho: 'Ctrl+B', ativo: () => !!editor.value?.isActive('bold'), acao: () => editor.value?.chain().focus().toggleBold().run() },
    { rotulo: 'Itálico', icone: Italic, atalho: 'Ctrl+I', ativo: () => !!editor.value?.isActive('italic'), acao: () => editor.value?.chain().focus().toggleItalic().run() },
    { rotulo: 'Sublinhado', icone: Underline, atalho: 'Ctrl+U', ativo: () => !!editor.value?.isActive('underline'), acao: () => editor.value?.chain().focus().toggleUnderline().run() },
  ],
  [
    { rotulo: 'Título', icone: Heading2, ativo: () => !!editor.value?.isActive('heading', { level: 2 }), acao: () => editor.value?.chain().focus().toggleHeading({ level: 2 }).run() },
    { rotulo: 'Subtítulo', icone: Heading3, ativo: () => !!editor.value?.isActive('heading', { level: 3 }), acao: () => editor.value?.chain().focus().toggleHeading({ level: 3 }).run() },
  ],
  [
    { rotulo: 'Lista', icone: List, ativo: () => !!editor.value?.isActive('bulletList'), acao: () => editor.value?.chain().focus().toggleBulletList().run() },
    { rotulo: 'Lista numerada', icone: ListOrdered, ativo: () => !!editor.value?.isActive('orderedList'), acao: () => editor.value?.chain().focus().toggleOrderedList().run() },
    { rotulo: 'Citação', icone: Quote, ativo: () => !!editor.value?.isActive('blockquote'), acao: () => editor.value?.chain().focus().toggleBlockquote().run() },
  ],
  [
    { rotulo: 'Link', icone: Link2, ativo: () => !!editor.value?.isActive('link'), acao: abrirLink },
    { rotulo: 'Imagem', icone: ImagePlus, acao: () => emit('imagem') },
    { rotulo: 'Linha horizontal', icone: Minus, acao: () => editor.value?.chain().focus().setHorizontalRule().run() },
  ],
  [
    { rotulo: 'Alinhar à esquerda', icone: AlignLeft, ativo: () => !!editor.value?.isActive({ textAlign: 'left' }), acao: () => editor.value?.chain().focus().setTextAlign('left').run() },
    { rotulo: 'Centralizar', icone: AlignCenter, ativo: () => !!editor.value?.isActive({ textAlign: 'center' }), acao: () => editor.value?.chain().focus().setTextAlign('center').run() },
    { rotulo: 'Alinhar à direita', icone: AlignRight, ativo: () => !!editor.value?.isActive({ textAlign: 'right' }), acao: () => editor.value?.chain().focus().setTextAlign('right').run() },
    { rotulo: 'Justificar', icone: AlignJustify, ativo: () => !!editor.value?.isActive({ textAlign: 'justify' }), acao: () => editor.value?.chain().focus().setTextAlign('justify').run() },
  ],
  [
    { rotulo: 'Desfazer', icone: Undo2, atalho: 'Ctrl+Z', acao: () => editor.value?.chain().focus().undo().run() },
    { rotulo: 'Refazer', icone: Redo2, atalho: 'Ctrl+Shift+Z', acao: () => editor.value?.chain().focus().redo().run() },
  ],
]
const ALINHAR_E_ACOES = new Set(['Desfazer', 'Refazer', 'Imagem', 'Linha horizontal'])
</script>

<template>
  <div class="overflow-hidden rounded-xl border border-borda-forte bg-white text-slate-900 focus-within:border-marca focus-within:ring-3 focus-within:ring-marca/20" data-editor-visual>
    <div v-if="editavel" class="flex flex-wrap items-center gap-0.5 border-b border-slate-200 bg-slate-50 px-1.5 py-1" role="toolbar" :aria-label="`Formatação de ${rotulo}`">
      <template v-for="(g, i) in grupos" :key="i">
        <span v-if="i > 0" class="mx-0.5 h-5 w-px bg-slate-200" aria-hidden="true" />
        <button
          v-for="b in g"
          :key="b.rotulo"
          type="button"
          class="flex size-8 items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-200 hover:text-slate-900"
          :class="b.ativo?.() ? 'bg-slate-900 text-white hover:bg-slate-800 hover:text-white' : ''"
          :aria-label="b.rotulo"
          :aria-pressed="ALINHAR_E_ACOES.has(b.rotulo) ? undefined : !!b.ativo?.()"
          :title="b.atalho ? `${b.rotulo} (${tecla(b.atalho)})` : b.rotulo"
          :data-formatar="b.rotulo"
          @mousedown.prevent
          @click="b.acao()"
        >
          <component :is="b.icone" class="size-4" aria-hidden="true" />
        </button>
      </template>
    </div>
    <div v-if="linkAberto" class="flex flex-wrap items-start gap-2 border-b border-slate-200 bg-white px-3 py-2" data-editar-link>
      <label class="sr-only" for="endereco-link">Endereço do link</label>
      <div class="min-w-48 flex-1">
        <input
          id="endereco-link"
          v-model="endereco"
          type="url"
          placeholder="https://"
          class="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-900 focus:border-slate-500 focus:outline-none"
          @keydown.enter.prevent="aplicarLink"
          @keydown.esc.prevent="linkAberto = false"
        />
        <p v-if="erroLink" class="mt-1 text-xs font-medium text-red-700">{{ erroLink }}</p>
      </div>
      <button type="button" class="h-9 rounded-lg bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-700" @click="aplicarLink">Aplicar</button>
      <button v-if="editor?.isActive('link')" type="button" class="h-9 rounded-lg px-3 text-sm font-semibold text-slate-600 hover:bg-slate-100" @click="tirarLink">Tirar link</button>
      <button type="button" class="h-9 rounded-lg px-3 text-sm font-semibold text-slate-600 hover:bg-slate-100" @click="linkAberto = false">Cancelar</button>
    </div>
    <EditorContent :editor="editor" class="max-h-[32rem] overflow-y-auto" />
  </div>
</template>

<style>
/* Texto de exemplo do TipTap (Placeholder) no primeiro parágrafo vazio. */
[data-editor-visual] .ProseMirror p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
  color: #94a3b8;
}
[data-editor-visual] .ProseMirror img.ProseMirror-selectednode {
  outline: 3px solid #ff7c5c;
  outline-offset: 2px;
}
</style>
