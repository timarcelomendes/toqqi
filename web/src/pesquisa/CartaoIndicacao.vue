<script setup lang="ts">
// Etapa 5c: convite para indicar outra empresa, na tela final da pesquisa (promotor, no convite individual).
// O mesmo cartão aparece na pré-visualização do editor e na prévia de Configurações › Crescimento: sem `enviar`, é só
// exemplo (o envio fica desligado). Tudo é texto: nada de HTML vindo dos textos do convite nem do que a pessoa digita.
// Como a página pública, não usa Pinia, router nem ícones externos (SVG inline).
import { computed, nextTick, reactive, ref, useId } from 'vue'
import { formatarTelefone } from '@/utils/validacao'
import { variaveisDaCor } from './cor'
import {
  LIMITE_EMPRESA_INDICACAO,
  LIMITE_NOME_INDICACAO,
  LIMITE_OBSERVACAO_INDICACAO,
  MAXIMO_INDICACOES,
  MENSAGEM_OBRIGADO_INDICACAO,
  camposDoServidor,
  camposIndicacaoVazios,
  montarIndicacao,
  validarIndicacao,
  type CamposIndicacao,
  type ErroIndicacao,
} from './indicacao'
import type { ConviteIndicacao, DadosIndicacao } from './tipos'

const props = withDefaults(
  defineProps<{
    convite: ConviteIndicacao
    /** Nome da empresa (a conta), na confirmação. */
    empresa?: string
    /** Envia a indicação e devolve a mensagem de obrigado. Sem ela, o cartão é só um exemplo. */
    enviar?: (dados: DadosIndicacao) => Promise<string | void>
    /** Fora da pesquisa (prévias), a cor dos botões; dentro dela, vale a cor do formulário. */
    cor?: string | null
  }>(),
  { empresa: '', enviar: undefined, cor: null },
)

const id = `ind-${useId()}`
const campos = reactive<CamposIndicacao>(camposIndicacaoVazios())
const podeIdentificar = ref(true)
const confirmo = ref(false)
const erros = reactive<Record<string, string>>({})
const erroGeral = ref<string | null>(null)
const enviando = ref(false)
const enviadas = ref(0)
/** 'limite': a 4ª indicação (409 limite_indicacoes); 'indisponivel': a pesquisa não aceita mais (409 indicacao_indisponivel). */
const etapa = ref<'formulario' | 'obrigado' | 'limite' | 'indisponivel'>('formulario')
const mensagem = ref('')
const raiz = ref<HTMLElement | null>(null)
const caixaFinal = ref<HTMLElement | null>(null)

const exemplo = computed(() => !props.enviar)
const estilo = computed(() => (props.cor ? variaveisDaCor(props.cor) : undefined))
const podeOutra = computed(() => etapa.value === 'obrigado' && enviadas.value < MAXIMO_INDICACOES)
const textoConfirmo = computed(() => {
  const e = props.empresa.trim()
  return e ? `Confirmo que essa pessoa aceita receber um contato de ${e}.` : 'Confirmo que essa pessoa aceita receber um contato.'
})

const ORDEM = ['nome', 'empresa', 'telefone', 'email', 'observacao', 'confirmo'] as const

function descritoPor(campo: string, extra?: string): string | undefined {
  return [erros[campo] ? `${id}-${campo}-erro` : '', extra ?? ''].filter(Boolean).join(' ') || undefined
}

function limparErros() {
  for (const k of Object.keys(erros)) delete erros[k]
  erroGeral.value = null
}

async function focarPrimeiroErro() {
  await nextTick()
  const campo = ORDEM.find((c) => erros[c])
  if (campo) raiz.value?.querySelector<HTMLElement>(`[data-campo="${campo}"]`)?.focus()
}

function aoDigitarTelefone(e: Event) {
  const el = e.target as HTMLInputElement
  const formatado = formatarTelefone(el.value)
  if (el.value !== formatado) {
    const doFim = el.value.length - (el.selectionEnd ?? el.value.length)
    el.value = formatado
    const pos = Math.max(0, formatado.length - doFim)
    try {
      if (document.activeElement === el) el.setSelectionRange(pos, pos)
    } catch {
      /* campo sem cursor */
    }
  }
  campos.telefone = formatado
  if (erros.telefone) delete erros.telefone
}

