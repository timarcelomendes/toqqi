<script setup lang="ts">
// Início para quem tem painel.ver: "como estamos e o que preciso tratar hoje".
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Download, HelpCircle, LineChart, Table2 } from 'lucide-vue-next'
import { mensagemDoErro, painelApi, type FiltrosPainel, type GrupoNota, type Id, type Painel } from '@/api'
import { avisar } from '@/composables/avisos'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { PERIODOS, erroPeriodoEscolhido, intervaloDoPeriodo, rotuloPeriodo, type PresetPeriodo } from '@/utils/periodo'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Selecao from '@/components/ui/Selecao.vue'
import AjudaPainel from './AjudaPainel.vue'
import BlocoAtencao from './BlocoAtencao.vue'
import BlocoComentarios from './BlocoComentarios.vue'
import BlocoEmpresas from './BlocoEmpresas.vue'
import BlocoPalavras from './BlocoPalavras.vue'
import BlocoTemas from './BlocoTemas.vue'
import CartaoMovimentacao from './CartaoMovimentacao.vue'
import CartaoNps from './CartaoNps.vue'
import CartoesIndicadores from './CartoesIndicadores.vue'
import FaixaPicos from './FaixaPicos.vue'
import GraficoEvolucao from './GraficoEvolucao.vue'
import PrimeirosPassos from './PrimeirosPassos.vue'
import { montarPassos, mostrarPassos, ocultarPassos, passosOcultos } from './logica'

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()

