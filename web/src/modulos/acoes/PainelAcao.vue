<script setup lang="ts">
// Painel lateral de uma ação: ver e editar tudo (título, descrição, o que foi feito, responsável, prioridade,
// prazo, situação, empresa) e ver a resposta que deu origem. Concluir pede responsável e o que foi feito.
// Etapa 5d: abaixo da descrição, os passos sugeridos pela IA (relê a ação enquanto estão sendo sugeridos).
import { computed, nextTick, reactive, ref, toRaw, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ArrowRight, MessageSquareText, MoreHorizontal, Trash2 } from 'lucide-vue-next'
import { acoesApi, mensagemDoErro, type Acao, type SituacaoAcao } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData, formatarDataHora } from '@/utils/datas'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import Selecao from '@/components/ui/Selecao.vue'
import CampoEmpresa from '@/modulos/contatos/CampoEmpresa.vue'
import SeloNota from '@/modulos/respostas/SeloNota.vue'
import { rotuloCategoria } from '@/modulos/respostas/logica'
import type { PassosAtualizados } from '@/modulos/ia/logica'
import PassosIa from './PassosIa.vue'
import RetornoCliente from './RetornoCliente.vue'
import SeletorPrioridade from './SeletorPrioridade.vue'
import {
  COLUNAS,
  LIMITE_TEXTO_ACAO,
  SITUACOES_ACAO,
  edicaoDaAcao,
  mudancasAcao,
  seloPrazo,
  validarEdicaoAcao,
  type EdicaoAcao,
} from './logica'

const props = withDefaults(
  defineProps<{
    acao: Acao | null
    aberto: boolean
    carregando?: boolean
    erroCarga?: string | null
    /** Abriu porque tentaram concluir sem o que falta: já começa em "Concluída" mostrando o que preencher. */
    concluir?: boolean
    /** Erros do servidor ao mover (422 com campos). */
    errosIniciais?: Record<string, string> | null
  }>(),
  { carregando: false, erroCarga: null, concluir: false, errosIniciais: null },
)
const emit = defineEmits<{ fechar: []; salva: [Acao, Acao]; excluida: [Acao]; recarregada: [Acao]; passos: [PassosAtualizados] }>()

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const podeTratar = computed(() => sessao.pode('acoes.tratar'))
/** A lista de responsáveis pede contatos.ver: sem ela, o campo mostra o atual e não muda. */
const podeVerResponsaveis = computed(() => sessao.pode('contatos.ver'))
const { enviando, erroGeral, codigoErro, erros, executar, limpar } = useFormulario()
const excluindo = ref(false)
const locais = reactive<Record<string, string>>({})
const edicao = reactive<EdicaoAcao>({
  titulo: '',
  descricao: '',
  resolucao: '',
  responsavel_id: '',
  prioridade: 'media',
  prazo: '',
  situacao: 'a_fazer',
  empresa: null,
})
const campoResolucao = ref<InstanceType<typeof AreaTexto> | null>(null)

const abertoModel = computed({
  get: () => props.aberto,
  set: (v: boolean) => {
    if (!v) emit('fechar')
  },
})

// Enquanto o painel é preenchido com a ação, as mudanças nos campos não são "do usuário".
let preenchendo = false

function preencher() {
  const a = props.acao
  if (!a) return
  preenchendo = true
  try {
    limpar()
    for (const k of Object.keys(locais)) delete locais[k]
    Object.assign(edicao, edicaoDaAcao(a))
    if (props.concluir) {
      edicao.situacao = 'concluida'
      Object.assign(locais, validarEdicaoAcao(edicao, a))
    }
    if (props.errosIniciais) Object.assign(locais, props.errosIniciais)
  } finally {
    preenchendo = false
  }
  if (props.concluir || props.errosIniciais) focarFalta()
}
/** A ação que este painel mesmo buscou de novo depois de um erro (já está no formulário, com o que a pessoa mudou). */
let recarregada: Acao | null = null
watch(
  () => [props.acao, props.aberto, props.concluir],
  () => {
    if (!props.aberto || !props.acao) return
    // (toRaw: a tela guarda a ação num ref, que devolve um proxy do mesmo objeto.)
    if (recarregada && toRaw(props.acao) === toRaw(recarregada)) {
      recarregada = null
      return
    }
    preencher()
  },
  { immediate: true },
)
watch(
  () => props.aberto,
  (v) => {
    if (v && sessao.pode('contatos.ver')) cadastros.garantir(['responsaveis'])
  },
  { immediate: true },
)

async function focarFalta() {
  await nextTick()
  await nextTick()
  if (locais.responsavel_id || erros.responsavel_id) document.querySelector<HTMLElement>('#campo-responsavel-acao select')?.focus()
  else campoResolucao.value?.elemento?.focus()
}

