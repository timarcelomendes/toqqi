<script setup lang="ts">
// O topo de Crescimento (docs/api-crescimento-panorama.md): no período escolhido, quanto os clientes felizes trouxeram
// (a "Receita gerada pelo Toqqi", comparada com o período anterior), a trilha do promotor ao cliente, as ofertas, os
// próximos passos, quem mais indica e o depoimento mais recente. Os números que têm lista nas abas levam a ela, já com
// os filtros que dão a mesma conta. Conta sem nenhum promotor, indicação ou oferta: explica como funciona.
// `recarregar` atualiza sem piscar depois de uma mudança nas abas.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { ChevronRight, Minus, TrendingDown, TrendingUp } from 'lucide-vue-next'
import { crescimentoApi, mensagemDoErro, type ConfigCrescimento, type PanoramaCrescimento } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData, hojeIso } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import {
  PERIODOS_PANORAMA,
  PERIODO_PANORAMA_PADRAO,
  barrasMeses,
  detalheMes,
  enderecoDoDestino,
  intervaloPanorama,
  mesCurto,
  mesLongo,
  moedaCurta,
  moedaInteira,
  origemReceita,
  partesReceita,
  periodoAtual,
  proximosPassos,
  quemMaisIndica,
  temMovimento,
  textoNota,
  trilhaIndicacoes,
  trilhaOfertas,
  variacaoReceita,
  type PeriodoPanorama,
} from './panorama'
import { numeroDecimal } from './logica'

const props = defineProps<{
  /** Para saber se o convite de indicação está desligado (null enquanto carrega ou se falhou: aí não fala nisso). */
  config?: ConfigCrescimento | null
}>()
/** Um número ou passo levou a uma aba: a tela rola até a lista. */
const emit = defineEmits<{ irParaLista: [] }>()

const sessao = useSessaoStore()
const podeConfigurar = computed(() => sessao.pode('configuracoes.gerenciar'))
const podeVerEmpresas = computed(() => sessao.pode('contatos.ver'))
const podeEnviar = computed(() => sessao.pode('envios.ver'))

const periodo = ref<PeriodoPanorama>(PERIODO_PANORAMA_PADRAO)
const dados = ref<PanoramaCrescimento | null>(null)
/** O período dos dados na tela (muda junto com eles, não com o clique). */
const periodoDosDados = ref<PeriodoPanorama>(PERIODO_PANORAMA_PADRAO)
const carregando = ref(true)
const atualizando = ref(false)
const erro = ref<string | null>(null)
const anuncio = ref('')
let controle: AbortController | null = null

async function carregar(silencioso = false, anunciar = false) {
  controle?.abort()
  const meu = (controle = new AbortController())
  const p = periodo.value
  if (!silencioso) carregando.value = !dados.value
  atualizando.value = !!dados.value && !silencioso
  erro.value = null
  try {
    const r = await crescimentoApi.panorama(intervaloPanorama(p, hojeIso()), meu.signal)
    dados.value = r
    periodoDosDados.value = p
    if (anunciar) anuncio.value = `Receita gerada pelo Toqqi ${periodoAtual(p)}: ${moedaInteira(r.receita.total)} por mês.`
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    if (!silencioso || !dados.value) erro.value = mensagemDoErro(e)
  } finally {
    if (controle === meu) {
      carregando.value = false
      atualizando.value = false
    }
  }
}

watch(periodo, () => carregar(false, true))
onMounted(() => carregar())
onBeforeUnmount(() => controle?.abort())
defineExpose({ recarregar: () => carregar(true) })

