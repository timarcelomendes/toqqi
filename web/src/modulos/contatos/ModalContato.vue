<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { contatosApi, type Contato, type DadosContato, type Id, type Referencia } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { telefoneParaCampo } from '@/utils/formatos'
import { apenasDigitos, emailValido, formatarTelefone } from '@/utils/validacao'
import AlertaLimitePlano from '@/components/app/AlertaLimitePlano.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import Modal from '@/components/ui/Modal.vue'
import CampoEmpresa from './CampoEmpresa.vue'
import SelecaoCadastro from './SelecaoCadastro.vue'

const props = defineProps<{ contato: Contato | null; empresaInicial?: Referencia | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [Contato] }>()

const sessao = useSessaoStore()
const { enviando, erroGeral, codigoErro, erros, executar, limpar } = useFormulario()
const novo = computed(() => !props.contato)
const podeCriarCadastros = computed(() => sessao.pode('contatos.editar'))
const dados = reactive({
  nome: '',
  email: '',
  telefone: '',
  empresa: null as Referencia | null,
  cargo_id: '' as Id | '',
  perfil_id: '' as Id | '',
  codigo_externo: '',
  recebe_pesquisas: true,
  ativo: true,
})
const locais = reactive<Record<string, string | undefined>>({})
const mostrarMais = ref(false)

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  const c = props.contato
  Object.assign(dados, {
    nome: c?.nome ?? '',
    email: c?.email ?? '',
    telefone: telefoneParaCampo(c?.telefone),
    empresa: c?.empresa ?? props.empresaInicial ?? null,
    cargo_id: c?.cargo?.id ?? '',
    perfil_id: c?.perfil?.id ?? '',
    codigo_externo: c?.codigo_externo ?? '',
    recebe_pesquisas: c?.recebe_pesquisas ?? true,
    ativo: c?.ativo ?? true,
  })
  mostrarMais.value = !!c?.codigo_externo
})

function aoDigitarTelefone(v: string) {
  dados.telefone = formatarTelefone(v)
}

function erro(campo: string) {
  if (locais[campo]) return locais[campo]
  if (erros[campo]) return erros[campo]
  if (campo === 'email' && codigoErro.value === 'email_em_uso') return erroGeral.value
  return undefined
}
const limiteDoPlano = computed(() => codigoErro.value === 'limite_do_plano')
const erroTopo = computed(() => {
  if (limiteDoPlano.value) return null
  if (codigoErro.value === 'email_em_uso' && !erros.email) return null
  return erroGeral.value
})

async function salvar() {
  const email = dados.email.trim()
  const tel = apenasDigitos(dados.telefone)
  locais.nome = dados.nome.trim() ? undefined : 'Informe o nome.'
  locais.email = email && !emailValido(email) ? 'Confira o e-mail: parece que falta alguma parte.' : undefined
  locais.telefone = tel && (tel.length < 10 || tel.length > 13) ? 'Informe DDD e número, ex.: (11) 91234-5678.' : undefined
  if (!email && !tel && !locais.email) locais.email = 'Informe o e-mail ou o telefone (pelo menos um dos dois).'
  if (Object.values(locais).some(Boolean)) return

  const corpo: DadosContato = {
    nome: dados.nome.trim(),
    email: email || null,
    telefone: tel || null,
    empresa_id: dados.empresa?.id ?? null,
    cargo_id: dados.cargo_id === '' ? null : dados.cargo_id,
    perfil_id: dados.perfil_id === '' ? null : dados.perfil_id,
    codigo_externo: dados.codigo_externo.trim() || null,
    recebe_pesquisas: dados.recebe_pesquisas,
    ativo: dados.ativo,
  }
  const c = await executar(() => (novo.value ? contatosApi.criar(corpo) : contatosApi.atualizar(props.contato!.id, corpo)))
  if (!c) return
  emit('salvo', c)
  avisar.sucesso(novo.value ? `${c.nome} foi cadastrado(a).` : 'Alterações salvas.')
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="novo ? 'Novo contato' : 'Editar contato'" :descricao="novo ? 'Quem vai receber as pesquisas.' : contato?.nome" :bloqueado="enviando" tamanho="lg">
    <form id="form-contato" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <AlertaLimitePlano v-if="limiteDoPlano" :mensagem="erroGeral" />
      <Alerta v-else-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>

      <Campo v-model="dados.nome" rotulo="Nome" autocomplete="off" obrigatorio data-autofoco maxlength="150" :erro="erro('nome')" />
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo v-model="dados.email" rotulo="E-mail" tipo="email" inputmode="email" autocomplete="off" :erro="erro('email')" />
        <Campo
          :model-value="dados.telefone"
          rotulo="Telefone / WhatsApp"
          tipo="tel"
          inputmode="tel"
          autocomplete="off"
          placeholder="(11) 91234-5678"
          :erro="erro('telefone')"
          @update:model-value="aoDigitarTelefone"
        />
      </div>
      <p class="-mt-2 text-sm text-texto-fraco">Precisa de pelo menos um dos dois: e-mail ou telefone.</p>

      <CampoEmpresa v-model="dados.empresa" rotulo="Empresa" opcional :pode-criar="podeCriarCadastros" :erro="erro('empresa_id')" placeholder="Busque ou crie uma empresa" />
      <div class="grid gap-4 sm:grid-cols-2">
        <SelecaoCadastro v-model="dados.cargo_id" tipo="cargos" rotulo="Cargo" :pode-criar="podeCriarCadastros" :erro="erro('cargo_id')" />
        <SelecaoCadastro
          v-model="dados.perfil_id"
          tipo="perfis"
          rotulo="Perfil"
          :pode-criar="podeCriarCadastros"
          :erro="erro('perfil_id')"
          dica="Ex.: Decisor, Influenciador."
        />
      </div>

      <div class="flex flex-col gap-4 rounded-xl border border-borda p-4">
        <Interruptor v-model="dados.recebe_pesquisas" rotulo="Recebe pesquisas" descricao="Desligue se a pessoa não quer mais receber." />
        <Interruptor v-model="dados.ativo" rotulo="Contato ativo" descricao="Inativos não recebem nada e não contam no limite do plano." />
      </div>

      <button v-if="!mostrarMais" type="button" class="link w-fit text-sm" @click="mostrarMais = true">Mais opções</button>
      <Campo
        v-else
        v-model="dados.codigo_externo"
        rotulo="Código no seu sistema"
        opcional
        dica="O código deste cliente no seu ERP ou CRM, se quiser ligar os dois."
        maxlength="80"
        :erro="erro('codigo_externo')"
      />
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-contato" :carregando="enviando">{{ novo ? 'Cadastrar contato' : 'Salvar' }}</Botao>
    </template>
  </Modal>
</template>
