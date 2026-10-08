<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authApi, mensagemDoErro } from '@/api'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { destinoSeguro, emailValido } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import BotaoGoogle from './BotaoGoogle.vue'
import CabecalhoAcesso from './CabecalhoAcesso.vue'

const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()
const { enviando, erroGeral, codigoErro, erros, executar } = useFormulario()

const dados = reactive({ email: '', senha: '', lembrar: false })
const errosLocais = reactive<{ email?: string; senha?: string }>({})
const aviso = ref<string | null>(null)
const reenvio = reactive({ enviando: false, mensagem: '' as string, erro: '' as string })
const entrandoGoogle = ref(false)

onMounted(() => {
  aviso.value = sessao.avisoEntrar
  sessao.avisoEntrar = null
  if (typeof rota.query.email === 'string') dados.email = rota.query.email
})

function validar(): boolean {
  errosLocais.email = !dados.email.trim()
    ? 'Informe seu e-mail.'
    : !emailValido(dados.email)
      ? 'Confira o e-mail: parece que falta alguma parte.'
      : undefined
  errosLocais.senha = dados.senha ? undefined : 'Informe sua senha.'
  return !errosLocais.email && !errosLocais.senha
}

async function enviar() {
  aviso.value = null
  reenvio.mensagem = ''
  reenvio.erro = ''
  if (!validar()) return
  const ok = await executar(async () => {
    await sessao.entrar(dados.email.trim(), dados.senha, dados.lembrar)
    return true
  })
  if (ok) router.replace(destinoSeguro(rota.query.voltar))
}

/** Entrar com o Google: quem já tem conta entra; quem não tem vai terminar o cadastro (o nome da empresa). */
async function entrarGoogle(credencial: string) {
  aviso.value = null
  entrandoGoogle.value = true
  const r = await executar(() => sessao.entrarComGoogle(credencial, dados.lembrar))
  entrandoGoogle.value = false
  if (r === 'entrou') router.replace(destinoSeguro(rota.query.voltar))
  else if (r === 'novo') router.push({ name: 'cadastro' })
}

async function reenviarConfirmacao() {
  reenvio.enviando = true
  reenvio.erro = ''
  try {
    const r = await authApi.reenviarConfirmacao(dados.email.trim())
    reenvio.mensagem = r?.mensagem || 'Pronto! Enviamos um novo link de confirmação para o seu e-mail.'
  } catch (e) {
    reenvio.erro = mensagemDoErro(e)
  } finally {
    reenvio.enviando = false
  }
}
</script>

<template>
  <CabecalhoAcesso titulo="Que bom ver você" descricao="Entre para acompanhar o que seus clientes estão dizendo." />

  <div class="mb-5 flex flex-col gap-3" aria-live="polite">
    <Alerta v-if="aviso" tom="atencao">{{ aviso }}</Alerta>

    <template v-if="erroGeral">
      <Alerta v-if="codigoErro === 'email_nao_confirmado'" tom="atencao" titulo="Falta confirmar seu e-mail">
        <p>{{ erroGeral }}</p>
        <p v-if="reenvio.mensagem" class="mt-2 font-medium text-sucesso">{{ reenvio.mensagem }}</p>
        <p v-else-if="reenvio.erro" class="mt-2 font-medium text-erro">{{ reenvio.erro }}</p>
        <Botao v-if="!reenvio.mensagem" class="mt-3" tamanho="sm" variante="secundario" :carregando="reenvio.enviando" @click="reenviarConfirmacao">
          Reenviar confirmação
        </Botao>
      </Alerta>
      <Alerta v-else-if="codigoErro === 'acesso_pendente'" tom="info" titulo="Seu acesso está aguardando aprovação">
        {{ erroGeral }}
        <span class="mt-1 block">Assim que um administrador da sua empresa aprovar, você já pode entrar.</span>
      </Alerta>
      <Alerta v-else-if="codigoErro === 'acesso_bloqueado'" tom="erro" titulo="Acesso bloqueado">
        {{ erroGeral }}
        <span class="mt-1 block">Se acha que é um engano, fale com o administrador da sua empresa.</span>
      </Alerta>
      <Alerta v-else tom="erro">{{ erroGeral }}</Alerta>
    </template>
  </div>

  <BotaoGoogle texto="signin_with" divisor="ou entre com seu e-mail" :ocupado="entrandoGoogle" @credencial="entrarGoogle" />

  <form class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
    <Campo
      v-model="dados.email"
      rotulo="E-mail"
      tipo="email"
      autocomplete="email"
      inputmode="email"
      autocapitalize="off"
      obrigatorio
      :erro="errosLocais.email ?? erros.email"
    />
    <div class="flex flex-col gap-1.5">
      <CampoSenha v-model="dados.senha" :erro="errosLocais.senha ?? erros.senha" />
      <RouterLink to="/esqueci-senha" class="link self-end text-sm">Esqueci a senha</RouterLink>
    </div>
    <CaixaSelecao v-model="dados.lembrar" rotulo="Lembrar de mim neste aparelho" />
    <Botao tipo="submit" tamanho="lg" bloco :carregando="enviando" class="mt-2">Entrar</Botao>
  </form>

  <div class="mt-8 flex flex-col gap-2 border-t border-borda pt-6 text-center text-sm text-texto-suave">
    <p>Ainda não usa o Toqqi? <RouterLink to="/cadastro" class="link">Criar conta</RouterLink></p>
    <p>Sua empresa já usa? <RouterLink to="/pedir-acesso" class="link">Pedir acesso à minha empresa</RouterLink></p>
  </div>
</template>
