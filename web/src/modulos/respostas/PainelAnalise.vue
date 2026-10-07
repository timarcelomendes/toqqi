<script setup lang="ts">
// Painel lateral "Analisar": tudo o que o cliente respondeu, o contexto do pedido, a análise da equipe
// (nota, comentário, o que faltou, o que combinamos, temas) e as ações ligadas à resposta.
import { computed, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Archive, ArchiveRestore, ArrowRight, Building2, ClipboardList, MoreHorizontal, Plus, Trash2, UserRound } from 'lucide-vue-next'
import { ApiError, mensagemDoErro, respostasApi, type Acao, type Id, type RespostaDetalhe, type RespostaItem, type TemaResposta } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData, formatarDataHora } from '@/utils/datas'
import { CANAIS } from '@/utils/rotulos'
import { ROTULOS_CONTEXTO, type CampoContexto } from '@/pesquisa/tipos'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import ModalNovaAcao, { type InicioAcao } from '@/modulos/acoes/ModalNovaAcao.vue'
import SeloAcao from '@/modulos/acoes/SeloAcao.vue'
import { prioridadeSugerida, tituloSugerido } from '@/modulos/acoes/logica'
import AnaliseIa from './AnaliseIa.vue'
import SeletorNota from './SeletorNota.vue'
import SeloNota from './SeloNota.vue'
import { analisada } from './ia'
import {
  LIMITE_ANALISE,
  LIMITE_COMENTARIO,
  ORIGENS_RESPOSTA,
  TEMAS_PADRAO,
  edicaoInicial,
  faixaDaNota,
  mudancasAnalise,
  quandoFoiResposta,
  rotuloCategoria,
  textoExclusao,
  tomCategoria,
  validarAnalise,
  type EdicaoAnalise,
} from './logica'

const props = withDefaults(defineProps<{ id: Id | null; temas?: TemaResposta[] }>(), { temas: () => TEMAS_PADRAO })
const emit = defineEmits<{ fechar: []; atualizada: [RespostaItem]; excluida: [Id] }>()

const sessao = useSessaoStore()
const podeEditar = computed(() => sessao.pode('respostas.editar'))
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()

const aberto = computed({
  get: () => props.id !== null,
  set: (v: boolean) => {
    if (!v) emit('fechar')
  },
})
const detalhe = ref<RespostaDetalhe | null>(null)
const carregando = ref(false)
const erroCarga = ref<string | null>(null)
const ocupado = ref<'arquivar' | 'excluir' | null>(null)
const edicao = reactive<EdicaoAnalise>({ nota: null, comentario: '', o_que_faltou: '', o_que_combinamos: '', temas: [] })
const locais = reactive<Record<string, string>>({})
const novaAcaoAberta = ref(false)

function aplicar(r: RespostaDetalhe) {
  detalhe.value = r
  Object.assign(edicao, edicaoInicial(r))
  for (const k of Object.keys(locais)) delete locais[k]
  limpar()
}

let pedido = 0
async function carregar() {
  const id = props.id
  if (id === null) return
  const meu = ++pedido
  carregando.value = true
  erroCarga.value = null
  detalhe.value = null
  try {
    const r = await respostasApi.obter(id)
    if (meu === pedido) aplicar(r)
  } catch (e) {
    if (meu !== pedido) return
    erroCarga.value = e instanceof ApiError && e.status === 404 ? 'Essa resposta não existe mais. Ela pode ter sido excluída.' : mensagemDoErro(e)
  } finally {
    if (meu === pedido) carregando.value = false
  }
}
watch(
  () => props.id,
  (id) => {
    if (id !== null) return carregar()
    pedido++
    detalhe.value = null
  },
  { immediate: true },
)

const faixa = computed(() => faixaDaNota(detalhe.value?.tipo_nota))
const mudancas = computed(() => (detalhe.value ? mudancasAnalise(detalhe.value, edicao, props.temas) : {}))
const alterado = computed(() => Object.keys(mudancas.value).length > 0)
const erro = (c: string) => locais[c] ?? erros[c] ?? null

