<script setup lang="ts">
// Planos de ação: quadro A fazer → Em andamento → Concluído. Arrastar entre colunas (mouse) ou "Mover para…"
// (teclado e toque); no celular, uma coluna por vez. /planos-de-acao/:id abre o painel da ação.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AlertTriangle, CheckCircle2, ClipboardList, Plus, Search, Settings, SlidersHorizontal } from 'lucide-vue-next'
import { ApiError, acoesApi, empresasApi, mensagemDoErro, type Acao, type Id, type QuadroAcoes, type Referencia, type SituacaoAcao } from '@/api'
import { avisar } from '@/composables/avisos'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import { PERIODOS, erroPeriodoEscolhido, intervaloDoPeriodo } from '@/utils/periodo'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Selecao from '@/components/ui/Selecao.vue'
import CampoEmpresa from '@/modulos/contatos/CampoEmpresa.vue'
import CartaoAcao from './CartaoAcao.vue'
import ModalConcluidas from './ModalConcluidas.vue'
import ModalNovaAcao from './ModalNovaAcao.vue'
import PainelAcao from './PainelAcao.vue'
import {
  COLUNAS,
  FILTROS_QUADRO_PADRAO,
  LIMITE_BUSCA,
  LIMITE_CONCLUIDAS,
  acharNoQuadro,
  colocarNoQuadro,
  comNovaSituacao,
  contarFiltrosQuadro,
  filtrosQuadroDaQuery,
  filtrosQuadroParaApi,
  moverNoQuadro,
  normalizarQuadro,
  podeMover,
  quadroVazio,
  queryDosFiltrosQuadro,
  removerDoQuadro,
  type FiltrosQuadro,
} from './logica'
import { CATEGORIAS, categoriasDoTipo } from '@/modulos/respostas/logica'

const rota = useRoute()
const router = useRouter()
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const podeTratar = computed(() => sessao.pode('acoes.tratar'))
const hoje = hojeIso()

// ── Filtros ↔ endereço ──────────────────────────────────────────────────────
const filtros = reactive<FiltrosQuadro>(filtrosQuadroDaQuery(rota.query as Record<string, string>))
const busca = ref(filtros.busca)
const filtrosAbertos = ref(contarFiltrosQuadro(filtros) > 0)
const qtdFiltros = computed(() => contarFiltrosQuadro(filtros))
// Datas escolhidas à mão: as duas, válidas e na ordem; senão, avisa no campo e não busca de novo.
const erroDatas = computed(() => (filtros.periodo === 'personalizado' ? erroPeriodoEscolhido(filtros.de, filtros.ate) : null))
const filtrosApi = computed(() => filtrosQuadroParaApi(filtros, hoje))
const temFiltro = computed(() => qtdFiltros.value > 0 || !!filtros.busca || filtros.so_vencidas)

function escreverEndereco() {
  const q = queryDosFiltrosQuadro(filtros)
  if (JSON.stringify(q) !== JSON.stringify(queryDosFiltrosQuadro(filtrosQuadroDaQuery(rota.query as Record<string, string>))) || Object.keys(rota.query).length !== Object.keys(q).length) {
    router.replace({ name: 'planos-de-acao', params: rota.params, query: q })
  }
}
watch(
  () => rota.query,
  (q) => {
    if (rota.name !== 'planos-de-acao') return
    const novo = filtrosQuadroDaQuery(q as Record<string, string>)
    if (JSON.stringify(queryDosFiltrosQuadro(novo)) !== JSON.stringify(queryDosFiltrosQuadro(filtros))) {
      Object.assign(filtros, novo)
      busca.value = novo.busca
    }
  },
)
let atrasoBusca: ReturnType<typeof setTimeout> | null = null
watch(busca, (v) => {
  if (atrasoBusca) clearTimeout(atrasoBusca)
  atrasoBusca = setTimeout(() => (filtros.busca = v.trim().slice(0, LIMITE_BUSCA)), 300)
})
watch(
  () => filtros.periodo,
  (novo, antigo) => {
    if (novo !== 'personalizado' || filtros.de || filtros.ate) return
    const r = intervaloDoPeriodo(antigo, {}, hoje)
    filtros.de = r.de ?? ''
    filtros.ate = r.ate ?? hoje
  },
)
watch(
  () => JSON.stringify(queryDosFiltrosQuadro(filtros)),
  () => {
    escreverEndereco()
    carregar()
  },
)