function aoMudar(campo: keyof CamposIndicacao | 'confirmo') {
  if (erros[campo]) delete erros[campo]
  // "Telefone ou e-mail": preencher um dos dois tira o aviso do outro.
  if ((campo === 'email' || campo === 'telefone') && erros.telefone?.includes('pelo menos um')) delete erros.telefone
}

async function enviarIndicacao() {
  if (!props.enviar || enviando.value) return
  limparErros()
  const locais = validarIndicacao(campos, { confirmo: confirmo.value })
  if (Object.keys(locais).length) {
    Object.assign(erros, locais)
    focarPrimeiroErro()
    return
  }
  enviando.value = true
  try {
    const r = await props.enviar(montarIndicacao(campos, podeIdentificar.value, true))
    enviadas.value++
    mensagem.value = (typeof r === 'string' && r.trim()) || MENSAGEM_OBRIGADO_INDICACAO
    etapa.value = 'obrigado'
    await nextTick()
    caixaFinal.value?.focus()
  } catch (err) {
    const x = (err ?? {}) as ErroIndicacao
    // Os dois 409 encerram o cartão (tentar de novo não adianta): a mensagem da API, sem o formulário.
    if (x.codigo === 'limite_indicacoes' || x.codigo === 'indicacao_indisponivel') {
      const limite = x.codigo === 'limite_indicacoes'
      if (limite) enviadas.value = MAXIMO_INDICACOES
      mensagem.value = x.mensagem || (limite ? 'Você já fez 3 indicações. Obrigado!' : 'Esta pesquisa não aceita mais indicações.')
      etapa.value = limite ? 'limite' : 'indisponivel'
      await nextTick()
      caixaFinal.value?.focus()
      return
    }
    const porCampo = camposDoServidor(x.campos)
    if (Object.keys(porCampo).length) {
      Object.assign(erros, porCampo)
      focarPrimeiroErro()
    } else {
      erroGeral.value = x.mensagem || 'Não conseguimos enviar agora. Confira sua internet e tente de novo.'
    }
  } finally {
    enviando.value = false
  }
}

async function indicarOutra() {
  Object.assign(campos, camposIndicacaoVazios())
  podeIdentificar.value = true
  confirmo.value = false
  limparErros()
  etapa.value = 'formulario'
  await nextTick()
  raiz.value?.querySelector<HTMLElement>('[data-campo="nome"]')?.focus()
}

// Desligados só no exemplo: continuam com cara de campo (é uma prévia de como o cliente vê).
const classeCampo =
  'w-full rounded-xl border-2 bg-white px-4 text-base text-slate-900 placeholder:text-slate-400 transition-colors focus:border-[var(--cor)] focus:outline-none disabled:cursor-default'
const borda = (campo: string) => (erros[campo] ? 'border-red-500' : 'border-slate-200')
</script>

