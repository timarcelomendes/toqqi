<script setup lang="ts">
// O botão oficial "Entrar com o Google" (Google Identity Services) e, embaixo, o "ou" para o formulário de e-mail
// (docs/api-login-google.md). Só aparece quando a API tem o ID do cliente do Google; se o script do Google não carrega
// (bloqueador, sem internet), some e a entrada com e-mail e senha segue sozinha. O botão é desenhado pelo Google (num
// iframe dele): o tema acompanha o claro e o escuro do Toqqi.
import { nextTick, onMounted, ref, watch } from 'vue'
import { carregarGoogle, idClienteGoogle, type GoogleId } from '@/composables/google'
import { useTema } from '@/composables/tema'

const props = defineProps<{
  /** O texto do botão, escrito pelo Google: "Fazer login com o Google" ou "Continuar com o Google". */
  texto: 'signin_with' | 'continue_with'
  /** O texto entre o botão e o formulário ("ou entre com seu e-mail"). */
  divisor: string
  /** A API está conferindo o token: o botão fica apagado e aparece "Entrando com o Google…". */
  ocupado?: boolean
}>()
const emit = defineEmits<{ credencial: [string] }>()

const alvo = ref<HTMLElement | null>(null)
/** 'nada': sem ID do cliente (ou o script falhou); 'carregando': há ID, esperando o script; 'pronto': botão desenhado. */
const estado = ref<'nada' | 'carregando' | 'pronto'>('nada')
const { tema } = useTema()
let gid: GoogleId | null = null

function desenhar() {
  if (!gid || !alvo.value) return
  const largura = alvo.value.clientWidth || 400
  gid.renderButton(alvo.value, {
    type: 'standard',
    theme: tema.value === 'escuro' ? 'filled_black' : 'outline',
    size: 'large',
    text: props.texto,
    shape: 'rectangular',
    logo_alignment: 'center',
    width: Math.round(Math.max(200, Math.min(400, largura))),
    locale: 'pt-BR',
  })
}

onMounted(async () => {
  const cid = await idClienteGoogle()
  if (!cid) return
  estado.value = 'carregando'
  gid = await carregarGoogle()
  if (!gid) {
    estado.value = 'nada'
    return
  }
  gid.initialize({
    client_id: cid,
    callback: (r) => {
      if (r?.credential) emit('credencial', r.credential)
    },
    ux_mode: 'popup',
    auto_select: false,
    context: props.texto === 'signin_with' ? 'signin' : 'signup',
    itp_support: true,
  })
  estado.value = 'pronto'
  await nextTick()
  desenhar()
})

watch(tema, () => desenhar())
</script>

<template>
  <div v-if="estado !== 'nada'" data-entrar-google :data-estado="estado">
    <div class="flex min-h-11 justify-center">
      <div ref="alvo" class="w-full max-w-[400px] transition-opacity" :class="ocupado ? 'pointer-events-none opacity-50' : ''" />
    </div>
    <p v-if="ocupado" class="mt-2 text-center text-sm text-texto-suave" role="status" data-entrando-google>Entrando com o Google…</p>
    <div class="my-6 flex items-center gap-3 text-sm text-texto-fraco">
      <span class="h-px flex-1 bg-borda" aria-hidden="true" />
      {{ divisor }}
      <span class="h-px flex-1 bg-borda" aria-hidden="true" />
    </div>
  </div>
</template>
