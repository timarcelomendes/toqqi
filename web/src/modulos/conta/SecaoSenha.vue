<script setup lang="ts">
import { reactive, ref } from 'vue'
import { euApi } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import SecaoCartao from './SecaoCartao.vue'

const emit = defineEmits<{ trocou: [] }>()
const { enviando, erroGeral, erros, executar } = useFormulario()
const dados = reactive({ atual: '', nova: '', repetir: '' })
const novaOk = ref(false)
const locais = reactive<{ atual?: string; nova?: string; repetir?: string }>({})

async function salvar() {
  locais.atual = dados.atual ? undefined : 'Informe sua senha atual.'
  locais.nova = novaOk.value ? undefined : 'A nova senha ainda não cumpre todas as regras.'
  locais.repetir = dados.repetir === dados.nova ? undefined : 'As duas senhas não são iguais.'
  if (locais.atual || locais.nova || locais.repetir) return
  const r = await executar(async () => {
    await euApi.trocarSenha(dados.atual, dados.nova)
    return true
  })
  if (r) {
    dados.atual = dados.nova = dados.repetir = ''
    avisar.sucesso('Senha trocada. Por segurança, desconectamos seus outros aparelhos.')
    emit('trocou')
  }
}
</script>

<template>
  <SecaoCartao titulo="Senha" descricao="Ao trocar, seus outros aparelhos são desconectados por segurança.">
    <form class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <CampoSenha v-model="dados.atual" rotulo="Senha atual" autocomplete="current-password" :erro="locais.atual ?? erros.senha_atual" />
      <CampoSenha v-model="dados.nova" v-model:valida="novaOk" rotulo="Nova senha" autocomplete="new-password" com-regras :erro="locais.nova ?? erros.senha_nova" />
      <CampoSenha v-model="dados.repetir" rotulo="Repita a nova senha" autocomplete="new-password" :erro="locais.repetir" />
      <div>
        <Botao tipo="submit" :carregando="enviando">Trocar senha</Botao>
      </div>
    </form>
  </SecaoCartao>
</template>
