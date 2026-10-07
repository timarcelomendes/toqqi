<script setup lang="ts">
// Página pública /sair (sem token): a pessoa digita o e-mail e a Toqqi manda a ele um link para cada empresa que lhe
// envia pesquisas, para sair da lista ou voltar a receber (docs/api-voltar-a-receber.md). A resposta é sempre a
// mesma, ache ou não o e-mail. Leve como a pesquisa: sem Pinia, router nem ícones externos.
import { nextTick, ref, useId } from 'vue'
import { ApiError } from '@/api/erros'
import { publicoApi } from '@/api/publico'
import { conferirEmail } from './descadastro'

type Estado = 'pronto' | 'enviado'

const id = useId()
const estado = ref<Estado>('pronto')
const email = ref('')
const erro = ref('')
const mensagem = ref('')
const enviando = ref(false)
const titulo = ref<HTMLElement | null>(null)
const campo = ref<HTMLInputElement | null>(null)

async function mudar(novo: Estado) {
  estado.value = novo
  await nextTick()
  titulo.value?.focus()
}

function textoDoErro(e: unknown) {
  if (e instanceof ApiError && e.status !== 0 && e.status < 500) return e.campo('email') || e.mensagem
  return 'Não deu certo agora. Confira sua internet e tente de novo.'
}

async function pedir() {
  if (enviando.value) return
  erro.value = conferirEmail(email.value) ?? ''
  if (erro.value) {
    campo.value?.focus()
    return
  }
  enviando.value = true
  try {
    const r = await publicoApi.pedirLinkDescadastro(email.value.trim())
    mensagem.value = r.mensagem
    await mudar('enviado')
  } catch (e) {
    erro.value = textoDoErro(e)
    campo.value?.focus()
  } finally {
    enviando.value = false
  }
}

async function outroEmail() {
  email.value = ''
  erro.value = ''
  estado.value = 'pronto'
  await nextTick()
  campo.value?.focus()
}

document.title = 'Receber ou não as pesquisas'

const botao =
  'inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl px-6 font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:cursor-not-allowed disabled:opacity-60'
</script>

<template>
  <main class="flex min-h-dvh flex-col" aria-labelledby="titulo-pedir-link">
    <section class="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-5 py-10 sm:py-16">
      <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <!-- Pedir o link -->
        <form v-if="estado === 'pronto'" class="flex flex-col gap-5" novalidate data-estado="pronto" @submit.prevent="pedir">
          <div>
            <h1 id="titulo-pedir-link" ref="titulo" tabindex="-1" class="text-xl font-extrabold text-slate-900 focus:outline-none">Receber ou não as pesquisas</h1>
            <p class="mt-2 text-slate-600">
              Digite o seu e-mail. Mandamos para ele um link para cada empresa que envia pesquisas para você pelo Toqqi: por ele, você
              sai da lista ou volta a receber.
            </p>
          </div>

          <div class="flex flex-col gap-1.5">
            <label :for="`email-${id}`" class="text-sm font-semibold text-slate-800">Seu e-mail</label>
            <input
              :id="`email-${id}`"
              ref="campo"
              v-model="email"
              type="email"
              inputmode="email"
              autocomplete="email"
              maxlength="254"
              placeholder="nome@empresa.com.br"
              :aria-invalid="erro ? 'true' : undefined"
              :aria-describedby="erro ? `erro-${id}` : undefined"
              class="h-12 w-full rounded-xl border bg-white px-3.5 text-[0.95rem] text-slate-900 focus:outline-none focus:ring-3"
              :class="erro ? 'border-red-500 focus:border-red-600 focus:ring-red-600/15' : 'border-slate-300 focus:border-slate-900 focus:ring-slate-900/15'"
            />
            <p v-if="erro" :id="`erro-${id}`" role="alert" class="text-sm font-medium text-red-700" data-erro>{{ erro }}</p>
          </div>

          <button type="submit" :class="[botao, 'bg-slate-900 text-white hover:bg-slate-700']" :disabled="enviando" :aria-busy="enviando || undefined">
            <svg v-if="enviando" viewBox="0 0 24 24" class="size-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
            Enviar o link
          </button>

          <p class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600" data-dica-whatsapp>
            Recebe pelo WhatsApp? Na conversa com a empresa, responda <strong class="text-slate-900">SAIR</strong> para parar ou
            <strong class="text-slate-900">VOLTAR</strong> para voltar a receber.
          </p>
        </form>

        <!-- Pedido feito (a mesma tela, ache ou não o e-mail) -->
        <div v-else class="flex flex-col items-center gap-4 text-center" data-estado="enviado">
          <span class="flex size-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5" /><path d="M3.5 7l8.5 6 8.5-6" /></svg>
          </span>
          <div>
            <h1 id="titulo-pedir-link" ref="titulo" tabindex="-1" class="text-xl font-extrabold text-slate-900 focus:outline-none">Confira o seu e-mail</h1>
            <p class="mt-2 break-words text-slate-600" data-mensagem>{{ mensagem }}</p>
          </div>
          <button type="button" class="text-sm font-semibold text-slate-600 underline underline-offset-4 hover:text-slate-900" @click="outroEmail">
            Usar outro e-mail
          </button>
        </div>
      </div>
    </section>

    <footer class="pb-6 text-center text-xs text-slate-400">
      Pesquisas enviadas com <a href="https://toqqi.com" class="font-semibold text-slate-500 hover:text-slate-700" target="_blank" rel="noopener">toqqi</a>
    </footer>
  </main>
</template>
