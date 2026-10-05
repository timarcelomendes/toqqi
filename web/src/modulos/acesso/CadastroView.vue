<script setup lang="ts">
import { reactive, ref } from 'vue'
import { MailCheck } from 'lucide-vue-next'
import { authApi, mensagemDoErro } from '@/api'
import { useFormulario } from '@/composables/formulario'
import { usarDiasTeste } from '@/composables/planosPublicos'
import { apenasDigitos, emailValido, formatarTelefone } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import CabecalhoAcesso from './CabecalhoAcesso.vue'
import { apagarOrigem, origemParaCadastro } from '@/site/origem'

const { enviando, erroGeral, erros, executar } = useFormulario()
const dados = reactive({ empresa: '', nome: '', email: '', telefone: '', senha: '', aceite: false })
const senhaOk = ref(false)
const locais = reactive<Record<string, string | undefined>>({})
const concluido = ref<string | null>(null)
const reenvio = reactive({ enviando: false, mensagem: '' })
/** Etapa 5g: os dias do teste vêm de Plataforma › Parâmetros (GET /publico/planos); carregando ou com falha, 14. */
const diasTeste = usarDiasTeste()

function validar(): boolean {
  locais.empresa = dados.empresa.trim() ? undefined : 'Informe o nome da sua empresa.'
  locais.nome = dados.nome.trim() ? undefined : 'Informe seu nome.'
  locais.email = !dados.email.trim()
    ? 'Informe seu e-mail.'
    : emailValido(dados.email)
      ? undefined
      : 'Confira o e-mail: parece que falta alguma parte.'
  const tel = apenasDigitos(dados.telefone)
  locais.telefone = tel && (tel.length < 10 || tel.length > 11) ? 'Informe o número com DDD, ex.: (11) 91234-5678.' : undefined
  locais.senha = senhaOk.value ? undefined : 'A senha ainda não cumpre todas as regras abaixo.'
  locais.aceite_termos = dados.aceite ? undefined : 'Para continuar, aceite os termos de uso e a política de privacidade.'
  return !Object.values(locais).some(Boolean)
}

function erro(campo: string) {
  return locais[campo] ?? erros[campo]
}

async function enviar() {
  if (!validar()) return
  const tel = apenasDigitos(dados.telefone)
  const r = await executar(() =>
    authApi.cadastrar({
      empresa: dados.empresa.trim(),
      nome: dados.nome.trim(),
      email: dados.email.trim(),
      senha: dados.senha,
      ...(tel ? { telefone: tel } : {}),
      aceite_termos: true,
      origem: origemParaCadastro(),
    }),
  )
  if (r) apagarOrigem()
  if (r) concluido.value = r.mensagem || 'Enviamos um link de confirmação para o seu e-mail.'
}

async function reenviar() {
  reenvio.enviando = true
  try {
    const r = await authApi.reenviarConfirmacao(dados.email.trim())
    reenvio.mensagem = r?.mensagem || 'Enviamos um novo link. Confira também a caixa de spam.'
  } catch (e) {
    reenvio.mensagem = mensagemDoErro(e)
  } finally {
    reenvio.enviando = false
  }
}
</script>

<template>
  <template v-if="concluido">
    <CabecalhoAcesso :icone="MailCheck" tom="sucesso" titulo="Confira o seu e-mail">
      <p class="mt-2 text-[0.95rem] leading-relaxed text-texto-suave">
        {{ concluido }} Enviamos para <strong class="text-texto">{{ dados.email }}</strong>. Clique no link para ativar
        sua conta e começar seus {{ diasTeste }} dias grátis.
      </p>
    </CabecalhoAcesso>
    <Alerta tom="info">Não chegou em alguns minutos? Olhe a caixa de spam ou promoções.</Alerta>
    <div class="mt-6 flex flex-col gap-3">
      <p v-if="reenvio.mensagem" class="text-sm font-medium text-texto-suave" role="status">{{ reenvio.mensagem }}</p>
      <Botao v-else variante="secundario" bloco :carregando="reenvio.enviando" @click="reenviar">Reenviar e-mail</Botao>
      <Botao para="/entrar" variante="fantasma" bloco>Ir para Entrar</Botao>
    </div>
  </template>

  <template v-else>
    <CabecalhoAcesso titulo="Crie sua conta" :descricao="`Em poucos minutos você começa a ouvir seus clientes. ${diasTeste} dias grátis, sem cartão.`" />
    <Alerta v-if="erroGeral" tom="erro" class="mb-5">{{ erroGeral }}</Alerta>
    <form class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <Campo v-model="dados.empresa" rotulo="Nome da empresa" autocomplete="organization" obrigatorio :erro="erro('empresa')" />
      <Campo v-model="dados.nome" rotulo="Seu nome" autocomplete="name" obrigatorio :erro="erro('nome')" />
      <Campo
        v-model="dados.email"
        rotulo="E-mail de trabalho"
        tipo="email"
        autocomplete="email"
        inputmode="email"
        autocapitalize="off"
        obrigatorio
        :erro="erro('email')"
      />
      <Campo
        :model-value="dados.telefone"
        rotulo="WhatsApp"
        opcional
        tipo="tel"
        autocomplete="tel-national"
        inputmode="tel"
        placeholder="(11) 91234-5678"
        dica="Só para te ajudar, se precisar. Não enviamos propaganda."
        :mascara="formatarTelefone"
        :erro="erro('telefone')"
        @update:model-value="(v: string) => (dados.telefone = v)"
      />
      <CampoSenha
        v-model="dados.senha"
        v-model:valida="senhaOk"
        rotulo="Crie uma senha"
        autocomplete="new-password"
        com-regras
        :erro="erro('senha')"
      />
      <div class="flex flex-col gap-1.5">
        <CaixaSelecao v-model="dados.aceite" rotulo="Li e aceito os termos">
          Li e aceito os <RouterLink to="/termos" target="_blank" class="link">termos de uso</RouterLink> e a
          <RouterLink to="/privacidade" target="_blank" class="link">política de privacidade</RouterLink>.
        </CaixaSelecao>
        <p v-if="erro('aceite_termos')" class="pl-8 text-sm font-medium text-erro">{{ erro('aceite_termos') }}</p>
      </div>
      <Botao tipo="submit" tamanho="lg" bloco :carregando="enviando" class="mt-2">Começar {{ diasTeste }} dias grátis</Botao>
    </form>
    <p class="mt-6 border-t border-borda pt-6 text-center text-sm text-texto-suave">
      Já tem conta? <RouterLink to="/entrar" class="link">Entrar</RouterLink>
    </p>
  </template>
</template>