// Ao escolher "Concluída", o campo do que foi feito aparece e recebe o foco.
watch(
  () => edicao.situacao,
  async (s, antes) => {
    if (s === 'concluida' && antes && antes !== 'concluida' && !props.concluir) {
      await nextTick()
      campoResolucao.value?.elemento?.focus()
    }
    if (s !== 'concluida') {
      delete locais.responsavel_id
      delete locais.resolucao
    }
  },
)
// Ao preencher o que falta, o aviso some na hora. Só conta o que a pessoa mudou depois de abrir
// (o aviso que veio do servidor continua até ela mexer no campo).
watch(
  () => edicao.responsavel_id,
  (v) => {
    if (!preenchendo && locais.responsavel_id && v !== '') delete locais.responsavel_id
  },
  { flush: 'sync' },
)
watch(
  () => edicao.resolucao,
  (v) => {
    if (!preenchendo && locais.resolucao && v.trim()) delete locais.resolucao
  },
  { flush: 'sync' },
)

const mudancas = computed(() => (props.acao ? mudancasAcao(props.acao, edicao) : {}))
const alterado = computed(() => Object.keys(mudancas.value).length > 0)
const erro = (c: string) => locais[c] ?? erros[c] ?? null
const mostrarResolucao = computed(() => edicao.situacao === 'concluida' || !!props.acao?.resolucao || !!edicao.resolucao)
const selo = computed(() => (props.acao ? seloPrazo({ ...props.acao, situacao: edicao.situacao, prazo: edicao.prazo || null, prazo_selo: undefined }) : null))
const opcoesSituacao = COLUNAS.map((c) => ({ valor: c.situacao, rotulo: SITUACOES_ACAO[c.situacao].rotulo }))
const opcoesResponsaveis = computed(() => {
  const lista = cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome }))
  const atual = props.acao?.responsavel
  if (atual && !lista.some((o) => String(o.valor) === String(atual.id))) lista.unshift({ valor: atual.id, rotulo: atual.nome })
  return lista
})
const faltasConcluir = computed(() => [locais.responsavel_id || erros.responsavel_id, locais.resolucao || erros.resolucao].filter(Boolean))

async function salvar() {
  const a = props.acao
  if (!a) return
  for (const k of Object.keys(locais)) delete locais[k]
  const v = validarEdicaoAcao(edicao, a)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    focarFalta()
    return
  }
  const dados = mudancas.value
  if (!Object.keys(dados).length) return
  const r = await executar(() => acoesApi.atualizar(a.id, dados))
  if (!r) {
    if (erros.responsavel_id || erros.resolucao) focarFalta()
    // O servidor recusou: a ação pode ter mudado em outra sessão (ex.: o responsável foi removido).
    if (codigoErro.value && codigoErro.value !== 'sem_conexao') void conferirComServidor(a)
    return
  }
  emit('salva', r, a)
  const mudouSituacao = dados.situacao && dados.situacao !== a.situacao
  avisar.sucesso(
    mudouSituacao
      ? r.situacao === 'concluida'
        ? 'Ação concluída. Bom trabalho!'
        : `Ação movida para ${SITUACOES_ACAO[r.situacao as SituacaoAcao]?.rotulo ?? r.situacao}.`
      : 'Ação salva.',
  )
}

/**
 * Busca a ação de novo e atualiza o formulário sem perder o que a pessoa mudou nem os avisos do servidor:
 * os campos que ela não mexeu passam a mostrar o valor atual (assim a próxima tentativa já parte do que vale).
 */
async function conferirComServidor(a: Acao) {
  let nova: Acao
  try {
    nova = await acoesApi.obter(a.id)
  } catch {
    return
  }
  if (!props.aberto || !props.acao || String(props.acao.id) !== String(a.id)) return
  const original = edicaoDaAcao(props.acao)
  const minhas: Record<string, unknown> = {}
  for (const k of Object.keys(edicao) as (keyof EdicaoAcao)[]) {
    if (JSON.stringify(edicao[k]) !== JSON.stringify(original[k])) minhas[k] = edicao[k]
  }
  preenchendo = true
  Object.assign(edicao, edicaoDaAcao(nova), minhas)
  preenchendo = false
  recarregada = nova
  emit('recarregada', nova)
}

async function excluir() {
  const a = props.acao
  if (!a) return
  const ok = await confirmar({
    titulo: 'Excluir esta ação?',
    mensagem: `A ação "${a.titulo}" sai do quadro de vez. ${a.resposta ? 'A resposta do cliente continua guardada. ' : ''}Não dá para desfazer.`,
    confirmar: 'Excluir ação',
    perigo: true,
  })
  if (!ok) return
  excluindo.value = true
  try {
    await acoesApi.excluir(a.id)
    avisar.sucesso('Ação excluída.')
    emit('excluida', a)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    excluindo.value = false
  }
}

