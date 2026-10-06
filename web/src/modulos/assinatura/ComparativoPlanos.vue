<script setup lang="ts">
// Etapa 5k: os planos lado a lado, com tudo o que muda entre eles (preço no ciclo e na forma de pagamento, contatos
// ativos, perguntas ao ToqqiAI, comentários lidos pela IA, WhatsApp automático) e o que todos têm. Aparece também com a
// assinatura vigente, com o plano atual marcado e "Trocar para este" nos outros (no mensal; no anual, a troca é com a
// equipe). No computador, uma tabela; no celular, um cartão por plano.
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'
import type { PlanoAssinatura, TabelaPersonalizado } from '@/api/tipos'
import { formatarMoeda, formatarNumero } from '@/utils/formatos'
import { ajustarContatos, tetoPersonalizado } from '@/utils/precos'
import { equivaleMes, type PlanoExibido } from './logica'
import Botao from '@/components/ui/Botao.vue'

const props = withDefaults(
  defineProps<{
    planos: PlanoExibido[]
    tabela: TabelaPersonalizado
    /** O Personalizado nos números de agora (o contratado, na assinatura; senão os da calculadora); null = fora da tabela. */
    personalizado?: PlanoExibido | null
    /** Plano em uso (coluna marcada). */
    atual?: string | null
    rotuloAtual?: string
    /** Mostra "Trocar para este" nos outros planos. */
    podeTrocar?: boolean
    /** O Personalizado de agora é o contratado (mostra os números dele em vez de "você escolhe"). */
    personalizadoContratado?: boolean
  }>(),
  { personalizado: null, atual: null, rotuloAtual: 'Seu plano', podeTrocar: false, personalizadoContratado: false },
)
const emit = defineEmits<{ trocar: [chave: string] }>()
/** Os números do Personalizado (fora do contratado): a simulação, com o preço e os limites calculados na hora. */
const contatos = defineModel<number>('contatos', { default: 1000 })
const cotaIa = defineModel<number>('cotaIa', { default: 500 })

type Coluna = { chave: string; nome: string; plano: PlanoExibido | null }
const colunas = computed<Coluna[]>(() => [
  ...props.planos.map((p) => ({ chave: String(p.chave), nome: p.nome, plano: p })),
  { chave: 'personalizado', nome: 'Personalizado', plano: props.personalizado },
])
const ciclo = computed(() => props.planos[0]?.ciclo ?? 'mensal')
const periodo = computed(() => (ciclo.value === 'anual' ? 'por ano' : 'por mês'))
const opcoesCota = computed(() => props.tabela.ia.map((p) => ({ valor: p.cota, rotulo: formatarNumero(p.cota) })))
function aoMudarContatos(e: Event) {
  contatos.value = ajustarContatos(Number((e.target as HTMLInputElement).value), props.tabela)
  ;(e.target as HTMLInputElement).value = String(contatos.value)
}
const ehAtual = (c: Coluna) => props.atual === c.chave
const contratado = computed(() => props.personalizadoContratado && props.atual === 'personalizado')

function franquia(v: number | null | undefined): string {
  return v === null || v === undefined ? 'Sem franquia' : `${formatarNumero(v)} por mês`
}
const linhas = computed(() => {
  // Personalizado: sempre calculado com os números de agora (o contratado ou a simulação).
  const pers = props.personalizado
  const contatosPers = pers?.contatos ? formatarNumero(pers.contatos) : '—'
  const cotaPers = pers?.cota_ia ? `${formatarNumero(pers.cota_ia)} por mês` : '—'
  const tetoPers = pers?.contatos ? `${formatarNumero(tetoPersonalizado(pers.contatos))} por mês` : '—'
  const valor = (c: Coluna, f: (p: PlanoAssinatura) => string, pers: string) => (c.chave === 'personalizado' ? pers : c.plano ? f(c.plano) : '—')
  return [
    { rotulo: 'Contatos ativos', valores: colunas.value.map((c) => valor(c, (p) => (p.contatos === null ? 'Sem limite' : formatarNumero(p.contatos)), contatosPers)) },
    {
      rotulo: 'Perguntas ao ToqqiAI',
      dica: 'Também os resumos do Início e os pareceres dos Relatórios.',
      valores: colunas.value.map((c) => valor(c, (p) => (p.ia_cota === undefined ? '—' : `${formatarNumero(p.ia_cota)} por mês`), cotaPers)),
    },
    {
      rotulo: 'Comentários lidos pela IA',
      dica: 'Temas e sentimento de cada resposta, sem gastar a cota do ToqqiAI.',
      valores: colunas.value.map((c) => valor(c, (p) => (p.ia_teto === undefined ? '—' : `${formatarNumero(p.ia_teto)} por mês`), tetoPers)),
    },
    {
      rotulo: 'WhatsApp automático',
      dica: 'Pelo número da sua empresa; a Meta cobra cada mensagem direto da sua conta.',
      valores: colunas.value.map((c) => valor(c, (p) => franquia(p.whatsapp), 'Sem franquia')),
    },
    { rotulo: 'Usuários, envios e formulários', valores: colunas.value.map(() => 'Sem limite') },
  ]
})
const RECURSOS = [
  'Pesquisas NPS e CSAT com a sua marca, por e-mail e WhatsApp',
  'Planos de ação, alertas de pico e resumo semanal',
  'Relatórios, matriz NPS × valor e receita em risco',
  'Crescimento: indicações, ofertas e depoimentos',
  'Integrações, API e webhooks',
]
</script>

