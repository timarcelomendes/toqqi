<script setup lang="ts">
// Etapa 5j: conector do RD Station CRM. O administrador cola o token de instância do RD; o Toqqi traz as empresas e
// os contatos ("Sincronizar agora") e, se ligado, manda a pesquisa NPS aos contatos de cada negócio ganho no RD.
import { onMounted, ref } from 'vue'
import { conectoresApi, mensagemDoErro, type ConectorRd } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { formatarDataHora } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'

const estado = ref<ConectorRd | null>(null)
const erroCarga = ref<string | null>(null)
const token = ref('')
const pesquisar = ref(true)
const ocupado = ref<'conectar' | 'sincronizar' | 'alterar' | 'desconectar' | null>(null)
const erroToken = ref<string | null>(null)

async function carregar() {
  erroCarga.value = null
  try {
    estado.value = (await conectoresApi.ver()).rdstation_crm
    pesquisar.value = estado.value.pesquisar_ao_ganhar ?? true
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  }
}

async function conectar() {
  erroToken.value = token.value.trim().length < 10 ? 'Cole o token de instância do RD Station CRM.' : null
  if (erroToken.value) return
  ocupado.value = 'conectar'
  try {
    estado.value = await conectoresApi.conectarRd(token.value.trim(), pesquisar.value)
    token.value = ''
    avisar.sucesso('RD Station CRM conectado. Agora traga as empresas e os contatos com “Sincronizar agora”.')
  } catch (e) {
    erroToken.value = mensagemDoErro(e)
  } finally {
    ocupado.value = null
  }
}

async function sincronizar() {
  ocupado.value = 'sincronizar'
  try {
    const r = await conectoresApi.sincronizarRd()
    avisar.sucesso(`Sincronizado: ${formatarNumero(r.empresas_novas)} empresas e ${formatarNumero(r.contatos_novos)} contatos novos.`)
    await carregar()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
    await carregar()
  } finally {
    ocupado.value = null
  }
}

async function alterar(v: boolean) {
  ocupado.value = 'alterar'
  try {
    estado.value = await conectoresApi.alterarRd(v)
  } catch (e) {
    pesquisar.value = !v
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function desconectar() {
  const ok = await confirmar({
    titulo: 'Desconectar o RD Station CRM?',
    mensagem: 'O Toqqi apaga o token e deixa de receber os negócios ganhos. Empresas e contatos já trazidos continuam aqui.',
    confirmar: 'Desconectar',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = 'desconectar'
  try {
    await conectoresApi.desconectarRd()
    estado.value = { conectado: false }
    avisar.sucesso('RD Station CRM desconectado.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-rd" data-secao-rd>
    <header>
      <h2 id="t-rd" class="text-base font-bold text-texto">RD Station CRM</h2>
      <p class="text-sm text-texto-suave">Traga as empresas e os contatos do seu CRM e pesquise o cliente quando um negócio for ganho.</p>
    </header>
    <Alerta v-if="erroCarga" tom="erro">{{ erroCarga }} <button type="button" class="link" @click="carregar">Tentar de novo</button></Alerta>

    <form v-else-if="estado && !estado.conectado" class="flex flex-col gap-4" novalidate @submit.prevent="conectar">
      <ol class="list-decimal pl-5 text-sm text-texto-suave">
        <li>No RD Station CRM, abra seu perfil e copie o <strong>Token de instância</strong>.</li>
        <li>Cole aqui e conecte. O token fica guardado cifrado e só é usado para falar com o RD.</li>
      </ol>
      <Campo v-model="token" rotulo="Token de instância" tipo="password" autocomplete="off" spellcheck="false" :erro="erroToken" data-token-rd />
      <div class="rounded-xl border border-borda p-4">
        <Interruptor v-model="pesquisar" rotulo="Pesquisar quando um negócio for ganho" descricao="Os contatos da negociação recebem a pesquisa NPS, pelas regras de envio da conta (descadastro, descanso e canal)." />
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
      <p v-if="estado.resumo" class="text-sm text-texto-suave" data-resumo-rd>
        Na última vez: {{ formatarNumero(estado.resumo.empresas_novas) }} empresas e {{ formatarNumero(estado.resumo.contatos_novos) }} contatos novos;
        {{ formatarNumero(estado.resumo.contatos_existentes) }} contatos já estavam no Toqqi
        <template v-if="estado.resumo.sem_email_ou_telefone">; {{ formatarNumero(estado.resumo.sem_email_ou_telefone) }} sem e-mail nem telefone ficaram de fora</template>.
        <template v-if="estado.resumo.limite_do_plano"> Parou no limite de contatos do seu plano.</template>
      </p>
      <div class="rounded-xl border border-borda p-4">
        <Interruptor
          v-model="pesquisar"
          :desabilitado="ocupado !== null"
          rotulo="Pesquisar quando um negócio for ganho"
          descricao="Os contatos da negociação recebem a pesquisa NPS, pelas regras de envio da conta (descadastro, descanso e canal)."
          @update:model-value="alterar"
        />
      </div>
      <div class="flex flex-wrap gap-2">
        <Botao :carregando="ocupado === 'sincronizar'" :desabilitado="ocupado !== null && ocupado !== 'sincronizar'" data-sincronizar-rd @click="sincronizar">Sincronizar agora</Botao>
        <Botao variante="perigo-suave" :carregando="ocupado === 'desconectar'" :desabilitado="ocupado !== null && ocupado !== 'desconectar'" @click="desconectar">Desconectar</Botao>
      </div>
      <p class="text-xs text-texto-fraco">Sincronizar cria as empresas e os contatos que faltam (com e-mail ou telefone). Nunca apaga nem muda o que já está no Toqqi.</p>
    </template>
  </section>
</template>
