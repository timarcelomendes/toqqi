<script setup lang="ts">
// "Mover para…" (docs/api-etapa-5l.md §5.3): escolher a nova posição de um item numa lista, sem arrastar.
import { computed, ref, watch } from 'vue'
import Botao from '@/components/ui/Botao.vue'
import Modal from '@/components/ui/Modal.vue'
import { nomeDoItem, numerosDasPerguntas } from '../logicaEditor'
import { usarEditor } from './documento'
import SelecaoCompacta from './SelecaoCompacta.vue'

const props = defineProps<{ itemId: string | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ mover: [id: string, depoisDe: string | null] }>()
const editor = usarEditor()

const INICIO = ':inicio'
const destino = ref<string>(INICIO)
const item = computed(() => editor.doc.perguntas.find((p) => p.id === props.itemId) ?? null)
const numeros = computed(() => numerosDasPerguntas(editor.doc.perguntas))
const opcoes = computed(() => [
  { valor: INICIO, rotulo: 'No começo do formulário' },
  ...editor.doc.perguntas.filter((p) => p.id !== props.itemId).map((p) => ({ valor: p.id, rotulo: `Depois de ${nomeDoItem(p, numeros.value, 50)}` })),
])

// Abre na posição de agora (depois do item que vem antes dele).
watch(aberto, (v) => {
  if (!v) return
  const i = editor.doc.perguntas.findIndex((p) => p.id === props.itemId)
  destino.value = i > 0 ? editor.doc.perguntas[i - 1]!.id : INICIO
})

function mover() {
  if (!props.itemId) return
  emit('mover', props.itemId, destino.value === INICIO ? null : destino.value)
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Mover para…" :descricao="item ? `Escolha onde “${nomeDoItem(item, numeros, 50)}” vai ficar.` : undefined" tamanho="sm">
    <form id="form-mover-para" class="flex flex-col gap-1.5" @submit.prevent="mover">
      <p class="text-sm font-semibold text-texto" aria-hidden="true">Nova posição</p>
      <!-- O foco já abre na lista (o atributo chega ao <select>) -->
      <SelecaoCompacta :valor="destino" rotulo="Nova posição" data-autofoco data-mover-destino @escolher="(v) => (destino = v)">
        <option v-for="o in opcoes" :key="o.valor" :value="o.valor">{{ o.rotulo }}</option>
      </SelecaoCompacta>
    </form>
    <template #rodape>
      <Botao variante="secundario" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-mover-para" data-confirmar-mover>Mover</Botao>
    </template>
  </Modal>
</template>
