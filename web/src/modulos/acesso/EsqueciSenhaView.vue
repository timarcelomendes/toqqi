<script setup lang="ts">
import { ref } from 'vue'
import { KeyRound, MailCheck } from 'lucide-vue-next'
import { authApi } from '@/api'
import { useFormulario } from '@/composables/formulario'
import { emailValido } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CabecalhoAcesso from './CabecalhoAcesso.vue'

const { enviando, erroGeral, erros, executar } = useFormulario()
const email = ref('')
const erroLocal = ref<string | undefined>()
const concluido = ref<string | null>(null)

async function enviar() {
  erroLocal.value = emailValido(email.value) ? undefined : 'Informe o e-mail que você usa para entrar.'
  if (erroLocal.value) return
  const r = await executar(() => authApi.esqueciSenha(email.value.trim()))
  if (r) concluido.value = r.mensagem || 'Se houver uma conta com esse e-mail, enviamos um link para criar uma nova senha.'
}
</script>

<template>
  <template v-if="concluido">
    <CabecalhoAcesso :icone="MailCheck" tom="sucesso" titulo="Confira o seu e-mail" :descricao="concluido" />
    <Alerta tom="info">O link vale por pouco tempo. Não achou? Olhe a caixa de spam.</Alerta>
    <Botao para="/entrar" variante="secundario" bloco class="mt-6">Voltar para Entrar</Botao>
  </template>
  <template v-else>
    <CabecalhoAcesso :icone="KeyRound" titulo="Esqueceu a senha?" descricao="Sem problema. Informe seu e-mail e enviamos um link para você criar uma nova." />
    <Alerta v-if="erroGeral" tom="erro" class="mb-5">{{ erroGeral }}</Alerta>
    <form class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <Campo v-model="email" rotulo="E-mail" tipo="email" autocomplete="email" inputmode="email" obrigatorio :erro="erroLocal ?? erros.email" />
      <Botao tipo="submit" tamanho="lg" bloco :carregando="enviando">Enviar link</Botao>
    </form>
    <p class="mt-6 text-center text-sm text-texto-suave">Lembrou? <RouterLink to="/entrar" class="link">Entrar</RouterLink></p>
  </template>
</template>
