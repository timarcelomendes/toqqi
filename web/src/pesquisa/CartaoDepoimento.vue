<script setup lang="ts">
// Melhoria 5, prova social: na tela final da pesquisa, para quem deu nota alta, "Podemos publicar seu comentário?"
// (quando a conta ligou os depoimentos e a pessoa escreveu um comentário) e o botão para avaliar a empresa no Google
// (ou onde a conta configurou). Como a página pública, sem Pinia, router nem ícones externos.
import { ref, useId } from 'vue'
import type { TelaFinalDepoimento } from './tipos'

const props = defineProps<{
  dados: TelaFinalDepoimento
  /** Autoriza e devolve a mensagem de obrigado. Sem ela (prévia), o botão não faz nada. */
  autorizar?: () => Promise<string | void>
}>()

const id = `dep-${useId()}`
const etapa = ref<'pergunta' | 'enviando' | 'feito' | 'erro'>('pergunta')
const mensagem = ref('')

async function permitir() {
  if (!props.autorizar || etapa.value === 'enviando') return
  etapa.value = 'enviando'
  try {
    mensagem.value = (await props.autorizar()) || 'Obrigado! Seu comentário pode ajudar outras empresas a nos conhecer.'
    etapa.value = 'feito'
  } catch {
    mensagem.value = 'Não conseguimos registrar agora. Tente de novo em instantes.'
    etapa.value = 'erro'
  }
}
</script>

<template>
  <section class="w-full rounded-2xl border border-slate-200 bg-slate-50 p-4 text-left [color-scheme:light] sm:p-5" :aria-labelledby="`${id}-t`" data-cartao-depoimento>
    <template v-if="dados.pedir">
      <h2 :id="`${id}-t`" class="text-lg font-extrabold leading-snug text-slate-900">Podemos publicar seu comentário?</h2>
      <p class="mt-1 text-[0.95rem] text-slate-600">Ele aparece como depoimento, com seu primeiro nome e o nome da sua empresa. Nada mais é mostrado.</p>
      <p v-if="etapa === 'feito' || etapa === 'erro'" role="status" class="mt-3 text-base font-bold" :class="etapa === 'feito' ? 'text-emerald-700' : 'text-slate-700'" data-depoimento-final>
        {{ mensagem }}
      </p>
      <div v-if="etapa !== 'feito'" class="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          class="inline-flex h-11 items-center justify-center rounded-xl bg-[var(--cor)] px-5 text-sm font-bold text-[var(--cor-texto)] shadow-sm transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 disabled:opacity-60"
          :disabled="etapa === 'enviando'"
          data-autorizar-depoimento
          @click="permitir"
        >
          {{ etapa === 'enviando' ? 'Enviando…' : 'Pode publicar' }}
        </button>
      </div>
    </template>
    <h2 v-else :id="`${id}-t`" class="text-lg font-extrabold leading-snug text-slate-900">Que tal contar para mais gente?</h2>

    <div v-if="dados.avaliar_url" :class="dados.pedir ? 'mt-4 border-t border-slate-200 pt-4' : 'mt-3'">
      <p v-if="dados.pedir" class="mb-2 text-[0.95rem] text-slate-600">Uma avaliação pública também ajuda muito:</p>
      <a
        :href="dados.avaliar_url"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex h-11 items-center justify-center gap-2 rounded-xl border-2 border-[var(--cor)] bg-white px-4 text-sm font-bold text-slate-900 transition hover:bg-[var(--cor-suave)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
        data-avaliar
      >
        <svg viewBox="0 0 24 24" class="size-4 text-[var(--cor)]" fill="currentColor" aria-hidden="true">
          <path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z" />
        </svg>
        {{ dados.avaliar_rotulo }}
        <span class="sr-only">(abre em outra aba)</span>
      </a>
    </div>
  </section>
</template>
