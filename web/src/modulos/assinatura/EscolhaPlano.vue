<script setup lang="ts">
// Os planos para escolher, como rádios nativos (o Tab entra no escolhido e as setas trocam): cartões lado a lado no
// computador (um embaixo do outro no celular) ou linhas (`compacto`, na janela de trocar de plano). Plano que não
// comporta os contatos ativos de hoje fica bloqueado ao assinar; ao trocar, dá para escolher e ver o aviso.
import { useId } from 'vue'
import { Check, CheckCircle2, Circle, UsersRound } from 'lucide-vue-next'
import type { PlanoAssinatura } from '@/api/tipos'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import { RECURSOS_PLANOS, cabeNoPlano, rotuloLimite, textoContratado } from './logica'

const props = withDefaults(
  defineProps<{
    planos: PlanoAssinatura[]
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
  }>(),
  { atual: null, rotuloAtual: 'Plano atual', bloquearSemEspaco: true, desabilitado: false, compacto: false, contratado: null },
)
const escolhido = defineModel<string | null>({ default: null })
/** `porPonteiro`: escolheu com mouse ou toque (com o teclado, a tela não rola sozinha). */
const emit = defineEmits<{ escolheu: [chave: string, porPonteiro: boolean] }>()

const nome = `plano-${useId()}`
const cabe = (p: PlanoAssinatura) => cabeNoPlano(p, props.contatosAtivos)
const bloqueado = (p: PlanoAssinatura) => props.desabilitado || (props.bloquearSemEspaco && !cabe(p))
const contratadoDe = (p: PlanoAssinatura) => (props.atual === p.chave ? textoContratado(props.contratado, p.preco) : null)

let ponteiro = false
function aoApertar() {
  ponteiro = true
}
function aoMudar(chave: string) {
  emit('escolheu', chave, ponteiro)
  ponteiro = false
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
            <span class="block font-bold tabular-nums text-texto">{{ formatarMoeda(p.preco) }}</span>{{ ' ' }}<span class="block text-xs text-texto-fraco">por mês</span>
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
            <span class="flex flex-wrap items-baseline gap-x-1.5">
              <span class="text-2xl font-bold tracking-tight tabular-nums text-texto">{{ formatarMoeda(p.preco) }}</span>{{ ' ' }}<span class="text-sm text-texto-suave">por mês</span>
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
    </div>
  </fieldset>
</template>