const primeiroNome = computed(() => sessao.usuario?.nome?.split(' ')[0] ?? '')
const saudacao = computed(() => {
  const hora = Number(new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', hour: 'numeric', hour12: false }).format(new Date()))
  return hora < 12 ? 'Bom dia' : hora < 18 ? 'Boa tarde' : 'Boa noite'
})

// ── Filtros (uma linha acima de tudo; valem para todos os blocos) ─────────────
const filtros = reactive({ periodo: '90' as PresetPeriodo, de: '', ate: '', grupo_id: '' as Id | '', so_ativos: true })
const hoje = hojeIso()
// Datas escolhidas à mão: as duas, válidas e na ordem; senão, avisa no campo e não busca de novo.
const erroDatas = computed(() => (filtros.periodo === 'personalizado' ? erroPeriodoEscolhido(filtros.de, filtros.ate) : null))
const intervalo = computed(() => intervaloDoPeriodo(filtros.periodo, { de: filtros.de, ate: filtros.ate }))
const rotulo = computed(() => rotuloPeriodo(filtros.periodo, { de: filtros.de, ate: filtros.ate }))
const consultaApi = computed<FiltrosPainel>(() => ({
  ...intervalo.value,
  ...(filtros.grupo_id !== '' ? { grupo_id: filtros.grupo_id } : {}),
  so_ativos: filtros.so_ativos,
}))

/**
 * Os filtros dos números que estão na tela (o último pedido que deu certo). Títulos dos cartões e atalhos usam
 * estes: enquanto as datas escolhidas estão incompletas ou trocadas, nada mostra um período que não foi buscado.
 */
interface FiltrosNaTela {
  periodo: PresetPeriodo
  rotulo: string
  intervalo: { de?: string; ate?: string }
  grupo_id: Id | ''
  so_ativos: boolean
}
const naTela = ref<FiltrosNaTela | null>(null)
const filtrosNaTela = computed<FiltrosNaTela>(
  () => naTela.value ?? { periodo: filtros.periodo, rotulo: rotulo.value, intervalo: intervalo.value, grupo_id: filtros.grupo_id, so_ativos: filtros.so_ativos },
)
/**
 * Os mesmos filtros na tela Respostas (para os atalhos), para os números baterem: as mesmas datas que o painel
 * pediu, o grupo e "só empresas ativas". Os blocos que só contam NPS levam também tipo_nota=nps.
 */
const consultaRespostas = computed(() => {
  const f = filtrosNaTela.value
  const q: Record<string, string> = {}
  if (f.intervalo.de) q.de = f.intervalo.de
  if (f.intervalo.ate) q.ate = f.intervalo.ate
  if (f.grupo_id !== '') q.grupo_id = String(f.grupo_id)
  if (f.so_ativos) q.so_ativos = 'true'
  return q
})
const consultaNps = computed(() => ({ ...consultaRespostas.value, tipo_nota: 'nps' }))
const podeVerRespostas = computed(() => sessao.pode('respostas.ver'))
function linkGrupo(g: GrupoNota) {
  return podeVerRespostas.value ? { path: '/respostas', query: { ...consultaNps.value, categoria: g } } : undefined
}

// ── Dados ───────────────────────────────────────────────────────────────────
const dados = ref<Painel | null>(null)
const carregando = ref(true)
const atualizando = ref(false)
const erro = ref<string | null>(null)
const baixando = ref(false)
let controle: AbortController | null = null

async function carregar() {
  if (erroDatas.value) return
  controle?.abort()
  controle = new AbortController()
  // Ao trocar filtro, o painel atual continua na tela (mais apagado) até chegar o novo.
  if (dados.value) atualizando.value = true
  else carregando.value = true
  erro.value = null
  const pedido: FiltrosNaTela = {
    periodo: filtros.periodo,
    rotulo: rotulo.value,
    intervalo: { ...intervalo.value },
    grupo_id: filtros.grupo_id,
    so_ativos: filtros.so_ativos,
  }
  try {
    dados.value = await painelApi.obter(consultaApi.value, controle.signal)
    naTela.value = pedido
  } catch (e) {
    if (e instanceof DOMException) return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
    atualizando.value = false
  }
}

// Ao escolher "Escolher as datas", começa com o intervalo que estava na tela (os números não pulam).
watch(
  () => filtros.periodo,
  (novo, antigo) => {
    if (novo !== 'personalizado' || filtros.de || filtros.ate) return
    const r = intervaloDoPeriodo(antigo)
    filtros.de = r.de ?? ''
    filtros.ate = r.ate ?? hoje
  },
)

let atraso: ReturnType<typeof setTimeout> | null = null
watch(consultaApi, () => {
  if (atraso) clearTimeout(atraso)
  atraso = setTimeout(carregar, 250)
}, { deep: true })

async function exportar() {
  if (erroDatas.value) return
  baixando.value = true
  try {
    await painelApi.baixarCsv(consultaApi.value)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}

// ── Primeiros passos ────────────────────────────────────────────────────────
const ocultos = ref(passosOcultos(sessao.conta?.id))
const passos = computed(() => montarPassos(dados.value?.primeiros_passos, sessao.pode))
const verPassos = computed(() => !!dados.value && mostrarPassos(passos.value, ocultos.value))
const podeReexibirPassos = computed(() => !!dados.value && ocultos.value && passos.value.some((p) => !p.feito))
function esconderPassos() {
  ocultos.value = true
  const guardou = ocultarPassos(sessao.conta?.id, true)
  avisar.info(
    guardou
      ? 'Primeiros passos escondidos. Para ver de novo, use "Mostrar primeiros passos" no fim da página.'
      : 'Primeiros passos escondidos até você sair. Seu navegador não deixou guardar essa escolha.',
  )
}
function mostrarDeNovo() {
  ocultos.value = false
  ocultarPassos(sessao.conta?.id, false)
}

const evolucaoEmTabela = ref(false)

// ── Ajuda ───────────────────────────────────────────────────────────────────
const ajudaAberta = ref(false)
async function abrirAjuda() {
  ajudaAberta.value = true
  await nextTick()
  document.getElementById('ajuda-painel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  carregar()
  if (sessao.pode('contatos.ver')) cadastros.garantir(['grupos'])
})
onBeforeUnmount(() => {
  controle?.abort()
  if (atraso) clearTimeout(atraso)
})
</script>

<template>
  <CabecalhoPagina :titulo="`${saudacao}, ${primeiroNome}!`" descricao="Como estão seus clientes e o que precisa de cuidado hoje.">
    <template #acoes>
      <Botao variante="fantasma" @click="abrirAjuda"><HelpCircle class="size-4" aria-hidden="true" /> Como ler os números</Botao>
      <Botao v-if="sessao.pode('painel.exportar')" variante="secundario" :carregando="baixando" :desabilitado="carregando || !!erroDatas" @click="exportar">
        <Download v-if="!baixando" class="size-4" aria-hidden="true" /> Exportar CSV
      </Botao>
    </template>
  </CabecalhoPagina>

  <!-- Filtros: uma linha acima de tudo -->
  <section class="mb-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start" aria-label="Filtros do painel">
    <Selecao v-model="filtros.periodo" rotulo="Período" :opcoes="PERIODOS" class="sm:w-52" />
    <template v-if="filtros.periodo === 'personalizado'">
      <div class="grid grid-cols-2 gap-3 sm:flex sm:gap-3">
        <Campo v-model="filtros.de" rotulo="De" tipo="date" :max="filtros.ate || hoje" class="sm:w-40" :erro="erroDatas && erroDatas.includes('inicial') ? erroDatas : null" />
        <Campo v-model="filtros.ate" rotulo="Até" tipo="date" :min="filtros.de || undefined" :max="hoje" class="sm:w-40" :erro="erroDatas && !erroDatas.includes('inicial') ? erroDatas : null" />
      </div>
    </template>
    <Selecao
      v-if="cadastros.listas.grupos.length || filtros.grupo_id !== ''"
      v-model="filtros.grupo_id"
      rotulo="Grupo de empresas"
      :opcoes="cadastros.listas.grupos.map((g) => ({ valor: g.id, rotulo: g.nome }))"
      vazio="Todos os grupos"
      class="sm:w-56"
    />
    <div class="flex min-h-11 items-center sm:mt-7">
      <Interruptor v-model="filtros.so_ativos" rotulo="Só empresas ativas" class="w-full sm:w-auto sm:gap-3" />
    </div>
  </section>

  <!-- Primeira carga -->
  <div v-if="carregando && !dados" class="grid grid-cols-1 gap-4 sm:grid-cols-3" role="status" aria-label="Carregando o painel">
    <div v-for="i in 6" :key="i" class="cartao h-44 animate-pulse p-6" :class="i === 1 || i === 5 ? 'sm:col-span-3' : i === 6 ? 'hidden' : ''">
      <div class="h-3 w-1/3 rounded bg-superficie-2" />
      <div class="mt-5 h-10 w-1/4 rounded bg-superficie-2" />
      <div class="mt-5 h-3 w-2/3 rounded bg-superficie-2" />
    </div>
    <span class="sr-only">Carregando o painel…</span>
  </div>

  <Alerta v-else-if="erro && !dados" tom="erro">
    {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <div v-else-if="dados" class="flex flex-col gap-4 transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || undefined">
    <Alerta v-if="erro" tom="erro">
      Não deu para atualizar com os filtros novos: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <!-- Picos de reclamação dos últimos 7 dias (não dependem dos filtros da tela) -->
    <FaixaPicos :picos="dados.picos ?? []" :pode-ver-respostas="podeVerRespostas" />

    <PrimeirosPassos v-if="verPassos" :passos="passos" @ocultar="esconderPassos" />

    <CartaoNps :nps="dados.nps" :periodo="filtrosNaTela.rotulo" :link-grupo="linkGrupo" />
    <CartoesIndicadores :variacao="dados.variacao" :periodo="dados.periodo" :csat="dados.csat" :taxa="dados.taxa_resposta" />
    <BlocoAtencao :atencao="dados.atencao" />

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <section class="cartao flex min-w-0 flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-evolucao">
        <header class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 id="t-evolucao" class="text-base font-bold text-texto">Evolução do NPS</h2>
            <p class="text-sm text-texto-suave">Mês a mês{{ filtrosNaTela.periodo === 'tudo' ? ', nos últimos 6 meses com respostas' : '' }}.</p>
          </div>
          <button
            v-if="dados.evolucao?.length"
            type="button"
            class="-mr-2 inline-flex h-10 shrink-0 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto"
            :aria-pressed="evolucaoEmTabela"
            @click="evolucaoEmTabela = !evolucaoEmTabela"
          >
            <LineChart v-if="evolucaoEmTabela" class="size-4" aria-hidden="true" />
            <Table2 v-else class="size-4" aria-hidden="true" />
            {{ evolucaoEmTabela ? 'Ver gráfico' : 'Ver em tabela' }}
          </button>
        </header>
        <GraficoEvolucao v-if="dados.evolucao?.length" v-model:tabela="evolucaoEmTabela" :pontos="dados.evolucao" />
        <p v-else class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">Ainda não há respostas de NPS para mostrar a evolução.</p>
      </section>
      <BlocoTemas :temas="dados.temas ?? []" :consulta="consultaNps" :pode-ver-respostas="podeVerRespostas" class="min-w-0" />
    </div>

    <div class="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
      <CartaoMovimentacao :movimentacao="dados.movimentacao" class="min-w-0" />
      <BlocoPalavras :palavras="dados.palavras ?? []" :consulta="consultaRespostas" :pode-ver-respostas="podeVerRespostas" class="min-w-0" />
    </div>

    <BlocoComentarios :comentarios="dados.comentarios ?? []" :consulta="consultaRespostas" :pode-ver-respostas="podeVerRespostas" />
    <BlocoEmpresas :empresas="dados.empresas ?? { menor: [], maior: [] }" :consulta="consultaNps" :pode-ver-respostas="podeVerRespostas" />

    <AjudaPainel v-model:aberta="ajudaAberta" />
    <p v-if="podeReexibirPassos" class="text-center">
      <button type="button" class="link inline-flex min-h-10 items-center text-sm" @click="mostrarDeNovo">Mostrar primeiros passos</button>
    </p>
  </div>
</template>
