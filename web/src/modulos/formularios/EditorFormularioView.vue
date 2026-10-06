<script setup lang="ts">
// Editor de formulário (docs/api-etapa-5l.md §5.3): o documento de trabalho salva sozinho num rascunho e o que está no
// ar só muda ao clicar em "Publicar". Cabeçalho com o nome, a situação (publicado, versão, alterações não publicadas),
// o estado do salvamento, desfazer/refazer, problemas, descartar e publicar; abas Perguntas (3 colunas), Aparência,
// Compartilhar e Respostas (esta usa o publicado).
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { AlertTriangle, ArrowLeft, CircleAlert, CloudOff, Keyboard, LoaderCircle, Redo2, RefreshCw, Undo2 } from 'lucide-vue-next'
import { ApiError, formulariosApi, mensagemDoErro } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useMenuLateral } from '@/composables/menuLateral'
import { useSessaoStore } from '@/stores/sessao'
import { indicePrincipal, tipoPrincipal } from '@/pesquisa/logica'
import { TIPOS_FORMULARIO } from '@/utils/rotulos'
import Abas from '@/components/ui/Abas.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import AbaAparencia from './editor/AbaAparencia.vue'
import AbaCompartilhar from './editor/AbaCompartilhar.vue'
import AbaPerguntas from './editor/AbaPerguntas.vue'
import AbaRespostas from './editor/AbaRespostas.vue'
import AjudaAtalhos from './editor/AjudaAtalhos.vue'
import PainelProblemas from './editor/PainelProblemas.vue'
import PreVisualizacao from './editor/PreVisualizacao.vue'
import { criarEditor, fornecerEditor } from './editor/documento'
import { emCampoDeTexto, haQuanto, hora, tecla } from './editor/textos'
import type { Problema } from './validacaoFormulario'

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
const menu = useMenuLateral()
const podeEditar = computed(() => sessao.pode('formularios.editar'))
const nomeEmpresa = computed(() => sessao.conta?.nome ?? 'Sua empresa')

const editor = criarEditor({ formularioId: String(rota.params.id) })
fornecerEditor(editor)
const formulario = editor.formulario

const carregando = ref(true)
const erroCarga = ref<string | null>(null)
const naoExiste = ref(false)
const mudandoAtivo = ref(false)
const ajudaAberta = ref(false)
const abaPerguntas = ref<InstanceType<typeof AbaPerguntas> | null>(null)
// Relógio de minuto em minuto: "há 5 minutos" acompanha.
const agora = ref(Date.now())
let relogio: ReturnType<typeof setInterval> | undefined

const valida = (v: unknown): Aba => (ABAS.some((a) => a.valor === v) ? (v as Aba) : 'perguntas')
const aba = ref<Aba>(valida(rota.query.aba))
watch(aba, (a) => router.replace({ query: a === 'perguntas' ? {} : { aba: a } }))
const visitadas = reactive(new Set<Aba>([aba.value]))
watch(aba, (a) => visitadas.add(a))

const tipoAtual = computed(() => tipoPrincipal(editor.doc.perguntas))
const prefixoImagens = computed(() => formulario.value?.prefixo_imagens ?? null)
const qtdProblemas = computed(() => editor.problemas.value.length)
const qtdErros = computed(() => editor.erros.value.length)

// ── Nome e anotação interna (salvam na hora, fora do rascunho) ──
const nome = ref('')
const descricao = ref<string | null>('')
const erroDescricao = ref<string | null>(null)
const errosAparencia = computed(() => {
  const erros: Record<string, string> = {}
  if (erroDescricao.value) erros.descricao = erroDescricao.value
  return erros
})
let esperaDescricao: ReturnType<typeof setTimeout> | undefined
watch(descricao, (v) => {
  const f = formulario.value
  if (!f || !podeEditar.value || (v ?? '').trim() === (f.descricao ?? '').trim()) return
  clearTimeout(esperaDescricao)
  esperaDescricao = setTimeout(() => void salvarDescricao(), 1200)
})