function limparFiltros() {
  Object.assign(filtros, { ...FILTROS_QUADRO_PADRAO, busca: filtros.busca, so_vencidas: filtros.so_vencidas })
}
function limparTudo() {
  busca.value = ''
  Object.assign(filtros, { ...FILTROS_QUADRO_PADRAO })
}

const nomesEmpresas = reactive<Record<string, string>>({})
const empresaFiltro = computed<Referencia | null>({
  get: () => (filtros.empresa_id === '' ? null : { id: filtros.empresa_id, nome: nomesEmpresas[String(filtros.empresa_id)] ?? 'Empresa escolhida' }),
  set: (v) => {
    if (v) nomesEmpresas[String(v.id)] = v.nome
    filtros.empresa_id = v?.id ?? ''
  },
})
async function descobrirEmpresa() {
  const e = filtros.empresa_id
  if (e === '' || nomesEmpresas[String(e)]) return
  const todas = [...quadro.value.colunas.a_fazer, ...quadro.value.colunas.em_andamento, ...quadro.value.colunas.concluida]
  const daLista = todas.find((a) => String(a.empresa?.id) === String(e))?.empresa?.nome
  if (daLista) nomesEmpresas[String(e)] = daLista
  else if (sessao.pode('contatos.ver')) {
    try {
      nomesEmpresas[String(e)] = (await empresasApi.obter(e)).nome
    } catch {
      /* fica "Empresa escolhida" */
    }
  }
}

/** Grupos e responsáveis vêm de listas que pedem contatos.ver (sem ela, nada de chamar a API). */
const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))
function comAtual(opcoes: { valor: Id; rotulo: string }[], atual: Id | '', rotulo: string) {
  if (atual !== '' && !opcoes.some((o) => String(o.valor) === String(atual))) opcoes.push({ valor: atual, rotulo })
  return opcoes
}
const opcoesResponsavel = computed(() =>
  comAtual(
    [{ valor: '0' as Id, rotulo: 'Sem responsável' }, ...cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome }))],
    filtros.responsavel_id,
    'Responsável escolhido',
  ),
)
const opcoesGrupo = computed(() => comAtual(cadastros.listas.grupos.map((g) => ({ valor: g.id, rotulo: g.nome })), filtros.grupo_id, 'Grupo escolhido'))
// As mesmas categorias da tela Respostas, só as que existem no tipo escolhido.
const opcoesCategoria = computed(() => categoriasDoTipo(filtros.tipo_nota).map((g) => ({ valor: g, rotulo: CATEGORIAS[g].plural })))
const opcoesTipo = [
  { valor: 'nps' as const, rotulo: 'NPS (0 a 10)' },
  { valor: 'csat' as const, rotulo: 'CSAT (1 a 5)' },
]
// Tipo e categoria precisam combinar (ex.: CSAT não tem "detrator").
watch(
  () => filtros.tipo_nota,
  (t) => {
    if (filtros.categoria && !categoriasDoTipo(t).includes(filtros.categoria)) filtros.categoria = ''
  },
)

// ── Quadro ──────────────────────────────────────────────────────────────────
const quadro = ref<QuadroAcoes>(quadroVazio())
const carregando = ref(true)
const atualizando = ref(false)
const erro = ref<string | null>(null)
const ocupados = reactive(new Set<string>())
const anuncio = ref('')
let controle: AbortController | null = null
let recarga: ReturnType<typeof setTimeout> | null = null
let carregouUmaVez = false

async function carregar(silencioso = false) {
  if (erroDatas.value) {
    carregando.value = false
    return
  }
  controle?.abort()
  controle = new AbortController()
  if (carregouUmaVez) atualizando.value = !silencioso
  else carregando.value = true
  erro.value = null
  try {
    quadro.value = normalizarQuadro(await acoesApi.quadro(filtrosApi.value, controle.signal), hoje)
    carregouUmaVez = true
    descobrirEmpresa()
  } catch (e) {
    if (e instanceof DOMException) return
    if (!silencioso) erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
    atualizando.value = false
  }
}

