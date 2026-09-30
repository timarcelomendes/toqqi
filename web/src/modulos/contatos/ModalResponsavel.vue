<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { responsaveisApi, type DadosResponsavel, type Responsavel } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { emailValido } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{ responsavel: Responsavel | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [Responsavel] }>()

const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const novo = computed(() => !props.responsavel)
const dados = reactive({ nome: '', funcao: '', email: '', foto_url: '', teams_webhook: '' })
const locais = reactive<Record<string, string | undefined>>({})

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  const r = props.responsavel
  Object.assign(dados, {
    nome: r?.nome ?? '',
    funcao: r?.funcao ?? '',
    email: r?.email ?? '',
    foto_url: r?.foto_url ?? '',
    teams_webhook: r?.teams_webhook ?? '',
  })
})

function erro(campo: string) {
  return locais[campo] ?? erros[campo]
}

async function salvar() {
  locais.nome = dados.nome.trim() ? undefined : 'Informe o nome.'
  locais.email = dados.email.trim() && !emailValido(dados.email) ? 'Confira o e-mail.' : undefined
  locais.foto_url = dados.foto_url.trim() && !/^https?:\/\//i.test(dados.foto_url.trim()) ? 'Use um endereço que comece com https://' : undefined
  locais.teams_webhook =
    dados.teams_webhook.trim() && !/^https:\/\//i.test(dados.teams_webhook.trim()) ? 'O endereço do Teams precisa começar com https://' : undefined
  if (Object.values(locais).some(Boolean)) return
  const corpo: DadosResponsavel = {
    nome: dados.nome.trim(),
    funcao: dados.funcao.trim() || null,
    email: dados.email.trim() || null,
    foto_url: dados.foto_url.trim() || null,
    teams_webhook: dados.teams_webhook.trim() || null,
  }
  const r = await executar(() => (novo.value ? responsaveisApi.criar(corpo) : responsaveisApi.atualizar(props.responsavel!.id, corpo)))
  if (!r) return
  emit('salvo', r)
  avisar.sucesso(novo.value ? `${r.nome} foi cadastrado(a).` : 'Alterações salvas.')
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="novo ? 'Novo responsável' : 'Editar responsável'" descricao="Quem da sua empresa cuida de uma carteira de clientes." :bloqueado="enviando">
    <form id="form-responsavel" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroGeral && !Object.keys(erros).length" tom="erro">{{ erroGeral }}</Alerta>
      <Campo v-model="dados.nome" rotulo="Nome" obrigatorio data-autofoco maxlength="150" :erro="erro('nome')" />
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo v-model="dados.funcao" rotulo="Função" opcional placeholder="Ex.: Gerente de contas" maxlength="120" :erro="erro('funcao')" />
        <Campo v-model="dados.email" rotulo="E-mail" tipo="email" opcional inputmode="email" :erro="erro('email')" />
      </div>
      <Campo v-model="dados.foto_url" rotulo="Endereço da foto" opcional tipo="url" placeholder="https://…" :erro="erro('foto_url')" />
      <Campo
        v-model="dados.teams_webhook"
        rotulo="Aviso no Microsoft Teams"
        opcional
        tipo="url"
        placeholder="https://…webhook.office.com/…"
        :erro="erro('teams_webhook')"
        dica="Cole o endereço do webhook do canal do Teams. Assim essa pessoa recebe avisos das respostas da carteira dela."
      />
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-responsavel" :carregando="enviando">{{ novo ? 'Cadastrar' : 'Salvar' }}</Botao>
    </template>
  </Modal>
</template>
