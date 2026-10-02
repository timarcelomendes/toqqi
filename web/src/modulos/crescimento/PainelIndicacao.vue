<script setup lang="ts">
// Painel lateral de uma indicação: os dados da pessoa indicada, a observação, quem indicou, os botões para falar com
// ela (WhatsApp e e-mail), a troca de situação (valor mensal ao virar cliente, motivo ao não avançar), a troca de
// responsável e "Excluir (pedido da pessoa)". Tudo como texto: nada do que veio da indicação vira HTML.
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { Mail, MessageCircle, MoreHorizontal, Trash2 } from 'lucide-vue-next'
import { crescimentoApi, mensagemDoErro, type Indicacao } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useFormulario } from '@/composables/formulario'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData, formatarDataHora } from '@/utils/datas'
import { exibirTelefone, formatarDecimal, formatarMoeda, lerMoeda } from '@/utils/formatos'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import Selecao from '@/components/ui/Selecao.vue'
import TextoEmail from '@/components/ui/TextoEmail.vue'
import {
  LIMITE_MOTIVO,
  ORDEM_SITUACOES,
  SITUACOES_INDICACAO,
  aplicarMudancas,
  edicaoDaIndicacao,
  linkEmail,
  linkWhatsapp,
  mudancasIndicacao,
  nomesDoIndicador,
  quemIndicou,
  situacaoIndicacao,
  validarEdicaoIndicacao,
  type EdicaoIndicacao,
} from './logica'

const props = defineProps<{ indicacao: Indicacao | null; aberto: boolean }>()
const emit = defineEmits<{ fechar: []; salva: [nova: Indicacao, antiga: Indicacao]; excluida: [Indicacao] }>()

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const podeTratar = computed(() => sessao.pode('crescimento.tratar'))
/** A lista de responsáveis pede contatos.ver: sem ela, o campo mostra o atual e não muda. */
const podeVerResponsaveis = computed(() => sessao.pode('contatos.ver'))
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const excluindo = ref(false)
const locais = reactive<Record<string, string>>({})
const edicao = reactive<EdicaoIndicacao>({ situacao: 'nova', valor_mensal: '', motivo: '', responsavel_id: '' })
const campoValor = ref<InstanceType<typeof Campo> | null>(null)
const campoMotivo = ref<InstanceType<typeof AreaTexto> | null>(null)
const anuncio = ref('')

const abertoModel = computed({
  get: () => props.aberto,
  set: (v: boolean) => {
    if (!v) emit('fechar')
  },
})

let preenchendo = false
watch(
  () => [props.indicacao, props.aberto] as const,
  () => {
    if (!props.aberto || !props.indicacao) return
    preenchendo = true
    limpar()
    for (const k of Object.keys(locais)) delete locais[k]
    Object.assign(edicao, edicaoDaIndicacao(props.indicacao))
    preenchendo = false
  },
  { immediate: true },
)
watch(
  () => props.aberto,
  (v) => {
    if (v && podeVerResponsaveis.value) cadastros.garantir(['responsaveis'])
  },
  { immediate: true },
)

// Virar cliente pede o valor; não avançar abre o motivo: o campo que aparece recebe o foco.
watch(
  () => edicao.situacao,
  async (s, antes) => {
    if (preenchendo || !antes || s === antes) return
    delete locais.valor_mensal
    delete locais.motivo
    anuncio.value = s === 'cliente' ? 'Informe o valor mensal do novo cliente.' : s === 'nao_avancou' ? 'Se quiser, conte o motivo.' : ''
    await nextTick()
    if (s === 'cliente') campoValor.value?.focar()
    else if (s === 'nao_avancou') campoMotivo.value?.elemento?.focus()
  },
)
watch(
  () => edicao.valor_mensal,
  () => {
    if (!preenchendo) delete locais.valor_mensal
  },
)