const titulo = computed(() => (detalhe.value ? (detalhe.value.contato?.nome ?? 'Resposta sem identificação') : carregando.value ? 'Carregando…' : 'Resposta'))
const subtitulo = computed(() => {
  const r = detalhe.value
  if (!r) return undefined
  return [r.empresa?.nome, formatarData(r.data)].filter(Boolean).join(' · ')
})

const contexto = computed(() => {
  const r = detalhe.value
  if (!r) return []
  const itens = Object.entries(r.contexto ?? {})
    .filter(([, v]) => v)
    .map(([k, v]) => ({ rotulo: ROTULOS_CONTEXTO[k as CampoContexto] ?? k, valor: String(v) }))
  if (r.referencia) itens.unshift({ rotulo: 'Referência', valor: r.referencia })
  if (r.convite?.assunto) itens.push({ rotulo: 'Assunto do convite', valor: r.convite.assunto })
  if (r.convite?.evento) itens.push({ rotulo: 'Evento', valor: r.convite.evento.replace(/_/g, ' ') })
  return itens
})

/**
 * As perguntas do formulário com o que o cliente respondeu. Registrada à mão ou importada só tem a nota (e o
 * comentário, que tem campo próprio): as perguntas sem resposta não aparecem, para não encher de "—".
 */
const perguntas = computed(() => {
  const r = detalhe.value
  if (!r?.perguntas?.length) return []
  // Etapa 5l: blocos de conteúdo não têm resposta (a API já tira; aqui, por garantia).
  const lista = r.perguntas.filter((p) => p.tipo !== 'conteudo' && p.tipo !== 'quebra_pagina')
  return r.origem === 'pesquisa' ? lista : lista.filter((p) => p.resposta !== null && p.resposta !== '')
})

function alternarTema(chave: string) {
  edicao.temas = edicao.temas.includes(chave) ? edicao.temas.filter((t) => t !== chave) : [...edicao.temas, chave]
}

async function salvar() {
  if (!detalhe.value) return
  for (const k of Object.keys(locais)) delete locais[k]
  const v = validarAnalise(edicao, detalhe.value.tipo_nota)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    return
  }
  const dados = mudancas.value
  if (!Object.keys(dados).length) return
  const r = await executar(() => respostasApi.analisar(detalhe.value!.id, dados))
  if (!r) return
  // A API devolve o detalhe completo: a resposta da pergunta principal acompanha a nota nova.
  const novo = r as Partial<RespostaDetalhe>
  aplicar({
    ...detalhe.value,
    ...r,
    perguntas: novo.perguntas ?? detalhe.value.perguntas,
    convite: novo.convite !== undefined ? novo.convite : detalhe.value.convite,
    acoes: novo.acoes ?? detalhe.value.acoes,
  })
  emit('atualizada', r)
  avisar.sucesso(dados.nota !== undefined && detalhe.value?.acoes.length ? 'Análise salva. A ação que já existia continua como estava.' : 'Análise salva.')
}

