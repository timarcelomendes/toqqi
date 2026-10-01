<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { MessageSquareText } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { rotuloCategoria, tomCategoria } from '@/modulos/respostas/logica'

defineProps<{ comentarios: Painel['comentarios']; podeVerRespostas: boolean; /** Os filtros do painel, para "Ver todas". */ consulta?: Record<string, string> }>()

const COR = { sucesso: 'bg-sucesso-suave text-sucesso', atencao: 'bg-atencao-suave text-atencao', erro: 'bg-erro-suave text-erro' } as const
function cor(c: Painel['comentarios'][number]) {
  return COR[tomCategoria(c.grupo, c.nota, c.tipo_nota) as keyof typeof COR] ?? 'bg-superficie-2 text-texto-suave'
}
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-comentarios">
    <header class="flex items-start justify-between gap-3">
      <div>
        <h2 id="t-comentarios" class="text-base font-bold text-texto">Comentários recentes</h2>
        <p class="text-sm text-texto-suave">O que os clientes escreveram por último. Toque para analisar.</p>
      </div>
      <RouterLink v-if="podeVerRespostas" :to="{ path: '/respostas', query: consulta ?? {} }" class="link inline-flex min-h-10 shrink-0 items-center text-sm">Ver todas</RouterLink>
    </header>
    <ul v-if="comentarios.length" class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      <li v-for="c in comentarios" :key="String(c.resposta_id)" class="min-w-0">
        <component
          :is="podeVerRespostas ? RouterLink : 'div'"
          :to="podeVerRespostas ? { path: '/respostas', query: { analisar: String(c.resposta_id) } } : undefined"
          class="flex h-full gap-3 rounded-xl border border-borda p-3.5"
          :class="podeVerRespostas ? 'hover:border-borda-forte hover:bg-superficie-2/60' : ''"
        >
          <span class="flex size-10 shrink-0 items-center justify-center rounded-xl text-base font-extrabold" :class="cor(c)">
            <span class="sr-only">Nota </span>{{ c.nota ?? '—' }}<span class="sr-only">{{ c.tipo_nota === 'csat' ? ' de 5' : ' de 10' }}{{ c.grupo ? `, ${rotuloCategoria(c.grupo)}` : '' }}.</span>
          </span>
          <span class="flex min-w-0 flex-1 flex-col">
            <span class="line-clamp-3 whitespace-pre-line text-sm text-texto">{{ c.comentario }}</span>
            <span class="mt-1 truncate text-xs text-texto-fraco">{{ c.contato?.nome ?? 'Sem identificação' }}<template v-if="c.empresa"> · {{ c.empresa.nome }}</template></span>
            <span class="text-xs text-texto-fraco">{{ formatarData(c.data) }}</span>
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
