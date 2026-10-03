<script setup lang="ts">
// Auditoria › E-mails enviados (etapa 5e, docs/api-etapa-5e.md §5 e §6.3): cada e-mail que saiu em nome da conta
// (pesquisas e e-mails do sistema), dos últimos 90 dias. No topo, o alerta das falhas dos últimos 7 dias com "Ver só as
// falhas"; filtros de período (padrão 30 dias), situação, tipo e busca; tabela no computador e cartões no celular.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { MailCheck, Search } from 'lucide-vue-next'
import { emailsEnviadosApi, mensagemDoErro, type EmailEnviado } from '@/api'
import { formatarDataHora, hojeIso } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import TextoEmail from '@/components/ui/TextoEmail.vue'
import {
  FILTROS_EMAILS_PADRAO,
  PERIODOS_EMAILS,
  SITUACOES_EMAIL,
  TIPOS_EMAIL,
  ehSoFalhas,
  erroPeriodoEmails,
  filtrosEmailsParaApi,
  filtrosSoFalhas,
  primeiroDiaGuardado,
  rotuloTipoEmail,
  situacaoEmail,
  temFiltroEmails,
  textoFalhas,
  textoTotalEmails,
  type FiltrosEmailsTela,
} from './emails'

const hoje = hojeIso()
const filtros = reactive<FiltrosEmailsTela>({ ...FILTROS_EMAILS_PADRAO })
const pagina = ref(1)
const itens = ref<EmailEnviado[]>([])
const total = ref(0)
const porPagina = ref(20)
const falhas7 = ref(0)
const carregando = ref(true)
const carregou = ref(false)
const erro = ref<string | null>(null)
let controlador: AbortController | null = null
let espera: ReturnType<typeof setTimeout> | undefined
/** A busca do último pedido: a espera da digitação só busca de novo se ela mudou. */
let buscaAplicada = ''

const opcoesSituacao = (Object.keys(SITUACOES_EMAIL) as (keyof typeof SITUACOES_EMAIL)[]).map((s) => ({ valor: s, rotulo: SITUACOES_EMAIL[s].rotulo }))
const erroPeriodo = computed(() => erroPeriodoEmails(filtros, hoje))
const temFiltro = computed(() => temFiltroEmails(filtros))
const soFalhas = computed(() => ehSoFalhas(filtros))

const colunas: Coluna[] = [
  { chave: 'criado_em', rotulo: 'Data' },
  { chave: 'tipo', rotulo: 'Tipo' },
  { chave: 'destinatario', rotulo: 'Destinatário' },
  { chave: 'assunto', rotulo: 'Assunto' },
  { chave: 'situacao', rotulo: 'Situação' },
  { chave: 'erro', rotulo: 'Erro' },
]

