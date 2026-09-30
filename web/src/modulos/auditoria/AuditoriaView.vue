<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ChevronDown, ChevronLeft, ChevronRight, History, Search, UserRound } from 'lucide-vue-next'
import { auditoriaApi, mensagemDoErro, type Gravidade, type ItemAuditoria } from '@/api'
import { formatarDataHora, hojeIso } from '@/utils/datas'
import { GRAVIDADES } from '@/utils/rotulos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Selecao from '@/components/ui/Selecao.vue'

const filtros = reactive({ de: hojeIso(-30), ate: hojeIso(), gravidade: '' as Gravidade | '', busca: '' })
const pagina = ref(1)
const itens = ref<ItemAuditoria[]>([])
const total = ref(0)
const porPagina = ref(20)
const carregando = ref(true)
const erro = ref<string | null>(null)
const abertos = ref(new Set<ItemAuditoria['id']>())
let controlador: AbortController | null = null
let espera: ReturnType<typeof setTimeout> | undefined

const opcoesGravidade = (Object.keys(GRAVIDADES) as Gravidade[]).map((g) => ({ valor: g, rotulo: GRAVIDADES[g].rotulo }))
const totalPaginas = computed(() => Math.max(1, Math.ceil(total.value / (porPagina.value || 20))))
const erroPeriodo = computed(() => (filtros.de && filtros.ate && filtros.de > filtros.ate ? 'A data inicial é depois da final.' : null))
const temFiltro = computed(() => !!filtros.gravidade || !!filtros.busca.trim())

