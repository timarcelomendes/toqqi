<script setup lang="ts">
// Respostas: todas as notas e comentários, com filtros no endereço (dá para compartilhar o link),
// métricas do filtro, análise no painel lateral, arquivar, excluir (admin), registrar à mão e exportar.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Archive,
  ArchiveRestore,
  Download,
  Eye,
  MessageSquareText,
  MoreHorizontal,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import {
  contatosApi,
  empresasApi,
  mensagemDoErro,
  respostasApi,
  type GrupoNota,
  type Id,
  type MetricasRespostas,
  type Referencia,
  type RespostaItem,
  type TemaResposta,
} from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData, hojeIso } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import { PERIODOS, erroPeriodoEscolhido, intervaloDoPeriodo } from '@/utils/periodo'
import { CANAIS } from '@/utils/rotulos'
import BarraGrupos from '@/components/app/BarraGrupos.vue'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import Paginacao from '@/components/ui/Paginacao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import SeloAcao from '@/modulos/acoes/SeloAcao.vue'
import CampoEmpresa from '@/modulos/contatos/CampoEmpresa.vue'
import { faixaNps, formatarMedia2, formatarNps } from '@/modulos/painel/logica'
import ModalRegistrarResposta from './ModalRegistrarResposta.vue'
import PainelAnalise from './PainelAnalise.vue'
import SeloNota from './SeloNota.vue'
import SeloSentimento from './SeloSentimento.vue'
import { OPCOES_SENTIMENTO, analisada, mostrarFiltrosIa } from './ia'
import {
  CATEGORIAS,
  FILTROS_PADRAO,
  LIMITE_BUSCA,
  TEMAS_PADRAO,
  categoriasDoTipo,
  contarFiltrosAtivos,
  contextoNoFiltro,
  filtrosDaQuery,
  filtrosParaApi,
  mesmaBusca,
  mesmosFiltros,
  queryDosFiltros,
  rotuloTema,
  textoExclusao,
  type Consulta,
  type FiltrosTela,
} from './logica'

const rota = useRoute()
const router = useRouter()
const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const podeEditar = computed(() => sessao.pode('respostas.editar'))
/** Empresas, grupos e perfis vêm de listas que pedem contatos.ver (sem ela, nada de chamar a API). */
const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))
function opcoesCadastro(lista: { id: Id; nome: string }[], atual: Id | '', rotuloAtual: string) {
  const opcoes = lista.map((x) => ({ valor: x.id, rotulo: x.nome }))
  if (atual !== '' && !opcoes.some((o) => String(o.valor) === String(atual))) opcoes.unshift({ valor: atual, rotulo: rotuloAtual })
  return opcoes
}

// ── Filtros ↔ endereço ──────────────────────────────────────────────────────
const filtros = reactive<FiltrosTela>(filtrosDaQuery(rota.query as Consulta))
const busca = ref(filtros.busca)
const filtrosAbertos = ref(contarFiltrosAtivos(filtros) > 0)
const hoje = hojeIso()

function idDaQuery(v: unknown): Id | null {
  const s = Array.isArray(v) ? v[0] : v
  return typeof s === 'string' && /^[\w-]{1,40}$/.test(s) ? s : null
}
const analisando = ref<Id | null>(idDaQuery(rota.query.analisar))

function consultaAtual(): Record<string, string> {
  return { ...queryDosFiltros(filtros), ...(analisando.value !== null ? { analisar: String(analisando.value) } : {}) }
}
function escreverEndereco() {
  const q = consultaAtual()
  const atual = Object.fromEntries(Object.entries(rota.query).filter(([, v]) => typeof v === 'string')) as Record<string, string>
  if (JSON.stringify(q) !== JSON.stringify(atual)) router.replace({ query: q })
}

// Endereço mudou por fora (voltar do navegador, link do painel): a tela acompanha.
watch(
  () => rota.query,
  (q) => {
    if (rota.name !== 'respostas') return
    const novo = filtrosDaQuery(q as Consulta)
    if (!mesmosFiltros(novo, filtros)) {
      Object.assign(filtros, novo)
      busca.value = novo.busca
    }
    const a = idDaQuery(q.analisar)
    if (String(a) !== String(analisando.value)) analisando.value = a
  },
)

