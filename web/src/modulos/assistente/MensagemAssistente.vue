<script setup lang="ts">
// Uma resposta do ToqqiAI (o assistente de IA), com o selo dele ao lado: o texto (revelado aos poucos quando acabou de chegar; de uma vez com movimento reduzido),
// os atalhos para as telas que a pessoa pode abrir e, na última resposta, as sugestões de próxima pergunta.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ArrowRight } from 'lucide-vue-next'
import type { MensagemConversa } from '@/stores/assistente'
import { useSessaoStore } from '@/stores/sessao'
import IconeToqqiAI from '@/components/app/IconeToqqiAI.vue'
import Botao from '@/components/ui/Botao.vue'
import { atalhosDaResposta } from '@/modulos/ajuda/atalhos'
import TextoAssistente from './TextoAssistente.vue'
import { semMovimento } from './logica'

const props = defineProps<{
  mensagem: MensagemConversa
  /** Só a última resposta mostra as sugestões. */
  ultima?: boolean
  /** Sugestões desligadas (enviando outra pergunta ou assistente indisponível). */
  desabilitado?: boolean
}>()
const emit = defineEmits<{ revelada: []; progresso: []; sugestao: [texto: string] }>()

const sessao = useSessaoStore()
const atalhos = computed(() => atalhosDaResposta(props.mensagem.atalhos, { pode: sessao.pode, admin: sessao.admin }))
const sugestoes = computed(() => (props.ultima ? (props.mensagem.sugestoes ?? []) : []))

// Efeito curto de digitação: ~40 passos de 20 ms, qualquer que seja o tamanho da resposta.
const revelando = ref(false)
const visiveis = ref(0)
let relogio: ReturnType<typeof setInterval> | undefined

function terminar() {
  if (relogio) clearInterval(relogio)
  relogio = undefined
  if (!revelando.value) return
  revelando.value = false
  emit('revelada')
}

onMounted(() => {
  if (!props.mensagem.nova) return
  const total = props.mensagem.texto.length
  if (semMovimento() || total === 0) {
    emit('revelada')
    return
  }
  revelando.value = true
  const passo = Math.max(3, Math.ceil(total / 40))
  relogio = setInterval(() => {
    visiveis.value = Math.min(total, visiveis.value + passo)
    emit('progresso')
    if (visiveis.value >= total) terminar()
  }, 20)
})
onBeforeUnmount(() => {
  if (relogio) clearInterval(relogio)
})

defineExpose({ terminar })
</script>

<template>
  <li class="flex items-start gap-2" data-papel="assistente">
    <IconeToqqiAI variante="selo" class="mt-0.5 size-6" data-avatar />
    <div class="flex min-w-0 flex-1 flex-col items-start gap-2">
      <div class="max-w-full break-words rounded-2xl rounded-bl-md bg-superficie-2 px-3.5 py-2.5 text-sm leading-relaxed text-texto">
        <span class="sr-only">ToqqiAI: </span>
        <TextoAssistente :texto="revelando ? mensagem.texto.slice(0, visiveis) : mensagem.texto" />
      </div>
      <template v-if="!revelando">
        <div v-if="atalhos.length" class="flex flex-wrap gap-2" data-atalhos>
          <Botao v-for="a in atalhos" :key="a.chave" :para="a.caminho" variante="secundario" tamanho="sm">
            Abrir {{ a.rotulo }} <ArrowRight class="size-4" aria-hidden="true" />
          </Botao>
        </div>
        <ul v-if="sugestoes.length" class="flex flex-col items-start gap-1.5" aria-label="Sugestões de perguntas" data-sugestoes>
          <li v-for="s in sugestoes" :key="s" class="max-w-full">
            <button
              type="button"
              class="max-w-full rounded-xl border border-borda-forte bg-superficie px-3 py-1.5 text-left text-sm text-texto-suave transition-colors hover:border-marca/40 hover:bg-marca-suave hover:text-texto disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="desabilitado"
              @click="emit('sugestao', s)"
            >
              {{ s }}
            </button>
          </li>
        </ul>
      </template>
    </div>
  </li>
</template>
