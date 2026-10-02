<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { BellRing, FlaskConical, KeyRound, List, MoreHorizontal, Pencil, Plus, Power, PowerOff, Trash2, Webhook as IconeWebhook } from 'lucide-vue-next'
import { mensagemDoErro, webhooksApi, type Id, type ResultadoTesteWebhook, type Webhook, type WebhookCriado } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { formatarDataHora } from '@/utils/datas'
import { rotuloEventoWebhook } from '@/utils/rotulos'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import BlocoCodigo from './BlocoCodigo.vue'
import ModalEntregas from './ModalEntregas.vue'
import ModalSegredo from './ModalSegredo.vue'
import ModalWebhook from './ModalWebhook.vue'
import { FALHAS_PARA_DESATIVAR, situacaoWebhook } from './logica'

/** Máximo de avisos por conta (regra da API). */
const LIMITE = 5

const lista = ref<Webhook[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const ocupado = ref<Id | null>(null)
const testes = ref<Record<string, ResultadoTesteWebhook>>({})
const modalAberto = ref(false)
const editando = ref<Webhook | null>(null)
const entregasDe = ref<Webhook | null>(null)
const entregasAberto = ref(false)
const segredo = ref<string | null>(null)

const exemploAssinatura = `X-Toqqi-Assinatura: t=1767225600,v1=5f8a...c2

// Para conferir (exemplo em Node.js):
const [t, v1] = cabecalho.split(',').map((p) => p.split('=')[1])
const esperado = crypto.createHmac('sha256', SEGREDO).update(\`\${t}.\${corpoBruto}\`).digest('hex')
const valido = crypto.timingSafeEqual(Buffer.from(esperado), Buffer.from(v1))`

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    lista.value = await webhooksApi.listar()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function substituir(w: Webhook) {
  lista.value = lista.value.map((x) => (String(x.id) === String(w.id) ? { ...x, ...w } : x))
}

function novo() {
  editando.value = null
  modalAberto.value = true
}
function editar(w: Webhook) {
  editando.value = w
  modalAberto.value = true
}
function aoCriar(w: WebhookCriado) {
  segredo.value = w.segredo
  // Recarrega a lista: assim não dependemos de a criação devolver o aviso completo.
  carregar()
}
function verEntregas(w: Webhook) {
  entregasDe.value = w
  entregasAberto.value = true
}

async function acao<T>(w: Webhook, fazer: () => Promise<T>): Promise<T | undefined> {
  ocupado.value = w.id
  try {
    return await fazer()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
    return undefined
  } finally {
    ocupado.value = null
  }
}

async function alternarAtivo(w: Webhook) {
  if (w.ativo) {
    const ok = await confirmar({
      titulo: 'Desligar este aviso?',
      mensagem: 'O outro sistema deixa de receber os avisos até você ligar de novo. Nada é reenviado depois.',
      confirmar: 'Desligar',
    })
    if (!ok) return
  }
  const r = await acao(w, () => webhooksApi.atualizar(w.id, { ativo: !w.ativo }))
  if (!r) return
  substituir(r)
  avisar.sucesso(r.ativo ? 'Aviso ligado.' : 'Aviso desligado.')
}

async function testar(w: Webhook) {
  const r = await acao(w, () => webhooksApi.testar(w.id))
  if (r) testes.value = { ...testes.value, [String(w.id)]: r }
}

async function trocarSegredo(w: Webhook) {
  const ok = await confirmar({
    titulo: 'Gerar um novo segredo?',
    mensagem: 'O segredo atual para de valer na hora. Avise o técnico para atualizar a conferência da assinatura no outro sistema.',
    confirmar: 'Gerar novo segredo',
    perigo: true,
  })
  if (!ok) return
  const r = await acao(w, () => webhooksApi.novoSegredo(w.id))
  if (r) segredo.value = r.segredo
  carregar()
}

async function excluir(w: Webhook) {
  const ok = await confirmar({
    titulo: 'Excluir este aviso?',
    mensagem: `${w.url} deixa de receber avisos do Toqqi. O histórico de entregas também é apagado.`,
    confirmar: 'Excluir',
    perigo: true,
  })
  if (!ok) return
  const r = await acao(w, async () => {
    await webhooksApi.excluir(w.id)
    return true
  })
  if (!r) return
  lista.value = lista.value.filter((x) => String(x.id) !== String(w.id))
  avisar.sucesso('Aviso excluído.')
}

onMounted(carregar)
</script>

<template>
  <div class="flex flex-col gap-6">
    <section class="cartao p-5 sm:p-6" aria-labelledby="t-webhooks">
      <div class="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start">
        <div class="flex min-w-0 flex-1 items-start gap-3">
          <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><BellRing class="size-5" aria-hidden="true" /></div>
          <div>
            <h2 id="t-webhooks" class="text-base font-bold text-texto">Avisos para outros sistemas</h2>
            <p class="mt-1 max-w-2xl text-sm text-texto-suave">
              O Toqqi avisa o sistema da sua empresa (ou o Zapier, Make, n8n) assim que um cliente responde ou sai da lista. Serve, por exemplo,
              para abrir um chamado quando chega uma nota baixa. Até {{ LIMITE }} avisos por conta.
            </p>
          </div>
        </div>
        <Botao v-if="!carregando && !erro" :desabilitado="lista.length >= LIMITE" class="shrink-0" @click="novo">
          <Plus class="size-4" aria-hidden="true" /> Novo aviso
        </Botao>
      </div>

      <Carregando v-if="carregando" :linhas="3" />
      <Alerta v-else-if="erro" tom="erro">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <EstadoVazio
        v-else-if="!lista.length"
        :icone="IconeWebhook"
        titulo="Nenhum aviso ainda"
        descricao="Crie um aviso quando o técnico da sua empresa passar o endereço que vai receber as respostas."
      />
      <ul v-else class="flex flex-col gap-3">
        <li v-for="w in lista" :key="w.id" class="rounded-xl border border-borda p-4" :aria-busy="ocupado === w.id">
          <div class="flex items-start gap-3">
            <div class="min-w-0 flex-1">
              <p class="break-all font-mono text-sm font-semibold text-texto">{{ w.url }}</p>
              <div class="mt-2 flex flex-wrap items-center gap-1.5">
                <Etiqueta :tom="situacaoWebhook(w).tom" ponto>{{ situacaoWebhook(w).rotulo }}</Etiqueta>
                <Etiqueta v-for="e in w.eventos" :key="e" tom="info">{{ rotuloEventoWebhook(e) }}</Etiqueta>
              </div>
              <p class="mt-2 text-sm text-texto-fraco">
                <template v-if="w.ultima_entrega">
                  Último aviso em {{ formatarDataHora(w.ultima_entrega.quando) }}:
                  <span :class="w.ultima_entrega.ok ? 'text-sucesso' : 'text-erro'">
                    {{ w.ultima_entrega.ok ? 'entregue' : 'não entregue' }}<template v-if="w.ultima_entrega.status_http"> (resposta {{ w.ultima_entrega.status_http }})</template>
                  </span>
                </template>
                <template v-else>Nenhum aviso enviado ainda.</template>
              </p>
              <p v-if="w.falhas_seguidas > 0" class="mt-1 text-sm" :class="w.falhas_seguidas >= FALHAS_PARA_DESATIVAR ? 'text-erro' : 'text-atencao'">
                {{ w.falhas_seguidas === 1 ? '1 falha seguida' : `${w.falhas_seguidas} falhas seguidas` }}.
                <template v-if="w.ativo">Com {{ FALHAS_PARA_DESATIVAR }}, o aviso é desligado e os administradores recebem um e-mail.</template>
                <template v-else-if="w.falhas_seguidas >= FALHAS_PARA_DESATIVAR">Foi desligado por isso. Confira o endereço com o técnico e ligue de novo.</template>
              </p>
              <Alerta v-if="testes[String(w.id)]" :tom="testes[String(w.id)]!.ok ? 'sucesso' : 'erro'" class="mt-3">
                <strong>{{ testes[String(w.id)]!.ok ? 'Teste entregue.' : 'O teste não foi entregue.' }}</strong>
                {{ testes[String(w.id)]!.mensagem }}
                <template v-if="testes[String(w.id)]!.status_http"> (resposta {{ testes[String(w.id)]!.status_http }})</template>
              </Alerta>
            </div>
            <MenuSuspenso :rotulo="`Ações do aviso para ${w.url}`">
              <template #gatilho="{ props }">
                <Botao v-bind="props" variante="fantasma" :somente-icone="`Ações do aviso para ${w.url}`" :carregando="ocupado === w.id">
                  <MoreHorizontal v-if="ocupado !== w.id" class="size-5" aria-hidden="true" />
                </Botao>
              </template>
              <ItemMenu :icone="FlaskConical" @click="testar(w)">Testar</ItemMenu>
              <ItemMenu :icone="List" @click="verEntregas(w)">Ver avisos enviados</ItemMenu>
              <ItemMenu :icone="Pencil" @click="editar(w)">Editar</ItemMenu>
              <ItemMenu :icone="w.ativo ? PowerOff : Power" @click="alternarAtivo(w)">{{ w.ativo ? 'Desligar' : 'Ligar' }}</ItemMenu>
              <ItemMenu :icone="KeyRound" @click="trocarSegredo(w)">Novo segredo</ItemMenu>
              <ItemMenu :icone="Trash2" perigo @click="excluir(w)">Excluir</ItemMenu>
            </MenuSuspenso>
          </div>
        </li>
      </ul>
    </section>

    <details class="cartao group p-5 sm:p-6">
      <summary class="cursor-pointer text-sm font-bold text-texto">Para o técnico: formato e assinatura dos avisos</summary>
      <div class="mt-4 flex flex-col gap-3 text-sm text-texto-suave">
        <p>
          Cada aviso é um <code class="font-mono text-xs">POST</code> em JSON com
          <code class="font-mono text-xs">{"id", "evento", "criado_em", "conta": {"id", "nome"}, "dados": {...}}</code>.
          Em <code class="font-mono text-xs">resposta.criada</code>, <code class="font-mono text-xs">dados</code> traz a resposta e
          <code class="font-mono text-xs">convite: {evento, referencia}</code>; em <code class="font-mono text-xs">contato.descadastrado</code>,
          traz <code class="font-mono text-xs">{email_mascarado, contato_id, origem}</code>.
        </p>
        <p data-formato-indicacoes>
          Em <code class="font-mono text-xs">indicacao.criada</code> (pela pesquisa ou registrada pela equipe) e
          <code class="font-mono text-xs">indicacao.atualizada</code> (mudou de situação), <code class="font-mono text-xs">dados</code> traz o item
          da lista de indicações:
          <code class="font-mono text-xs [overflow-wrap:anywhere]">{id, origem, nome, empresa, telefone, email, observacao, indicador: {contato, empresa}, pode_identificar, responsavel, situacao, valor_mensal, motivo, criada_em, atualizada_em}</code>;
          em <code class="font-mono text-xs">indicacao.atualizada</code>, também <code class="font-mono text-xs">situacao_anterior</code>.
        </p>
        <p>
          Cabeçalhos: <code class="font-mono text-xs">X-Toqqi-Evento</code>, <code class="font-mono text-xs">X-Toqqi-Entrega</code> (id único, use para não
          processar duas vezes) e <code class="font-mono text-xs">X-Toqqi-Assinatura</code> no formato <code class="font-mono text-xs">t=&lt;unix&gt;,v1=&lt;hex&gt;</code>,
          em que <code class="font-mono text-xs">v1</code> é o HMAC-SHA256 do texto <code class="font-mono text-xs">"&lt;t&gt;.&lt;corpo&gt;"</code> com o segredo do aviso.
          Recuse avisos com assinatura diferente ou com <code class="font-mono text-xs">t</code> muito antigo.
        </p>
        <p>
          Responda com um código 2xx em até 10 segundos. Se falhar, o Toqqi tenta de novo em 1 min, 5 min, 30 min, 2 h e 6 h.
          O endereço precisa ser <code class="font-mono text-xs">https://</code> e público, sem redirecionamento.
        </p>
        <BlocoCodigo :texto="exemploAssinatura" rotulo="Copiar"><template #titulo>Conferir a assinatura</template></BlocoCodigo>
      </div>
    </details>

    <ModalWebhook v-model:aberto="modalAberto" :webhook="editando" @criado="aoCriar" @salvo="substituir" />
    <ModalEntregas v-model:aberto="entregasAberto" :webhook="entregasDe" />
    <ModalSegredo
      :segredo="segredo"
      titulo="Segredo do aviso"
      descricao="O técnico usa este segredo para conferir que o aviso veio mesmo do Toqqi."
      rotulo-campo="Segredo"
      @fechado="segredo = null"
    />
  </div>
</template>
