<script setup lang="ts">
// Plataforma › Parâmetros (etapa 5g, docs/api-etapa-5g.md §7): os quatro grupos (Planos, IA, WhatsApp automático, Teste
// e cortesia), cada um com o seu formulário e o seu "Salvar alterações", e o histórico de alterações. Salvar um grupo
// relê o histórico; "Recarregar" (depois do 409 de outra pessoa) relê só aquele grupo. O `teste.dias` gravado (lido, salvo
// ou relido) sobe em `diasTeste`, para a aba Contas usar o mesmo número no "+N dias" sem recarregar a página.
import { onMounted, ref, watch } from 'vue'
import { mensagemDoErro, parametrosApi, type GrupoParametrosPlataforma } from '@/api'
import { avisar } from '@/composables/avisos'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import CartaoParametros from './CartaoParametros.vue'
import HistoricoParametros from './HistoricoParametros.vue'
import { ehGrupoParametros } from './parametros'

const emit = defineEmits<{ diasTeste: [number] }>()

const grupos = ref<GrupoParametrosPlataforma[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const historico = ref<InstanceType<typeof HistoricoParametros> | null>(null)

// Os valores de um grupo só mudam aqui com o que está gravado (GET ao abrir, resposta do PUT ou "Recarregar"); o que a
// pessoa digita e ainda não salvou fica no formulário do cartão e não sobe.
watch(
  () => grupos.value.find((g) => g.grupo === 'teste')?.valores['teste.dias'],
  (dias) => {
    if (typeof dias === 'number' && Number.isInteger(dias) && dias > 0) emit('diasTeste', dias)
  },
)

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    const r = await parametrosApi.obter()
    // Só os grupos que a tela conhece, na ordem da API.
    grupos.value = (r.grupos ?? []).filter((g) => ehGrupoParametros(g.grupo))
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function substituir(g: GrupoParametrosPlataforma) {
  const i = grupos.value.findIndex((x) => x.grupo === g.grupo)
  if (i >= 0) grupos.value.splice(i, 1, g)
}

function aoSalvar(g: GrupoParametrosPlataforma) {
  substituir(g)
  historico.value?.recarregar()
}

/** Outra pessoa mudou o grupo: busca os valores de agora (os campos daquele cartão voltam a eles). */
async function recarregarGrupo(grupo: string) {
  try {
    const r = await parametrosApi.obter()
    const g = (r.grupos ?? []).find((x) => x.grupo === grupo)
    if (g) substituir({ ...g })
    historico.value?.recarregar()
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  }
}

onMounted(carregar)
</script>

<template>
  <div class="flex flex-col gap-6" data-aba-parametros>
    <p class="max-w-3xl text-[0.95rem] text-texto-suave">
      O que vale para todas as contas do Toqqi. Cada grupo é salvo à parte e fica no histórico. Limites, cotas, tetos e franquias valem na hora;
      o preço novo, só para assinaturas novas e trocas de plano.
    </p>

    <Carregando v-if="carregando" :linhas="5" rotulo="Carregando os parâmetros" />
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <template v-else>
      <CartaoParametros v-for="g in grupos" :key="g.grupo" :dados="g" @salvo="aoSalvar" @recarregar="recarregarGrupo(g.grupo)" />
    </template>

    <HistoricoParametros ref="historico" />
  </div>
</template>
