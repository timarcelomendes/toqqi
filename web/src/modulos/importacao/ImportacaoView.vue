<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { AlertTriangle, ArrowLeft, CheckCircle2, ClipboardList, Download, FileSpreadsheet, MessageSquareText, RefreshCw, Sparkles, Upload, UsersRound, X } from 'lucide-vue-next'
import {
  ApiError,
  acoesApi,
  importacaoApi,
  mensagemDoErro,
  painelApi,
  type AnaliseImportacao,
  type ChaveImportacao,
  type ConferenciaImportacao,
  type Id,
  type ResultadoImportacao,
  type TipoImportacao,
} from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarNumero, plural } from '@/utils/formatos'
import { intervaloDoPeriodo } from '@/utils/periodo'
import { rotuloCriarPlanos, textoPlanosCriados } from '@/modulos/painel/logica'
import AlertaLimitePlano from '@/components/app/AlertaLimitePlano.vue'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Selecao from '@/components/ui/Selecao.vue'
import {
  TIPOS_IMPORTACAO,
  chavesPossiveis,
  corpoParaTipo,
  escolherChave,
  exemplosDaColuna,
  faltaEmailOuTelefone,
  mapeamentoInicial,
  obrigatoriosFaltando,
  pendenciasMapeamento,
  textoIaImportados,
  tipoDaQuery,
  validarArquivo,
  type Mapeamento,
} from './mapeamento'

type Passo = 1 | 2 | 3 | 4
const PASSOS = ['Preparar a planilha', 'Enviar o arquivo', 'Conferir as colunas', 'Pronto']
const CHAVES: Record<ChaveImportacao, { rotulo: string; descricao: string }> = {
  email: { rotulo: 'Pelo e-mail', descricao: 'Quem tiver o mesmo e-mail é a mesma pessoa.' },
  codigo_externo: { rotulo: 'Pelo código do seu sistema', descricao: 'Use se a planilha vem do seu ERP ou CRM.' },
  telefone: { rotulo: 'Pelo telefone', descricao: 'Quem tiver o mesmo telefone é a mesma pessoa.' },
}

const cadastros = useCadastrosStore()
const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()
const passo = ref<Passo>(1)

// Etapa 4a: a mesma tela importa contatos ou respostas antigas (?tipo=respostas).
const tipoEscolhido = ref<TipoImportacao>(tipoDaQuery(rota.query.tipo))
const arquivo = ref<File | null>(null)
const erroArquivo = ref<string | null>(null)
const arrastando = ref(false)
const analisando = ref(false)
const baixando = ref(false)
const analise = ref<AnaliseImportacao | null>(null)
const mapeamento = reactive<Mapeamento>({})
const opcoes = reactive({ chave: null as ChaveImportacao | null, atualizar_existentes: true, grupo_id: '' as Id | '' })
const conferencia = ref<ConferenciaImportacao | null>(null)
const corpoConferido = ref<string | null>(null)
const conferindo = ref(false)
const ignorarComProblema = ref(false)
const importando = ref(false)
const resultado = ref<ResultadoImportacao | null>(null)
const erro = ref<string | null>(null)
const limitePlano = ref<string | null>(null)
const expirou = ref(false)
const entrada = ref<HTMLInputElement | null>(null)

/** Depois da análise, vale o tipo que a API confirmou. */
const tipo = computed<TipoImportacao>(() => analise.value?.tipo ?? tipoEscolhido.value)
const textos = computed(() => TIPOS_IMPORTACAO[tipo.value])
const voltar = computed(() =>
  tipo.value === 'respostas' && !sessao.pode('respostas.ver') ? TIPOS_IMPORTACAO.contatos.voltar : textos.value.voltar,
)
watch(
  tipoEscolhido,
  (t) => {
    if (tipoDaQuery(rota.query.tipo) !== t) router.replace({ query: t === 'respostas' ? { ...rota.query, tipo: 'respostas' } : {} })
    document.title = `${TIPOS_IMPORTACAO[t].titulo} · Toqqi`
  },
  { immediate: true },
)
watch(
  () => rota.query.tipo,
  (v) => {
    if (passo.value === 1 && !analise.value) tipoEscolhido.value = tipoDaQuery(v)
  },
)
function item(n: number) {
  return plural(n, textos.value.item[0], textos.value.item[1])
}