<template>
  <div class="flex flex-col gap-4" data-comparativo>
    <!-- Celular: um cartão por plano -->
    <div class="flex flex-col gap-3 md:hidden" data-cartoes-planos>
      <section
        v-for="(c, i) in colunas"
        :key="c.chave"
        class="cartao flex flex-col gap-3 p-4"
        :class="ehAtual(c) ? 'border-marca ring-1 ring-marca' : ''"
        :data-cartao-plano="c.chave"
        :aria-label="c.nome"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="text-base font-bold text-texto">{{ c.nome }}</h3>
            <span v-if="ehAtual(c)" class="whitespace-nowrap rounded-full bg-marca-suave px-2 py-0.5 text-xs font-semibold text-marca-texto">{{ rotuloAtual }}</span>
          </div>
          <p class="shrink-0 text-right">
            <template v-if="c.plano">
              <s v-if="Number(c.plano.cheio) !== Number(c.plano.preco)" class="block text-xs tabular-nums text-texto-fraco">{{ formatarMoeda(c.plano.cheio) }}</s>
              <span class="block font-bold tabular-nums text-texto">{{ formatarMoeda(c.plano.preco) }}</span>
            </template>
            <span class="block text-xs text-texto-suave">{{ periodo }}</span>
          </p>
        </div>
        <div v-if="c.chave === 'personalizado' && !contratado" class="grid grid-cols-2 gap-2" data-simulador>
          <label class="flex flex-col gap-1 text-xs font-semibold text-texto-suave">
            Contatos ativos
            <input type="number" inputmode="numeric" :min="tabela.contatos_min" :max="tabela.contatos_max" :step="tabela.passo" :value="contatos"
                   class="h-9 w-full rounded-lg border border-borda-forte bg-superficie px-2.5 text-sm tabular-nums text-texto focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20"
                   @change="aoMudarContatos" />
          </label>
          <label class="flex flex-col gap-1 text-xs font-semibold text-texto-suave">
            Perguntas ao ToqqiAI
            <select v-model.number="cotaIa" class="h-9 w-full rounded-lg border border-borda-forte bg-superficie px-2 text-sm text-texto focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20">
              <option v-for="o in opcoesCota" :key="o.valor" :value="o.valor">{{ o.rotulo }}</option>
            </select>
          </label>
        </div>
        <dl class="flex flex-col gap-1.5 text-sm">
          <div v-for="l in linhas" :key="l.rotulo" class="flex justify-between gap-3 border-t border-borda pt-1.5">
            <dt class="text-texto-suave">{{ l.rotulo }}</dt>
            <dd class="text-right font-semibold tabular-nums text-texto">{{ l.valores[i] }}</dd>
          </div>
        </dl>
        <Botao
          v-if="podeTrocar && (!ehAtual(c) || c.chave === 'personalizado')"
          variante="secundario"
          tamanho="sm"
          class="self-start"
          :data-trocar-para="c.chave"
          @click="emit('trocar', c.chave)"
        >
          {{ ehAtual(c) ? 'Mudar os números' : 'Trocar para este' }}
        </Botao>
      </section>
    </div>

    <!-- Computador: tabela -->
    <div class="cartao hidden overflow-x-auto p-0 md:block">
      <table class="w-full min-w-[44rem] border-collapse text-sm">
        <caption class="sr-only">Comparação dos planos</caption>
        <thead>
          <tr>
            <th scope="col" class="sticky left-0 z-10 w-48 bg-superficie px-4 py-4 text-left align-bottom text-xs font-semibold uppercase tracking-wide text-texto-fraco">
              Plano
            </th>
            <th
              v-for="c in colunas"
              :key="c.chave"
              scope="col"
              class="px-4 py-4 text-left align-bottom"
              :class="ehAtual(c) ? 'bg-marca-suave/40' : ''"
              :data-coluna="c.chave"
            >
              <span class="flex flex-col gap-1">
                <span class="flex flex-wrap items-center gap-2">
                  <span class="text-base font-bold text-texto">{{ c.nome }}</span>
                  <span v-if="ehAtual(c)" class="whitespace-nowrap rounded-full bg-marca-suave px-2 py-0.5 text-xs font-semibold text-marca-texto">{{ rotuloAtual }}</span>
                </span>
                <template v-if="c.plano">
                  <s v-if="Number(c.plano.cheio) !== Number(c.plano.preco)" class="text-xs tabular-nums text-texto-fraco">{{ formatarMoeda(c.plano.cheio) }}</s>
                  <span class="text-lg font-bold tabular-nums text-texto">{{ formatarMoeda(c.plano.preco) }}</span>
                  <span class="text-xs text-texto-suave">{{ periodo }}<template v-if="equivaleMes(c.plano)"> · {{ equivaleMes(c.plano) }}</template></span>
                </template>
                <span v-if="c.chave === 'personalizado' && !contratado" class="mt-2 flex flex-col gap-1.5" data-simulador>
                  <label class="flex items-center justify-between gap-2 text-xs font-semibold text-texto-suave">
                    Contatos
                    <input type="number" inputmode="numeric" :min="tabela.contatos_min" :max="tabela.contatos_max" :step="tabela.passo" :value="contatos"
                           class="h-8 w-24 rounded-lg border border-borda-forte bg-superficie px-2 text-right text-sm font-normal tabular-nums text-texto focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20"
                           @change="aoMudarContatos" />
                  </label>
                  <label class="flex items-center justify-between gap-2 text-xs font-semibold text-texto-suave">
                    Perguntas
                    <select v-model.number="cotaIa" class="h-8 w-24 rounded-lg border border-borda-forte bg-superficie px-1.5 text-sm font-normal text-texto focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20">
                      <option v-for="o in opcoesCota" :key="o.valor" :value="o.valor">{{ o.rotulo }}</option>
                    </select>
                  </label>
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in linhas" :key="l.rotulo" class="border-t border-borda">
            <th scope="row" class="sticky left-0 z-10 bg-superficie px-4 py-3 text-left align-top font-semibold text-texto">
              {{ l.rotulo }}
              <span v-if="l.dica" class="mt-0.5 block text-xs font-normal text-texto-fraco">{{ l.dica }}</span>
            </th>
            <td v-for="(v, i) in l.valores" :key="i" class="px-4 py-3 align-top tabular-nums text-texto" :class="ehAtual(colunas[i]!) ? 'bg-marca-suave/40 font-semibold' : ''">
              {{ v }}
            </td>
          </tr>
        </tbody>
        <tfoot v-if="podeTrocar">
          <tr class="border-t border-borda">
            <td class="sticky left-0 z-10 bg-superficie px-4 py-3" />
            <td v-for="c in colunas" :key="c.chave" class="px-4 py-3" :class="ehAtual(c) ? 'bg-marca-suave/40' : ''">
              <Botao
                v-if="!ehAtual(c) || c.chave === 'personalizado'"
                variante="secundario"
                tamanho="sm"
                :data-trocar-para="c.chave"
                @click="emit('trocar', c.chave)"
              >
                {{ ehAtual(c) ? 'Mudar os números' : 'Trocar para este' }}
              </Botao>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div class="flex flex-col gap-2 rounded-xl bg-superficie-2 p-4 text-sm">
      <p class="font-semibold text-texto">Em todos os planos</p>
      <ul class="grid gap-x-6 gap-y-1.5 text-texto-suave sm:grid-cols-2">
        <li v-for="r in RECURSOS" :key="r" class="flex items-start gap-2"><Check class="mt-0.5 size-4 shrink-0 text-sucesso" aria-hidden="true" />{{ r }}</li>
      </ul>
    </div>
  </div>
</template>