async function arquivarOuRestaurar() {
  const r0 = detalhe.value
  if (!r0) return
  ocupado.value = 'arquivar'
  try {
    const r = r0.arquivada ? await respostasApi.restaurar(r0.id) : await respostasApi.arquivar(r0.id)
    detalhe.value = { ...r0, ...r, perguntas: r0.perguntas, convite: r0.convite, acoes: r0.acoes }
    emit('atualizada', r)
    avisar.sucesso(r.arquivada ? 'Resposta arquivada: ela saiu dos números do painel e das métricas.' : 'Resposta restaurada: ela voltou a contar nos números.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function excluir() {
  const r = detalhe.value
  if (!r) return
  const t = textoExclusao(r, r.acoes?.length ?? 0)
  const ok = await confirmar({ titulo: t.titulo, mensagem: t.mensagem, confirmar: t.confirmar, perigo: true })
  if (!ok) return
  ocupado.value = 'excluir'
  try {
    await respostasApi.excluir(r.id)
    avisar.sucesso('Resposta excluída.')
    emit('excluida', r.id)
    detalhe.value = null
    emit('fechar')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function antesDeFechar(): Promise<boolean> {
  if (!alterado.value || enviando.value) return true
  return confirmar({
    titulo: 'Sair sem salvar a análise?',
    mensagem: 'Você mudou a análise desta resposta e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
}

// Links de dentro do painel (abrir a ação, a ficha do contato) também passam pela pergunta de "sair sem salvar".
onBeforeRouteLeave(() => (props.id === null ? true : antesDeFechar()))

const inicioAcao = computed<InicioAcao | null>(() => {
  const r = detalhe.value
  if (!r) return null
  return {
    titulo: tituloSugerido(r),
    descricao: [r.comentario ? `Comentário do cliente: ${r.comentario}` : '', r.contato ? `Contato: ${r.contato.nome}${r.contato.email ? ` (${r.contato.email})` : ''}` : '']
      .filter(Boolean)
      .join('\n'),
    empresa: r.empresa ? { id: r.empresa.id, nome: r.empresa.nome } : null,
    contato: r.contato ? { id: r.contato.id, nome: r.contato.nome } : null,
    resposta_id: r.id,
    prioridade: prioridadeSugerida(r.grupo),
    origem: `A partir da resposta de ${r.contato?.nome ?? 'cliente sem cadastro'}${typeof r.nota === 'number' ? `, nota ${r.nota}` : ''}.`,
  }
})

function aoCriarAcao(a: Acao) {
  const r = detalhe.value
  if (!r) return
  const resumo = { id: a.id, situacao: a.situacao, prazo: a.prazo, prazo_selo: a.prazo_selo }
  detalhe.value = { ...r, acao: r.acao ?? resumo, acoes: [...(r.acoes ?? []), { ...resumo, titulo: a.titulo }] }
  emit('atualizada', detalhe.value)
}
</script>

<template>
  <PainelLateral v-model:aberto="aberto" :titulo="titulo" :descricao="subtitulo" largura="lg" :bloqueado="enviando || !!ocupado" :antes-de-fechar="antesDeFechar">
    <Carregando v-if="carregando" :linhas="5" rotulo="Carregando a resposta" />
    <Alerta v-else-if="erroCarga" tom="erro">
      {{ erroCarga }} <button v-if="!erroCarga.includes('não existe')" type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <div v-else-if="detalhe" class="flex flex-col gap-6">
      <!-- Resumo -->
      <div class="flex items-start gap-4">
        <SeloNota :nota="detalhe.nota" :grupo="detalhe.grupo" :tipo="detalhe.tipo_nota" tamanho="lg" />
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-1.5">
            <Etiqueta v-if="detalhe.grupo" :tom="tomCategoria(detalhe.grupo)" ponto>
              {{ rotuloCategoria(detalhe.grupo) }}
            </Etiqueta>
            <Etiqueta v-if="detalhe.tipo_nota" tom="neutro">{{ detalhe.tipo_nota === 'csat' ? 'CSAT (1 a 5)' : 'NPS (0 a 10)' }}</Etiqueta>
            <Etiqueta v-if="detalhe.arquivada" tom="neutro">Arquivada</Etiqueta>
            <Etiqueta v-if="detalhe.edicoes" tom="info" data-editada>Editada pelo cliente</Etiqueta>
          </div>
          <!-- Com data informada (à mão ou importada), a hora não quer dizer nada: só o dia. -->
          <p class="mt-1.5 text-sm text-texto-suave">{{ quandoFoiResposta(detalhe) }} · {{ CANAIS[detalhe.canal] ?? detalhe.canal }}</p>
          <p class="text-xs text-texto-fraco">
            {{ ORIGENS_RESPOSTA[detalhe.origem] ?? detalhe.origem }}<template v-if="detalhe.registrada_por"> ({{ detalhe.registrada_por.nome }})</template>
            <template v-if="detalhe.formulario?.nome"> · {{ detalhe.formulario.nome }}</template>
          </p>
          <p v-if="detalhe.edicoes && detalhe.editada_em" class="text-xs text-texto-fraco" data-quando-editada>
            O cliente mudou a resposta {{ detalhe.edicoes === 1 ? 'uma vez' : `${detalhe.edicoes} vezes` }}, a última em {{ formatarDataHora(detalhe.editada_em) }}.
          </p>
        </div>
      </div>

      <Alerta v-if="detalhe.arquivada" tom="info" titulo="Resposta arquivada">
        Ela não entra no NPS, no painel nem nas métricas. Use "Restaurar" para voltar a contar.
      </Alerta>

      <!-- Contato -->
      <section v-if="detalhe.contato || detalhe.empresa" class="grid grid-cols-1 gap-3 rounded-xl bg-superficie-2 p-4 text-sm sm:grid-cols-2" aria-label="Quem respondeu">
        <div v-if="detalhe.contato" class="flex min-w-0 items-start gap-2">
          <UserRound class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
          <div class="min-w-0">
            <RouterLink v-if="sessao.pode('contatos.ver')" :to="`/contatos/${detalhe.contato.id}`" class="link block truncate">{{ detalhe.contato.nome }}</RouterLink>
            <p v-else class="truncate font-semibold text-texto">{{ detalhe.contato.nome }}</p>
            <p v-if="detalhe.contato.email" class="truncate text-texto-fraco">{{ detalhe.contato.email }}</p>
            <p v-if="detalhe.contato.perfil" class="text-texto-fraco">Perfil: {{ detalhe.contato.perfil.nome }}</p>
          </div>
        </div>
        <div v-if="detalhe.empresa" class="flex min-w-0 items-start gap-2">
          <Building2 class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
          <div class="min-w-0">
            <p class="truncate font-semibold text-texto">{{ detalhe.empresa.nome }}</p>
            <p v-if="detalhe.empresa.grupo" class="text-texto-fraco">Grupo: {{ detalhe.empresa.grupo.nome }}</p>
          </div>
        </div>
      </section>

      <!-- Todas as perguntas -->
      <section aria-labelledby="t-respondeu">
        <h3 id="t-respondeu" class="mb-2 text-sm font-bold uppercase tracking-wide text-texto-fraco">O que o cliente respondeu</h3>
        <dl v-if="perguntas.length" class="flex flex-col divide-y divide-borda rounded-xl border border-borda">
          <div v-for="p in perguntas" :key="p.id" class="px-4 py-3">
            <dt class="text-sm text-texto-suave">{{ p.titulo }}</dt>
            <dd class="mt-0.5 whitespace-pre-line break-words font-semibold text-texto">{{ p.resposta || '—' }}</dd>
          </div>
        </dl>
        <p v-else class="text-sm text-texto-fraco">Esta resposta não tem perguntas guardadas (foi registrada à mão ou importada).</p>
      </section>

      <!-- Etapa 4b: resumo, tom e temas pela IA (ou em que pé está a análise, com a IA ativa na conta) -->
      <AnaliseIa v-if="detalhe.ia && (sessao.conta?.ia_ativa || analisada(detalhe.ia))" :ia="detalhe.ia" :temas="temas" />

      <!-- Contexto do pedido -->
      <section v-if="contexto.length" aria-labelledby="t-contexto">
        <h3 id="t-contexto" class="mb-2 text-sm font-bold uppercase tracking-wide text-texto-fraco">Sobre o pedido ou a entrega</h3>
        <dl class="grid grid-cols-1 gap-x-4 gap-y-2 rounded-xl border border-borda p-4 text-sm sm:grid-cols-2">
          <div v-for="c in contexto" :key="c.rotulo" class="min-w-0">
            <dt class="text-texto-fraco">{{ c.rotulo }}</dt>
            <dd class="break-words font-semibold text-texto">{{ c.valor }}</dd>
          </div>
        </dl>
      </section>

      <!-- Análise -->
      <section aria-labelledby="t-analise">
        <h3 id="t-analise" class="mb-1 text-sm font-bold uppercase tracking-wide text-texto-fraco">Análise da equipe</h3>
        <p v-if="detalhe.analisada_em" class="mb-3 text-xs text-texto-fraco">
          Analisada<template v-if="detalhe.analisada_por"> por {{ detalhe.analisada_por.nome }}</template> em {{ formatarDataHora(detalhe.analisada_em) }}.
        </p>
        <form v-if="podeEditar" id="form-analise" class="flex flex-col gap-5" novalidate @submit.prevent="salvar">
          <Alerta v-if="erroGeral && !Object.keys(erros).length" tom="erro">{{ erroGeral }}</Alerta>
          <SeletorNota
            v-if="faixa && detalhe.tipo_nota"
            v-model="edicao.nota"
            :tipo="detalhe.tipo_nota"
            rotulo="Nota"
            :erro="erro('nota')"
            :dica="edicao.nota !== detalhe.nota ? 'Mudar a nota muda a categoria. A ação que já foi criada continua como está.' : undefined"
          />
          <AreaTexto v-model="edicao.comentario" rotulo="Comentário do cliente" :linhas="3" :maximo="LIMITE_COMENTARIO" :erro="erro('comentario')" />
          <AreaTexto
            v-model="edicao.o_que_faltou"
            rotulo="O que faltou"
            opcional
            :linhas="2"
            :maximo="LIMITE_ANALISE"
            placeholder="Na visão do cliente, o que deu errado ou faltou."
            :erro="erro('o_que_faltou')"
          />
          <AreaTexto
            v-model="edicao.o_que_combinamos"
            rotulo="O que combinamos com o cliente"
            opcional
            :linhas="2"
            :maximo="LIMITE_ANALISE"
            placeholder="O que foi prometido, por quem e até quando."
            :erro="erro('o_que_combinamos')"
          />
          <fieldset class="flex flex-col gap-2" :aria-describedby="erro('temas') ? 'erro-temas' : 'dica-temas'">
            <legend class="mb-1 text-sm font-semibold text-texto">Temas</legend>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="t in temas"
                :key="t.chave"
                type="button"
                class="inline-flex min-h-10 items-center gap-1.5 rounded-xl border px-3 text-sm font-semibold transition-colors"
                :class="edicao.temas.includes(t.chave) ? 'border-marca bg-marca-suave text-marca-texto' : 'border-borda-forte text-texto-suave hover:bg-superficie-2'"
                :aria-pressed="edicao.temas.includes(t.chave)"
                @click="alternarTema(t.chave)"
              >
                {{ t.rotulo }}
              </button>
            </div>
            <p v-if="erro('temas')" id="erro-temas" class="text-sm font-medium text-erro">{{ erro('temas') }}</p>
            <p id="dica-temas" class="text-xs text-texto-fraco">
              {{
                detalhe.temas_manuais
                  ? 'Escolhidos por alguém da equipe: não mudam sozinhos se o comentário mudar.'
                  : analisada(detalhe.ia)
                    ? 'Marcados pela IA a partir do comentário. Se você mudar, a escolha passa a ser sua.'
                    : 'Marcados sozinhos pelas palavras do comentário. Se você mudar, a escolha passa a ser sua.'
              }}
            </p>
          </fieldset>
        </form>
        <dl v-else class="flex flex-col gap-3 text-sm">
          <div>
            <dt class="text-texto-fraco">Comentário do cliente</dt>
            <dd class="whitespace-pre-line text-texto">{{ detalhe.comentario || '—' }}</dd>
          </div>
          <div>
            <dt class="text-texto-fraco">O que faltou</dt>
            <dd class="whitespace-pre-line text-texto">{{ detalhe.o_que_faltou || '—' }}</dd>
          </div>
          <div>
            <dt class="text-texto-fraco">O que combinamos com o cliente</dt>
            <dd class="whitespace-pre-line text-texto">{{ detalhe.o_que_combinamos || '—' }}</dd>
          </div>
          <div>
            <dt class="text-texto-fraco">Temas</dt>
            <dd class="mt-1 flex flex-wrap gap-1.5">
              <Etiqueta v-for="t in detalhe.temas" :key="t" tom="info">{{ temas.find((x) => x.chave === t)?.rotulo ?? t }}</Etiqueta>
              <span v-if="!detalhe.temas.length" class="text-texto">—</span>
            </dd>
          </div>
        </dl>
      </section>

      <!-- Ações ligadas -->
      <section aria-labelledby="t-acoes-resposta">
        <h3 id="t-acoes-resposta" class="mb-2 text-sm font-bold uppercase tracking-wide text-texto-fraco">Plano de ação</h3>
        <ul v-if="detalhe.acoes?.length" class="flex flex-col divide-y divide-borda rounded-xl border border-borda">
          <li v-for="a in detalhe.acoes" :key="String(a.id)" class="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <p class="text-sm font-semibold text-texto">{{ a.titulo }}</p>
              <SeloAcao :acao="a" class="mt-1" />
            </div>
            <Botao v-if="sessao.pode('acoes.ver')" variante="secundario" tamanho="sm" class="!h-10 shrink-0" :para="`/planos-de-acao/${a.id}`">
              Abrir ação <ArrowRight class="size-4" aria-hidden="true" />
            </Botao>
          </li>
        </ul>
        <div v-else class="flex flex-col gap-3 rounded-xl border border-dashed border-borda-forte p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <p class="flex items-center gap-2 text-texto-suave">
            <ClipboardList class="size-4 shrink-0 text-texto-fraco" aria-hidden="true" /> Nenhuma ação ligada a esta resposta.
          </p>
          <Botao v-if="sessao.pode('acoes.tratar')" variante="secundario" tamanho="sm" class="!h-10" @click="novaAcaoAberta = true">
            <Plus class="size-4" aria-hidden="true" /> Criar ação
          </Botao>
        </div>
        <button
          v-if="detalhe.acoes?.length && sessao.pode('acoes.tratar')"
          type="button"
          class="link mt-2 inline-flex min-h-10 items-center gap-1 text-sm"
          @click="novaAcaoAberta = true"
        >
          <Plus class="size-4" aria-hidden="true" /> Criar outra ação
        </button>
      </section>
    </div>

    <template v-if="detalhe" #rodape>
      <!-- Celular: salvar à vista e o resto num menu (o rodapé não toma a tela) -->
      <MenuSuspenso v-if="podeEditar || sessao.admin" rotulo="Mais opções desta resposta" alinhar="esquerda" fixo class="sm:hidden">
        <template #gatilho="{ props }">
          <Botao v-bind="props" variante="secundario" :carregando="!!ocupado" :desabilitado="enviando">
            <MoreHorizontal v-if="!ocupado" class="size-4" aria-hidden="true" /> Mais
          </Botao>
        </template>
        <ItemMenu v-if="podeEditar" :icone="detalhe.arquivada ? ArchiveRestore : Archive" @click="arquivarOuRestaurar">
          {{ detalhe.arquivada ? 'Restaurar' : 'Arquivar' }}
        </ItemMenu>
        <ItemMenu v-if="sessao.admin" :icone="Trash2" perigo @click="excluir">Excluir de vez</ItemMenu>
      </MenuSuspenso>
      <div class="hidden sm:contents">
        <Botao
          v-if="sessao.admin"
          variante="perigo-suave"
          class="mr-auto"
          :carregando="ocupado === 'excluir'"
          :desabilitado="enviando || ocupado === 'arquivar'"
          @click="excluir"
        >
          <Trash2 v-if="ocupado !== 'excluir'" class="size-4" aria-hidden="true" /> Excluir de vez
        </Botao>
        <Botao
          v-if="podeEditar"
          variante="secundario"
          :carregando="ocupado === 'arquivar'"
          :desabilitado="enviando || ocupado === 'excluir'"
          @click="arquivarOuRestaurar"
        >
          <template v-if="ocupado !== 'arquivar'">
            <ArchiveRestore v-if="detalhe.arquivada" class="size-4" aria-hidden="true" />
            <Archive v-else class="size-4" aria-hidden="true" />
          </template>
          {{ detalhe.arquivada ? 'Restaurar' : 'Arquivar' }}
        </Botao>
      </div>
      <Botao v-if="podeEditar" tipo="submit" form="form-analise" class="flex-1 sm:flex-none" :carregando="enviando" :desabilitado="!alterado || !!ocupado">
        Salvar análise
      </Botao>
    </template>
  </PainelLateral>

  <ModalNovaAcao v-model:aberto="novaAcaoAberta" :inicio="inicioAcao" @criada="aoCriarAcao" />
</template>
