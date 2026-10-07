<script setup lang="ts">
// Um feedback da pessoa (/feedback/:id): a conversa com a equipe Toqqi, a caixa para escrever mais (texto e até 3
// imagens) e, no elogio, a autorização de usar como depoimento no site do Toqqi (dá para retirar). Abrir marca como
// visto (a API), e o número do menu se acerta.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Send } from 'lucide-vue-next'
import { feedbackApi, mensagemDoErro, type Feedback } from '@/api'
import { ApiError } from '@/api/erros'
import { avisar } from '@/composables/avisos'
import { usarFeedback } from '@/composables/feedback'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import CampoImagens, { type ImagemEscolhida } from './CampoImagens.vue'
import ConversaFeedback from './ConversaFeedback.vue'
import { MAX_TEXTO, erroDoTexto, infoSituacao, infoTipo, rotuloImpacto, rotuloQuando } from './logica'

const rota = useRoute()
const { atualizarNovidades } = usarFeedback()

const feedback = ref<Feedback | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const naoAchou = ref(false)
const texto = ref('')
const imagens = ref<ImagemEscolhida[]>([])
const erroTexto = ref<string | null>(null)
const enviando = ref(false)
const salvandoAutorizacao = ref(false)
let controlador: AbortController | null = null

const fid = computed(() => Number(rota.params.id))
const fechado = computed(() => feedback.value?.situacao === 'concluido' || feedback.value?.situacao === 'encerrado')

async function carregar() {
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  naoAchou.value = false
  try {
    feedback.value = await feedbackApi.detalhe(fid.value, controlador.signal)
    void atualizarNovidades(true)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    if (e instanceof ApiError && e.status === 404) naoAchou.value = true
    else erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

watch(fid, () => void carregar(), { immediate: true })
onBeforeUnmount(() => controlador?.abort())

async function enviar() {
  if (!feedback.value || enviando.value) return
  erroTexto.value = erroDoTexto(texto.value, imagens.value.length > 0)
  if (erroTexto.value) return
  enviando.value = true
  try {
    feedback.value = await feedbackApi.responder(
      feedback.value.id,
      texto.value.trim(),
      imagens.value.map((i) => ({ blob: i.blob, nome: i.nome })),
    )
    texto.value = ''
    imagens.value = []
    avisar.sucesso('Mensagem enviada para a equipe Toqqi.')
  } catch (e) {
    if (e instanceof ApiError && e.campo('texto')) erroTexto.value = e.campo('texto')!
    else avisar.erro(e instanceof ApiError && e.campo('imagens') ? e.campo('imagens')! : mensagemDoErro(e))
  } finally {
    enviando.value = false
  }
}

async function alternarAutorizacao(autoriza: boolean) {
  if (!feedback.value || salvandoAutorizacao.value) return
  salvandoAutorizacao.value = true
  try {
    feedback.value = await feedbackApi.autorizarDepoimento(feedback.value.id, autoriza)
    avisar.sucesso(autoriza ? 'Obrigado! A equipe pode usar seu elogio no site.' : 'Autorização retirada.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    salvandoAutorizacao.value = false
  }
}

const carregarImagem = (imagemId: number, sinal: AbortSignal) => feedbackApi.imagem(fid.value, imagemId, sinal)
</script>

<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-6">
    <RouterLink to="/feedback" class="link inline-flex w-fit items-center gap-1.5 text-sm"><ArrowLeft class="size-4" aria-hidden="true" /> Seus feedbacks</RouterLink>

    <Carregando v-if="carregando && !feedback" :linhas="3" rotulo="Carregando o feedback" />
    <Alerta v-else-if="naoAchou" tom="atencao" titulo="Não encontramos esse feedback" data-nao-achou>
      Ele pode ser de outra pessoa ou o endereço veio incompleto. Veja a lista em <RouterLink to="/feedback" class="link">Seus feedbacks</RouterLink>.
    </Alerta>
    <Alerta v-else-if="erro && !feedback" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-if="feedback">
      <header class="flex flex-col gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="titulo-pagina">{{ infoTipo(feedback.tipo).rotulo }}</h1>
          <Etiqueta :tom="infoSituacao(feedback.situacao).tom" ponto data-situacao>{{ infoSituacao(feedback.situacao).rotulo }}</Etiqueta>
        </div>
        <p class="text-sm text-texto-suave">
          Enviado {{ rotuloQuando(feedback.criado_em) }}<template v-if="feedback.pagina_titulo"> · Tela: {{ feedback.pagina_titulo }}</template><template v-if="rotuloImpacto(feedback.impacto)"> · {{ rotuloImpacto(feedback.impacto) }}</template>
        </p>
      </header>

      <div v-if="feedback.tipo === 'elogio'" class="cartao flex items-start justify-between gap-4 p-4 sm:p-5" data-depoimento>
        <div>
          <p class="font-semibold text-texto">Usar este elogio no site do Toqqi</p>
          <p class="mt-0.5 text-sm text-texto-suave">Com o seu nome e o nome da empresa. A equipe só publica com a sua autorização.</p>
        </div>
        <Interruptor
          :model-value="feedback.autoriza_depoimento"
          rotulo="Autorizo usar este elogio no site do Toqqi"
          rotulo-oculto
          :desabilitado="salvandoAutorizacao"
          @update:model-value="alternarAutorizacao"
        />
      </div>

      <section class="cartao p-4 sm:p-6" aria-label="Conversa com a equipe Toqqi">
        <ConversaFeedback :mensagens="feedback.mensagens" perspectiva="usuario" :carregar-imagem="carregarImagem" />
      </section>

      <form class="cartao flex flex-col gap-4 p-4 sm:p-6" novalidate data-responder @submit.prevent="enviar">
        <p v-if="fechado" class="text-sm text-texto-suave">Este feedback está {{ infoSituacao(feedback.situacao).rotulo.toLowerCase() }}. Se precisar de algo, escreva: a equipe vê sua mensagem.</p>
        <AreaTexto
          v-model="texto"
          rotulo="Sua mensagem"
          placeholder="Mais um detalhe, uma dúvida ou um obrigado."
          :linhas="3"
          :maximo="MAX_TEXTO"
          :erro="erroTexto"
          :disabled="enviando"
          data-texto-resposta
          @input="erroTexto = null"
        />
        <CampoImagens v-model="imagens" :desabilitado="enviando" />
        <div class="flex justify-end">
          <Botao tipo="submit" :carregando="enviando" data-enviar-resposta><Send class="size-4" aria-hidden="true" /> Enviar mensagem</Botao>
        </div>
      </form>
    </template>
  </div>
</template>
