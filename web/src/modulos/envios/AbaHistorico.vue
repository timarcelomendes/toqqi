<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { History, Mail, MessageCircle, RotateCcw, Search, SlidersHorizontal, X } from 'lucide-vue-next'
import { enviosApi, mensagemDoErro, type CanalEnvio, type Envio, type FiltrosHistorico, type Id, type SituacaoEnvio, type TipoEnvio } from '@/api'
import { avisar } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import { CANAIS_ENVIO, INTERVALO_ATUALIZACAO_MS, ORIGENS_ENVIO, SITUACOES_ENVIO, TIPOS_ENVIO, rotuloDe, situacaoEnvio } from './logica'

const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()
const podeDisparar = computed(() => sessao.pode('envios.disparar'))

const linhas = ref<Envio[]>([])
const total = ref(0)
const porPagina = ref(50)
const pagina = ref(1)
const carregando = ref(true)
const erro = ref<string | null>(null)
const filtrosAbertos = ref(false)
const tentando = ref<Id | null>(null)

// Vindo do detalhe do contato: /envios?aba=historico&contato=ID&nome=...
const contatoFiltro = ref<{ id: string; nome: string } | null>(
  typeof rota.query.contato === 'string' ? { id: rota.query.contato, nome: typeof rota.query.nome === 'string' ? rota.query.nome : 'este contato' } : null,
)

const filtros = reactive({
  busca: '',
  de: '',
  ate: '',
  tipo: '' as TipoEnvio | '',
  canal: '' as CanalEnvio | '',
  situacao: '' as SituacaoEnvio | '',
})

const opcoes = <T extends string>(mapa: Record<T, string>) => (Object.keys(mapa) as T[]).map((valor) => ({ valor, rotulo: mapa[valor] }))
const opcoesSituacao = (Object.keys(SITUACOES_ENVIO) as SituacaoEnvio[]).map((valor) => ({ valor, rotulo: SITUACOES_ENVIO[valor].rotulo }))

const colunas: Coluna[] = [
  { chave: 'criado_em', rotulo: 'Quando', classe: 'hidden sm:table-cell' },
  { chave: 'contato', rotulo: 'Para' },
  { chave: 'tipo', rotulo: 'O quê', classe: 'hidden md:table-cell' },
  { chave: 'situacao', rotulo: 'Situação', classe: 'hidden sm:table-cell' },
  { chave: 'origem', rotulo: 'Como saiu', classe: 'hidden lg:table-cell' },
  { chave: 'acoes', rotulo: 'Ações', rotuloOculto: true, alinhar: 'direita' },
]

const filtrosAtivos = computed(() => [filtros.de, filtros.ate, filtros.tipo, filtros.canal, filtros.situacao].filter((v) => v !== '').length)

let controle: AbortController | null = null
let temporizador: ReturnType<typeof setTimeout> | null = null
let desmontado = false

async function carregar(silencioso = false) {
  controle?.abort()
  controle = new AbortController()
  if (temporizador) clearTimeout(temporizador)
  if (!silencioso) {
    carregando.value = true
    erro.value = null
  }
  const q: FiltrosHistorico = { ...filtros, busca: filtros.busca.trim(), contato_id: contatoFiltro.value?.id ?? '', pagina: pagina.value }
  try {
    const r = await enviosApi.historico(q, controle.signal)
    linhas.value = r.itens
    total.value = r.total
    porPagina.value = r.por_pagina || 50
  } catch (e) {
    if (e instanceof DOMException) return
    if (!silencioso) erro.value = mensagemDoErro(e)
  } finally {
    if (!silencioso) carregando.value = false
    // Enquanto algo estiver saindo, atualiza sozinho.
    if (!desmontado && linhas.value.some((l) => l.situacao === 'pendente')) {
      temporizador = setTimeout(() => carregar(true), INTERVALO_ATUALIZACAO_MS)
    }
  }
}

function recarregar() {
  carregar()
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
  () => [filtros.de, filtros.ate, filtros.tipo, filtros.canal, filtros.situacao, contatoFiltro.value?.id],
  () => {
    pagina.value = 1
    carregar()
  },
)
watch(pagina, () => carregar())

function limparFiltros() {
  Object.assign(filtros, { de: '', ate: '', tipo: '', canal: '', situacao: '' })
}

function tirarContato() {
  contatoFiltro.value = null
  const { contato: _c, nome: _n, ...resto } = rota.query
  router.replace({ query: resto })
}

async function tentarDeNovo(e: Envio) {
  tentando.value = e.id
  try {
    await enviosApi.tentarDeNovo(e.id)
    avisar.sucesso(`Estamos enviando de novo para ${e.contato?.nome ?? e.para}.`)
    carregar(true)
  } catch (err) {
    avisar.erro(mensagemDoErro(err))
  } finally {
    tentando.value = null
  }
}

onMounted(() => carregar())
onBeforeUnmount(() => {
  desmontado = true
  controle?.abort()
  if (temporizador) clearTimeout(temporizador)
  if (atraso) clearTimeout(atraso)
})
defineExpose({ recarregar })
</script>

