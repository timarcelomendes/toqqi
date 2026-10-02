<script setup lang="ts">
// Assistente (docs/api-etapa-5b.md §6.2): botão no canto inferior direito de todas as telas logadas (some sem IA na
// plataforma e na impressão) e o painel da conversa. Telas largas e altas: 400 px preso ao canto, sem bloquear a página;
// celular (ou tela baixa: celular deitado, zoom de 200%): tela cheia, com o foco preso dentro. Esc fecha; ao abrir, o foco
// vai para a caixa de texto; ao fechar, volta para quem abriu (o botão ou, se ele sumiu, o conteúdo da página). O foco
// nunca cai no <body> enquanto o painel está aberto (senão o Esc e o Tab deixam de funcionar nele).
// Camadas: o botão e o painel preso ao canto ficam em z-[25], acima das barras de salvar (z-10/z-20) e abaixo do
// cabeçalho (z-30, que tem o menu da conta) e dos menus suspensos (z-40); em tela cheia (modal), o painel fica em z-[45].
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { CircleAlert, RotateCcw, SendHorizontal, Sparkles, SquarePen, X } from 'lucide-vue-next'
import { focaveis } from '@/composables/focoPreso'
import { liberarRolagem, travarRolagem } from '@/composables/rolagem'
import { useAssistenteStore } from '@/stores/assistente'
import { useSessaoStore } from '@/stores/sessao'
import { formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Medidor from '@/components/ui/Medidor.vue'
import MensagemAssistente from './MensagemAssistente.vue'
import { useFolgaDasBarras } from './folga'
import { explicacaoIndisponivel, LIMITE_PERGUNTA, MIDIA_PAINEL, textoCota } from './logica'

const assistente = useAssistenteStore()
const sessao = useSessaoStore()
const rota = useRoute()

const botao = ref<HTMLButtonElement | null>(null)
const painel = ref<HTMLElement | null>(null)
const caixa = ref<HTMLTextAreaElement | null>(null)
const lista = ref<HTMLElement | null>(null)
const folga = useFolgaDasBarras()

// Fora de MIDIA_PAINEL (a mesma consulta da variante `painel:` das classes): painel em tela cheia e modal.
const telaCheia = ref(false)
let consulta: MediaQueryList | null = null
const aoMudarTela = () => (telaCheia.value = !!consulta && !consulta.matches)

const cota = computed(() => assistente.cota)
const explicacao = computed(() => explicacaoIndisponivel(assistente.disponivel, assistente.estado?.motivo))
const motivo = computed(() => assistente.estado?.motivo ?? null)
const tamanho = computed(() => assistente.rascunho.length)
const podeEnviar = computed(() => assistente.disponivel && !assistente.enviando && !!assistente.rascunho.trim())
const ultimaId = computed(() => assistente.mensagens.at(-1)?.id)
/** Perguntas de exemplo da API, na conversa vazia. */
const sugestoesIniciais = computed(() => (assistente.disponivel ? (assistente.estado?.sugestoes ?? []) : []))

/** Com uma barra de salvar presa ao rodapé, o botão e o painel (preso ao canto) sobem acima dela. */
const estiloBotao = computed(() => (folga.value ? { bottom: `${folga.value + (telaCheia.value ? 16 : 24)}px` } : undefined))
const estiloPainel = computed(() =>
  folga.value && !telaCheia.value ? { bottom: `${folga.value + 24}px`, height: `min(40rem, calc(100dvh - 6rem - ${folga.value}px))` } : undefined,
)

/** O foco vai para a caixa de texto; com ela desligada, para o próprio painel (tabindex -1). */
function focarCaixa() {
  if (caixa.value && !caixa.value.disabled) caixa.value.focus()
  else painel.value?.focus()
}

/**
 * Desce até o fim da conversa (sempre, ou só se já estava perto dele). Numa resposta longa, para com a última pergunta
 * no alto, para a resposta ser lida do começo.
 */
function rolarParaFim(forcar = false) {
  const el = lista.value
  if (!el) return
  const fim = el.scrollHeight - el.clientHeight
  if (!forcar && fim - el.scrollTop > 96) return
  const perguntas = el.querySelectorAll<HTMLElement>('[data-papel="usuario"]')
  const ultima = perguntas[perguntas.length - 1]
  el.scrollTop = Math.max(0, Math.min(fim, ultima ? ultima.offsetTop - 12 : fim))
}

/** A caixa cresce com o texto até umas 6 linhas (depois rola). */
function ajustarAltura() {
  const el = caixa.value
  if (!el) return
  el.style.height = 'auto'
  // scrollHeight não conta as bordas (a caixa usa border-box): sem somá-las, uma linha só já mostraria a barra de rolagem.
  if (el.scrollHeight) el.style.height = `${Math.min(el.scrollHeight + el.offsetHeight - el.clientHeight, 144)}px`
}

async function enviar() {
  if (!podeEnviar.value) return
  const texto = assistente.rascunho
  assistente.rascunho = ''
  // Pelo botão de enviar (que desliga enquanto a pergunta vai), o foco iria para o <body>: fica na caixa.
  focarCaixa()
  await nextTick()
  ajustarAltura()
  const foi = await assistente.perguntar(texto)
  if (!foi && !assistente.rascunho) assistente.rascunho = texto
}

/** Enter envia; Shift+Enter quebra a linha (e nada acontece no meio de uma composição, como acentos no celular). */
function aoTeclarEnter(e: KeyboardEvent) {
  if (e.shiftKey || e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  enviar()
}

async function usarSugestao(texto: string) {
  focarCaixa()
  await assistente.perguntar(texto)
}

/** "Tentar de novo" some enquanto a pergunta vai de novo (o erro sai da conversa): o foco passa para a caixa. */
async function tentarDeNovo() {
  focarCaixa()
  await assistente.tentarDeNovo()
}

function novaConversa() {
  assistente.novaConversa()
  focarCaixa()
}

let abridor: HTMLElement | null = null
let fechouPorNavegacao = false

function fechar() {
  assistente.fechar()
}

/** Põe o foco em `el`, se ele ainda estiver na página e aceitar o foco. */
function focarSePuder(el: HTMLElement | null | undefined): boolean {
  if (!el?.isConnected) return false
  el.focus()
  return document.activeElement === el
}

watch(
  () => assistente.aberto,
  async (aberto) => {
    if (aberto) {
      const ativo = document.activeElement
      abridor = ativo instanceof HTMLElement && ativo !== document.body ? ativo : null
      await nextTick()
      ajustarAltura()
      focarCaixa()
      rolarParaFim(true)
      return
    }
    await nextTick()
    if (fechouPorNavegacao) {
      fechouPorNavegacao = false
      return
    }
    const quemAbriu = abridor
    abridor = null
    // Quem abriu; senão o botão; se o botão também sumiu (o assistente saiu da plataforma), o conteúdo da página.
    if (!focarSePuder(quemAbriu) && !focarSePuder(botao.value)) document.getElementById('conteudo')?.focus()
  },
)

// Um controle com o foco desligou ou sumiu enquanto a pergunta ia ou voltava: a caixa que desliga com a resposta que
// gastou a última análise (ou com o 409 de cota esgotada e conta pausada), o botão de enviar, "Tentar de novo". O foco
// iria para o <body>: vai para a caixa, se ela estiver ligada, ou para o painel.
watch([() => assistente.disponivel, () => assistente.enviando], async () => {
  const antes = document.activeElement
  if (!assistente.aberto || !painel.value || !(antes instanceof HTMLElement) || antes === painel.value || !painel.value.contains(antes)) return
  await nextTick()
  const agora = document.activeElement
  const perdeu = !antes.isConnected || !agora || agora === document.body || (agora === antes && antes.matches(':disabled'))
  if (perdeu && assistente.aberto) focarCaixa()
})

// Em tela cheia o painel cobre a página: um atalho (ou outro link) abre a tela e fecha o painel.
watch(
  () => rota.fullPath,
  () => {
    if (assistente.aberto && telaCheia.value) {
      fechouPorNavegacao = true
      fechar()
    }
  },
)

// Em tela cheia, a página por baixo não rola enquanto o painel está aberto.
let travada = false
watch(
  () => assistente.aberto && telaCheia.value,
  (travar) => {
    if (travar && !travada) travarRolagem()
    else if (!travar && travada) liberarRolagem()
    travada = travar
  },
  { immediate: true },
)

// Conversa nova, pergunta indo, resposta chegando: mostra o fim da conversa.
watch(
  () => [assistente.mensagens.length, assistente.enviando],
  async () => {
    await nextTick()
    rolarParaFim(true)
  },
)

/** Tab e Shift+Tab ficam dentro do painel em tela cheia (modal); com o painel preso ao canto a página continua acessível. */
function aoTeclarTab(e: KeyboardEvent) {
  if (!telaCheia.value || !painel.value) return
  const itens = focaveis(painel.value)
  if (!itens.length) {
    e.preventDefault()
    painel.value.focus()
    return
  }
  const primeiro = itens[0]!
  const ultimo = itens[itens.length - 1]!
  const atual = document.activeElement
  // Com o foco no próprio painel (a caixa desligada), Shift+Tab sairia dele: vai para o último item.
  const fora = atual === painel.value || !painel.value.contains(atual)
  if (e.shiftKey && (atual === primeiro || fora)) {
    e.preventDefault()
    ultimo.focus()
  } else if (!e.shiftKey && (atual === ultimo || fora)) {
    e.preventDefault()
    primeiro.focus()
  }
}

onMounted(() => {
  if (typeof window.matchMedia === 'function') {
    consulta = window.matchMedia(MIDIA_PAINEL)
    aoMudarTela()
    consulta.addEventListener?.('change', aoMudarTela)
  }
  // Ao entrar: decide se o botão aparece (e, se a busca falhar, tenta de novo mais tarde).
  assistente.acompanharEstado()
})
onBeforeUnmount(() => {
  consulta?.removeEventListener?.('change', aoMudarTela)
  assistente.pararDeAcompanhar()
  if (travada) liberarRolagem()
})
</script>

<template>
  <div class="print:hidden">
    <button
      v-if="assistente.visivel"
      v-show="!assistente.aberto"
      ref="botao"
      type="button"
      aria-label="Assistente"
      aria-haspopup="dialog"
      class="fixed bottom-4 right-4 z-[25] flex size-12 items-center justify-center gap-2 rounded-full bg-marca-forte text-white shadow-lg transition-[bottom,background-color] duration-150 hover:bg-marca-hover motion-reduce:transition-none painel:bottom-6 painel:right-6 sm:w-auto sm:px-5"
      :style="estiloBotao"
      data-botao-assistente
      @click="assistente.abrir()"
    >
      <Sparkles class="size-5 shrink-0" aria-hidden="true" />
      <span class="hidden text-sm font-semibold sm:inline">Assistente</span>
    </button>

    <section
      v-if="assistente.aberto"
      id="painel-assistente"
      ref="painel"
      role="dialog"
      aria-labelledby="t-assistente"
      :aria-modal="telaCheia ? 'true' : undefined"
      tabindex="-1"
      class="fixed inset-0 z-[45] flex flex-col bg-superficie animate-surgir focus:outline-none painel:inset-auto painel:bottom-6 painel:right-6 painel:z-[25] painel:h-[min(40rem,calc(100dvh-6rem))] painel:w-[25rem] painel:overflow-hidden painel:rounded-2xl painel:border painel:border-borda painel:shadow-2xl"
      :style="estiloPainel"
      data-painel-assistente
      @keydown.esc.stop.prevent="fechar"
      @keydown.tab="aoTeclarTab"
    >
      <!-- Cabeçalho: nome, cota do mês e as ações -->
      <header class="shrink-0 border-b border-borda px-4 pb-3 pt-3">
        <div class="flex items-center gap-2">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-marca-suave text-marca-texto" aria-hidden="true">
            <Sparkles class="size-4" />
          </span>
          <h2 id="t-assistente" class="min-w-0 flex-1 truncate text-base font-bold text-texto">Assistente</h2>
          <Botao variante="fantasma" tamanho="sm" :desabilitado="!assistente.mensagens.length || assistente.enviando" data-nova-conversa @click="novaConversa">
            <SquarePen class="size-4" aria-hidden="true" /> Nova conversa
          </Botao>
          <button
            type="button"
            class="-mr-1.5 flex size-9 shrink-0 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto"
            aria-label="Fechar o assistente"
            @click="fechar"
          >
            <X class="size-5" aria-hidden="true" />
          </button>
        </div>
        <div v-if="cota" class="mt-2.5 flex flex-col gap-1.5">
          <p class="text-xs text-texto-suave" data-cota>{{ textoCota(cota) }}</p>
          <Medidor fino :valor="cota.usadas" :maximo="cota.limite" rotulo="Análises de IA usadas neste mês" :texto="textoCota(cota)" />
        </div>
      </header>

      <!-- Conversa -->
      <div ref="lista" class="relative min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4" data-conversa>
        <div v-if="!assistente.mensagens.length" class="flex flex-col gap-4" data-vazio>
          <p class="text-sm leading-relaxed text-texto-suave">
            Pergunte sobre o NPS e o CSAT dos seus clientes (com comparação de períodos de até 12 meses) ou tire dúvidas sobre como usar o Toqqi.
          </p>
          <ul v-if="sugestoesIniciais.length" class="flex flex-col items-start gap-2" aria-label="Sugestões de perguntas" data-sugestoes>
            <li v-for="s in sugestoesIniciais" :key="s" class="max-w-full">
              <button
                type="button"
                class="max-w-full rounded-xl border border-borda-forte bg-superficie px-3 py-2 text-left text-sm text-texto transition-colors hover:border-marca/40 hover:bg-marca-suave disabled:cursor-not-allowed disabled:opacity-55"
                :disabled="assistente.enviando"
                @click="usarSugestao(s)"
              >
                {{ s }}
              </button>
            </li>
          </ul>
        </div>

        <ul v-else class="flex flex-col gap-4" aria-label="Conversa">
          <template v-for="m in assistente.mensagens" :key="m.id">
            <li v-if="m.papel === 'usuario'" class="flex flex-col items-end gap-1.5" data-papel="usuario">
              <p class="max-w-[85%] break-words rounded-2xl rounded-br-md bg-marca-suave px-3.5 py-2.5 text-sm leading-relaxed text-texto">
                <span class="sr-only">Você: </span><span class="whitespace-pre-wrap">{{ m.texto }}</span>
              </p>
              <div v-if="m.erro" class="flex max-w-[85%] flex-col items-end gap-1 text-right text-sm text-erro" data-erro>
                <p class="flex items-start gap-1.5">
                  <CircleAlert class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <span>{{ m.erro.mensagem }}</span>
                </p>
                <button
                  v-if="m.erro.repetir && m.id === ultimaId"
                  type="button"
                  class="link inline-flex items-center gap-1 text-sm"
                  :disabled="assistente.enviando || !assistente.disponivel"
                  @click="tentarDeNovo"
                >
                  <RotateCcw class="size-3.5" aria-hidden="true" /> Tentar de novo
                </button>
              </div>
            </li>
            <MensagemAssistente
              v-else
              :mensagem="m"
              :ultima="m.id === ultimaId"
              :desabilitado="assistente.enviando || !assistente.disponivel"
              @revelada="assistente.marcarRevelada(m.id)"
              @progresso="rolarParaFim()"
              @sugestao="usarSugestao"
            />
          </template>
          <li v-if="assistente.enviando" class="flex items-center gap-2.5 text-sm text-texto-suave" data-consultando>
            <span class="flex gap-1 rounded-2xl rounded-bl-md bg-superficie-2 px-3 py-3" aria-hidden="true">
              <span class="size-1.5 animate-pulse rounded-full bg-texto-fraco" />
              <span class="size-1.5 animate-pulse rounded-full bg-texto-fraco [animation-delay:150ms]" />
              <span class="size-1.5 animate-pulse rounded-full bg-texto-fraco [animation-delay:300ms]" />
            </span>
            Consultando os dados…
          </li>
        </ul>
      </div>

      <!-- Para leitores de tela: a resposta nova (inteira, não aos pedaços), o erro ou "Consultando os dados…" -->
      <p class="sr-only" aria-live="polite" aria-atomic="true" data-anuncio>{{ assistente.anuncio }}</p>

      <!-- Caixa de texto -->
      <form class="shrink-0 border-t border-borda px-4 pb-3 pt-3" data-caixa @submit.prevent="enviar">
        <Alerta v-if="explicacao" tom="atencao" class="mb-3" data-bloqueio>
          {{ explicacao }}
          <template v-if="motivo === 'cota_esgotada' && sessao.pode('configuracoes.gerenciar')">
            <RouterLink to="/configuracoes/ia" class="link mt-1 block">Ver uso em Configurações › IA</RouterLink>
          </template>
          <template v-else-if="motivo === 'conta_pausada' && sessao.pode('assinatura.gerenciar')">
            <RouterLink to="/assinatura" class="link mt-1 block">Ver assinatura</RouterLink>
          </template>
        </Alerta>
        <label for="assistente-pergunta" class="sr-only">Sua pergunta</label>
        <div class="flex items-end gap-2">
          <textarea
            id="assistente-pergunta"
            ref="caixa"
            v-model="assistente.rascunho"
            rows="1"
            :maxlength="LIMITE_PERGUNTA"
            :disabled="!assistente.disponivel"
            enterkeyhint="send"
            aria-describedby="assistente-dica"
            placeholder="Faça uma pergunta"
            class="block max-h-36 min-h-11 w-full resize-none rounded-xl border border-borda-forte bg-superficie px-3.5 py-2.5 text-[0.95rem] leading-6 text-texto placeholder:text-texto-fraco/80 transition-colors hover:border-texto-fraco/60 focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20 disabled:cursor-not-allowed disabled:bg-superficie-2"
            @input="ajustarAltura"
            @keydown.enter="aoTeclarEnter"
          />
          <Botao tipo="submit" somente-icone="Enviar pergunta" class="shrink-0" :desabilitado="!podeEnviar">
            <SendHorizontal class="size-5" aria-hidden="true" />
          </Botao>
        </div>
        <p id="assistente-dica" class="mt-1.5 flex items-center justify-between gap-3 text-xs text-texto-fraco">
          <span class="hidden sm:inline">Enter envia; Shift+Enter quebra a linha.</span>
          <span class="ml-auto tabular-nums" :class="tamanho >= LIMITE_PERGUNTA ? 'font-semibold text-erro' : tamanho >= 900 ? 'text-atencao' : ''" data-contador>
            {{ formatarNumero(tamanho) }}/{{ formatarNumero(LIMITE_PERGUNTA) }}<span class="sr-only"> caracteres</span>
          </span>
        </p>
        <p class="mt-2 text-xs leading-snug text-texto-fraco">Respostas geradas por IA com os dados da sua conta. Confira os números nos relatórios.</p>
      </form>
    </section>
  </div>
</template>
