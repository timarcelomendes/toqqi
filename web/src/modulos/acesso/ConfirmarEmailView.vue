<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { CircleCheck, LinkIcon, LoaderCircle } from 'lucide-vue-next'
import { ApiError, authApi, mensagemDoErro } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { emailValido } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CabecalhoAcesso from './CabecalhoAcesso.vue'

const rota = useRoute()
const sessao = useSessaoStore()
const estado = ref<'carregando' | 'sucesso' | 'invalido' | 'erro'>('carregando')
const mensagem = ref('')
const reenvio = reactive({ email: '', erro: '', enviando: false, enviado: '' })

async function confirmar() {
  const token = typeof rota.query.token === 'string' ? rota.query.token : ''
  if (!token) {
    estado.value = 'invalido'
    return
  }
  estado.value = 'carregando'
  try {
    const r = await authApi.confirmarEmail(token)
    mensagem.value = r?.mensagem || 'Seu e-mail foi confirmado.'
    estado.value = 'sucesso'
  } catch (e) {
    mensagem.value = mensagemDoErro(e)
    estado.value = e instanceof ApiError && (e.codigo === 'link_invalido' || e.status === 400) ? 'invalido' : 'erro'
  }
}

async function reenviar() {
  reenvio.erro = emailValido(reenvio.email) ? '' : 'Informe um e-mail válido.'
  if (reenvio.erro) return
  reenvio.enviando = true
  try {
    const r = await authApi.reenviarConfirmacao(reenvio.email.trim())
    reenvio.enviado = r?.mensagem || 'Se houver uma conta com esse e-mail, enviamos um novo link.'
  } catch (e) {
    reenvio.erro = mensagemDoErro(e)
  } finally {
    reenvio.enviando = false
  }
}

onMounted(confirmar)
</script>

<template>
  <div v-if="estado === 'carregando'" class="flex flex-col items-center gap-4 py-8 text-center" role="status">
    <LoaderCircle class="size-10 animate-spin text-marca" aria-hidden="true" />
    <p class="font-semibold text-texto">Confirmando seu e-mail…</p>
  </div>

  <template v-else-if="estado === 'sucesso'">
    <CabecalhoAcesso :icone="CircleCheck" tom="sucesso" titulo="E-mail confirmado!" :descricao="`${mensagem} Agora é só entrar.`" />
    <Botao v-if="sessao.logado" para="/inicio" tamanho="lg" bloco>Ir para o início</Botao>
    <Botao v-else para="/entrar" tamanho="lg" bloco>Entrar</Botao>
  </template>

  <template v-else-if="estado === 'erro'">
    <CabecalhoAcesso titulo="Não deu para confirmar agora" :descricao="mensagem" />
    <Botao tamanho="lg" bloco @click="confirmar">Tentar de novo</Botao>
  </template>

  <template v-else>
    <CabecalhoAcesso
      :icone="LinkIcon"
      tom="erro"
      titulo="Este link não vale mais"
      descricao="O link pode ter expirado ou já ter sido usado. Informe seu e-mail que mandamos um novo."
    />
    <Alerta v-if="reenvio.enviado" tom="sucesso">{{ reenvio.enviado }}</Alerta>
    <form v-else class="flex flex-col gap-4" novalidate @submit.prevent="reenviar">
      <Campo v-model="reenvio.email" rotulo="E-mail" tipo="email" autocomplete="email" inputmode="email" obrigatorio :erro="reenvio.erro" />
      <Botao tipo="submit" tamanho="lg" bloco :carregando="reenvio.enviando">Enviar novo link</Botao>
    </form>
    <p class="mt-6 text-center text-sm text-texto-suave"><RouterLink to="/entrar" class="link">Voltar para Entrar</RouterLink></p>
  </template>
</template>
