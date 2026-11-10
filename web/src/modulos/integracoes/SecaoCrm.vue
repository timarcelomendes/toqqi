<script setup lang="ts">
// Conectores do Pipedrive e do HubSpot (no modelo do RD Station CRM): o administrador cola o token (Pipedrive) ou a
// chave de serviço (HubSpot); o Toqqi traz as empresas e os contatos ("Sincronizar agora") e, se ligado, manda a
// pesquisa NPS aos contatos de cada negócio ganho. No Pipedrive o aviso chega na hora (webhook cadastrado pelo Toqqi) e a
// nota volta ao negócio; no HubSpot o Toqqi consulta os negócios ganhos a cada 30 minutos.
import { computed, onMounted, ref } from 'vue'
import { conectoresApi, mensagemDoErro, type ChaveCrm, type ConectorCrm } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { formatarDataHora } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import LogoParceiro from './LogoParceiro.vue'
import { TEXTOS_CRM } from './logicaCrm'

const props = defineProps<{ chave: ChaveCrm; embutido?: boolean }>()
const emit = defineEmits<{ mudou: [] }>()

const t = computed(() => TEXTOS_CRM[props.chave])
const estado = ref<ConectorCrm | null>(null)
const erroCarga = ref<string | null>(null)
const token = ref('')
const pesquisar = ref(true)
const ocupado = ref<'conectar' | 'sincronizar' | 'alterar' | 'desconectar' | null>(null)
const erroToken = ref<string | null>(null)

async function carregar() {
  erroCarga.value = null
  try {
    estado.value = (await conectoresApi.ver())[props.chave]
    pesquisar.value = estado.value.pesquisar_ao_ganhar ?? true
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  }
}

async function conectar() {
  erroToken.value = token.value.trim().length < 10 ? t.value.erroVazio : null
  if (erroToken.value) return
  ocupado.value = 'conectar'
  try {
    estado.value = await conectoresApi.conectarCrm(props.chave, token.value.trim(), pesquisar.value)
    token.value = ''
    emit('mudou')
    avisar.sucesso(`${t.value.nome} conectado. Agora traga as empresas e os contatos com “Sincronizar agora”.`)
  } catch (e) {
    erroToken.value = mensagemDoErro(e)
  } finally {
    ocupado.value = null
  }
}

async function sincronizar() {
  ocupado.value = 'sincronizar'
  try {
    const r = await conectoresApi.sincronizarCrm(props.chave)
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
  ocupado.value = 'alterar'
  try {
    estado.value = await conectoresApi.alterarCrm(props.chave, v)
  } catch (e) {
    pesquisar.value = !v
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function desconectar() {
  const ok = await confirmar({
    titulo: `Desconectar o ${t.value.nome}?`,
    mensagem: `O Toqqi apaga ${t.value.oToken} e deixa de pesquisar os negócios ganhos. Empresas e contatos já trazidos continuam aqui.`,
    confirmar: 'Desconectar',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = 'desconectar'
  try {
    await conectoresApi.desconectarCrm(props.chave)
    estado.value = { conectado: false }
    emit('mudou')
    avisar.sucesso(`${t.value.nome} desconectado.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
</script>

<template>
  <section class="flex flex-col gap-4" :class="props.embutido ? '' : 'cartao p-5 sm:p-6'" :aria-labelledby="`t-${chave}`" :data-secao-crm="chave">
    <header v-if="!props.embutido" class="flex items-start gap-3">
      <LogoParceiro :chave="chave" :nome="t.nome" :iniciais="t.iniciais" />
      <div class="min-w-0">
        <h2 :id="`t-${chave}`" class="text-base font-bold text-texto">{{ t.nome }}</h2>
        <p class="text-sm text-texto-suave">Traga as empresas e os contatos do seu CRM e pesquise o cliente quando um negócio for ganho.</p>
      </div>
    </header>
    <details class="rounded-xl border border-borda p-3 text-sm" :open="estado ? !estado.conectado : true" data-o-que-faz>
      <summary class="cursor-pointer font-semibold text-texto">O que a integração faz</summary>
      <dl class="mt-3 flex flex-col gap-2.5">
        <div v-for="item in t.oQueFaz" :key="item.titulo">
          <dt class="font-semibold text-texto">{{ item.titulo }}</dt>
          <dd class="text-texto-suave">{{ item.texto }}</dd>
        </div>
      </dl>
    </details>
    <Alerta v-if="erroCarga" tom="erro">{{ erroCarga }} <button type="button" class="link" @click="carregar">Tentar de novo</button></Alerta>

    <form v-else-if="estado && !estado.conectado" class="flex flex-col gap-4" novalidate @submit.prevent="conectar">
      <ol class="flex list-decimal flex-col gap-1.5 pl-5 text-sm text-texto-suave" :data-passos-crm="chave">
        <li v-for="(passo, i) in t.passos" :key="i">
          <template v-for="(parte, j) in passo" :key="j">
            <strong v-if="typeof parte === 'object' && 'forte' in parte">{{ parte.forte }}</strong>
            <a v-else-if="typeof parte === 'object'" :href="parte.link" target="_blank" rel="noopener noreferrer" class="link">{{ parte.texto }}</a>
            <template v-else>{{ parte }}</template>
          </template>
        </li>
      </ol>
      <Campo v-model="token" :rotulo="t.rotuloToken" tipo="password" autocomplete="off" spellcheck="false" :erro="erroToken" :data-token-crm="chave" />
      <div class="rounded-xl border border-borda p-4">
        <Interruptor v-model="pesquisar" rotulo="Pesquisar quando um negócio for ganho" :descricao="t.descricaoPesquisa" />
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
      <p v-if="estado.resumo" class="text-sm text-texto-suave" data-resumo-crm>
        Na última vez: {{ formatarNumero(estado.resumo.empresas_novas) }} empresas e {{ formatarNumero(estado.resumo.contatos_novos) }} contatos novos;
        {{ formatarNumero(estado.resumo.contatos_existentes) }} contatos já estavam no Toqqi
        <template v-if="estado.resumo.sem_email_ou_telefone">; {{ formatarNumero(estado.resumo.sem_email_ou_telefone) }} sem e-mail nem telefone ficaram de fora</template>.
        <template v-if="estado.resumo.limite_do_plano"> Parou no limite de contatos do seu plano.</template>
      </p>
      <div class="flex flex-col gap-2 rounded-xl border border-borda p-4">
        <Interruptor
          v-model="pesquisar"
          :desabilitado="ocupado !== null"
          rotulo="Pesquisar quando um negócio for ganho"
          :descricao="t.descricaoPesquisa"
          @update:model-value="alterar"
        />
        <p v-if="pesquisar && chave === 'hubspot'" class="text-xs text-texto-fraco" data-consulta-hubspot>
          {{ estado.consultado_em ? `Última consulta em ${formatarDataHora(estado.consultado_em)}.` : 'A primeira consulta sai em até 30 minutos.' }}
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Botao :carregando="ocupado === 'sincronizar'" :desabilitado="ocupado !== null && ocupado !== 'sincronizar'" :data-sincronizar-crm="chave" @click="sincronizar">Sincronizar agora</Botao>
        <Botao variante="perigo-suave" :carregando="ocupado === 'desconectar'" :desabilitado="ocupado !== null && ocupado !== 'desconectar'" @click="desconectar">Desconectar</Botao>
      </div>
      <p class="text-xs text-texto-fraco">Sincronizar cria as empresas e os contatos que faltam (com e-mail ou telefone). Nunca apaga nem muda o que já está no Toqqi.</p>
    </template>
  </section>
</template>
