<script setup lang="ts">
// Cria ou edita um aviso para outro sistema (webhook). Ao criar, o segredo volta para a tela mostrar uma vez.
import { computed, reactive, watch } from 'vue'
import { webhooksApi, type EventoWebhook, type Webhook, type WebhookCriado } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { EVENTOS_WEBHOOK } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Modal from '@/components/ui/Modal.vue'
import { validarUrlWebhook } from './logica'

const props = defineProps<{ webhook: Webhook | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ criado: [w: WebhookCriado]; salvo: [w: Webhook] }>()

const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const dados = reactive({
  url: '',
  eventos: { 'resposta.criada': true, 'contato.descadastrado': false, 'indicacao.criada': false, 'indicacao.atualizada': false } as Record<EventoWebhook, boolean>,
})
const editando = computed(() => !!props.webhook)
const eventos = Object.keys(EVENTOS_WEBHOOK) as EventoWebhook[]

watch(aberto, (v) => {
  if (!v) return
  limpar()
  dados.url = props.webhook?.url ?? ''
  for (const e of eventos) dados.eventos[e] = props.webhook ? props.webhook.eventos.includes(e) : e === 'resposta.criada'
})

async function salvar() {
  limpar()
  const url = dados.url.trim()
  const escolhidos = eventos.filter((e) => dados.eventos[e])
  const erroUrl = validarUrlWebhook(url)
  if (erroUrl) erros.url = erroUrl
  if (!escolhidos.length) erros.eventos = 'Escolha pelo menos um aviso.'
  if (erroUrl || !escolhidos.length) return

  if (props.webhook) {
    const r = await executar(() => webhooksApi.atualizar(props.webhook!.id, { url, eventos: escolhidos }))
    if (!r) return
    avisar.sucesso('Aviso atualizado.')
    aberto.value = false
    emit('salvo', r)
  } else {
    const r = await executar(() => webhooksApi.criar({ url, eventos: escolhidos }))
    if (!r) return
    aberto.value = false
    emit('criado', r)
  }
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    :titulo="editando ? 'Editar aviso' : 'Novo aviso para outro sistema'"
    descricao="O Toqqi avisa o endereço abaixo, na hora, quando algo acontecer."
    :bloqueado="enviando"
  >
    <form id="form-webhook" class="flex flex-col gap-5" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <Campo
        v-model="dados.url"
        rotulo="Endereço que recebe os avisos"
        tipo="url"
        inputmode="url"
        autocomplete="off"
        spellcheck="false"
        obrigatorio
        placeholder="https://seusistema.com.br/toqqi"
        :erro="erros.url"
        dica="Precisa começar com https:// e ser um endereço público da internet."
      />
      <fieldset class="flex flex-col gap-3" :aria-describedby="erros.eventos ? 'erro-eventos-webhook' : undefined">
        <legend class="mb-1 text-sm font-semibold text-texto">Avisar quando</legend>
        <CaixaSelecao
          v-for="e in eventos"
          :key="e"
          v-model="dados.eventos[e]"
          :rotulo="EVENTOS_WEBHOOK[e].rotulo"
          :descricao="EVENTOS_WEBHOOK[e].descricao"
        />
        <p v-if="erros.eventos" id="erro-eventos-webhook" class="text-sm font-medium text-erro">{{ erros.eventos }}</p>
      </fieldset>
      <p v-if="!editando" class="text-sm text-texto-fraco">Depois de criar, mostramos um segredo para o técnico conferir que o aviso veio mesmo do Toqqi.</p>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-webhook" :carregando="enviando">{{ editando ? 'Salvar' : 'Criar aviso' }}</Botao>
    </template>
  </Modal>
</template>
