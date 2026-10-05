<script setup lang="ts">
// Etapa 5j: conector do Bling (ERP). "Conectar com o Bling" leva à autorização no Bling e volta para cá; a
// sincronização roda em segundo plano (o Bling é lento para dar o e-mail de cada cliente) e esta tela acompanha.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { conectoresApi, mensagemDoErro, type ConectorBling } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { formatarDataHora } from '@/utils/datas'
import { formatarNumero } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Interruptor from '@/components/ui/Interruptor.vue'

const props = defineProps<{ embutido?: boolean }>()
const emit = defineEmits<{ mudou: [] }>()
const estado = ref<ConectorBling | null>(null)
const erroCarga = ref<string | null>(null)
const pesquisar = ref(true)
const ocupado = ref<string | null>(null)
let espera: ReturnType<typeof setTimeout> | null = null

async function carregar() {
  try {
    const antes = estado.value?.sincronizando
    estado.value = (await conectoresApi.ver()).bling
    pesquisar.value = estado.value.pesquisar_ao_faturar ?? true
    erroCarga.value = null
    if (estado.value.sincronizando) espera = setTimeout(carregar, 3000)
    else if (antes) {
      avisar.sucesso('Sincronização com o Bling concluída.')
      emit('mudou')
    }
  } catch (e) {
    erroCarga.value = mensagemDoErro(e)
  }
}

async function conectar() {
  ocupado.value = 'conectar'
  try {
    window.location.assign((await conectoresApi.autorizarBling()).url)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
    ocupado.value = null
  }
}

async function sincronizar() {
  try {
    estado.value = await conectoresApi.sincronizarBling()
    espera = setTimeout(carregar, 3000)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  }
}

async function alterar(v: boolean) {
  try {
    estado.value = await conectoresApi.alterarBling(v)
  } catch (e) {
    pesquisar.value = !v
    avisar.erro(mensagemDoErro(e))
  }
}

async function desconectar() {
  const ok = await confirmar({
    titulo: 'Desconectar o Bling?',
    mensagem: 'O Toqqi apaga o acesso e deixa de receber as notas emitidas. Empresas e contatos já trazidos continuam aqui.',
    confirmar: 'Desconectar',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = 'desconectar'
  try {
    await conectoresApi.desconectarBling()
    await carregar()
    emit('mudou')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
onBeforeUnmount(() => espera && clearTimeout(espera))
</script>

<template>
  <section class="flex flex-col gap-4" :class="props.embutido ? '' : 'cartao p-5 sm:p-6'" data-secao-bling>
    <details class="rounded-xl border border-borda p-3 text-sm" :open="estado ? !estado.conectado : true" data-o-que-faz>
      <summary class="cursor-pointer font-semibold text-texto">O que a integração faz</summary>
      <dl class="mt-3 flex flex-col gap-2.5">
        <div><dt class="font-semibold text-texto">Clientes</dt><dd class="text-texto-suave">“Sincronizar agora” traz os clientes ativos do Bling: cada um vira uma empresa com um contato (e-mail e telefone do cadastro). Roda em segundo plano; a cada vez traz até 600 clientes novos e continua de onde parou. Nunca apaga nem muda o que já existe aqui.</dd></div>
        <div><dt class="font-semibold text-texto">Pesquisa na nota emitida</dt><dd class="text-texto-suave">Quando uma nota fiscal é emitida no Bling, o cliente da nota recebe a pesquisa NPS, uma vez por nota, pelas regras de envio da conta.</dd></div>
        <div><dt class="font-semibold text-texto">Segurança</dt><dd class="text-texto-suave">A conexão é autorizada por você na tela do Bling; o Toqqi guarda só o acesso, cifrado, e confere a assinatura de cada aviso.</dd></div>
        <div><dt class="font-semibold text-texto">Ainda não faz</dt><dd class="text-texto-suave">Não traz o valor mensal pelo faturamento e não devolve a nota ao Bling.</dd></div>
      </dl>
    </details>
    <Alerta v-if="erroCarga" tom="erro">{{ erroCarga }}</Alerta>

    <template v-else-if="estado && !estado.disponivel">
      <Alerta tom="info">A conexão com o Bling ainda não está disponível. Em breve.</Alerta>
    </template>

    <template v-else-if="estado && !estado.conectado">
      <p class="text-sm text-texto-suave">Você vai para o Bling, entra com o seu usuário e autoriza o Toqqi. Depois volta para cá.</p>
      <Botao class="self-start" :carregando="ocupado === 'conectar'" data-conectar-bling @click="conectar">Conectar com o Bling</Botao>
    </template>

    <template v-else-if="estado">
      <p class="text-sm text-texto">
        <strong class="text-sucesso">Conectado</strong>
        <template v-if="estado.sincronizando"> · sincronizando…</template>
        <template v-else-if="estado.sincronizado_em"> · última sincronização em {{ formatarDataHora(estado.sincronizado_em) }}</template>
        <template v-else> · ainda não sincronizado</template>
      </p>
      <Alerta v-if="estado.erro" tom="atencao">{{ estado.erro }}</Alerta>
      <p v-if="estado.resumo && !estado.sincronizando" class="text-sm text-texto-suave">
        Na última vez: {{ formatarNumero(estado.resumo.empresas_novas) }} empresas e {{ formatarNumero(estado.resumo.contatos_novos) }} contatos novos;
        {{ formatarNumero(estado.resumo.contatos_existentes) }} já estavam no Toqqi<template v-if="estado.resumo.inativos">; {{ estado.resumo.inativos }} inativos ignorados</template>.
        <template v-if="estado.resumo.cortado"> Ainda há clientes no Bling: sincronize de novo para continuar.</template>
        <template v-if="estado.resumo.limite_do_plano"> Parou no limite de contatos do seu plano.</template>
      </p>
      <div class="rounded-xl border border-borda p-4">
        <Interruptor v-model="pesquisar" rotulo="Pesquisar quando uma nota for emitida" descricao="O cliente da nota recebe a pesquisa NPS pelas regras de envio da conta (descadastro, descanso e canal)." @update:model-value="alterar" />
      </div>
      <div class="flex flex-wrap gap-2">
        <Botao :carregando="!!estado.sincronizando" @click="sincronizar">Sincronizar agora</Botao>
        <Botao variante="perigo-suave" :carregando="ocupado === 'desconectar'" @click="desconectar">Desconectar</Botao>
      </div>
    </template>
  </section>
</template>
