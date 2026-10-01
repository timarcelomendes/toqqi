<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  AlertTriangle,
  Clock,
  Hourglass,
  ListChecks,
  MessageCircle,
  Search,
  Send,
  SlidersHorizontal,
  ThumbsUp,
  UserX,
  X,
} from 'lucide-vue-next'
import {
  enviosApi,
  mensagemDoErro,
  type ContatoEnvio,
  type FiltrosFila,
  type Id,
  type Referencia,
  type ResumoEnvios,
  type SituacaoContato,
} from '@/api'
import { avisar } from '@/composables/avisos'
import { useWhatsapp } from '@/composables/whatsapp'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData, formatarDiaMes } from '@/utils/datas'
import { exibirTelefone, formatarNumero } from '@/utils/formatos'
import { situacaoContato } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import CampoEmpresa from '@/modulos/contatos/CampoEmpresa.vue'
import ModalDisparo, { type AlvoDisparo } from './ModalDisparo.vue'
import {
  INTERVALO_ATUALIZACAO_MS,
  LIMITE_SELECAO,
  alternarPagina,
  alternarSelecao,
  contatos as rotuloContatos,
  estadoPagina,
  podeEnviarEmail,
  podeEnviarWhatsapp,
  temEnviando,
  type Selecao as TipoSelecao,
} from './logica'

withDefaults(defineProps<{ emailLiberado?: boolean }>(), { emailLiberado: true })
const emit = defineEmits<{ 'pre-condicao': [] }>()

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const whatsapp = useWhatsapp()
const podeDisparar = computed(() => sessao.pode('envios.disparar'))

const linhas = ref<ContatoEnvio[]>([])
const total = ref(0)
const porPagina = ref(50)
const pagina = ref(1)
const carregando = ref(true)
const erro = ref<string | null>(null)
const resumo = ref<ResumoEnvios | null>(null)
const filtrosAbertos = ref(false)
const contandoFila = ref(false)

const filtros = reactive({
  situacao: '' as SituacaoContato | '',
  busca: '',
  grupo_id: '' as Id | '',
  responsavel_id: '' as Id | '',
  empresa: null as Referencia | null,
  proximo_de: '',
  proximo_ate: '',
  ultimo_de: '',
  ultimo_ate: '',
  lembrete: '' as 'hoje' | 'amanha' | '',
  mostrar_inativos: false,
})

const selecao = reactive<TipoSelecao>(new Map())
const modalAberto = ref(false)
const alvo = ref<AlvoDisparo | null>(null)

type Cartao = { chave: keyof ResumoEnvios; situacao: SituacaoContato; rotulo: string; icone: typeof Clock; cor: string }
const cartoes: Cartao[] = [
  { chave: 'na_fila', situacao: 'na_fila', rotulo: 'Na fila', icone: ListChecks, cor: 'text-info bg-info-suave' },
  { chave: 'aguardando', situacao: 'aguardando', rotulo: 'Aguardando resposta', icone: Hourglass, cor: 'text-atencao bg-atencao-suave' },
  { chave: 'responderam', situacao: 'respondeu', rotulo: 'Responderam', icone: ThumbsUp, cor: 'text-sucesso bg-sucesso-suave' },
  { chave: 'com_erro', situacao: 'nao_saiu', rotulo: 'Com erro', icone: AlertTriangle, cor: 'text-erro bg-erro-suave' },
  { chave: 'saiu_da_lista', situacao: 'saiu_da_lista', rotulo: 'Saíram da lista', icone: UserX, cor: 'text-texto-suave bg-superficie-2' },
]

const colunas = computed<Coluna[]>(() => [
  ...(podeDisparar.value ? [{ chave: 'sel', rotulo: 'Selecionar', rotuloOculto: true, classe: 'w-10 !pr-0' }] : []),
  { chave: 'nome', rotulo: 'Contato' },
  { chave: 'situacao', rotulo: 'Situação', classe: 'hidden md:table-cell' },
  { chave: 'ultimo_envio', rotulo: 'Último envio', classe: 'hidden lg:table-cell' },
  { chave: 'proximo_envio', rotulo: 'Próximo envio', classe: 'hidden xl:table-cell' },
  { chave: 'acoes', rotulo: 'Ações', rotuloOculto: true, alinhar: 'direita' },
])

