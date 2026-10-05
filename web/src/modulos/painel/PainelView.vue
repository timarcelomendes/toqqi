<script setup lang="ts">
// Início para quem tem painel.ver: "como estamos e o que preciso tratar hoje" (painel v2, docs/painel-v2.md).
// De cima para baixo: cabeçalho com filtros em pílulas; primeiros passos em uma linha; Resumo (medidor + O que mudou +
// distribuição); indicadores; evolução de 12 meses + Quem mudou de lado; Do que estão falando + Tom e Palavras;
// Comentários; Empresas; Como ler o painel. Os filtros ficam no endereço (/inicio?periodo=30…).
// Etapa 5h (docs/api-etapa-5h.md §1 e §2): conta sem nenhuma resposta → "Comece por aqui" no lugar do painel; modo
// exemplo (o mesmo painel com `painelExemplo`, links e botões desligados, salvo "Como ler o painel"; ?exemplo=1 abre
// direto nele e sai do endereço); "Criar planos para N empresas" na manchete (POST /acoes/detratores).
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Check, ChevronDown, Download, HelpCircle, LineChart, Table2 } from 'lucide-vue-next'
import { acoesApi, crescimentoApi, mensagemDoErro, painelApi, type CarteiraSaude, type ResumoCrescimento, type FiltrosGeracaoIa, type FiltrosPainel, type GrupoNota, type Id, type Painel } from '@/api'
import { avisar } from '@/composables/avisos'
import { useAssistenteStore } from '@/stores/assistente'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { PERIODOS, erroPeriodoEscolhido, intervaloDoPeriodo, rotuloPeriodo, type PresetPeriodo } from '@/utils/periodo'
import Alerta from '@/components/ui/Alerta.vue'
import Campo from '@/components/ui/Campo.vue'
import ComecePorAqui from '@/modulos/inicio/ComecePorAqui.vue'
import { exemploNaConsulta, semRespostas } from '@/modulos/inicio/logica'
import { usarModoExemplo } from '@/modulos/inicio/modoExemplo'
import AjudaPainel from './AjudaPainel.vue'
import BlocoComentarios from './BlocoComentarios.vue'
import BlocoEmpresas from './BlocoEmpresas.vue'
import BlocoPalavras from './BlocoPalavras.vue'
import BlocoTemas from './BlocoTemas.vue'
import BlocoTom from './BlocoTom.vue'
import CartaoMovimentacao from './CartaoMovimentacao.vue'
import CartaoResumo from './CartaoResumo.vue'
import CartaoResumoIa from './CartaoResumoIa.vue'
import CartaoCarteiraSaude from '@/modulos/saude/CartaoCarteiraSaude.vue'
import CartoesIndicadores from './CartoesIndicadores.vue'
import GraficoEvolucao from './GraficoEvolucao.vue'
import PrimeirosPassos from './PrimeirosPassos.vue'
import ResumoIaExemplo from './ResumoIaExemplo.vue'
import { painelExemplo } from './exemplo'
import {
  FILTROS_PADRAO,
  PERGUNTA_TOQQIAI,
  acoesManchete,
  consultaDosFiltros,
  dataPorExtenso,
  diasNoIntervalo,
  filtrosDaConsulta,
  montarManchete,
  montarPassos,
  mostrarPassos,
  ocultarPassos,
  passosOcultos,
  picosValemParaFiltros,
  textoPeriodoAnterior,
  textoPlanosCriados,
  tituloEvolucao12m,
  tituloNps,
} from './logica'

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const assistente = useAssistenteStore()
const rota = useRoute()
const router = useRouter()

const primeiroNome = computed(() => sessao.usuario?.nome?.split(' ')[0] ?? '')

