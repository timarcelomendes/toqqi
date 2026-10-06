<script setup lang="ts">
// Os planos para escolher, como rádios nativos (o Tab entra no escolhido e as setas trocam): cartões lado a lado no
// computador (um embaixo do outro no celular) ou linhas (`compacto`, na janela de trocar de plano). Plano que não
// comporta os contatos ativos de hoje fica bloqueado ao assinar; ao trocar, dá para escolher e ver o aviso.
// Etapa 5k: `planos` podem vir com o valor da fatura no ciclo e na forma escolhidos (`PlanoExibido`: preço riscado
// quando há desconto, "por ano" no anual) e, com `personalizado` e `tabela`, o Personalizado entra como mais uma opção,
// com a calculadora (contatos de 100 em 100 e o pacote do ToqqiAI) logo abaixo quando escolhido.
import { computed, useId } from 'vue'
import { Check, CheckCircle2, Circle, SlidersHorizontal, UsersRound } from 'lucide-vue-next'
import type { PlanoAssinatura, TabelaPersonalizado } from '@/api/tipos'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import { ajustarContatos } from '@/utils/precos'
import Selecao from '@/components/ui/Selecao.vue'
import { RECURSOS_PLANOS, cabeNoPlano, equivaleMes, rotuloLimite, textoContratado, type PlanoExibido } from './logica'

type Plano = PlanoAssinatura | PlanoExibido

const props = withDefaults(
  defineProps<{
    planos: Plano[]
    contatosAtivos: number
    /** Nome do grupo para leitores de tela. */
    rotulo: string
    /** Plano em uso, com a etiqueta `rotuloAtual`. */
    atual?: string | null
    rotuloAtual?: string
    bloquearSemEspaco?: boolean
    desabilitado?: boolean
    compacto?: boolean
    /** Etapa 5g: o valor que a conta paga no plano atual (o contratado); diferente do preço de hoje, aparece no cartão. */
    contratado?: PlanoAssinatura['preco'] | null
    /** Etapa 5k: o Personalizado com os números da calculadora (null = fora da tabela) e a tabela dele. */
    personalizado?: Plano | null
    tabela?: TabelaPersonalizado | null
  }>(),
  {
    atual: null, rotuloAtual: 'Plano atual', bloquearSemEspaco: true, desabilitado: false, compacto: false,
    contratado: null, personalizado: null, tabela: null,
  },
)
const escolhido = defineModel<string | null>({ default: null })
const contatos = defineModel<number>('contatos', { default: 1000 })
const cotaIa = defineModel<number>('cotaIa', { default: 500 })
/** `porPonteiro`: escolheu com mouse ou toque (com o teclado, a tela não rola sozinha). */
const emit = defineEmits<{ escolheu: [chave: string, porPonteiro: boolean] }>()

const nome = `plano-${useId()}`
const idContatos = `contatos-${useId()}`
const pacotes = computed(() =>
  (props.tabela?.ia ?? []).map((pacote) => ({
    valor: pacote.cota,
    rotulo: `${formatarNumero(pacote.cota)}${Number(pacote.preco) > 0 ? ` (+ ${formatarMoeda(pacote.preco)} por mês)` : ' (incluídas)'}`,
  })),
)
const cabe = (p: Plano) => cabeNoPlano(p, props.contatosAtivos)
const bloqueado = (p: Plano) => props.desabilitado || (props.bloquearSemEspaco && !cabe(p))
const contratadoDe = (p: Plano) => (props.atual === p.chave ? textoContratado(props.contratado, p.preco) : null)
const periodo = (p: Plano) => ('ciclo' in p && p.ciclo === 'anual' ? 'por ano' : 'por mês')
const riscado = (p: Plano) => ('cheio' in p && Number(p.cheio) !== Number(p.preco) ? p.cheio : null)
const equivale = (p: Plano) => ('ciclo' in p ? equivaleMes(p) : null)
const comPersonalizado = computed(() => !!props.tabela)
const persEscolhido = computed(() => escolhido.value === 'personalizado')

let ponteiro = false
function aoApertar() {
  ponteiro = true
}
function aoMudar(chave: string) {
  emit('escolheu', chave, ponteiro)
  ponteiro = false
}
function aoSairContatos(e: Event) {
  if (!props.tabela) return
  const v = Number((e.target as HTMLInputElement).value)
  contatos.value = ajustarContatos(v, props.tabela)
}
</script>

