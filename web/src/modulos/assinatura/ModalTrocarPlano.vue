<script setup lang="ts">
// Trocar de plano: os 3 planos (o atual marcado), o novo valor, o efeito na fatura em aberto e no limite de contatos.
// Plano menor com mais contatos ativos que o limite avisa antes e não deixa trocar (a API também recusaria, com 422).
// Etapa 5g: o plano atual mostra o valor contratado quando o preço de hoje é outro; trocar manda sempre o preço mostrado
// e, se ele mudou nesse meio-tempo (409 `preco_mudou`), a tela relê os planos e explica. Se a API recusar o preço mandado
// (422 no campo `preco`), o alerta traz a mensagem dela e "Recarregar", que recarrega a página.
import { computed, nextTick, ref, watch } from 'vue'
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
const emit = defineEmits<{ trocado: [EstadoAssinatura]; recarregar: [] }>()

const sessao = useSessaoStore()
const { enviando, erroGeral, codigoErro, erros, executar, limpar } = useFormulario()
const atual = computed(() => props.estado.assinatura?.plano ?? null)
const escolhido = ref<string | null>(null)
const formTroca = ref<HTMLFormElement | null>(null)
/** 422 no campo `preco`: a API não aceitou o preço que esta tela mandou; só recarregando a página. */
const erroPreco = computed(() => erros.preco ?? null)

function recarregarPagina() {
  location.reload()
}

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
  const r = await executar(() => assinaturaApi.trocarPlano(plano.chave, plano.preco))
  if (!r) {
    // O preço mudou desde que a janela abriu: a tela busca os planos de novo e a mensagem da API explica.
    if (codigoErro.value === 'preco_mudou') emit('recarregar')
    else if (erroPreco.value) {
      // O botão de trocar desligou enquanto enviava: o foco vai ao "Recarregar" do alerta (e fica na janela).
      await nextTick()
      formTroca.value?.querySelector<HTMLElement>('[data-recarregar]')?.focus()
    }
    return
  }
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
    <form id="form-trocar-plano" ref="formTroca" class="flex flex-col gap-4" novalidate @submit.prevent="trocar">
      <Alerta v-if="erroGeral" :tom="erroPreco || codigoErro === 'preco_mudou' ? 'atencao' : 'erro'" data-erro-troca>
        {{ erroPreco ?? erroGeral }}
        <button v-if="erroPreco" type="button" class="link ml-1" data-recarregar @click="recarregarPagina">Recarregar</button>
      </Alerta>
      <EscolhaPlano
        v-model="escolhido"
        :planos="estado.planos"
        :contatos-ativos="estado.contatos_ativos"
        rotulo="Planos"
        :atual="atual"
        :bloquear-sem-espaco="false"
        :desabilitado="enviando"
        :contratado="estado.assinatura?.valor ?? null"
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
