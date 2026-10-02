<script setup lang="ts">
// Termos de uso e Política de privacidade (docs/api-aceite-lgpd.md §3): desenha um DocumentoLegal (dados em
// legal/termos.ts e legal/privacidade.ts). Sem v-html: texto puro e links como dados.
import { computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSessaoStore } from '@/stores/sessao'
import Botao from '@/components/ui/Botao.vue'
import { textoVersao } from './legal/aceite'
import { idDaAncora } from './legal/documento'
import { PRIVACIDADE } from './legal/privacidade'
import { TERMOS } from './legal/termos'
import TextoLegal from './legal/TextoLegal.vue'
import type { DocumentoLegal } from './legal/tipos'
import { VERSAO_DOCUMENTOS } from './legal/versao'

const props = defineProps<{ tipo: 'termos' | 'privacidade'; /** Só para testes: outro documento. */ documento?: DocumentoLegal }>()
const sessao = useSessaoStore()
const rota = useRoute()

const doc = computed<DocumentoLegal>(() => props.documento ?? (props.tipo === 'termos' ? TERMOS : PRIVACIDADE))
const versao = textoVersao(VERSAO_DOCUMENTOS)

const semMovimento = () =>
  typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Leva a seção da âncora para a vista e põe o foco no título dela (leitores de tela começam ali). */
async function irParaSecao(hash: string, suave: boolean) {
  const id = idDaAncora(hash)
  await nextTick()
  if (!id || !doc.value.secoes.some((s) => s.id === id)) {
    if (!suave) window.scrollTo?.({ top: 0 }) // âncora que não existe: começa do topo
    return
  }
  const titulo = document.getElementById(`t-${id}`)
  document.getElementById(id)?.scrollIntoView?.({ block: 'start', behavior: suave && !semMovimento() ? 'smooth' : 'auto' })
  titulo?.focus({ preventScroll: true })
}

// Abrir /privacidade#cookies: o router não rola (meta `ancoras`); a tela desce até a seção depois de montar.
onMounted(() => {
  if (rota.hash) irParaSecao(rota.hash, false)
})
// Clique no sumário (ou voltar/avançar entre seções).
// (De /termos para /privacidade a tela é a mesma, só troca o documento: por isso olha o caminho também.)
watch(
  () => [rota.path, rota.hash] as const,
  ([, hash]) => {
    if (hash) irParaSecao(hash, true)
  },
)
</script>

<template>
  <article class="max-w-none">
    <h1 class="text-2xl font-bold tracking-tight text-texto sm:text-[1.75rem]">{{ doc.titulo }}</h1>
    <p class="mt-2 text-sm text-texto-fraco" data-teste="versao">{{ versao }}</p>

    <div class="mt-6 space-y-4 leading-relaxed text-texto-suave">
      <template v-for="(b, i) in doc.introducao" :key="`i${i}`">
        <p v-if="b.tipo === 'p'"><TextoLegal :texto="b.texto" /></p>
      </template>
    </div>

    <nav v-if="doc.secoes.length" class="mt-6 rounded-xl border border-borda bg-superficie-2/50 p-4 sm:p-5" aria-labelledby="sumario">
      <h2 id="sumario" class="text-sm font-bold text-texto">Nesta página</h2>
      <ol class="mt-2 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
        <li v-for="(s, i) in doc.secoes" :key="s.id" class="flex gap-2">
          <span class="w-5 shrink-0 text-right tabular-nums text-texto-fraco">{{ i + 1 }}.</span>
          <RouterLink :to="{ hash: `#${s.id}` }" class="link font-medium">{{ s.titulo }}</RouterLink>
        </li>
      </ol>
    </nav>

    <section
      v-for="(s, i) in doc.secoes"
      :id="s.id"
      :key="s.id"
      class="mt-8 scroll-mt-6"
      :aria-labelledby="`t-${s.id}`"
    >
      <h2 :id="`t-${s.id}`" tabindex="-1" class="rounded-sm text-lg font-bold text-texto">{{ i + 1 }}. {{ s.titulo }}</h2>
      <div class="mt-3 space-y-4 leading-relaxed text-texto-suave">
        <template v-for="(b, j) in s.blocos" :key="j">
          <p v-if="b.tipo === 'p'"><TextoLegal :texto="b.texto" /></p>

          <ul v-else-if="b.tipo === 'lista'" class="list-disc space-y-1.5 pl-5 marker:text-texto-fraco">
            <li v-for="(item, k) in b.itens" :key="k"><TextoLegal :texto="item" /></li>
          </ul>

          <template v-else-if="b.tipo === 'tabela'">
            <!-- Celular: cada linha vira um cartão com os nomes das colunas. -->
            <ul class="flex flex-col gap-3 sm:hidden" data-teste="tabela-celular">
              <li v-for="(linha, k) in b.linhas" :key="k" class="rounded-xl border border-borda p-3.5 text-sm">
                <dl class="flex flex-col gap-2">
                  <div v-for="(cel, c) in linha" :key="c">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-texto-fraco">{{ b.colunas[c] }}</dt>
                    <dd class="mt-0.5 break-words" :class="c === 0 ? 'font-semibold text-texto' : ''"><TextoLegal :texto="cel" /></dd>
                  </div>
                </dl>
              </li>
            </ul>
            <!-- Computador: tabela. -->
            <div class="hidden overflow-x-auto rounded-xl border border-borda sm:block">
              <table class="w-full border-collapse text-sm">
                <thead class="bg-superficie-2/60">
                  <tr>
                    <th v-for="col in b.colunas" :key="col" scope="col" class="px-3 py-2.5 text-left font-semibold text-texto">{{ col }}</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-borda border-t border-borda">
                  <tr v-for="(linha, k) in b.linhas" :key="k" class="align-top">
                    <component
                      :is="c === 0 ? 'th' : 'td'"
                      v-for="(cel, c) in linha"
                      :key="c"
                      :scope="c === 0 ? 'row' : undefined"
                      class="px-3 py-2.5 text-left break-words"
                      :class="c === 0 ? 'font-semibold text-texto' : 'font-normal'"
                    >
                      <TextoLegal :texto="cel" />
                    </component>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </template>
      </div>
    </section>

    <Botao :para="sessao.logado ? '/inicio' : '/entrar'" variante="secundario" class="mt-10">Voltar</Botao>
  </article>
</template>
