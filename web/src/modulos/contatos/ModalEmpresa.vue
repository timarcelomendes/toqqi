<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { empresasApi, type DadosEmpresa, type Empresa, type Id } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDecimal, formatarDocumento, lerMoeda } from '@/utils/formatos'
import { normalizarDocumento } from '@/utils/validacao'
import { MENSAGENS, documentoValido } from '@/modulos/configuracoes/empresa'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Modal from '@/components/ui/Modal.vue'
import Selecao from '@/components/ui/Selecao.vue'
import SelecaoCadastro from './SelecaoCadastro.vue'

const props = defineProps<{ empresa: Empresa | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [Empresa] }>()

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const { enviando, erroGeral, codigoErro, erros, executar, limpar } = useFormulario()
const novo = computed(() => !props.empresa)
const podeCriar = computed(() => sessao.pode('contatos.editar'))
const dados = reactive({
  nome: '',
  documento: '',
  grupo_id: '' as Id | '',
  segmento_id: '' as Id | '',
  responsavel_id: '' as Id | '',
  valor_mensal: '',
  cliente_desde: '',
  codigo_externo: '',
  ativa: true,
})
const locais = reactive<Record<string, string | undefined>>({})
const opcoesResponsaveis = computed(() => cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome })))
const salvo = ref(false)

watch(aberto, (v) => {
  if (!v) return
  limpar()
  salvo.value = false
  for (const k of Object.keys(locais)) delete locais[k]
  const e = props.empresa
  Object.assign(dados, {
    nome: e?.nome ?? '',
    documento: formatarDocumento(e?.documento),
    grupo_id: e?.grupo?.id ?? '',
    segmento_id: e?.segmento?.id ?? '',
    responsavel_id: e?.responsavel?.id ?? '',
    valor_mensal: formatarDecimal(e?.valor_mensal),
    cliente_desde: e?.cliente_desde?.slice(0, 10) ?? '',
    codigo_externo: e?.codigo_externo ?? '',
    ativa: e?.ativa ?? true,
  })
})

function erro(campo: string) {
  if (locais[campo]) return locais[campo]
  if (erros[campo]) return erros[campo]
  if (campo === 'nome' && codigoErro.value === 'nome_em_uso') return erroGeral.value
  return undefined
}
const erroTopo = computed(() => (codigoErro.value === 'nome_em_uso' && !erros.nome ? null : erroGeral.value))

// Valor que não dá para ler fica como foi digitado: ao salvar, o campo pede para conferir (em vez de sumir).
function aoSairValor() {
  const n = lerMoeda(dados.valor_mensal)
  if (n !== null) dados.valor_mensal = formatarDecimal(n)
}

async function salvar() {
  const doc = normalizarDocumento(dados.documento)
  const valor = dados.valor_mensal.trim() ? lerMoeda(dados.valor_mensal) : null
  locais.nome = dados.nome.trim() ? undefined : 'Informe o nome da empresa.'
  locais.documento = !doc
    ? undefined
    : doc.length !== 11 && doc.length !== 14
      ? 'O CPF tem 11 números e o CNPJ tem 14 caracteres.'
      : documentoValido(doc)
        ? undefined
        : MENSAGENS.documento
  locais.valor_mensal = dados.valor_mensal.trim() && (valor === null || valor < 0) ? 'Digite um valor, ex.: 1.250,00.' : undefined
  if (Object.values(locais).some(Boolean)) return
  const corpo: DadosEmpresa = {
    nome: dados.nome.trim(),
    documento: doc || null,
    grupo_id: dados.grupo_id === '' ? null : dados.grupo_id,
    segmento_id: dados.segmento_id === '' ? null : dados.segmento_id,
    responsavel_id: dados.responsavel_id === '' ? null : dados.responsavel_id,
    valor_mensal: valor,
    cliente_desde: dados.cliente_desde || null,
    codigo_externo: dados.codigo_externo.trim() || null,
    ativa: dados.ativa,
  }
  const e = await executar(() => (novo.value ? empresasApi.criar(corpo) : empresasApi.atualizar(props.empresa!.id, corpo)))
  if (!e) return
  emit('salvo', e)
  avisar.sucesso(novo.value ? `${e.nome} foi cadastrada.` : 'Alterações salvas.')
  aberto.value = false
}

onMounted(() => cadastros.garantir(['responsaveis']))
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="novo ? 'Nova empresa' : 'Editar empresa'" :descricao="novo ? 'Um cliente da sua empresa.' : empresa?.nome" :bloqueado="enviando" tamanho="lg">
    <form id="form-empresa" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>
      <Campo v-model="dados.nome" rotulo="Nome" obrigatorio data-autofoco autocomplete="off" maxlength="150" :erro="erro('nome')" />
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo
          v-model="dados.documento"
          rotulo="CNPJ ou CPF"
          opcional
          autocapitalize="characters"
          autocomplete="off"
          spellcheck="false"
          placeholder="00.000.000/0000-00"
          :mascara="formatarDocumento"
          :erro="erro('documento')"
        />
        <Campo v-model="dados.codigo_externo" rotulo="Código no seu sistema" opcional maxlength="80" :erro="erro('codigo_externo')" />
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <SelecaoCadastro v-model="dados.grupo_id" tipo="grupos" rotulo="Grupo" :pode-criar="podeCriar" :erro="erro('grupo_id')" />
        <SelecaoCadastro v-model="dados.segmento_id" tipo="segmentos" rotulo="Segmento" :pode-criar="podeCriar" :erro="erro('segmento_id')" />
      </div>
      <Selecao
        v-model="dados.responsavel_id"
        rotulo="Responsável pela carteira"
        :opcoes="opcoesResponsaveis"
        vazio="Ninguém"
        :erro="erro('responsavel_id')"
        :dica="opcoesResponsaveis.length ? undefined : 'Cadastre responsáveis na aba Responsáveis.'"
      />
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo v-model="dados.valor_mensal" rotulo="Valor mensal" opcional inputmode="decimal" placeholder="0,00" :erro="erro('valor_mensal')" @blur="aoSairValor">
          <template #antes><span class="text-sm font-semibold">R$</span></template>
        </Campo>
        <Campo v-model="dados.cliente_desde" rotulo="Cliente desde" tipo="date" opcional :erro="erro('cliente_desde')" />
      </div>
      <div class="rounded-xl border border-borda p-4">
        <Interruptor v-model="dados.ativa" rotulo="Empresa ativa" descricao="Empresas inativas continuam no histórico, mas saem dos filtros do dia a dia." />
      </div>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-empresa" :carregando="enviando">{{ novo ? 'Cadastrar empresa' : 'Salvar' }}</Botao>
    </template>
  </Modal>
</template>