let atrasoBusca: ReturnType<typeof setTimeout> | null = null
watch(busca, (v) => {
  if (atrasoBusca) clearTimeout(atrasoBusca)
  atrasoBusca = setTimeout(() => (filtros.busca = v.trim().slice(0, LIMITE_BUSCA)), 300)
})

// Tipo e categoria precisam combinar (ex.: CSAT não tem "detrator").
watch(
  () => filtros.tipo_nota,
  (t) => {
    if (filtros.categoria && !categoriasDoTipo(t).includes(filtros.categoria)) filtros.categoria = ''
  },
)
// Ao escolher "Escolher as datas", começa com o intervalo que estava valendo.
watch(
  () => filtros.periodo,
  (novo, antigo) => {
    if (novo !== 'personalizado' || filtros.de || filtros.ate) return
    const r = intervaloDoPeriodo(antigo, {}, hoje)
    filtros.de = r.de ?? ''
    filtros.ate = r.ate ?? hoje
  },
)

// Datas escolhidas à mão: as duas, válidas e na ordem; senão, avisa no campo e não busca de novo.
const erroDatas = computed(() => (filtros.periodo === 'personalizado' ? erroPeriodoEscolhido(filtros.de, filtros.ate) : null))
const qtdFiltros = computed(() => contarFiltrosAtivos(filtros))
/** Contexto da entrega no filtro (vem de Relatórios › Entregas): aparece em "Mostrando", como o contato. */
const contexto = computed(() => contextoNoFiltro(filtros))
const temFiltro = computed(
  () => qtdFiltros.value > 0 || !!filtros.busca || filtros.periodo !== FILTROS_PADRAO.periodo || filtros.contato_id !== '' || contexto.value.length > 0,
)

function limparFiltros() {
  Object.assign(filtros, {
    ...FILTROS_PADRAO,
    busca: filtros.busca,
    periodo: filtros.periodo,
    de: filtros.de,
    ate: filtros.ate,
    contato_id: filtros.contato_id,
    motorista: filtros.motorista,
    rota: filtros.rota,
    filial: filtros.filial,
    transportadora: filtros.transportadora,
  })
}
function limparTudo() {
  busca.value = ''
  Object.assign(filtros, { ...FILTROS_PADRAO })
}

// ── Nomes para os filtros que vêm só com o id (empresa e contato) ───────────
const nomes = reactive({ empresas: {} as Record<string, string>, contatos: {} as Record<string, string> })
const empresaFiltro = computed<Referencia | null>({
  get: () => (filtros.empresa_id === '' ? null : { id: filtros.empresa_id, nome: nomes.empresas[String(filtros.empresa_id)] ?? 'Empresa escolhida' }),
  set: (v) => {
    if (v) nomes.empresas[String(v.id)] = v.nome
    filtros.empresa_id = v?.id ?? ''
  },
})
const nomeContato = computed(() => (filtros.contato_id === '' ? null : (nomes.contatos[String(filtros.contato_id)] ?? 'este contato')))

async function descobrirNomes() {
  const e = filtros.empresa_id
  if (e !== '' && !nomes.empresas[String(e)]) {
    const daLista = lista.value.find((r) => String(r.empresa?.id) === String(e))?.empresa?.nome
    if (daLista) nomes.empresas[String(e)] = daLista
    else if (sessao.pode('contatos.ver')) {
      try {
        nomes.empresas[String(e)] = (await empresasApi.obter(e)).nome
      } catch {
        /* fica "Empresa escolhida" */
      }
    }
  }
  const c = filtros.contato_id
  if (c !== '' && !nomes.contatos[String(c)]) {
    const daLista = lista.value.find((r) => String(r.contato?.id) === String(c))?.contato?.nome
    if (daLista) nomes.contatos[String(c)] = daLista
    else if (sessao.pode('contatos.ver')) {
      try {
        nomes.contatos[String(c)] = (await contatosApi.obter(c)).nome
      } catch {
        /* fica "este contato" */
      }
    }
  }
}

// ── Lista ───────────────────────────────────────────────────────────────────
const lista = ref<RespostaItem[]>([])
const total = ref(0)
const porPagina = ref(50)
const metricas = ref<MetricasRespostas | null>(null)
const carregando = ref(true)
const atualizando = ref(false)
const erro = ref<string | null>(null)
const temas = ref<TemaResposta[]>(TEMAS_PADRAO)
let controle: AbortController | null = null