async function carregar() {
  if (erroPeriodo.value) return
  clearTimeout(espera)
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  buscaAplicada = filtros.busca.trim()
  try {
    const r = await emailsEnviadosApi.listar(filtrosEmailsParaApi(filtros, pagina.value, hoje), controlador.signal)
    itens.value = r.itens ?? []
    total.value = r.total ?? 0
    porPagina.value = r.por_pagina || 20
    falhas7.value = r.falhas_7_dias ?? 0
    carregou.value = true
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

/** Filtro mudou: volta para a primeira página (que busca) ou busca de novo. */
function daPrimeira() {
  if (pagina.value !== 1) pagina.value = 1
  else void carregar()
}

// Período, situação e tipo: busca na hora. Texto: espera a pessoa parar de digitar.
watch(() => [filtros.periodo, filtros.de, filtros.ate, filtros.situacao, filtros.tipo], daPrimeira)
watch(
  () => filtros.busca,
  (b) => {
    clearTimeout(espera)
    if (b.trim() === buscaAplicada) return
    espera = setTimeout(daPrimeira, 400)
  },
)
watch(pagina, () => void carregar())

// "Escolher as datas" começa com o período que estava valendo (as datas não ficam vazias).
watch(
  () => filtros.periodo,
  (p, antes) => {
    if (p !== 'personalizado' || (filtros.de && filtros.ate)) return
    const atual = filtrosEmailsParaApi({ ...filtros, periodo: antes ?? '30' }, 1, hoje)
    filtros.de = atual.de ?? ''
    filtros.ate = atual.ate ?? ''
  },
  { flush: 'sync' },
)

/** "Ver só as falhas" (e, de novo, "Ver todos os e-mails"): é o mesmo botão, então o foco fica nele. */
function alternarFalhas() {
  Object.assign(filtros, soFalhas.value ? { ...FILTROS_EMAILS_PADRAO } : filtrosSoFalhas())
}

function limparFiltros() {
  Object.assign(filtros, { ...FILTROS_EMAILS_PADRAO })
}

onMounted(carregar)
onBeforeUnmount(() => {
  controlador?.abort()
  clearTimeout(espera)
})
</script>

<template>
  <div class="flex flex-col gap-4" data-aba-emails>
    <Alerta v-if="falhas7 > 0" tom="atencao" data-alerta-falhas>
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p class="font-semibold text-atencao">{{ textoFalhas(falhas7) }}</p>
        <Botao variante="secundario" tamanho="sm" class="self-start sm:self-auto" data-so-falhas @click="alternarFalhas">
          {{ soFalhas ? 'Ver todos os e-mails' : 'Ver só as falhas' }}
        </Botao>
      </div>
    </Alerta>

    <div class="cartao grid gap-3 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4" data-filtros-emails>
      <Selecao v-model="filtros.periodo" rotulo="Período" :opcoes="PERIODOS_EMAILS" />
      <Selecao v-model="filtros.situacao" rotulo="Situação" :opcoes="opcoesSituacao" vazio="Todas" />
      <Selecao v-model="filtros.tipo" rotulo="Tipo" :opcoes="TIPOS_EMAIL" vazio="Todos" />
      <Campo v-model="filtros.busca" rotulo="Buscar" tipo="search" placeholder="Destinatário ou assunto">
        <template #antes><Search class="size-4" aria-hidden="true" /></template>
      </Campo>
      <div v-if="filtros.periodo === 'personalizado'" class="grid grid-cols-2 gap-3 sm:col-span-2" data-datas-emails>
        <Campo v-model="filtros.de" rotulo="De" tipo="date" :min="primeiroDiaGuardado(hoje)" :max="filtros.ate || hoje" :erro="erroPeriodo" />
        <Campo v-model="filtros.ate" rotulo="Até" tipo="date" :min="filtros.de || primeiroDiaGuardado(hoje)" :max="hoje" />
      </div>
    </div>

    <div class="cartao">
      <div class="flex min-h-12 items-center justify-between gap-3 border-b border-borda px-4 py-3 text-sm sm:px-5">
        <p class="text-texto-suave" aria-live="polite" data-total-emails>
          <template v-if="carregando">Carregando…</template>
          <template v-else-if="!erro">{{ textoTotalEmails(total) }} {{ soFalhas ? 'com falha nos últimos 7 dias' : 'no período' }}</template>
        </p>
        <Botao v-if="temFiltro" variante="fantasma" tamanho="sm" data-limpar-filtros @click="limparFiltros">Limpar filtros</Botao>
      </div>

      <div v-if="carregando && !carregou" class="p-5"><Carregando :linhas="5" rotulo="Carregando os e-mails" /></div>
      <Alerta v-else-if="erro" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <EstadoVazio
        v-else-if="!itens.length"
        :icone="temFiltro ? Search : MailCheck"
        :titulo="temFiltro ? 'Nenhum e-mail com esses filtros' : 'Nenhum e-mail no período'"
        :descricao="temFiltro ? 'Tente mudar os filtros ou o período.' : 'Os convites, lembretes, agradecimentos e e-mails do sistema aparecem aqui assim que saírem.'"
        data-vazio-emails
      />
      <div v-else :class="{ 'opacity-60 transition-opacity': carregando }" :aria-busy="carregando">
        <!-- Computador: tabela -->
        <div class="hidden md:block" data-tabela-emails>
          <Tabela :colunas="colunas" :linhas="itens" :chave="(e) => String(e.id)" legenda="E-mails enviados">
            <template #cel-criado_em="{ linha: e }">
              <span class="whitespace-nowrap text-texto-suave">{{ formatarDataHora(e.criado_em) }}</span>
            </template>
            <template #cel-tipo="{ linha: e }">
              <span class="text-texto-suave">{{ rotuloTipoEmail(e) }}</span>
            </template>
            <template #cel-destinatario="{ linha: e }">
              <span class="block max-w-60 text-texto"><TextoEmail :email="e.destinatario" /></span>
            </template>
            <template #cel-assunto="{ linha: e }">
              <span class="block max-w-72 text-texto [overflow-wrap:anywhere]">{{ e.assunto || '—' }}</span>
            </template>
            <template #cel-situacao="{ linha: e }">
              <Etiqueta :tom="situacaoEmail(e.situacao).tom" ponto>{{ situacaoEmail(e.situacao).rotulo }}</Etiqueta>
            </template>
            <template #cel-erro="{ linha: e }">
              <span v-if="e.erro" class="block max-w-64 text-xs text-erro">{{ e.erro }}</span>
              <span v-else class="text-texto-fraco">—</span>
            </template>
          </Tabela>
        </div>

        <!-- Celular: cartões -->
        <ul class="divide-y divide-borda md:hidden" aria-label="E-mails enviados" data-cartoes-emails>
          <li v-for="e in itens" :key="String(e.id)" class="flex flex-col gap-1.5 px-4 py-3.5" data-cartao-email>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <Etiqueta :tom="situacaoEmail(e.situacao).tom" ponto>{{ situacaoEmail(e.situacao).rotulo }}</Etiqueta>
              <span class="text-xs text-texto-fraco">{{ formatarDataHora(e.criado_em) }}</span>
            </div>
            <p class="font-semibold text-texto [overflow-wrap:anywhere]">{{ e.assunto || '—' }}</p>
            <p class="text-sm text-texto-suave"><span class="text-texto-fraco">Para </span><TextoEmail :email="e.destinatario" /></p>
            <p class="text-xs text-texto-fraco">{{ rotuloTipoEmail(e) }}</p>
            <p v-if="e.erro" class="text-sm text-erro"><span class="sr-only">Erro: </span>{{ e.erro }}</p>
          </li>
        </ul>
      </div>

      <Paginacao v-if="!erro" v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando" :nome-itens="total === 1 ? 'e-mail' : 'e-mails'" />
    </div>

    <div class="flex flex-col gap-1 text-sm text-texto-fraco" data-nota-emails>
      <p>Enviado = o provedor aceitou o e-mail. Devoluções da caixa de quem recebe não aparecem aqui.</p>
      <p>Guardamos os últimos 90 dias.</p>
    </div>
  </div>
</template>
