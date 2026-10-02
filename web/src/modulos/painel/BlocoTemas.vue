<script setup lang="ts">
// "Do que estão falando": uma linha por tema (ponto na cor do tema), barra divergente com as reclamações à esquerda
// (`grafico-detrator`) e as demais menções à direita (`grafico-cinza`), na mesma escala; à direita a variação das menções
// (▲/▼/=) e a nota média. Cada linha tem a frase inteira para leitor de tela; com respostas.ver, abre as respostas do tema.
// No celular, o nome fica acima da barra.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Tags } from 'lucide-vue-next'
import type { Painel } from '@/api/tipos'
import { formatarNumero } from '@/utils/formatos'
import { corDoTema } from '@/modulos/relatorios/logica'
import { barrasDivergentes, descreverTema, formatarMedia1, tomNotaMedia, variacaoMencoes } from './logica'

const props = defineProps<{ temas: Painel['temas']; consulta: Record<string, string>; podeVerRespostas: boolean }>()

const COR_TOM = { sucesso: 'text-sucesso', atencao: 'text-atencao', erro: 'text-erro', neutro: 'text-texto-suave' } as const
const temReclamacoes = computed(() => props.temas.some((t) => typeof t.reclamacoes === 'number'))
const linhas = computed(() => {
  const barras = barrasDivergentes(props.temas)
  return props.temas.map((t, i) => {
    const v = variacaoMencoes(t.variacao)
    return {
      tema: t,
      barra: barras[i]!,
      cor: corDoTema(t.chave).fundo,
      leitura: descreverTema(t),
      variacao: v ? { seta: v.direcao === 'sobe' ? '▲' : v.direcao === 'desce' ? '▼' : '=', numero: v.direcao === 'igual' ? '' : String(Math.abs(Math.round(t.variacao as number))), direcao: v.direcao } : null,
      corNota: COR_TOM[tomNotaMedia(t.nota_media) as keyof typeof COR_TOM] ?? 'text-texto-suave',
    }
  })
})
</script>

<template>
  <section class="cartao flex flex-col gap-4 p-5 sm:p-6" aria-labelledby="t-temas">
    <header class="flex flex-col gap-2">
      <div>
        <h2 id="t-temas" class="text-base font-bold text-texto">Do que estão falando</h2>
        <p class="text-sm text-texto-suave">
          {{ temReclamacoes ? 'Reclamações à esquerda, demais menções à direita.' : 'Menções nos comentários de NPS.' }}
        </p>
      </div>
      <ul v-if="temas.length" class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-texto-suave" aria-label="Legenda">
        <li v-if="temReclamacoes" class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-detrator" aria-hidden="true" />reclamação</li>
        <li class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-[3px] bg-grafico-cinza" aria-hidden="true" />{{ temReclamacoes ? 'outras menções' : 'menções' }}</li>
        <li class="inline-flex items-center gap-1.5"><span aria-hidden="true">▲▼</span>menções contra o período anterior</li>
      </ul>
    </header>

    <ol v-if="temas.length" class="-mx-2 flex flex-col">
      <li v-for="l in linhas" :key="l.tema.chave" data-tema>
        <component
          :is="podeVerRespostas ? RouterLink : 'div'"
          :to="podeVerRespostas ? { path: '/respostas', query: { ...consulta, tema: l.tema.chave } } : undefined"
          class="grid min-h-11 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 rounded-xl px-2 py-2 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)_7.5rem]"
          :class="podeVerRespostas ? 'group hover:bg-superficie-2' : ''"
        >
          <span class="sr-only">{{ l.leitura }}</span>
          <!-- Nome -->
          <span class="flex min-w-0 items-center gap-2 text-sm font-semibold text-texto" aria-hidden="true">
            <span class="size-2.5 shrink-0 rounded-full" :class="l.cor" />
            <span class="truncate group-hover:underline">{{ l.tema.rotulo }}</span>
          </span>
          <!-- Variação e nota (no celular, ao lado do nome) -->
          <span class="col-start-2 row-start-1 whitespace-nowrap text-right text-xs font-semibold sm:col-start-3" aria-hidden="true">
            <!-- Mais menções não é necessariamente ruim: a seta fica cinza (a API não diz a variação das reclamações). -->
            <span v-if="l.variacao" class="text-texto-suave" data-variacao-tema>{{ l.variacao.seta }}{{ l.variacao.numero ? ` ${l.variacao.numero}` : '' }}</span>
            <span v-if="l.variacao && l.tema.nota_media !== null && l.tema.nota_media !== undefined" class="text-texto-fraco"> · </span>
            <span v-if="l.tema.nota_media !== null && l.tema.nota_media !== undefined" :class="l.corNota">nota {{ formatarMedia1(l.tema.nota_media) }}</span>
          </span>
          <!-- Barra divergente -->
          <span class="col-span-2 grid grid-cols-2 items-center gap-1 sm:col-span-1 sm:col-start-2 sm:row-start-1" aria-hidden="true">
            <span class="flex h-3 items-center justify-end gap-1.5">
              <span v-if="l.barra.reclamacoes" class="text-[11px] font-semibold tabular-nums text-texto-suave">{{ formatarNumero(l.barra.reclamacoes) }}</span>
              <span v-if="l.barra.esquerda > 0" class="h-full rounded-l-full bg-grafico-detrator" :style="{ width: `${Math.max(3, l.barra.esquerda * 85)}%` }" />
            </span>
            <span class="flex h-3 items-center gap-1.5 border-l border-borda-forte pl-1">
              <span v-if="l.barra.direita > 0" class="h-full rounded-r-full bg-grafico-cinza" :style="{ width: `${Math.max(3, l.barra.direita * 85)}%` }" />
              <span v-if="l.barra.outras" class="text-[11px] font-semibold tabular-nums text-texto-suave">{{ formatarNumero(l.barra.outras) }}</span>
            </span>
          </span>
        </component>
      </li>
    </ol>
    <div v-else class="flex items-start gap-3 rounded-xl bg-superficie-2 p-4 text-sm">
      <Tags class="mt-0.5 size-5 shrink-0 text-texto-fraco" aria-hidden="true" />
      <p class="text-texto-suave">Nenhum assunto encontrado nos comentários deste período.</p>
    </div>
  </section>
</template>
