<script setup lang="ts">
// Editar os dados de cobrança da assinatura (cliente no Asaas): PUT /assinatura/dados. Sem mudança, não salva.
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { assinaturaApi, type DadosCobranca, type EstadoAssinatura } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Modal from '@/components/ui/Modal.vue'
import CamposCobranca from './CamposCobranca.vue'
import { corpoCobranca, formCobrancaDe, mesmosDadosCobranca, validarCobranca, type FormCobranca } from './logica'

const props = defineProps<{ dados: DadosCobranca; disponivel: boolean }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [EstadoAssinatura] }>()

const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const original = ref<FormCobranca>(formCobrancaDe(null))
const form = ref<FormCobranca>(formCobrancaDe(null))
const locais = reactive<Partial<Record<keyof FormCobranca, string>>>({})
const raiz = ref<HTMLFormElement | null>(null)

function limparTudo() {
  limpar()
  for (const k of Object.keys(locais) as (keyof FormCobranca)[]) delete locais[k]
}

watch(aberto, (v) => {
  if (!v) return
  limparTudo()
  original.value = formCobrancaDe(props.dados)
  form.value = { ...original.value }
})

const alterado = computed(() => !mesmosDadosCobranca(form.value, original.value))
const errosForm = computed(() => ({
  razao_social: locais.razao_social ?? erros.razao_social,
  documento: locais.documento ?? erros.documento,
  email_cobranca: locais.email_cobranca ?? erros.email_cobranca,
  telefone: locais.telefone ?? erros.telefone,
}))

async function focarPrimeiroErro() {
  await nextTick()
  raiz.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

async function salvar() {
  if (!alterado.value || enviando.value) return
  limparTudo()
  const v = validarCobranca(form.value)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    erroGeral.value = 'Confira os campos destacados.'
    focarPrimeiroErro()
    return
  }
  const r = await executar(() => assinaturaApi.alterarDados(corpoCobranca(form.value)))
  if (!r) {
    focarPrimeiroErro()
    return
  }
  emit('salvo', r)
  avisar.sucesso('Dados de cobrança salvos.')
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Dados de cobrança" descricao="As próximas faturas saem com estes dados." tamanho="lg" :bloqueado="enviando">
    <form id="form-dados-cobranca" ref="raiz" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="!disponivel" tom="info">A cobrança online ainda não está disponível. Fale com a equipe Toqqi.</Alerta>
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <CamposCobranca v-model="form" :erros="errosForm" :desabilitado="enviando || !disponivel" />
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-dados-cobranca" :carregando="enviando" :desabilitado="!alterado || !disponivel">Salvar dados</Botao>
    </template>
  </Modal>
</template>
