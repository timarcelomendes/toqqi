<script setup lang="ts">
// Confirma o envio manual (dizendo para quantos) e depois mostra o que saiu e o que ficou de fora.
import { computed, ref, watch } from 'vue'
import { ChevronDown, Send } from 'lucide-vue-next'
import { enviosApi, type FiltrosFila, type Id, type ResultadoDisparo } from '@/api'
import { useFormulario } from '@/composables/formulario'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Modal from '@/components/ui/Modal.vue'
import { contatos } from './logica'

export type AlvoDisparo =
  | { tipo: 'contatos'; ids: Id[]; nome?: string }
  | { tipo: 'fila'; quantidade: number; filtros: Omit<FiltrosFila, 'pagina' | 'por_pagina'> }

const props = defineProps<{ alvo: AlvoDisparo | null }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ enviado: [ResultadoDisparo]; 'pre-condicao': [] }>()

const { enviando, erroGeral, codigoErro, executar, limpar } = useFormulario()
const ignorarDescanso = ref(false)
const resultado = ref<ResultadoDisparo | null>(null)

const quantidade = computed(() => (props.alvo ? (props.alvo.tipo === 'fila' ? props.alvo.quantidade : props.alvo.ids.length) : 0))
const titulo = computed(() => {
  if (resultado.value) return 'Pronto!'
  const a = props.alvo
  if (a?.tipo === 'contatos' && a.ids.length === 1 && a.nome) return `Enviar a pesquisa para ${a.nome}?`
  return `Enviar a pesquisa para ${contatos(quantidade.value)}?`
})

watch(aberto, (v) => {
  if (!v) return
  limpar()
  resultado.value = null
  ignorarDescanso.value = false
})

async function enviar() {
  const a = props.alvo
  if (!a) return
  const r = await executar(() =>
    enviosApi.disparar(
      a.tipo === 'fila'
        ? { toda_fila: true, filtros: a.filtros, ...(ignorarDescanso.value ? { ignorar_descanso: true } : {}) }
        : { contato_ids: a.ids, ...(ignorarDescanso.value ? { ignorar_descanso: true } : {}) },
    ),
  )
  if (codigoErro.value === 'pre_condicao') emit('pre-condicao')
  if (!r) return
  resultado.value = { agendados: r.agendados ?? 0, ignorados: Array.isArray(r.ignorados) ? r.ignorados : [] }
  emit('enviado', resultado.value)
}
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="titulo" :bloqueado="enviando">
    <div v-if="resultado" class="flex flex-col gap-4" data-teste="resultado-disparo">
      <Alerta v-if="resultado.agendados" tom="sucesso" :titulo="resultado.agendados === 1 ? '1 pesquisa está saindo agora' : `${resultado.agendados.toLocaleString('pt-BR')} pesquisas estão saindo agora`">
        A lista se atualiza sozinha enquanto os e-mails saem. Pode continuar usando o Toqqi normalmente.
      </Alerta>
      <Alerta v-else tom="atencao" titulo="Nenhuma pesquisa saiu">Todos os contatos escolhidos ficaram de fora. Veja o motivo de cada um abaixo.</Alerta>

      <details v-if="resultado.ignorados.length" class="group rounded-xl border border-borda" :open="!resultado.agendados">
        <summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-texto [&::-webkit-details-marker]:hidden">
          <span>{{ resultado.ignorados.length === 1 ? '1 contato ficou de fora' : `${resultado.ignorados.length.toLocaleString('pt-BR')} contatos ficaram de fora` }}</span>
          <ChevronDown class="size-4 text-texto-fraco transition-transform group-open:rotate-180" aria-hidden="true" />
        </summary>
        <ul class="max-h-64 divide-y divide-borda overflow-y-auto border-t border-borda text-sm">
          <li v-for="i in resultado.ignorados" :key="String(i.contato_id)" class="flex flex-col px-4 py-2.5 sm:flex-row sm:gap-3">
            <span class="font-medium text-texto sm:w-2/5 sm:shrink-0">{{ i.nome }}</span>
            <span class="text-texto-suave">{{ i.motivo }}</span>
          </li>
        </ul>
      </details>
    </div>

    <form v-else id="form-disparo" class="flex flex-col gap-4" novalidate @submit.prevent="enviar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <p class="text-[0.95rem] leading-relaxed text-texto-suave">
        <template v-if="alvo?.tipo === 'fila'">
          Todos os contatos que estão na fila<template v-if="Object.keys(alvo.filtros).length"> (com os filtros que você escolheu)</template>
          recebem a pesquisa por e-mail agora: <strong class="text-texto">{{ contatos(quantidade) }}</strong>.
        </template>
        <template v-else>
          <strong class="text-texto">{{ quantidade === 1 ? 'Esta pessoa recebe' : `${contatos(quantidade)} recebem` }}</strong>
          a pesquisa por e-mail agora, mesmo que o próximo envio ainda não tenha chegado.
        </template>
      </p>
      <p class="text-sm text-texto-fraco">
        Quem não tem e-mail, saiu da lista ou recebeu outra pesquisa há pouco tempo fica de fora. Depois do envio você vê quem foi e o motivo.
      </p>
      <div class="rounded-xl border border-borda bg-superficie-2/50 p-3.5">
        <CaixaSelecao
          v-model="ignorarDescanso"
          rotulo="Enviar mesmo para quem está em descanso"
          descricao="O descanso evita cansar o cliente com pesquisas seguidas. Marque só se tiver um bom motivo, como um atendimento que acabou de acontecer."
        />
      </div>
    </form>

    <template #rodape>
      <Botao v-if="resultado" @click="aberto = false">Fechar</Botao>
      <template v-else>
        <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
        <Botao tipo="submit" form="form-disparo" :carregando="enviando" :desabilitado="!quantidade">
          <Send v-if="!enviando" class="size-4" aria-hidden="true" />
          {{ quantidade === 1 ? 'Enviar agora' : `Enviar para ${contatos(quantidade)}` }}
        </Botao>
      </template>
    </template>
  </Modal>
</template>