/** Filtros que valem para a lista e para "toda a fila" (sem página nem situação). */
function filtrosBase(): Omit<FiltrosFila, 'pagina' | 'por_pagina' | 'situacao'> {
  const f: Omit<FiltrosFila, 'pagina' | 'por_pagina' | 'situacao'> = {}
  if (filtros.busca.trim()) f.busca = filtros.busca.trim()
  if (filtros.grupo_id !== '') f.grupo_id = filtros.grupo_id
  if (filtros.responsavel_id !== '') f.responsavel_id = filtros.responsavel_id
  if (filtros.empresa) f.empresa_id = filtros.empresa.id
  for (const k of ['proximo_de', 'proximo_ate', 'ultimo_de', 'ultimo_ate'] as const) if (filtros[k]) f[k] = filtros[k]
  if (filtros.lembrete) f.lembrete = filtros.lembrete
  if (filtros.mostrar_inativos) f.mostrar_inativos = true
  return f
}

const filtrosAtivos = computed(
  () =>
    [filtros.grupo_id, filtros.responsavel_id, filtros.proximo_de, filtros.proximo_ate, filtros.ultimo_de, filtros.ultimo_ate, filtros.lembrete].filter(
      (v) => v !== '',
    ).length +
    (filtros.empresa ? 1 : 0) +
    (filtros.mostrar_inativos ? 1 : 0),
)

let controle: AbortController | null = null
let temporizador: ReturnType<typeof setTimeout> | null = null
let desmontado = false

function pararAtualizacao() {
  if (temporizador) clearTimeout(temporizador)
  temporizador = null
}

function agendarAtualizacao() {
  pararAtualizacao()
  if (desmontado || !temEnviando(linhas.value)) return
  temporizador = setTimeout(() => carregar(true), INTERVALO_ATUALIZACAO_MS)
}

async function carregarResumo() {
  try {
    resumo.value = await enviosApi.resumo()
  } catch {
    /* os cartões ficam sem número; a lista continua */
  }
}

/** `silencioso`: atualização automática, sem esqueleto de carregamento nem mensagem de erro por cima da lista. */
async function carregar(silencioso = false) {
  controle?.abort()
  controle = new AbortController()
  pararAtualizacao()
  if (!silencioso) {
    carregando.value = true
    erro.value = null
  }
  try {
    const r = await enviosApi.contatos(
      { ...filtrosBase(), ...(filtros.situacao ? { situacao: filtros.situacao } : {}), pagina: pagina.value },
      controle.signal,
    )
    linhas.value = r.itens
    total.value = r.total
    porPagina.value = r.por_pagina || 50
    if (silencioso) carregarResumo()
  } catch (e) {
    if (e instanceof DOMException) return
    if (!silencioso) erro.value = mensagemDoErro(e)
  } finally {
    if (!silencioso) carregando.value = false
    agendarAtualizacao()
  }
}

function recarregar() {
  carregar()
  carregarResumo()
}

let atraso: ReturnType<typeof setTimeout> | null = null
watch(
  () => filtros.busca,
  () => {
    if (atraso) clearTimeout(atraso)
    atraso = setTimeout(() => {
      pagina.value = 1
      carregar()
    }, 300)
  },
)
watch(
  () => [
    filtros.situacao,
    filtros.grupo_id,
    filtros.responsavel_id,
    filtros.empresa?.id,
    filtros.proximo_de,
    filtros.proximo_ate,
    filtros.ultimo_de,
    filtros.ultimo_ate,
    filtros.lembrete,
    filtros.mostrar_inativos,
  ],
  () => {
    pagina.value = 1
    carregar()
  },
)
watch(pagina, () => carregar())

function escolherCartao(s: SituacaoContato) {
  filtros.situacao = filtros.situacao === s ? '' : s
}

