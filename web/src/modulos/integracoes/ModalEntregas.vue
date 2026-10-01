<script setup lang="ts">
// Últimas entregas de um webhook (30 dias), página a página.
import { onBeforeUnmount, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, Inbox } from 'lucide-vue-next'
import { mensagemDoErro, webhooksApi, type EntregaWebhook, type Webhook } from '@/api'
import { formatarDataHora } from '@/utils/datas'
import { rotuloEventoWebhook } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Modal from '@/components/ui/Modal.vue'
import { lerPaginaEntregas } from './logica'

const props = defineProps<{ webhook: Webhook | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })

const itens = ref<EntregaWebhook[]>([])
const pagina = ref(1)
const temMais = ref(false)
const tamanhoPrimeira = ref(0)
const carregando = ref(false)
const erro = ref<string | null>(null)
let controle: AbortController | null = null

async function carregar() {
  if (!props.webhook) return
  controle?.abort()
  controle = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await webhooksApi.entregas(props.webhook.id, pagina.value, controle.signal)
    const lido = lerPaginaEntregas(r, pagina.value, tamanhoPrimeira.value)
    itens.value = lido.itens
    temMais.value = lido.temMais
    tamanhoPrimeira.value = lido.tamanho
  } catch (e) {
    if (e instanceof DOMException) return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

watch(aberto, (v) => {
  if (!v) {
    controle?.abort()
    return
  }
  itens.value = []
  pagina.value = 1
  tamanhoPrimeira.value = 0
  carregar()
})

function mudar(delta: number) {
  pagina.value = Math.max(1, pagina.value + delta)
  carregar()
}

onBeforeUnmount(() => controle?.abort())
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Avisos enviados" :descricao="webhook ? `Para ${webhook.url}, nos últimos 30 dias.` : undefined" tamanho="lg">
    <Carregando v-if="carregando && !itens.length" :linhas="4" />
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <EstadoVazio
      v-else-if="!itens.length"
      :icone="Inbox"
      :titulo="pagina > 1 ? 'Não há avisos mais antigos' : 'Nenhum aviso enviado ainda'"
      :descricao="pagina > 1 ? 'Volte para a página anterior.' : 'Quando acontecer um dos eventos escolhidos, o aviso aparece aqui.'"
    />
    <ul v-else class="flex flex-col divide-y divide-borda" :aria-busy="carregando">
      <li v-for="e in itens" :key="e.id" class="flex flex-col gap-1 py-3 sm:flex-row sm:items-start sm:gap-4">
        <div class="min-w-0 flex-1">
          <p class="font-semibold text-texto">{{ rotuloEventoWebhook(e.evento) }}</p>
          <p class="text-sm text-texto-fraco">
            {{ formatarDataHora(e.criado_em) }} · {{ e.tentativas === 1 ? '1 tentativa' : `${e.tentativas} tentativas` }}
            <template v-if="e.status_http"> · resposta {{ e.status_http }}</template>
          </p>
          <p v-if="e.erro" class="mt-0.5 break-words text-sm text-erro">{{ e.erro }}</p>
        </div>
        <Etiqueta :tom="e.ok ? 'sucesso' : 'erro'" ponto class="self-start">{{ e.ok ? 'Entregue' : 'Não entregue' }}</Etiqueta>
      </li>
    </ul>
    <template #rodape>
      <div v-if="pagina > 1 || temMais" class="flex items-center gap-2 sm:mr-auto">
        <Botao variante="secundario" tamanho="sm" :desabilitado="pagina <= 1 || carregando" @click="mudar(-1)">
          <ChevronLeft class="size-4" aria-hidden="true" /> Mais recentes
        </Botao>
        <span class="text-sm text-texto-fraco">Página {{ pagina }}</span>
        <Botao variante="secundario" tamanho="sm" :desabilitado="!temMais || carregando" @click="mudar(1)">
          Mais antigos <ChevronRight class="size-4" aria-hidden="true" />
        </Botao>
      </div>
      <Botao variante="secundario" @click="aberto = false">Fechar</Botao>
    </template>
  </Modal>
</template>
