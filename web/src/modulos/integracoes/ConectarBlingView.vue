<script setup lang="ts">
// /conectar/bling: a volta da instalação pela loja do Bling (Central de Extensões). A API já trocou o código pelos
// tokens; aqui a pessoa entra (ou cria a conta grátis) e o Toqqi liga o Bling à conta dela. Sem sessão, o código fica
// guardado neste navegador (instalacaoBling.ts) e o app volta para cá depois de entrar (AppLayout).
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CheckCircle2, PlugZap } from 'lucide-vue-next'
import { conectoresApi, mensagemDoErro } from '@/api'
import { avisar } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import { esquecerInstalacao, guardarInstalacao, instalacaoGuardada } from './instalacaoBling'

const rota = useRoute()
const router = useRouter()
const sessao = useSessaoStore()

const VOLTAR = '/conectar/bling'
const resultado = computed(() => (typeof rota.query.resultado === 'string' ? rota.query.resultado : null))
const codigo = ref<string | null>(null)
const ligando = ref(false)
const erro = ref<string | null>(null)

const situacao = computed<'falhou' | 'sem_instalacao' | 'entrar' | 'nao_admin' | 'ligando' | 'erro'>(() => {
  if (resultado.value) return 'falhou'
  if (!codigo.value) return 'sem_instalacao'
  if (!sessao.logado) return 'entrar'
  if (!sessao.admin) return 'nao_admin'
  return erro.value ? 'erro' : 'ligando'
})

async function ligar() {
  if (!codigo.value || ligando.value) return
  ligando.value = true
  erro.value = null
  try {
    await conectoresApi.ligarInstalacaoBling(codigo.value)
    esquecerInstalacao()
    avisar.sucesso('Bling conectado. Traga os clientes com “Sincronizar agora”.')
    await router.replace({ path: '/integracoes', query: { aba: 'crm', conector: 'bling' } })
  } catch (e) {
    erro.value = mensagemDoErro(e)
    if (/venceu|já foi usada|não pode mais ser lida/.test(erro.value)) esquecerInstalacao()
  } finally {
    ligando.value = false
  }
}

onMounted(() => {
  const daUrl = typeof rota.query.instalacao === 'string' ? rota.query.instalacao : null
  if (daUrl) {
    guardarInstalacao(daUrl)
    void router.replace({ path: VOLTAR }) // o código sai do endereço (histórico, prints)
  }
  codigo.value = daUrl ?? instalacaoGuardada()
  if (codigo.value && sessao.logado && sessao.admin) void ligar()
})
</script>

<template>
  <section class="flex w-full flex-col gap-5" aria-labelledby="t-conectar-bling" data-conectar-bling>
    <div class="flex items-center gap-3">
      <span class="grid size-11 place-items-center rounded-xl bg-marca-suave text-marca" aria-hidden="true"><PlugZap class="size-5" /></span>
      <h1 id="t-conectar-bling" class="text-xl font-bold text-texto">Conectar o Bling ao Toqqi</h1>
    </div>

    <template v-if="situacao === 'falhou'">
      <Alerta tom="erro" data-situacao="falhou">
        {{ resultado === 'negado' ? 'A autorização no Bling foi cancelada.' : 'Não conseguimos concluir a instalação com o Bling.' }}
        Instale de novo pela Central de Extensões do Bling ou, se já tem conta, conecte em Integrações › Bling.
      </Alerta>
      <div class="flex flex-wrap gap-2">
        <Botao :para="sessao.logado ? '/integracoes?aba=crm&conector=bling' : '/entrar'">{{ sessao.logado ? 'Abrir Integrações' : 'Entrar no Toqqi' }}</Botao>
      </div>
    </template>

    <template v-else-if="situacao === 'sem_instalacao'">
      <p class="text-texto-suave" data-situacao="sem_instalacao">
        Para conectar, instale o Toqqi pela Central de Extensões do Bling ou, já dentro do Toqqi, abra Integrações › Bling e
        clique em “Conectar com o Bling”.
      </p>
      <div class="flex flex-wrap gap-2">
        <Botao :para="sessao.logado ? '/integracoes?aba=crm&conector=bling' : '/entrar'">{{ sessao.logado ? 'Abrir Integrações' : 'Entrar no Toqqi' }}</Botao>
        <a href="/bling" class="inline-flex h-10 items-center rounded-xl px-3 text-sm font-semibold text-texto-suave hover:bg-superficie-2">Como funciona</a>
      </div>
    </template>

    <template v-else-if="situacao === 'entrar'">
      <p class="flex items-start gap-2 text-texto" data-situacao="entrar">
        <CheckCircle2 class="mt-0.5 size-5 shrink-0 text-sucesso" aria-hidden="true" />
        <span>O Bling autorizou o Toqqi. Falta só entrar na sua conta, ou criar uma, para ligar os dois.</span>
      </p>
      <p class="text-sm text-texto-suave">
        Quem ainda não usa o Toqqi começa com 14 dias de todos os recursos, sem cartão. Esta autorização fica guardada neste
        navegador por 24 horas.
      </p>
      <div class="flex flex-col gap-2 sm:flex-row">
        <Botao :para="{ path: '/cadastro', query: { voltar: VOLTAR } }" data-criar-conta>Criar conta grátis</Botao>
        <Botao variante="secundario" :para="{ path: '/entrar', query: { voltar: VOLTAR } }" data-entrar>Já tenho conta</Botao>
      </div>
    </template>

    <template v-else-if="situacao === 'nao_admin'">
      <Alerta tom="atencao" data-situacao="nao_admin">
        Só um administrador da sua empresa no Toqqi pode conectar o Bling. Peça a ele para abrir este mesmo link, ou entre com
        uma conta de administrador.
      </Alerta>
    </template>

    <template v-else-if="situacao === 'erro'">
      <Alerta tom="erro" data-situacao="erro">{{ erro }}</Alerta>
      <div class="flex flex-wrap gap-2">
        <Botao :carregando="ligando" @click="ligar">Tentar de novo</Botao>
        <Botao variante="secundario" para="/integracoes?aba=crm&conector=bling">Abrir Integrações</Botao>
      </div>
    </template>

    <Carregando v-else :linhas="2" rotulo="Conectando o Bling à sua conta" />
  </section>
</template>
