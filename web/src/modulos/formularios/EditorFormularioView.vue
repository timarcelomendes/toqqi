<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Eye } from 'lucide-vue-next'
import { ApiError, formulariosApi, mensagemDoErro, type Formulario, type Pergunta, type Tema } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { indicePrincipal, tipoPrincipal } from '@/pesquisa/logica'
import { TEMA_PADRAO } from '@/pesquisa/tipos'
import { formatarDataHora } from '@/utils/datas'
import { TIPOS_FORMULARIO } from '@/utils/rotulos'
import Abas from '@/components/ui/Abas.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Modal from '@/components/ui/Modal.vue'
import AbaAparencia from './editor/AbaAparencia.vue'
import AbaCompartilhar from './editor/AbaCompartilhar.vue'
import AbaPerguntas from './editor/AbaPerguntas.vue'
import AbaRespostas from './editor/AbaRespostas.vue'
import PreVisualizacao from './editor/PreVisualizacao.vue'
import { errosPorPergunta, validarFormulario } from './validacaoFormulario'

type Aba = 'perguntas' | 'aparencia' | 'compartilhar' | 'respostas'
const ABAS: { valor: Aba; rotulo: string }[] = [
  { valor: 'perguntas', rotulo: 'Perguntas' },
  { valor: 'aparencia', rotulo: 'Aparência' },
  { valor: 'compartilhar', rotulo: 'Compartilhar' },
  { valor: 'respostas', rotulo: 'Respostas' },
]

const rota = useRoute()
const router = useRouter()
const sessao = useSessaoStore()
const podeEditar = computed(() => sessao.pode('formularios.editar'))
const nomeEmpresa = computed(() => sessao.conta?.nome ?? 'Sua empresa')

const formulario = ref<Formulario | null>(null)
const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const naoExiste = ref(false)
const salvando = ref(false)
const mudandoAtivo = ref(false)
const erroSalvar = ref<string | null>(null)
const erros = ref<Record<string, string>>({})
const selecionada = ref<string | null>(null)
const previaAberta = ref(false)

const valida = (v: unknown): Aba => (ABAS.some((a) => a.valor === v) ? (v as Aba) : 'perguntas')
const aba = ref<Aba>(valida(rota.query.aba))
watch(aba, (a) => router.replace({ query: a === 'perguntas' ? {} : { aba: a } }))
const visitadas = reactive(new Set<Aba>([aba.value]))
watch(aba, (a) => visitadas.add(a))

// Rascunho: o que a pessoa está editando. `salvo` guarda a versão do servidor para comparar.
const rascunho = reactive({ nome: '', descricao: '' as string | null, perguntas: [] as Pergunta[], tema: { ...TEMA_PADRAO } as Tema })
const salvo = ref('')
const editavel = () => ({ nome: rascunho.nome, descricao: rascunho.descricao || null, perguntas: rascunho.perguntas, tema: rascunho.tema })
const alterado = computed(() => !!formulario.value && JSON.stringify(editavel()) !== salvo.value)

const tipoAtual = computed(() => tipoPrincipal(rascunho.perguntas))
const errosPerguntas = computed(() => errosPorPergunta(erros.value))
const qtdErrosPerguntas = computed(() => Object.keys(errosPerguntas.value).length)

function aplicar(f: Formulario) {
  formulario.value = f
  rascunho.nome = f.nome
  rascunho.descricao = f.descricao ?? ''
  rascunho.perguntas = JSON.parse(JSON.stringify(f.perguntas ?? [])) as Pergunta[]
  rascunho.tema = { ...TEMA_PADRAO, ...JSON.parse(JSON.stringify(f.tema ?? {})) } as Tema
  salvo.value = JSON.stringify(editavel())
  document.title = `${f.nome} · Toqqi`
}