const mudancas = computed(() => (props.indicacao ? mudancasIndicacao(props.indicacao, edicao) : {}))
const alterado = computed(() => Object.keys(mudancas.value).length > 0)
const erro = (c: string) => locais[c] ?? erros[c] ?? null
const opcoesSituacao = ORDEM_SITUACOES.map((s) => ({ valor: s, rotulo: SITUACOES_INDICACAO[s].rotulo }))
const opcoesResponsaveis = computed(() => {
  const lista = cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome }))
  const atual = props.indicacao?.responsavel
  if (atual && !lista.some((o) => String(o.valor) === String(atual.id))) lista.unshift({ valor: atual.id, rotulo: atual.nome })
  return lista
})

const selo = computed(() => situacaoIndicacao(props.indicacao?.situacao))
const telefone = computed(() => exibirTelefone(props.indicacao?.telefone))
const whatsapp = computed(() => linkWhatsapp(props.indicacao?.telefone))
const email = computed(() => linkEmail(props.indicacao?.email))
const indicador = computed(() => (props.indicacao ? nomesDoIndicador(props.indicacao) : []))
const quem = computed(() => (props.indicacao ? quemIndicou(props.indicacao) : ''))

function aoSairValor() {
  const n = lerMoeda(edicao.valor_mensal)
  if (n !== null && n >= 0) edicao.valor_mensal = formatarDecimal(n)
}

async function salvar() {
  const i = props.indicacao
  if (!i || enviando.value) return
  for (const k of Object.keys(locais)) delete locais[k]
  const v = validarEdicaoIndicacao(edicao)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    await nextTick()
    if (v.valor_mensal) campoValor.value?.focar()
    else campoMotivo.value?.elemento?.focus()
    return
  }
  const dados = mudancas.value
  if (!Object.keys(dados).length) return
  const r = await executar(() => crescimentoApi.atualizarIndicacao(i.id, dados))
  if (r === undefined && (erroGeral.value || Object.keys(erros).length)) {
    if (erros.valor_mensal) campoValor.value?.focar()
    return
  }
  const responsavel = cadastros.listas.responsaveis.find((x) => String(x.id) === String(dados.responsavel_id)) ?? null
  const nova = r && typeof r === 'object' && 'id' in r ? r : aplicarMudancas(i, dados, responsavel ? { id: responsavel.id, nome: responsavel.nome } : null)
  emit('salva', nova, i)
  const mudou = dados.situacao && dados.situacao !== i.situacao
  avisar.sucesso(mudou ? `Indicação marcada como “${situacaoIndicacao(nova.situacao).rotulo}”.` : 'Indicação salva.')
}