/** Depois de mexer, confere com o servidor sem piscar (os filtros podem tirar a ação do quadro). */
function agendarRecarga() {
  if (recarga) clearTimeout(recarga)
  recarga = setTimeout(() => {
    if (!ocupados.size) carregar(true)
  }, 800)
}

const totalNoQuadro = computed(() => COLUNAS.reduce((n, c) => n + quadro.value.colunas[c.situacao].length, 0))
const totais = computed(() => quadro.value.totais)

// ── Celular: uma coluna por vez ─────────────────────────────────────────────
const colunaAtiva = ref<SituacaoAcao>('a_fazer')
const telaLarga = ref(false)
let consulta: MediaQueryList | null = null
const aoMudarTela = (e: MediaQueryListEvent) => (telaLarga.value = e.matches)

function aoTeclarAbas(e: KeyboardEvent) {
  const i = COLUNAS.findIndex((c) => c.situacao === colunaAtiva.value)
  const n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? COLUNAS.length - 1 : null
  if (n === null) return
  e.preventDefault()
  const alvo = COLUNAS[(n + COLUNAS.length) % COLUNAS.length]!
  colunaAtiva.value = alvo.situacao
  document.getElementById(`aba-coluna-${alvo.situacao}`)?.focus()
}

// ── Mover ───────────────────────────────────────────────────────────────────
const tituloColuna = (s: SituacaoAcao) => COLUNAS.find((c) => c.situacao === s)?.titulo ?? s

/**
 * Depois de mover, o foco do teclado não pode cair no nada (o cartão saiu da coluna).
 * No computador, vai para o cartão na coluna nova. No celular (uma coluna por vez), fica na coluna em que a
 * pessoa estava: no cartão que ocupou o lugar dele ou, se a coluna ficou vazia, na aba da coluna de destino.
 */
async function focarDepoisDeMover(id: Id, de: SituacaoAcao, para: SituacaoAcao, posicao: number) {
  await nextTick()
  const botaoDoCartao = (s: SituacaoAcao) => Array.from(document.querySelectorAll<HTMLElement>(`#coluna-${s} [data-acao] h3 button`))
  if (telaLarga.value) {
    botaoDoCartao(para).find((b) => b.closest('[data-acao]')?.getAttribute('data-acao') === String(id))?.focus()
    return
  }
  const restantes = botaoDoCartao(de)
  const proximo = restantes[Math.min(posicao, restantes.length - 1)]
  if (proximo) proximo.focus()
  else document.getElementById(`aba-coluna-${para}`)?.focus()
}

/**
 * A ação mudou em outro lugar (o servidor recusou a mudança): busca de novo e atualiza o cartão e o painel,
 * para a próxima tentativa já partir do que vale. Se ela não existe mais, sai do quadro.
 */
async function recarregarAcao(a: Acao): Promise<Acao | null> {
  try {
    const atual = await acoesApi.obter(a.id)
    quadro.value = colocarNoQuadro(quadro.value, atual, acharNoQuadro(quadro.value, a.id) ?? a, hoje)
    if (acaoAberta.value && String(acaoAberta.value.id) === String(a.id)) acaoAberta.value = atual
    return atual
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      quadro.value = removerDoQuadro(quadro.value, a.id, a, hoje)
      avisar.atencao('Essa ação não existe mais. Ela pode ter sido excluída.')
      return null
    }
    return a
  }
}

