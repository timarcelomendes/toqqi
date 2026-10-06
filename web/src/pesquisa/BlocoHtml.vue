<script setup lang="ts">
// O ÚNICO componente do site com v-html (docs/api-etapa-5l.md §3.3; tests/htmlSeguro.test.ts confere). Todo HTML que
// chega aqui passa por `limparHtml` (lista permitida de §3.1) antes de ir para a tela. As citações já vêm trocadas e
// escapadas por quem usa (`citarHtml`). Sem o limpador (falha ao carregar), mostra só o texto: nunca o HTML cru.
import { ref, watch } from 'vue'
import { limparHtmlComRelatorio, textoDoHtml, type ResultadoLimpeza } from './html'

const props = defineProps<{
  html: string | null | undefined
  /** O começo das URLs das imagens da plataforma (as outras imagens saem). */
  prefixoImagens?: string | null
}>()
const emit = defineEmits<{
  /** O HTML já limpo e o que foi removido (o editor mostra o aviso). */
  limpo: [ResultadoLimpeza]
}>()

const limpo = ref('')
const pronto = ref(false)
const textoPuro = ref<string | null>(null)
let pedido = 0

watch(
  [() => props.html, () => props.prefixoImagens],
  async ([html, prefixo]) => {
    const meu = ++pedido
    try {
      const r = await limparHtmlComRelatorio(html ?? '', prefixo ?? null)
      if (meu !== pedido) return
      limpo.value = r.html
      textoPuro.value = null
      emit('limpo', r)
    } catch {
      if (meu !== pedido) return
      limpo.value = ''
      textoPuro.value = textoDoHtml(html)
    } finally {
      if (meu === pedido) pronto.value = true
    }
  },
  { immediate: true },
)
</script>

<template>
  <div v-if="textoPuro !== null" class="bloco-html" data-bloco-html="texto"><p>{{ textoPuro }}</p></div>
  <div v-else class="bloco-html" :aria-busy="pronto ? undefined : 'true'" data-bloco-html v-html="limpo" />
</template>

<style>
/* Tipografia do HTML dos blocos de conteúdo e dos finais (o Tailwind zera listas, títulos e margens). A pesquisa é
   sempre clara; a cor da pesquisa entra nos detalhes (sublinhado dos links, barra da citação). */
.bloco-html {
  font-size: 1rem;
  line-height: 1.6;
  color: #334155;
  overflow-wrap: anywhere;
}
.bloco-html > :first-child {
  margin-top: 0;
}
.bloco-html > :last-child {
  margin-bottom: 0;
}
.bloco-html p,
.bloco-html ul,
.bloco-html ol,
.bloco-html blockquote,
.bloco-html pre,
.bloco-html table,
.bloco-html figure,
.bloco-html div {
  margin: 0 0 0.85em;
}
.bloco-html h2,
.bloco-html h3,
.bloco-html h4 {
  color: #0f172a;
  line-height: 1.25;
  margin: 1.1em 0 0.45em;
}
.bloco-html h2 {
  font-size: 1.35rem;
  font-weight: 800;
}
.bloco-html h3 {
  font-size: 1.15rem;
  font-weight: 700;
}
.bloco-html h4 {
  font-size: 1rem;
  font-weight: 700;
}
.bloco-html strong,
.bloco-html b {
  font-weight: 700;
  color: #0f172a;
}
/* Só links de verdade (um <a> sem endereço, como o que perdeu um href perigoso na limpeza, fica como texto). */
.bloco-html a[href] {
  color: #0f172a;
  font-weight: 600;
  text-decoration: underline;
  text-decoration-color: var(--cor, #94a3b8);
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
}
.bloco-html a[href]:focus-visible {
  outline: 2px solid #0f172a;
  outline-offset: 2px;
  border-radius: 2px;
}
.bloco-html ul {
  list-style: disc;
  padding-left: 1.4em;
}
.bloco-html ol {
  list-style: decimal;
  padding-left: 1.4em;
}
.bloco-html li + li {
  margin-top: 0.25em;
}
.bloco-html blockquote {
  border-left: 3px solid var(--cor, #cbd5e1);
  padding-left: 1em;
  color: #475569;
}
.bloco-html hr {
  border: 0;
  border-top: 1px solid #e2e8f0;
  margin: 1.4em 0;
}
.bloco-html img {
  display: inline-block;
  vertical-align: middle;
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
.bloco-html table {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  font-size: 0.95em;
}
.bloco-html th,
.bloco-html td {
  border: 1px solid #e2e8f0;
  padding: 0.4em 0.65em;
  text-align: left;
  vertical-align: top;
}
.bloco-html th {
  background: #f8fafc;
  font-weight: 700;
  color: #0f172a;
}
.bloco-html caption {
  caption-side: bottom;
  padding-top: 0.4em;
  font-size: 0.85em;
  color: #64748b;
}
.bloco-html code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
  background: #f1f5f9;
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.bloco-html pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 0.8em 1em;
  border-radius: 8px;
  overflow-x: auto;
  white-space: pre-wrap;
}
.bloco-html pre code {
  background: none;
  padding: 0;
  color: inherit;
}
.bloco-html small {
  font-size: 0.85em;
}
.bloco-html figcaption {
  margin-top: 0.3em;
  font-size: 0.85em;
  color: #64748b;
}
</style>