// ── O que a tela mostra ─────────────────────────────────────────────────────
const receita = computed(() => partesReceita(dados.value?.receita.total))
const variacao = computed(() => (dados.value ? variacaoReceita(dados.value, periodoDosDados.value) : null))
const origem = computed(() => (dados.value ? origemReceita(dados.value) : ''))
const movimento = computed(() => !!dados.value && temMovimento(dados.value))
const conviteDesligado = computed(() => props.config?.indicacoes_ativas === false)
const trilhas = computed(() => {
  const p = dados.value
  if (!p) return []
  return [
    { chave: 'indicacoes', titulo: 'Do promotor ao cliente', etapas: trilhaIndicacoes(p, periodoDosDados.value), receita: p.receita.indicacoes },
    { chave: 'ofertas', titulo: 'Ofertas para clientes felizes', etapas: trilhaOfertas(p), receita: p.receita.ofertas },
  ]
})
const passos = computed(() => (dados.value ? proximosPassos(dados.value, { conviteDesligado: conviteDesligado.value, podeConfigurar: podeConfigurar.value }) : []))
const fas = computed(() => (dados.value ? quemMaisIndica(dados.value) : []))
const depoimentos = computed(() => dados.value?.depoimentos ?? null)
const destaque = computed(() => depoimentos.value?.destaque ?? null)
const notaDestaque = computed(() => (destaque.value ? textoNota(destaque.value.nota, destaque.value.tipo_nota) : null))
const barras = computed(() => (dados.value ? barrasMeses(dados.value, periodoDosDados.value, hojeIso()) : []))
const mesAtivo = ref<number | null>(null)
const barraAtiva = computed(() => (mesAtivo.value === null ? null : (barras.value[mesAtivo.value] ?? null)))

const COR_VARIACAO = { subiu: 'text-sucesso', caiu: 'text-atencao', igual: 'text-texto-fraco' } as const
const ICONE_VARIACAO = { subiu: TrendingUp, caiu: TrendingDown, igual: Minus } as const
const temValor = (v: PanoramaCrescimento['receita']['total']) => (numeroDecimal(v) ?? 0) > 0

/** Como funciona (conta que ainda não começou): a trilha, sem números. */
const COMO_FUNCIONA = [
  { titulo: 'O cliente dá nota 9 ou 10', texto: 'e vê, na tela final da pesquisa, o convite para indicar outra empresa.', largura: 100 },
  { titulo: 'A indicação chega aqui', texto: 'com o responsável certo, para a sua equipe fazer o primeiro contato.', largura: 64 },
  { titulo: 'Os clientes felizes recebem uma oferta', texto: 'em Oportunidades, com o texto pronto para o WhatsApp ou o e-mail.', largura: 42 },
  { titulo: 'O que fechar vira receita', texto: 'somada aqui, em reais por mês, e comparada com o período anterior.', largura: 26 },
] as const
</script>