<template>
  <section
    ref="raiz"
    class="@container w-full rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left [color-scheme:light] sm:p-5"
    :style="estilo"
    :aria-labelledby="`${id}-titulo`"
    data-cartao-indicacao
  >
    <div class="flex items-start gap-3">
      <span class="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-full bg-[var(--cor-suave)] text-[var(--cor)]" aria-hidden="true">
        <svg viewBox="0 0 24 24" class="size-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M19 8v6M22 11h-6" />
        </svg>
      </span>
      <div class="min-w-0 flex-1">
        <h2 :id="`${id}-titulo`" class="break-words text-lg font-extrabold leading-snug text-slate-900">{{ convite.titulo }}</h2>
        <p v-if="convite.texto" class="mt-1 whitespace-pre-line break-words text-[0.95rem] text-slate-600">{{ convite.texto }}</p>
      </div>
    </div>
    <p v-if="convite.recompensa" class="mt-3 flex items-start gap-2 rounded-xl bg-white px-3 py-2.5 text-sm font-semibold text-slate-800 ring-1 ring-slate-200" data-recompensa>
      <svg viewBox="0 0 24 24" class="mt-px size-4 shrink-0 text-[var(--cor)]" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 7v14M20 11v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8M7.5 7a1 1 0 0 1 0-5A4.8 8 0 0 1 12 7a4.8 8 0 0 1 4.5-5 1 1 0 0 1 0 5" /><rect x="3" y="7" width="18" height="4" rx="1" />
      </svg>
      <span class="min-w-0 whitespace-pre-line break-words">{{ convite.recompensa }}</span>
    </p>

    <!-- Depois de enviar -->
    <div v-if="etapa !== 'formulario'" ref="caixaFinal" tabindex="-1" class="mt-4 flex flex-col items-start gap-3 focus:outline-none" data-indicacao-final>
      <p role="status" class="flex items-center gap-2 text-base font-bold text-slate-900">
        <!-- Indisponível não é um "deu certo": um "i" no lugar do visto -->
        <svg v-if="etapa === 'indisponivel'" viewBox="0 0 24 24" class="size-5 shrink-0 text-slate-500" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" />
        </svg>
        <svg v-else viewBox="0 0 24 24" class="size-5 shrink-0 text-emerald-600" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
        {{ mensagem }}
      </p>
      <button
        v-if="podeOutra"
        type="button"
        class="inline-flex h-11 items-center justify-center rounded-xl border-2 border-[var(--cor)] bg-white px-4 text-sm font-bold text-slate-900 transition hover:bg-[var(--cor-suave)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
        @click="indicarOutra"
      >
        Indicar outra pessoa
      </button>
      <p v-else-if="etapa === 'obrigado'" class="text-sm text-slate-500">Você fez {{ MAXIMO_INDICACOES }} indicações, o máximo por pesquisa.</p>
    </div>

    <!-- No exemplo, um bloco comum (a prévia de Configurações fica dentro de outro formulário) e campos desligados -->
    <component :is="exemplo ? 'div' : 'form'" v-else class="mt-4 flex flex-col gap-4" v-bind="exemplo ? {} : { novalidate: true }" @submit.prevent="enviarIndicacao">
      <div class="flex flex-col gap-1.5">
        <label :for="`${id}-nome`" class="text-sm font-semibold text-slate-800">Nome de quem você indica <span class="text-red-600" aria-hidden="true">*</span></label>
        <input
          :id="`${id}-nome`"
          v-model="campos.nome"
          data-campo="nome"
          type="text"
          autocomplete="off"
          required
          :maxlength="LIMITE_NOME_INDICACAO"
          :disabled="exemplo"
          :aria-invalid="erros.nome ? 'true' : undefined"
          :aria-describedby="descritoPor('nome')"
          :class="[classeCampo, 'h-12', borda('nome')]"
          @input="aoMudar('nome')"
        />
        <p v-if="erros.nome" :id="`${id}-nome-erro`" class="text-sm font-semibold text-red-700">{{ erros.nome }}</p>
      </div>

      <div class="flex flex-col gap-1.5">
        <label :for="`${id}-empresa`" class="text-sm font-semibold text-slate-800">Empresa <span class="font-normal text-slate-500">(opcional)</span></label>
        <input
          :id="`${id}-empresa`"
          v-model="campos.empresa"
          data-campo="empresa"
          type="text"
          autocomplete="off"
          :maxlength="LIMITE_EMPRESA_INDICACAO"
          :disabled="exemplo"
          :aria-invalid="erros.empresa ? 'true' : undefined"
          :aria-describedby="descritoPor('empresa')"
          :class="[classeCampo, 'h-12', borda('empresa')]"
          @input="aoMudar('empresa')"
        />
        <p v-if="erros.empresa" :id="`${id}-empresa-erro`" class="text-sm font-semibold text-red-700">{{ erros.empresa }}</p>
      </div>

      <!-- Lado a lado só quando o cartão é largo (na prévia estreita de Configurações, um embaixo do outro) -->
      <div class="grid gap-4 @sm:grid-cols-2">
        <div class="flex min-w-0 flex-col gap-1.5">
          <label :for="`${id}-telefone`" class="text-sm font-semibold text-slate-800">WhatsApp ou telefone</label>
          <input
            :id="`${id}-telefone`"
            :value="campos.telefone"
            data-campo="telefone"
            type="tel"
            inputmode="tel"
            autocomplete="off"
            placeholder="(11) 91234-5678"
            :disabled="exemplo"
            :aria-invalid="erros.telefone ? 'true' : undefined"
            :aria-describedby="descritoPor('telefone', `${id}-um-dos-dois`)"
            :class="[classeCampo, 'h-12', borda('telefone')]"
            @input="aoDigitarTelefone"
          />
          <p v-if="erros.telefone" :id="`${id}-telefone-erro`" class="text-sm font-semibold text-red-700">{{ erros.telefone }}</p>
        </div>
        <div class="flex min-w-0 flex-col gap-1.5">
          <label :for="`${id}-email`" class="text-sm font-semibold text-slate-800">E-mail</label>
          <input
            :id="`${id}-email`"
            v-model="campos.email"
            data-campo="email"
            type="email"
            inputmode="email"
            autocomplete="off"
            placeholder="nome@empresa.com"
            :disabled="exemplo"
            :aria-invalid="erros.email ? 'true' : undefined"
            :aria-describedby="descritoPor('email', `${id}-um-dos-dois`)"
            :class="[classeCampo, 'h-12', borda('email')]"
            @input="aoMudar('email')"
          />
          <p v-if="erros.email" :id="`${id}-email-erro`" class="text-sm font-semibold text-red-700">{{ erros.email }}</p>
        </div>
      </div>
      <p :id="`${id}-um-dos-dois`" class="-mt-2 text-sm text-slate-500">Informe pelo menos um dos dois.</p>

      <div class="flex flex-col gap-1.5">
        <label :for="`${id}-observacao`" class="text-sm font-semibold text-slate-800">Quer contar algo sobre essa pessoa? <span class="font-normal text-slate-500">(opcional)</span></label>
        <textarea
          :id="`${id}-observacao`"
          v-model="campos.observacao"
          data-campo="observacao"
          rows="3"
          :maxlength="LIMITE_OBSERVACAO_INDICACAO"
          :disabled="exemplo"
          :aria-invalid="erros.observacao ? 'true' : undefined"
          :aria-describedby="descritoPor('observacao')"
          :class="[classeCampo, 'resize-y py-3', borda('observacao')]"
          placeholder="Ex.: é a compradora da loja do centro; prefere contato à tarde."
          @input="aoMudar('observacao')"
        />
        <p v-if="erros.observacao" :id="`${id}-observacao-erro`" class="text-sm font-semibold text-red-700">{{ erros.observacao }}</p>
      </div>

      <div class="flex flex-col gap-3">
        <label class="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
          <input v-model="podeIdentificar" type="checkbox" :disabled="exemplo" class="mt-0.5 size-5 shrink-0 cursor-pointer accent-[var(--cor)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900" />
          <span>Pode dizer que fui eu que indiquei</span>
        </label>
        <div class="flex flex-col gap-1">
          <label class="flex cursor-pointer items-start gap-3 text-sm text-slate-800">
            <input
              v-model="confirmo"
              data-campo="confirmo"
              type="checkbox"
              required
              :disabled="exemplo"
              :aria-invalid="erros.confirmo ? 'true' : undefined"
              :aria-describedby="descritoPor('confirmo')"
              class="mt-0.5 size-5 shrink-0 cursor-pointer accent-[var(--cor)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
              @change="aoMudar('confirmo')"
            />
            <span>{{ textoConfirmo }} <span class="text-red-600" aria-hidden="true">*</span></span>
          </label>
          <p v-if="erros.confirmo" :id="`${id}-confirmo-erro`" class="pl-8 text-sm font-semibold text-red-700">{{ erros.confirmo }}</p>
        </div>
      </div>

      <div v-if="erroGeral" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{{ erroGeral }}</div>

      <div class="flex flex-col items-stretch gap-2 @sm:flex-row @sm:items-center">
        <button
          type="submit"
          class="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-[var(--cor)] px-6 text-base font-bold text-[var(--cor-texto)] shadow-sm transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="exemplo || enviando"
          :aria-busy="enviando || undefined"
          :aria-describedby="exemplo ? `${id}-exemplo` : undefined"
        >
          <svg v-if="enviando" viewBox="0 0 24 24" class="size-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
          Enviar indicação
        </button>
        <p v-if="exemplo" :id="`${id}-exemplo`" class="text-xs text-slate-500" data-aviso-exemplo>Exemplo: aqui a indicação não é enviada.</p>
      </div>
    </component>
  </section>
</template>
