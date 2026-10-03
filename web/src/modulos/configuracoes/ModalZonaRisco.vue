<script setup lang="ts">
// Confirmação da Zona de risco (etapa 5f), como ModalExcluirConta: alertdialog com o que vai ser apagado, o link para
// baixar todos os dados antes e o campo APAGAR (em qualquer caixa, sem espaços nas pontas, a regra da API). "Apagar
// para sempre" só com APAGAR. Erro: a mensagem da API (no campo, quando é da confirmação). O foco volta ao gatilho
// quando fecha (Modal).
import { computed, nextTick, ref, watch } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { ApiError, dadosContaApi, type OpcaoZonaRisco, type ResultadoZonaRisco, type ZonaRisco } from '@/api'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'
import { PALAVRA_CONFIRMACAO, ROTULOS_OPCAO, confirmacaoValida, mensagemErroZona, textoOpcao, type MensagemExportacao } from './dadosConta'

const props = defineProps<{
  opcao: OpcaoZonaRisco
  zona: ZonaRisco | null
  /** O .zip está sendo gerado (o mesmo estado do botão da página). */
  baixando: boolean
  mensagemExportacao: MensagemExportacao | null
}>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ apagado: [ResultadoZonaRisco]; baixar: [] }>()

const confirmacao = ref('')
const enviando = ref(false)
const erroTopo = ref<string | null>(null)
const erroCampo = ref<string | null>(null)
const campo = ref<InstanceType<typeof Campo> | null>(null)

const valida = computed(() => confirmacaoValida(confirmacao.value))
const titulo = computed(() => ROTULOS_OPCAO[props.opcao].titulo)
const descricao = computed(() => (props.zona ? textoOpcao(props.opcao, props.zona) : ''))

watch(aberto, (v) => {
  if (!v) return
  confirmacao.value = ''
  erroTopo.value = null
  erroCampo.value = null
})
// Depois de um erro no campo, digitar de novo limpa a mensagem.
watch(confirmacao, () => (erroCampo.value = null))

async function apagar() {
  if (enviando.value || !valida.value) return
  enviando.value = true
  erroTopo.value = null
  erroCampo.value = null
  try {
    const r = await dadosContaApi.apagar(props.opcao, confirmacao.value.trim())
    aberto.value = false
    emit('apagado', r)
  } catch (e) {
    const doCampo = e instanceof ApiError ? e.campo('confirmacao') : undefined
    if (doCampo) {
      erroCampo.value = doCampo
      await nextTick()
      campo.value?.focar()
    } else {
      erroTopo.value = mensagemErroZona(e)
    }
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="titulo" tamanho="sm" papel="alertdialog" :bloqueado="enviando">
    <form id="form-zona-risco" class="flex flex-col gap-4" novalidate data-modal-zona @submit.prevent="apagar">
      <Alerta tom="erro" titulo="Isso não tem volta">
        <p data-resumo-opcao>{{ descricao }}</p>
        <p class="mt-2">
          <button type="button" class="link font-semibold" :aria-disabled="baixando ? 'true' : undefined" data-baixar-antes @click="!baixando && emit('baixar')">
            Baixar todos os dados antes
          </button>
        </p>
        <!-- Sempre no lugar (vazio quando não há o que dizer), para o leitor de tela anunciar o andamento. -->
        <p aria-live="polite" :class="mensagemExportacao?.tom === 'erro' ? 'font-medium text-erro' : ''" data-status-exportacao-modal>{{ mensagemExportacao?.texto ?? '' }}</p>
      </Alerta>
      <Alerta v-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>
      <Campo
        ref="campo"
        v-model="confirmacao"
        :rotulo="`Para confirmar, digite ${PALAVRA_CONFIRMACAO}`"
        autocomplete="off"
        autocorrect="off"
        autocapitalize="off"
        spellcheck="false"
        :erro="erroCampo"
        data-campo-confirmacao
      />
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <!-- Desligado de verdade até digitar APAGAR; enquanto apaga, continua no Tab (o foco não cai no <body>). -->
      <Botao tipo="submit" form="form-zona-risco" variante="perigo" :carregando="enviando" :desabilitado="!valida" :focavel="enviando" data-apagar-para-sempre>
        <Trash2 v-if="!enviando" class="size-4" aria-hidden="true" /> Apagar para sempre
      </Botao>
    </template>
  </Modal>
</template>