<template>
  <section class="mb-8" aria-labelledby="t-panorama" :aria-busy="carregando || atualizando || undefined" data-panorama>
    <h2 id="t-panorama" class="sr-only">Panorama do crescimento</h2>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>

    <!-- Primeira carga -->
    <div v-if="carregando && !dados" class="cartao p-5 sm:p-8" role="status" aria-label="Carregando o panorama">
      <div class="animate-pulse">
        <div class="h-4 w-44 rounded bg-superficie-2" />
        <div class="mt-4 h-14 w-60 rounded-lg bg-superficie-2" />
        <div class="mt-3 h-4 w-72 max-w-full rounded bg-superficie-2" />
        <div class="mt-10 grid gap-x-12 gap-y-8 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div class="flex flex-col gap-5">
            <div v-for="i in 4" :key="i" class="h-3 rounded bg-superficie-2" :style="{ width: `${104 - i * 18}%` }" />
          </div>
          <div class="flex flex-col gap-5">
            <div v-for="i in 2" :key="i" class="h-3 rounded bg-superficie-2" :style="{ width: `${100 - i * 30}%` }" />
          </div>
        </div>
      </div>
    </div>

    <Alerta v-else-if="erro && !dados" tom="erro">
      Não deu para carregar o panorama: {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
    </Alerta>

    <template v-else-if="dados">
      <!-- Trocar o período falhou: os números de antes ficam, com o aviso -->
      <Alerta v-if="erro" tom="erro" class="mb-4" data-erro-atualizar>
        Não deu para atualizar o panorama: {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
      </Alerta>

      <!-- Conta que ainda não começou: como funciona, em vez de zeros -->
      <div v-if="!dados.tem_historico" class="cartao grid gap-8 p-5 sm:p-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-center lg:gap-12" data-comecar>
        <div>
          <h3 class="text-xl font-bold text-texto sm:text-2xl">Aqui aparece o que seus clientes felizes trazem</h3>
          <p class="mt-2 max-w-xl text-[0.95rem] text-texto-suave">
            As indicações que viram cliente e as ofertas aceitas somam a receita gerada pelo Toqqi. Tudo começa com uma pesquisa respondida com nota
            9 ou 10.
          </p>
          <div v-if="(conviteDesligado && podeConfigurar) || podeEnviar" class="mt-5 flex flex-wrap gap-2">
            <Botao v-if="conviteDesligado && podeConfigurar" para="/configuracoes/crescimento">Ligar o convite de indicação</Botao>
            <Botao v-if="podeEnviar" :variante="conviteDesligado && podeConfigurar ? 'secundario' : 'primario'" para="/envios">Enviar uma pesquisa</Botao>
          </div>
          <p v-if="conviteDesligado && !podeConfigurar" class="mt-4 max-w-xl text-sm text-texto-fraco" data-pedir-admin>
            O convite de indicação está desligado. Peça a um administrador para ligar em Configurações › Crescimento.
          </p>
        </div>
        <ol class="flex flex-col gap-4" aria-label="Como funciona">
          <li v-for="(passo, i) in COMO_FUNCIONA" :key="passo.titulo" class="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3">
            <span
              class="flex size-7 items-center justify-center rounded-full text-xs font-bold"
              :class="i === COMO_FUNCIONA.length - 1 ? 'bg-marca-forte text-white' : 'bg-superficie-2 text-texto-suave'"
              aria-hidden="true"
            >
              {{ i + 1 }}
            </span>
            <div class="min-w-0">
              <p class="text-sm font-semibold text-texto">{{ passo.titulo }}</p>
              <p class="text-sm text-texto-suave">{{ passo.texto }}</p>
              <span
                class="mt-2 block h-2 rounded-r-[4px]"
                :class="i === COMO_FUNCIONA.length - 1 ? 'bg-marca' : 'bg-grafico-cinza/60'"
                :style="{ width: `${passo.largura}%` }"
                aria-hidden="true"
              />
            </div>
          </li>
        </ol>
      </div>

      <template v-else>
        <div class="cartao p-5 transition-opacity sm:p-8" :class="atualizando ? 'opacity-60' : ''" data-panorama-principal>
          <!-- A receita do período e a escolha do período -->
          <div class="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-texto-suave">Receita gerada pelo Toqqi</h3>
              <p class="mt-2 flex flex-wrap items-baseline gap-x-1.5 text-texto" :title="`${moedaInteira(dados.receita.total)} por mês`" data-receita>
                <span class="text-2xl font-bold sm:text-3xl" aria-hidden="true">R$</span>
                <span class="text-[3.25rem] leading-none font-extrabold tracking-tight sm:text-[4rem]" aria-hidden="true">{{ receita.numero }}</span>
                <span v-if="receita.sufixo" class="text-2xl font-bold sm:text-3xl" aria-hidden="true">{{ receita.sufixo }}</span>
                <span class="text-base font-semibold text-texto-fraco" aria-hidden="true">/mês</span>
                <span class="sr-only">{{ moedaInteira(dados.receita.total) }} por mês</span>
              </p>
              <p class="mt-3 max-w-xl text-sm text-texto-suave" data-origem>{{ origem }}</p>
              <p v-if="variacao" class="mt-1 flex items-center gap-1.5 text-sm font-semibold" :class="COR_VARIACAO[variacao.sentido]" data-variacao>
                <component :is="ICONE_VARIACAO[variacao.sentido]" class="size-4 shrink-0" aria-hidden="true" />
                {{ variacao.texto }}
              </p>
            </div>
            <div class="flex shrink-0 flex-col gap-5 sm:w-[17.5rem]">
              <BotoesSegmentados v-model="periodo" :opcoes="PERIODOS_PANORAMA" rotulo="Período do panorama" bloco class="sm:self-end" />
              <!-- Mês a mês (12 meses): em destaque, os meses do período; a dica mostra o valor de cada um -->
              <figure v-if="barras.length" class="m-0" data-meses>
                <div class="relative flex h-16 items-end gap-0.5 border-b border-borda-forte" aria-hidden="true" @pointerleave="mesAtivo = null">
                  <div
                    v-for="(b, i) in barras"
                    :key="b.mes"
                    class="flex h-full flex-1 cursor-default items-end"
                    @pointerenter="mesAtivo = i"
                    @click="mesAtivo = i"
                  >
                    <!-- Mês sem receita: um traço no lugar da barra (a última barra visível não parece o mês de hoje) -->
                    <span
                      class="block w-full origin-bottom animate-subir transition-[opacity,height] duration-300"
                      :style="{ height: b.altura ? `${b.altura}%` : '3px', animationDelay: `${i * 25}ms` }"
                      :class="[
                        b.altura ? (b.noPeriodo ? 'rounded-t-[4px] bg-marca' : 'rounded-t-[4px] bg-grafico-cinza/60') : b.noPeriodo ? 'bg-marca/40' : 'bg-borda-forte',
                        b.atual && b.altura ? 'opacity-60' : '',
                        mesAtivo !== null && mesAtivo !== i ? 'opacity-50' : '',
                      ]"
                      :data-mes="b.mes"
                    />
                  </div>
                  <div
                    v-if="barraAtiva"
                    class="pointer-events-none absolute bottom-full z-10 mb-2 w-max max-w-[15rem] rounded-lg bg-texto px-3 py-2 text-xs text-superficie shadow-cartao"
                    :class="mesAtivo! < 3 ? 'left-0' : mesAtivo! > 8 ? 'right-0' : '-translate-x-1/2'"
                    :style="mesAtivo! >= 3 && mesAtivo! <= 8 ? { left: `${((mesAtivo! + 0.5) / barras.length) * 100}%` } : undefined"
                    data-dica-mes
                  >
                    <span class="block first-letter:uppercase">{{ mesLongo(barraAtiva.mes) }}{{ barraAtiva.atual ? ', até hoje' : '' }}</span>
                    <span class="block text-sm font-bold">{{ moedaInteira(barraAtiva.valor) }}/mês</span>
                    <span v-if="barraAtiva.valor > 0" class="block opacity-80">{{ detalheMes(barraAtiva) }}</span>
                  </div>
                </div>
                <!-- A tabela fica numa caixa sr-only (a tabela não encolhe para 1 px e alargaria a página) -->
                <div class="sr-only">
                  <table>
                    <caption>Receita nova por mês, nos últimos 12 meses</caption>
                    <thead>
                      <tr><th scope="col">Mês</th><th scope="col">Receita nova por mês</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="b in barras" :key="b.mes">
                        <th scope="row">{{ mesLongo(b.mes) }}{{ b.atual ? ' (até hoje)' : '' }}</th>
                        <td>{{ moedaInteira(b.valor) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <figcaption class="mt-1.5 flex items-baseline justify-between gap-2 text-xs text-texto-fraco">
                  <span aria-hidden="true">{{ barras.length ? mesCurto(barras[0]!.mes) : '' }}</span>
                  <span>Receita nova por mês</span>
                  <span aria-hidden="true">{{ barras.length ? mesCurto(barras[barras.length - 1]!.mes) : '' }}</span>
                </figcaption>
              </figure>
            </div>
          </div>

          <!-- As trilhas: o resultado de cada uma em destaque; o resto, apagado -->
          <div v-if="movimento" class="mt-8 grid gap-x-12 gap-y-8 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <section v-for="t in trilhas" :key="t.chave" :aria-labelledby="`t-trilha-${t.chave}`" :data-trilha="t.chave">
              <div class="flex items-baseline justify-between gap-3 border-b border-borda px-2 pb-2">
                <h3 :id="`t-trilha-${t.chave}`" class="text-sm font-semibold text-texto-suave">{{ t.titulo }}</h3>
                <p class="shrink-0 text-sm text-texto-fraco" :title="`${moedaInteira(t.receita)} por mês`" data-receita-trilha>
                  <span class="font-bold" :class="temValor(t.receita) ? 'text-texto' : 'text-texto-fraco'" aria-hidden="true">{{ moedaCurta(numeroDecimal(t.receita) ?? 0) }}</span
                  ><span aria-hidden="true">/mês</span>
                  <span class="sr-only">Receita: {{ moedaInteira(t.receita) }} por mês</span>
                </p>
              </div>
              <ol class="mt-1 grid grid-cols-[minmax(0,1fr)_auto_1rem] gap-x-3 sm:grid-cols-[auto_minmax(0,1fr)_auto_1rem]">
                <li v-for="(e, j) in t.etapas" :key="e.chave" class="col-span-full grid grid-cols-subgrid" :data-etapa="e.chave">
                  <component
                    :is="e.destino ? RouterLink : 'div'"
                    v-bind="e.destino ? { to: enderecoDoDestino(e.destino) } : {}"
                    class="col-span-full grid grid-cols-subgrid items-center gap-y-2 rounded-lg px-2 py-2.5"
                    :class="e.destino ? 'group transition-colors hover:bg-superficie-2' : ''"
                    @click="e.destino && emit('irParaLista')"
                  >
                    <span class="min-w-0">
                      <span class="block text-sm font-semibold text-texto" :class="e.destino ? 'group-hover:underline' : ''">{{ e.rotulo }}</span>
                      <span v-if="e.detalhe" class="block text-xs text-texto-fraco">{{ e.detalhe }}</span>
                    </span>
                    <span class="order-last col-span-full sm:order-none sm:col-span-1" aria-hidden="true">
                      <span
                        class="block h-3 origin-left animate-crescer rounded-r-[4px] transition-[width] duration-500"
                        :class="e.resultado ? 'bg-marca' : 'bg-grafico-cinza dark:bg-grafico-cinza/70'"
                        :style="{ width: `${e.largura}%`, animationDelay: `${150 + j * 90}ms` }"
                        data-barra
                      />
                    </span>
                    <span class="text-right text-xl font-bold tabular-nums text-texto">{{ formatarNumero(e.valor) }}</span>
                    <ChevronRight v-if="e.destino" class="size-4 text-texto-fraco transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                    <span v-else aria-hidden="true" />
                    <span v-if="e.destino" class="sr-only">, ver na lista</span>
                  </component>
                </li>
              </ol>
            </section>
          </div>
          <div v-else class="mt-8 rounded-xl bg-superficie-2 px-5 py-4" data-sem-movimento>
            <p class="text-sm font-semibold text-texto">Nenhum promotor, indicação ou oferta {{ periodoAtual(periodoDosDados) }}.</p>
            <p class="mt-0.5 text-sm text-texto-suave">As trilhas aparecem quando alguém der nota 9 ou 10, indicar outra empresa ou receber uma oferta.</p>
            <Botao v-if="periodoDosDados !== '365'" variante="secundario" tamanho="sm" class="mt-3" @click="periodo = '365'">Ver os últimos 12 meses</Botao>
          </div>

          <!-- Próximos passos -->
          <div v-if="passos.length" class="mt-8 border-t border-borda pt-6" data-proximos-passos>
            <h3 class="text-sm font-semibold text-texto-suave">Próximos passos</h3>
            <ul class="mt-3 grid gap-3 md:grid-cols-3">
              <li v-for="p in passos" :key="p.chave" class="flex">
                <RouterLink
                  :to="enderecoDoDestino(p.destino)"
                  class="group flex w-full flex-col justify-between gap-3 rounded-xl border border-borda p-4 transition-colors hover:border-marca/40 hover:bg-marca-suave"
                  :data-passo="p.chave"
                  @click="'aba' in p.destino && emit('irParaLista')"
                >
                  <span class="text-sm text-texto-suave">
                    <strong v-if="p.quantidade !== null" class="text-lg leading-none font-bold text-texto">{{ formatarNumero(p.quantidade) }}</strong>
                    {{ p.texto }}
                  </span>
                  <span class="inline-flex items-center gap-1 text-sm font-semibold text-marca-texto">
                    {{ p.acao }}
                    <ChevronRight class="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                  </span>
                </RouterLink>
              </li>
            </ul>
          </div>
        </div>

        <!-- Quem mais indica e o depoimento mais recente -->
        <div class="mt-4 grid gap-4 lg:grid-cols-2">
          <section class="cartao p-5 transition-opacity sm:p-6" :class="atualizando ? 'opacity-60' : ''" aria-labelledby="t-fas" data-fas>
            <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 id="t-fas" class="text-sm font-semibold text-texto-suave">Quem mais indica</h3>
              <p v-if="fas.length" class="flex items-center gap-3 text-xs text-texto-fraco" data-legenda>
                <span class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-marca" aria-hidden="true" />Viraram cliente</span>
                <span class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-cinza dark:bg-grafico-cinza/70" aria-hidden="true" />As outras</span>
              </p>
            </div>
            <ol v-if="fas.length" class="mt-4 flex flex-col gap-4">
              <li v-for="f in fas" :key="String(f.id)" data-fa>
                <div class="flex items-baseline justify-between gap-3">
                  <RouterLink v-if="podeVerEmpresas" :to="`/contatos/empresas/${f.id}`" class="min-w-0 truncate rounded-sm text-sm font-semibold text-texto hover:underline">
                    {{ f.nome }}
                  </RouterLink>
                  <span v-else class="min-w-0 truncate text-sm font-semibold text-texto">{{ f.nome }}</span>
                  <span class="shrink-0 text-sm text-texto-suave">
                    <strong class="font-bold text-texto">{{ formatarNumero(f.indicacoes) }}</strong> {{ f.indicacoes === 1 ? 'indicação' : 'indicações' }}
                  </span>
                </div>
                <div class="mt-1.5 flex h-2.5 gap-0.5" :style="{ width: `${f.largura}%` }" aria-hidden="true">
                  <span v-if="f.clientes" class="h-full bg-marca" :class="f.parteClientes >= 100 ? 'rounded-r-[4px]' : ''" :style="{ width: `${f.parteClientes}%` }" />
                  <span v-if="f.parteClientes < 100" class="h-full min-w-0.5 flex-1 rounded-r-[4px] bg-grafico-cinza dark:bg-grafico-cinza/70" />
                </div>
                <p class="mt-1 text-xs text-texto-fraco">{{ f.detalhe }}</p>
              </li>
            </ol>
            <p v-else class="mt-3 max-w-md text-sm text-texto-suave" data-fas-vazio>
              Ninguém indicou outra empresa {{ periodoAtual(periodoDosDados) }}. Quem indicar aparece aqui, com quantas indicações viraram cliente.
            </p>
          </section>

          <section class="cartao flex flex-col p-5 sm:p-6" aria-labelledby="t-depoimento" data-depoimento-destaque>
            <h3 id="t-depoimento" class="text-sm font-semibold text-texto-suave">Depoimento mais recente</h3>
            <figure v-if="destaque" class="mt-3 flex flex-1 flex-col">
              <span class="-mb-3 block h-12 text-[4.5rem] leading-none font-extrabold text-marca select-none" aria-hidden="true">“</span>
              <blockquote class="line-clamp-5 max-w-prose text-lg leading-relaxed font-medium text-texto" :title="destaque.comentario">
                {{ destaque.comentario }}
              </blockquote>
              <figcaption class="mt-3 text-sm">
                <span class="block font-semibold text-texto">{{ destaque.assinatura }}</span>
                <span v-if="notaDestaque || destaque.data_resposta" class="block text-texto-fraco">
                  {{ [notaDestaque, destaque.data_resposta ? `em ${formatarData(destaque.data_resposta)}` : null].filter(Boolean).join(', ') }}
                </span>
              </figcaption>
            </figure>
            <p v-else class="mt-3 max-w-md text-sm text-texto-suave" data-depoimento-vazio>
              Quando um promotor deixa um comentário e autoriza a publicação, o depoimento vem para a sua aprovação. O último aprovado aparece aqui.
            </p>
            <p class="mt-5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <RouterLink :to="{ name: 'crescimento', params: { aba: 'depoimentos' } }" class="link" @click="emit('irParaLista')">Ver os depoimentos</RouterLink>
              <span v-if="depoimentos && depoimentos.aprovados" class="text-texto-fraco">{{ plural(depoimentos.aprovados, 'aprovado', 'aprovados') }}</span>
            </p>
          </section>
        </div>
      </template>
    </template>
  </section>
</template>