<template>
  <div class="cartao">
    <div class="flex flex-col gap-3 border-b border-borda p-4 sm:px-5">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Campo v-model="filtros.busca" rotulo="Buscar no histórico" rotulo-oculto tipo="search" placeholder="Buscar por nome ou e-mail" class="sm:max-w-sm sm:flex-1">
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <Botao variante="secundario" class="sm:ml-auto" :aria-expanded="filtrosAbertos" aria-controls="filtros-historico" @click="filtrosAbertos = !filtrosAbertos">
          <SlidersHorizontal class="size-4" aria-hidden="true" /> Filtros
          <span v-if="filtrosAtivos" class="rounded-full bg-marca-forte px-1.5 text-xs text-white">{{ filtrosAtivos }}</span>
        </Botao>
      </div>
      <div v-show="filtrosAbertos" id="filtros-historico" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Campo v-model="filtros.de" rotulo="De" tipo="date" />
        <Campo v-model="filtros.ate" rotulo="Até" tipo="date" />
        <Selecao v-model="filtros.tipo" rotulo="O quê" :opcoes="opcoes(TIPOS_ENVIO)" vazio="Tudo" />
        <Selecao v-model="filtros.canal" rotulo="Canal" :opcoes="opcoes(CANAIS_ENVIO)" vazio="Todos" />
        <Selecao v-model="filtros.situacao" rotulo="Situação" :opcoes="opcoesSituacao" vazio="Todas" />
        <div v-if="filtrosAtivos" class="sm:col-span-2 lg:col-span-5">
          <Botao variante="fantasma" tamanho="sm" @click="limparFiltros">Limpar filtros</Botao>
        </div>
      </div>
      <div v-if="contatoFiltro" class="flex items-center gap-2 text-sm">
        <span class="text-texto-fraco">Só os envios de</span>
        <Etiqueta tom="marca">{{ contatoFiltro.nome }}</Etiqueta>
        <button type="button" class="link inline-flex items-center gap-1 text-sm" @click="tirarContato">
          <X class="size-3.5" aria-hidden="true" /> Ver de todos
        </button>
      </div>
    </div>

    <Alerta v-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
    </Alerta>

    <Tabela v-else :colunas="colunas" :linhas="linhas" :chave="(e) => e.id" :carregando="carregando" legenda="Histórico de envios">
      <template #cel-criado_em="{ linha: e }">
        <span class="whitespace-nowrap text-texto-suave">{{ formatarDataHora(e.criado_em) }}</span>
      </template>
      <template #cel-contato="{ linha: e }">
        <div class="min-w-0">
          <RouterLink v-if="e.contato" :to="`/contatos/${e.contato.id}`" class="block truncate font-semibold text-texto hover:underline">{{ e.contato.nome }}</RouterLink>
          <p class="truncate" :class="e.contato ? 'text-texto-fraco' : 'font-semibold text-texto'">{{ e.para }}</p>
          <p class="text-xs text-texto-fraco sm:hidden">{{ formatarDataHora(e.criado_em) }}</p>
          <p class="text-xs text-texto-suave md:hidden">{{ rotuloDe(TIPOS_ENVIO, e.tipo) }} · {{ rotuloDe(CANAIS_ENVIO, e.canal) }}</p>
          <div class="mt-1 sm:hidden">
            <Etiqueta :tom="situacaoEnvio(e.situacao).tom" ponto>{{ situacaoEnvio(e.situacao).rotulo }}</Etiqueta>
            <p v-if="e.erro" class="mt-1 text-xs text-erro">{{ e.erro }}</p>
          </div>
        </div>
      </template>
      <template #cel-tipo="{ linha: e }">
        <span class="inline-flex items-center gap-1.5 whitespace-nowrap text-texto-suave">
          <MessageCircle v-if="e.canal === 'whatsapp'" class="size-4 text-emerald-700" aria-hidden="true" />
          <Mail v-else class="size-4 text-texto-fraco" aria-hidden="true" />
          {{ rotuloDe(TIPOS_ENVIO, e.tipo) }}<span class="sr-only"> por {{ rotuloDe(CANAIS_ENVIO, e.canal) }}</span>
        </span>
      </template>
      <template #cel-situacao="{ linha: e }">
        <div class="flex flex-col items-start gap-1">
          <Etiqueta :tom="situacaoEnvio(e.situacao).tom" ponto>{{ situacaoEnvio(e.situacao).rotulo }}</Etiqueta>
          <p v-if="e.erro" class="max-w-64 text-xs text-erro">{{ e.erro }}</p>
          <p v-if="e.situacao === 'aberto_no_whatsapp'" class="max-w-64 text-xs text-texto-fraco">Depende de quem abriu ter apertado Enviar no WhatsApp.</p>
        </div>
      </template>
      <template #cel-origem="{ linha: e }">
        <span class="text-texto-suave">{{ e.origem === 'manual' && e.usuario ? `Enviado por ${e.usuario.nome}` : rotuloDe(ORIGENS_ENVIO, e.origem) }}</span>
      </template>
      <template #cel-acoes="{ linha: e }">
        <Botao
          v-if="podeDisparar && e.pode_tentar_de_novo"
          variante="secundario"
          tamanho="sm"
          :carregando="tentando === e.id"
          :desabilitado="tentando !== null"
          @click="tentarDeNovo(e)"
        >
          <RotateCcw v-if="tentando !== e.id" class="size-4" aria-hidden="true" /> Tentar de novo<span class="sr-only"> para {{ e.contato?.nome ?? e.para }}</span>
        </Botao>
      </template>
      <template #vazio>
        <EstadoVazio
          v-if="filtros.busca || filtrosAtivos || contatoFiltro"
          :icone="Search"
          titulo="Nenhum envio encontrado"
          descricao="Tente outra busca ou limpe os filtros."
        />
        <EstadoVazio v-else :icone="History" titulo="Nada enviado ainda" descricao="Cada pesquisa, lembrete e agradecimento que sair aparece aqui, com a situação de cada um." />
      </template>
    </Tabela>
    <Paginacao v-if="!erro" v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando" :nome-itens="total === 1 ? 'envio' : 'envios'" />
  </div>
</template>
