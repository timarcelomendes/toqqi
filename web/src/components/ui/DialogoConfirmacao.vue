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
  <Modal v-model:aberto="aberto" :titulo="estadoConfirmacao.titulo" tamanho="sm" papel="alertdialog" elevado>
    <p v-if="estadoConfirmacao.mensagem" class="text-[0.95rem] leading-relaxed text-texto-suave">
      {{ estadoConfirmacao.mensagem }}
    </p>
    <p
      v-if="estadoConfirmacao.complemento?.length"
      class="mt-3 text-[0.95rem] leading-relaxed text-texto-suave"
      data-teste="confirmacao-complemento"
    >
      <template v-for="(p, i) in estadoConfirmacao.complemento" :key="i">
        <template v-if="typeof p === 'string'">{{ p }}</template>
        <RouterLink v-else :to="p.para" class="link" @click="responderConfirmacao(false)">{{ p.texto }}</RouterLink>
      </template>
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