async function salvarDescricao() {
  const f = formulario.value
  if (!f) return
  const nova = descricao.value?.trim() || null
  try {
    const r = await formulariosApi.atualizar(f.id, { descricao: nova })
    formulario.value = { ...f, descricao: r?.descricao ?? nova }
    erroDescricao.value = null
  } catch (e) {
    erroDescricao.value = e instanceof ApiError ? (e.campo('descricao') ?? e.mensagem) : mensagemDoErro(e)
  }
}
const erroNome = ref<string | null>(null)
const salvandoNome = ref(false)

async function salvarNome() {
  const f = formulario.value
  if (!f || !podeEditar.value) return
  const novo = nome.value.trim()
  if (novo === f.nome) {
    erroNome.value = null
    return
  }
  if (!novo) {
    erroNome.value = 'Dê um nome para o formulário.'
    return
  }
  salvandoNome.value = true
  try {
    const r = await formulariosApi.atualizar(f.id, { nome: novo })
    formulario.value = { ...f, nome: r?.nome ?? novo }
    nome.value = r?.nome ?? novo
    erroNome.value = null
    document.title = `${nome.value} · Toqqi`
  } catch (e) {
    erroNome.value = e instanceof ApiError ? (e.campo('nome') ?? e.mensagem) : mensagemDoErro(e)
  } finally {
    salvandoNome.value = false
  }
}

