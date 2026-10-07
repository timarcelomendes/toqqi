<script setup lang="ts">
// Página pública /sair/:token: a pessoa deixa de receber pesquisas da empresa (ou volta a receber).
// Leve como a pesquisa: sem Pinia, router nem ícones externos.
import { nextTick, onMounted, ref, useId } from 'vue'
import { ApiError } from '@/api/erros'
import { publicoApi, type DescadastroPublico } from '@/api/publico'
import { LIMITE_MOTIVO, MOTIVOS_RAPIDOS, montarMotivo, tokenDoCaminho, type MotivoRapido } from './descadastro'

type Estado = 'carregando' | 'pronto' | 'saiu' | 'voltou' | 'invalido' | 'erro'

const props = defineProps<{ caminho?: string }>()
const token = tokenDoCaminho(props.caminho ?? window.location.pathname)
const id = useId()

const estado = ref<Estado>('carregando')
const dados = ref<DescadastroPublico | null>(null)
const motivo = ref<MotivoRapido | null>(null)
const texto = ref('')
const enviando = ref(false)
const erroAcao = ref('')
const mensagemErro = ref('')
const titulo = ref<HTMLElement | null>(null)

function eInvalido(e: unknown) {
  return e instanceof ApiError && (e.status === 404 || e.codigo === 'link_invalido')
}

function textoDoErro(e: unknown, padrao: string) {
  return e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.mensagem : padrao
}

async function mudar(novo: Estado) {
  estado.value = novo
  await nextTick()
  titulo.value?.focus()
}

async function carregar() {
  if (!token) return mudar('invalido')
  estado.value = 'carregando'
  try {
    dados.value = await publicoApi.descadastro(token)
    await mudar(dados.value.descadastrado ? 'saiu' : 'pronto')
  } catch (e) {
    if (eInvalido(e)) return mudar('invalido')
    mensagemErro.value = textoDoErro(e, 'Não conseguimos abrir esta página. Confira sua internet e tente de novo.')
    await mudar('erro')
  }
}

async function sair() {
  if (!token || enviando.value) return
  enviando.value = true
  erroAcao.value = ''
  try {
    const m = montarMotivo(motivo.value, texto.value)
    await publicoApi.alterarDescadastro(token, m ? { motivo: m } : {})
    await mudar('saiu')
  } catch (e) {
    if (eInvalido(e)) return mudar('invalido')
    erroAcao.value = textoDoErro(e, 'Não deu certo agora. Confira sua internet e tente de novo.')
  } finally {
    enviando.value = false
  }
}

async function voltar() {
  if (!token || enviando.value) return
  enviando.value = true
  erroAcao.value = ''
  try {
    await publicoApi.alterarDescadastro(token, { voltar: true })
    motivo.value = null
    texto.value = ''
    await mudar('voltou')
  } catch (e) {
    if (eInvalido(e)) return mudar('invalido')
    erroAcao.value = textoDoErro(e, 'Não deu certo agora. Confira sua internet e tente de novo.')
  } finally {
    enviando.value = false
  }
}

document.title = 'Não receber mais pesquisas'
onMounted(carregar)

const botao =
  'inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl px-6 font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:cursor-not-allowed disabled:opacity-60'
</script>

