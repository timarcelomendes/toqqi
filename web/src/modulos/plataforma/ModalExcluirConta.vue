<script setup lang="ts">
// Exclusão definitiva de uma conta (superadmin): exige digitar o nome da empresa.
import { computed, ref, watch } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { plataformaContasApi, type ContaPlataforma } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{ conta: ContaPlataforma | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ excluida: [ContaPlataforma] }>()

const { enviando, erroGeral, codigoErro, executar, limpar } = useFormulario()
const nome = ref('')

/** Mesma regra da API: sem diferenciar maiúsculas (e sem espaços nas pontas). */
const confere = computed(
  () => !!props.conta && nome.value.trim().toLocaleLowerCase('pt-BR') === props.conta.nome.trim().toLocaleLowerCase('pt-BR'),
)

watch(aberto, (v) => {
  if (!v) return
  limpar()
  nome.value = ''
})

async function excluir() {
  const c = props.conta
  if (!c || !confere.value) return
  const ok = await executar(async () => {
    await plataformaContasApi.excluir(c.id, nome.value.trim())
    return true
  })
  if (!ok) return
  avisar.sucesso(`A conta ${c.nome} foi excluída.`)
  aberto.value = false
  emit('excluida', c)
}

const erroCampo = computed(() => (codigoErro.value === 'nome_nao_confere' ? erroGeral.value || 'O nome não confere.' : null))
const erroTopo = computed(() => (codigoErro.value === 'nome_nao_confere' ? null : erroGeral.value))
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="conta ? `Excluir a conta ${conta.nome}?` : 'Excluir conta'" tamanho="sm" papel="alertdialog" :bloqueado="enviando">
    <form id="form-excluir-conta" class="flex flex-col gap-4" novalidate @submit.prevent="excluir">
      <Alerta tom="erro" titulo="Isso não tem volta">
        Apaga a conta e tudo o que é dela: usuários, contatos, empresas, formulários, respostas e envios. Ninguém da empresa consegue mais entrar.
      </Alerta>
      <Alerta v-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>
      <Campo
        v-model="nome"
        rotulo="Para confirmar, digite o nome da conta"
        autocomplete="off"
        spellcheck="false"
        :placeholder="conta?.nome"
        :erro="erroCampo"
        :dica="conta ? `Digite: ${conta.nome}` : undefined"
      />
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-excluir-conta" variante="perigo" :carregando="enviando" :desabilitado="!confere">
        <Trash2 v-if="!enviando" class="size-4" aria-hidden="true" /> Excluir para sempre
      </Botao>
    </template>
  </Modal>
</template>
