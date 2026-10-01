<script setup lang="ts">
// WhatsApp automático já conectado: número, modelo, ligar/desligar, franquia, excedente, teste e desconectar.
import { computed, ref } from 'vue'
import { CheckCircle2, Gauge, MessageCircle, Send, Unplug } from 'lucide-vue-next'
import { mensagemDoErro, whatsappAutomaticoApi, type WhatsappIntegracao } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { formatarMoeda, telefoneWhatsapp } from '@/utils/formatos'
import { formatarTelefone } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import BarraFranquia from './BarraFranquia.vue'
import BlocoCodigo from './BlocoCodigo.vue'
import { estadoFranquia, explicacaoFranquia } from './logica'

const props = defineProps<{ dados: WhatsappIntegracao }>()
const emit = defineEmits<{ atualizado: [w: WhatsappIntegracao]; desconectado: [] }>()

const ocupado = ref<'ativo' | 'excedente' | 'teste' | 'desconectar' | null>(null)
const telefone = ref('')
const erroTelefone = ref<string | null>(null)
const resultadoTeste = ref<{ ok: boolean; texto: string } | null>(null)

const franquia = computed(() => estadoFranquia(props.dados.franquia))
const valorExtra = computed(() => formatarMoeda(props.dados.franquia.valor_excedente ?? 1.5))

