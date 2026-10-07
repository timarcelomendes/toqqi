<script setup lang="ts">
// Seus feedbacks (/feedback): o que a pessoa já mandou para a equipe Toqqi, a atividade mais recente primeiro, com a
// situação e "Resposta nova" quando a equipe respondeu ou mudou a situação depois da última vez que ela abriu.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronRight, MessageSquareHeart, MessagesSquare, Paperclip } from 'lucide-vue-next'
import { feedbackApi, mensagemDoErro, type FeedbackDoUsuario } from '@/api'
import { usarFeedback } from '@/composables/feedback'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { infoSituacao, infoTipo, rotuloQuando } from './logica'

const { abrir, definirNovidades, janela } = usarFeedback()
const itens = ref<FeedbackDoUsuario[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
let controlador: AbortController | null = null

async function carregar() {
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await feedbackApi.listar(controlador.signal)
    itens.value = r.itens
    definirNovidades(r.novidades)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

// Enviou um feedback novo por esta tela: a lista se atualiza quando a janela fecha.
watch(
  () => janela.aberta,
  (aberta, antes) => {
    if (antes && !aberta) void carregar()
  },
)
onMounted(carregar)
onBeforeUnmount(() => controlador?.abort())
</script>

<template>
  <CabecalhoPagina titulo="Seus feedbacks" descricao="O que você mandou para a equipe Toqqi: erros, ideias, melhorias e elogios, com as respostas.">
    <template #acoes>
      <Botao data-novo-feedback @click="abrir()"><MessageSquareHeart class="size-4" aria-hidden="true" /> Enviar feedback</Botao>
    </template>
  </CabecalhoPagina>

  <div class="cartao">
    <div v-if="carregando && !itens.length" class="p-5"><Carregando :linhas="3" rotulo="Carregando seus feedbacks" /></div>
    <Alerta v-else-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <EstadoVazio
      v-else-if="!itens.length"
      :icone="MessageSquareHeart"
      titulo="Você ainda não mandou nenhum feedback"
      descricao="Achou um erro, teve uma ideia ou gostou de algo? Conte para a equipe Toqqi: a gente lê tudo e responde por aqui."
      data-vazio-feedbacks
    >
      <Botao @click="abrir()">Enviar feedback</Botao>
    </EstadoVazio>
    <ul v-else class="divide-y divide-borda" aria-label="Seus feedbacks" :aria-busy="carregando">
      <li v-for="f in itens" :key="f.id" :data-feedback="f.id">
        <RouterLink
          :to="`/feedback/${f.id}`"
          class="flex items-center gap-4 px-4 py-4 transition-colors hover:bg-superficie-2 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-foco sm:px-5"
        >
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <Etiqueta :tom="infoTipo(f.tipo).tom">{{ infoTipo(f.tipo).rotulo }}</Etiqueta>
              <Etiqueta :tom="infoSituacao(f.situacao).tom" ponto data-situacao>{{ infoSituacao(f.situacao).rotulo }}</Etiqueta>
              <span v-if="f.novidade" class="rounded-full bg-marca-forte px-2 py-0.5 text-xs font-bold text-white" data-novidade>Resposta nova</span>
            </div>
            <p class="mt-1.5 truncate font-semibold text-texto" data-trecho>{{ f.trecho }}</p>
            <p class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-texto-fraco">
              <span>Atualizado {{ rotuloQuando(f.atualizado_em) }}</span>
              <span v-if="f.pagina_titulo">Tela: {{ f.pagina_titulo }}</span>
              <span class="inline-flex items-center gap-1"><MessagesSquare class="size-3.5" aria-hidden="true" />{{ f.mensagens === 1 ? '1 mensagem' : `${f.mensagens} mensagens` }}</span>
              <span v-if="f.imagens" class="inline-flex items-center gap-1"><Paperclip class="size-3.5" aria-hidden="true" />{{ f.imagens === 1 ? '1 imagem' : `${f.imagens} imagens` }}</span>
            </p>
          </div>
          <ChevronRight class="size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
