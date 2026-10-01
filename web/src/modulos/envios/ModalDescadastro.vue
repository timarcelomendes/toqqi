<script setup lang="ts">
// Registra um pedido de descadastro recebido fora do e-mail (telefone, balcão...).
import { ref, watch } from 'vue'
import { enviosApi } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'

const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ registrado: [] }>()
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const email = ref('')
const motivo = ref('')

watch(aberto, (v) => {
  if (!v) return
  limpar()
  email.value = ''
  motivo.value = ''
})

async function registrar() {
  limpar()
  const e = email.value.trim().toLowerCase()
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) {
    erros.email = 'Confira o e-mail.'
    return
  }
  const ok = await executar(async () => {
    await enviosApi.registrarDescadastro({ email: e, ...(motivo.value.trim() ? { motivo: motivo.value.trim() } : {}) })
    return true
  })
  if (!ok) return
  avisar.sucesso(`${e} não vai mais receber pesquisas.`)
  aberto.value = false
  emit('registrado')
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    titulo="Registrar descadastro"
    descricao="Para quando o cliente pede por telefone, pessoalmente ou por outro canal para não receber mais pesquisas."
    :bloqueado="enviando"
  >
    <form id="form-descadastro" class="flex flex-col gap-4" novalidate @submit.prevent="registrar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <Campo v-model="email" rotulo="E-mail do cliente" tipo="email" autocomplete="off" obrigatorio :erro="erros.email" />
      <AreaTexto v-model="motivo" rotulo="Motivo" opcional :maximo="300" :linhas="2" :erro="erros.motivo" placeholder="Ex.: pediu por telefone em 12/03" />
      <Alerta tom="info">
        Depois de registrado, a sua equipe não consegue desfazer. Só a própria pessoa volta a receber, pelo link
        "Não quero mais receber pesquisas" de um e-mail antigo.
      </Alerta>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-descadastro" :carregando="enviando">Registrar descadastro</Botao>
    </template>
  </Modal>
</template>