const campos = computed(() => analise.value?.campos ?? [])
const opcoesCampos = computed(() => campos.value.map((c) => ({ valor: c.chave, rotulo: c.rotulo + (c.obrigatorio ? ' *' : '') })))
const possiveis = computed(() => chavesPossiveis(mapeamento))
const pendencias = computed(() => pendenciasMapeamento(mapeamento, campos.value, opcoes.chave, tipo.value))
const faltando = computed(() => obrigatoriosFaltando(mapeamento, campos.value))
const colunasImportadas = computed(() => Object.values(mapeamento).filter(Boolean).length)

const corpo = computed(() => corpoParaTipo(tipo.value, mapeamento, opcoes))
// Mudou algo depois de conferir: precisa conferir de novo.
const conferenciaValida = computed(() => !!conferencia.value && corpoConferido.value === JSON.stringify(corpo.value))
const podeImportar = computed(
  () =>
    conferenciaValida.value &&
    !!conferencia.value &&
    conferencia.value.prontas > 0 &&
    (conferencia.value.com_problema === 0 || ignorarComProblema.value),
)

watch(mapeamento, () => (opcoes.chave = escolherChave(mapeamento, opcoes.chave)), { deep: true })

function tratarErro(e: unknown) {
  if (e instanceof ApiError && (e.status === 402 || e.codigo === 'limite_do_plano')) limitePlano.value = e.mensagem
  else if (e instanceof ApiError && (e.status === 404 || e.status === 410)) expirou.value = true
  else erro.value = mensagemDoErro(e)
}
function limparErros() {
  erro.value = null
  limitePlano.value = null
  expirou.value = false
}

async function baixarModelo() {
  baixando.value = true
  limparErros()
  try {
    await importacaoApi.baixarModelo(tipoEscolhido.value)
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    baixando.value = false
  }
}

function escolherArquivo(f: File | null | undefined) {
  erroArquivo.value = null
  if (!f) return
  const msg = validarArquivo(f)
  if (msg) {
    erroArquivo.value = msg
    arquivo.value = null
    return
  }
  arquivo.value = f
}

function aoSoltar(e: DragEvent) {
  arrastando.value = false
  escolherArquivo(e.dataTransfer?.files?.[0])
}

async function analisar() {
  if (!arquivo.value) return
  analisando.value = true
  limparErros()
  try {
    const a = await importacaoApi.analisar(arquivo.value, tipoEscolhido.value)
    analise.value = a
    for (const k of Object.keys(mapeamento)) delete mapeamento[k]
    Object.assign(mapeamento, mapeamentoInicial(a.colunas, a.mapeamento_sugerido ?? {}, a.campos))
    opcoes.chave = escolherChave(mapeamento, null)
    conferencia.value = null
    corpoConferido.value = null
    ignorarComProblema.value = false
    passo.value = 3
    if (tipo.value === 'contatos') cadastros.garantir(['grupos'])
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) erroArquivo.value = e.campo('arquivo') ?? e.mensagem
    else tratarErro(e)
  } finally {
    analisando.value = false
  }
}

async function conferir() {
  if (!analise.value || !corpo.value || pendencias.value.length) return
  conferindo.value = true
  limparErros()
  const enviado = JSON.stringify(corpo.value)
  try {
    conferencia.value = await importacaoApi.conferir(analise.value.id, corpo.value)
    corpoConferido.value = enviado
    ignorarComProblema.value = false
  } catch (e) {
    tratarErro(e)
  } finally {
    conferindo.value = false
  }
}

async function importar() {
  if (!analise.value || !corpo.value || !podeImportar.value) return
  importando.value = true
  limparErros()
  try {
    resultado.value = await importacaoApi.importar(analise.value.id, { ...corpo.value, ignorar_com_problema: ignorarComProblema.value })
    passo.value = 4
    if (tipo.value === 'respostas') buscarDetratores()
  } catch (e) {
    tratarErro(e)
  } finally {
    importando.value = false
  }
}