async function carregar() {
  if (erroDatas.value) {
    carregando.value = false
    return
  }
  controle?.abort()
  controle = new AbortController()
  if (lista.value.length || metricas.value) atualizando.value = true
  else carregando.value = true
  erro.value = null
  try {
    const r = await respostasApi.listar(filtrosParaApi(filtros, hoje), controle.signal)
    lista.value = r.itens ?? []
    total.value = r.total ?? 0
    porPagina.value = r.por_pagina || 50
    metricas.value = r.metricas ?? null
    // A página ficou vazia (ex.: depois de arquivar a última): volta para a última que existe.
    if (!lista.value.length && filtros.pagina > 1 && total.value > 0) filtros.pagina = Math.max(1, Math.ceil(total.value / porPagina.value))
    descobrirNomes()
  } catch (e) {
    if (e instanceof DOMException) return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
    atualizando.value = false
  }
}

watch(
  () => ({ ...filtros }),
  (novo, antigo) => {
    if (antigo && !mesmaBusca(novo, antigo) && novo.pagina !== 1) {
      filtros.pagina = 1
      return
    }
    escreverEndereco()
    carregar()
  },
)
watch(analisando, escreverEndereco)

const pagina = computed({ get: () => filtros.pagina, set: (p: number) => (filtros.pagina = p) })

// ── Métricas ────────────────────────────────────────────────────────────────
const nps = computed(() => metricas.value?.nps ?? null)
const faixa = computed(() => (nps.value ? faixaNps(nps.value.faixa, nps.value.valor) : null))
function linkCategoria(g: GrupoNota) {
  return { path: '/respostas', query: { ...queryDosFiltros({ ...filtros, categoria: g, pagina: 1 }) } }
}

// ── IA (etapa 4b): "Sentimento" e "Só reclamações" com a IA ativa, com análises na lista ou já no endereço ──
const mostrarIa = computed(() =>
  mostrarFiltrosIa({
    iaAtiva: sessao.conta?.ia_ativa,
    temAnalise: lista.value.some((r) => analisada(r.ia)),
    filtroLigado: !!filtros.sentimento || filtros.reclamacao,
  }),
)

// ── Opções dos filtros ──────────────────────────────────────────────────────
const opcoesCategoria = computed(() => categoriasDoTipo(filtros.tipo_nota).map((g) => ({ valor: g, rotulo: CATEGORIAS[g].plural })))
const opcoesTipo = [
  { valor: 'nps' as const, rotulo: 'NPS (0 a 10)' },
  { valor: 'csat' as const, rotulo: 'CSAT (1 a 5)' },
]
const opcoesArquivadas = [
  { valor: 'false' as const, rotulo: 'Só as ativas' },
  { valor: 'true' as const, rotulo: 'Só as arquivadas' },
  { valor: 'todas' as const, rotulo: 'Ativas e arquivadas' },
]
const opcoesDataPor = [
  { valor: 'resposta' as const, rotulo: 'Data da resposta' },
  { valor: 'entrada' as const, rotulo: 'Data de entrada' },
]
const dicaDataPor = computed(() =>
  filtros.periodo === 'tudo'
    ? 'Escolha um período para usar.'
    : filtros.data_por === 'entrada'
      ? 'Quando a resposta chegou ao Toqqi (numa importação, o dia em que foi importada).'
      : undefined,
)

// ── Ações das linhas ────────────────────────────────────────────────────────
const ocupado = ref<Id | null>(null)
const registrarAberto = ref(false)
const baixando = ref(false)

function abrir(r: RespostaItem) {
  analisando.value = r.id
}

function substituir(r: RespostaItem) {
  const i = lista.value.findIndex((x) => String(x.id) === String(r.id))
  if (i >= 0) lista.value.splice(i, 1, { ...lista.value[i]!, ...r })
}

