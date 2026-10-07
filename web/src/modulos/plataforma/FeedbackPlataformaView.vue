<script setup lang="ts">
// Plataforma › Feedback › um feedback (/plataforma/feedback/:id, só superadmin; é o link dos e-mails da equipe): a
// conversa, a resposta (texto → e-mail para a pessoa; só a situação → linha na conversa, sem e-mail), a conta, quem
// mandou, onde estava (tela, navegador, versão), o diagnóstico (erros do site e pedidos que falharam, com o request id
// para achar no log e em Plataforma › Erros), a nota interna e, no elogio autorizado, o depoimento pronto para copiar.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Send } from 'lucide-vue-next'
import { mensagemDoErro, plataformaFeedbackApi, type FeedbackPlataforma, type SituacaoFeedback } from '@/api'
import { ApiError } from '@/api/erros'
import { avisar } from '@/composables/avisos'
import { usarFeedback } from '@/composables/feedback'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Selecao from '@/components/ui/Selecao.vue'
import ConversaFeedback from '@/modulos/feedback/ConversaFeedback.vue'
import {
  OPCOES_SITUACAO,
  erroDoTexto,
  infoSituacao,
  infoTipo,
  rotuloImpacto,
  rotuloQuando,
  textoDepoimento,
} from '@/modulos/feedback/logica'
import { PERFIS } from '@/utils/rotulos'

const PLANOS: Record<string, string> = { essencial: 'Essencial', profissional: 'Profissional', empresa: 'Empresa', personalizado: 'Personalizado' }
const SITUACOES_CONTA: Record<string, string> = {
  teste: 'Em teste',
  teste_expirado: 'Teste encerrado',
  ativa: 'Assinante',
  atrasada: 'Pagamento atrasado',
  cancelada: 'Cancelada',
  cortesia: 'Cortesia',
}

const rota = useRoute()
const { atualizarAtencao } = usarFeedback()
const f = ref<FeedbackPlataforma | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const resposta = ref('')
const situacao = ref<SituacaoFeedback | ''>('')
const erroResposta = ref<string | null>(null)
const enviando = ref(false)
const nota = ref('')
const salvandoNota = ref(false)
let controlador: AbortController | null = null

const fid = computed(() => Number(rota.params.id))
const mudouSituacao = computed(() => !!f.value && !!situacao.value && situacao.value !== f.value.situacao)
const rotuloEnviar = computed(() => (resposta.value.trim() ? 'Enviar resposta' : mudouSituacao.value ? 'Mudar a situação' : 'Enviar resposta'))
const notaMudou = computed(() => !!f.value && nota.value.trim() !== f.value.nota_interna)
const primeiroTexto = computed(() => f.value?.mensagens.find((m) => m.autor === 'usuario' && m.texto)?.texto ?? '')
const diagnostico = computed(() => f.value?.contexto.diagnostico ?? null)

function aplicar(novo: FeedbackPlataforma) {
  f.value = novo
  situacao.value = novo.situacao
  nota.value = novo.nota_interna
}