// ── Etapa 5h: depois de importar respostas, o convite para criar os planos dos detratores sem plano (últimos 90 dias,
// os mesmos filtros do Início: só empresas ativas). A contagem vem do painel (quem não vê o painel não vê o convite).
const ULTIMOS_90 = { ...intervaloDoPeriodo('90'), so_ativos: true }
const semPlano = ref(0)
const criandoPlanos = ref(false)
const podeCriarPlanos = computed(() => sessao.pode('acoes.tratar') && sessao.pode('painel.ver'))
const iaMarcadas = computed(() => Number(resultado.value?.ia_marcadas) || 0)

async function buscarDetratores() {
  semPlano.value = 0
  if (!podeCriarPlanos.value) return
  try {
    semPlano.value = Number((await painelApi.obter(ULTIMOS_90)).atencao.detratores_sem_plano) || 0
  } catch {
    semPlano.value = 0 // sem a contagem, sem o convite (a importação já deu certo)
  }
}

async function criarPlanos() {
  if (criandoPlanos.value) return
  criandoPlanos.value = true
  try {
    const r = await acoesApi.criarParaDetratores(ULTIMOS_90)
    if (r.criadas > 0) {
      avisar.sucesso(textoPlanosCriados(r))
      router.push('/planos-de-acao').catch(() => undefined)
    } else {
      avisar.info(textoPlanosCriados(r))
      semPlano.value = 0
    }
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    criandoPlanos.value = false
  }
}

function recomecar() {
  arquivo.value = null
  analise.value = null
  conferencia.value = null
  resultado.value = null
  semPlano.value = 0
  limparErros()
  passo.value = 2
}

function qtdProblemas(r: ResultadoImportacao) {
  return Array.isArray(r.problemas) ? r.problemas.length : Number(r.problemas) || 0
}

