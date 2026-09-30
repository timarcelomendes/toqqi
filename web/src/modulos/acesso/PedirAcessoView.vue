<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Building2, Hourglass } from 'lucide-vue-next'
import { authApi } from '@/api'
import { useFormulario } from '@/composables/formulario'
import { emailValido } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import CabecalhoAcesso from './CabecalhoAcesso.vue'

const { enviando, erroGeral, erros, executar } = useFormulario()
const dados = reactive({ nome: '', email: '', senha: '' })
const senhaOk = ref(false)
const locais = reactive<Record<string, string | undefined>>({})
const concluido = ref<string | null>(null)

async function enviar() {
  locais.nome = dados.nome.trim() ? undefined : 'Informe seu nome.'
  locais.email = emailValido(dados.email) ? undefined : 'Informe seu e-mail da empresa.'
  locais.senha = senhaOk.value ? undefined : 'A senha ainda não cumpre todas as regras.'
  if (locais.nome || locais.email || locais.senha) return
  const r = await executar(() => authApi.pedirAcesso({ nome: dados.nome.trim(), email: dados.email.trim(), senha: dados.senha }))
  if (r) concluido.value = r.mensagem || 'Pedido enviado.'
}
</script>

<template>
  <template v-if="concluido">
    <CabecalhoAcesso :icone="Hourglass" tom="sucesso" titulo="Pedido registrado" :descricao="concluido" />
    <Alerta tom="info">
      Se a sua empresa usa o Toqqi e liberou o domínio do seu e-mail, um administrador vai analisar o pedido. Depois
      de aprovado, confirme seu e-mail (se pedirmos) e entre normalmente.
    </Alerta>
    <Botao para="/entrar" variante="secundario" bloco class="mt-6">Voltar para Entrar</Botao>
  </template>
  <template v-else>
    <CabecalhoAcesso
      :icone="Building2"
      titulo="Pedir acesso à minha empresa"
      descricao="Sua empresa já usa o Toqqi? Use seu e-mail corporativo e um administrador aprova seu acesso."
    />
    <Alerta v-if="erroGeral" tom="erro" class="mb-5">{{ erroGeral }}</Alerta>
    <form class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <Campo v-model="dados.nome" rotulo="Seu nome" autocomplete="name" obrigatorio :erro="locais.nome ?? erros.nome" />
      <Campo
        v-model="dados.email"
        rotulo="E-mail corporativo"
        tipo="email"
        autocomplete="email"
        inputmode="email"
        autocapitalize="off"
        placeholder="voce@suaempresa.com.br"
        dica="O mesmo domínio que a sua empresa usa (nada de Gmail ou Hotmail)."
        obrigatorio
        :erro="locais.email ?? erros.email"
      />
      <CampoSenha v-model="dados.senha" v-model:valida="senhaOk" rotulo="Crie uma senha" autocomplete="new-password" com-regras :erro="locais.senha ?? erros.senha" />
      <Botao tipo="submit" tamanho="lg" bloco :carregando="enviando" class="mt-2">Pedir acesso</Botao>
    </form>
    <p class="mt-6 border-t border-borda pt-6 text-center text-sm text-texto-suave">
      Já tem acesso? <RouterLink to="/entrar" class="link">Entrar</RouterLink>
    </p>
  </template>
</template>