async function carregar() {
  if (erroPeriodo.value) return
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await auditoriaApi.listar(
      { de: filtros.de, ate: filtros.ate, gravidade: filtros.gravidade, busca: filtros.busca.trim(), pagina: pagina.value },
      controlador.signal,
    )
    itens.value = r.itens
    total.value = r.total
    porPagina.value = r.por_pagina || 20
    pagina.value = r.pagina || pagina.value
    abertos.value = new Set()
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function irPara(p: number) {
  pagina.value = Math.min(Math.max(1, p), totalPaginas.value)
  carregar()
  document.getElementById('conteudo')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Datas e gravidade: busca na hora. Texto: espera a pessoa parar de digitar.
watch(() => [filtros.de, filtros.ate, filtros.gravidade], () => {
  pagina.value = 1
  carregar()
})
watch(() => filtros.busca, () => {
  clearTimeout(espera)
  espera = setTimeout(() => {
    pagina.value = 1
    carregar()
  }, 400)
})

function limparFiltros() {
  filtros.gravidade = ''
  filtros.busca = ''
}

function alternar(id: ItemAuditoria['id']) {
  const s = new Set(abertos.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  abertos.value = s
}

function detalheTexto(d: ItemAuditoria['detalhe']): string | null {
  if (d === null || d === undefined || d === '') return null
  if (typeof d === 'string') return d
  return null
}
function detalheCampos(d: ItemAuditoria['detalhe']): [string, string][] {
  if (!d || typeof d !== 'object') return []
  return Object.entries(d).map(([k, v]) => [k.replace(/_/g, ' '), typeof v === 'object' ? JSON.stringify(v) : String(v)])
}

onMounted(carregar)
onBeforeUnmount(() => {
  controlador?.abort()
  clearTimeout(espera)
})
</script>

<template>
  <CabecalhoPagina titulo="Auditoria" descricao="Tudo o que aconteceu de importante na sua conta: quem fez, o quê e quando." />

  <div class="cartao mb-4 grid gap-3 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4">
    <Campo v-model="filtros.de" rotulo="De" tipo="date" :max="filtros.ate || undefined" :erro="erroPeriodo" />
    <Campo v-model="filtros.ate" rotulo="Até" tipo="date" :min="filtros.de || undefined" :max="hojeIso()" />
    <Selecao v-model="filtros.gravidade" rotulo="Gravidade" :opcoes="opcoesGravidade" vazio="Todas" />
    <Campo v-model="filtros.busca" rotulo="Buscar" tipo="search" placeholder="Evento, pessoa, detalhe…">
      <template #antes><Search class="size-4" aria-hidden="true" /></template>
    </Campo>
  </div>

  <div class="cartao">
    <div class="flex items-center justify-between gap-3 border-b border-borda px-4 py-3 text-sm sm:px-5">
      <p class="text-texto-suave" aria-live="polite">
        <template v-if="!carregando && !erro">
          {{ total === 1 ? '1 registro' : `${total.toLocaleString('pt-BR')} registros` }} no período
        </template>
        <template v-else-if="carregando">Carregando…</template>
      </p>
      <Botao v-if="temFiltro" variante="fantasma" tamanho="sm" @click="limparFiltros">Limpar filtros</Botao>
    </div>

    <div v-if="carregando && !itens.length" class="p-5"><Carregando :linhas="5" /></div>
    <Alerta v-else-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <EstadoVazio
      v-else-if="!itens.length"
      :icone="History"
      titulo="Nenhum registro encontrado"
      :descricao="temFiltro ? 'Tente mudar os filtros ou o período.' : 'Não aconteceu nada registrado neste período.'"
    />
    <ul v-else class="divide-y divide-borda" :class="{ 'opacity-60 transition-opacity': carregando }" :aria-busy="carregando">
      <li v-for="item in itens" :key="item.id">
        <button
          type="button"
          class="flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors hover:bg-superficie-2/50 sm:items-center sm:px-5"
          :aria-expanded="abertos.has(item.id)"
          :aria-controls="`detalhe-${item.id}`"
          @click="alternar(item.id)"
        >
          <div class="flex min-w-0 flex-1 flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-4">
            <Etiqueta :tom="GRAVIDADES[item.gravidade]?.tom ?? 'neutro'" ponto class="self-start sm:w-28 sm:justify-center sm:self-auto">
              {{ GRAVIDADES[item.gravidade]?.rotulo ?? item.gravidade }}
            </Etiqueta>
            <p class="min-w-0 flex-1 font-semibold text-texto">{{ item.rotulo }}</p>
            <p class="flex items-center gap-1.5 text-sm text-texto-suave sm:w-48">
              <UserRound class="size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
              <span class="truncate">{{ item.usuario?.nome ?? 'Sistema' }}</span>
            </p>
            <p class="whitespace-nowrap text-sm text-texto-fraco sm:w-44 sm:text-right">{{ formatarDataHora(item.criado_em) }}</p>
          </div>
          <ChevronDown class="mt-1 size-5 shrink-0 text-texto-fraco transition-transform sm:mt-0" :class="{ 'rotate-180': abertos.has(item.id) }" aria-hidden="true" />
          <span class="sr-only">{{ abertos.has(item.id) ? 'Esconder detalhes' : 'Ver detalhes' }}</span>
        </button>
        <div v-if="abertos.has(item.id)" :id="`detalhe-${item.id}`" class="bg-superficie-2/40 px-4 pb-4 pt-1 text-sm sm:px-5">
          <p v-if="detalheTexto(item.detalhe)" class="whitespace-pre-line text-texto-suave">{{ detalheTexto(item.detalhe) }}</p>
          <dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            <template v-for="[k, v] in detalheCampos(item.detalhe)" :key="k">
              <dt class="capitalize text-texto-fraco">{{ k }}</dt>
              <dd class="break-all text-texto">{{ v }}</dd>
            </template>
            <dt class="text-texto-fraco">Evento</dt>
            <dd class="font-mono text-xs leading-5 text-texto">{{ item.evento }}</dd>
            <template v-if="item.ip">
              <dt class="text-texto-fraco">IP</dt>
              <dd class="text-texto">{{ item.ip }}</dd>
            </template>
          </dl>
        </div>
      </li>
    </ul>

    <nav v-if="totalPaginas > 1 && !erro" class="flex items-center justify-between gap-3 border-t border-borda px-4 py-3 sm:px-5" aria-label="Paginação">
      <Botao variante="secundario" tamanho="sm" :desabilitado="pagina <= 1 || carregando" @click="irPara(pagina - 1)">
        <ChevronLeft class="size-4" aria-hidden="true" /> Anterior
      </Botao>
      <p class="text-sm text-texto-suave">Página {{ pagina }} de {{ totalPaginas }}</p>
      <Botao variante="secundario" tamanho="sm" :desabilitado="pagina >= totalPaginas || carregando" @click="irPara(pagina + 1)">
        Próxima <ChevronRight class="size-4" aria-hidden="true" />
      </Botao>
    </nav>
  </div>
</template>
