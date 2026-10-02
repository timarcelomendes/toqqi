<script setup lang="ts">
// O resumo do topo de Crescimento: nos últimos 90 dias, as indicações (recebidas, viraram cliente e a receita mensal
// vinda delas) e as ofertas (feitas e aceitas). `recarregar` atualiza sem piscar depois de uma mudança na tela.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { MessageCircle, UserPlus } from 'lucide-vue-next'
import { crescimentoApi, mensagemDoErro, type ResumoCrescimento } from '@/api'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import { formatarPct } from '@/modulos/painel/logica'
import { partesMoedaCurta } from '@/modulos/relatorios/logica'
import { numeroDecimal, taxa } from './logica'

const dados = ref<ResumoCrescimento | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
let controle: AbortController | null = null

async function carregar(silencioso = false) {
  controle?.abort()
  controle = new AbortController()
  if (!silencioso) carregando.value = !dados.value
  erro.value = null
  try {
    dados.value = await crescimentoApi.resumo({}, controle.signal)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    if (!silencioso || !dados.value) erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

onMounted(() => carregar())
onBeforeUnmount(() => controle?.abort())
defineExpose({ recarregar: () => carregar(true) })

const ind = computed(() => dados.value?.indicacoes ?? null)
const ofe = computed(() => dados.value?.ofertas ?? null)
const taxaClientes = computed(() => taxa(ind.value?.clientes, ind.value?.recebidas))
const taxaAceitas = computed(() => taxa(ofe.value?.aceitas, ofe.value?.feitas))
const receita = computed(() => numeroDecimal(ind.value?.receita_mensal) ?? 0)
const receitaCurta = computed(() => partesMoedaCurta(receita.value))
const receitaOfertas = computed(() => numeroDecimal(ofe.value?.receita) ?? 0)
</script>

<template>
  <section class="mb-6" aria-labelledby="t-resumo-crescimento" :aria-busy="carregando || undefined">
    <h2 id="t-resumo-crescimento" class="mb-2 text-xs font-semibold uppercase tracking-wide text-texto-fraco">Últimos 90 dias</h2>

    <div v-if="carregando && !dados" class="grid gap-4 lg:grid-cols-[3fr_2fr]" role="status" aria-label="Carregando o resumo">
      <div v-for="i in 2" :key="i" class="cartao h-28 animate-pulse p-5">
        <div class="h-3 w-1/3 rounded bg-superficie-2" />
        <div class="mt-4 h-7 w-2/3 rounded bg-superficie-2" />
      </div>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      Não deu para carregar o resumo: {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
    </Alerta>

    <div v-else-if="ind && ofe" class="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div class="cartao p-4 sm:p-5" role="group" aria-labelledby="t-resumo-indicacoes" data-resumo-indicacoes>
        <h3 id="t-resumo-indicacoes" class="flex items-center gap-2 text-sm font-semibold text-texto-suave">
          <UserPlus class="size-4 text-marca-texto" aria-hidden="true" /> Indicações
        </h3>
        <dl class="mt-3 grid grid-cols-3 gap-3">
          <div class="min-w-0">
            <dt class="text-xs text-texto-fraco">Recebidas</dt>
            <dd class="mt-0.5 text-2xl font-extrabold leading-tight tabular-nums text-texto">{{ formatarNumero(ind.recebidas) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-xs text-texto-fraco">Viraram cliente</dt>
            <dd class="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 leading-tight">
              <span class="text-2xl font-extrabold tabular-nums text-texto">{{ formatarNumero(ind.clientes) }}</span>
              <span v-if="taxaClientes !== null" class="text-xs font-semibold text-texto-fraco">{{ formatarPct(taxaClientes) }}<span class="sr-only"> das recebidas</span></span>
            </dd>
          </div>
          <div class="min-w-0">
            <dt class="text-xs text-texto-fraco">Receita mensal</dt>
            <dd class="mt-0.5 flex items-baseline gap-0.5 font-extrabold leading-tight text-texto" :title="formatarMoeda(receita, 'R$ 0,00')">
              <span class="text-xs font-bold" aria-hidden="true">R$</span>
              <span class="text-2xl tabular-nums" aria-hidden="true">{{ receitaCurta?.numero ?? '0' }}</span>
              <span v-if="receitaCurta?.sufixo" class="text-xs font-bold" aria-hidden="true">{{ receitaCurta.sufixo }}</span>
              <span class="sr-only">{{ formatarMoeda(receita, 'R$ 0,00') }}</span>
            </dd>
          </div>
        </dl>
      </div>

      <div class="cartao p-4 sm:p-5" role="group" aria-labelledby="t-resumo-ofertas" data-resumo-ofertas>
        <h3 id="t-resumo-ofertas" class="flex items-center gap-2 text-sm font-semibold text-texto-suave">
          <MessageCircle class="size-4 text-sucesso" aria-hidden="true" /> Ofertas
        </h3>
        <dl class="mt-3 grid grid-cols-2 gap-3">
          <div class="min-w-0">
            <dt class="text-xs text-texto-fraco">Feitas</dt>
            <dd class="mt-0.5 text-2xl font-extrabold leading-tight tabular-nums text-texto">{{ formatarNumero(ofe.feitas) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-xs text-texto-fraco">Aceitas</dt>
            <dd class="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 leading-tight">
              <span class="text-2xl font-extrabold tabular-nums text-texto">{{ formatarNumero(ofe.aceitas) }}</span>
              <span v-if="taxaAceitas !== null" class="text-xs font-semibold text-texto-fraco">{{ formatarPct(taxaAceitas) }}<span class="sr-only"> das feitas</span></span>
            </dd>
            <dd v-if="receitaOfertas > 0" class="mt-0.5 text-xs text-texto-fraco">{{ formatarMoeda(receitaOfertas) }} em vendas</dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>
