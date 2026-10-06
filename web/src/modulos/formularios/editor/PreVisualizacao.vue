<script setup lang="ts">
// Pré-visualização do editor: a página da pesquisa (como hoje) e, para quem vê os envios, o convite por e-mail e a
// mensagem do WhatsApp com os textos de Configurações › Envios, o logo e os botões de nota deste formulário.
// Etapa 5c: com as indicações ligadas, terminar a página com nota de promotor mostra o cartão de indicação de exemplo
// (com o envio desligado), com os textos de Configurações › Crescimento.
// Etapa 5e: o e-mail sai com o visual de Configurações › Envios (cor, logo, imagem de topo, assinatura e rodapé); sem cor
// própria da conta, vale a cor deste formulário, a que está na tela (mesmo antes de salvar).
// Etapa 5l: mostra o documento de trabalho (rascunho), segue o item selecionado (`focoId`; fora do caminho, com a faixa
// do motivo), mostra o final escolhido pela lógica, "Reiniciar" e o seletor Celular/Computador.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { ImageIcon, Monitor, RotateCcw, Smartphone } from 'lucide-vue-next'
import { crescimentoApi, enviosApi, mensagemDoErro, type ConfigCrescimento, type ConfigEnvios } from '@/api'
import type { ConviteIndicacao, Final, Pergunta, Tema, TipoFormulario } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import { logoParaCliente } from '@/utils/imagens'
import Pesquisa from '@/pesquisa/Pesquisa.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import PreviaEmail from '@/modulos/configuracoes/PreviaEmail.vue'
import PreviaWhatsapp from '@/modulos/configuracoes/PreviaWhatsapp.vue'
import { previaConvite } from '@/modulos/configuracoes/configCrescimento'
import { montarPreviaEmail, renderizarMensagem } from '@/modulos/configuracoes/mensagens'
import { perguntaPrincipal } from '@/pesquisa/logica'

// `titulo`: o rótulo "Pré-visualização" no topo (a janela do celular já tem o próprio título).
const props = withDefaults(
  defineProps<{
    nome: string
    perguntas: Pergunta[]
    tema: Tema
    nomeEmpresa: string
    tipo?: TipoFormulario
    titulo?: boolean
    /** Etapa 5l: os finais por condição (o final da prévia sai da lógica). */
    finais?: Final[]
    /** Etapa 5l: o item (ou final) selecionado no editor. */
    focoId?: string | null
    /** Etapa 5l: quando o item em foco aparece, em frase. */
    motivoFoco?: string | null
    prefixoImagens?: string | null
  }>(),
  { tipo: 'nps', titulo: true, finais: () => [], focoId: null, motivoFoco: null, prefixoImagens: null },
)
const sessao = useSessaoStore()
const pesquisa = ref<{ recomecar: () => void } | null>(null)
// Sem logo no formulário, o cliente vê o logo da empresa (a API faz o mesmo na página pública e nos e-mails).
const logo = computed(() => logoParaCliente(props.tema.logo_url, sessao.conta?.logo_url))
const temaPrevia = computed<Tema>(() => ({ ...props.tema, logo_url: logo.value.url }))

type Canal = 'pagina' | 'email' | 'whatsapp'
const CANAIS: { valor: Canal; rotulo: string }[] = [
  { valor: 'pagina', rotulo: 'Página' },
  { valor: 'email', rotulo: 'E-mail' },
  { valor: 'whatsapp', rotulo: 'WhatsApp' },
]
const canal = ref<Canal>('pagina')
// Os textos dos convites vêm de Configurações › Envios (GET /envios/configuracao pede envios.ver).
const veMensagens = computed(() => sessao.pode('envios.ver'))
const podeEditarMensagens = computed(() => sessao.pode('configuracoes.gerenciar'))

// ── Celular / Computador ──
type Aparelho = 'celular' | 'computador'
const aparelho = ref<Aparelho>('celular')
const LARGURA_COMPUTADOR = 1024
const caixa = ref<HTMLElement | null>(null)
const medidas = ref({ largura: 400, altura: 600 })
let observador: ResizeObserver | null = null
onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  observador = new ResizeObserver(([e]) => {
    if (e) medidas.value = { largura: e.contentRect.width, altura: e.contentRect.height }
  })
  if (caixa.value) observador.observe(caixa.value)
})
watch(caixa, (el, antes) => {
  if (antes) observador?.unobserve(antes)
  if (el) observador?.observe(el)
})
onBeforeUnmount(() => observador?.disconnect())
/** "Computador": a página com 1024 px, reduzida para caber numa janela de navegador (margem de 12 px e barra de 24). */
const areaComputador = computed(() => ({
  largura: Math.max(120, medidas.value.largura - 24 - 2),
  altura: Math.max(120, medidas.value.altura - 24 - 24 - 2),
}))
const escala = computed(() => Math.min(1, areaComputador.value.largura / LARGURA_COMPUTADOR))
const estiloComputador = computed(() => ({
  width: `${LARGURA_COMPUTADOR}px`,
  height: `${areaComputador.value.altura / escala.value}px`,
  transform: `scale(${escala.value})`,
  transformOrigin: 'top left',
}))