function limparFiltros() {
  Object.assign(filtros, {
    grupo_id: '',
    responsavel_id: '',
    empresa: null,
    proximo_de: '',
    proximo_ate: '',
    ultimo_de: '',
    ultimo_ate: '',
    lembrete: '',
    mostrar_inativos: false,
  })
}

// ── Seleção ─────────────────────────────────────────────
const selecionaveis = computed(() => linhas.value.filter(podeEnviarEmail))
const estadoDaPagina = computed(() => estadoPagina(selecao, selecionaveis.value))

function avisarLimite() {
  avisar.atencao(`Dá para enviar para até ${formatarNumero(LIMITE_SELECAO)} contatos de uma vez. Envie estes e depois escolha os próximos.`)
}

function alternar(c: ContatoEnvio, e: Event) {
  if (alternarSelecao(selecao, c) === 'limite') {
    ;(e.target as HTMLInputElement).checked = false
    avisarLimite()
  }
}

function alternarTodos() {
  const r = alternarPagina(selecao, selecionaveis.value)
  if (r.foraDoLimite) avisarLimite()
}

function limparSelecao() {
  selecao.clear()
}

// ── Envio ───────────────────────────────────────────────
function enviarUm(c: ContatoEnvio) {
  alvo.value = { tipo: 'contatos', ids: [c.id], nome: c.nome }
  modalAberto.value = true
}

function enviarSelecionados() {
  if (!selecao.size) return
  alvo.value = { tipo: 'contatos', ids: [...selecao.values()].map((s) => s.id) }
  modalAberto.value = true
}

async function enviarFila() {
  contandoFila.value = true
  try {
    const base = filtrosBase()
    // Quantos estão na fila com os filtros atuais (a confirmação sempre diz o número).
    const r = await enviosApi.contatos({ ...base, situacao: 'na_fila', pagina: 1, por_pagina: 1 })
    if (!r.total) {
      avisar.info(filtrosAtivos.value || base.busca ? 'Ninguém na fila com esses filtros.' : 'Ninguém na fila agora. Todos já receberam a pesquisa.')
      return
    }
    alvo.value = { tipo: 'fila', quantidade: r.total, filtros: base }
    modalAberto.value = true
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    contandoFila.value = false
  }
}

function aoEnviar() {
  if (alvo.value?.tipo === 'contatos' && alvo.value.ids.length > 1) limparSelecao()
  recarregar()
}

async function abrirWhatsapp(c: ContatoEnvio) {
  if (await whatsapp.abrir(c)) recarregar()
}

function motivoSemEmail(c: ContatoEnvio): string | null {
  if (!c.ativo) return 'Contato inativo'
  if (c.situacao === 'saiu_da_lista') return 'Saiu da lista'
  if (!c.email) return 'Sem e-mail'
  return null
}

onMounted(() => {
  recarregar()
  cadastros.garantir(['grupos', 'responsaveis'])
})
onBeforeUnmount(() => {
  desmontado = true
  controle?.abort()
  pararAtualizacao()
  if (atraso) clearTimeout(atraso)
})
defineExpose({ recarregar })
</script>