// ── Modo exemplo (etapa 5h): o estado é do Início (a faixa fica acima de tudo); aqui, os dados ──
const { ativo: modoExemplo, ligar: ligarExemplo, desligar: desligarExemplo } = usarModoExemplo()
const titulo = ref<HTMLElement | null>(null)
const comece = ref<InstanceType<typeof ComecePorAqui> | null>(null)
// ?exemplo=1 abre direto no modo exemplo; o parâmetro sai do endereço (recarregar volta aos dados da conta).
if (exemploNaConsulta(rota.query.exemplo)) {
  ligarExemplo()
  const { exemplo: _exemplo, ...resto } = rota.query
  router.replace({ query: resto }).catch(() => undefined)
}
const saudacao = computed(() => {
  const hora = Number(new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', hour: 'numeric', hour12: false }).format(new Date()))
  return hora < 12 ? 'Bom dia' : hora < 18 ? 'Boa tarde' : 'Boa noite'
})

// ── Filtros (pílulas no cabeçalho; valem para todos os blocos e ficam no endereço) ──
const filtros = reactive(modoExemplo.value ? { ...FILTROS_PADRAO } : filtrosDaConsulta(rota.query))
const hoje = hojeIso()
const hojePorExtenso = dataPorExtenso(hoje)
const rotuloGrupo = computed(() => cadastros.listas.grupos.find((g) => String(g.id) === String(filtros.grupo_id))?.nome ?? 'Todos os grupos')
/** Filtro em forma de pílula: alvo de 44 px, borda forte e o foco visível de sempre. */
const PILULA =
  'inline-flex h-11 cursor-pointer items-center rounded-full border border-borda-forte bg-superficie px-4 text-sm font-semibold text-texto hover:bg-superficie-2'
const rotuloPreset = computed(() => PERIODOS.find((p) => p.valor === filtros.periodo)?.rotulo ?? '')

// Grupo que não existe (endereço velho ou digitado): volta a "Todos os grupos" assim que a lista de grupos chega.
watch(
  () => [cadastros.carregado.grupos, cadastros.listas.grupos.length, filtros.grupo_id] as const,
  ([carregados]) => {
    if (carregados && filtros.grupo_id !== '' && !cadastros.listas.grupos.some((g) => String(g.id) === String(filtros.grupo_id))) filtros.grupo_id = ''
  },
  { immediate: true },
)

// Endereço ↔ filtros: trocar um filtro troca o endereço (sem novo item no histórico); voltar/avançar troca os filtros.
// Roda já na carga: o endereço com valor inválido (período sem datas, datas trocadas, grupo inexistente) é corrigido
// para o que a tela está mostrando. Enquanto as datas escolhidas estão incompletas, o endereço fica no último válido.
const CHAVES_FILTRO = ['periodo', 'de', 'ate', 'grupo_id', 'so_ativos']
const filtrosDoEndereco = (q: typeof rota.query) => JSON.stringify(Object.fromEntries(Object.entries(q).filter(([k]) => CHAVES_FILTRO.includes(k))))
/** O último endereço que esta tela escreveu: ao voltar pelo watcher da rota, não desfaz o que a pessoa está digitando. */
let escrito: string | null = null
watch(
  () => consultaDosFiltros(filtros),
  (q) => {
    if (filtros.periodo === 'personalizado' && erroPeriodoEscolhido(filtros.de, filtros.ate)) return
    const atual = Object.fromEntries(Object.entries(rota.query).filter(([k]) => CHAVES_FILTRO.includes(k)))
    if (JSON.stringify(q) === JSON.stringify(atual)) return
    const outros = Object.fromEntries(Object.entries(rota.query).filter(([k]) => !CHAVES_FILTRO.includes(k) && k !== 'exemplo'))
    escrito = JSON.stringify(q)
    router.replace({ query: { ...outros, ...q } }).catch(() => undefined)
  },
  { deep: true, immediate: true },
)
watch(
  () => rota.query,
  (q) => {
    if (rota.path !== '/inicio') return
    if (escrito !== null && filtrosDoEndereco(q) === escrito) return
    escrito = null
    const novos = filtrosDaConsulta(q)
    if (JSON.stringify(consultaDosFiltros(novos)) !== JSON.stringify(consultaDosFiltros(filtros))) Object.assign(filtros, novos)
  },
)
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
/** Etapa 5d: o resumo da IA é dos mesmos filtros dos números na tela (lê de novo quando eles mudam). */
const filtrosResumo = computed<FiltrosGeracaoIa>(() => {
  const f = filtrosNaTela.value
  return { ...f.intervalo, ...(f.grupo_id !== '' ? { grupo_id: f.grupo_id } : {}), so_ativos: f.so_ativos }
})
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
  if (erroDatas.value) {
    carregando.value = false // nunca fica preso em "Carregando": os campos de data mostram o que falta
    return
  }
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

// ── Modo exemplo e "Comece por aqui" (etapa 5h) ─────────────────────────────
/** O painel na tela: o de exemplo (modo exemplo) ou o da conta. */
const painelTela = computed<Painel | null>(() => (modoExemplo.value ? painelExemplo(hoje) : dados.value))
/** Conta sem nenhuma resposta (a importada conta): "Comece por aqui" no lugar do painel. */
const comecePorAqui = computed(() => !modoExemplo.value && !!dados.value && semRespostas(dados.value.primeiros_passos))
/** Os filtros só com o painel na tela (no exemplo, desligados); não aparecem enquanto o primeiro painel carrega. */
const mostrarFiltros = computed(() => modoExemplo.value || (!!dados.value && !comecePorAqui.value))

watch(modoExemplo, async (ligado) => {
  if (ligado) {
    Object.assign(filtros, { ...FILTROS_PADRAO }) // o exemplo é dos últimos 90 dias, sem grupo, só ativas
    window.scrollTo?.({ top: 0 })
    return
  }
  // de volta aos dados da conta: o foco volta ao botão do exemplo (ou ao título)
  await nextTick()
  if (comece.value) comece.value.focarExemplo()
  else titulo.value?.focus()
})

// ── Primeiros passos ────────────────────────────────────────────────────────
const ocultos = ref(passosOcultos(sessao.conta?.id))
const passos = computed(() => montarPassos(painelTela.value?.primeiros_passos, sessao.pode))
const verPassos = computed(() => !!painelTela.value && mostrarPassos(passos.value, ocultos.value))
const podeReexibirPassos = computed(() => !modoExemplo.value && !!dados.value && ocultos.value && passos.value.some((p) => !p.feito))
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
/** A evolução de 12 meses (painel v2); servidor antigo: a evolução de antes, sem os destaques. */
const evolucao12m = computed(() =>
  Array.isArray(painelTela.value?.evolucao_12m) && painelTela.value!.evolucao_12m.length ? painelTela.value!.evolucao_12m : null,
)
const pontosEvolucao = computed(() => evolucao12m.value ?? painelTela.value?.evolucao ?? [])
const tituloEvolucao = computed(() => (evolucao12m.value ? tituloEvolucao12m(evolucao12m.value[evolucao12m.value.length - 1]?.mes, hoje) : 'Evolução do NPS'))
const temNpsNaEvolucao = computed(() => pontosEvolucao.value.some((p) => typeof p.nps === 'number'))

// ── Resumo: título, período anterior e a manchete ──────────────────────────
const tituloResumo = computed(() => tituloNps(filtrosNaTela.value.periodo, filtrosNaTela.value.rotulo))
const textoAnterior = computed(() => textoPeriodoAnterior(painelTela.value?.periodo?.anterior))
const carteiraSaude = ref<CarteiraSaude | null>(null)

// ── Receita gerada pelo Toqqi (melhoria 6): indicações que viraram cliente e ofertas aceitas no período do painel ──
const gerada = ref<ResumoCrescimento | null>(null)
let controleGerada: AbortController | null = null
watch(
  () => [modoExemplo.value, filtrosNaTela.value.intervalo.de, filtrosNaTela.value.intervalo.ate] as const,
  async ([exemplo, de, ate]) => {
    controleGerada?.abort()
    gerada.value = null
    if (exemplo || !sessao.pode('crescimento.ver')) return
    controleGerada = new AbortController()
    try {
      gerada.value = await crescimentoApi.resumo({ ...(de ? { de } : {}), ...(ate ? { ate } : {}) }, controleGerada.signal)
    } catch {
      gerada.value = null // o cartão só some; o resto do painel segue
    }
  },
  { immediate: true },
)
const entradaManchete = computed(() => {
  const d = painelTela.value
  return d
    ? {
        nps: d.nps,
        variacao: d.variacao,
        diasAnteriores: diasNoIntervalo(d.periodo?.anterior?.de, d.periodo?.anterior?.ate),
        picos: d.picos ?? [],
        // Os picos são da conta inteira nos últimos 7 dias: só valem se o período termina hoje e sem grupo.
        picosValem: picosValemParaFiltros({ ate: filtrosNaTela.value.intervalo.ate, grupo_id: filtrosNaTela.value.grupo_id }, hoje),
        atencao: d.atencao,
        renovacoes: modoExemplo.value ? null : carteiraSaude.value?.renovacoes_em_risco ?? null,
      }
    : null
})
const manchete = computed(() => (entradaManchete.value ? montarManchete(entradaManchete.value) : null))
const acoes = computed(() =>
  entradaManchete.value && manchete.value
    ? acoesManchete(entradaManchete.value, manchete.value, {
        podeVerRespostas: podeVerRespostas.value,
        podeVerAcoes: sessao.pode('acoes.ver'),
        toqqiAI: assistente.disponivel,
        consultaNps: consultaNps.value,
        podeTratarAcoes: sessao.pode('acoes.tratar'),
      })
    : [],
)
function perguntarAoToqqiAI() {
  if (!modoExemplo.value) assistente.abrir(PERGUNTA_TOQQIAI)
}

// ── Planos para os detratores sem plano (etapa 5h): os mesmos filtros dos números na tela ──
const criandoPlanos = ref(false)
async function criarPlanos() {
  if (criandoPlanos.value || modoExemplo.value) return
  criandoPlanos.value = true
  try {
    const r = await acoesApi.criarParaDetratores(filtrosResumo.value)
    if (r.criadas > 0) {
      avisar.sucesso(textoPlanosCriados(r))
      router.push('/planos-de-acao').catch(() => undefined)
    } else {
      avisar.info(textoPlanosCriados(r))
      carregar()
    }
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    criandoPlanos.value = false
  }
}

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
  desligarExemplo() // o modo exemplo não fica salvo: sair do Início volta aos dados da conta
})
</script>

