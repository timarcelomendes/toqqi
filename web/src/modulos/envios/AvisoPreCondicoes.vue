<script setup lang="ts">
// O que falta para as pesquisas por e-mail saírem (GET /envios/pre-condicoes), com o atalho para resolver.
import { CheckCircle2, ChevronRight, CircleAlert } from 'lucide-vue-next'
import type { PreCondicoes } from '@/api'

defineProps<{ dados: PreCondicoes }>()

const interna = (rota: string) => rota.startsWith('/')

/** Texto para os itens já resolvidos (a API só manda mensagem do que falta). */
const RESOLVIDOS: Record<string, string> = {
  assinatura: 'Assinatura em dia',
  provedor: 'Envio de e-mails configurado',
  formulario: 'Formulário da pesquisa escolhido',
  envios_ativos: 'Envios ligados',
}
const texto = (i: PreCondicoes['itens'][number]) => i.mensagem || (i.ok ? (RESOLVIDOS[i.chave] ?? 'Pronto') : 'Falta resolver este item.')
</script>

<template>
  <section
    v-if="!dados.pronto"
    class="rounded-2xl border border-atencao/30 bg-atencao-suave p-4 sm:p-5"
    role="status"
    aria-labelledby="titulo-pre-condicoes"
  >
    <h2 id="titulo-pre-condicoes" class="flex items-center gap-2 font-bold text-texto">
      <CircleAlert class="size-5 shrink-0 text-atencao" aria-hidden="true" />
      Falta pouco para as pesquisas por e-mail começarem a sair
    </h2>
    <p class="mt-1 text-sm text-texto-suave">
      Enquanto isso, você já pode mandar pelo WhatsApp. Resolva os itens abaixo para liberar o e-mail:
    </p>
    <ul class="mt-3 flex flex-col gap-2">
      <li v-for="item in dados.itens" :key="item.chave" class="flex flex-col gap-2 rounded-xl bg-superficie/70 px-3 py-2.5 text-sm sm:flex-row sm:items-center">
        <span class="flex flex-1 items-start gap-2">
          <CheckCircle2 v-if="item.ok" class="mt-0.5 size-4 shrink-0 text-sucesso" aria-hidden="true" />
          <CircleAlert v-else class="mt-0.5 size-4 shrink-0 text-atencao" aria-hidden="true" />
          <span :class="item.ok ? 'text-texto-fraco' : 'font-medium text-texto'">
            <span class="sr-only">{{ item.ok ? 'Resolvido: ' : 'Falta: ' }}</span>{{ texto(item) }}
          </span>
        </span>
        <template v-if="!item.ok && item.acao">
          <RouterLink
            v-if="interna(item.acao.rota)"
            :to="item.acao.rota"
            class="inline-flex items-center gap-1 self-start rounded-lg px-2 py-1 font-semibold text-marca-texto hover:bg-marca-suave sm:self-auto"
          >
            {{ item.acao.rotulo }} <ChevronRight class="size-4" aria-hidden="true" />
          </RouterLink>
        </template>
      </li>
    </ul>
  </section>
</template>
