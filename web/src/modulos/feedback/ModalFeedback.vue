<script setup lang="ts">
// Janela "Enviar feedback" (docs/api-feedback.md §6): 1) o tipo (algo deu errado, ideia, melhoria, elogio), 2) o texto,
// com o impacto (erro), até 3 imagens (colar, arrastar, escolher), os detalhes técnicos (erro: navegador, tela, versão e
// os últimos erros desta página, com "Ver o que vai junto") e a autorização do depoimento (elogio), 3) enviado, com o
// link para a conversa. Abre por cima da tela em que a pessoa está e leva o caminho e o título dela.
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Bug, CircleCheckBig, Heart, Lightbulb, MessagesSquare, Wrench } from 'lucide-vue-next'
import { feedbackApi, mensagemDoErro, type ImpactoFeedback, type TipoFeedback } from '@/api'
import { ApiError } from '@/api/erros'
import { usarFeedback } from '@/composables/feedback'
import { diagnosticoAtual, diagnosticoParaEnvio, tamanhoDaJanela } from '@/utils/diagnostico'
import { VERSAO_SITE } from '@/utils/erros'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Modal from '@/components/ui/Modal.vue'
import Alerta from '@/components/ui/Alerta.vue'
import CampoImagens, { type ImagemEscolhida } from './CampoImagens.vue'
import { IMPACTOS, MAX_TEXTO, ORDEM_TIPOS, TIPOS_FEEDBACK, erroDoTexto, telaDeOrigem, textoNovidades } from './logica'

const ICONES = { erro: Bug, sugestao: Lightbulb, melhoria: Wrench, elogio: Heart } as const
const CORES_ICONE: Record<TipoFeedback, string> = {
  erro: 'bg-erro-suave text-erro',
  sugestao: 'bg-info-suave text-info',
  melhoria: 'bg-atencao-suave text-atencao',
  elogio: 'bg-sucesso-suave text-sucesso',
}

const { janela, novidades } = usarFeedback()
const rota = useRoute()
const router = useRouter()

type Passo = 'tipo' | 'texto' | 'enviado'
const passo = ref<Passo>('tipo')
const tipo = ref<TipoFeedback>('erro')
const texto = ref('')
const impacto = ref<ImpactoFeedback | ''>('')
const imagens = ref<ImagemEscolhida[]>([])
const detalhes = ref(true)
const autoriza = ref(false)
const erro = ref<string | null>(null)
const erroTexto = ref<string | null>(null)
const enviando = ref(false)
const enviadoId = ref<number | null>(null)
const origem = ref<{ pagina: string; titulo: string | null } | null>(null)
const area = ref<InstanceType<typeof AreaTexto> | null>(null)

const info = computed(() => TIPOS_FEEDBACK[tipo.value])
const titulo = computed(() =>
  passo.value === 'tipo' ? 'Enviar feedback' : passo.value === 'texto' ? info.value.titulo : 'Feedback enviado',
)
const descricao = computed(() =>
  passo.value === 'tipo'
    ? 'Conte para a equipe Toqqi o que deu errado, uma ideia, uma melhoria ou o que você gostou.'
    : passo.value === 'texto'
      ? 'A equipe Toqqi lê tudo e responde por aqui e por e-mail.'
      : undefined,
)
const resumoTecnico = computed(() => {
  const d = diagnosticoAtual()
  const navegador = typeof navigator !== 'undefined' ? navigator.userAgent : ''
  return [
    { rotulo: 'Navegador', valor: navegador.length > 90 ? `${navegador.slice(0, 89)}…` : navegador || '—' },
    { rotulo: 'Tamanho da tela', valor: tamanhoDaJanela() ?? '—' },
    { rotulo: 'Versão do Toqqi', valor: VERSAO_SITE },
    { rotulo: 'Erros recentes nesta página', valor: String(d.erros.length) },
    { rotulo: 'Pedidos que falharam', valor: String(d.pedidos.length) },
  ]
})

function origemAgora() {
  const anterior = typeof window !== 'undefined' ? (window.history.state as { back?: unknown } | null)?.back : null
  let deAntes: { path: string; titulo: string | null } | null = null
  if (typeof anterior === 'string') {
    try {
      const r = router.resolve(anterior)
      deAntes = { path: r.path, titulo: typeof r.meta.titulo === 'string' ? r.meta.titulo : null }
    } catch {
      deAntes = null
    }
  }
  return telaDeOrigem({ path: rota.path, titulo: typeof rota.meta.titulo === 'string' ? rota.meta.titulo : null }, deAntes)
}