async function patch(campo: 'ativo' | 'excedente', dados: { ativo?: boolean; excedente_ativo?: boolean }, ok: string) {
  ocupado.value = campo
  try {
    const r = await whatsappAutomaticoApi.atualizar(dados)
    emit('atualizado', r)
    avisar.sucesso(ok)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function mudarAtivo(v: boolean) {
  if (!v) {
    const ok = await confirmar({
      titulo: 'Desligar o WhatsApp automático?',
      mensagem: 'Enquanto estiver desligado, as pesquisas vão por e-mail para quem tem e-mail cadastrado. A conexão continua salva.',
      confirmar: 'Desligar',
    })
    if (!ok) return
  }
  await patch('ativo', { ativo: v }, v ? 'WhatsApp automático ligado.' : 'WhatsApp automático desligado.')
}

async function mudarExcedente(v: boolean) {
  if (v) {
    const ok = await confirmar({
      titulo: 'Liberar mensagens extras?',
      mensagem: `Quando a franquia do mês acabar, as pesquisas continuam saindo pelo WhatsApp e cada mensagem extra custa ${valorExtra.value}, cobrada junto com a sua assinatura. Sem isso, elas passam a ir por e-mail até o mês virar.`,
      confirmar: `Liberar (${valorExtra.value} cada)`,
    })
    if (!ok) return
  }
  await patch('excedente', { excedente_ativo: v }, v ? 'Mensagens extras liberadas.' : 'Mensagens extras desligadas. Depois da franquia, vai por e-mail.')
}

async function enviarTeste() {
  erroTelefone.value = null
  resultadoTeste.value = null
  const numero = telefoneWhatsapp(telefone.value)
  if (!numero) {
    erroTelefone.value = 'Informe um celular com DDD.'
    return
  }
  ocupado.value = 'teste'
  try {
    const r = await whatsappAutomaticoApi.enviarTeste(numero)
    resultadoTeste.value = { ok: true, texto: r?.mensagem || 'Mensagem de teste enviada. Confira o WhatsApp desse número.' }
  } catch (e) {
    resultadoTeste.value = { ok: false, texto: mensagemDoErro(e) }
  } finally {
    ocupado.value = null
  }
}

async function desconectar() {
  const ok = await confirmar({
    titulo: 'Desconectar o WhatsApp?',
    mensagem:
      'O Toqqi para de enviar pelo seu número e apaga o token guardado. As pesquisas passam a ir por e-mail. Para voltar, será preciso colar os dados de novo.',
    confirmar: 'Desconectar',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = 'desconectar'
  try {
    await whatsappAutomaticoApi.desconectar()
    avisar.sucesso('WhatsApp desconectado.')
    emit('desconectado')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <Alerta v-if="dados.ultimo_erro" tom="erro" titulo="O último envio pelo WhatsApp deu erro">{{ dados.ultimo_erro }}</Alerta>

    <!-- Conexão -->
    <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-wa-conexao">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-sucesso-suave text-sucesso"><MessageCircle class="size-5" aria-hidden="true" /></div>
        <h2 id="t-wa-conexao" class="text-base font-bold text-texto">WhatsApp automático</h2>
        <p class="mt-1 text-sm text-texto-suave">As pesquisas saem do número da sua empresa, pela plataforma oficial da Meta.</p>
      </div>
      <div class="flex flex-col gap-5 md:col-span-2">
        <div class="flex flex-wrap items-center gap-3">
          <CheckCircle2 class="size-6 shrink-0 text-sucesso" aria-hidden="true" />
          <div class="min-w-0">
            <p class="text-lg font-bold text-texto">{{ dados.numero_exibicao || 'Número conectado' }}</p>
            <p v-if="dados.nome_verificado" class="text-sm text-texto-suave">Aparece para o cliente como <strong class="text-texto">{{ dados.nome_verificado }}</strong></p>
          </div>
          <Etiqueta :tom="dados.ativo ? 'sucesso' : 'neutro'" ponto class="sm:ml-auto">{{ dados.ativo ? 'Enviando' : 'Desligado' }}</Etiqueta>
        </div>
        <dl class="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt class="text-texto-fraco">Modelo de mensagem</dt>
            <dd class="font-mono text-texto">{{ dados.modelo ? `${dados.modelo.nome} (${dados.modelo.idioma})` : '—' }}</dd>
          </div>
          <div>
            <dt class="text-texto-fraco">Identificação do número</dt>
            <dd class="break-all font-mono text-texto">{{ dados.phone_number_id || '—' }}</dd>
          </div>
        </dl>
        <Interruptor
          :model-value="dados.ativo"
          :desabilitado="ocupado !== null"
          rotulo="Enviar pesquisas pelo WhatsApp"
          descricao="Desligado, as pesquisas vão por e-mail. Escolha o canal em Configurações de envio."
          @update:model-value="mudarAtivo"
        />
        <p class="text-sm"><RouterLink to="/configuracoes/envios" class="link">Escolher o canal em Configurações de envio</RouterLink></p>
      </div>
    </section>

    <!-- Franquia -->
    <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-wa-franquia">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Gauge class="size-5" aria-hidden="true" /></div>
        <h2 id="t-wa-franquia" class="text-base font-bold text-texto">Franquia do mês</h2>
        <p class="mt-1 text-sm text-texto-suave">
          Seu plano inclui {{ dados.franquia.limite }} pesquisas por WhatsApp automático por mês. Os administradores recebem um e-mail aos 80% e quando acabar.
        </p>
      </div>
      <div class="flex flex-col gap-4 md:col-span-2">
        <BarraFranquia :franquia="dados.franquia" />
        <Alerta v-if="franquia.nivel !== 'ok'" :tom="franquia.nivel === 'esgotada' ? 'erro' : 'atencao'">{{ explicacaoFranquia(dados.franquia) }}</Alerta>
        <p v-else class="text-sm text-texto-suave">{{ explicacaoFranquia(dados.franquia) }}</p>
        <p class="text-sm text-texto-fraco">
          Quando a franquia acaba, as pesquisas passam a ir por e-mail (para quem tem e-mail). Se preferir que continuem pelo WhatsApp, libere as mensagens extras:
          cada uma custa {{ valorExtra }}.
        </p>
        <Interruptor
          :model-value="dados.franquia.excedente_ativo"
          :desabilitado="ocupado !== null"
          rotulo="Continuar pelo WhatsApp depois da franquia"
          :descricao="`${valorExtra} por mensagem extra, cobrado na assinatura.`"
          @update:model-value="mudarExcedente"
        />
        <p v-if="dados.franquia.excedentes_mes > 0" class="text-sm text-texto-suave">
          Neste mês: {{ dados.franquia.excedentes_mes }} {{ dados.franquia.excedentes_mes === 1 ? 'mensagem extra' : 'mensagens extras' }}
          ({{ formatarMoeda(dados.franquia.excedentes_mes * (dados.franquia.valor_excedente ?? 1.5)) }}).
        </p>
      </div>
    </section>

    <!-- Teste -->
    <section class="cartao grid gap-6 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-wa-teste">
      <div>
        <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Send class="size-5" aria-hidden="true" /></div>
        <h2 id="t-wa-teste" class="text-base font-bold text-texto">Enviar um teste</h2>
        <p class="mt-1 text-sm text-texto-suave">Manda o modelo de mensagem para um celular, para ver como chega. Use o seu número.</p>
      </div>
      <form class="flex flex-col gap-3 md:col-span-2" novalidate @submit.prevent="enviarTeste">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
          <Campo
            :model-value="telefone"
            rotulo="Celular"
            tipo="tel"
            inputmode="tel"
            autocomplete="tel"
            placeholder="(11) 91234-5678"
            :erro="erroTelefone"
            class="sm:max-w-xs sm:flex-1"
            @update:model-value="(v: string) => (telefone = formatarTelefone(v))"
          />
          <Botao tipo="submit" variante="secundario" :carregando="ocupado === 'teste'" :desabilitado="ocupado !== null && ocupado !== 'teste'" class="sm:mt-7">
            <Send v-if="ocupado !== 'teste'" class="size-4" aria-hidden="true" /> Enviar teste
          </Botao>
        </div>
        <Alerta v-if="resultadoTeste" :tom="resultadoTeste.ok ? 'sucesso' : 'erro'">{{ resultadoTeste.texto }}</Alerta>
      </form>
    </section>

    <details class="cartao p-5 sm:p-6">
      <summary class="cursor-pointer text-sm font-bold text-texto">Dados do webhook para o painel da Meta</summary>
      <div class="mt-4 flex flex-col gap-3 text-sm text-texto-suave">
        <p>Se as confirmações de entrega e leitura não estiverem aparecendo, confira se estes dados estão no app da Meta (WhatsApp → Configuração → Webhook), com o campo <code class="font-mono text-xs">messages</code> assinado.</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <BlocoCodigo v-if="dados.webhook_url" :texto="dados.webhook_url" quebrar><template #titulo>URL de retorno de chamada</template></BlocoCodigo>
          <BlocoCodigo v-if="dados.webhook_verificacao" :texto="dados.webhook_verificacao" quebrar><template #titulo>Token de verificação</template></BlocoCodigo>
        </div>
      </div>
    </details>

    <div class="flex justify-end">
      <Botao variante="perigo-suave" :carregando="ocupado === 'desconectar'" :desabilitado="ocupado !== null" @click="desconectar">
        <Unplug v-if="ocupado !== 'desconectar'" class="size-4" aria-hidden="true" /> Desconectar WhatsApp
      </Botao>
    </div>
  </div>
</template>