function tamanho(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`
}

onBeforeRouteLeave(async () => {
  if (!analise.value || resultado.value || importando.value) return true
  return confirmar({
    titulo: 'Sair da importação?',
    mensagem: 'Nada foi importado ainda. Se sair agora, vai precisar enviar o arquivo de novo.',
    confirmar: 'Sair',
    cancelar: 'Continuar importando',
  })
})

onMounted(() => {
  if (tipoEscolhido.value === 'contatos') cadastros.garantir(['grupos'])
})
</script>

<template>
  <RouterLink :to="voltar.para" class="mb-4 inline-flex min-h-10 items-center gap-1.5 rounded-lg text-sm font-semibold text-texto-suave hover:text-texto">
    <ArrowLeft class="size-4" aria-hidden="true" /> {{ voltar.rotulo }}
  </RouterLink>
  <CabecalhoPagina :titulo="textos.titulo" :descricao="textos.subtitulo" />

  <!-- Etapas -->
  <ol class="mb-6 grid grid-cols-4 gap-2" aria-label="Etapas da importação">
    <li v-for="(nome, i) in PASSOS" :key="nome" :aria-current="passo === i + 1 ? 'step' : undefined" class="flex flex-col gap-2">
      <span class="h-1.5 rounded-full" :class="passo > i ? 'bg-marca' : 'bg-superficie-2'" aria-hidden="true" />
      <span class="text-xs font-semibold sm:text-sm" :class="passo === i + 1 ? 'text-texto' : 'text-texto-fraco'">
        <span class="sm:hidden">{{ i + 1 }}</span><span class="hidden sm:inline">{{ i + 1 }}. {{ nome }}</span>
        <span class="sr-only">{{ passo > i + 1 ? '(feito)' : passo === i + 1 ? '(etapa atual)' : '' }}</span>
      </span>
    </li>
  </ol>

  <div class="flex flex-col gap-4">
    <AlertaLimitePlano v-if="limitePlano" :mensagem="limitePlano" />
    <Alerta v-if="expirou" tom="atencao" titulo="A análise expirou">
      O arquivo fica guardado por 1 hora. Envie de novo para continuar.
      <button type="button" class="link ml-1" @click="recomecar">Enviar o arquivo de novo</button>
    </Alerta>
    <Alerta v-if="erro" tom="erro">{{ erro }}</Alerta>

    <!-- 1. O que importar e como preparar a planilha -->
    <section v-if="passo === 1" class="cartao p-5 sm:p-8" aria-labelledby="t-passo1">
      <fieldset>
        <legend id="t-passo1" class="text-lg font-bold text-texto">O que você quer importar?</legend>
        <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <label
            v-for="(t, k) in TIPOS_IMPORTACAO"
            :key="k"
            class="flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
            :class="tipoEscolhido === k ? 'border-marca bg-marca-suave' : 'border-borda-forte hover:bg-superficie-2'"
          >
            <input v-model="tipoEscolhido" type="radio" name="tipo-importacao" :value="k" class="sr-only" />
            <span class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-superficie text-marca-texto ring-1 ring-borda" aria-hidden="true">
              <UsersRound v-if="k === 'contatos'" class="size-5" />
              <MessageSquareText v-else class="size-5" />
            </span>
            <span class="flex flex-col gap-0.5">
              <span class="font-bold text-texto">{{ t.rotulo }}</span>
              <span class="text-sm text-texto-suave">{{ t.descricao }}</span>
            </span>
          </label>
        </div>
      </fieldset>

      <h2 class="mt-8 text-lg font-bold text-texto">Como deixar a planilha pronta</h2>
      <ul v-if="tipoEscolhido === 'contatos'" class="mt-3 flex max-w-2xl list-disc flex-col gap-1.5 pl-5 text-[0.95rem] text-texto-suave">
        <li>Uma pessoa por linha, com o <strong class="text-texto">nome</strong> e o <strong class="text-texto">e-mail ou o telefone</strong>.</li>
        <li>A primeira linha tem o nome das colunas. Não precisa ser igual ao modelo: na próxima etapa você diz o que é cada coluna.</li>
        <li>Empresas, grupos, cargos e responsáveis que ainda não existem são criados sozinhos.</li>
        <li>Aceitamos .csv, .xlsx e .xls de até 5 MB (cerca de 20 mil linhas).</li>
      </ul>
      <ul v-else class="mt-3 flex max-w-2xl list-disc flex-col gap-1.5 pl-5 text-[0.95rem] text-texto-suave">
        <li>Uma resposta por linha, com o <strong class="text-texto">e-mail do contato</strong>, a <strong class="text-texto">data</strong> e a <strong class="text-texto">nota de 0 a 10</strong>. Empresa e comentário são opcionais.</li>
        <li>O contato precisa já estar cadastrado no Toqqi. Se ainda não está, importe os contatos antes.</li>
        <li>Datas como 31/12/2025 ou 2025-12-31, de 2000 até hoje. A nota precisa ser inteira: “9,0” vale 9, mas “8,7” não é aceita.</li>
        <li>O mesmo contato com a mesma data é a mesma resposta: você escolhe se atualiza a que já foi importada ou mantém.</li>
        <li>As respostas antigas entram no histórico e nos números, mas não viram ação e ninguém recebe e-mail.</li>
        <li>Aceitamos .csv, .xlsx e .xls de até 5 MB (cerca de 20 mil linhas).</li>
      </ul>
      <div class="mt-6 flex flex-wrap gap-2">
        <Botao variante="secundario" :carregando="baixando" @click="baixarModelo"><Download class="size-4" aria-hidden="true" /> Baixar planilha modelo</Botao>
        <Botao @click="passo = 2">Já tenho minha planilha</Botao>
      </div>
    </section>

    <!-- 2. Arquivo -->
    <section v-else-if="passo === 2" class="cartao p-5 sm:p-8" aria-labelledby="t-passo2">
      <h2 id="t-passo2" class="text-lg font-bold text-texto">Envie sua planilha</h2>
      <div
        class="mt-4 flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors"
        :class="arrastando ? 'border-marca bg-marca-suave' : erroArquivo ? 'border-erro/50' : 'border-borda-forte'"
        @dragover.prevent="arrastando = true"
        @dragleave.prevent="arrastando = false"
        @drop.prevent="aoSoltar"
      >
        <FileSpreadsheet class="size-10 text-texto-fraco" aria-hidden="true" />
        <template v-if="arquivo">
          <p class="font-semibold text-texto">{{ arquivo.name }}</p>
          <p class="text-sm text-texto-fraco">{{ tamanho(arquivo.size) }}</p>
          <button type="button" class="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-texto-suave hover:text-texto" @click="arquivo = null">
            <X class="size-4" aria-hidden="true" /> Trocar arquivo
          </button>
        </template>
        <template v-else>
          <p class="font-semibold text-texto">Arraste o arquivo para cá</p>
          <p class="text-sm text-texto-fraco">ou</p>
          <Botao variante="secundario" @click="entrada?.click()"><Upload class="size-4" aria-hidden="true" /> Escolher arquivo</Botao>
          <p class="text-xs text-texto-fraco">.csv, .xlsx ou .xls · até 5 MB</p>
        </template>
        <input
          ref="entrada"
          type="file"
          class="sr-only"
          accept=".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          aria-label="Escolher planilha"
          tabindex="-1"
          @change="escolherArquivo(($event.target as HTMLInputElement).files?.[0]); ($event.target as HTMLInputElement).value = ''"
        />
      </div>
      <p v-if="erroArquivo" class="mt-2 text-sm font-medium text-erro" role="alert">{{ erroArquivo }}</p>
      <div class="mt-6 flex flex-wrap justify-between gap-2">
        <Botao variante="fantasma" @click="passo = 1"><ArrowLeft class="size-4" aria-hidden="true" /> Voltar</Botao>
        <Botao :desabilitado="!arquivo" :carregando="analisando" @click="analisar">{{ analisando ? 'Lendo a planilha…' : 'Continuar' }}</Botao>
      </div>
    </section>

    <!-- 3. Mapear e conferir -->
    <template v-else-if="passo === 3 && analise">
      <section class="cartao" aria-labelledby="t-passo3">
        <header class="border-b border-borda p-5">
          <h2 id="t-passo3" class="text-lg font-bold text-texto">O que é cada coluna?</h2>
          <p class="mt-1 text-sm text-texto-suave">
            Encontramos {{ plural(analise.total_linhas, 'linha', 'linhas') }} e {{ plural(analise.colunas.length, 'coluna', 'colunas') }} em
            <strong class="text-texto">{{ arquivo?.name }}</strong>. Já sugerimos o que deu para reconhecer; confira e ajuste.
          </p>
          <ul class="mt-3 flex flex-wrap gap-2 text-sm" aria-label="Campos obrigatórios">
            <li
              v-for="c in campos.filter((x) => x.obrigatorio)"
              :key="c.chave"
              class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold"
              :class="faltando.some((f) => f.chave === c.chave) ? 'bg-atencao-suave text-atencao' : 'bg-sucesso-suave text-sucesso'"
            >
              <CheckCircle2 v-if="!faltando.some((f) => f.chave === c.chave)" class="size-4" aria-hidden="true" />
              <AlertTriangle v-else class="size-4" aria-hidden="true" />
              {{ c.rotulo }}<span class="sr-only">{{ faltando.some((f) => f.chave === c.chave) ? ': falta indicar' : ': ok' }}</span>
            </li>
            <li
              v-if="tipo === 'contatos'"
              class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold"
              :class="faltaEmailOuTelefone(mapeamento) ? 'bg-atencao-suave text-atencao' : 'bg-sucesso-suave text-sucesso'"
            >
              <CheckCircle2 v-if="!faltaEmailOuTelefone(mapeamento)" class="size-4" aria-hidden="true" />
              <AlertTriangle v-else class="size-4" aria-hidden="true" />
              E-mail ou telefone
            </li>
          </ul>
        </header>
        <ul class="divide-y divide-borda">
          <li v-for="col in analise.colunas" :key="col" class="grid gap-3 px-5 py-3.5 sm:grid-cols-[1fr_1fr_16rem] sm:items-center">
            <div class="min-w-0">
              <p class="truncate font-semibold text-texto">{{ col }}</p>
              <p class="text-xs text-texto-fraco sm:hidden">{{ exemplosDaColuna(analise, col).join(' · ') || 'sem exemplos' }}</p>
            </div>
            <p class="hidden truncate text-sm text-texto-fraco sm:block" :title="exemplosDaColuna(analise, col, 5).join(' · ')">
              {{ exemplosDaColuna(analise, col).join(' · ') || '—' }}
            </p>
            <Selecao :model-value="mapeamento[col] ?? ''" @update:model-value="(v) => (mapeamento[col] = String(v))" :rotulo="`Importar a coluna “${col}” como`" rotulo-oculto :opcoes="opcoesCampos" vazio="Não importar" />
          </li>
        </ul>
        <p class="border-t border-borda px-5 py-3 text-sm text-texto-fraco">
          {{ plural(colunasImportadas, 'coluna será importada', 'colunas serão importadas') }}. Campos com * são obrigatórios.
        </p>
      </section>

      <section class="cartao flex flex-col gap-5 p-5" aria-labelledby="t-opcoes">
        <template v-if="tipo === 'contatos'">
          <h2 id="t-opcoes" class="text-lg font-bold text-texto">Como tratar quem já está cadastrado</h2>
          <fieldset>
            <legend class="mb-2 text-sm font-semibold text-texto">Reconhecer a mesma pessoa</legend>
            <div class="grid gap-2 sm:grid-cols-3">
              <label
                v-for="(c, k) in CHAVES"
                :key="k"
                class="flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
                :class="[
                  opcoes.chave === k ? 'border-marca bg-marca-suave' : 'border-borda-forte hover:bg-superficie-2',
                  possiveis.includes(k) ? '' : 'cursor-not-allowed opacity-50',
                ]"
              >
                <input v-model="opcoes.chave" type="radio" name="chave" :value="k" class="sr-only" :disabled="!possiveis.includes(k)" />
                <span class="text-sm font-bold text-texto">{{ c.rotulo }}</span>
                <span class="text-xs text-texto-suave">{{ possiveis.includes(k) ? c.descricao : 'Essa coluna não está na planilha.' }}</span>
              </label>
            </div>
          </fieldset>
          <Interruptor
            v-model="opcoes.atualizar_existentes"
            rotulo="Atualizar quem já existe"
            descricao="Ligado: os dados da planilha substituem os do cadastro. Desligado: quem já existe fica como está."
          />
          <Selecao
            v-model="opcoes.grupo_id"
            rotulo="Grupo para esta importação (opcional)"
            :opcoes="cadastros.listas.grupos.map((g) => ({ valor: g.id, rotulo: g.nome }))"
            vazio="Nenhum"
            dica="Coloca as empresas desta planilha no grupo escolhido. Útil para separar uma carteira ou filial."
          />
        </template>
        <template v-else>
          <h2 id="t-opcoes" class="text-lg font-bold text-texto">Respostas que já foram importadas</h2>
          <Interruptor
            v-model="opcoes.atualizar_existentes"
            rotulo="Atualizar as que já existem"
            descricao="Se já existe uma resposta importada do mesmo contato na mesma data: ligado, a nota e o comentário são trocados pelos da planilha; desligado, a que já existe fica como está."
          />
          <p class="text-sm text-texto-fraco">Se a empresa da planilha for diferente da empresa do contato, vale a do cadastro do contato.</p>
        </template>

        <Alerta v-if="pendencias.length" tom="atencao" titulo="Antes de conferir">
          <ul class="list-disc pl-4">
            <li v-for="p in pendencias" :key="p">{{ p }}</li>
          </ul>
        </Alerta>

        <div class="flex flex-wrap justify-between gap-2">
          <Botao variante="fantasma" @click="recomecar"><ArrowLeft class="size-4" aria-hidden="true" /> Outro arquivo</Botao>
          <Botao :variante="conferenciaValida ? 'secundario' : 'primario'" :desabilitado="!!pendencias.length" :carregando="conferindo" @click="conferir">
            <RefreshCw v-if="conferencia && !conferenciaValida" class="size-4" aria-hidden="true" />
            {{ conferencia && !conferenciaValida ? 'Conferir de novo' : 'Conferir' }}
          </Botao>
        </div>
      </section>

      <!-- Resultado da conferência -->
      <section v-if="conferencia" class="cartao flex flex-col gap-5 p-5" aria-labelledby="t-conf" aria-live="polite">
        <h2 id="t-conf" class="text-lg font-bold text-texto">Resultado da conferência</h2>
        <Alerta v-if="!conferenciaValida" tom="info">Você mudou algo depois de conferir. Confira de novo para liberar a importação.</Alerta>
        <dl class="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div class="rounded-xl bg-sucesso-suave p-4">
            <dt class="text-sm font-semibold text-sucesso">Prontas</dt>
            <dd class="text-2xl font-extrabold text-texto">{{ formatarNumero(conferencia.prontas) }}</dd>
          </div>
          <div class="rounded-xl p-4" :class="conferencia.com_problema ? 'bg-erro-suave' : 'bg-superficie-2'">
            <dt class="text-sm font-semibold" :class="conferencia.com_problema ? 'text-erro' : 'text-texto-fraco'">Com problema</dt>
            <dd class="text-2xl font-extrabold text-texto">{{ formatarNumero(conferencia.com_problema) }}</dd>
          </div>
          <div class="rounded-xl bg-superficie-2 p-4">
            <dt class="text-sm font-semibold text-texto-fraco">{{ tipo === 'respostas' ? 'Respostas novas' : 'Contatos novos' }}</dt>
            <dd class="text-2xl font-extrabold text-texto">{{ formatarNumero(conferencia.novos) }}</dd>
          </div>
          <div class="rounded-xl bg-superficie-2 p-4">
            <dt class="text-sm font-semibold text-texto-fraco">{{ tipo === 'respostas' ? 'Serão atualizadas' : 'Serão atualizados' }}</dt>
            <dd class="text-2xl font-extrabold text-texto">{{ formatarNumero(conferencia.atualizados) }}</dd>
          </div>
        </dl>

        <Alerta v-for="a in conferencia.avisos" :key="a" tom="atencao">{{ a }}</Alerta>

        <div v-if="conferencia.problemas.length">
          <h3 class="mb-2 text-sm font-bold text-texto">Linhas com problema</h3>
          <div class="max-h-72 overflow-y-auto rounded-xl border border-borda">
            <table class="w-full text-sm">
              <caption class="sr-only">Linhas com problema</caption>
              <thead class="sticky top-0 bg-superficie-2">
                <tr>
                  <th scope="col" class="w-20 px-4 py-2 text-left text-xs font-semibold uppercase text-texto-fraco">Linha</th>
                  <th scope="col" class="px-4 py-2 text-left text-xs font-semibold uppercase text-texto-fraco">O que aconteceu</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(p, i) in conferencia.problemas" :key="i" class="border-t border-borda">
                  <td class="px-4 py-2 font-mono tabular-nums text-texto">{{ p.linha }}</td>
                  <td class="px-4 py-2 text-texto-suave">{{ p.motivo }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="conferencia.com_problema > conferencia.problemas.length" class="mt-1 text-xs text-texto-fraco">
            Mostrando as primeiras {{ formatarNumero(conferencia.problemas.length) }}.
          </p>
        </div>

        <CaixaSelecao
          v-if="conferencia.com_problema > 0 && conferencia.prontas > 0"
          v-model="ignorarComProblema"
          rotulo="Importar só as linhas sem problema"
          :descricao="conferencia.com_problema === 1 ? 'A linha com problema fica de fora. Você pode corrigir e importar depois.' : `As ${formatarNumero(conferencia.com_problema)} linhas com problema ficam de fora. Você pode corrigir e importar depois.`"
        />
        <p v-if="conferencia.prontas === 0" class="text-sm font-medium text-erro">Nenhuma linha está pronta. Corrija a planilha e envie de novo.</p>

        <div class="flex justify-end">
          <Botao tamanho="lg" :desabilitado="!podeImportar" :carregando="importando" @click="importar">
            {{ importando ? 'Importando…' : `Importar ${item(conferencia.prontas)}` }}
          </Botao>
        </div>
      </section>
    </template>

    <!-- 4. Resultado -->
    <section v-else-if="passo === 4 && resultado" class="cartao p-6 text-center sm:p-10" aria-labelledby="t-fim">
      <span class="mx-auto flex size-14 items-center justify-center rounded-full bg-sucesso-suave text-sucesso" aria-hidden="true">
        <CheckCircle2 class="size-8" />
      </span>
      <h2 id="t-fim" class="mt-4 text-xl font-bold text-texto">Importação concluída!</h2>
      <dl class="mx-auto mt-6 grid max-w-xl grid-cols-3 gap-3">
        <div class="rounded-xl bg-superficie-2 p-4">
          <dt class="text-sm text-texto-fraco">{{ tipo === 'respostas' ? 'Novas' : 'Novos' }}</dt>
          <dd class="text-2xl font-extrabold text-texto">{{ formatarNumero(resultado.novos) }}</dd>
        </div>
        <div class="rounded-xl bg-superficie-2 p-4">
          <dt class="text-sm text-texto-fraco">{{ tipo === 'respostas' ? 'Atualizadas' : 'Atualizados' }}</dt>
          <dd class="text-2xl font-extrabold text-texto">{{ formatarNumero(resultado.atualizados) }}</dd>
        </div>
        <div class="rounded-xl bg-superficie-2 p-4">
          <dt class="text-sm text-texto-fraco">Deixados de fora</dt>
          <dd class="text-2xl font-extrabold text-texto">{{ formatarNumero(resultado.ignorados || qtdProblemas(resultado)) }}</dd>
        </div>
      </dl>
      <p v-if="tipo === 'respostas'" class="mx-auto mt-2 max-w-md text-sm text-texto-suave">
        As respostas entraram no histórico de cada contato e já contam no painel. Nenhuma ação foi criada e ninguém recebeu e-mail.
      </p>
      <div v-if="tipo === 'respostas' && (iaMarcadas > 0 || semPlano > 0)" class="mx-auto mt-6 flex max-w-xl flex-col gap-3 text-left">
        <p v-if="iaMarcadas > 0" class="flex items-start gap-3 rounded-xl bg-marca-suave p-4 text-sm text-texto" data-ia-importados>
          <Sparkles class="mt-0.5 size-5 shrink-0 text-marca-texto" aria-hidden="true" />
          <span>{{ textoIaImportados(iaMarcadas) }}</span>
        </p>
        <div v-if="semPlano > 0" class="flex flex-col gap-3 rounded-xl border border-borda bg-superficie-2 p-4 sm:flex-row sm:items-center" data-convite-planos>
          <ClipboardList class="hidden size-5 shrink-0 text-texto-suave sm:block" aria-hidden="true" />
          <p class="min-w-0 flex-1 text-sm text-texto">
            <strong class="font-semibold">{{ semPlano === 1 ? '1 empresa teve' : `${formatarNumero(semPlano)} empresas tiveram` }} detrator nos últimos 90 dias</strong>
            <span class="text-texto-suave"> e {{ semPlano === 1 ? 'ainda não tem' : 'ainda não têm' }} plano de ação.</span>
          </p>
          <Botao class="shrink-0 self-start sm:self-auto" :carregando="criandoPlanos" data-criar-planos @click="criarPlanos">
            <ClipboardList v-if="!criandoPlanos" class="size-4" aria-hidden="true" /> {{ rotuloCriarPlanos(semPlano) }}
          </Botao>
        </div>
      </div>
      <div class="mt-8 flex flex-wrap justify-center gap-2">
        <Botao v-if="tipo === 'respostas' && sessao.pode('respostas.ver')" :variante="semPlano > 0 ? 'secundario' : 'primario'" para="/respostas">Ver respostas</Botao>
        <Botao v-else para="/contatos">Ver contatos</Botao>
        <Botao variante="secundario" @click="recomecar">Importar outra planilha</Botao>
      </div>
    </section>
  </div>
</template>
