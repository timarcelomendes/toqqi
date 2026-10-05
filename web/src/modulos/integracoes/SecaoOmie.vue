<script setup lang="ts">
// Etapa 5j: conector do Omie (ERP). O administrador cola o App Key e o App Secret de um aplicativo do Omie; o Toqqi
// traz os clientes ("Sincronizar agora") e, com o endereço cadastrado nos webhooks do aplicativo no Omie, manda a
// pesquisa NPS quando um pedido é faturado ou uma nota é autorizada.
import { onMounted, ref } from 'vue'
import { conectoresApi, mensagemDoErro, type ConectorOmie } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { formatarDataHora } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import LogoParceiro from './LogoParceiro.vue'

/** Dentro do painel lateral do catálogo: sem a moldura do cartão e sem o cabeçalho (o painel já tem). */
const props = defineProps<{ embutido?: boolean }>()
const emit = defineEmits<{ mudou: [] }>()

const estado = ref<ConectorOmie | null>(null)
const erroCarga = ref<string | null>(null)
const appKey = ref('')
const appSecret = ref('')
const pesquisar = ref(true)
const ocupado = ref<string | null>(null)
const erroChaves = ref<string | null>(null)

async function carregar() {
  erroCarga.value = null
  try {
    estado.value = (await conectoresApi.ver()).omie
    pesquisar.value = estado.value.pesquisar_ao_faturar ?? true
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  }
}

async function conectar() {
  erroChaves.value = appKey.value.trim().length < 5 || appSecret.value.trim().length < 10 ? 'Cole o App Key e o App Secret do aplicativo do Omie.' : null
  if (erroChaves.value) return
  ocupado.value = 'conectar'
  try {
    estado.value = await conectoresApi.conectarOmie(appKey.value.trim(), appSecret.value.trim(), pesquisar.value)
    appKey.value = ''
    emit('mudou')
    appSecret.value = ''
    avisar.sucesso('Omie conectado. Traga os clientes com “Sincronizar agora”.')
  } catch (e) {
    erroChaves.value = mensagemDoErro(e)
  } finally {
    ocupado.value = null
  }
}

