<script setup lang="ts">
// Resultado da última oferta feita a uma empresa: aceitou (com o valor, opcional), recusou ou ficou sem resposta.
// Resultado novo começa sem nada marcado; "Mudar resultado" abre com o resultado e o valor que já estavam.
import { computed, ref, watch } from 'vue'
import { crescimentoApi, type DadosResultadoOferta, type Oportunidade, type ResultadoOferta, type UltimaOferta } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { formatarData } from '@/utils/datas'
import { formatarDecimal, lerMoeda } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'
import { ORDEM_RESULTADOS, RESULTADOS_OFERTA, numeroDecimal } from './logica'

const props = defineProps<{ oportunidade: Oportunidade | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [empresaId: Oportunidade['empresa']['id'], oferta: UltimaOferta] }>()

const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
/** '' = nada marcado ainda (resultado novo). */
const resultado = ref<ResultadoOferta | ''>('')
const valor = ref('')
const erroValor = ref<string | null>(null)
const erroResultado = ref<string | null>(null)
const opcoes: { valor: ResultadoOferta | ''; rotulo: string }[] = ORDEM_RESULTADOS.map((r) => ({ valor: r, rotulo: RESULTADOS_OFERTA[r].rotulo }))
const oferta = computed(() => props.oportunidade?.ultima_oferta ?? null)
/** O valor que a oferta já tem (só com 'aceitou'): o campo vazio não o apaga. */
const valorAnterior = computed(() => (oferta.value?.resultado === 'aceitou' ? numeroDecimal(oferta.value.valor) : null))

watch(aberto, (v) => {
  if (!v) return
  limpar()
  erroValor.value = null
  erroResultado.value = null
  resultado.value = oferta.value?.resultado ?? ''
  valor.value = formatarDecimal(valorAnterior.value)
})
watch(valor, () => (erroValor.value = null))
watch(resultado, () => (erroResultado.value = null))

function aoSairValor() {
  const n = lerMoeda(valor.value)
  if (n !== null && n >= 0) valor.value = formatarDecimal(n)
}

async function salvar() {
  const o = props.oportunidade
  const of = oferta.value
  if (!o || !of || enviando.value) return
  const escolhido = resultado.value
  if (!escolhido) {
    erroResultado.value = 'Escolha como foi a oferta.'
    return
  }
  // Campo vazio não manda `valor`: a API mantém o que já estava (e os outros resultados o limpam).
  const dados: DadosResultadoOferta = { resultado: escolhido }
  if (escolhido === 'aceitou' && valor.value.trim()) {
    const v = lerMoeda(valor.value)
    if (v === null || v < 0) {
      erroValor.value = 'Digite um valor, ex.: 1.250,00.'
      return
    }
    dados.valor = v
  }
  const r = await executar(() => crescimentoApi.registrarResultado(of.id, dados))
  if (r === undefined && (erroGeral.value || Object.keys(erros).length)) return
  const veio = r && typeof r === 'object' ? r : null
  const nova: UltimaOferta = {
    id: of.id,
    criada_em: veio?.criada_em || of.criada_em,
    resultado: veio?.resultado ?? escolhido,
    valor: veio && 'valor' in veio ? veio.valor : escolhido === 'aceitou' ? (dados.valor ?? of.valor) : null,
  }
  emit('salvo', o.empresa.id, nova)
  const valorFinal = nova.resultado === 'aceitou' ? numeroDecimal(nova.valor) : null
  const valorTexto = valorFinal ? ` (R$ ${formatarDecimal(valorFinal)})` : ''
  avisar.sucesso(`Resultado registrado: ${RESULTADOS_OFERTA[nova.resultado ?? escolhido].rotulo.toLowerCase()}${valorTexto}.`)
  aberto.value = false
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    titulo="Resultado da oferta"
    :descricao="oportunidade ? `${oportunidade.empresa.nome}${oferta ? ` · oferta de ${formatarData(oferta.criada_em)}` : ''}` : undefined"
    :bloqueado="enviando"
    tamanho="sm"
  >
    <form id="form-resultado-oferta" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroGeral && !erros.valor" tom="erro">{{ erroGeral }}</Alerta>
      <div class="flex flex-col gap-2">
        <p class="text-sm font-semibold text-texto" aria-hidden="true">Como foi?</p>
        <BotoesSegmentados v-model="resultado" :opcoes="opcoes" rotulo="Como foi a oferta" bloco />
        <p v-if="erroResultado" role="alert" class="text-sm font-medium text-erro" data-erro-resultado>{{ erroResultado }}</p>
      </div>
      <Campo
        v-if="resultado === 'aceitou'"
        v-model="valor"
        rotulo="Valor da venda"
        opcional
        inputmode="decimal"
        placeholder="0,00"
        :erro="erroValor ?? erros.valor"
        :dica="
          valorAnterior !== null
            ? 'Entra na receita das ofertas, no resumo do topo. Em branco, fica o valor já registrado (para zerar, digite 0).'
            : 'Entra na receita das ofertas, no resumo do topo.'
        "
        @blur="aoSairValor"
      >
        <template #antes><span class="text-sm font-semibold">R$</span></template>
      </Campo>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-resultado-oferta" :carregando="enviando">Salvar resultado</Botao>
    </template>
  </Modal>
</template>
