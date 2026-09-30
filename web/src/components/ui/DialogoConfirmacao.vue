<script setup lang="ts">
import { computed } from 'vue'
import { estadoConfirmacao, responderConfirmacao } from '@/composables/confirmacao'
import Botao from './Botao.vue'
import Modal from './Modal.vue'

const aberto = computed({
  get: () => estadoConfirmacao.aberto,
  set: (v: boolean) => {
    if (!v) responderConfirmacao(false)
  },
})
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="estadoConfirmacao.titulo" tamanho="sm" papel="alertdialog">
    <p v-if="estadoConfirmacao.mensagem" class="text-[0.95rem] leading-relaxed text-texto-suave">
      {{ estadoConfirmacao.mensagem }}
    </p>
    <template #rodape>
      <Botao variante="secundario" @click="responderConfirmacao(false)">
        {{ estadoConfirmacao.cancelar ?? 'Cancelar' }}
      </Botao>
      <Botao :variante="estadoConfirmacao.perigo ? 'perigo' : 'primario'" data-autofoco @click="responderConfirmacao(true)">
        {{ estadoConfirmacao.confirmar ?? 'Confirmar' }}
      </Botao>
    </template>
  </Modal>
</template>
