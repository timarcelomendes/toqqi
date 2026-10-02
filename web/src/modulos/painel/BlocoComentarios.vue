<script setup lang="ts">
// O que os clientes disseram por último: cartões como citações, com a nota num selo da cor do grupo, o fundo suave do
// grupo, quem disse e a data. Com respostas.ver, o cartão abre a análise da resposta.
import { RouterLink } from 'vue-router'
import { MessageSquareText } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { formatarData, formatarDiaMes } from '@/utils/datas'
import { rotuloCategoria, tomCategoria } from '@/modulos/respostas/logica'

defineProps<{ comentarios: Painel['comentarios']; podeVerRespostas: boolean; /** Os filtros do painel, para "Ver todas". */ consulta?: Record<string, string> }>()

const FUNDO = { sucesso: 'bg-sucesso-suave', atencao: 'bg-atencao-suave', erro: 'bg-erro-suave' } as const
const SELO = { sucesso: 'bg-sucesso text-superficie', atencao: 'bg-atencao text-superficie', erro: 'bg-erro text-superficie' } as const
type Cor = keyof typeof FUNDO
function tom(c: Painel['comentarios'][number]): Cor | null {
  const t = tomCategoria(c.grupo, c.nota, c.tipo_nota)
  return t in FUNDO ? (t as Cor) : null
}
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-comentarios">
    <header class="flex items-start justify-between gap-3">
      <div>
        <h2 id="t-comentarios" class="text-base font-bold text-texto">O que os clientes disseram por último</h2>
        <p class="text-sm text-texto-suave">{{ podeVerRespostas ? 'Toque para abrir a resposta e criar o plano de ação.' : 'Os comentários mais recentes do período.' }}</p>
      </div>
      <RouterLink v-if="podeVerRespostas" :to="{ path: '/respostas', query: consulta ?? {} }" class="link inline-flex min-h-11 shrink-0 items-center text-sm">Ver todas</RouterLink>
    </header>
    <ul v-if="comentarios.length" class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      <li v-for="c in comentarios" :key="String(c.resposta_id)" class="min-w-0">
        <component
          :is="podeVerRespostas ? RouterLink : 'div'"
          :to="podeVerRespostas ? { path: '/respostas', query: { analisar: String(c.resposta_id) } } : undefined"
          class="flex h-full flex-col gap-2.5 rounded-xl p-4"
          :class="[tom(c) ? FUNDO[tom(c)!] : 'bg-superficie-2', podeVerRespostas ? 'ring-borda-forte hover:ring-1' : '']"
          data-comentario
        >
          <span class="flex items-center justify-between gap-3">
            <span class="inline-flex h-6 min-w-7 items-center justify-center rounded-md px-1.5 text-sm font-extrabold" :class="tom(c) ? SELO[tom(c)!] : 'bg-borda-forte text-texto'">
              <span class="sr-only">Nota </span>{{ c.nota ?? '—' }}<span class="sr-only">{{ c.tipo_nota === 'csat' ? ' de 5' : ' de 10' }}{{ c.grupo ? `, ${rotuloCategoria(c.grupo)}` : '' }}.</span>
            </span>
            <span class="text-xs text-texto-fraco"><span class="sr-only">Em </span><span aria-hidden="true">{{ formatarDiaMes(c.data) }}</span><span class="sr-only">{{ formatarData(c.data) }}</span></span>
          </span>
          <q class="line-clamp-4 whitespace-pre-line text-[0.95rem] leading-relaxed text-texto">{{ c.comentario }}</q>
          <span class="mt-auto truncate text-xs text-texto-suave">
            <strong class="font-semibold">{{ c.contato?.nome ?? 'Sem identificação' }}</strong><template v-if="c.empresa"> · {{ c.empresa.nome }}</template>
          </span>
        </component>
      </li>
    </ul>
    <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
      <MessageSquareText class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
      <p class="text-texto-suave">Nenhum comentário neste período.</p>
    </div>
  </section>
</template>
