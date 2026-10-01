<script setup lang="ts">
// Criar uma ação à mão (no quadro ou a partir de uma resposta).
import { computed, reactive, watch } from 'vue'
import { acoesApi, type Acao, type Id, type PrioridadeAcao, type Referencia } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'
import Selecao from '@/components/ui/Selecao.vue'
import CampoEmpresa from '@/modulos/contatos/CampoEmpresa.vue'
import SeletorPrioridade from './SeletorPrioridade.vue'

export interface InicioAcao {
  titulo?: string
  descricao?: string
  empresa?: Referencia | null
  contato?: Referencia | null
  resposta_id?: Id | null
  prioridade?: PrioridadeAcao
  prazo?: string | null
  /** Texto curto de onde a ação vem (ex.: "Da resposta de Ana Souza, nota 3"). */
  origem?: string
}

const props = defineProps<{ inicio?: InicioAcao | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ criada: [Acao] }>()

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const dados = reactive({
  titulo: '',
  descricao: '',
  empresa: null as Referencia | null,
  responsavel_id: '' as Id | '',
  prioridade: 'media' as PrioridadeAcao,
  prazo: '',
})
const locais = reactive<Record<string, string>>({})

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  const i = props.inicio ?? {}
  Object.assign(dados, {
    titulo: i.titulo ?? '',
    descricao: i.descricao ?? '',
    empresa: i.empresa ?? null,
    responsavel_id: '',
    prioridade: i.prioridade ?? 'media',
    prazo: i.prazo ?? '',
  })
  if (sessao.pode('contatos.ver')) cadastros.garantir(['responsaveis'])
})

const opcoesResponsaveis = computed(() => cadastros.listas.responsaveis.map((r) => ({ valor: r.id, rotulo: r.nome })))
const erro = (c: string) => locais[c] ?? erros[c] ?? null
const erroTopo = computed(() => (Object.keys(erros).length ? null : erroGeral.value))

async function criar() {
  for (const k of Object.keys(locais)) delete locais[k]
  const titulo = dados.titulo.trim()
  if (!titulo) locais.titulo = 'Dê um título para a ação, por exemplo: "Ligar para o cliente".'
  else if (titulo.length > 200) locais.titulo = 'Use até 200 caracteres no título.'
  if (dados.descricao.length > 4000) locais.descricao = 'Use até 4.000 caracteres na descrição.'
  if (Object.keys(locais).length) return
  const i = props.inicio ?? {}
  const a = await executar(() =>
    acoesApi.criar({
      titulo,
      ...(dados.descricao.trim() ? { descricao: dados.descricao.trim() } : {}),
      ...(dados.empresa ? { empresa_id: dados.empresa.id } : {}),
      ...(i.contato ? { contato_id: i.contato.id } : {}),
      ...(i.resposta_id !== undefined && i.resposta_id !== null ? { resposta_id: i.resposta_id } : {}),
      ...(dados.responsavel_id !== '' ? { responsavel_id: dados.responsavel_id } : {}),
      prioridade: dados.prioridade,
      ...(dados.prazo ? { prazo: dados.prazo } : {}),
    }),
  )
  if (!a) return
  emit('criada', a)
  avisar.sucesso('Ação criada. Ela está na coluna A fazer.')
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Nova ação" :descricao="inicio?.origem ?? 'Uma tarefa para cuidar de um cliente.'" tamanho="lg" :bloqueado="enviando">
    <form id="form-nova-acao" class="flex flex-col gap-4" novalidate @submit.prevent="criar">
      <Alerta v-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>
      <Campo v-model="dados.titulo" rotulo="Título" obrigatorio maxlength="200" autocomplete="off" data-autofoco :erro="erro('titulo')" />
      <AreaTexto v-model="dados.descricao" rotulo="Descrição" opcional :linhas="3" :maximo="4000" placeholder="O que precisa ser feito e por quê." :erro="erro('descricao')" />
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <CampoEmpresa v-model="dados.empresa" rotulo="Empresa" opcional placeholder="Digite para buscar" :erro="erro('empresa_id')" />
        <Selecao
          v-model="dados.responsavel_id"
          rotulo="Responsável"
          :opcoes="opcoesResponsaveis"
          :vazio="dados.empresa ? 'O responsável da empresa' : 'Escolher depois'"
          :desabilitado="!sessao.pode('contatos.ver')"
          :dica="sessao.pode('contatos.ver') ? undefined : 'Seu perfil não tem acesso à lista de responsáveis.'"
          :erro="erro('responsavel_id')"
        />
      </div>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SeletorPrioridade v-model="dados.prioridade" :erro="erro('prioridade')" />
        <Campo v-model="dados.prazo" rotulo="Prazo" opcional tipo="date" :erro="erro('prazo')" />
      </div>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-nova-acao" :carregando="enviando">Criar ação</Botao>
    </template>
  </Modal>
</template>
