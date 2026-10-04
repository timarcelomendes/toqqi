<script setup lang="ts">
// Plataforma (só superadmin). Etapa 5g: duas abas, como a Auditoria. "Contas" (as contas de clientes, a tela de antes) e
// "Parâmetros" (preços, limites, IA, WhatsApp e teste). A aba fica no endereço: /plataforma e /plataforma/parametros
// (/plataforma/contas vira /plataforma). Cada aba guarda o que tem enquanto a pessoa alterna (fica montada e escondida
// com v-show: por isso cada uma tem uma raiz só). O `teste.dias` que Parâmetros leu ou salvou passa para Contas, que
// assim mostra e pede o mesmo "+N dias" sem recarregar a página.
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import AbaContas from './AbaContas.vue'
import AbaParametros from './AbaParametros.vue'
import { ABAS_PLATAFORMA, abaPlataformaDaRota, type AbaPlataforma } from './parametros'

const rota = useRoute()
const router = useRouter()

const aba = ref<AbaPlataforma>(abaPlataformaDaRota(rota.params.aba))
const visitadas = ref(new Set<AbaPlataforma>([aba.value]))
/** `teste.dias` gravado no banco, quando a aba Parâmetros já o leu, salvou ou releu (null antes disso). */
const diasGravados = ref<number | null>(null)

/** O endereço certo de cada aba (Contas sem nada; os parâmetros em /plataforma/parametros). */
function escreverEndereco(a: AbaPlataforma) {
  const certo = a === 'parametros' ? 'parametros' : undefined
  if ((rota.params.aba || undefined) !== certo) {
    void router.replace({ path: certo ? '/plataforma/parametros' : '/plataforma', query: rota.query })
  }
}

if (rota.params.aba === 'contas') escreverEndereco(aba.value)

watch(aba, (a) => {
  visitadas.value.add(a)
  escreverEndereco(a)
})
// Voltar e avançar do navegador: a aba acompanha o endereço.
watch(
  () => rota.params.aba,
  () => {
    if (!rota.path.startsWith('/plataforma')) return
    const nova = abaPlataformaDaRota(rota.params.aba)
    if (nova !== aba.value) aba.value = nova
  },
)
</script>

<template>
  <CabecalhoPagina titulo="Plataforma" descricao="Contas de clientes e parâmetros do Toqqi. Área exclusiva da nossa equipe." />

  <Abas v-model="aba" :abas="ABAS_PLATAFORMA" rotulo="Seções da plataforma">
    <AbaContas v-if="visitadas.has('contas')" v-show="aba === 'contas'" :dias-gravados="diasGravados" />
    <AbaParametros v-if="visitadas.has('parametros')" v-show="aba === 'parametros'" @dias-teste="diasGravados = $event" />
  </Abas>
</template>
