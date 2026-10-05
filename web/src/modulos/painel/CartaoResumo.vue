<script setup lang="ts">
// Resumo do período (um cartão, duas áreas): à esquerda o medidor do NPS, a faixa e a variação; à direita "O que mudou"
// (manchete por regras, sem IA), até 3 botões e a distribuição detratores/neutros/promotores. Etapa 5h: o botão
// "Criar planos para N empresas" avisa quem chama (`criarPlanos`); no modo exemplo, todos os botões ficam desligados.
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { ClipboardList, Gauge } from 'lucide-vue-next'
import type { GrupoNota, Painel } from '@/api/tipos'
import { plural } from '@/utils/formatos'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import IconeToqqiAI from '@/components/app/IconeToqqiAI.vue'
import Botao from '@/components/ui/Botao.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MedidorNps from './MedidorNps.vue'
import { faixaNps, formatarNps, igualAo, type AcaoManchete, type Manchete } from './logica'

const props = defineProps<{
  nps: Painel['nps']
  variacao: Painel['variacao']
  /** "NPS dos últimos 90 dias". */
  titulo: string
  /** "os 90 dias antes" / "o período anterior". */
  textoAnterior: string
  manchete: Manchete
  acoes: AcaoManchete[]
  linkGrupo?: (g: GrupoNota) => RouteLocationRaw | undefined
  /** Etapa 5h: criando os planos dos detratores (o botão mostra que está carregando). */
  criandoPlanos?: boolean
  /** Etapa 5h, modo exemplo: os botões aparecem, desligados. */
  desativado?: boolean
}>()
const emit = defineEmits<{ perguntar: []; criarPlanos: [] }>()

const faixa = computed(() => faixaNps(props.nps.faixa, props.nps.valor))
const temNps = computed(() => props.nps.total > 0 && typeof props.nps.valor === 'number')
const variacao = computed(() => {
  if (!props.variacao) return null
  const v = Math.round(props.variacao.valor)
  const n = Math.abs(v)
  return {
    direcao: v > 0 ? 'sobe' : v < 0 ? 'desce' : 'igual',
    seta: v > 0 ? '▲' : v < 0 ? '▼' : '=',
    texto: v === 0 ? 'Igual' : `${n} ${n === 1 ? 'ponto' : 'pontos'}`,
    leitura: v === 0 ? 'O NPS ficou igual' : `O NPS ${v > 0 ? 'subiu' : 'caiu'} ${n} ${n === 1 ? 'ponto' : 'pontos'}`,
    anterior: formatarNps(props.variacao.anterior),
  }
})
const decisores = computed(() => props.nps.decisores ?? { valor: null, total: 0 })
/** O primeiro botão (o pico ou, sem pico, os detratores/planos) é o principal; o ToqqiAI tem o seu estilo. */
function variante(i: number): 'primario' | 'secundario' {
  return i === 0 ? 'primario' : 'secundario'
}
</script>