async function carregar() {
  carregando.value = true
  erroCarga.value = null
  naoExiste.value = false
  try {
    aplicar(await formulariosApi.obter(String(rota.params.id)))
    // Abre a primeira pergunta para quem chega num formulário novo.
    if (!selecionada.value && rascunho.perguntas.length && podeEditar.value) {
      const ip = indicePrincipal(rascunho.perguntas)
      selecionada.value = rascunho.perguntas[Math.max(0, ip)]!.id
    }
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) naoExiste.value = true
    else erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

// Validação local some assim que a pessoa mexe (evita erro "velho" apontando o índice errado).
watch(
  () => JSON.stringify(rascunho.perguntas),
  () => {
    if (Object.keys(erros.value).some((k) => k.startsWith('perguntas'))) {
      erros.value = Object.fromEntries(Object.entries(erros.value).filter(([k]) => !k.startsWith('perguntas')))
    }
  },
)

function mostrarErros(novos: Record<string, string>) {
  erros.value = novos
  const pp = errosPorPergunta(novos)
  const primeiro = Object.keys(pp).map(Number).sort((a, b) => a - b)[0]
  if (primeiro !== undefined) {
    aba.value = 'perguntas'
    selecionada.value = rascunho.perguntas[primeiro]?.id ?? selecionada.value
  } else if (Object.keys(novos).some((k) => k.startsWith('tema') || k === 'descricao')) {
    aba.value = 'aparencia'
  }
}

async function salvar() {
  if (!formulario.value || !podeEditar.value || salvando.value || !alterado.value) return
  erroSalvar.value = null
  const locais = validarFormulario(rascunho.perguntas, rascunho.nome)
  if (Object.keys(locais).length) {
    mostrarErros(locais)
    erroSalvar.value = locais.nome ?? 'Algumas perguntas precisam de ajuste antes de salvar.'
    return
  }
  salvando.value = true
  try {
    const f = await formulariosApi.atualizar(formulario.value.id, {
      nome: rascunho.nome.trim(),
      descricao: rascunho.descricao?.trim() || null,
      perguntas: rascunho.perguntas,
      tema: rascunho.tema,
    })
    // Mantém ativo/publico/padrões atualizados mesmo se a resposta vier resumida.
    aplicar({ ...formulario.value, ...f })
    erros.value = {}
    avisar.sucesso('Formulário salvo.')
  } catch (e) {
    if (e instanceof ApiError) {
      if (Object.keys(e.campos).length) mostrarErros(e.campos)
      erroSalvar.value = e.codigo === 'formulario_padrao' ? e.mensagem : Object.keys(e.campos).length ? `${e.mensagem} Confira os itens marcados.` : e.mensagem
    } else erroSalvar.value = mensagemDoErro(e)
  } finally {
    salvando.value = false
  }
}

async function descartar() {
  const ok = await confirmar({
    titulo: 'Descartar as alterações?',
    mensagem: 'Tudo volta a ficar como estava na última vez que você salvou.',
    confirmar: 'Descartar',
    perigo: true,
  })
  if (ok && formulario.value) {
    aplicar(formulario.value)
    erros.value = {}
    erroSalvar.value = null
  }
}

async function mudarAtivo(v: boolean) {
  if (!formulario.value) return
  mudandoAtivo.value = true
  try {
    const f = await formulariosApi.atualizar(formulario.value.id, { ativo: v })
    formulario.value = { ...formulario.value, ativo: f?.ativo ?? v }
    avisar.sucesso(v ? 'Formulário ativado: já pode receber respostas.' : 'Formulário desativado: ninguém consegue responder até você ativar de novo.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    mudandoAtivo.value = false
  }
}

function aoAtualizar(parcial: Partial<Formulario>) {
  if (!formulario.value) return
  // Quem vira padrão tira o padrão do outro; aqui só refletimos este formulário.
  formulario.value = { ...formulario.value, ...Object.fromEntries(Object.entries(parcial).filter(([, v]) => v !== undefined)) }
}

// Ctrl/Cmd + S salva.
function atalho(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault()
    salvar()
  }
}
function antesDeSair(e: BeforeUnloadEvent) {
  if (!alterado.value) return
  e.preventDefault()
  e.returnValue = ''
}

onBeforeRouteLeave(async () => {
  if (!alterado.value) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Você mudou o formulário e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
})

watch(
  () => rota.params.id,
  (novo, antigo) => {
    if (novo && novo !== antigo) carregar()
  },
)

onMounted(() => {
  carregar()
  document.addEventListener('keydown', atalho)
  window.addEventListener('beforeunload', antesDeSair)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', atalho)
  window.removeEventListener('beforeunload', antesDeSair)
})
</script>

<template>
  <div>
    <RouterLink to="/formularios" class="mb-4 inline-flex items-center gap-1.5 rounded-lg text-sm font-semibold text-texto-suave hover:text-texto">
      <ArrowLeft class="size-4" aria-hidden="true" /> Formulários
    </RouterLink>

    <Carregando v-if="carregando" :linhas="5" />
    <div v-else-if="naoExiste" class="cartao">
      <EstadoVazio titulo="Formulário não encontrado" descricao="Ele pode ter sido excluído ou arquivado.">
        <Botao para="/formularios" variante="secundario">Ver formulários</Botao>
      </EstadoVazio>
    </div>
    <Alerta v-else-if="erroCarga" tom="erro">
      {{ erroCarga }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-else-if="formulario">
      <!-- Cabeçalho -->
      <header class="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start">
        <div class="min-w-0 flex-1">
          <label for="nome-formulario" class="sr-only">Nome do formulário</label>
          <input
            id="nome-formulario"
            v-model="rascunho.nome"
            maxlength="120"
            :readonly="!podeEditar"
            class="titulo-pagina -mx-2 w-full rounded-lg border border-transparent bg-transparent px-2 py-0.5 hover:border-borda focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20"
            :aria-invalid="erros.nome ? 'true' : undefined"
            placeholder="Nome do formulário"
          />
          <p v-if="erros.nome" class="mt-1 text-sm font-medium text-erro">{{ erros.nome }}</p>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-sm text-texto-fraco">
            <Etiqueta :tom="TIPOS_FORMULARIO[tipoAtual].tom">{{ TIPOS_FORMULARIO[tipoAtual].rotulo }}</Etiqueta>
            <Etiqueta v-if="formulario.padrao_nps" tom="sucesso">Padrão NPS</Etiqueta>
            <Etiqueta v-if="formulario.padrao_csat" tom="sucesso">Padrão CSAT</Etiqueta>
            <span>Salvo em {{ formatarDataHora(formulario.atualizado_em) }}</span>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <div class="rounded-xl border border-borda bg-superficie px-3 py-2">
            <Interruptor
              :model-value="formulario.ativo"
              rotulo="Recebendo respostas"
              :desabilitado="!podeEditar || mudandoAtivo || formulario.padrao_nps || formulario.padrao_csat"
              @update:model-value="mudarAtivo"
            />
          </div>
          <Botao variante="secundario" class="xl:hidden" @click="previaAberta = true"><Eye class="size-4" aria-hidden="true" /> Pré-visualizar</Botao>
          <Botao v-if="podeEditar" :desabilitado="!alterado" :carregando="salvando" title="Salvar (Ctrl+S)" @click="salvar">Salvar</Botao>
        </div>
      </header>

      <Alerta v-if="!podeEditar" tom="info" class="mb-4">Seu perfil pode ver este formulário, mas não editar.</Alerta>
      <Alerta v-if="erroSalvar" tom="erro" class="mb-4">{{ erroSalvar }}</Alerta>

      <!-- A coluna da pré-visualização só existe nas abas que a mostram (nas outras, o conteúdo usa a largura toda). -->
      <div class="grid gap-6" :class="aba === 'perguntas' || aba === 'aparencia' ? 'xl:grid-cols-[minmax(0,1fr)_24rem]' : ''">
        <div class="min-w-0">
          <Abas v-model="aba" :abas="ABAS.map((a) => (a.valor === 'perguntas' && qtdErrosPerguntas ? { ...a, rotulo: `Perguntas (${qtdErrosPerguntas} com ajuste)` } : a))" rotulo="Seções do formulário">
            <AbaPerguntas
              v-if="visitadas.has('perguntas')"
              v-show="aba === 'perguntas'"
              v-model="rascunho.perguntas"
              v-model:selecionada="selecionada"
              :erros="errosPerguntas"
              :pode-editar="podeEditar"
              :nome-empresa="nomeEmpresa"
            />
            <fieldset v-if="visitadas.has('aparencia')" v-show="aba === 'aparencia'" :disabled="!podeEditar" class="min-w-0">
              <AbaAparencia v-model:tema="rascunho.tema" v-model:descricao="rascunho.descricao" :erros="erros" :formulario-id="formulario.id" />
            </fieldset>
            <AbaCompartilhar v-if="visitadas.has('compartilhar')" v-show="aba === 'compartilhar'" :formulario="formulario" :pode-editar="podeEditar" :alterado="alterado" @atualizado="aoAtualizar" />
            <AbaRespostas v-if="visitadas.has('respostas')" v-show="aba === 'respostas'" :formulario-id="formulario.id" :perguntas="formulario.perguntas" />
          </Abas>
        </div>

        <!-- Pré-visualização ao lado (telas grandes) -->
        <aside v-if="aba === 'perguntas' || aba === 'aparencia'" class="hidden xl:block" aria-label="Pré-visualização">
          <!-- termina acima do botão do assistente, que fica no canto da tela -->
          <div class="sticky top-20 h-[calc(100dvh-9.5rem)]">
            <PreVisualizacao :nome="rascunho.nome" :perguntas="rascunho.perguntas" :tema="rascunho.tema" :nome-empresa="nomeEmpresa" :tipo="tipoAtual" />
          </div>
        </aside>
      </div>

      <!-- Barra de salvar -->
      <Transition enter-from-class="translate-y-full opacity-0" enter-active-class="transition duration-200" leave-active-class="transition duration-150" leave-to-class="translate-y-full opacity-0">
        <div v-if="alterado && podeEditar" data-barra-fixa class="sticky bottom-4 z-20 mt-6">
          <div class="flex flex-col gap-3 rounded-2xl border border-borda bg-superficie p-4 shadow-xl sm:flex-row sm:items-center" role="region" aria-label="Alterações não salvas">
            <p class="flex-1 text-sm font-semibold text-texto">
              Você tem alterações não salvas. <span class="hidden font-normal text-texto-fraco sm:inline">Dica: Ctrl+S (ou ⌘+S) salva.</span>
            </p>
            <div class="flex gap-2">
              <Botao variante="secundario" :desabilitado="salvando" @click="descartar">Descartar</Botao>
              <Botao :carregando="salvando" @click="salvar">Salvar</Botao>
            </div>
          </div>
        </div>
      </Transition>

      <Modal v-model:aberto="previaAberta" titulo="Pré-visualização" descricao="É assim que seu cliente vê. Nada é gravado." tamanho="lg">
        <div class="-mx-5 -my-5 h-[70dvh] sm:-mx-6">
          <PreVisualizacao :nome="rascunho.nome" :perguntas="rascunho.perguntas" :tema="rascunho.tema" :nome-empresa="nomeEmpresa" :tipo="tipoAtual" :titulo="false" />
        </div>
      </Modal>
    </template>
  </div>
</template>
