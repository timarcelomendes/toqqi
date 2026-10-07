<script setup lang="ts">
// Plataforma › Feedback (docs/api-feedback.md §4): os feedbacks de todas as contas, a atividade mais recente primeiro.
// Filtros de tipo e situação (abertos = recebido, em análise ou planejado) e busca (conta, nome ou e-mail de quem mandou,
// ou o texto). O ponto coral marca o que precisa de atenção (novo ou com mensagem que a equipe ainda não viu).
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { MessageSquareHeart, MessagesSquare, Paperclip, RefreshCw } from 'lucide-vue-next'
import { mensagemDoErro, plataformaFeedbackApi, type FeedbackPlataformaResumo, type FiltroSituacaoFeedback, type TipoFeedback } from '@/api'
import { usarFeedback } from '@/composables/feedback'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Selecao from '@/components/ui/Selecao.vue'
import { ORDEM_TIPOS, TIPOS_FEEDBACK, infoSituacao, infoTipo, rotuloQuando, textoAtencao } from '@/modulos/feedback/logica'

const SITUACOES: { valor: FiltroSituacaoFeedback; rotulo: string }[] = [
  { valor: 'abertos', rotulo: 'Abertos' },
  { valor: 'concluidos', rotulo: 'Concluídos' },
  { valor: 'encerrados', rotulo: 'Encerrados' },
  { valor: 'todos', rotulo: 'Todos' },
]
const TIPOS = ORDEM_TIPOS.map((t) => ({ valor: t, rotulo: TIPOS_FEEDBACK[t].rotulo }))

const { definirAtencao } = usarFeedback()
const filtros = reactive<{ tipo: TipoFeedback | ''; situacao: FiltroSituacaoFeedback; busca: string }>({ tipo: '', situacao: 'abertos', busca: '' })
const itens = ref<FeedbackPlataformaResumo[]>([])
const contagem = ref({ atencao: 0, abertos: 0 })
const carregando = ref(true)
const carregou = ref(false)
const erro = ref<string | null>(null)
let controlador: AbortController | null = null
let espera: ReturnType<typeof setTimeout> | undefined

const temFiltro = computed(() => !!filtros.tipo || filtros.situacao !== 'abertos' || !!filtros.busca.trim())

