<script setup lang="ts">
import { reactive, watch } from 'vue'
import { euApi } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { PERFIS } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import SecaoCartao from './SecaoCartao.vue'

const sessao = useSessaoStore()
const { enviando, erroGeral, erros, executar } = useFormulario()
const dados = reactive({ nome: '', cargo: '' })
const locais = reactive<{ nome?: string }>({})

watch(
  () => sessao.usuario,
  (u) => {
    dados.nome = u?.nome ?? ''
    dados.cargo = u?.cargo ?? ''
  },
  { immediate: true },
)

async function salvar() {
  locais.nome = dados.nome.trim() ? undefined : 'Informe seu nome.'
  if (locais.nome) return
  const u = await executar(() => euApi.atualizar({ nome: dados.nome.trim(), cargo: dados.cargo.trim() || null }))
  if (u) {
    sessao.atualizarUsuario(u)
    avisar.sucesso('Seus dados foram salvos.')
  }
}
</script>

<template>
  <SecaoCartao titulo="Seus dados" descricao="Como você aparece para a sua equipe.">
    <form class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo v-model="dados.nome" rotulo="Nome" autocomplete="name" obrigatorio :erro="locais.nome ?? erros.nome" />
        <Campo v-model="dados.cargo" rotulo="Cargo" opcional placeholder="Ex.: Gerente comercial" autocomplete="organization-title" :erro="erros.cargo" />
      </div>
      <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <p class="text-texto-suave">E-mail: <strong class="font-semibold text-texto">{{ sessao.usuario?.email }}</strong></p>
        <p v-if="sessao.usuario" class="flex items-center gap-2 text-texto-suave">
          Perfil: <Etiqueta :tom="PERFIS[sessao.usuario.perfil]?.tom">{{ PERFIS[sessao.usuario.perfil]?.rotulo ?? sessao.usuario.perfil }}</Etiqueta>
        </p>
      </div>
      <div>
        <Botao tipo="submit" :carregando="enviando">Salvar dados</Botao>
      </div>
    </form>
  </SecaoCartao>
</template>
