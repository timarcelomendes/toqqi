<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, History, Link2, MessageCircle, MessageSquarePlus, MessageSquareText, Pencil, Trash2 } from 'lucide-vue-next'
import { ApiError, contatosApi, mensagemDoErro, type Contato, type ContatoDetalhe, type ItemHistorico } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useWhatsapp } from '@/composables/whatsapp'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { exibirTelefone } from '@/utils/formatos'
import { CANAIS, GRUPOS_NOTA, iniciais, situacaoContato, tomGrupo } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import ModalRegistrarResposta from '@/modulos/respostas/ModalRegistrarResposta.vue'
import { quandoFoiResposta, seloOrigem } from '@/modulos/respostas/logica'
import ModalContato from './ModalContato.vue'
import ModalLinkPesquisa from './ModalLinkPesquisa.vue'

const rota = useRoute()
const router = useRouter()
const sessao = useSessaoStore()
const contato = ref<ContatoDetalhe | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const naoExiste = ref(false)
const editarAberto = ref(false)
const linkAberto = ref(false)
const registrarAberto = ref(false)
const excluindo = ref(false)
const whatsapp = useWhatsapp()
const podeWhatsapp = computed(
  () => !!contato.value && sessao.pode('envios.disparar') && contato.value.ativo && !!contato.value.telefone && contato.value.situacao !== 'saiu_da_lista',
)

async function abrirWhatsapp() {
  if (contato.value && (await whatsapp.abrir(contato.value))) carregar()
}

const id = computed(() => String(rota.params.id))