async function carregar() {
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await plataformaFeedbackApi.listar({ tipo: filtros.tipo, situacao: filtros.situacao, busca: filtros.busca.trim() }, controlador.signal)
    itens.value = r.itens
    contagem.value = r.contagem
    definirAtencao(r.contagem.atencao)
    carregou.value = true
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

watch(() => [filtros.tipo, filtros.situacao], () => void carregar())
watch(
  () => filtros.busca,
  () => {
    clearTimeout(espera)
    espera = setTimeout(() => void carregar(), 350)
  },
)

function limparFiltros() {
  Object.assign(filtros, { tipo: '', situacao: 'abertos', busca: '' })
}

onMounted(carregar)
onBeforeUnmount(() => {
  controlador?.abort()
  clearTimeout(espera)
})
</script>

<template>
  <!-- Uma raiz só: a Plataforma esconde a aba com v-show -->
  <div class="flex flex-col gap-4" data-aba-feedback>
    <div class="cartao grid gap-3 p-4 sm:grid-cols-3 sm:p-5">
      <Selecao v-model="filtros.tipo" rotulo="Tipo" :opcoes="TIPOS" vazio="Todos" />
      <Selecao v-model="filtros.situacao" rotulo="Situação" :opcoes="SITUACOES" />
      <Campo v-model="filtros.busca" rotulo="Buscar" tipo="search" placeholder="Conta, pessoa, e-mail ou texto" data-busca-feedback />
    </div>

    <div class="cartao">
      <div class="flex min-h-12 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-borda px-4 py-3 text-sm sm:px-5">
        <p class="text-texto-suave" aria-live="polite" data-total-feedback>
          <template v-if="carregando && !carregou">Carregando…</template>
          <template v-else-if="!erro">
            {{ itens.length === 1 ? '1 feedback' : `${itens.length} feedbacks` }}
            <template v-if="contagem.atencao"> · <span class="font-semibold text-marca-texto">{{ textoAtencao(contagem.atencao) }}</span></template>
          </template>
        </p>
        <div class="flex flex-wrap gap-2">
          <Botao v-if="temFiltro" variante="fantasma" tamanho="sm" @click="limparFiltros">Limpar filtros</Botao>
          <Botao variante="secundario" tamanho="sm" :carregando="carregando && carregou" @click="carregar">
            <RefreshCw class="size-4" aria-hidden="true" /> Atualizar
          </Botao>
        </div>
      </div>

      <div v-if="carregando && !carregou" class="p-5"><Carregando :linhas="4" rotulo="Carregando os feedbacks" /></div>
      <Alerta v-else-if="erro" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <EstadoVazio
        v-else-if="!itens.length"
        :icone="MessageSquareHeart"
        :titulo="temFiltro ? 'Nenhum feedback com esses filtros' : 'Nenhum feedback aberto'"
        :descricao="temFiltro ? 'Mude os filtros ou limpe a busca.' : 'Os erros, ideias, melhorias e elogios de quem usa o Toqqi aparecem aqui.'"
        data-vazio-feedback
      />
      <ul v-else class="divide-y divide-borda" :class="{ 'opacity-60 transition-opacity': carregando }" :aria-busy="carregando" aria-label="Feedbacks">
        <li v-for="f in itens" :key="f.id" :data-feedback="f.id">
          <RouterLink
            :to="`/plataforma/feedback/${f.id}`"
            class="flex gap-3 px-4 py-4 transition-colors hover:bg-superficie-2 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-foco sm:px-5"
          >
            <span class="mt-2 size-2.5 shrink-0 rounded-full" :class="f.atencao ? 'bg-marca-forte' : 'bg-transparent'" aria-hidden="true" />
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span v-if="f.atencao" class="sr-only">Precisa de atenção.</span>
                <Etiqueta :tom="infoTipo(f.tipo).tom">{{ infoTipo(f.tipo).rotulo }}</Etiqueta>
                <Etiqueta :tom="infoSituacao(f.situacao).tom" ponto>{{ infoSituacao(f.situacao).rotulo }}</Etiqueta>
                <Etiqueta v-if="f.impacto === 'bloqueia'" tom="erro" data-bloqueia>Impede o trabalho</Etiqueta>
                <Etiqueta v-if="f.autoriza_depoimento" tom="sucesso">Pode usar no site</Etiqueta>
                <span class="text-xs text-texto-fraco">#{{ f.id }}</span>
              </div>
              <p class="mt-1.5 truncate text-texto" :class="f.atencao ? 'font-bold' : 'font-semibold'" data-trecho>{{ f.trecho }}</p>
              <p class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-texto-fraco">
                <span class="font-semibold text-texto-suave">{{ f.conta_nome }}</span>
                <span>{{ f.autor_nome ?? 'Saiu da conta' }}<template v-if="f.autor_email"> · {{ f.autor_email }}</template></span>
                <span>{{ rotuloQuando(f.atualizado_em) }}</span>
                <span class="inline-flex items-center gap-1"><MessagesSquare class="size-3.5" aria-hidden="true" />{{ f.mensagens }}</span>
                <span v-if="f.imagens" class="inline-flex items-center gap-1"><Paperclip class="size-3.5" aria-hidden="true" />{{ f.imagens }}</span>
              </p>
            </div>
          </RouterLink>
        </li>
      </ul>
    </div>

    <p class="text-sm text-texto-fraco">
      Cada feedback novo e cada mensagem nova chegam por e-mail aos superadmins. A resposta escrita aqui chega à pessoa no Toqqi e por e-mail;
      mudar só a situação aparece para ela na conversa, sem e-mail. As imagens dos feedbacks concluídos ou encerrados há mais de 180 dias são apagadas.
    </p>
  </div>
</template>