function reiniciar() {
  tipo.value = janela.tipo ?? 'erro'
  passo.value = janela.tipo ? 'texto' : 'tipo'
  texto.value = ''
  impacto.value = ''
  imagens.value = []
  detalhes.value = true
  autoriza.value = false
  erro.value = null
  erroTexto.value = null
  enviadoId.value = null
  origem.value = origemAgora()
}

watch(
  () => janela.aberta,
  (aberta) => {
    if (aberta) {
      reiniciar()
      if (passo.value === 'texto') void focarTexto()
    } else {
      imagens.value = [] // as miniaturas liberam as URLs
    }
  },
)
// Mudou de página (ex.: "Seus feedbacks"): a janela fecha.
watch(() => rota.fullPath, () => {
  if (janela.aberta && !enviando.value) janela.aberta = false
})

async function focarTexto() {
  await nextTick()
  area.value?.elemento?.focus()
}

function escolher(t: TipoFeedback) {
  tipo.value = t
  passo.value = 'texto'
  erro.value = null
  void focarTexto()
}

async function enviar() {
  if (enviando.value) return
  erroTexto.value = erroDoTexto(texto.value)
  if (erroTexto.value) {
    void focarTexto()
    return
  }
  erro.value = null
  enviando.value = true
  const comDetalhes = tipo.value === 'erro' && detalhes.value
  try {
    const f = await feedbackApi.criar({
      tipo: tipo.value,
      texto: texto.value.trim(),
      impacto: tipo.value === 'erro' && impacto.value ? impacto.value : null,
      autoriza_depoimento: tipo.value === 'elogio' && autoriza.value,
      detalhes: comDetalhes,
      pagina: origem.value?.pagina ?? null,
      pagina_titulo: origem.value?.titulo ?? null,
      tela: comDetalhes ? tamanhoDaJanela() : null,
      versao_site: comDetalhes ? VERSAO_SITE : null,
      diagnostico: comDetalhes ? diagnosticoParaEnvio() : null,
      imagens: imagens.value.map((i) => ({ blob: i.blob, nome: i.nome })),
    })
    enviadoId.value = f.id
    passo.value = 'enviado'
    imagens.value = []
  } catch (e) {
    if (e instanceof ApiError && e.campo('texto')) erroTexto.value = e.campo('texto')!
    erro.value = e instanceof ApiError && e.campo('imagens') ? e.campo('imagens')! : mensagemDoErro(e)
  } finally {
    enviando.value = false
  }
}

function fechar() {
  janela.aberta = false
}
</script>