<template>
  <fieldset class="m-0 min-w-0 border-0 p-0">
    <legend class="sr-only">{{ rotulo }}</legend>
    <div class="grid grid-cols-1 gap-3" :class="compacto ? '' : 'md:grid-cols-3 md:gap-4'">
      <label
        v-for="p in planos"
        :key="p.chave"
        class="relative flex min-w-0"
        :class="bloqueado(p) ? 'cursor-not-allowed' : 'cursor-pointer'"
        :data-plano="p.chave"
        @pointerdown="aoApertar"
      >
        <input
          v-model="escolhido"
          type="radio"
          :name="nome"
          :value="p.chave"
          class="peer sr-only"
          :disabled="bloqueado(p)"
          @change="aoMudar(p.chave)"
        />
        <!-- Linha (janela de trocar de plano) -->
        <span
          v-if="compacto"
          class="flex w-full items-center gap-3 rounded-xl border border-borda bg-superficie px-4 py-3 transition-colors peer-checked:border-marca peer-checked:bg-marca-suave/50 peer-checked:ring-1 peer-checked:ring-marca peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-foco"
          :class="bloqueado(p) ? 'opacity-60' : 'hover:border-borda-forte'"
        >
          <CheckCircle2 v-if="escolhido === p.chave" class="size-5 shrink-0 text-marca" aria-hidden="true" />
          <Circle v-else class="size-5 shrink-0 text-borda-forte" aria-hidden="true" />
          <span class="flex min-w-0 flex-1 flex-col">
            <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span class="font-semibold text-texto">{{ p.nome }}</span>
              <span v-if="atual === p.chave" class="rounded-full bg-superficie-2 px-2 py-0.5 text-xs font-semibold text-texto-suave">{{ rotuloAtual }}</span>
            </span>
            <span class="text-sm text-texto-suave">{{ rotuloLimite(p.contatos) }}</span>
            <span v-if="contratadoDe(p)" class="text-xs text-texto-suave" data-contratado>{{ contratadoDe(p) }}</span>
            <span v-if="!cabe(p)" class="text-xs font-semibold text-atencao">Não comporta os {{ formatarNumero(contatosAtivos) }} contatos ativos de hoje.</span>
          </span>
          <span class="shrink-0 text-right">
            <s v-if="riscado(p)" class="block text-xs tabular-nums text-texto-fraco" data-cheio>{{ formatarMoeda(riscado(p)!) }}</s>
            <span class="block font-bold tabular-nums text-texto">{{ formatarMoeda(p.preco) }}</span>{{ ' ' }}<span class="block text-xs text-texto-fraco">{{ periodo(p) }}</span>
          </span>
        </span>
        <!-- Cartão (bloqueado: o conteúdo esmaece, o motivo continua legível) -->
        <span
          v-else
          class="flex w-full flex-col gap-4 rounded-cartao border border-borda bg-superficie p-5 shadow-cartao transition-colors peer-checked:border-marca peer-checked:ring-1 peer-checked:ring-marca peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-foco"
          :class="bloqueado(p) ? '' : 'hover:border-borda-forte'"
        >
          <span class="flex flex-col gap-4" :class="bloqueado(p) ? 'opacity-60' : ''">
            <span class="flex items-start justify-between gap-3">
              <span class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                <span class="text-base font-bold text-texto">{{ p.nome }}</span>
                <span v-if="atual === p.chave" class="whitespace-nowrap rounded-full bg-marca-suave px-2 py-0.5 text-xs font-semibold text-marca-texto">{{ rotuloAtual }}</span>
              </span>
              <CheckCircle2 v-if="escolhido === p.chave" class="size-6 shrink-0 text-marca" aria-hidden="true" />
              <Circle v-else class="size-6 shrink-0 text-borda-forte" aria-hidden="true" />
            </span>
            <span class="flex flex-col gap-0.5">
              <s v-if="riscado(p)" class="text-sm tabular-nums text-texto-fraco" data-cheio>{{ formatarMoeda(riscado(p)!) }}</s>
              <span class="flex flex-wrap items-baseline gap-x-1.5">
                <span class="text-2xl font-bold tracking-tight tabular-nums text-texto">{{ formatarMoeda(p.preco) }}</span>{{ ' ' }}<span class="text-sm text-texto-suave">{{ periodo(p) }}</span>
              </span>
              <span v-if="equivale(p)" class="text-xs text-texto-suave">{{ equivale(p) }}</span>
            </span>
            <span class="flex flex-col gap-2 text-sm text-texto-suave">
              <span class="flex items-start gap-2"><UsersRound class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />{{ rotuloLimite(p.contatos) }}</span>
              <span class="flex items-start gap-2"><Check class="mt-0.5 size-4 shrink-0 text-sucesso" aria-hidden="true" />{{ RECURSOS_PLANOS }}</span>
            </span>
            <span v-if="contratadoDe(p)" class="text-xs text-texto-suave" data-contratado>{{ contratadoDe(p) }}</span>
          </span>
          <span v-if="!cabe(p)" class="rounded-lg bg-atencao-suave px-3 py-2 text-xs font-semibold text-atencao">
            Você tem {{ formatarNumero(contatosAtivos) }} contatos ativos: este plano permite até {{ formatarNumero(p.contatos ?? 0) }}.{{
              bloqueado(p) && !desabilitado ? ' Desative contatos para escolher este plano.' : ''
            }}
          </span>
        </span>
      </label>

      <!-- Personalizado: mais uma opção do mesmo grupo; a calculadora aparece quando ele está escolhido -->
      <div
        v-if="comPersonalizado"
        class="flex min-w-0 flex-col overflow-hidden border border-borda bg-superficie transition-colors"
        :class="[
          compacto ? 'rounded-xl' : 'rounded-cartao shadow-cartao md:col-span-3',
          persEscolhido ? 'border-marca ring-1 ring-marca' : '',
        ]"
        data-plano="personalizado"
      >
        <label class="relative flex min-w-0" :class="desabilitado ? 'cursor-not-allowed' : 'cursor-pointer'" @pointerdown="aoApertar">
          <input
            v-model="escolhido"
            type="radio"
            :name="nome"
            value="personalizado"
            class="peer sr-only"
            :disabled="desabilitado"
            @change="aoMudar('personalizado')"
          />
          <span
            class="flex w-full items-center gap-3 peer-focus-visible:outline-2 peer-focus-visible:-outline-offset-2 peer-focus-visible:outline-foco"
            :class="[compacto ? 'px-4 py-3' : 'p-5', desabilitado ? 'opacity-60' : '']"
          >
            <CheckCircle2 v-if="persEscolhido" class="shrink-0 text-marca" :class="compacto ? 'size-5' : 'size-6'" aria-hidden="true" />
            <Circle v-else class="shrink-0 text-borda-forte" :class="compacto ? 'size-5' : 'size-6'" aria-hidden="true" />
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="font-bold text-texto" :class="compacto ? 'font-semibold' : 'text-base'">Personalizado</span>
                <span v-if="atual === 'personalizado'" class="whitespace-nowrap rounded-full bg-marca-suave px-2 py-0.5 text-xs font-semibold text-marca-texto">{{ rotuloAtual }}</span>
              </span>
              <span class="text-sm text-texto-suave">Monte o seu: escolha os contatos ativos e as perguntas ao ToqqiAI por mês.</span>
            </span>
            <span v-if="personalizado" class="shrink-0 text-right" data-preco-personalizado>
              <s v-if="riscado(personalizado)" class="block text-xs tabular-nums text-texto-fraco">{{ formatarMoeda(riscado(personalizado)!) }}</s>
              <span class="block font-bold tabular-nums text-texto" :class="compacto ? '' : 'text-xl'">{{ formatarMoeda(personalizado.preco) }}</span>{{ ' ' }}<span class="block text-xs text-texto-fraco">{{ periodo(personalizado) }}</span>
            </span>
            <SlidersHorizontal v-else class="size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
          </span>
        </label>
        <div v-if="persEscolhido && tabela" class="grid grid-cols-1 gap-4 border-t border-borda bg-superficie-2/60 sm:grid-cols-2" :class="compacto ? 'px-4 py-3' : 'px-5 py-4'" data-calculadora>
          <div class="flex flex-col gap-1.5">
            <label :for="idContatos" class="text-sm font-semibold text-texto">Contatos ativos</label>
            <input
              :id="idContatos"
              type="number"
              inputmode="numeric"
              class="h-11 w-full rounded-xl border border-borda-forte bg-superficie px-3.5 text-[0.95rem] tabular-nums text-texto transition-colors focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20 disabled:cursor-not-allowed disabled:bg-superficie-2"
              :min="tabela.contatos_min"
              :max="tabela.contatos_max"
              :step="tabela.passo"
              :value="contatos"
              :disabled="desabilitado"
              :aria-describedby="`${idContatos}-ajuda`"
              @change="aoSairContatos"
            />
            <p :id="`${idContatos}-ajuda`" class="text-xs text-texto-suave">
              De 100 em 100, de {{ formatarNumero(tabela.contatos_min) }} a {{ formatarNumero(tabela.contatos_max) }}. Hoje você tem {{ formatarNumero(contatosAtivos) }}.
            </p>
            <p v-if="personalizado && !cabe(personalizado)" class="text-xs font-semibold text-atencao">Menos que os {{ formatarNumero(contatosAtivos) }} contatos ativos de hoje.</p>
          </div>
          <div class="flex flex-col gap-1.5">
            <Selecao v-model="cotaIa" rotulo="Perguntas ao ToqqiAI por mês" :opcoes="pacotes" :desabilitado="desabilitado" />
            <p class="text-xs text-texto-suave">Quanto mais contatos, mais barato cada 100. WhatsApp automático sem franquia.</p>
          </div>
        </div>
      </div>
    </div>
  </fieldset>
</template>
