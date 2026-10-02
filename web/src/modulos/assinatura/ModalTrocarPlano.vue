<script setup lang="ts">
// Trocar de plano: os 3 planos (o atual marcado), o novo valor, o efeito na fatura em aberto e no limite de contatos.
// Plano menor com mais contatos ativos que o limite avisa antes e não deixa trocar (a API também recusaria, com 422).
import { computed, ref, watch } from 'vue'
import { assinaturaApi, type EstadoAssinatura } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Modal from '@/components/ui/Modal.vue'
import EscolhaPlano from './EscolhaPlano.vue'
import { efeitoTroca, planoPorChave } from './logica'

const props = defineProps<{ estado: EstadoAssinatura }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ trocado: [EstadoAssinatura] }>()

const sessao = useSessaoStore()
const { enviando, erroGeral, executar, limpar } = useFormulario()
const atual = computed(() => props.estado.assinatura?.plano ?? null)
const escolhido = ref<string | null>(null)

watch(aberto, (v) => {
  if (!v) return
  limpar()
  escolhido.value = atual.value
})

const novo = computed(() => (escolhido.value && escolhido.value !== atual.value ? planoPorChave(props.estado.planos, escolhido.value) : null))
const efeito = computed(() => (novo.value ? efeitoTroca(props.estado, novo.value) : null))
const podeTrocar = computed(() => !!novo.value && !!efeito.value?.cabe && props.estado.disponivel)

async function trocar() {
  const plano = novo.value
  if (!plano || !podeTrocar.value) return
  const r = await executar(() => assinaturaApi.trocarPlano(plano.chave))
  if (!r) return
  emit('trocado', r)
  avisar.sucesso(`Plano trocado para ${plano.nome}.`)
  aberto.value = false
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    titulo="Trocar de plano"
    descricao="O novo valor vale para as próximas faturas e para as pendentes (as vencidas não mudam). O limite de contatos muda na hora."
    :bloqueado="enviando"
  >
    <form id="form-trocar-plano" class="flex flex-col gap-4" novalidate @submit.prevent="trocar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <EscolhaPlano
        v-model="escolhido"
        :planos="estado.planos"
        :contatos-ativos="estado.contatos_ativos"
        rotulo="Planos"
        :atual="atual"
        :bloquear-sem-espaco="false"
        :desabilitado="enviando"
        compacto
      />
      <!-- Sempre na página, para o leitor de tela anunciar o efeito quando outro plano é escolhido. -->
      <div aria-live="polite" class="flex flex-col gap-3">
        <div v-if="efeito" class="flex flex-col gap-1 rounded-xl bg-superficie-2 p-4 text-sm" data-efeito>
          <p class="font-semibold text-texto">{{ efeito.valor }}</p>
          <p v-if="efeito.fatura" class="text-texto-suave">{{ efeito.fatura }}</p>
          <p v-if="efeito.vencidas" class="text-texto-suave">{{ efeito.vencidas }}</p>
          <p class="text-texto-suave">{{ efeito.limite }}</p>
        </div>
        <Alerta v-if="efeito && efeito.aviso" tom="atencao">
          {{ efeito.aviso }}
          <RouterLink v-if="sessao.pode('contatos.ver')" to="/contatos" class="link ml-1">Ver contatos</RouterLink>
        </Alerta>
      </div>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-trocar-plano" :carregando="enviando" :desabilitado="!podeTrocar">
        {{ novo ? `Trocar para o ${novo.nome}` : 'Trocar de plano' }}
      </Botao>
    </template>
  </Modal>
</template>