async function antesDeFechar(): Promise<boolean> {
  if (!alterado.value || enviando.value) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Você mudou esta ação e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
}

// Links de dentro do painel (ex.: "Ver a resposta completa") também passam pela pergunta de "sair sem salvar".
onBeforeRouteLeave(() => (props.aberto ? antesDeFechar() : true))

const origem = computed(() => {
  const a = props.acao
  if (!a) return ''
  if (a.origem === 'automatica') return 'Criada sozinha pela resposta do cliente'
  return a.criado_por ? `Criada por ${a.criado_por.nome}` : 'Criada à mão'
})
</script>

<template>
  <PainelLateral
    v-model:aberto="abertoModel"
    :titulo="acao ? acao.titulo : carregando ? 'Carregando…' : 'Ação'"
    :descricao="acao?.empresa?.nome"
    :bloqueado="enviando || excluindo"
    :antes-de-fechar="antesDeFechar"
  >
    <template v-if="acao" #antes-do-titulo>
      <div class="mb-1.5 flex flex-wrap items-center gap-1.5">
        <Etiqueta :tom="SITUACOES_ACAO[acao.situacao]?.tom ?? 'neutro'">{{ SITUACOES_ACAO[acao.situacao]?.rotulo ?? acao.situacao }}</Etiqueta>
        <Etiqueta v-if="selo && selo.tipo !== 'data'" :tom="selo.tom" ponto>{{ selo.rotulo }}</Etiqueta>
      </div>
    </template>

    <Carregando v-if="carregando && !acao" :linhas="5" rotulo="Carregando a ação" />
    <Alerta v-else-if="erroCarga && !acao" tom="erro">{{ erroCarga }}</Alerta>

    <div v-else-if="acao" class="flex flex-col gap-6">
      <Alerta v-if="faltasConcluir.length && edicao.situacao === 'concluida'" tom="atencao" titulo="Para concluir, falta pouco">
        <ul class="list-disc pl-4">
          <li v-for="f in faltasConcluir" :key="f">{{ f }}</li>
        </ul>
      </Alerta>
      <Alerta v-else-if="erroGeral && !Object.keys(erros).length" tom="erro">{{ erroGeral }}</Alerta>

      <form id="painel-acao-form" class="flex flex-col gap-5" novalidate @submit.prevent="salvar">
        <fieldset :disabled="!podeTratar" class="flex min-w-0 flex-col gap-5">
          <legend class="sr-only">Dados da ação</legend>
          <Campo v-model="edicao.titulo" rotulo="Título" maxlength="200" autocomplete="off" :erro="erro('titulo')" />

          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Selecao v-model="edicao.situacao" rotulo="Situação" :opcoes="opcoesSituacao" :erro="erro('situacao')" />
            <div id="campo-responsavel-acao">
              <Selecao
                v-model="edicao.responsavel_id"
                rotulo="Responsável"
                :opcoes="opcoesResponsaveis"
                vazio="Sem responsável"
                :desabilitado="!podeVerResponsaveis"
                :erro="erro('responsavel_id')"
                :dica="
                  !podeVerResponsaveis
                    ? 'Seu perfil não tem acesso à lista de responsáveis.'
                    : edicao.situacao === 'concluida'
                      ? undefined
                      : 'Quem cuida desta ação.'
                "
              />
            </div>
          </div>

          <AreaTexto
            v-if="mostrarResolucao"
            ref="campoResolucao"
            v-model="edicao.resolucao"
            rotulo="O que foi feito"
            :linhas="3"
            :maximo="LIMITE_TEXTO_ACAO"
            placeholder="Ex.: liguei para o cliente, pedimos desculpas e combinamos aviso antes de cada entrega."
            :erro="erro('resolucao')"
            :dica="edicao.situacao === 'concluida' ? 'Obrigatório para concluir. Fica guardado no histórico.' : undefined"
          />

          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <SeletorPrioridade v-model="edicao.prioridade" :erro="erro('prioridade')" :desabilitado="!podeTratar" />
            <Campo v-model="edicao.prazo" rotulo="Prazo" tipo="date" :erro="erro('prazo')" :dica="selo?.descricao" />
          </div>

          <CampoEmpresa v-model="edicao.empresa" rotulo="Empresa" opcional placeholder="Digite para buscar" :erro="erro('empresa_id')" />

          <AreaTexto v-model="edicao.descricao" rotulo="Descrição" :linhas="5" :maximo="LIMITE_TEXTO_ACAO" :erro="erro('descricao')" />
        </fieldset>
        <p v-if="!podeTratar" class="text-sm text-texto-fraco">Seu perfil pode ver as ações, mas não mudar.</p>
      </form>

      <RetornoCliente :acao="acao" @enviado="(a) => emit('recarregada', a)" />

      <PassosIa :acao="acao" @atualizada="emit('passos', $event)" />

      <!-- Resposta que deu origem -->
      <section v-if="acao.resposta" aria-labelledby="t-origem">
        <h3 id="t-origem" class="mb-2 text-sm font-bold uppercase tracking-wide text-texto-fraco">Resposta que deu origem</h3>
        <div class="flex gap-3 rounded-xl border border-borda p-4">
          <SeloNota :nota="acao.resposta.nota" :grupo="acao.resposta.grupo" :tipo="acao.resposta.tipo_nota" />
          <div class="min-w-0 flex-1 text-sm">
            <p class="font-semibold text-texto">
              {{ acao.contato?.nome ?? 'Cliente' }}<span v-if="acao.resposta.grupo" class="font-normal text-texto-fraco"> · {{ rotuloCategoria(acao.resposta.grupo) }}</span>
            </p>
            <p class="text-xs text-texto-fraco">{{ formatarData(acao.resposta.data) }}</p>
            <p v-if="acao.resposta.comentario" class="mt-1.5 whitespace-pre-line text-texto-suave">“{{ acao.resposta.comentario }}”</p>
            <RouterLink
              v-if="sessao.pode('respostas.ver')"
              :to="{ path: '/respostas', query: { analisar: String(acao.resposta.id) } }"
              class="link mt-1 inline-flex min-h-10 items-center gap-1"
            >
              <MessageSquareText class="size-4" aria-hidden="true" /> Ver a resposta completa <ArrowRight class="size-4" aria-hidden="true" />
            </RouterLink>
          </div>
        </div>
      </section>
      <p v-else-if="acao.contato" class="text-sm text-texto-suave">
        Contato:
        <RouterLink v-if="sessao.pode('contatos.ver')" :to="`/contatos/${acao.contato.id}`" class="link">{{ acao.contato.nome }}</RouterLink>
        <template v-else>{{ acao.contato.nome }}</template>
      </p>

      <!-- Histórico -->
      <dl class="grid grid-cols-1 gap-x-4 gap-y-1.5 rounded-xl bg-superficie-2 p-4 text-xs sm:grid-cols-[auto_1fr]">
        <dt class="text-texto-fraco">Origem</dt>
        <dd class="text-texto-suave">{{ origem }}</dd>
        <dt class="text-texto-fraco">Criada em</dt>
        <dd class="text-texto-suave">{{ formatarDataHora(acao.criada_em) }}</dd>
        <template v-if="acao.iniciada_em">
          <dt class="text-texto-fraco">Começou em</dt>
          <dd class="text-texto-suave">{{ formatarDataHora(acao.iniciada_em) }}</dd>
        </template>
        <template v-if="acao.concluida_em">
          <dt class="text-texto-fraco">Concluída em</dt>
          <dd class="text-texto-suave">{{ formatarDataHora(acao.concluida_em) }}<template v-if="acao.concluida_por"> por {{ acao.concluida_por.nome }}</template></dd>
        </template>
      </dl>
    </div>

    <template v-if="acao && (podeTratar || sessao.pode('acoes.excluir'))" #rodape>
      <MenuSuspenso v-if="sessao.pode('acoes.excluir')" rotulo="Mais opções desta ação" alinhar="esquerda" fixo class="sm:hidden">
        <template #gatilho="{ props: p }">
          <Botao v-bind="p" variante="secundario" :carregando="excluindo" :desabilitado="enviando">
            <MoreHorizontal v-if="!excluindo" class="size-4" aria-hidden="true" /> Mais
          </Botao>
        </template>
        <ItemMenu :icone="Trash2" perigo @click="excluir">Excluir ação</ItemMenu>
      </MenuSuspenso>
      <div class="hidden sm:contents">
        <Botao v-if="sessao.pode('acoes.excluir')" variante="perigo-suave" class="mr-auto" :carregando="excluindo" :desabilitado="enviando" @click="excluir">
          <Trash2 v-if="!excluindo" class="size-4" aria-hidden="true" /> Excluir ação
        </Botao>
      </div>
      <Botao v-if="podeTratar" tipo="submit" form="painel-acao-form" class="flex-1 sm:flex-none" :carregando="enviando" :desabilitado="!alterado || excluindo">
        {{ edicao.situacao === 'concluida' && acao.situacao !== 'concluida' ? 'Concluir ação' : 'Salvar' }}
      </Botao>
    </template>
  </PainelLateral>
</template>