async function mover(a: Acao, para: SituacaoAcao) {
  if (a.situacao === para || ocupados.has(String(a.id))) return
  const pode = podeMover(a, para)
  if (!pode.ok) {
    abrir(a, { concluir: true })
    anuncio.value = 'Para concluir, falta escolher o responsável ou contar o que foi feito.'
    return
  }
  const de = a.situacao
  const posicao = quadro.value.colunas[de].findIndex((x) => String(x.id) === String(a.id))
  const otimista = comNovaSituacao(a, para, new Date().toISOString(), hoje)
  quadro.value = moverNoQuadro(quadro.value, a.id, para, otimista.concluida_em ?? undefined, hoje)
  ocupados.add(String(a.id))
  // No computador, o aviso para leitor de tela sai daqui; no celular, o aviso na tela (também lido) diz o mesmo.
  if (telaLarga.value) anuncio.value = `Ação movida para ${tituloColuna(para)}: ${a.titulo}.`
  void focarDepoisDeMover(a.id, de, para, Math.max(0, posicao))
  try {
    const r = await acoesApi.atualizar(a.id, { situacao: para })
    quadro.value = colocarNoQuadro(quadro.value, r, acharNoQuadro(quadro.value, a.id) ?? otimista, hoje)
    if (!telaLarga.value) avisar.sucesso(`Ação movida para ${tituloColuna(para)}.`)
    agendarRecarga()
  } catch (e) {
    // Volta a ação para onde estava e busca de novo: ela pode ter mudado em outra sessão
    // (ex.: o responsável foi removido), e o cartão e o painel não podem ficar com dados velhos.
    quadro.value = colocarNoQuadro(quadro.value, a, acharNoQuadro(quadro.value, a.id) ?? otimista, hoje)
    anuncio.value = `Não deu para mover “${a.titulo}”. Ela continua em ${tituloColuna(de)}.`
    const atual = e instanceof ApiError && e.status !== 0 ? await recarregarAcao(a) : a
    if (!atual) return
    if (e instanceof ApiError && e.status === 422 && para === 'concluida' && Object.keys(e.campos).length) abrir(atual, { concluir: true, erros: e.campos })
    else avisar.erro(mensagemDoErro(e))
  } finally {
    ocupados.delete(String(a.id))
  }
}

// Arrastar e soltar (mouse). O teclado e o toque usam o menu "Mover".
const arrastada = ref<Acao | null>(null)
const colunaAlvo = ref<SituacaoAcao | null>(null)
function aoArrastar(a: Acao) {
  arrastada.value = a
}
function aoTerminarArraste() {
  arrastada.value = null
  colunaAlvo.value = null
}
function aoPassarPorCima(e: DragEvent, s: SituacaoAcao) {
  if (!arrastada.value) return
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = arrastada.value.situacao === s ? 'none' : 'move'
  colunaAlvo.value = s
}
function aoSair(e: DragEvent, s: SituacaoAcao) {
  const dentro = e.relatedTarget instanceof Node && (e.currentTarget as HTMLElement).contains(e.relatedTarget)
  if (!dentro && colunaAlvo.value === s) colunaAlvo.value = null
}
function aoSoltar(e: DragEvent, s: SituacaoAcao) {
  e.preventDefault()
  const a = arrastada.value
  aoTerminarArraste()
  if (a) mover(a, s)
}

// ── Painel da ação (/planos-de-acao/:id) ────────────────────────────────────
const idAberto = computed(() => {
  const id = rota.params.id
  const s = Array.isArray(id) ? id[0] : id
  return typeof s === 'string' && s ? s : null
})
const acaoAberta = ref<Acao | null>(null)
const carregandoAcao = ref(false)
const erroAcao = ref<string | null>(null)
const concluirPendente = ref(false)
const errosMover = ref<Record<string, string> | null>(null)

watch(
  idAberto,
  async (id) => {
    if (!id) {
      acaoAberta.value = null
      concluirPendente.value = false
      errosMover.value = null
      return
    }
    const noQuadro = acharNoQuadro(quadro.value, id)
    if (noQuadro) {
      acaoAberta.value = noQuadro
      return
    }
    carregandoAcao.value = true
    erroAcao.value = null
    acaoAberta.value = null
    try {
      const a = await acoesApi.obter(id)
      if (idAberto.value === id) acaoAberta.value = a
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        avisar.atencao('Essa ação não existe mais. Ela pode ter sido excluída.')
        fecharPainel()
      } else erroAcao.value = mensagemDoErro(e)
    } finally {
      carregandoAcao.value = false
    }
  },
  { immediate: true },
)

function abrir(a: Acao, opcoes: { concluir?: boolean; erros?: Record<string, string> } = {}) {
  concluirPendente.value = !!opcoes.concluir
  errosMover.value = opcoes.erros ?? null
  acaoAberta.value = a
  router.replace({ name: 'planos-de-acao', params: { id: String(a.id) }, query: rota.query })
}
function fecharPainel() {
  concluirPendente.value = false
  errosMover.value = null
  router.replace({ name: 'planos-de-acao', params: {}, query: rota.query })
}
function aoSalvar(r: Acao, anterior: Acao) {
  quadro.value = colocarNoQuadro(quadro.value, r, anterior, hoje)
  acaoAberta.value = r
  const mudouSituacao = r.situacao !== anterior.situacao
  concluirPendente.value = false
  errosMover.value = null
  agendarRecarga()
  if (mudouSituacao) fecharPainel()
}
/** O painel buscou a ação de novo depois de um erro: o cartão acompanha. */
function aoRecarregar(nova: Acao) {
  const noQuadro = acharNoQuadro(quadro.value, nova.id)
  if (noQuadro) quadro.value = colocarNoQuadro(quadro.value, nova, noQuadro, hoje)
  acaoAberta.value = nova
}
function aoExcluir(a: Acao) {
  quadro.value = removerDoQuadro(quadro.value, a.id, a, hoje)
  fecharPainel()
  agendarRecarga()
}