<template>
  <Modal v-model:aberto="janela.aberta" :titulo="titulo" :descricao="descricao" tamanho="lg" :bloqueado="enviando">
    <!-- 1) o tipo -->
    <div v-if="passo === 'tipo'" class="flex flex-col gap-4" data-passo-feedback="tipo">
      <ul class="grid gap-3 sm:grid-cols-2">
        <li v-for="t in ORDEM_TIPOS" :key="t">
          <button
            type="button"
            class="flex h-full w-full items-start gap-3 rounded-2xl border border-borda bg-superficie p-4 text-left transition-colors hover:border-marca hover:bg-marca-suave/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
            :data-tipo-feedback="t"
            @click="escolher(t)"
          >
            <span class="flex size-10 shrink-0 items-center justify-center rounded-xl" :class="CORES_ICONE[t]" aria-hidden="true">
              <component :is="ICONES[t]" class="size-5" />
            </span>
            <span class="min-w-0">
              <span class="block font-bold text-texto">{{ TIPOS_FEEDBACK[t].titulo }}</span>
              <span class="mt-0.5 block text-sm text-texto-suave">{{ TIPOS_FEEDBACK[t].descricao }}</span>
            </span>
          </button>
        </li>
      </ul>
      <RouterLink to="/feedback" class="link inline-flex w-fit items-center gap-1.5 text-sm" data-seus-feedbacks>
        <MessagesSquare class="size-4" aria-hidden="true" /> Seus feedbacks
        <span v-if="novidades > 0" class="rounded-full bg-marca-forte px-1.5 text-xs font-bold text-white">{{ novidades }}</span>
        <span v-if="novidades > 0" class="sr-only">, {{ textoNovidades(novidades) }}</span>
      </RouterLink>
    </div>

    <!-- 2) o texto -->
    <form v-else-if="passo === 'texto'" id="form-feedback" class="flex flex-col gap-5" novalidate data-passo-feedback="texto" @submit.prevent="enviar">
      <div class="flex flex-wrap items-center gap-2 text-sm">
        <span class="inline-flex items-center gap-2 rounded-full px-2.5 py-1 font-semibold" :class="CORES_ICONE[tipo]">
          <component :is="ICONES[tipo]" class="size-4" aria-hidden="true" /> {{ info.rotulo }}
        </span>
        <button type="button" class="link text-sm" :disabled="enviando" data-trocar-tipo @click="passo = 'tipo'">Trocar o tipo</button>
        <span v-if="origem?.titulo" class="text-texto-fraco" data-tela-origem>· Tela: {{ origem.titulo }}</span>
      </div>

      <fieldset v-if="tipo === 'erro'" class="flex flex-col gap-2">
        <legend class="mb-2 text-sm font-semibold text-texto">Isso impede seu trabalho? <span class="font-normal text-texto-fraco">(opcional)</span></legend>
        <BotoesSegmentados v-model="impacto" :opcoes="IMPACTOS" rotulo="Impacto do erro" bloco :desabilitado="enviando" />
      </fieldset>

      <AreaTexto
        ref="area"
        v-model="texto"
        :rotulo="info.pergunta"
        :placeholder="info.exemplo"
        :linhas="5"
        :maximo="MAX_TEXTO"
        :erro="erroTexto"
        :disabled="enviando"
        contador
        data-texto-feedback
        @input="erroTexto = null"
      />

      <CampoImagens v-model="imagens" :desabilitado="enviando" />

      <div v-if="tipo === 'erro'" class="flex flex-col gap-2 rounded-xl bg-superficie-2 p-3.5">
        <CaixaSelecao
          v-model="detalhes"
          rotulo="Enviar detalhes técnicos"
          descricao="O navegador, o tamanho da tela, a versão do Toqqi e os últimos erros desta página. Ajuda a equipe a achar o problema mais rápido."
          :desabilitado="enviando"
          data-detalhes-tecnicos
        />
        <details v-if="detalhes" class="pl-8 text-sm">
          <summary class="w-fit cursor-pointer rounded-sm font-semibold text-marca-texto">Ver o que vai junto</summary>
          <dl class="mt-2 grid gap-1 text-xs text-texto-suave sm:grid-cols-[auto_1fr] sm:gap-x-3">
            <template v-for="l in resumoTecnico" :key="l.rotulo">
              <dt class="font-semibold text-texto">{{ l.rotulo }}</dt>
              <dd class="[overflow-wrap:anywhere]">{{ l.valor }}</dd>
            </template>
          </dl>
        </details>
      </div>

      <CaixaSelecao
        v-if="tipo === 'elogio'"
        v-model="autoriza"
        rotulo="Pode usar este elogio no site do Toqqi"
        descricao="Com o seu nome e o nome da empresa. Você pode retirar a autorização quando quiser, em Seus feedbacks."
        :desabilitado="enviando"
        data-autoriza-depoimento
      />

      <Alerta v-if="erro" tom="erro" data-erro-feedback>{{ erro }}</Alerta>
    </form>

    <!-- 3) enviado -->
    <div v-else class="flex flex-col items-center gap-3 py-4 text-center" data-passo-feedback="enviado" role="status">
      <span class="flex size-14 items-center justify-center rounded-full bg-sucesso-suave text-sucesso" aria-hidden="true">
        <CircleCheckBig class="size-8" />
      </span>
      <p class="text-lg font-bold text-texto">Recebemos seu feedback!</p>
      <p class="max-w-md text-sm text-texto-suave">{{ info.enviado }}</p>
    </div>

    <!-- No passo do tipo não há rodapé (a escolha é o próprio cartão). -->
    <template v-if="passo !== 'tipo'" #rodape>
      <template v-if="passo === 'texto'">
        <Botao variante="fantasma" :desabilitado="enviando" data-voltar-feedback @click="janela.tipo ? fechar() : (passo = 'tipo')">
          <ArrowLeft v-if="!janela.tipo" class="size-4" aria-hidden="true" /> {{ janela.tipo ? 'Cancelar' : 'Voltar' }}
        </Botao>
        <Botao tipo="submit" form="form-feedback" :carregando="enviando" data-enviar-feedback>Enviar</Botao>
      </template>
      <template v-else-if="passo === 'enviado'">
        <Botao variante="secundario" :para="enviadoId ? `/feedback/${enviadoId}` : '/feedback'" data-ver-conversa>Ver a conversa</Botao>
        <Botao data-fechar-feedback @click="fechar">Fechar</Botao>
      </template>
    </template>
  </Modal>
</template>
