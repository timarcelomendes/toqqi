<script setup lang="ts">
// Registrar à mão uma nota que chegou por telefone, WhatsApp, e-mail ou numa reunião.
import { computed, reactive, ref, watch } from 'vue'
import { Info } from 'lucide-vue-next'
import { respostasApi, type CanalManual, type RespostaItem } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import { hojeIso } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Modal from '@/components/ui/Modal.vue'
import Selecao from '@/components/ui/Selecao.vue'
import CampoContato, { type ContatoEscolhido } from '@/modulos/contatos/CampoContato.vue'
import SeletorNota from './SeletorNota.vue'
import { CANAIS_REGISTRO, LIMITE_COMENTARIO, validarRegistro } from './logica'

const props = defineProps<{ contatoInicial?: ContatoEscolhido | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ registrada: [RespostaItem] }>()

const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const sessao = useSessaoStore()
const hoje = ref(hojeIso())
const dados = reactive({
  contato: null as ContatoEscolhido | null,
  nota: null as number | null,
  canal: 'manual' as CanalManual,
  data: '',
  comentario: '',
})
const locais = reactive<Record<string, string>>({})

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  hoje.value = hojeIso()
  Object.assign(dados, { contato: props.contatoInicial ?? null, nota: null, canal: 'manual', data: hoje.value, comentario: '' })
})

const erro = (campo: string) => locais[campo] ?? erros[campo] ?? null
/** Sem acesso aos contatos não dá para buscar quem deu a nota (só registrar para um contato já escolhido). */
const semComoEscolherContato = computed(() => !sessao.pode('contatos.ver') && !dados.contato)
const erroTopo = computed(() => (Object.keys(erros).length ? null : erroGeral.value))

async function registrar() {
  for (const k of Object.keys(locais)) delete locais[k]
  const v = validarRegistro({ contatoId: dados.contato?.id ?? null, nota: dados.nota, data: dados.data, comentario: dados.comentario }, hoje.value)
  if (Object.keys(v).length) {
    Object.assign(locais, v)
    return
  }
  const r = await executar(() =>
    respostasApi.registrar({
      // O contato pode ter vindo do endereço (?contato_id=101, texto): no corpo vai como número.
      contato_id: typeof dados.contato!.id === 'string' && /^\d+$/.test(dados.contato!.id) ? Number(dados.contato!.id) : dados.contato!.id,
      nota: dados.nota!,
      canal: dados.canal,
      ...(dados.comentario.trim() ? { comentario: dados.comentario.trim() } : {}),
      // A data só vai quando não é hoje (em São Paulo): sem ela, a resposta fica com a hora em que foi
      // registrada; com ela, o servidor guarda o dia ao meio-dia.
      ...(dados.data && dados.data !== hojeIso() ? { data: dados.data } : {}),
    }),
  )
  if (!r) return
  emit('registrada', r)
  avisar.sucesso(
    r.acao ? `Resposta registrada. Como a nota pede cuidado, uma ação foi criada em Planos de ação.` : 'Resposta registrada.',
    dados.contato ? `Nota ${r.nota ?? dados.nota} de ${dados.contato.nome}` : undefined,
  )
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Registrar resposta" descricao="Uma nota que o cliente deu fora da pesquisa." tamanho="lg" :bloqueado="enviando">
    <form id="form-registrar-resposta" class="flex flex-col gap-5" novalidate @submit.prevent="registrar">
      <Alerta v-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>
      <Alerta v-if="semComoEscolherContato" tom="atencao" titulo="Não dá para escolher o contato">
        Peça a um administrador para liberar os contatos no seu perfil, ou registre a partir das respostas de um contato
        (filtrando a lista por ele).
      </Alerta>

      <CampoContato v-model="dados.contato" rotulo="Contato" obrigatorio :erro="erro('contato_id')" data-autofoco />

      <SeletorNota v-model="dados.nota" rotulo="Nota de 0 a 10" :erro="erro('nota')" />

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Selecao v-model="dados.canal" rotulo="Como chegou" :opcoes="CANAIS_REGISTRO" :erro="erro('canal')" />
        <Campo v-model="dados.data" rotulo="Data da resposta" tipo="date" min="2000-01-01" :max="hoje" :erro="erro('data')" />
      </div>

      <AreaTexto
        v-model="dados.comentario"
        rotulo="Comentário"
        opcional
        :linhas="3"
        :maximo="LIMITE_COMENTARIO"
        placeholder="O que o cliente disse, com as palavras dele."
        :erro="erro('comentario')"
      />

      <p class="flex items-start gap-2 rounded-xl bg-superficie-2 p-3 text-sm text-texto-suave">
        <Info class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
        <span>
          Conta nos números como qualquer resposta. Nota de 0 a 8 vira uma ação no quadro de Planos de ação (e nota 9 ou 10 também, se estiver ligado nas
          configurações). O cliente não recebe e-mail de agradecimento.
        </span>
      </p>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-registrar-resposta" :carregando="enviando" :desabilitado="semComoEscolherContato">Registrar resposta</Botao>
    </template>
  </Modal>
</template>