<template>
  <div class="flex flex-col gap-5">
    <!-- Cartões: resumo e atalho de filtro -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" role="group" aria-label="Resumo e filtro rápido por situação">
      <button
        v-for="c in cartoes"
        :key="c.chave"
        type="button"
        class="cartao flex flex-col items-start gap-2 p-4 text-left transition-colors hover:border-borda-forte focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco"
        :class="filtros.situacao === c.situacao ? '!border-marca ring-2 ring-marca/25' : ''"
        :aria-pressed="filtros.situacao === c.situacao"
        @click="escolherCartao(c.situacao)"
      >
        <span class="flex size-8 items-center justify-center rounded-lg" :class="c.cor" aria-hidden="true"><component :is="c.icone" class="size-4" /></span>
        <span class="text-2xl font-extrabold tabular-nums text-texto">{{ resumo ? formatarNumero(resumo[c.chave]) : '—' }}</span>
        <span class="text-sm font-medium text-texto-suave">{{ c.rotulo }}</span>
      </button>
    </div>
    <p v-if="resumo" class="-mt-2 text-sm text-texto-fraco">
      {{ formatarNumero(resumo.enviados_30d) }} {{ resumo.enviados_30d === 1 ? 'pesquisa enviada' : 'pesquisas enviadas' }} nos últimos 30 dias
      · {{ formatarNumero(resumo.lembretes_hoje) }} {{ resumo.lembretes_hoje === 1 ? 'lembrete previsto' : 'lembretes previstos' }} para hoje
    </p>

    <div class="cartao">
      <div class="flex flex-col gap-3 border-b border-borda p-4 sm:px-5">
        <div class="flex flex-col gap-3 md:flex-row md:items-center">
          <Campo v-model="filtros.busca" rotulo="Buscar contatos" rotulo-oculto tipo="search" placeholder="Buscar por nome, e-mail ou telefone" class="md:max-w-sm md:flex-1">
            <template #antes><Search class="size-4" aria-hidden="true" /></template>
          </Campo>
          <div class="flex flex-wrap items-center gap-2 md:ml-auto">
            <Botao variante="secundario" :aria-expanded="filtrosAbertos" aria-controls="filtros-fila" @click="filtrosAbertos = !filtrosAbertos">
              <SlidersHorizontal class="size-4" aria-hidden="true" /> Filtros
              <span v-if="filtrosAtivos" class="rounded-full bg-marca-forte px-1.5 text-xs text-white">{{ filtrosAtivos }}</span>
            </Botao>
            <Botao
              v-if="podeDisparar"
              :carregando="contandoFila"
              :desabilitado="!emailLiberado"
              :title="emailLiberado ? undefined : 'Resolva os itens do aviso acima para liberar o envio por e-mail.'"
              @click="enviarFila"
            >
              <Send v-if="!contandoFila" class="size-4" aria-hidden="true" /> Enviar para toda a fila
            </Botao>
          </div>
        </div>
        <div v-show="filtrosAbertos" id="filtros-fila" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Selecao v-model="filtros.grupo_id" rotulo="Grupo" :opcoes="cadastros.listas.grupos.map((g) => ({ valor: g.id, rotulo: g.nome }))" vazio="Todos" />
          <Selecao v-model="filtros.responsavel_id" rotulo="Responsável" :opcoes="cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome }))" vazio="Todos" />
          <CampoEmpresa v-model="filtros.empresa" rotulo="Empresa" placeholder="Todas" />
          <Selecao
            v-model="filtros.lembrete"
            rotulo="Lembrete"
            :opcoes="[{ valor: 'hoje', rotulo: 'Lembrete sai hoje' }, { valor: 'amanha', rotulo: 'Lembrete sai amanhã' }]"
            vazio="Tanto faz"
          />
          <fieldset class="flex flex-col gap-1.5 sm:col-span-2">
            <legend class="mb-1.5 text-sm font-semibold text-texto">Próximo envio</legend>
            <div class="grid grid-cols-2 gap-2">
              <Campo v-model="filtros.proximo_de" rotulo="Próximo envio a partir de" rotulo-oculto tipo="date" />
              <Campo v-model="filtros.proximo_ate" rotulo="Próximo envio até" rotulo-oculto tipo="date" />
            </div>
          </fieldset>
          <fieldset class="flex flex-col gap-1.5 sm:col-span-2">
            <legend class="mb-1.5 text-sm font-semibold text-texto">Último envio</legend>
            <div class="grid grid-cols-2 gap-2">
              <Campo v-model="filtros.ultimo_de" rotulo="Último envio a partir de" rotulo-oculto tipo="date" />
              <Campo v-model="filtros.ultimo_ate" rotulo="Último envio até" rotulo-oculto tipo="date" />
            </div>
          </fieldset>
          <div class="flex flex-wrap items-center justify-between gap-3 sm:col-span-2 lg:col-span-4">
            <CaixaSelecao v-model="filtros.mostrar_inativos" rotulo="Mostrar contatos inativos" />
            <Botao v-if="filtrosAtivos" variante="fantasma" tamanho="sm" @click="limparFiltros">Limpar filtros</Botao>
          </div>
        </div>
        <div v-if="filtros.situacao" class="flex items-center gap-2 text-sm">
          <span class="text-texto-fraco">Mostrando:</span>
          <Etiqueta :tom="situacaoContato(filtros.situacao).tom">{{ cartoes.find((c) => c.situacao === filtros.situacao)?.rotulo }}</Etiqueta>
          <button type="button" class="link inline-flex items-center gap-1 text-sm" @click="filtros.situacao = ''">
            <X class="size-3.5" aria-hidden="true" /> Mostrar todos
          </button>
        </div>
      </div>

      <!-- Barra de seleção -->
      <div
        v-if="podeDisparar && (selecao.size || selecionaveis.length)"
        class="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-borda px-4 py-2.5 sm:px-5"
        :class="selecao.size ? 'bg-marca-suave' : ''"
      >
        <label class="flex cursor-pointer items-center gap-2.5 text-sm font-medium text-texto">
          <input
            type="checkbox"
            class="size-5 cursor-pointer rounded-md accent-[var(--t-marca-forte)]"
            :checked="estadoDaPagina === 'todos'"
            :indeterminate="estadoDaPagina === 'alguns'"
            :disabled="!selecionaveis.length"
            @change="alternarTodos"
          />
          Marcar todos desta página
        </label>
        <template v-if="selecao.size">
          <p class="text-sm text-texto" aria-live="polite">
            <strong>{{ rotuloContatos(selecao.size) }}</strong> {{ selecao.size === 1 ? 'selecionado' : 'selecionados' }}
            <span class="text-texto-fraco">(máximo {{ formatarNumero(LIMITE_SELECAO) }})</span>
          </p>
          <div class="flex flex-wrap items-center gap-2 sm:ml-auto">
            <Botao variante="fantasma" tamanho="sm" @click="limparSelecao">Limpar seleção</Botao>
            <Botao tamanho="sm" :desabilitado="!emailLiberado" @click="enviarSelecionados">
              <Send class="size-4" aria-hidden="true" /> Enviar para selecionados
            </Botao>
          </div>
        </template>
      </div>

      <Alerta v-if="erro" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
      </Alerta>

      <Tabela v-else :colunas="colunas" :linhas="linhas" :chave="(c) => c.id" :carregando="carregando" legenda="Contatos para envio de pesquisa">
        <template #cel-sel="{ linha: c }">
          <input
            v-if="podeEnviarEmail(c)"
            type="checkbox"
            class="size-5 cursor-pointer rounded-md accent-[var(--t-marca-forte)]"
            :checked="selecao.has(String(c.id))"
            :aria-label="`Selecionar ${c.nome}`"
            @change="alternar(c, $event)"
          />
          <span v-else class="sr-only">{{ motivoSemEmail(c) ?? 'Não pode ser selecionado agora' }}</span>
        </template>
        <template #cel-nome="{ linha: c }">
          <div class="min-w-0">
            <RouterLink :to="`/contatos/${c.id}`" class="block truncate font-semibold text-texto hover:underline">{{ c.nome }}</RouterLink>
            <p class="truncate text-texto-fraco">{{ c.email || exibirTelefone(c.telefone) || 'Sem e-mail e sem telefone' }}</p>
            <p v-if="c.empresa" class="truncate text-xs text-texto-suave">{{ c.empresa.nome }}</p>
            <div class="mt-1 flex flex-wrap gap-1.5 md:hidden">
              <Etiqueta :tom="situacaoContato(c.situacao, c).tom" ponto>{{ situacaoContato(c.situacao, c).rotulo }}</Etiqueta>
            </div>
            <p v-if="c.ultimo_envio" class="mt-0.5 text-xs text-texto-fraco lg:hidden">Último envio: {{ formatarData(c.ultimo_envio) }}</p>
          </div>
        </template>
        <template #cel-situacao="{ linha: c }">
          <div class="flex flex-col items-start gap-1">
            <Etiqueta :tom="situacaoContato(c.situacao, c).tom" ponto>{{ situacaoContato(c.situacao, c).rotulo }}</Etiqueta>
            <p v-if="c.situacao === 'nao_saiu' && c.ultimo_erro" class="max-w-56 text-xs text-erro">{{ c.ultimo_erro }}</p>
            <p v-if="c.descanso_ate && c.situacao === 'na_fila'" class="text-xs text-texto-fraco">Em descanso até {{ formatarDiaMes(c.descanso_ate) }}</p>
          </div>
        </template>
        <template #cel-ultimo_envio="{ linha: c }">
          <span class="whitespace-nowrap text-texto-suave">{{ formatarData(c.ultimo_envio, 'Nunca') }}</span>
          <p v-if="c.lembretes_enviados" class="text-xs text-texto-fraco">
            {{ c.lembretes_enviados === 1 ? '1 lembrete enviado' : `${c.lembretes_enviados} lembretes enviados` }}
          </p>
        </template>
        <template #cel-proximo_envio="{ linha: c }">
          <span class="whitespace-nowrap text-texto-suave">{{ c.proximo_envio ? formatarData(c.proximo_envio) : c.situacao === 'na_fila' ? 'Já pode receber' : '—' }}</span>
          <p v-if="c.proximo_lembrete" class="text-xs text-texto-fraco">Lembrete em {{ formatarDiaMes(c.proximo_lembrete) }}</p>
        </template>
        <template #cel-acoes="{ linha: c }">
          <div v-if="podeDisparar" class="flex justify-end gap-1.5">
            <Botao
              v-if="podeEnviarEmail(c)"
              variante="secundario"
              tamanho="sm"
              :desabilitado="!emailLiberado"
              @click="enviarUm(c)"
            >
              <Send class="size-4" aria-hidden="true" /><span class="hidden sm:inline">Enviar agora</span><span class="sr-only sm:hidden">Enviar agora para {{ c.nome }}</span>
            </Botao>
            <button
              v-if="podeEnviarWhatsapp(c)"
              type="button"
              class="inline-flex h-8 items-center gap-1.5 rounded-xl bg-emerald-700 px-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco disabled:cursor-not-allowed disabled:opacity-55"
              :disabled="whatsapp.abrindo.value !== null"
              :aria-label="`Enviar pelo WhatsApp para ${c.nome}`"
              :title="`Enviar pelo WhatsApp para ${c.nome}`"
              @click="abrirWhatsapp(c)"
            >
              <MessageCircle class="size-4" :class="{ 'animate-pulse': whatsapp.abrindo.value === c.id }" aria-hidden="true" />
              <span class="hidden sm:inline">WhatsApp</span>
            </button>
          </div>
        </template>
        <template #vazio>
          <EstadoVazio
            v-if="filtros.busca || filtrosAtivos || filtros.situacao"
            :icone="Search"
            titulo="Ninguém encontrado"
            descricao="Tente outra busca ou limpe os filtros."
          >
            <Botao variante="secundario" @click="() => { filtros.busca = ''; filtros.situacao = ''; limparFiltros() }">Limpar busca e filtros</Botao>
          </EstadoVazio>
          <EstadoVazio v-else :icone="Send" titulo="Ainda não há contatos para enviar" descricao="Cadastre ou importe seus clientes em Contatos. Eles aparecem aqui prontos para receber a pesquisa.">
            <Botao v-if="sessao.pode('contatos.ver')" variante="secundario" para="/contatos">Ir para Contatos</Botao>
          </EstadoVazio>
        </template>
      </Tabela>
      <Paginacao v-if="!erro" v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando" :nome-itens="total === 1 ? 'contato' : 'contatos'" />
    </div>

    <ModalDisparo v-model:aberto="modalAberto" :alvo="alvo" @enviado="aoEnviar" @pre-condicao="emit('pre-condicao')" />
  </div>
</template>
