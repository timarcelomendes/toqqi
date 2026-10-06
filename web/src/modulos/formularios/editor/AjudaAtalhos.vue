<script setup lang="ts">
// Lista de atalhos do editor (tecla "?").
import Modal from '@/components/ui/Modal.vue'
import { tecla } from './textos'

const aberto = defineModel<boolean>('aberto', { default: false })
const ATALHOS = [
  { teclas: ['Ctrl+S'], o_que: 'Salvar o rascunho agora' },
  { teclas: ['Ctrl+Z'], o_que: 'Desfazer' },
  { teclas: ['Ctrl+Shift+Z', 'Ctrl+Y'], o_que: 'Refazer' },
  { teclas: ['Ctrl+D'], o_que: 'Duplicar o item selecionado' },
  { teclas: ['Alt+↑', 'Alt+↓'], o_que: 'Mover o item para cima ou para baixo' },
  { teclas: ['/'], o_que: 'Abrir o menu "Adicionar" (fora de um campo de texto)' },
  { teclas: ['Delete'], o_que: 'Excluir o item (na estrutura, com confirmação)' },
  { teclas: ['?'], o_que: 'Mostrar esta lista' },
]
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Atalhos do teclado" descricao="Dentro do texto formatado, Ctrl+Z desfaz só o texto." tamanho="md">
    <dl class="flex flex-col divide-y divide-borda" data-ajuda-atalhos>
      <div v-for="a in ATALHOS" :key="a.o_que" class="flex items-center justify-between gap-4 py-2.5">
        <dt class="text-sm text-texto-suave">{{ a.o_que }}</dt>
        <dd class="flex shrink-0 flex-wrap justify-end gap-1">
          <kbd v-for="t in a.teclas" :key="t" class="rounded-md border border-borda-forte bg-superficie-2 px-1.5 py-0.5 font-sans text-xs font-semibold text-texto">{{ tecla(t) }}</kbd>
        </dd>
      </div>
    </dl>
  </Modal>
</template>