const config = ref<ConfigEnvios | null>(null)
const carregando = ref(false)
const erro = ref<string | null>(null)

async function carregarMensagens() {
  if (config.value || carregando.value) return
  carregando.value = true
  erro.value = null
  try {
    config.value = await enviosApi.configuracao()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function escolher(c: Canal) {
  canal.value = c
  if (c !== 'pagina') void carregarMensagens()
}

const exemplo = computed(() => ({
  nome: 'Maria Souza',
  empresa: props.nomeEmpresa || sessao.conta?.nome || 'Sua empresa',
  empresa_cliente: 'Mercado Bom Preço',
  link: `${window.location.origin}/r/exemplo`,
}))
const previaEmail = computed(() =>
  config.value
    ? montarPreviaEmail(config.value, 'convite', props.tipo, exemplo.value, logo.value.url || null, { temaCor: props.tema.cor, pergunta: perguntaPrincipal(props.perguntas) })
    : null,
)
// "Usando o logo da empresa" só quando o canal mostra o logo (no e-mail, "Mostrar o logo" pode estar desligado).
const avisoLogoEmpresa = computed(
  () => logo.value.daEmpresa && (canal.value === 'pagina' || (canal.value === 'email' && config.value?.email_mostrar_logo !== false)),
)
const textoWhatsapp = computed(() => (config.value ? renderizarMensagem(config.value.texto_whatsapp, exemplo.value) : ''))

// Etapa 5c: o convite de indicação de exemplo (GET /crescimento/configuracao pede crescimento.ver ou configuracoes.gerenciar),
// buscado só quando a pré-visualização termina com nota de promotor, e uma vez só.
const veCrescimento = computed(() => sessao.pode('crescimento.ver') || sessao.pode('configuracoes.gerenciar'))
let configCrescimento: Promise<ConfigCrescimento | null> | null = null
async function indicacaoExemplo(): Promise<ConviteIndicacao | null> {
  if (!veCrescimento.value) return null
  configCrescimento ??= crescimentoApi.configuracao().catch(() => {
    configCrescimento = null
    return null
  })
  const c = await configCrescimento
  return c?.indicacoes_ativas ? previaConvite(c, { empresa: exemplo.value.empresa, nome: 'Maria Souza' }) : null
}

const formularioPrevia = computed(() => ({ nome: props.nome, perguntas: props.perguntas, tema: temaPrevia.value, prefixo_imagens: props.prefixoImagens }))
const variaveis = { empresa: '', nome: 'Maria Souza', assunto: '', referencia: 'Pedido 12345' }
const variaveisPrevia = computed(() => ({ ...variaveis, empresa: props.nomeEmpresa }))
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden rounded-cartao border border-borda bg-slate-100 dark:bg-slate-900/60" data-previa>
    <div class="flex flex-col gap-2 border-b border-borda bg-superficie px-3 py-2">
      <div class="flex items-center justify-between gap-2">
        <p v-if="titulo" class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">Pré-visualização</p>
        <div v-if="canal === 'pagina'" class="ml-auto flex items-center gap-1">
          <div class="flex rounded-lg border border-borda-forte p-0.5" role="radiogroup" aria-label="Tamanho da tela" data-aparelho>
            <button
              v-for="a in [{ v: 'celular', t: 'Celular', i: Smartphone }, { v: 'computador', t: 'Computador', i: Monitor }] as const"
              :key="a.v"
              type="button"
              role="radio"
              :aria-checked="aparelho === a.v"
              :title="a.t"
              class="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs font-semibold transition-colors"
              :class="aparelho === a.v ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto'"
              :data-aparelho-opcao="a.v"
              @click="aparelho = a.v"
            >
              <component :is="a.i" class="size-3.5" aria-hidden="true" /> <span class="hidden 2xl:inline">{{ a.t }}</span><span class="sr-only 2xl:hidden">{{ a.t }}</span>
            </button>
          </div>
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-texto-suave hover:bg-superficie-2"
            aria-label="Reiniciar prévia"
            title="Reiniciar prévia"
            data-reiniciar
            @click="pesquisa?.recomecar()"
          >
            <RotateCcw class="size-3.5" aria-hidden="true" /> Reiniciar
          </button>
        </div>
      </div>
      <div v-if="veMensagens" class="flex rounded-xl border border-borda-forte p-0.5" role="radiogroup" aria-label="Como o cliente recebe" data-canais-previa>
        <button
          v-for="o in CANAIS"
          :key="o.valor"
          type="button"
          role="radio"
          :aria-checked="canal === o.valor"
          :data-canal="o.valor"
          class="h-8 flex-1 rounded-[0.6rem] px-2 text-xs font-semibold transition-colors"
          :class="canal === o.valor ? 'bg-marca-suave text-marca-texto' : 'text-texto-fraco hover:text-texto'"
          @click="escolher(o.valor)"
        >
          {{ o.rotulo }}
        </button>
      </div>
    </div>

    <div v-if="canal === 'pagina'" ref="caixa" class="relative flex-1 overflow-hidden" :data-aparelho-atual="aparelho">
      <!-- Celular: a página em 390 px, numa moldura -->
      <div v-if="aparelho === 'celular'" class="h-full overflow-y-auto px-2 py-3">
        <div class="mx-auto min-h-full w-full max-w-[390px] overflow-hidden rounded-[1.75rem] border-[6px] border-slate-800 bg-slate-50 shadow-lg" data-moldura-celular>
          <Pesquisa
            ref="pesquisa"
            :formulario="formularioPrevia"
            :variaveis="variaveisPrevia"
            previa
            :reiniciavel="false"
            :finais="finais"
            :foco-id="focoId"
            :motivo-foco="motivoFoco"
            :indicacao-exemplo="indicacaoExemplo"
          />
        </div>
      </div>
      <!-- Computador: a página em 1024 px, reduzida para caber, numa janela de navegador -->
      <div v-else class="h-full p-3">
        <div class="flex h-full flex-col overflow-hidden rounded-xl border border-slate-300 bg-slate-50 shadow-sm" data-tela-computador>
          <div class="flex h-6 shrink-0 items-center gap-1.5 border-b border-slate-300 bg-slate-200 px-2.5" aria-hidden="true">
            <span class="size-2 rounded-full bg-slate-400" />
            <span class="size-2 rounded-full bg-slate-400" />
            <span class="size-2 rounded-full bg-slate-400" />
          </div>
          <div class="relative flex-1 overflow-hidden">
            <div class="absolute left-0 top-0 overflow-y-auto bg-slate-50" :style="estiloComputador">
              <Pesquisa
                ref="pesquisa"
                :formulario="formularioPrevia"
                :variaveis="variaveisPrevia"
                previa
                :reiniciavel="false"
                :finais="finais"
                :foco-id="focoId"
                :motivo-foco="motivoFoco"
                :indicacao-exemplo="indicacaoExemplo"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="flex-1 overflow-y-auto p-3" aria-live="polite" data-previa-canal>
      <Carregando v-if="carregando" rotulo="Carregando as mensagens" />
      <Alerta v-else-if="erro" tom="erro">
        {{ erro }}
        <button type="button" class="link ml-1" @click="carregarMensagens">Tentar de novo</button>
      </Alerta>
      <template v-else-if="config">
        <PreviaEmail v-if="canal === 'email' && previaEmail" :previa="previaEmail" :empresa="exemplo.empresa" />
        <PreviaWhatsapp v-else-if="canal === 'whatsapp'" :texto="textoWhatsapp" :link="exemplo.link" />
      </template>
    </div>

    <div class="flex flex-col gap-0.5 border-t border-borda bg-superficie px-3 py-2 text-xs text-texto-fraco">
      <p v-if="avisoLogoEmpresa" class="flex items-center gap-1.5 font-semibold text-texto-suave" data-aviso-logo>
        <ImageIcon class="size-3.5 shrink-0" aria-hidden="true" /> Usando o logo da empresa
      </p>
      <p v-if="canal === 'pagina'">Exemplo com cliente “Maria” e referência “Pedido 12345”. Mostra o rascunho; nada é gravado aqui.</p>
      <template v-else>
        <p>
          {{ canal === 'email' ? 'Convite por e-mail com os textos e o visual' : 'Mensagem do botão WhatsApp com os textos' }} de Configurações › Envios.
          Exemplo com a cliente Maria, da Mercado Bom Preço.
        </p>
        <RouterLink v-if="podeEditarMensagens" to="/configuracoes/envios" class="link self-start font-semibold" data-editar-mensagens>
          Editar as mensagens
        </RouterLink>
      </template>
    </div>
  </div>
</template>
