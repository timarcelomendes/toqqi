<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { CircleCheck, KeyRound, LinkIcon } from 'lucide-vue-next'
import { authApi } from '@/api'
import { useFormulario } from '@/composables/formulario'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import CabecalhoAcesso from './CabecalhoAcesso.vue'

const rota = useRoute()
const token = computed(() => (typeof rota.query.token === 'string' ? rota.query.token : ''))
const { enviando, erroGeral, codigoErro, erros, executar } = useFormulario()
const dados = reactive({ senha: '', repetir: '' })
const senhaOk = ref(false)
const locais = reactive<{ senha?: string; repetir?: string }>({})
const concluido = ref<string | null>(null)
const linkInvalido = computed(() => !token.value || codigoErro.value === 'link_invalido')

async function enviar() {
  locais.senha = senhaOk.value ? undefined : 'A senha ainda não cumpre todas as regras.'
  locais.repetir = dados.repetir === dados.senha ? undefined : 'As duas senhas não são iguais.'
  if (locais.senha || locais.repetir) return
  const r = await executar(() => authApi.redefinirSenha(token.value, dados.senha))
  if (r) concluido.value = r.mensagem || 'Sua senha foi trocada.'
}
</script>

<template>
  <template v-if="concluido">
    <CabecalhoAcesso :icone="CircleCheck" tom="sucesso" titulo="Senha nova salva!" :descricao="`${concluido} Use a nova senha para entrar.`" />
    <Botao para="/entrar" tamanho="lg" bloco>Entrar</Botao>
  </template>
  <template v-else-if="linkInvalido">
    <CabecalhoAcesso
      :icone="LinkIcon"
      tom="erro"
      titulo="Este link não vale mais"
      :descricao="erroGeral ?? 'O link pode ter expirado ou já ter sido usado. Peça um novo, é rapidinho.'"
    />
    <Botao para="/esqueci-senha" tamanho="lg" bloco>Pedir um novo link</Botao>
  </template>
  <template v-else>
    <CabecalhoAcesso :icone="KeyRound" titulo="Crie uma senha nova" descricao="Escolha uma senha forte que você não usa em outros sites." />
    <Alerta v-if="erroGeral" tom="erro" class="mb-5">{{ erroGeral }}</Alerta>
    <form class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <CampoSenha v-model="dados.senha" v-model:valida="senhaOk" rotulo="Nova senha" autocomplete="new-password" com-regras :erro="locais.senha ?? erros.senha" />
      <CampoSenha v-model="dados.repetir" rotulo="Repita a nova senha" autocomplete="new-password" :erro="locais.repetir" />
      <Botao tipo="submit" tamanho="lg" bloco :carregando="enviando" class="mt-2">Salvar nova senha</Botao>
    </form>
  </template>
</template>