async function carregar() {
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    aplicar(await plataformaFeedbackApi.detalhe(fid.value, controlador.signal))
    void atualizarAtencao(true, true)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = e instanceof ApiError && e.status === 404 ? 'Não encontramos esse feedback.' : mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

watch(fid, () => void carregar(), { immediate: true })
onBeforeUnmount(() => controlador?.abort())

async function responder() {
  if (!f.value || enviando.value) return
  const texto = resposta.value.trim()
  erroResposta.value = texto ? erroDoTexto(texto) : mudouSituacao.value ? null : 'Escreva a resposta ou escolha uma situação diferente da atual.'
  if (erroResposta.value) return
  enviando.value = true
  try {
    aplicar(await plataformaFeedbackApi.responder(f.value.id, { texto, situacao: mudouSituacao.value ? (situacao.value as SituacaoFeedback) : null }))
    resposta.value = ''
    avisar.sucesso(texto ? 'Resposta enviada. A pessoa recebe no Toqqi e por e-mail.' : 'Situação atualizada.')
  } catch (e) {
    if (e instanceof ApiError && e.campo('texto')) erroResposta.value = e.campo('texto')!
    else avisar.erro(mensagemDoErro(e))
  } finally {
    enviando.value = false
  }
}

async function salvarNota() {
  if (!f.value || salvandoNota.value) return
  salvandoNota.value = true
  try {
    aplicar(await plataformaFeedbackApi.alterar(f.value.id, { nota_interna: nota.value }))
    avisar.sucesso('Nota interna salva.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    salvandoNota.value = false
  }
}

const carregarImagem = (imagemId: number, sinal: AbortSignal) => plataformaFeedbackApi.imagem(fid.value, imagemId, sinal)
</script>

<template>
  <div class="flex flex-col gap-6">
    <RouterLink to="/plataforma/feedback" class="link inline-flex w-fit items-center gap-1.5 text-sm"><ArrowLeft class="size-4" aria-hidden="true" /> Plataforma › Feedback</RouterLink>

    <Carregando v-if="carregando && !f" :linhas="4" rotulo="Carregando o feedback" />
    <Alerta v-else-if="erro && !f" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <template v-if="f">
      <header class="flex flex-col gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="titulo-pagina">{{ infoTipo(f.tipo).rotulo }} #{{ f.id }}</h1>
          <Etiqueta :tom="infoSituacao(f.situacao).tom" ponto data-situacao>{{ infoSituacao(f.situacao).rotulo }}</Etiqueta>
          <Etiqueta v-if="f.impacto" :tom="f.impacto === 'bloqueia' ? 'erro' : 'neutro'">{{ rotuloImpacto(f.impacto) }}</Etiqueta>
        </div>
        <p class="text-sm text-texto-suave">
          Enviado {{ rotuloQuando(f.criado_em) }} por {{ f.autor?.nome ?? 'uma pessoa que saiu da conta' }}, da conta {{ f.conta.nome }}.
        </p>
      </header>

      <div class="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div class="flex min-w-0 flex-col gap-6">
          <section class="cartao p-4 sm:p-6" aria-label="Conversa">
            <ConversaFeedback :mensagens="f.mensagens" perspectiva="equipe" :carregar-imagem="carregarImagem" />
          </section>

          <form class="cartao flex flex-col gap-4 p-4 sm:p-6" novalidate data-responder-equipe @submit.prevent="responder">
            <AreaTexto
              v-model="resposta"
              :rotulo="f.autor ? `Resposta para ${f.autor.nome}` : 'Resposta'"
              :dica="f.autor ? 'Chega no Toqqi e por e-mail.' : 'A pessoa saiu da conta: a resposta fica só aqui.'"
              :linhas="4"
              :maximo="5000"
              :erro="erroResposta"
              :disabled="enviando"
              data-texto-equipe
              @input="erroResposta = null"
            />
            <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div class="sm:w-56">
                <Selecao v-model="situacao" rotulo="Situação" :opcoes="OPCOES_SITUACAO" :desabilitado="enviando" data-situacao-equipe />
              </div>
              <Botao tipo="submit" :carregando="enviando" data-enviar-equipe><Send class="size-4" aria-hidden="true" /> {{ rotuloEnviar }}</Botao>
            </div>
          </form>
        </div>

        <aside class="flex flex-col gap-4" aria-label="Detalhes do feedback">
          <section class="cartao flex flex-col gap-1 p-4 text-sm" data-conta>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-texto-fraco">Conta</h2>
            <p class="font-semibold text-texto">{{ f.conta.nome }}</p>
            <p class="text-texto-suave">{{ PLANOS[f.conta.plano] ?? f.conta.plano }} · {{ SITUACOES_CONTA[f.conta.situacao] ?? f.conta.situacao }}</p>
          </section>

          <section class="cartao flex flex-col gap-1 p-4 text-sm" data-quem-mandou>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-texto-fraco">Quem mandou</h2>
            <template v-if="f.autor">
              <p class="font-semibold text-texto">{{ f.autor.nome }}</p>
              <p class="text-texto-suave [overflow-wrap:anywhere]">{{ f.autor.email }}</p>
              <p class="text-texto-suave">
                {{ PERFIS[f.autor.perfil as keyof typeof PERFIS]?.rotulo ?? f.autor.perfil }}<template v-if="f.autor.cargo"> · {{ f.autor.cargo }}</template>
                <template v-if="f.autor.situacao !== 'ativo'"> · {{ f.autor.situacao === 'bloqueado' ? 'Bloqueado' : 'Pendente' }}</template>
              </p>
            </template>
            <p v-else class="text-texto-suave">A pessoa saiu da conta.</p>
          </section>

          <section v-if="f.tipo === 'elogio'" class="cartao flex flex-col gap-2 p-4 text-sm" data-depoimento-plataforma>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-texto-fraco">Depoimento</h2>
            <template v-if="f.autoriza_depoimento">
              <p class="text-texto">{{ textoDepoimento(primeiroTexto, f.autor?.nome, f.conta.nome) }}</p>
              <BotaoCopiar :texto="textoDepoimento(primeiroTexto, f.autor?.nome, f.conta.nome)" rotulo="Copiar depoimento" tamanho="sm" />
            </template>
            <p v-else class="text-texto-suave">Sem autorização para usar no site.</p>
          </section>

          <section class="cartao flex flex-col gap-2 p-4 text-sm" data-contexto>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-texto-fraco">Onde estava</h2>
            <dl class="grid gap-1.5">
              <div v-if="f.contexto.pagina_titulo || f.contexto.pagina">
                <dt class="text-xs text-texto-fraco">Tela</dt>
                <dd class="text-texto">{{ f.contexto.pagina_titulo ?? '—' }} <span v-if="f.contexto.pagina" class="font-mono text-xs text-texto-suave [overflow-wrap:anywhere]">{{ f.contexto.pagina }}</span></dd>
              </div>
              <div v-if="f.contexto.navegador">
                <dt class="text-xs text-texto-fraco">Navegador</dt>
                <dd class="text-xs text-texto-suave [overflow-wrap:anywhere]">{{ f.contexto.navegador }}</dd>
              </div>
              <div v-if="f.contexto.tela || f.contexto.versao_site" class="flex gap-6">
                <div v-if="f.contexto.tela"><dt class="text-xs text-texto-fraco">Janela</dt><dd class="font-mono text-xs">{{ f.contexto.tela }}</dd></div>
                <div v-if="f.contexto.versao_site"><dt class="text-xs text-texto-fraco">Versão do site</dt><dd class="font-mono text-xs">{{ f.contexto.versao_site }}</dd></div>
              </div>
            </dl>
            <p v-if="!f.contexto.pagina && !f.contexto.navegador" class="text-texto-suave">Sem detalhes técnicos.</p>
          </section>

          <section v-if="diagnostico" class="cartao flex flex-col gap-3 p-4 text-sm" data-diagnostico>
            <h2 class="text-xs font-semibold uppercase tracking-wider text-texto-fraco">Diagnóstico</h2>
            <div v-if="diagnostico.erros?.length">
              <p class="mb-1 font-semibold text-texto">Erros do site</p>
              <ul class="flex flex-col gap-1.5 text-xs">
                <li v-for="(e, i) in diagnostico.erros" :key="`e${i}`" class="[overflow-wrap:anywhere]">
                  <span class="font-semibold text-texto">{{ e.tipo }}</span><span v-if="e.mensagem" class="text-texto-suave">: {{ e.mensagem }}</span>
                  <span class="block font-mono text-texto-fraco">{{ e.local }}<template v-if="e.quando"> · {{ rotuloQuando(e.quando) }}</template></span>
                </li>
              </ul>
            </div>
            <div v-if="diagnostico.pedidos?.length">
              <p class="mb-1 font-semibold text-texto">Pedidos que falharam</p>
              <ul class="flex flex-col gap-1.5 text-xs">
                <li v-for="(p, i) in diagnostico.pedidos" :key="`p${i}`" class="font-mono [overflow-wrap:anywhere]">
                  <span class="text-texto">{{ p.metodo }} {{ p.caminho }}</span>
                  <span class="text-texto-suave"> → {{ [p.status || 'sem conexão', p.codigo].filter(Boolean).join(' ') }}</span>
                  <span v-if="p.request_id" class="block text-texto-fraco">pedido {{ p.request_id }}</span>
                </li>
              </ul>
            </div>
            <RouterLink to="/plataforma/erros" class="link w-fit text-xs">Ver Plataforma › Erros</RouterLink>
          </section>

          <section class="cartao flex flex-col gap-3 p-4" data-nota-interna>
            <AreaTexto v-model="nota" rotulo="Nota interna" dica="Só a equipe Toqqi vê." :linhas="3" :maximo="5000" :disabled="salvandoNota" />
            <Botao variante="secundario" tamanho="sm" class="self-end" :desabilitado="!notaMudou" :carregando="salvandoNota" data-salvar-nota @click="salvarNota">Salvar nota</Botao>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>