<template>
  <!-- Cabeçalho: data e saudação à esquerda e, na mesma linha (pela base), os filtros em pílulas à direita; exportar e
       ajuda logo abaixo dos filtros, discretos. No celular, tudo empilha. Sem respostas ("Comece por aqui"), só a
       saudação e o convite; no modo exemplo, os filtros aparecem desligados. -->
  <header class="mb-5 grid grid-cols-1 gap-x-6 gap-y-3 sm:mb-6 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-end">
    <div class="min-w-0">
      <p class="text-xs font-semibold uppercase tracking-wider text-texto-fraco">{{ hojePorExtenso }}</p>
      <h1 ref="titulo" tabindex="-1" class="titulo-pagina mt-1 focus:outline-none">{{ saudacao }}, {{ primeiroNome }}!</h1>
      <p v-if="comecePorAqui" class="mt-1.5 max-w-2xl text-[0.95rem] text-texto-suave" data-subtitulo-comece>Em 4 passos você recebe as primeiras respostas.</p>
    </div>
    <section v-if="mostrarFiltros" class="flex flex-wrap items-center gap-2 lg:justify-end" aria-label="Filtros do painel" data-filtros>
      <div class="relative">
        <label for="filtro-periodo" class="sr-only">Período</label>
        <select id="filtro-periodo" v-model="filtros.periodo" :class="[PILULA, 'appearance-none pr-9 disabled:cursor-not-allowed disabled:opacity-60']" :title="rotuloPreset" :disabled="modoExemplo">
          <option v-for="o in PERIODOS" :key="o.valor" :value="o.valor">{{ o.rotulo }}</option>
        </select>
        <ChevronDown class="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" aria-hidden="true" />
      </div>
      <div v-if="cadastros.listas.grupos.length || filtros.grupo_id !== ''" class="relative">
        <label for="filtro-grupo" class="sr-only">Grupo de empresas</label>
        <select
          id="filtro-grupo"
          v-model="filtros.grupo_id"
          :class="[PILULA, 'max-w-56 appearance-none truncate pr-9 disabled:cursor-not-allowed disabled:opacity-60']"
          :title="rotuloGrupo"
          :disabled="modoExemplo"
        >
          <option value="">Todos os grupos</option>
          <option v-for="g in cadastros.listas.grupos" :key="String(g.id)" :value="g.id">{{ g.nome }}</option>
        </select>
        <ChevronDown class="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" aria-hidden="true" />
      </div>
      <button
        type="button"
        :class="[PILULA, 'gap-1.5 disabled:cursor-not-allowed disabled:opacity-60', filtros.so_ativos ? '!border-sucesso/40 !bg-sucesso-suave !text-sucesso' : '']"
        :aria-pressed="filtros.so_ativos"
        :disabled="modoExemplo"
        title="Só empresas ativas"
        @click="filtros.so_ativos = !filtros.so_ativos"
      >
        <Check v-if="filtros.so_ativos" class="size-4" aria-hidden="true" />
        Só ativas<span class="sr-only"> (só empresas ativas)</span>
      </button>
    </section>
    <div v-if="mostrarFiltros" class="-mt-1 flex flex-wrap items-center gap-x-1 lg:col-start-2 lg:justify-end" data-atalhos-cabecalho>
      <button
        v-if="sessao.pode('painel.exportar')"
        type="button"
        class="inline-flex min-h-11 items-center gap-1.5 rounded-full px-2.5 text-[13px] font-semibold sm:min-h-9 text-texto-suave hover:bg-superficie-2 hover:text-texto disabled:cursor-not-allowed disabled:opacity-55"
        :disabled="carregando || baixando || !!erroDatas || modoExemplo"
        :aria-busy="baixando || undefined"
        @click="exportar"
      >
        <Download class="size-4" aria-hidden="true" /> {{ baixando ? 'Exportando…' : 'Exportar CSV' }}
      </button>
      <button
        type="button"
        class="inline-flex min-h-11 items-center gap-1.5 rounded-full px-2.5 text-[13px] font-semibold sm:min-h-9 text-texto-suave hover:bg-superficie-2 hover:text-texto"
        data-como-ler
        @click="abrirAjuda"
      >
        <HelpCircle class="size-4" aria-hidden="true" /> Como ler os números
      </button>
    </div>
  </header>
  <div v-if="filtros.periodo === 'personalizado' && mostrarFiltros && !modoExemplo" class="-mt-1 mb-5 grid grid-cols-2 gap-3 sm:flex sm:justify-end">
    <Campo v-model="filtros.de" rotulo="De" tipo="date" :max="filtros.ate || hoje" class="sm:w-44" :erro="erroDatas && erroDatas.includes('inicial') ? erroDatas : null" />
    <Campo v-model="filtros.ate" rotulo="Até" tipo="date" :min="filtros.de || undefined" :max="hoje" class="sm:w-44" :erro="erroDatas && !erroDatas.includes('inicial') ? erroDatas : null" />
  </div>

  <!-- Primeira carga -->
  <div v-if="carregando && !painelTela" class="flex flex-col gap-4" role="status" aria-label="Carregando o painel">
    <div class="cartao h-72 animate-pulse p-6"><div class="h-3 w-1/4 rounded bg-superficie-2" /><div class="mt-6 h-24 w-1/3 rounded bg-superficie-2" /></div>
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <div v-for="i in 4" :key="i" class="cartao h-28 animate-pulse p-5"><div class="h-3 w-1/2 rounded bg-superficie-2" /></div>
    </div>
    <div class="cartao h-64 animate-pulse" />
    <span class="sr-only">Carregando o painel…</span>
  </div>

  <Alerta v-else-if="erro && !painelTela" tom="erro">
    {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>

  <!-- Etapa 5h: conta sem nenhuma resposta -->
  <ComecePorAqui v-else-if="comecePorAqui" ref="comece" :passos="passos" @exemplo="ligarExemplo" />

  <div
    v-else-if="painelTela"
    class="@container flex flex-col gap-4 pb-28 transition-opacity sm:gap-5"
    :class="atualizando && !modoExemplo ? 'opacity-60' : ''"
    :aria-busy="(atualizando && !modoExemplo) || undefined"
    :data-modo-exemplo="modoExemplo || undefined"
  >
    <Alerta v-if="erro && !modoExemplo" tom="erro">
      Não deu para atualizar com os filtros novos: {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <PrimeirosPassos v-if="verPassos" :passos="passos" @ocultar="esconderPassos" />

    <CartaoResumo
      v-if="manchete"
      :nps="painelTela.nps"
      :variacao="painelTela.variacao"
      :titulo="tituloResumo"
      :texto-anterior="textoAnterior"
      :manchete="manchete"
      :acoes="acoes"
      :link-grupo="modoExemplo ? undefined : linkGrupo"
      :criando-planos="criandoPlanos"
      :desativado="modoExemplo"
      @perguntar="perguntarAoToqqiAI"
      @criar-planos="criarPlanos"
    />
    <ResumoIaExemplo v-if="modoExemplo" :periodo="filtrosNaTela.rotulo" />
    <CartaoResumoIa v-else :filtros="filtrosResumo" :periodo="filtrosNaTela.rotulo" />
    <CartaoCarteiraSaude v-if="!modoExemplo" :grupo-id="filtros.grupo_id" @carregada="carteiraSaude = $event" />

    <CartoesIndicadores :atencao="painelTela.atencao" :gerada="gerada" :csat="painelTela.csat" :taxa="painelTela.taxa_resposta" :desativado="modoExemplo" />

    <div class="grid grid-cols-1 items-start gap-4 sm:gap-5 @4xl:grid-cols-[minmax(0,1fr)_minmax(19.5rem,0.5fr)]">
      <section class="cartao flex min-w-0 flex-col gap-3 p-5 sm:p-6" aria-labelledby="t-evolucao">
        <header class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 id="t-evolucao" class="text-base font-bold text-texto">{{ tituloEvolucao }}</h2>
            <p class="text-sm text-texto-suave">
              <template v-if="evolucao12m">{{ evolucao12m.some((m) => m.no_periodo) && evolucao12m.some((m) => !m.no_periodo) ? 'A faixa marcada com "Período" são os meses do filtro do painel.' : 'Mês a mês.' }}</template>
              <template v-else>Mês a mês{{ filtrosNaTela.periodo === 'tudo' ? ', nos últimos 6 meses com respostas' : '' }}.</template>
            </p>
          </div>
          <button
            v-if="temNpsNaEvolucao"
            type="button"
            class="-mr-2 inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-marca-texto hover:bg-marca-suave disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:bg-transparent"
            :aria-pressed="evolucaoEmTabela"
            :disabled="modoExemplo"
            @click="evolucaoEmTabela = !evolucaoEmTabela"
          >
            <LineChart v-if="evolucaoEmTabela" class="size-4" aria-hidden="true" />
            <Table2 v-else class="size-4" aria-hidden="true" />
            {{ evolucaoEmTabela ? 'Ver gráfico' : 'Ver em tabela' }}
          </button>
        </header>
        <GraficoEvolucao v-if="temNpsNaEvolucao" v-model:tabela="evolucaoEmTabela" :pontos="pontosEvolucao" :destaque="!!evolucao12m" />
        <p v-else class="rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">Ainda não há respostas de NPS para mostrar a evolução.</p>
      </section>
      <CartaoMovimentacao :movimentacao="painelTela.movimentacao" :desativado="modoExemplo" class="min-w-0" />
    </div>

    <div class="grid grid-cols-1 items-start gap-4 sm:gap-5 @4xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <BlocoTemas :temas="painelTela.temas ?? []" :consulta="consultaNps" :pode-ver-respostas="podeVerRespostas && !modoExemplo" class="min-w-0" />
      <div class="flex min-w-0 flex-col gap-4 sm:gap-5">
        <BlocoTom v-if="painelTela.tom" :tom="painelTela.tom" :texto-anterior="textoAnterior" :desativado="modoExemplo" />
        <BlocoPalavras :palavras="painelTela.palavras ?? []" :consulta="consultaRespostas" :pode-ver-respostas="podeVerRespostas && !modoExemplo" />
      </div>
    </div>

    <BlocoComentarios :comentarios="painelTela.comentarios ?? []" :consulta="consultaRespostas" :pode-ver-respostas="podeVerRespostas && !modoExemplo" />
    <BlocoEmpresas :empresas="painelTela.empresas ?? { menor: [], maior: [] }" :consulta="consultaNps" :pode-ver-respostas="podeVerRespostas && !modoExemplo" />

    <AjudaPainel v-model:aberta="ajudaAberta" />
    <p v-if="podeReexibirPassos" class="text-center">
      <button type="button" class="link inline-flex min-h-11 items-center text-sm" @click="mostrarDeNovo">Mostrar primeiros passos</button>
    </p>
  </div>
</template>
