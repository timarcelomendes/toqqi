<script setup lang="ts" generic="L">
export interface Coluna {
  chave: string
  rotulo: string
  /** Classes extras para th/td (ex.: esconder no celular: "hidden md:table-cell"). */
  classe?: string
  alinhar?: 'esquerda' | 'direita' | 'centro'
  /** Rótulo só para leitores de tela (ex.: coluna de ações). */
  rotuloOculto?: boolean
}

defineProps<{
  colunas: Coluna[]
  linhas: L[]
  chave: (linha: L) => string | number
  carregando?: boolean
  legenda?: string
}>()

defineSlots<
  {
    vazio?: () => unknown
  } & Record<`cel-${string}`, (p: { linha: L }) => unknown>
>()

const alinhamento = { esquerda: 'text-left', direita: 'text-right', centro: 'text-center' }
</script>

<template>
  <div class="relative overflow-x-auto">
    <table class="w-full border-collapse text-sm">
      <caption v-if="legenda" class="sr-only">{{ legenda }}</caption>
      <thead>
        <tr class="border-b border-borda">
          <th
            v-for="c in colunas"
            :key="c.chave"
            scope="col"
            class="whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-wide text-texto-fraco first:pl-5 last:pr-5"
            :class="[alinhamento[c.alinhar ?? 'esquerda'], c.classe]"
          >
            <span :class="{ 'sr-only': c.rotuloOculto }">{{ c.rotulo }}</span>
          </th>
        </tr>
      </thead>
      <tbody v-if="carregando">
        <tr v-for="i in 4" :key="i" class="border-b border-borda last:border-0">
          <td v-for="c in colunas" :key="c.chave" class="px-4 py-4 first:pl-5 last:pr-5" :class="c.classe">
            <div class="h-3.5 animate-pulse rounded bg-superficie-2" :style="{ width: `${50 + ((i * 13) % 40)}%` }" />
          </td>
        </tr>
      </tbody>
      <tbody v-else-if="linhas.length">
        <tr v-for="linha in linhas" :key="chave(linha)" class="border-b border-borda transition-colors last:border-0 hover:bg-superficie-2/50">
          <td
            v-for="c in colunas"
            :key="c.chave"
            class="px-4 py-3.5 align-middle first:pl-5 last:pr-5"
            :class="[alinhamento[c.alinhar ?? 'esquerda'], c.classe]"
          >
            <slot :name="`cel-${c.chave}`" :linha="linha">{{ (linha as Record<string, unknown>)[c.chave] ?? '—' }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!carregando && !linhas.length">
      <slot name="vazio"><p class="px-5 py-10 text-center text-sm text-texto-fraco">Nada por aqui ainda.</p></slot>
    </div>
  </div>
</template>
