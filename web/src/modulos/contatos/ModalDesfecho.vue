<script setup lang="ts">
// Etapa 5i (desfecho): "Marcar como perdida" (data, motivo e detalhe; os contatos ativos ficam inativos) e "Voltou a
// ser cliente" (valor mensal, renovação e reativar os contatos que a perda desativou). É o que alimenta Relatórios ›
// Desfecho: quem saiu, por quê e o que dizia antes de sair.
import { computed, reactive, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { empresasApi, type Empresa, type MotivoPerda } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import { formatarDecimal, formatarNumero, lerMoeda } from '@/utils/formatos'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Modal from '@/components/ui/Modal.vue'
import Selecao from '@/components/ui/Selecao.vue'
import { MOTIVOS_PERDA } from './desfecho'

const props = defineProps<{ empresa: Empresa | null; modo: 'perda' | 'retorno' }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [Empresa] }>()

const sessao = useSessaoStore()
const { enviando, erroGeral, codigoErro, erros, executar, limpar } = useFormulario()
const hoje = hojeIso()
const dados = reactive({
  perdida_em: hoje,
  motivo_perda: '' as MotivoPerda | '',
  motivo_detalhe: '',
  valor_mensal: '',
  renovacao_em: '',
  reativar: true,
})
const locais = reactive<Record<string, string | undefined>>({})

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  const e = props.empresa
  Object.assign(dados, {
    perdida_em: hoje,
    motivo_perda: '',
    motivo_detalhe: '',
    valor_mensal: formatarDecimal(e?.valor_mensal),
    renovacao_em: e?.renovacao_em?.slice(0, 10) ?? '',
    reativar: true,
  })
})

const contatos = computed(() => props.empresa?.contatos ?? 0)
const erro = (campo: string) => locais[campo] || erros[campo] || undefined

async function salvar() {
  const e = props.empresa
  if (!e) return
  if (props.modo === 'perda') {
    locais.motivo_perda = dados.motivo_perda ? undefined : 'Escolha o motivo.'
    locais.motivo_detalhe =
      dados.motivo_perda === 'outro' && dados.motivo_detalhe.trim().length < 3 ? 'Conte em poucas palavras o motivo.' : undefined
    locais.perdida_em = !dados.perdida_em ? 'Informe a data.' : dados.perdida_em > hoje ? 'A data não pode ser no futuro.' : undefined
    if (Object.values(locais).some(Boolean)) return
    const r = await executar(() =>
      empresasApi.perder(e.id, {
        perdida_em: dados.perdida_em,
        motivo_perda: dados.motivo_perda as MotivoPerda,
        motivo_detalhe: dados.motivo_detalhe.trim() || null,
      }),
    )
    if (!r) return
    emit('salvo', r)
    avisar.sucesso(
      r.contatos_desativados
        ? `${r.nome} foi marcada como perdida. ${formatarNumero(r.contatos_desativados)} ${r.contatos_desativados === 1 ? 'contato ficou inativo' : 'contatos ficaram inativos'}.`
        : `${r.nome} foi marcada como perdida.`,
    )
  } else {
    const valor = dados.valor_mensal.trim() ? lerMoeda(dados.valor_mensal) : null
    locais.valor_mensal = dados.valor_mensal.trim() && (valor === null || valor < 0) ? 'Digite um valor, ex.: 1.250,00.' : undefined
    if (Object.values(locais).some(Boolean)) return
    const r = await executar(() =>
      empresasApi.voltar(e.id, { valor_mensal: valor, renovacao_em: dados.renovacao_em || null, reativar_contatos: dados.reativar }),
    )
    if (!r) return
    emit('salvo', r)
    avisar.sucesso(
      r.contatos_reativados
        ? `${r.nome} voltou a ser cliente, com ${formatarNumero(r.contatos_reativados)} ${r.contatos_reativados === 1 ? 'contato reativado' : 'contatos reativados'}.`
        : `${r.nome} voltou a ser cliente.`,
    )
  }
  aberto.value = false
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    :titulo="modo === 'perda' ? 'Marcar como perdida' : 'Voltou a ser cliente'"
    :descricao="empresa?.nome"
    :bloqueado="enviando"
  >
    <form id="form-desfecho" class="flex flex-col gap-4" novalidate data-modal-desfecho @submit.prevent="salvar">
      <Alerta v-if="erroGeral" tom="erro">
        {{ erroGeral }}
        <RouterLink v-if="codigoErro === 'limite_do_plano' && sessao.pode('assinatura.gerenciar')" to="/assinatura" class="link">Ver planos</RouterLink>
      </Alerta>
      <template v-if="modo === 'perda'">
        <div class="grid gap-4 sm:grid-cols-2">
          <Selecao v-model="dados.motivo_perda" rotulo="Motivo" :opcoes="MOTIVOS_PERDA" vazio="Escolha" :erro="erro('motivo_perda')" />
          <Campo v-model="dados.perdida_em" rotulo="Deixou de ser cliente em" tipo="date" :max="hoje" :erro="erro('perdida_em')" />
        </div>
        <AreaTexto
          v-model="dados.motivo_detalhe"
          rotulo="O que aconteceu"
          :opcional="dados.motivo_perda !== 'outro'"
          contador
          :maximo="300"
          :linhas="2"
          placeholder="Ex.: fechou com outro fornecedor pelo preço."
          :erro="erro('motivo_detalhe')"
        />
        <Alerta tom="info">
          <template v-if="contatos > 0">Os contatos ativos desta empresa ficam inativos e param de receber pesquisas. </template>
          Ela sai do Início, das oportunidades e da carteira ativa, e entra em Relatórios › Desfecho.
        </Alerta>
      </template>
      <template v-else>
        <div class="grid gap-4 sm:grid-cols-2">
          <Campo v-model="dados.valor_mensal" rotulo="Valor mensal" opcional inputmode="decimal" placeholder="0,00" :erro="erro('valor_mensal')">
            <template #antes><span class="text-sm font-semibold">R$</span></template>
          </Campo>
          <Campo v-model="dados.renovacao_em" rotulo="Renovação do contrato" tipo="date" opcional :erro="erro('renovacao_em')" />
        </div>
        <div class="rounded-xl border border-borda p-4">
          <Interruptor v-model="dados.reativar" rotulo="Reativar os contatos" descricao="Os contatos que ficaram inativos quando a empresa foi marcada como perdida voltam a receber pesquisas." />
        </div>
      </template>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-desfecho" :variante="modo === 'perda' ? 'perigo' : 'primario'" :carregando="enviando">
        {{ modo === 'perda' ? 'Marcar como perdida' : 'Voltou a ser cliente' }}
      </Botao>
    </template>
  </Modal>
</template>
