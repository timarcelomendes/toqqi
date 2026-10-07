<script setup lang="ts">
// O número está "Pendente" no WhatsApp Manager: o Toqqi faz o registro na Cloud API com o token salvo e um PIN de 6
// dígitos que a pessoa digita ou gera aqui (vira a verificação em duas etapas do número; não fica guardado).
// docs/api-whatsapp-registro.md
import { computed, ref } from 'vue'
import { Dices, KeyRound } from 'lucide-vue-next'
import { mensagemDoErro, whatsappAutomaticoApi, type NumeroWhatsapp } from '@/api'
import { ApiError } from '@/api/erros'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import Campo from '@/components/ui/Campo.vue'
import { gerarPin, pinFraco, soPin } from './logica'

const props = defineProps<{ numero: NumeroWhatsapp }>()
const emit = defineEmits<{ registrado: [n: NumeroWhatsapp, mensagem: string] }>()

const pin = ref('')
const erroPin = ref<string | null>(null)
const erro = ref<string | null>(null)
const enviando = ref(false)
const campo = ref<InstanceType<typeof Campo> | null>(null)
const pinGerado = ref<string | null>(null)
/** O PIN do campo é o que o Toqqi acabou de gerar (mudou um número: passa a ser o digitado). */
const gerado = computed(() => pinGerado.value !== null && pin.value === pinGerado.value)
const fraco = computed(() => !gerado.value && pinFraco(pin.value))

function gerar() {
  pinGerado.value = gerarPin()
  pin.value = pinGerado.value
  erroPin.value = null
  erro.value = null
  campo.value?.focar()
}

async function registrar() {
  if (enviando.value) return
  erro.value = null
  erroPin.value = pin.value.length === 6 ? null : 'O PIN tem 6 números.'
  if (erroPin.value) {
    campo.value?.focar()
    return
  }
  enviando.value = true
  try {
    const r = await whatsappAutomaticoApi.registrarNumero(pin.value)
    pin.value = ''
    pinGerado.value = null
    emit('registrado', r.numero, r.mensagem)
  } catch (e) {
    if (e instanceof ApiError && e.campo('pin')) erroPin.value = e.campo('pin')!
    else erro.value = mensagemDoErro(e)
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <section class="cartao grid gap-6 border-atencao/40 p-5 sm:p-6 md:grid-cols-3" aria-labelledby="t-wa-registro" data-registro-numero>
    <div>
      <div class="mb-3 flex size-10 items-center justify-center rounded-xl bg-atencao-suave text-atencao"><KeyRound class="size-5" aria-hidden="true" /></div>
      <h2 id="t-wa-registro" class="text-base font-bold text-texto">Falta registrar o número na Meta</h2>
      <p class="mt-1 text-sm text-texto-suave">
        No WhatsApp Manager ele aparece como <strong class="text-texto">Pendente</strong>: a Meta só libera o envio depois deste registro. O Toqqi faz
        isso por você, com o token que já está salvo.
      </p>
    </div>
    <form class="flex flex-col gap-4 md:col-span-2" novalidate @submit.prevent="registrar">
      <Alerta v-if="props.numero.codigo_confirmado === false" tom="atencao" data-falta-codigo>
        A Meta ainda não vê o número como confirmado. Se o registro for recusado, confirme o número no WhatsApp Manager com o código que chega por
        SMS ou ligação e tente de novo.
      </Alerta>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <Campo
          ref="campo"
          v-model="pin"
          rotulo="PIN de 6 números"
          inputmode="numeric"
          autocomplete="off"
          placeholder="000000"
          :mascara="soPin"
          :erro="erroPin"
          class="sm:max-w-xs sm:flex-1"
          data-pin
        >
          <template #dica>
            <span v-if="gerado" class="flex flex-wrap items-center gap-x-2 gap-y-1" data-pin-gerado>
              PIN gerado: anote ou copie antes de registrar.
              <BotaoCopiar :texto="pin" rotulo="Copiar PIN" copiado="PIN copiado!" variante="fantasma" tamanho="sm" />
            </span>
            <span v-else-if="fraco" class="text-atencao" data-pin-fraco>PIN fácil de adivinhar. Se preferir, gere um.</span>
            <span v-else>Digite um PIN seu ou gere um.</span>
          </template>
        </Campo>
        <Botao variante="secundario" class="sm:mt-7" :desabilitado="enviando" data-gerar-pin @click="gerar">
          <Dices class="size-4" aria-hidden="true" /> Gerar PIN
        </Botao>
      </div>
      <div>
        <Botao tipo="submit" :carregando="enviando" class="w-full sm:w-auto">Registrar o número</Botao>
      </div>
      <div class="flex flex-col gap-1.5 text-sm text-texto-suave">
        <p>
          <strong class="text-texto">O PIN vira a verificação em duas etapas do número.</strong> Guarde junto com as suas senhas: a Meta pede de novo se
          um dia for preciso registrar o número outra vez. O Toqqi não guarda o PIN.
        </p>
        <p>Se o número já tinha verificação em duas etapas (por exemplo, porque era usado no app do WhatsApp), use o PIN dela.</p>
        <p class="text-texto-fraco">A Meta aceita até 10 tentativas a cada 3 dias. Depois disso, bloqueia o registro do número por 72 horas.</p>
      </div>
      <Alerta v-if="erro" tom="erro" data-erro-registro>{{ erro }}</Alerta>
    </form>
  </section>
</template>