async function sincronizar() {
  ocupado.value = 'sincronizar'
  try {
    const r = await conectoresApi.sincronizarOmie()
    avisar.sucesso(`Sincronizado: ${formatarNumero(r.empresas_novas)} empresas e ${formatarNumero(r.contatos_novos)} contatos novos.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
    await carregar()
    emit('mudou')
  }
}

async function alterar(v: boolean) {
  try {
    estado.value = await conectoresApi.alterarOmie(v)
  } catch (e) {
    pesquisar.value = !v
    avisar.erro(mensagemDoErro(e))
  }
}

async function desconectar() {
  const ok = await confirmar({
    titulo: 'Desconectar o Omie?',
    mensagem: 'O Toqqi apaga as chaves e deixa de receber os pedidos faturados. Remova também o webhook no Omie. Empresas e contatos já trazidos continuam aqui.',
    confirmar: 'Desconectar',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = 'desconectar'
  try {
    await conectoresApi.desconectarOmie()
    estado.value = { conectado: false }
    emit('mudou')
    avisar.sucesso('Omie desconectado.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
</script>

<template>
  <section class="flex flex-col gap-4" :class="props.embutido ? '' : 'cartao p-5 sm:p-6'" aria-labelledby="t-omie" data-secao-omie>
    <header v-if="!props.embutido" class="flex items-start gap-3">
      <LogoParceiro chave="omie" nome="Omie" iniciais="OM" />
      <div class="min-w-0">
        <h2 id="t-omie" class="text-base font-bold text-texto">Omie (ERP)</h2>
        <p class="text-sm text-texto-suave">Traga os clientes do Omie e pesquise quem recebeu um pedido faturado.</p>
      </div>
    </header>
    <details class="rounded-xl border border-borda p-3 text-sm" :open="estado ? !estado.conectado : true" data-o-que-faz>
      <summary class="cursor-pointer font-semibold text-texto">O que a integração faz</summary>
      <dl class="mt-3 flex flex-col gap-2.5">
        <div><dt class="font-semibold text-texto">Clientes</dt><dd class="text-texto-suave">“Sincronizar agora” traz os clientes ativos do Omie: cada um vira uma empresa (nome fantasia, CNPJ ou CPF) com um contato (e-mail e telefone do cadastro). Nunca apaga nem muda o que já existe aqui, e respeita o limite de contatos do plano.</dd></div>
        <div><dt class="font-semibold text-texto">Pesquisa no pedido faturado</dt><dd class="text-texto-suave">Com o endereço do Toqqi cadastrado nos webhooks do aplicativo no Omie, o cliente de cada pedido faturado (ou nota autorizada) recebe a pesquisa NPS, uma vez por pedido.</dd></div>
        <div><dt class="font-semibold text-texto">Segurança</dt><dd class="text-texto-suave">O App Key e o App Secret ficam cifrados. O endereço do aviso tem um segredo da sua conta; avisos de outro aplicativo são ignorados.</dd></div>
        <div><dt class="font-semibold text-texto">Ainda não faz</dt><dd class="text-texto-suave">Não traz o valor mensal pelo faturamento e não devolve a nota ao Omie.</dd></div>
      </dl>
    </details>
    <Alerta v-if="erroCarga" tom="erro">{{ erroCarga }} <button type="button" class="link" @click="carregar">Tentar de novo</button></Alerta>

    <form v-else-if="estado && !estado.conectado" class="flex flex-col gap-4" novalidate @submit.prevent="conectar">
      <ol class="list-decimal pl-5 text-sm text-texto-suave">
        <li>No Omie, em Configurações › Integrações (ou no portal do desenvolvedor), crie um aplicativo e copie o <strong>App Key</strong> e o <strong>App Secret</strong>.</li>
        <li>Cole aqui e conecte. As chaves ficam guardadas cifradas.</li>
      </ol>
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo v-model="appKey" rotulo="App Key" autocomplete="off" spellcheck="false" data-app-key />
        <Campo v-model="appSecret" rotulo="App Secret" tipo="password" autocomplete="off" spellcheck="false" data-app-secret />
      </div>
      <p v-if="erroChaves" class="text-sm font-medium text-erro" role="alert">{{ erroChaves }}</p>
      <div class="rounded-xl border border-borda p-4">
        <Interruptor v-model="pesquisar" rotulo="Pesquisar quando um pedido for faturado" descricao="O cliente recebe a pesquisa NPS pelas regras de envio da conta (descadastro, descanso e canal)." />
      </div>
      <Botao tipo="submit" class="self-start" :carregando="ocupado === 'conectar'">Conectar</Botao>
    </form>

    <template v-else-if="estado">
      <p class="text-sm text-texto">
        <strong class="text-sucesso">Conectado</strong>
        <template v-if="estado.sincronizado_em"> · última sincronização em {{ formatarDataHora(estado.sincronizado_em) }}</template>
        <template v-else> · ainda não sincronizado</template>
      </p>
      <Alerta v-if="estado.erro" tom="atencao">{{ estado.erro }}</Alerta>
      <p v-if="estado.resumo" class="text-sm text-texto-suave">
        Na última vez: {{ formatarNumero(estado.resumo.empresas_novas) }} empresas e {{ formatarNumero(estado.resumo.contatos_novos) }} contatos novos;
        {{ formatarNumero(estado.resumo.contatos_existentes) }} já estavam no Toqqi<template v-if="estado.resumo.inativos">; {{ estado.resumo.inativos }} clientes inativos ignorados</template><template v-if="estado.resumo.sem_email_ou_telefone">; {{ estado.resumo.sem_email_ou_telefone }} sem e-mail nem telefone</template>.
        <template v-if="estado.resumo.limite_do_plano"> Parou no limite de contatos do seu plano.</template>
      </p>
      <div class="rounded-xl border border-borda p-4">
        <Interruptor v-model="pesquisar" rotulo="Pesquisar quando um pedido for faturado" descricao="O cliente recebe a pesquisa NPS pelas regras de envio da conta (descadastro, descanso e canal)." @update:model-value="alterar" />
      </div>
      <div v-if="pesquisar && estado.url_aviso" class="flex flex-col gap-2 rounded-xl bg-superficie-2 p-4 text-sm" data-url-aviso-omie>
        <p class="font-semibold text-texto">Cadastre este endereço nos webhooks do aplicativo no Omie</p>
        <p class="text-texto-suave">No portal do desenvolvedor do Omie, abra o aplicativo, clique em “Adicionar novo webhook”, cole o endereço e ligue os eventos {{ (estado.eventos ?? []).join(', ') }}.</p>
        <div class="flex items-center gap-2">
          <code class="min-w-0 flex-1 truncate rounded-lg border border-borda bg-superficie px-3 py-2 text-xs">{{ estado.url_aviso }}</code>
          <BotaoCopiar :texto="estado.url_aviso" rotulo="Copiar endereço" />
        </div>
        <p class="text-xs text-texto-fraco">O endereço tem um segredo da sua conta: não compartilhe.</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Botao :carregando="ocupado === 'sincronizar'" :desabilitado="ocupado !== null && ocupado !== 'sincronizar'" @click="sincronizar">Sincronizar agora</Botao>
        <Botao variante="perigo-suave" :carregando="ocupado === 'desconectar'" :desabilitado="ocupado !== null && ocupado !== 'desconectar'" @click="desconectar">Desconectar</Botao>
      </div>
      <p class="text-xs text-texto-fraco">Cada cliente ativo vira uma empresa com um contato (e-mail ou telefone do cadastro). Nunca apaga nem muda o que já está no Toqqi.</p>
    </template>
  </section>
</template>