// ── Nova ação ───────────────────────────────────────────────────────────────
const novaAberta = ref(false)
const concluidasAbertas = ref(false)
function aoCriar(a: Acao) {
  quadro.value = colocarNoQuadro(quadro.value, a, null, hoje)
  colunaAtiva.value = a.situacao
  agendarRecarga()
}

onMounted(() => {
  carregar()
  if (sessao.pode('contatos.ver')) cadastros.garantir(['grupos', 'responsaveis'])
  if (typeof window.matchMedia === 'function') {
    consulta = window.matchMedia('(min-width: 768px)')
    telaLarga.value = consulta.matches
    consulta.addEventListener?.('change', aoMudarTela)
  }
})
onBeforeUnmount(() => {
  controle?.abort()
  if (atrasoBusca) clearTimeout(atrasoBusca)
  if (recarga) clearTimeout(recarga)
  consulta?.removeEventListener?.('change', aoMudarTela)
})
</script>

<template>
  <CabecalhoPagina titulo="Planos de ação" descricao="O que fazer com cada cliente que precisa de atenção, de “a fazer” até “concluído”.">
    <template #acoes>
      <Botao variante="fantasma" para="/configuracoes/acoes"><Settings class="size-4" aria-hidden="true" /> Prazos automáticos</Botao>
      <Botao v-if="podeTratar" @click="novaAberta = true"><Plus class="size-4" aria-hidden="true" /> Nova ação</Botao>
    </template>
  </CabecalhoPagina>

  <!-- Filtros -->
  <section class="cartao mb-5 flex flex-col gap-3 p-4 sm:px-5" aria-label="Filtros das ações">
    <div class="flex flex-col gap-3 md:flex-row md:items-center">
      <Campo v-model="busca" rotulo="Buscar ações" rotulo-oculto tipo="search" :maxlength="LIMITE_BUSCA" placeholder="Título, empresa ou contato" class="md:max-w-sm md:flex-1">
        <template #antes><Search class="size-4" aria-hidden="true" /></template>
      </Campo>
      <div class="flex flex-wrap items-center gap-2 md:ml-auto">
        <button
          type="button"
          class="inline-flex h-11 items-center gap-1.5 rounded-xl border px-3.5 text-sm font-semibold transition-colors"
          :class="filtros.so_vencidas ? 'border-erro bg-erro-suave text-erro' : 'border-borda-forte text-texto hover:bg-superficie-2'"
          :aria-pressed="filtros.so_vencidas"
          @click="filtros.so_vencidas = !filtros.so_vencidas"
        >
          <AlertTriangle class="size-4" aria-hidden="true" /> Só vencidas
          <span v-if="totais.vencidas && !filtros.so_vencidas" class="rounded-full bg-erro-suave px-1.5 text-xs text-erro">{{ formatarNumero(totais.vencidas) }}</span>
        </button>
        <Botao variante="secundario" class="!h-11" :aria-expanded="filtrosAbertos" aria-controls="filtros-acoes" @click="filtrosAbertos = !filtrosAbertos">
          <SlidersHorizontal class="size-4" aria-hidden="true" /> Filtros
          <span v-if="qtdFiltros" class="rounded-full bg-marca-forte px-1.5 text-xs text-white">{{ qtdFiltros }}</span>
        </Botao>
      </div>
    </div>
    <div v-show="filtrosAbertos" id="filtros-acoes" class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Selecao v-model="filtros.categoria" rotulo="Categoria da nota" :opcoes="opcoesCategoria" vazio="Todas" />
      <Selecao v-model="filtros.tipo_nota" rotulo="Tipo de pesquisa" :opcoes="opcoesTipo" vazio="NPS e CSAT" />
      <Selecao v-model="filtros.responsavel_id" rotulo="Responsável" :opcoes="opcoesResponsavel" vazio="Todos" />
      <CampoEmpresa v-model="empresaFiltro" rotulo="Empresa" placeholder="Todas" />
      <Selecao
        v-if="podeVerCadastros || filtros.grupo_id !== ''"
        v-model="filtros.grupo_id"
        rotulo="Grupo de empresas"
        :opcoes="opcoesGrupo"
        vazio="Todos"
        :dica="podeVerCadastros ? undefined : 'Seu perfil não tem acesso à lista de grupos.'"
      />
      <Selecao v-model="filtros.periodo" rotulo="Criadas" :opcoes="PERIODOS.map((p) => ({ ...p, rotulo: p.valor === 'tudo' ? 'Em qualquer data' : p.rotulo }))" />
      <div v-if="filtros.periodo === 'personalizado'" class="grid grid-cols-2 gap-2 sm:col-span-2">
        <Campo v-model="filtros.de" rotulo="Criadas de" tipo="date" :max="filtros.ate || hoje" :erro="erroDatas" />
        <Campo v-model="filtros.ate" rotulo="até" tipo="date" :min="filtros.de || undefined" :max="hoje" />
      </div>
      <div v-if="qtdFiltros" class="sm:col-span-2 lg:col-span-4">
        <Botao variante="fantasma" tamanho="sm" class="!h-10" @click="limparFiltros">Limpar filtros</Botao>
      </div>
    </div>
  </section>

  <Alerta v-if="erro" tom="erro" class="mb-5">
    {{ erro }} <button type="button" class="link ml-1" @click="carregar()">Tentar de novo</button>
  </Alerta>

  <div v-else-if="!carregando && !totalNoQuadro && !totais.concluida" class="cartao">
    <EstadoVazio v-if="temFiltro" :icone="Search" titulo="Nenhuma ação com esses filtros" descricao="Tente outra busca ou limpe os filtros.">
      <Botao variante="secundario" @click="limparTudo">Limpar busca e filtros</Botao>
    </EstadoVazio>
    <EstadoVazio
      v-else
      :icone="ClipboardList"
      titulo="Nenhuma ação por enquanto"
      descricao="Quando um cliente der nota baixa, uma ação aparece aqui sozinha, com responsável e prazo. Você também pode criar uma ação à mão."
    >
      <Botao v-if="podeTratar" @click="novaAberta = true"><Plus class="size-4" aria-hidden="true" /> Nova ação</Botao>
    </EstadoVazio>
  </div>

  <template v-else>
    <!-- Celular: uma coluna por vez -->
    <div role="tablist" aria-label="Colunas do quadro" class="mb-3 grid grid-cols-3 gap-1 rounded-xl bg-superficie-2 p-1 md:hidden" @keydown="aoTeclarAbas">
      <button
        v-for="c in COLUNAS"
        :id="`aba-coluna-${c.situacao}`"
        :key="c.situacao"
        type="button"
        role="tab"
        :aria-selected="colunaAtiva === c.situacao"
        :aria-controls="`coluna-${c.situacao}`"
        :tabindex="colunaAtiva === c.situacao ? 0 : -1"
        class="flex min-h-11 flex-col items-center justify-center rounded-lg px-1 text-xs font-semibold leading-tight transition-colors"
        :class="colunaAtiva === c.situacao ? 'bg-superficie text-texto shadow-sm' : 'text-texto-suave'"
        @click="colunaAtiva = c.situacao"
      >
        {{ c.titulo }}
        <span class="text-[0.7rem] font-bold tabular-nums" :class="colunaAtiva === c.situacao ? 'text-marca-texto' : 'text-texto-fraco'">{{ formatarNumero(totais[c.situacao]) }}</span>
      </button>
    </div>

    <div class="grid grid-cols-1 gap-4 transition-opacity md:grid-cols-3" :class="atualizando ? 'opacity-60' : ''" :aria-busy="carregando || atualizando || undefined">
      <section
        v-for="c in COLUNAS"
        :id="`coluna-${c.situacao}`"
        :key="c.situacao"
        :role="telaLarga ? undefined : 'tabpanel'"
        :aria-labelledby="telaLarga ? `titulo-coluna-${c.situacao}` : `aba-coluna-${c.situacao}`"
        class="flex min-w-0 flex-col gap-3 rounded-2xl border p-3 transition-colors md:min-h-96"
        :class="[
          colunaAtiva === c.situacao ? 'flex' : 'hidden md:flex',
          colunaAlvo === c.situacao && arrastada && arrastada.situacao !== c.situacao ? 'border-marca bg-marca-suave' : 'border-borda bg-superficie-2/60',
        ]"
        @dragover="aoPassarPorCima($event, c.situacao)"
        @dragleave="aoSair($event, c.situacao)"
        @drop="aoSoltar($event, c.situacao)"
      >
        <header class="flex items-center justify-between gap-2 px-1">
          <h2 :id="`titulo-coluna-${c.situacao}`" class="flex items-center gap-2 text-sm font-bold text-texto">
            <CheckCircle2 v-if="c.situacao === 'concluida'" class="size-4 text-sucesso" aria-hidden="true" />
            {{ c.titulo }}
            <span class="rounded-full bg-superficie px-2 py-0.5 text-xs font-bold tabular-nums text-texto-suave ring-1 ring-borda">{{ formatarNumero(totais[c.situacao]) }}</span>
          </h2>
          <span v-if="c.situacao !== 'concluida' && c.situacao === 'a_fazer' && totais.vencidas" class="text-xs font-semibold text-erro">
            {{ plural(totais.vencidas, 'vencida', 'vencidas') }} no quadro
          </span>
        </header>

        <div v-if="carregando" class="flex flex-col gap-3">
          <div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-xl bg-superficie" />
        </div>
        <template v-else>
          <ul v-if="quadro.colunas[c.situacao].length" class="flex flex-col gap-2.5" :aria-label="`Ações em ${c.titulo}`">
            <li v-for="a in quadro.colunas[c.situacao]" :key="String(a.id)" :data-acao="String(a.id)">
              <CartaoAcao
                :acao="a"
                :pode-mover="podeTratar"
                :arrastavel="podeTratar && telaLarga"
                :ocupado="ocupados.has(String(a.id))"
                :arrastando="arrastada?.id === a.id"
                @abrir="abrir"
                @mover="mover"
                @arrastar="aoArrastar"
                @soltar="aoTerminarArraste"
              />
            </li>
          </ul>
          <p
            v-else
            class="rounded-xl border border-dashed px-4 py-8 text-center text-sm"
            :class="colunaAlvo === c.situacao && arrastada ? 'border-marca text-marca-texto' : 'border-borda-forte text-texto-fraco'"
          >
            {{ arrastada && arrastada.situacao !== c.situacao ? 'Solte aqui' : c.vazio }}
          </p>
          <div v-if="c.situacao === 'concluida' && totais.concluida" class="mt-auto px-1 pt-1">
            <p v-if="quadro.colunas.concluida.length && totais.concluida > quadro.colunas.concluida.length" class="mb-1 text-xs text-texto-fraco">
              Aqui ficam as {{ Math.min(quadro.colunas.concluida.length, LIMITE_CONCLUIDAS) }} mais recentes.
            </p>
            <button type="button" class="link inline-flex min-h-10 items-center text-sm" @click="concluidasAbertas = true">
              Ver todas as concluídas ({{ formatarNumero(totais.concluida) }})
            </button>
          </div>
        </template>
      </section>
    </div>
    <p class="mt-3 hidden text-xs text-texto-fraco md:block">Arraste um cartão para outra coluna ou use “Mover” no cartão.</p>
  </template>

  <p class="sr-only" aria-live="polite">{{ anuncio }}</p>

  <PainelAcao
    :acao="acaoAberta"
    :aberto="idAberto !== null"
    :carregando="carregandoAcao"
    :erro-carga="erroAcao"
    :concluir="concluirPendente"
    :erros-iniciais="errosMover"
    @fechar="fecharPainel"
    @salva="aoSalvar"
    @excluida="aoExcluir"
    @recarregada="aoRecarregar"
  />
  <ModalNovaAcao v-model:aberto="novaAberta" @criada="aoCriar" />
  <ModalConcluidas v-model:aberto="concluidasAbertas" :filtros="filtrosApi" @abrir="abrir" />
</template>