<template>
  <section class="cartao @container overflow-hidden" aria-labelledby="t-resumo">
    <div class="grid grid-cols-1 @3xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
      <!-- O número -->
      <div class="flex flex-col items-center gap-2 border-b border-borda p-5 sm:p-6 @3xl:border-b-0 @3xl:border-r">
        <h2 id="t-resumo" class="self-start text-base font-bold text-texto">{{ titulo }}</h2>
        <template v-if="temNps">
          <MedidorNps :valor="nps.valor as number" :faixa="faixa?.rotulo" class="mt-2" />
          <Etiqueta v-if="faixa" :tom="faixa.tom">{{ faixa.rotulo }}</Etiqueta>
          <p v-if="variacao" class="mt-1 text-center text-sm text-texto-suave" data-variacao>
            <template v-if="variacao.direcao === 'igual'">
              <span class="font-bold text-texto-suave"><span aria-hidden="true">= </span>{{ igualAo(textoAnterior) }}</span> ({{ variacao.anterior }})
            </template>
            <template v-else>
              <span class="font-bold" :class="variacao.direcao === 'sobe' ? 'text-sucesso' : 'text-erro'">
                <span aria-hidden="true">{{ variacao.seta }} </span><span class="sr-only">{{ variacao.leitura }}: </span>{{ variacao.texto }}
              </span>
              sobre {{ textoAnterior }} ({{ variacao.anterior }})
            </template>
          </p>
          <p v-else class="mt-1 text-center text-xs text-texto-fraco">Sem período anterior com NPS para comparar.</p>
        </template>
        <div v-else class="mt-2 flex w-full items-start gap-3 rounded-xl bg-superficie-2 p-4">
          <Gauge class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
          <div class="text-sm">
            <p class="font-semibold text-texto">Nenhuma resposta de NPS neste período</p>
            <p class="text-texto-suave">Escolha um período maior ou envie a pesquisa para mais clientes. O número aparece assim que chegarem respostas.</p>
          </div>
        </div>
      </div>

      <!-- O que mudou -->
      <div class="flex min-w-0 flex-col gap-5 p-5 sm:p-6" :class="manchete.regra === 1 || manchete.regra === 2 ? 'bg-marca-suave/60' : ''">
        <div class="flex flex-col gap-2" data-manchete>
          <p class="text-xs font-bold uppercase tracking-wider text-marca-texto">O que mudou</p>
          <p class="text-lg font-bold leading-snug text-texto sm:text-xl" data-manchete-titulo>
            <template v-for="(p, i) in manchete.titulo" :key="i">
              <span v-if="p.enfase === 'alerta'" class="text-erro">{{ p.texto }}</span>
              <template v-else>{{ p.texto }}</template>
            </template>
          </p>
          <p v-if="manchete.apoio" class="text-sm text-texto-suave sm:text-[0.95rem]" data-manchete-apoio>
            <template v-for="(p, i) in manchete.apoio" :key="i">
              <strong v-if="p.enfase" class="font-bold text-texto">{{ p.texto }}</strong>
              <template v-else>{{ p.texto }}</template>
            </template>
          </p>
          <p v-if="manchete.outrosPicos.length" class="text-xs text-texto-fraco">
            Também com pico de reclamações: {{ manchete.outrosPicos.join(', ') }}.
          </p>
        </div>

        <div v-if="acoes.length" class="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <template v-for="(a, i) in acoes" :key="a.tipo">
            <Botao
              v-if="a.tipo === 'toqqiai'"
              variante="fantasma"
              class="!h-11 bg-marca-suave !text-marca-texto hover:!bg-marca-suave/70"
              :desabilitado="desativado"
              data-toqqiai
              @click="emit('perguntar')"
            >
              <IconeToqqiAI class="size-4" /> {{ a.rotulo }}
            </Botao>
            <Botao
              v-else-if="a.tipo === 'criar_planos'"
              :variante="variante(i)"
              class="!h-11"
              :carregando="criandoPlanos"
              :desabilitado="desativado"
              data-criar-planos
              @click="emit('criarPlanos')"
            >
              <ClipboardList v-if="!criandoPlanos" class="size-4" aria-hidden="true" /> {{ a.rotulo }}
            </Botao>
            <Botao v-else :variante="variante(i)" :para="a.para" :desabilitado="desativado" class="!h-11">{{ a.rotulo }}</Botao>
          </template>
        </div>

        <!-- No celular, cada grupo da legenda é um alvo de 44 px. -->
        <div v-if="nps.total > 0" class="mt-auto flex flex-col gap-2 [&_li>a]:min-h-11 sm:[&_li>a]:min-h-6">
          <BarraGrupos :detratores="nps.detratores" :neutros="nps.neutros" :promotores="nps.promotores" :pct="nps.pct" legenda="compacta" :link-grupo="linkGrupo" />
          <p class="text-right text-xs text-texto-suave">
            {{ plural(nps.total, 'resposta', 'respostas') }} de NPS ·
            <template v-if="decisores.total > 0">
              decisores: <strong class="font-semibold text-texto">{{ formatarNps(decisores.valor) }}</strong>
              <span class="text-texto-fraco"> ({{ plural(decisores.total, 'resposta', 'respostas') }})</span>
            </template>
            <span v-else class="text-texto-fraco">nenhum decisor respondeu</span>
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