async function arquivarOuRestaurar(r: RespostaItem) {
  ocupado.value = r.id
  try {
    const novo = r.arquivada ? await respostasApi.restaurar(r.id) : await respostasApi.arquivar(r.id)
    substituir(novo)
    avisar.sucesso(novo.arquivada ? 'Resposta arquivada: ela saiu dos números.' : 'Resposta restaurada: ela voltou a contar nos números.')
    carregar()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function excluir(r: RespostaItem) {
  ocupado.value = r.id
  try {
    // A confirmação diz quantas ações somem junto: buscamos o detalhe para contar.
    const d = await respostasApi.obter(r.id)
    const t = textoExclusao(r, d.acoes?.length ?? 0)
    ocupado.value = null
    if (!(await confirmar({ titulo: t.titulo, mensagem: t.mensagem, confirmar: t.confirmar, perigo: true }))) return
    ocupado.value = r.id
    await respostasApi.excluir(r.id)
    avisar.sucesso('Resposta excluída.')
    aoExcluir(r.id)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

function aoExcluir(id: Id) {
  lista.value = lista.value.filter((x) => String(x.id) !== String(id))
  total.value = Math.max(0, total.value - 1)
  carregar()
}

function aoAtualizar(r: RespostaItem) {
  const antes = lista.value.find((x) => String(x.id) === String(r.id))
  substituir(r)
  // Nota, comentário, temas ou arquivamento podem mudar as métricas e tirar (ou pôr) a resposta no filtro
  // atual (categoria, busca, tema, arquivadas): busca a lista de novo. Só a ação ligada mudou: não precisa.
  const mudouOQueFiltra =
    !antes ||
    antes.nota !== r.nota ||
    antes.grupo !== r.grupo ||
    antes.arquivada !== r.arquivada ||
    (antes.comentario ?? '') !== (r.comentario ?? '') ||
    JSON.stringify(antes.temas ?? []) !== JSON.stringify(r.temas ?? [])
  if (mudouOQueFiltra) carregar()
}

function aoRegistrar() {
  if (filtros.pagina !== 1) filtros.pagina = 1
  else carregar()
}

async function exportar() {
  if (erroDatas.value) return
  baixando.value = true
  try {
    await respostasApi.baixarCsv(filtrosParaApi(filtros, hoje))
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}

const contatoParaRegistro = computed(() => (filtros.contato_id !== '' && nomeContato.value ? { id: filtros.contato_id, nome: nomeContato.value } : null))

const colunas: Coluna[] = [
  { chave: 'data', rotulo: 'Quando', classe: 'w-32' },
  { chave: 'contato', rotulo: 'Contato', classe: 'w-[22%]' },
  { chave: 'nota', rotulo: 'Nota', alinhar: 'centro', classe: 'w-16' },
  { chave: 'comentario', rotulo: 'Comentário', classe: 'w-[38%]' },
  { chave: 'acao', rotulo: 'Ação' },
  { chave: 'opcoes', rotulo: 'Opções', rotuloOculto: true, alinhar: 'direita' },
]

onMounted(() => {
  carregar()
  respostasApi
    .temas()
    .then((t) => {
      if (Array.isArray(t) && t.length) temas.value = t
    })
    .catch(() => undefined)
  if (sessao.pode('contatos.ver')) cadastros.garantir(['grupos', 'perfis'])
})
onBeforeUnmount(() => {
  controle?.abort()
  if (atrasoBusca) clearTimeout(atrasoBusca)
})
</script>

<template>
  <CabecalhoPagina titulo="Respostas" descricao="Todas as notas e comentários dos seus clientes. Analise, arquive e crie ações a partir delas.">
    <template #acoes>
      <div class="hidden sm:contents">
        <Botao v-if="sessao.pode('importacao.usar')" variante="fantasma" :para="{ path: '/contatos/importar', query: { tipo: 'respostas' } }">
          <Upload class="size-4" aria-hidden="true" /> Importar respostas antigas
        </Botao>
        <Botao v-if="sessao.pode('painel.exportar')" variante="secundario" :carregando="baixando" :desabilitado="!total || !!erroDatas" @click="exportar">
          <Download v-if="!baixando" class="size-4" aria-hidden="true" /> Exportar CSV
        </Botao>
      </div>
      <Botao v-if="podeEditar" @click="registrarAberto = true"><Plus class="size-4" aria-hidden="true" /> Registrar resposta</Botao>
      <MenuSuspenso v-if="sessao.pode('importacao.usar') || sessao.pode('painel.exportar')" rotulo="Mais opções de respostas" alinhar="direita" class="sm:hidden">
        <template #gatilho="{ props }">
          <Botao v-bind="props" variante="secundario" :carregando="baixando"><MoreHorizontal v-if="!baixando" class="size-4" aria-hidden="true" /> Mais</Botao>
        </template>
        <ItemMenu v-if="sessao.pode('painel.exportar')" :icone="Download" @click="exportar">Exportar CSV</ItemMenu>
        <ItemMenu v-if="sessao.pode('importacao.usar')" :icone="Upload" :para="{ path: '/contatos/importar', query: { tipo: 'respostas' } }">Importar respostas antigas</ItemMenu>
      </MenuSuspenso>
    </template>
  </CabecalhoPagina>

  <!-- Métricas do filtro -->
  <section v-if="metricas && metricas.total > 0" class="cartao mb-5 grid grid-cols-1 gap-5 p-5 md:grid-cols-[auto_minmax(0,1fr)] md:items-center md:gap-8" aria-label="Números das respostas filtradas">
    <div class="grid grid-cols-2 gap-4 sm:flex sm:items-start sm:gap-8">
      <div v-if="nps && nps.total > 0">
        <p class="text-sm font-semibold text-texto-suave">NPS</p>
        <p class="text-3xl font-extrabold leading-tight text-texto sm:text-4xl">{{ formatarNps(nps.valor) }}</p>
        <Etiqueta v-if="faixa" :tom="faixa.tom" ponto>{{ faixa.rotulo }}</Etiqueta>
      </div>
      <div v-if="metricas.csat && metricas.csat.total > 0">
        <p class="text-sm font-semibold text-texto-suave">CSAT</p>
        <p class="text-3xl font-extrabold leading-tight text-texto sm:text-4xl">{{ formatarNumero(metricas.csat.percentual) }}%</p>
        <p class="text-xs text-texto-fraco">média {{ formatarMedia2(metricas.csat.media) }}</p>
      </div>
      <div>
        <p class="text-sm font-semibold text-texto-suave">Respostas</p>
        <p class="text-3xl font-extrabold leading-tight text-texto sm:text-4xl">{{ formatarNumero(metricas.total) }}</p>
      </div>
    </div>
    <BarraGrupos
      v-if="nps && nps.total > 0"
      :detratores="nps.detratores"
      :neutros="nps.neutros"
      :promotores="nps.promotores"
      legenda="compacta"
      :link-grupo="linkCategoria"
    />
  </section>

  <div class="cartao">
    <!-- Filtros -->
    <div class="flex flex-col gap-3 border-b border-borda p-4 sm:px-5">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start">
        <Campo v-model="busca" rotulo="Buscar respostas" rotulo-oculto tipo="search" :maxlength="LIMITE_BUSCA" placeholder="Contato, empresa ou comentário" class="lg:max-w-sm lg:flex-1">
          <template #antes><Search class="size-4" aria-hidden="true" /></template>
        </Campo>
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start lg:ml-auto">
          <Selecao v-model="filtros.periodo" rotulo="Período" rotulo-oculto :opcoes="PERIODOS" class="sm:w-52" />
          <div v-if="filtros.periodo === 'personalizado'" class="grid grid-cols-2 gap-2">
            <Campo v-model="filtros.de" rotulo="De" rotulo-oculto tipo="date" :max="filtros.ate || hoje" :erro="erroDatas" title="Data inicial" />
            <Campo v-model="filtros.ate" rotulo="Até" rotulo-oculto tipo="date" :min="filtros.de || undefined" :max="hoje" title="Data final" />
          </div>
          <Botao variante="secundario" class="!h-11" :aria-expanded="filtrosAbertos" aria-controls="filtros-respostas" @click="filtrosAbertos = !filtrosAbertos">
            <SlidersHorizontal class="size-4" aria-hidden="true" /> Filtros
            <span v-if="qtdFiltros" class="rounded-full bg-marca-forte px-1.5 text-xs text-white">{{ qtdFiltros }}</span>
          </Botao>
        </div>
      </div>

      <div v-show="filtrosAbertos" id="filtros-respostas" class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Selecao v-model="filtros.categoria" rotulo="Categoria" :opcoes="opcoesCategoria" vazio="Todas" />
        <Selecao v-model="filtros.tipo_nota" rotulo="Tipo de pesquisa" :opcoes="opcoesTipo" vazio="NPS e CSAT" />
        <Selecao v-model="filtros.tema" rotulo="Tema" :opcoes="temas.map((t) => ({ valor: t.chave, rotulo: t.rotulo }))" vazio="Todos" />
        <Selecao v-model="filtros.arquivadas" rotulo="Arquivadas" :opcoes="opcoesArquivadas" />
        <CampoEmpresa v-model="empresaFiltro" rotulo="Empresa" placeholder="Todas" />
        <!-- Grupos e perfis vêm dos cadastros (contatos.ver): sem acesso, só aparecem se já vierem no endereço. -->
        <Selecao
          v-if="podeVerCadastros || filtros.grupo_id !== ''"
          v-model="filtros.grupo_id"
          rotulo="Grupo de empresas"
          :opcoes="opcoesCadastro(cadastros.listas.grupos, filtros.grupo_id, 'Grupo escolhido')"
          vazio="Todos"
          :dica="podeVerCadastros ? undefined : 'Seu perfil não tem acesso à lista de grupos.'"
        />
        <Selecao
          v-if="podeVerCadastros || filtros.perfil_id !== ''"
          v-model="filtros.perfil_id"
          rotulo="Perfil do contato"
          :opcoes="opcoesCadastro(cadastros.listas.perfis, filtros.perfil_id, 'Perfil escolhido')"
          vazio="Todos"
          :dica="podeVerCadastros ? undefined : 'Seu perfil não tem acesso à lista de perfis.'"
        />
        <Selecao v-model="filtros.data_por" rotulo="Contar o período pela" :opcoes="opcoesDataPor" :desabilitado="filtros.periodo === 'tudo'" :dica="dicaDataPor" />
        <Selecao v-if="mostrarIa" v-model="filtros.sentimento" rotulo="Sentimento (IA)" :opcoes="OPCOES_SENTIMENTO" vazio="Todos" />
        <!-- Como no painel: tira as respostas de empresas desativadas (as sem empresa continuam). -->
        <div class="flex min-h-11 flex-col gap-3 sm:col-span-2 sm:flex-row sm:items-center sm:gap-8 lg:col-span-4">
          <Interruptor v-model="filtros.so_ativos" rotulo="Só empresas ativas" class="w-full sm:w-fit sm:items-center" />
          <Interruptor
            v-if="mostrarIa"
            v-model="filtros.reclamacao"
            rotulo="Só reclamações"
            class="w-full sm:w-fit sm:items-center"
            :descricao="filtros.tema ? 'Reclamações do tema escolhido.' : undefined"
          />
        </div>
        <div v-if="qtdFiltros" class="sm:col-span-2 lg:col-span-4">
          <Botao variante="fantasma" tamanho="sm" class="!h-10" @click="limparFiltros">Limpar filtros</Botao>
        </div>
      </div>

      <div v-if="filtros.contato_id !== '' || filtros.categoria || contexto.length" class="flex flex-wrap items-center gap-2 text-sm">
        <span class="text-texto-fraco">Mostrando:</span>
        <span v-if="filtros.contato_id !== ''" class="inline-flex min-h-9 items-center gap-1 rounded-xl bg-marca-suave pl-3 pr-1 font-semibold text-marca-texto">
          Respostas de {{ nomeContato }}
          <button type="button" class="flex size-8 items-center justify-center rounded-lg hover:bg-marca/15" :aria-label="`Ver respostas de todos, não só de ${nomeContato}`" @click="filtros.contato_id = ''">
            <X class="size-4" aria-hidden="true" />
          </button>
        </span>
        <span v-if="filtros.categoria" class="inline-flex min-h-9 items-center gap-1 rounded-xl bg-superficie-2 pl-3 pr-1 font-semibold text-texto">
          {{ CATEGORIAS[filtros.categoria].plural }}
          <button type="button" class="flex size-8 items-center justify-center rounded-lg hover:bg-borda" aria-label="Tirar o filtro de categoria" @click="filtros.categoria = ''">
            <X class="size-4" aria-hidden="true" />
          </button>
        </span>
        <!-- Contexto da entrega (de Relatórios › Entregas) -->
        <span v-for="c in contexto" :key="c.campo" class="inline-flex min-h-9 max-w-full items-center gap-1 rounded-xl bg-superficie-2 pl-3 pr-1 font-semibold text-texto" data-chip-contexto>
          <span class="min-w-0 truncate"><span class="font-normal text-texto-suave">{{ c.rotulo }}:</span> {{ c.valor }}</span>
          <button
            type="button"
            class="flex size-8 shrink-0 items-center justify-center rounded-lg hover:bg-borda"
            :aria-label="`Tirar o filtro de ${c.rotulo.toLowerCase()} (${c.valor})`"
            @click="filtros[c.campo] = ''"
          >
            <X class="size-4" aria-hidden="true" />
          </button>
        </span>
      </div>
    </div>

    <Alerta v-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-else>
      <div class="transition-opacity" :class="atualizando ? 'opacity-60' : ''" :aria-busy="atualizando || carregando || undefined">
        <!-- Computador: tabela -->
        <div class="hidden xl:block">
          <Tabela :colunas="colunas" :linhas="lista" :chave="(r) => r.id" :carregando="carregando" legenda="Respostas dos clientes">
            <template #cel-data="{ linha: r }">
              <span class="block whitespace-nowrap text-texto-suave">{{ formatarData(r.data) }}</span>
              <span class="block text-xs text-texto-fraco">{{ CANAIS[r.canal] ?? r.canal }}</span>
              <span v-if="r.arquivada" class="mt-1 block"><Etiqueta tom="neutro">Arquivada</Etiqueta></span>
              <span v-if="r.edicoes" class="mt-1 block"><Etiqueta tom="info">Editada</Etiqueta></span>
            </template>
            <template #cel-contato="{ linha: r }">
              <div class="min-w-0">
                <button type="button" class="block max-w-full break-words text-left font-semibold text-texto hover:underline" @click="abrir(r)">
                  {{ r.contato?.nome ?? 'Sem identificação' }}
                </button>
                <p class="break-words text-texto-fraco">{{ r.empresa?.nome ?? r.contato?.email ?? '—' }}</p>
              </div>
            </template>
            <template #cel-nota="{ linha: r }">
              <SeloNota :nota="r.nota" :grupo="r.grupo" :tipo="r.tipo_nota" tamanho="sm" />
            </template>
            <template #cel-comentario="{ linha: r }">
              <p v-if="r.comentario" class="line-clamp-2 text-texto">{{ r.comentario }}</p>
              <p v-else class="text-texto-fraco">Sem comentário</p>
              <div v-if="r.temas?.length || analisada(r.ia)" class="mt-1.5 flex flex-wrap gap-1">
                <SeloSentimento :ia="r.ia" />
                <Etiqueta v-for="t in r.temas" :key="t" tom="info">{{ rotuloTema(t, temas) }}</Etiqueta>
              </div>
            </template>
            <template #cel-acao="{ linha: r }">
              <SeloAcao v-if="r.acao" :acao="r.acao" :link="sessao.pode('acoes.ver')" compacto />
              <span v-else class="text-texto-fraco">—</span>
            </template>
            <template #cel-opcoes="{ linha: r }">
              <div class="flex items-center justify-end gap-1">
                <Botao variante="secundario" tamanho="sm" class="!h-9" @click="abrir(r)">Analisar</Botao>
                <MenuSuspenso v-if="podeEditar || sessao.admin" :rotulo="`Mais opções para a resposta de ${r.contato?.nome ?? 'cliente'}`" fixo>
                  <template #gatilho="{ props }">
                    <button
                      v-bind="props"
                      type="button"
                      class="flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
                      :disabled="ocupado === r.id"
                    >
                      <MoreHorizontal class="size-5" aria-hidden="true" />
                    </button>
                  </template>
                  <ItemMenu v-if="podeEditar" :icone="r.arquivada ? ArchiveRestore : Archive" @click="arquivarOuRestaurar(r)">{{ r.arquivada ? 'Restaurar' : 'Arquivar' }}</ItemMenu>
                  <ItemMenu v-if="sessao.admin" :icone="Trash2" perigo @click="excluir(r)">Excluir de vez</ItemMenu>
                </MenuSuspenso>
              </div>
            </template>
            <template #vazio><span /></template>
          </Tabela>
        </div>

        <!-- Celular: cartões -->
        <ul v-if="!carregando" class="flex flex-col divide-y divide-borda xl:hidden">
          <li v-for="r in lista" :key="String(r.id)" class="flex flex-col gap-2.5 px-4 py-4">
            <div class="flex items-start gap-3">
              <SeloNota :nota="r.nota" :grupo="r.grupo" :tipo="r.tipo_nota" />
              <div class="min-w-0 flex-1">
                <p class="truncate font-semibold text-texto">{{ r.contato?.nome ?? 'Sem identificação' }}</p>
                <p v-if="r.empresa?.nome" class="truncate text-sm text-texto-suave">{{ r.empresa.nome }}</p>
                <p class="text-xs text-texto-fraco">{{ [formatarData(r.data), CANAIS[r.canal] ?? r.canal].filter(Boolean).join(' · ') }}</p>
              </div>
              <MenuSuspenso v-if="podeEditar || sessao.admin" :rotulo="`Mais opções para a resposta de ${r.contato?.nome ?? 'cliente'}`" fixo>
                <template #gatilho="{ props }">
                  <button
                    v-bind="props"
                    type="button"
                    class="-mr-2 -mt-1 flex size-10 shrink-0 items-center justify-center rounded-xl text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50"
                    :disabled="ocupado === r.id"
                  >
                    <MoreHorizontal class="size-5" aria-hidden="true" />
                  </button>
                </template>
                <ItemMenu v-if="podeEditar" :icone="r.arquivada ? ArchiveRestore : Archive" @click="arquivarOuRestaurar(r)">{{ r.arquivada ? 'Restaurar' : 'Arquivar' }}</ItemMenu>
                <ItemMenu v-if="sessao.admin" :icone="Trash2" perigo @click="excluir(r)">Excluir de vez</ItemMenu>
              </MenuSuspenso>
            </div>
            <p v-if="r.comentario" class="line-clamp-3 text-sm text-texto">{{ r.comentario }}</p>
            <div v-if="r.temas?.length || r.arquivada || r.edicoes || analisada(r.ia)" class="flex flex-wrap gap-1">
              <Etiqueta v-if="r.arquivada" tom="neutro">Arquivada</Etiqueta>
              <Etiqueta v-if="r.edicoes" tom="info">Editada</Etiqueta>
              <SeloSentimento :ia="r.ia" />
              <Etiqueta v-for="t in r.temas" :key="t" tom="info">{{ rotuloTema(t, temas) }}</Etiqueta>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <SeloAcao v-if="r.acao" :acao="r.acao" :link="sessao.pode('acoes.ver')" />
              <span v-else class="text-xs text-texto-fraco">Sem ação</span>
              <Botao variante="secundario" tamanho="sm" class="!h-10" @click="abrir(r)"><Eye class="size-4" aria-hidden="true" /> Analisar</Botao>
            </div>
          </li>
        </ul>
        <div v-else class="p-4 xl:hidden"><div v-for="i in 3" :key="i" class="mb-3 h-24 animate-pulse rounded-xl bg-superficie-2" /></div>

        <template v-if="!carregando && !lista.length">
          <EstadoVazio v-if="temFiltro" :icone="Search" titulo="Nenhuma resposta com esses filtros" descricao="Tente outro período, outra busca ou limpe os filtros.">
            <Botao variante="secundario" @click="limparTudo">Limpar busca e filtros</Botao>
          </EstadoVazio>
          <EstadoVazio
            v-else
            :icone="MessageSquareText"
            titulo="Nenhuma resposta ainda"
            descricao="Quando seus clientes responderem a pesquisa, as notas e os comentários aparecem aqui. Você também pode registrar uma nota que recebeu por telefone ou trazer o histórico de uma planilha."
          >
            <div class="flex flex-wrap justify-center gap-2">
              <Botao v-if="podeEditar" @click="registrarAberto = true"><Plus class="size-4" aria-hidden="true" /> Registrar resposta</Botao>
              <Botao v-if="sessao.pode('importacao.usar')" variante="secundario" :para="{ path: '/contatos/importar', query: { tipo: 'respostas' } }">
                <Upload class="size-4" aria-hidden="true" /> Importar respostas antigas
              </Botao>
            </div>
          </EstadoVazio>
        </template>
      </div>
      <Paginacao v-model="pagina" :total="total" :por-pagina="porPagina" :carregando="carregando || atualizando" :nome-itens="total === 1 ? 'resposta' : 'respostas'" />
    </template>
  </div>

  <PainelAnalise :id="analisando" :temas="temas" @fechar="analisando = null" @atualizada="aoAtualizar" @excluida="aoExcluir" />
  <ModalRegistrarResposta v-model:aberto="registrarAberto" :contato-inicial="contatoParaRegistro" @registrada="aoRegistrar" />
</template>
