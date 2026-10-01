<script setup lang="ts">
// Mostra uma chave ou segredo uma única vez. Só fecha depois que a pessoa confirma que guardou.
import { computed, ref, watch } from 'vue'
import { KeyRound } from 'lucide-vue-next'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Modal from '@/components/ui/Modal.vue'
import { confirmarGuardado, fecharSegredo, mostrarSegredo, podeFecharSegredo, segredoVazio, type EstadoSegredo } from './logica'

const props = withDefaults(
  defineProps<{
    /** O valor a mostrar. Quando chega um novo, o modal abre. */
    segredo: string | null
    titulo: string
    descricao?: string
    rotuloCampo?: string
  }>(),
  { rotuloCampo: 'Chave' },
)
const emit = defineEmits<{ fechado: [] }>()

const estado = ref<EstadoSegredo>(segredoVazio())
watch(
  () => props.segredo,
  (v) => {
    if (v) estado.value = mostrarSegredo(v)
  },
  { immediate: true },
)

const aberto = computed({
  get: () => !!estado.value.valor,
  set: (v: boolean) => {
    if (!v) concluir()
  },
})
const guardado = computed({
  get: () => estado.value.guardado,
  set: (v: boolean) => (estado.value = confirmarGuardado(estado.value, v)),
})

function concluir() {
  if (!podeFecharSegredo(estado.value)) return
  estado.value = fecharSegredo(estado.value)
  emit('fechado')
}
</script>

<template>
  <Modal v-model:aberto="aberto" :titulo="titulo" :descricao="descricao" :bloqueado="!guardado" papel="alertdialog">
    <div class="flex flex-col gap-4">
      <Alerta tom="atencao" titulo="Guarde agora: ela não aparece de novo">
        Por segurança, o Toqqi não mostra este valor outra vez. Copie e cole em um lugar seguro, como o sistema da sua empresa ou um gerenciador de senhas.
      </Alerta>
      <div class="flex flex-col gap-1.5">
        <label for="segredo-gerado" class="flex items-center gap-1.5 text-sm font-semibold text-texto">
          <KeyRound class="size-4 text-texto-fraco" aria-hidden="true" /> {{ rotuloCampo }}
        </label>
        <input
          id="segredo-gerado"
          :value="estado.valor ?? ''"
          readonly
          spellcheck="false"
          autocomplete="off"
          class="h-11 w-full rounded-xl border border-borda-forte bg-superficie-2 px-3.5 font-mono text-sm text-texto"
          @focus="($event.target as HTMLInputElement).select()"
        />
      </div>
      <div>
        <BotaoCopiar :texto="estado.valor ?? ''" :rotulo="`Copiar ${rotuloCampo.toLowerCase()}`" variante="primario" />
      </div>
      <CaixaSelecao v-model="guardado" rotulo="Já copiei e guardei em um lugar seguro" />
    </div>
    <template #rodape>
      <Botao :desabilitado="!guardado" @click="concluir">Concluir</Botao>
    </template>
  </Modal>
</template>