async function excluir() {
  const i = props.indicacao
  if (!i) return
  const ok = await confirmar({
    titulo: 'Excluir esta indicação?',
    mensagem: `Use quando ${i.nome} pedir para apagar os dados dela. A indicação sai do Toqqi de vez (fica só o registro de que houve uma exclusão, sem os dados) e não dá para desfazer.`,
    confirmar: 'Excluir indicação',
    perigo: true,
  })
  if (!ok) return
  excluindo.value = true
  try {
    await crescimentoApi.excluirIndicacao(i.id)
    avisar.sucesso('Indicação excluída.')
    emit('excluida', i)
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
    mensagem: 'Você mudou esta indicação e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
}

// Sair da tela (voltar do navegador, um atalho) com o painel mudado também pergunta.
onBeforeRouteLeave(() => (props.aberto ? antesDeFechar() : true))
// Na mesma tela, o endereço muda quando só a aba ou os filtros mudam (trocar de aba, voltar do navegador): a mesma
// pergunta. Saindo sem salvar, o painel fecha junto (as mudanças ficam para trás, como na saída da tela).
onBeforeRouteUpdate(async () => {
  if (!props.aberto || !alterado.value) return true
  const ok = await antesDeFechar()
  if (ok) emit('fechar')
  return ok
})
</script>

<template>
  <PainelLateral
    v-model:aberto="abertoModel"
    :titulo="indicacao ? indicacao.nome : 'Indicação'"
    :descricao="indicacao?.empresa ?? undefined"
    :bloqueado="enviando || excluindo"
    :antes-de-fechar="antesDeFechar"
  >
    <template v-if="indicacao" #antes-do-titulo>
      <div class="mb-1.5 flex flex-wrap items-center gap-1.5">
        <Etiqueta :tom="selo.tom" ponto>{{ selo.rotulo }}</Etiqueta>
        <Etiqueta>{{ indicacao.origem === 'manual' ? 'Registrada à mão' : 'Veio pela pesquisa' }}</Etiqueta>
      </div>
    </template>

    <div v-if="indicacao" class="flex flex-col gap-6">
      <Alerta v-if="erroGeral && !Object.keys(erros).length" tom="erro">{{ erroGeral }}</Alerta>

      <!-- Falar com a pessoa -->
      <section aria-labelledby="t-contato-indicacao" class="flex flex-col gap-3">
        <h3 id="t-contato-indicacao" class="text-sm font-bold uppercase tracking-wide text-texto-fraco">Contato</h3>
        <dl class="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
          <dt class="text-texto-fraco">Telefone</dt>
          <dd class="text-texto">{{ telefone || 'Não informado' }}</dd>
          <dt class="text-texto-fraco">E-mail</dt>
          <dd class="text-texto"><TextoEmail v-if="indicacao.email" :email="indicacao.email" /><template v-else>Não informado</template></dd>
        </dl>
        <div class="flex flex-wrap gap-2">
          <Botao v-if="whatsapp" variante="secundario" :href="whatsapp" data-whatsapp-indicacao>
            <MessageCircle class="size-4 text-sucesso" aria-hidden="true" /> Falar pelo WhatsApp
          </Botao>
          <a v-if="email" :href="email" class="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-borda-forte bg-superficie px-4 text-sm font-semibold text-texto transition-colors hover:bg-superficie-2" data-email-indicacao>
            <Mail class="size-4 text-texto-fraco" aria-hidden="true" /> Mandar e-mail
          </a>
        </div>
      </section>

      <section v-if="indicacao.observacao" aria-labelledby="t-observacao-indicacao">
        <h3 id="t-observacao-indicacao" class="mb-2 text-sm font-bold uppercase tracking-wide text-texto-fraco">Observação</h3>
        <p class="whitespace-pre-line break-words rounded-xl bg-superficie-2 p-4 text-sm text-texto-suave">{{ indicacao.observacao }}</p>
      </section>

      <section aria-labelledby="t-quem-indicou">
        <h3 id="t-quem-indicou" class="mb-2 text-sm font-bold uppercase tracking-wide text-texto-fraco">Quem indicou</h3>
        <p class="text-sm text-texto" data-quem-indicou>{{ indicador.length ? indicador.join(' · ') : quem }}</p>
        <p v-if="indicacao.origem !== 'manual' && !indicacao.pode_identificar" class="mt-1 text-sm text-atencao" data-nao-identificar>
          Quem indicou pediu para não aparecer: ao falar com {{ indicacao.nome }}, não diga quem indicou.
        </p>
        <!-- Sem o nome (contato e empresa de quem indicou apagados), não há quem dizer -->
        <p v-else-if="indicacao.origem !== 'manual' && indicador.length" class="mt-1 text-sm text-texto-fraco" data-pode-identificar>Deixou dizer que foi quem indicou.</p>
      </section>

      <!-- Andamento -->
      <form v-if="podeTratar" id="painel-indicacao-form" class="flex flex-col gap-5" novalidate @submit.prevent="salvar">
        <fieldset class="flex min-w-0 flex-col gap-5">
          <legend class="mb-1 text-sm font-bold uppercase tracking-wide text-texto-fraco">Andamento</legend>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Selecao v-model="edicao.situacao" rotulo="Situação" :opcoes="opcoesSituacao" :erro="erro('situacao')" />
            <Selecao
              v-model="edicao.responsavel_id"
              rotulo="Responsável"
              :opcoes="opcoesResponsaveis"
              vazio="Sem responsável"
              :desabilitado="!podeVerResponsaveis"
              :erro="erro('responsavel_id')"
              :dica="podeVerResponsaveis ? 'Quem vai falar com a pessoa indicada.' : 'Seu perfil não tem acesso à lista de responsáveis.'"
            />
          </div>
          <Campo
            v-if="edicao.situacao === 'cliente'"
            ref="campoValor"
            v-model="edicao.valor_mensal"
            rotulo="Valor mensal do novo cliente"
            inputmode="decimal"
            placeholder="0,00"
            obrigatorio
            :erro="erro('valor_mensal')"
            dica="Entra na receita mensal vinda das indicações. Pode ser 0."
            @blur="aoSairValor"
          >
            <template #antes><span class="text-sm font-semibold">R$</span></template>
          </Campo>
          <AreaTexto
            v-if="edicao.situacao === 'nao_avancou'"
            ref="campoMotivo"
            v-model="edicao.motivo"
            rotulo="Motivo"
            opcional
            :linhas="3"
            :maximo="LIMITE_MOTIVO"
            placeholder="Ex.: já tem fornecedor com contrato até o fim do ano."
            :erro="erro('motivo')"
          />
        </fieldset>
      </form>
      <dl v-else class="grid grid-cols-1 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[auto_1fr]">
        <dt class="text-texto-fraco">Responsável</dt>
        <dd class="text-texto">{{ indicacao.responsavel?.nome ?? 'Sem responsável' }}</dd>
        <template v-if="indicacao.situacao === 'cliente'">
          <dt class="text-texto-fraco">Valor mensal</dt>
          <dd class="text-texto">{{ formatarMoeda(indicacao.valor_mensal) }}</dd>
        </template>
        <template v-if="indicacao.situacao === 'nao_avancou' && indicacao.motivo">
          <dt class="text-texto-fraco">Motivo</dt>
          <dd class="whitespace-pre-line text-texto">{{ indicacao.motivo }}</dd>
        </template>
      </dl>
      <p v-if="!podeTratar" class="text-sm text-texto-fraco">Seu perfil pode ver as indicações, mas não mudar.</p>

      <dl class="grid grid-cols-1 gap-x-4 gap-y-1.5 rounded-xl bg-superficie-2 p-4 text-xs sm:grid-cols-[auto_1fr]">
        <dt class="text-texto-fraco">Recebida em</dt>
        <dd class="text-texto-suave">{{ formatarDataHora(indicacao.criada_em) }}</dd>
        <template v-if="indicacao.atualizada_em && indicacao.atualizada_em !== indicacao.criada_em">
          <dt class="text-texto-fraco">Última mudança</dt>
          <dd class="text-texto-suave">{{ formatarData(indicacao.atualizada_em) }}</dd>
        </template>
      </dl>
      <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
    </div>

    <template v-if="indicacao && podeTratar" #rodape>
      <MenuSuspenso rotulo="Mais opções desta indicação" alinhar="esquerda" fixo class="sm:hidden">
        <template #gatilho="{ props: p }">
          <Botao v-bind="p" variante="secundario" :carregando="excluindo" :desabilitado="enviando">
            <MoreHorizontal v-if="!excluindo" class="size-4" aria-hidden="true" /> Mais
          </Botao>
        </template>
        <ItemMenu :icone="Trash2" perigo @click="excluir">Excluir (pedido da pessoa)</ItemMenu>
      </MenuSuspenso>
      <div class="hidden sm:contents">
        <Botao variante="perigo-suave" class="mr-auto" :carregando="excluindo" :desabilitado="enviando" @click="excluir">
          <Trash2 v-if="!excluindo" class="size-4" aria-hidden="true" /> Excluir (pedido da pessoa)
        </Botao>
      </div>
      <Botao tipo="submit" form="painel-indicacao-form" class="flex-1 sm:flex-none" :carregando="enviando" :desabilitado="!alterado || excluindo">Salvar</Botao>
    </template>
  </PainelLateral>
</template>
