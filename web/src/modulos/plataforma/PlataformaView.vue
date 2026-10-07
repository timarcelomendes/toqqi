<script setup lang="ts">
// Plataforma (só superadmin). Etapa 5h: abas, nesta ordem e endereços: Visão geral (/plataforma), Contas
// (/plataforma/contas), Parâmetros (/plataforma/parametros), Erros (/plataforma/erros) e Feedback
// (/plataforma/feedback). Cada aba guarda o que tem enquanto a pessoa alterna (fica montada e escondida com v-show: por isso cada uma tem uma raiz só) e só busca os dados
// quando é aberta pela primeira vez. O `teste.dias` que Parâmetros leu ou salvou passa para Contas (etapa 5g), que assim
// mostra e pede o mesmo "+N dias" sem recarregar a página.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import AbaContas from './AbaContas.vue'
import AbaErros from './AbaErros.vue'
import AbaFeedback from './AbaFeedback.vue'
import AbaParametros from './AbaParametros.vue'
import AbaVisao from './AbaVisao.vue'
import { usarFeedback } from '@/composables/feedback'
import { ABAS_PLATAFORMA, abaPlataformaDaRota, caminhoDaAba, type AbaPlataforma } from './abas'

const rota = useRoute()
const router = useRouter()

const daRota = () => abaPlataformaDaRota(rota.params.aba, rota.path)
const aba = ref<AbaPlataforma>(daRota())
const visitadas = ref(new Set<AbaPlataforma>([aba.value]))
// Feedback: o número do que precisa de atenção ao lado do nome da aba.
const { atencao } = usarFeedback()
const abas = computed(() =>
  ABAS_PLATAFORMA.map((a) => (a.valor === 'feedback' && atencao.value > 0 ? { ...a, rotulo: `${a.rotulo} (${atencao.value})` } : a)),
)
/** `teste.dias` gravado no banco, quando a aba Parâmetros já o leu, salvou ou releu (null antes disso). */
const diasGravados = ref<number | null>(null)

/** O endereço certo de cada aba (a Visão geral em /plataforma). */
function escreverEndereco(a: AbaPlataforma) {
  const certo = caminhoDaAba(a)
  if (rota.path.replace(/\/+$/, '') !== certo) void router.replace({ path: certo, query: rota.query })
}

watch(aba, (a) => {
  visitadas.value.add(a)
  escreverEndereco(a)
})
// Voltar e avançar do navegador: a aba acompanha o endereço.
watch(
  () => rota.path,
  () => {
    if (!rota.path.startsWith('/plataforma')) return
    const nova = daRota()
    if (nova !== aba.value) aba.value = nova
  },
)
</script>

<template>
  <CabecalhoPagina titulo="Plataforma" descricao="O negócio, as contas de clientes, os parâmetros, os erros e o feedback de quem usa o Toqqi. Área exclusiva da nossa equipe." />

  <Abas v-model="aba" :abas="abas" rotulo="Seções da plataforma">
    <AbaVisao v-if="visitadas.has('visao')" v-show="aba === 'visao'" />
    <AbaContas v-if="visitadas.has('contas')" v-show="aba === 'contas'" :dias-gravados="diasGravados" />
    <AbaParametros v-if="visitadas.has('parametros')" v-show="aba === 'parametros'" @dias-teste="diasGravados = $event" />
    <AbaErros v-if="visitadas.has('erros')" v-show="aba === 'erros'" />
    <AbaFeedback v-if="visitadas.has('feedback')" v-show="aba === 'feedback'" />
  </Abas>
</template>