<template>
  <main class="flex min-h-dvh flex-col" aria-labelledby="titulo-sair">
    <div v-if="estado === 'carregando'" class="flex flex-1 items-center justify-center py-24" role="status">
      <svg viewBox="0 0 24 24" class="size-8 animate-spin text-slate-400" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
      <span class="sr-only">Carregando…</span>
    </div>

    <section v-else class="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-5 py-10 sm:py-16">
      <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <!-- Pedir para sair -->
        <form v-if="estado === 'pronto' && dados" class="flex flex-col gap-5" novalidate @submit.prevent="sair">
          <div>
            <h1 id="titulo-sair" ref="titulo" tabindex="-1" class="text-xl font-extrabold text-slate-900 focus:outline-none">Não quer mais receber pesquisas?</h1>
            <p class="mt-2 text-slate-600">
              O e-mail <strong class="break-all text-slate-900" data-teste="email">{{ dados.email_mascarado }}</strong>
              deixa de receber pesquisas de <strong class="text-slate-900">{{ dados.empresa }}</strong>.
            </p>
          </div>

          <fieldset>
            <legend class="mb-2 text-sm font-semibold text-slate-800">Se quiser, conte o motivo</legend>
            <div class="flex flex-col gap-2">
              <label
                v-for="m in MOTIVOS_RAPIDOS"
                :key="m"
                class="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-4 py-2 text-[0.95rem] transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-slate-900"
                :class="motivo === m ? 'border-slate-900 bg-slate-50 font-semibold text-slate-900' : 'border-slate-300 text-slate-700 hover:border-slate-400'"
              >
                <input v-model="motivo" type="radio" :name="`motivo-${id}`" :value="m" class="size-4 accent-slate-900" />
                {{ m }}
              </label>
            </div>
          </fieldset>

          <div class="flex flex-col gap-1.5">
            <label :for="`texto-${id}`" class="text-sm font-semibold text-slate-800">Quer contar mais? <span class="font-normal text-slate-500">(opcional)</span></label>
            <textarea
              :id="`texto-${id}`"
              v-model="texto"
              rows="3"
              :maxlength="LIMITE_MOTIVO"
              :aria-describedby="`contagem-${id}`"
              class="w-full resize-y rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-[0.95rem] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-3 focus:ring-slate-900/15"
            />
            <p :id="`contagem-${id}`" class="text-right text-xs text-slate-500">{{ texto.length }}/{{ LIMITE_MOTIVO }}</p>
          </div>

          <p v-if="erroAcao" role="alert" class="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{{ erroAcao }}</p>

          <button type="submit" :class="[botao, 'bg-slate-900 text-white hover:bg-slate-700']" :disabled="enviando" :aria-busy="enviando || undefined">
            <svg v-if="enviando" viewBox="0 0 24 24" class="size-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
            Não quero mais receber
          </button>
        </form>

        <!-- Saiu (ou já tinha saído) -->
        <div v-else-if="estado === 'saiu'" class="flex flex-col items-center gap-4 text-center" data-estado="saiu">
          <span class="flex size-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          </span>
          <div>
            <h1 id="titulo-sair" ref="titulo" tabindex="-1" class="text-xl font-extrabold text-slate-900 focus:outline-none">Pronto, você saiu da lista</h1>
            <p class="mt-2 text-slate-600">
              <template v-if="dados">{{ dados.empresa }} não vai mais enviar pesquisas para <span class="break-all">{{ dados.email_mascarado }}</span>.</template>
              <template v-else>Você não vai mais receber pesquisas desta empresa.</template>
            </p>
          </div>
          <p v-if="erroAcao" role="alert" class="w-full rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{{ erroAcao }}</p>
          <button type="button" :class="[botao, 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50']" :disabled="enviando" :aria-busy="enviando || undefined" @click="voltar">
            Mudei de ideia, quero voltar a receber
          </button>
        </div>

        <!-- Voltou -->
        <div v-else-if="estado === 'voltou'" class="flex flex-col items-center gap-4 text-center" data-estado="voltou">
          <span class="flex size-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" /></svg>
          </span>
          <div>
            <h1 id="titulo-sair" ref="titulo" tabindex="-1" class="text-xl font-extrabold text-slate-900 focus:outline-none">Que bom ter você de volta!</h1>
            <p class="mt-2 text-slate-600">Você voltará a receber as pesquisas{{ dados ? ` de ${dados.empresa}` : '' }}. Obrigado por ajudar a melhorar.</p>
          </div>
          <button type="button" class="text-sm font-semibold text-slate-600 underline underline-offset-4 hover:text-slate-900" @click="mudar('pronto')">
            Não, quero sair da lista
          </button>
        </div>

        <!-- Link inválido -->
        <div v-else-if="estado === 'invalido'" class="flex flex-col items-center gap-3 text-center" data-estado="invalido">
          <span class="flex size-14 items-center justify-center rounded-full bg-slate-100 text-slate-500" aria-hidden="true">
            <svg viewBox="0 0 24 24" class="size-8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9.5" /><path d="M12 7.5v5.5M12 16.5v.3" /></svg>
          </span>
          <h1 id="titulo-sair" ref="titulo" tabindex="-1" class="text-xl font-extrabold text-slate-900 focus:outline-none">Este link não está valendo</h1>
          <p class="text-slate-600">
            O endereço pode ter vindo incompleto. Abra de novo o link "Não quero mais receber pesquisas" direto do e-mail que você recebeu ou
            <a href="/sair" class="font-semibold text-slate-900 underline underline-offset-4" data-pedir-link>peça um link novo</a>.
          </p>
        </div>

        <!-- Erro de conexão -->
        <div v-else class="flex flex-col items-center gap-4 text-center" data-estado="erro">
          <h1 id="titulo-sair" ref="titulo" tabindex="-1" class="text-xl font-extrabold text-slate-900 focus:outline-none">Não deu para abrir esta página</h1>
          <p class="text-slate-600">{{ mensagemErro }}</p>
          <button type="button" :class="[botao, 'bg-slate-900 text-white hover:bg-slate-700']" @click="carregar">Tentar de novo</button>
        </div>
      </div>
    </section>

    <footer class="pb-6 text-center text-xs text-slate-400">
      Pesquisas enviadas com <a href="https://toqqi.com" class="font-semibold text-slate-500 hover:text-slate-700" target="_blank" rel="noopener">toqqi</a>
    </footer>
  </main>
</template>
