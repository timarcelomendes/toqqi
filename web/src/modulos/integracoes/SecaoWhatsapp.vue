<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { mensagemDoErro, whatsappAutomaticoApi, type WhatsappIntegracao } from '@/api'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import GuiaWhatsapp from './GuiaWhatsapp.vue'
import PainelWhatsapp from './PainelWhatsapp.vue'

const dados = ref<WhatsappIntegracao | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    dados.value = await whatsappAutomaticoApi.obter()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function aoAtualizar(w: WhatsappIntegracao) {
  // Respostas de PUT/PATCH podem não trazer os dados do webhook: mantém os que já temos.
  dados.value = { ...dados.value, ...w } as WhatsappIntegracao
}

onMounted(carregar)
</script>

<template>
  <Carregando v-if="carregando" :linhas="4" />
  <Alerta v-else-if="erro" tom="erro">
    {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>
  <template v-else-if="dados">
    <PainelWhatsapp v-if="dados.conectado" :dados="dados" @atualizado="aoAtualizar" @desconectado="carregar" />
    <GuiaWhatsapp v-else :dados="dados" @conectado="aoAtualizar" />
  </template>
</template>