// ── Carregar ──
async function carregar() {
  carregando.value = true
  erroCarga.value = null
  naoExiste.value = false
  try {
    const f = await formulariosApi.obter(String(rota.params.id))
    editor.aplicarFormulario(f, { limparHistorico: true })
    nome.value = f.nome
    descricao.value = f.descricao ?? ''
    document.title = `${f.nome} · Toqqi`
    // Abre a nota principal (ou o primeiro item) para quem chega.
    if (!editor.selecionado.value && editor.doc.perguntas.length) {
      const ip = indicePrincipal(editor.doc.perguntas)
      editor.selecionado.value = editor.doc.perguntas[Math.max(0, ip)]!.id
    }
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) naoExiste.value = true
    else erroCarga.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

// ── Situação ──
const situacao = computed(() => {
  const f = formulario.value
  if (!f) return ''
  const quando = haQuanto(f.publicado_em ?? f.atualizado_em, agora.value)
  return `Publicado · versão ${f.versao ?? 1}${quando ? ` · ${quando}` : ''}`
})
const textoConflito = computed(() => {
  const c = editor.conflito.value
  const quem = c?.salvo_por_nome ? `por ${c.salvo_por_nome}` : ''
  const quando = c?.salvo_em ? `às ${hora(c.salvo_em)}` : ''
  const detalhe = [quem, quando].filter(Boolean).join(', ')
  return `Este formulário foi alterado em outra aba ou por outra pessoa${detalhe ? ` (${detalhe})` : ''}.`
})

// ── Ações ──
async function publicar() {
  if (!podeEditar.value) return
  const r = await editor.publicar()
  if (r.resultado === 'publicado') avisar.sucesso('Publicado. Quem abrir o link agora vê esta versão.')
  else if (r.resultado === 'sem_alteracoes') avisar.info(r.mensagem ?? 'Não há alterações para publicar.')
  else if (r.resultado === 'erro') avisar.erro(r.mensagem ?? 'Não foi possível publicar. Tente de novo.')
}

async function descartar() {
  const ok = await confirmar({
    titulo: 'Descartar as alterações?',
    mensagem: 'O formulário volta a ficar como está publicado. Se mudar de ideia logo depois, o Desfazer traz as alterações de volta.',
    confirmar: 'Descartar alterações',
    perigo: true,
  })
  if (!ok) return
  const r = await editor.descartar()
  if (r.ok) avisar.sucesso('Alterações descartadas. O formulário está como o publicado.')
  else avisar.erro(r.mensagem ?? 'Não foi possível descartar. Tente de novo.')
}

async function recarregar() {
  const ok = await confirmar({
    titulo: 'Recarregar o formulário?',
    mensagem: 'Você vai ver a versão salva por último. As mudanças feitas aqui depois disso se perdem.',
    confirmar: 'Recarregar',
    perigo: true,
  })
  if (!ok) return
  const r = await editor.recarregar()
  if (r.ok) nome.value = formulario.value?.nome ?? nome.value
  else avisar.erro(r.mensagem ?? 'Não foi possível recarregar.')
}

async function mudarAtivo(v: boolean) {
  const f = formulario.value
  if (!f) return
  mudandoAtivo.value = true
  try {
    const r = await formulariosApi.atualizar(f.id, { ativo: v })
    formulario.value = { ...f, ativo: r?.ativo ?? v }
    avisar.sucesso(v ? 'Formulário ativado: já pode receber respostas.' : 'Formulário desativado: ninguém consegue responder até você ativar de novo.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    mudandoAtivo.value = false
  }
}

function aoAtualizar(parcial: Record<string, unknown>) {
  const f = formulario.value
  if (!f) return
  formulario.value = { ...f, ...Object.fromEntries(Object.entries(parcial).filter(([, v]) => v !== undefined)) }
}

/** Clique num problema: seleciona o item (ou a aba) e leva o foco ao campo. */
function irParaProblema(p: Problema) {
  editor.painelProblemas.value = false
  if (p.alvo.tipo === 'tema') {
    aba.value = 'aparencia'
    return
  }
  aba.value = 'perguntas'
  if (p.alvo.tipo === 'item' || p.alvo.tipo === 'final') {
    editor.selecionado.value = p.alvo.id
    abaPerguntas.value?.focarCampo(p.campo ?? null, p.logica ?? null)
  }
}

// ── Atalhos (§5.3) ──
function algumaJanelaAberta(): boolean {
  return !!document.querySelector('[aria-modal="true"]')
}

function aoTeclar(e: KeyboardEvent) {
  if (!formulario.value || algumaJanelaAberta() || e.defaultPrevented) return
  const mod = e.ctrlKey || e.metaKey
  const alvo = e.target as HTMLElement | null
  const noTipTap = !!alvo?.closest?.('.ProseMirror')
  const tecla = e.key.toLowerCase()
  if (mod && tecla === 's') {
    e.preventDefault()
    if (podeEditar.value) void editor.salvar()
    return
  }
  if (!podeEditar.value) return
  if (mod && !e.altKey && ((tecla === 'z' && e.shiftKey) || (tecla === 'y' && !e.shiftKey))) {
    if (noTipTap) return // dentro do texto formatado, vale o refazer do próprio editor de texto
    e.preventDefault()
    editor.refazer()
    return
  }
  if (mod && !e.altKey && tecla === 'z') {
    if (noTipTap) return
    e.preventDefault()
    editor.desfazer()
    return
  }
  if (aba.value !== 'perguntas') return
  if (mod && !e.altKey && tecla === 'd') {
    e.preventDefault()
    abaPerguntas.value?.duplicarSelecionado()
    return
  }
  if (e.altKey && !mod && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    if (emCampoDeTexto(alvo)) return
    e.preventDefault()
    abaPerguntas.value?.moverSelecionado(e.key === 'ArrowUp' ? -1 : 1)
    return
  }
  if (mod || e.altKey || emCampoDeTexto(alvo)) return
  if (e.key === '/') {
    e.preventDefault()
    abaPerguntas.value?.abrirAdicionar()
  } else if (e.key === '?') {
    e.preventDefault()
    ajudaAberta.value = true
  }
}

// ── Sair com mudança não salva ──
function antesDeSair(e: BeforeUnloadEvent) {
  if (!editor.pendente()) return
  void editor.salvar()
  e.preventDefault()
  e.returnValue = ''
}

onBeforeRouteLeave(async () => {
  if (!editor.pendente()) return true
  if (editor.estado.value !== 'conflito' && (await editor.salvar())) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Algumas mudanças ainda não foram salvas no rascunho. Se sair agora, elas se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
})

onMounted(() => {
  carregar()
  menu.recolherNaTela(true)
  document.addEventListener('keydown', aoTeclar)
  window.addEventListener('beforeunload', antesDeSair)
  relogio = setInterval(() => (agora.value = Date.now()), 60_000)
})
onBeforeUnmount(() => {
  editor.encerrar()
  clearTimeout(esperaDescricao)
  menu.recolherNaTela(false)
  document.removeEventListener('keydown', aoTeclar)
  window.removeEventListener('beforeunload', antesDeSair)
  clearInterval(relogio)
})
</script>

<template>
  <div data-editor-formulario>
    <RouterLink to="/formularios" class="mb-3 inline-flex items-center gap-1.5 rounded-lg text-sm font-semibold text-texto-suave hover:text-texto">
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
      <header class="mb-4 flex flex-col gap-3 xl:flex-row xl:items-start" data-cabecalho-editor>
        <div class="min-w-0 flex-1">
          <label for="nome-formulario" class="sr-only">Nome do formulário</label>
          <input
            id="nome-formulario"
            v-model="nome"
            maxlength="120"
            :readonly="!podeEditar"
            class="titulo-pagina -mx-2 w-full rounded-lg border border-transparent bg-transparent px-2 py-0.5 hover:border-borda focus:border-marca focus:outline-none focus:ring-3 focus:ring-marca/20"
            :aria-invalid="erroNome ? 'true' : undefined"
            :aria-busy="salvandoNome || undefined"
            placeholder="Nome do formulário"
            data-nome-formulario
            @blur="salvarNome"
            @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
          />
          <p v-if="erroNome" class="mt-1 text-sm font-medium text-erro" role="alert">{{ erroNome }}</p>
          <div class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-sm text-texto-fraco">
            <Etiqueta :tom="TIPOS_FORMULARIO[tipoAtual].tom">{{ TIPOS_FORMULARIO[tipoAtual].rotulo }}</Etiqueta>
            <Etiqueta v-if="formulario.padrao_nps" tom="sucesso">Padrão NPS</Etiqueta>
            <Etiqueta v-if="formulario.padrao_csat" tom="sucesso">Padrão CSAT</Etiqueta>
            <span data-situacao>{{ situacao }}</span>
            <Etiqueta v-if="editor.temRascunho.value" tom="atencao" ponto data-alteracoes-nao-publicadas>Alterações não publicadas</Etiqueta>
            <!-- Estado do salvamento -->
            <span v-if="podeEditar" class="inline-flex items-center gap-1.5" :data-salvamento="editor.estado.value">
              <template v-if="editor.estado.value === 'salvando' || editor.estado.value === 'pendente'">
                <LoaderCircle class="size-3.5 animate-spin" aria-hidden="true" /> Salvando…
              </template>
              <template v-else-if="editor.estado.value === 'erro'">
                <CloudOff class="size-3.5 text-erro" aria-hidden="true" />
                <span class="font-medium text-erro" :title="editor.erroSalvar.value ?? undefined">Não foi possível salvar —</span>
                <button type="button" class="link text-sm" data-tentar-salvar @click="editor.salvar()">tentar de novo</button>
              </template>
              <template v-else-if="editor.estado.value === 'salvo' && editor.temRascunhoServidor.value">Rascunho salvo</template>
            </span>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2" role="toolbar" aria-label="Ações do formulário">
          <template v-if="podeEditar">
            <div class="flex items-center">
              <Botao variante="fantasma" tamanho="sm" :somente-icone="`Desfazer (${tecla('Ctrl+Z')})`" :desabilitado="!editor.historico.value.desfazer" data-desfazer @click="editor.desfazer()">
                <Undo2 class="size-4" aria-hidden="true" />
              </Botao>
              <Botao variante="fantasma" tamanho="sm" :somente-icone="`Refazer (${tecla('Ctrl+Shift+Z')})`" :desabilitado="!editor.historico.value.refazer" data-refazer @click="editor.refazer()">
                <Redo2 class="size-4" aria-hidden="true" />
              </Botao>
              <!-- Atalhos só fazem sentido com teclado: some no celular -->
              <span class="hidden md:contents">
                <Botao variante="fantasma" tamanho="sm" somente-icone="Atalhos do teclado (?)" @click="ajudaAberta = true">
                  <Keyboard class="size-4" aria-hidden="true" />
                </Botao>
              </span>
            </div>
            <Botao
              v-if="qtdProblemas"
              variante="secundario"
              tamanho="sm"
              :aria-label="`Problemas: ${qtdProblemas}`"
              data-botao-problemas
              @click="editor.painelProblemas.value = true"
            >
              <CircleAlert v-if="qtdErros" class="size-4 text-erro" aria-hidden="true" />
              <AlertTriangle v-else class="size-4 text-atencao" aria-hidden="true" />
              Problemas
              <span class="rounded-full px-1.5 text-xs font-bold" :class="qtdErros ? 'bg-erro-suave text-erro' : 'bg-atencao-suave text-atencao'">{{ qtdProblemas }}</span>
            </Botao>
            <Botao v-if="editor.temRascunho.value" variante="fantasma" tamanho="sm" :carregando="editor.descartando.value" data-descartar @click="descartar">
              Descartar alterações
            </Botao>
            <Botao
              :desabilitado="!editor.temRascunho.value || editor.estado.value === 'conflito'"
              :carregando="editor.publicando.value"
              data-publicar
              @click="publicar"
            >
              Publicar
            </Botao>
          </template>
          <div class="rounded-xl border border-borda bg-superficie px-3 py-1.5">
            <Interruptor
              :model-value="formulario.ativo"
              rotulo="Recebendo respostas"
              :desabilitado="!podeEditar || mudandoAtivo || formulario.padrao_nps || formulario.padrao_csat"
              @update:model-value="mudarAtivo"
            />
          </div>
        </div>
      </header>

      <Alerta v-if="!podeEditar" tom="info" class="mb-4">Seu perfil pode ver este formulário, mas não editar.</Alerta>

      <!-- Conflito (409 rascunho_desatualizado) -->
      <div v-if="editor.estado.value === 'conflito'" class="mb-4 flex flex-col gap-3 rounded-xl border border-atencao/30 bg-atencao-suave p-3.5 text-sm sm:flex-row sm:items-center" role="alert" data-faixa-conflito>
        <AlertTriangle class="size-5 shrink-0 text-atencao" aria-hidden="true" />
        <p class="flex-1 text-texto">{{ textoConflito }} Para não sobrescrever, recarregue antes de continuar.</p>
        <Botao variante="secundario" tamanho="sm" data-recarregar @click="recarregar"><RefreshCw class="size-4" aria-hidden="true" /> Recarregar</Botao>
      </div>

      <Abas v-model="aba" :abas="ABAS" rotulo="Seções do formulário">
        <AbaPerguntas
          v-if="visitadas.has('perguntas')"
          v-show="aba === 'perguntas'"
          ref="abaPerguntas"
          :pode-editar="podeEditar"
          :nome-empresa="nomeEmpresa"
          :formulario-id="formulario.id"
          :prefixo-imagens="prefixoImagens"
          :nome="nome"
        />
        <div v-if="visitadas.has('aparencia')" v-show="aba === 'aparencia'" class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <fieldset :disabled="!podeEditar" class="min-w-0">
            <AbaAparencia v-model:tema="editor.doc.tema" v-model:descricao="descricao" :erros="errosAparencia" :problemas="editor.problemas.value" :formulario-id="formulario.id" />
          </fieldset>
          <aside class="hidden xl:block" aria-label="Pré-visualização">
            <div class="sticky top-20 h-[calc(100dvh-9.5rem)]">
              <PreVisualizacao :nome="nome" :perguntas="editor.doc.perguntas" :tema="editor.doc.tema" :finais="editor.doc.finais" :nome-empresa="nomeEmpresa" :tipo="tipoAtual" :prefixo-imagens="prefixoImagens" />
            </div>
          </aside>
        </div>
        <AbaCompartilhar v-if="visitadas.has('compartilhar')" v-show="aba === 'compartilhar'" :formulario="formulario" :pode-editar="podeEditar" :alterado="editor.temRascunho.value" @atualizado="aoAtualizar" />
        <AbaRespostas v-if="visitadas.has('respostas')" v-show="aba === 'respostas'" :formulario-id="formulario.id" :perguntas="editor.publicado.value.perguntas" />
      </Abas>

      <PainelProblemas v-model:aberto="editor.painelProblemas.value" @ir="irParaProblema" />
      <AjudaAtalhos v-model:aberto="ajudaAberta" />
      <p class="sr-only" role="status" aria-live="polite">
        {{ editor.estado.value === 'erro' ? 'Não foi possível salvar o rascunho.' : editor.estado.value === 'conflito' ? 'Este formulário foi alterado em outro lugar.' : '' }}
      </p>
    </template>
  </div>
</template>