async function carregar() {
  carregando.value = true
  erro.value = null
  naoExiste.value = false
  try {
    contato.value = await contatosApi.obter(id.value)
    document.title = `${contato.value.nome} · Toqqi`
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) naoExiste.value = true
    else erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function aoSalvar(c: Contato) {
  contato.value = { ...c, historico: contato.value?.historico ?? [] }
}

async function excluir() {
  const c = contato.value
  if (!c) return
  const ok = await confirmar({
    titulo: `Excluir ${c.nome}?`,
    mensagem: 'O contato sai da lista e as respostas dele também são apagadas. Não dá para desfazer.',
    confirmar: 'Excluir contato',
    perigo: true,
  })
  if (!ok) return
  excluindo.value = true
  try {
    await contatosApi.excluir(c.id)
    avisar.sucesso(`${c.nome} foi excluído(a).`)
    router.push('/contatos')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    excluindo.value = false
  }
}

/** Próximo envio em palavras simples, conforme a situação. */
const proximoEnvio = computed(() => {
  const c = contato.value
  if (!c) return '—'
  if (!c.ativo || c.situacao === 'inativo') return 'Não recebe (contato inativo)'
  if (c.situacao === 'saiu_da_lista' || !c.recebe_pesquisas) return 'Não recebe (saiu da lista)'
  if (c.situacao === 'na_fila') return 'Já está na fila'
  return formatarData(c.proximo_envio)
})

const contatoParaRegistro = computed(() =>
  contato.value ? { id: contato.value.id, nome: contato.value.nome, email: contato.value.email, empresa: contato.value.empresa } : null,
)

function nomeFormulario(h: ItemHistorico) {
  if (!h.formulario) return null
  return typeof h.formulario === 'string' ? h.formulario : h.formulario.nome
}

watch(id, carregar)
onMounted(carregar)
</script>

<template>
  <div>
    <RouterLink to="/contatos" class="mb-4 inline-flex items-center gap-1.5 rounded-lg text-sm font-semibold text-texto-suave hover:text-texto">
      <ArrowLeft class="size-4" aria-hidden="true" /> Contatos
    </RouterLink>

    <Carregando v-if="carregando" :linhas="4" />
    <div v-else-if="naoExiste" class="cartao">
      <EstadoVazio titulo="Contato não encontrado" descricao="Ele pode ter sido excluído.">
        <Botao para="/contatos" variante="secundario">Ver todos os contatos</Botao>
      </EstadoVazio>
    </div>
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-else-if="contato">
      <header class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center">
        <span class="flex size-14 shrink-0 items-center justify-center rounded-full bg-marca-suave text-lg font-bold text-marca-texto" aria-hidden="true">{{ iniciais(contato.nome) }}</span>
        <div class="min-w-0 flex-1">
          <h1 class="titulo-pagina truncate">{{ contato.nome }}</h1>
          <div class="mt-1 flex flex-wrap items-center gap-2 text-sm text-texto-suave">
            <span v-if="contato.empresa">{{ contato.empresa.nome }}</span>
            <Etiqueta :tom="situacaoContato(contato.situacao, contato).tom" ponto>{{ situacaoContato(contato.situacao, contato).rotulo }}</Etiqueta>
            <Etiqueta v-if="!contato.ativo" tom="neutro">Inativo</Etiqueta>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            v-if="podeWhatsapp"
            type="button"
            class="inline-flex h-10 items-center gap-2 rounded-xl bg-emerald-700 px-4 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco disabled:cursor-not-allowed disabled:opacity-55"
            :disabled="whatsapp.abrindo.value !== null"
            @click="abrirWhatsapp"
          >
            <MessageCircle class="size-4" :class="{ 'animate-pulse': whatsapp.abrindo.value !== null }" aria-hidden="true" /> Enviar pelo WhatsApp
          </button>
          <Botao v-if="sessao.pode('envios.disparar') && contato.ativo" variante="secundario" @click="linkAberto = true"><Link2 class="size-4" aria-hidden="true" /> Gerar link de pesquisa</Botao>
          <Botao v-if="sessao.pode('contatos.editar')" variante="secundario" @click="editarAberto = true"><Pencil class="size-4" aria-hidden="true" /> Editar</Botao>
          <Botao v-if="sessao.pode('contatos.excluir')" variante="perigo-suave" :carregando="excluindo" somente-icone="Excluir contato" @click="excluir">
            <Trash2 class="size-4" aria-hidden="true" />
          </Botao>
        </div>
      </header>

      <div class="grid gap-6 lg:grid-cols-3">
        <section class="cartao p-5 lg:col-span-1" aria-labelledby="titulo-dados">
          <h2 id="titulo-dados" class="font-bold text-texto">Dados</h2>
          <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 text-sm">
            <dt class="text-texto-fraco">E-mail</dt>
            <dd class="min-w-0 break-words text-texto">{{ contato.email || '—' }}</dd>
            <dt class="text-texto-fraco">Telefone</dt>
            <dd class="text-texto">{{ exibirTelefone(contato.telefone) || '—' }}</dd>
            <dt class="text-texto-fraco">Empresa</dt>
            <dd class="text-texto">{{ contato.empresa?.nome ?? '—' }}</dd>
            <dt class="text-texto-fraco">Cargo</dt>
            <dd class="text-texto">{{ contato.cargo?.nome ?? '—' }}</dd>
            <dt class="text-texto-fraco">Perfil</dt>
            <dd class="text-texto">{{ contato.perfil?.nome ?? '—' }}</dd>
            <dt class="text-texto-fraco">Recebe pesquisas</dt>
            <dd class="text-texto">{{ contato.recebe_pesquisas ? 'Sim' : 'Não' }}</dd>
            <dt class="text-texto-fraco">Código</dt>
            <dd class="font-mono text-texto">{{ contato.codigo }}</dd>
            <template v-if="contato.codigo_externo">
              <dt class="text-texto-fraco">No seu sistema</dt>
              <dd class="font-mono text-texto">{{ contato.codigo_externo }}</dd>
            </template>
            <dt class="text-texto-fraco">Último envio</dt>
            <dd class="text-texto">{{ formatarData(contato.ultimo_envio, 'Nunca') }}</dd>
            <dt class="text-texto-fraco">Próximo envio</dt>
            <dd class="text-texto">{{ proximoEnvio }}</dd>
            <dt class="text-texto-fraco">Cadastrado em</dt>
            <dd class="text-texto">{{ formatarData(contato.criado_em) }}</dd>
          </dl>
          <RouterLink
            v-if="sessao.pode('envios.ver')"
            :to="{ path: '/envios', query: { aba: 'historico', contato: String(contato.id), nome: contato.nome } }"
            class="link mt-4 inline-flex items-center gap-1.5 text-sm"
          >
            <History class="size-4" aria-hidden="true" /> Ver pesquisas enviadas
          </RouterLink>
        </section>

        <section class="cartao lg:col-span-2" aria-labelledby="titulo-historico">
          <div class="flex flex-col gap-3 border-b border-borda px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <h2 id="titulo-historico" class="font-bold text-texto">Histórico de respostas</h2>
            <div class="grid grid-cols-1 gap-2 sm:flex sm:flex-wrap">
              <Botao
                v-if="sessao.pode('respostas.ver')"
                variante="secundario"
                tamanho="sm"
                class="!h-10 w-full sm:w-auto"
                :para="{ path: '/respostas', query: { contato_id: String(contato.id) } }"
              >
                <MessageSquareText class="size-4" aria-hidden="true" /> Ver respostas
              </Botao>
              <Botao v-if="sessao.pode('respostas.editar')" variante="secundario" tamanho="sm" class="!h-10 w-full sm:w-auto" @click="registrarAberto = true">
                <MessageSquarePlus class="size-4" aria-hidden="true" /> Registrar resposta
              </Botao>
            </div>
          </div>
          <EstadoVazio v-if="!contato.historico?.length" :icone="MessageSquareText" titulo="Nenhuma resposta ainda" descricao="Quando esta pessoa responder uma pesquisa, a nota e o comentário aparecem aqui." />
          <ol v-else class="divide-y divide-borda">
            <li v-for="(h, i) in contato.historico" :key="h.id ?? i" class="flex gap-4 px-5 py-4">
              <span
                v-if="h.nota !== null && h.nota !== undefined"
                class="flex size-11 shrink-0 items-center justify-center rounded-xl text-lg font-extrabold"
                :class="{
                  'bg-sucesso-suave text-sucesso': tomGrupo(h.grupo, h.nota) === 'sucesso',
                  'bg-atencao-suave text-atencao': tomGrupo(h.grupo, h.nota) === 'atencao',
                  'bg-erro-suave text-erro': tomGrupo(h.grupo, h.nota) === 'erro',
                }"
                :aria-label="`Nota ${h.nota}`"
              >{{ h.nota }}</span>
              <span v-else class="flex size-11 shrink-0 items-center justify-center rounded-xl bg-superficie-2 text-texto-fraco" aria-hidden="true">
                <MessageSquareText class="size-5" />
              </span>
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <p class="font-semibold text-texto">{{ nomeFormulario(h) ?? 'Resposta' }}</p>
                  <Etiqueta v-if="h.grupo" :tom="tomGrupo(h.grupo, h.nota)">{{ GRUPOS_NOTA[h.grupo] ?? h.grupo }}</Etiqueta>
                  <Etiqueta v-if="seloOrigem(h.origem)" tom="neutro">{{ seloOrigem(h.origem) }}</Etiqueta>
                  <Etiqueta v-if="h.arquivada" tom="neutro" title="Não entra no NPS, no painel nem nas métricas">Arquivada</Etiqueta>
                </div>
                <p class="text-xs text-texto-fraco">
                  {{ [quandoFoiResposta(h), h.canal ? (CANAIS[h.canal] ?? h.canal) : ''].filter(Boolean).join(' · ') }}
                  <template v-if="h.arquivada"> · não entra nos números</template>
                </p>
                <p v-if="h.comentario" class="mt-2 whitespace-pre-line text-sm text-texto-suave">{{ h.comentario }}</p>
              </div>
            </li>
          </ol>
        </section>
      </div>

      <ModalContato v-model:aberto="editarAberto" :contato="contato" @salvo="aoSalvar" />
      <ModalLinkPesquisa v-model:aberto="linkAberto" :contato="contato" />
      <ModalRegistrarResposta v-model:aberto="registrarAberto" :contato-inicial="contatoParaRegistro" @registrada="carregar" />
    </template>
  </div>
</template>
