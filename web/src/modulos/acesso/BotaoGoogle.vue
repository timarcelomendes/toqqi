<script setup lang="ts">
// "Continuar com o Google" e, embaixo, o "ou" para o formulário de e-mail (docs/api-login-google.md).
// Desde 13/10/2026 (Marcelo: "melhore o botão entrar com google") o botão é do Toqqi: a mesma altura, os mesmos cantos
// e a mesma letra do "Entrar", no estilo secundário, claro ou escuro como o resto da tela. O botão oficial (num iframe
// do Google) ficava mais baixo, de cantos retos, com outra letra, e trocava sozinho para "Fazer login como Fulano".
// Seguem as regras de marca do Google: o "G" original (a imagem servida pelo próprio Google) e o texto oficial
// "Continuar com o Google", que vale para quem já tem conta e para quem vai criar.
// Ao clicar, a janela do Google (modelo de token do Google Identity Services) devolve um token de acesso, que vai para a
// tela (evento `token`) e dali para a API, onde o próprio Google confirma de quem é. Janela fechada ou recusada: nada
// muda; janela bloqueada pelo navegador: o aviso embaixo do botão.
// Só aparece quando a API tem o ID do cliente do Google; se o script do Google não carrega (bloqueador, sem internet),
// some, e a entrada com e-mail e senha segue sozinha.
import { onMounted, ref } from 'vue'
import Botao from '@/components/ui/Botao.vue'
import { ESCOPOS_GOOGLE, URL_LOGO_GOOGLE, carregarGoogle, idClienteGoogle, type ClienteTokenGoogle } from '@/composables/google'

const props = defineProps<{
  /** O texto entre o botão e o formulário ("ou entre com seu e-mail"). */
  divisor: string
  /** A API está conferindo o token: o botão fica apagado, com "Entrando com o Google…". */
  ocupado?: boolean
}>()
const emit = defineEmits<{ token: [string] }>()

const MSG_BLOQUEADA = 'O navegador bloqueou a janela do Google. Permita janelas pop-up neste site e tente de novo.'
const MSG_FALHOU = 'Não deu para entrar com o Google agora. Tente de novo ou entre com e-mail e senha.'

/** 'nada': sem ID do cliente (ou o script falhou); 'carregando': há ID, esperando o script; 'pronto': abre a janela. */
const estado = ref<'nada' | 'carregando' | 'pronto'>('nada')
const erro = ref<string | null>(null)
let cliente: ClienteTokenGoogle | null = null

onMounted(async () => {
  const cid = await idClienteGoogle()
  if (!cid) return
  estado.value = 'carregando'
  const oauth2 = await carregarGoogle()
  if (!oauth2) {
    estado.value = 'nada'
    return
  }
  cliente = oauth2.initTokenClient({
    client_id: cid,
    scope: ESCOPOS_GOOGLE,
    prompt: 'select_account',
    callback: (r) => {
      if (r?.access_token) emit('token', r.access_token)
      else if (r?.error && r.error !== 'access_denied') erro.value = MSG_FALHOU // "access_denied": a pessoa recusou
    },
    error_callback: (e) => {
      if (e?.type === 'popup_failed_to_open') erro.value = MSG_BLOQUEADA
      else if (e?.type !== 'popup_closed') erro.value = MSG_FALHOU // fechou a janela: desistiu, sem aviso
    },
  })
  estado.value = 'pronto'
})

/** Abre a janela do Google. Direto no clique: depois de um `await`, o navegador bloquearia a janela. */
function abrir() {
  if (props.ocupado || !cliente) return
  erro.value = null
  cliente.requestAccessToken()
}
</script>

<template>
  <div v-if="estado !== 'nada'" data-entrar-google :data-estado="estado">
    <Botao variante="secundario" tamanho="lg" bloco focavel :carregando="ocupado" data-botao-google @click="abrir">
      <span class="flex items-center gap-3">
        <img v-if="!ocupado" :src="URL_LOGO_GOOGLE" alt="" width="20" height="20" class="size-5 shrink-0" referrerpolicy="no-referrer" decoding="async" />
        {{ ocupado ? 'Entrando com o Google…' : 'Continuar com o Google' }}
      </span>
    </Botao>
    <p v-if="erro" class="mt-2 text-sm text-erro" role="alert" data-erro-google>{{ erro }}</p>
    <div class="my-6 flex items-center gap-3 text-sm text-texto-fraco">
      <span class="h-px flex-1 bg-borda" aria-hidden="true" />
      {{ divisor }}
      <span class="h-px flex-1 bg-borda" aria-hidden="true" />
    </div>
  </div>
</template>
