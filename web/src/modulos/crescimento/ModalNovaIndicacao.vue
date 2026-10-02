<script setup lang="ts">
// Registrar uma indicação à mão (ex.: veio por telefone ou numa visita). Sem a confirmação do cartão público: quem
// registra responde por ela. Quem indicou e o responsável vêm dos cadastros (pedem contatos.ver).
import { computed, reactive, ref, watch } from 'vue'
import { crescimentoApi, type Id, type Indicacao, type Referencia } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarTelefone } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'
import Selecao from '@/components/ui/Selecao.vue'
import CampoContato, { type ContatoEscolhido } from '@/modulos/contatos/CampoContato.vue'
import CampoEmpresa from '@/modulos/contatos/CampoEmpresa.vue'
import {
  LIMITE_EMPRESA_INDICACAO,
  LIMITE_NOME_INDICACAO,
  LIMITE_OBSERVACAO_INDICACAO,
  camposDoServidor,
  camposIndicacaoVazios,
  camposParaApi,
  validarIndicacao,
  type CamposIndicacao,
} from '@/pesquisa/indicacao'

const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ criada: [Indicacao] }>()

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const podeVerCadastros = computed(() => sessao.pode('contatos.ver'))
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const campos = reactive<CamposIndicacao>(camposIndicacaoVazios())
const indicadorContato = ref<ContatoEscolhido | null>(null)
const indicadorEmpresa = ref<Referencia | null>(null)
const responsavelId = ref<Id | ''>('')
const locais = reactive<Record<string, string>>({})

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  Object.assign(campos, camposIndicacaoVazios())
  indicadorContato.value = null
  indicadorEmpresa.value = null
  responsavelId.value = ''
  if (podeVerCadastros.value) cadastros.garantir(['responsaveis'])
})

// Escolher o contato que indicou já preenche a empresa dele (dá para trocar).
watch(indicadorContato, (c) => {
  if (c?.empresa && !indicadorEmpresa.value) indicadorEmpresa.value = { id: c.empresa.id, nome: c.empresa.nome }
})

const opcoesResponsaveis = computed(() => cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome })))
const erro = (c: string) => locais[c] ?? camposDoServidor(erros)[c] ?? erros[`${c}_id`] ?? null
const erroTopo = computed(() => (Object.keys(erros).length ? null : erroGeral.value))

async function salvar() {
  for (const k of Object.keys(locais)) delete locais[k]
  const v = validarIndicacao(campos)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    return
  }
  const i = await executar(() =>
    crescimentoApi.registrarIndicacao({
      ...camposParaApi(campos),
      indicador_contato_id: indicadorContato.value?.id ?? null,
      indicador_empresa_id: indicadorEmpresa.value?.id ?? null,
      responsavel_id: responsavelId.value === '' ? null : responsavelId.value,
    }),
  )
  if (!i) return
  emit('criada', i)
  avisar.sucesso(`Indicação de ${i.nome ?? campos.nome.trim()} registrada.`)
  aberto.value = false
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    titulo="Registrar indicação"
    descricao="Para quando a indicação chega por telefone, numa visita ou numa conversa."
    :bloqueado="enviando"
    tamanho="lg"
  >
    <form id="form-nova-indicacao" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>

      <Campo v-model="campos.nome" rotulo="Nome de quem foi indicado" obrigatorio autocomplete="off" data-autofoco :maxlength="LIMITE_NOME_INDICACAO" :erro="erro('nome')" />
      <Campo v-model="campos.empresa" rotulo="Empresa" opcional autocomplete="off" :maxlength="LIMITE_EMPRESA_INDICACAO" :erro="erro('empresa')" />
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo
          v-model="campos.telefone"
          rotulo="WhatsApp ou telefone"
          tipo="tel"
          inputmode="tel"
          autocomplete="off"
          placeholder="(11) 91234-5678"
          :mascara="formatarTelefone"
          :erro="erro('telefone')"
        />
        <Campo v-model="campos.email" rotulo="E-mail" tipo="email" inputmode="email" autocomplete="off" :erro="erro('email')" />
      </div>
      <p class="-mt-2 text-sm text-texto-fraco">Precisa de pelo menos um dos dois: telefone ou e-mail.</p>
      <AreaTexto v-model="campos.observacao" rotulo="Observação" opcional :linhas="3" :maximo="LIMITE_OBSERVACAO_INDICACAO" :erro="erro('observacao')" />

      <fieldset v-if="podeVerCadastros" class="flex flex-col gap-4 rounded-xl border border-borda p-4">
        <legend class="px-1 text-sm font-semibold text-texto">Quem indicou e quem cuida</legend>
        <CampoContato v-model="indicadorContato" rotulo="Contato que indicou (opcional)" :erro="erro('indicador_contato')" />
        <CampoEmpresa v-model="indicadorEmpresa" rotulo="Empresa de quem indicou" opcional :erro="erro('indicador_empresa')" />
        <!-- Em branco, a API põe o responsável da empresa de quem indicou (sem essa empresa, fica sem responsável) -->
        <Selecao
          v-model="responsavelId"
          rotulo="Responsável"
          :opcoes="opcoesResponsaveis"
          vazio="O da empresa de quem indicou"
          :erro="erro('responsavel')"
          dica="Quem vai falar com a pessoa indicada. Em branco: o responsável da empresa de quem indicou."
        />
      </fieldset>
      <p v-else class="text-sm text-texto-fraco">Seu perfil não tem acesso aos contatos: quem indicou e o responsável ficam em branco.</p>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-nova-indicacao" :carregando="enviando">Registrar indicação</Botao>
    </template>
  </Modal>
</template>
