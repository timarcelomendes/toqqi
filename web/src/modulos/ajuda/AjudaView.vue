<script setup lang="ts">
// Ajuda (docs/api-etapa-5b.md §6.1): o conteúdo de GET /ajuda em tópicos e seções, com busca sem acento em todos os
// tópicos. Endereços: /ajuda (primeiro tópico), /ajuda/:topico e a âncora da seção (/ajuda/contatos#importar-planilha).
// Telas largas: tópicos à esquerda (fixos ao rolar); celular: a lista de tópicos e o conteúdo abaixo.
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { Search, SearchX, Sparkles } from 'lucide-vue-next'
import { ajudaApi, mensagemDoErro, type ConteudoAjuda, type TopicoAjuda } from '@/api'
import { useAssistenteStore } from '@/stores/assistente'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import { semMovimento } from '@/modulos/assistente/logica'
import SecaoAjuda from './SecaoAjuda.vue'
import { buscarNaAjuda, lerConteudo, type ResultadoAjuda } from './logica'

const rota = useRoute()
const router = useRouter()
const assistente = useAssistenteStore()

const conteudo = ref<ConteudoAjuda | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const busca = ref('')
const tituloTopico = ref<HTMLElement | null>(null)

const parametro = computed(() => {
  const t = rota.params.topico
  return (Array.isArray(t) ? t[0] : t) || null
})
const topicos = computed(() => conteudo.value?.topicos ?? [])
/** O tópico do endereço; em /ajuda, o primeiro. */
const topico = computed<TopicoAjuda | null>(() => topicos.value.find((t) => t.id === parametro.value) ?? topicos.value[0] ?? null)
const termo = computed(() => busca.value.trim())
const resultados = computed<ResultadoAjuda[]>(() => (conteudo.value && termo.value ? buscarNaAjuda(conteudo.value, termo.value) : []))
const anuncioBusca = computed(() => {
  if (!termo.value) return ''
  const n = resultados.value.length
  return n ? `${n} ${n === 1 ? 'seção encontrada' : 'seções encontradas'}` : 'Nenhum resultado'
})

const comportamento = (): ScrollBehavior => (semMovimento() ? 'auto' : 'smooth')
const telaLarga = () => typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 1024px)').matches

/** Leva a seção da âncora para a vista e põe o foco no título dela (leitores de tela começam ali). */
function irParaSecao(ancora: string) {
  let id = ancora.replace(/^#/, '')
  try {
    id = decodeURIComponent(id)
  } catch {
    /* âncora malformada: usa como veio */
  }
  if (!id) return
  const secao = document.getElementById(`ajuda-${id}`)
  if (!secao) return
  secao.scrollIntoView?.({ block: 'start', behavior: comportamento() })
  document.getElementById(`t-ajuda-${id}`)?.focus({ preventScroll: true })
}

/** Endereço com um tópico que não existe: volta para /ajuda. */
function conferirTopico() {
  if (conteudo.value && parametro.value && !topicos.value.some((t) => t.id === parametro.value)) {
    router.replace({ path: '/ajuda' })
  }
}

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    conteudo.value = lerConteudo(await ajudaApi.obter())
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
  conferirTopico()
  await nextTick()
  if (rota.hash) irParaSecao(rota.hash)
}

// Voltar e avançar, ou um link com âncora: vai para a seção.
watch(
  () => [parametro.value, rota.hash] as const,
  async ([, hash]) => {
    if (!conteudo.value) return
    conferirTopico()
    await nextTick()
    if (hash) irParaSecao(hash)
  },
)

const destinoTopico = (t: TopicoAjuda): RouteLocationRaw => ({ path: `/ajuda/${encodeURIComponent(t.id)}` })
const destinoResultado = (r: ResultadoAjuda): RouteLocationRaw => ({
  path: `/ajuda/${encodeURIComponent(r.topico.id)}`,
  hash: `#${encodeURIComponent(r.secao.id)}`,
})

type Navegar = (e?: MouseEvent) => Promise<unknown>

/** Escolher um tópico: some a busca e o título do tópico ganha o foco (no celular, a tela desce até o conteúdo). */
async function abrirTopico(navegar: Navegar, e: MouseEvent) {
  await navegar(e)
  if (!e.defaultPrevented) return // Ctrl+clique etc.: o navegador abre em outra aba
  busca.value = ''
  await nextTick()
  const h = tituloTopico.value
  if (!h) return
  const r = h.getBoundingClientRect()
  if (!telaLarga() || r.top < 72) h.scrollIntoView?.({ block: 'start', behavior: comportamento() })
  h.focus({ preventScroll: true })
}

async function abrirResultado(navegar: Navegar, e: MouseEvent, r: ResultadoAjuda) {
  await navegar(e)
  if (!e.defaultPrevented) return
  busca.value = ''
  await nextTick()
  irParaSecao(r.secao.id)
}

/** "Pergunte ao assistente": abre o chat com o que foi procurado na caixa de texto (sem enviar: cada pergunta gasta 1 análise). */
function perguntarAoAssistente(texto?: string) {
  assistente.abrir(texto)
}

onMounted(carregar)
</script>

<template>
  <CabecalhoPagina titulo="Ajuda" descricao="Como usar cada parte do Toqqi, passo a passo." />

  <div role="search" class="mb-6 max-w-xl">
    <Campo v-model="busca" tipo="search" rotulo="Buscar na ajuda" rotulo-oculto placeholder="Buscar na ajuda" autocomplete="off" data-busca-ajuda>
      <template #antes><Search class="size-4" aria-hidden="true" /></template>
    </Campo>
  </div>
  <p class="sr-only" role="status">{{ anuncioBusca }}</p>

  <Carregando v-if="carregando" :linhas="5" rotulo="Carregando a ajuda…" />
  <Alerta v-else-if="erro" tom="erro">
    {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>
  <EstadoVazio v-else-if="!topicos.length" :icone="SearchX" titulo="A ajuda ainda não tem conteúdo" descricao="Volte em breve." />

  <div v-else class="grid grid-cols-1 gap-6 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-10">
    <!-- Tópicos: chips no celular, lista fixa ao rolar nas telas largas -->
    <nav aria-label="Tópicos da ajuda" class="min-w-0 lg:sticky lg:top-24 lg:max-h-[calc(100dvh-7rem)] lg:self-start lg:overflow-y-auto" data-topicos>
      <p class="mb-2 hidden px-3 text-xs font-semibold uppercase tracking-wider text-texto-fraco lg:block">Tópicos</p>
      <ul class="flex flex-wrap gap-2 lg:flex-col lg:gap-0.5">
        <li v-for="t in topicos" :key="t.id">
          <RouterLink v-slot="{ href, navigate }" :to="destinoTopico(t)" custom>
            <a
              :href="href"
              :aria-current="!termo && topico?.id === t.id ? 'page' : undefined"
              class="flex items-center rounded-full border px-3 py-1.5 text-sm font-semibold transition-colors lg:rounded-xl lg:border-transparent lg:py-2"
              :class="
                !termo && topico?.id === t.id
                  ? 'border-marca/30 bg-marca-suave text-marca-texto'
                  : 'border-borda-forte text-texto-suave hover:bg-superficie-2 hover:text-texto'
              "
              :data-topico="t.id"
              @click="(e: MouseEvent) => abrirTopico(navigate, e)"
            >
              {{ t.titulo }}
            </a>
          </RouterLink>
        </li>
      </ul>
    </nav>

    <div class="min-w-0">
      <!-- Busca -->
      <section v-if="termo" aria-labelledby="t-resultados" data-resultados>
        <template v-if="resultados.length">
          <h2 id="t-resultados" class="mb-4 text-lg font-bold text-texto">Resultados para “{{ termo }}”</h2>
          <ul class="flex flex-col gap-3">
            <!-- O cartão inteiro abre a seção (o link se estende por ele); o nome do link é só o título da seção. -->
            <li v-for="r in resultados" :key="`${r.topico.id}#${r.secao.id}`" class="cartao relative p-4 transition-colors hover:border-marca/40 sm:p-5">
              <p class="text-xs font-semibold uppercase tracking-wide text-texto-fraco" data-resultado-topico>{{ r.topico.titulo }}</p>
              <RouterLink v-slot="{ href, navigate }" :to="destinoResultado(r)" custom>
                <a
                  :href="href"
                  class="mt-0.5 block font-bold text-texto after:absolute after:inset-0 after:rounded-cartao after:content-['']"
                  :data-resultado="`${r.topico.id}#${r.secao.id}`"
                  @click="(e: MouseEvent) => abrirResultado(navigate, e, r)"
                  >{{ r.secao.titulo }}</a
                >
              </RouterLink>
              <p v-if="r.trecho" class="mt-1 text-sm text-texto-suave" data-resultado-trecho>{{ r.trecho }}</p>
            </li>
          </ul>
        </template>
        <div v-else class="cartao">
          <h2 id="t-resultados" class="sr-only">Nenhum resultado</h2>
          <EstadoVazio :icone="SearchX" titulo="Nenhum resultado" :descricao="`Não achamos “${termo}” na ajuda. Tente outras palavras ou escolha um tópico.`">
            <Botao v-if="assistente.disponivel" variante="secundario" data-perguntar-assistente @click="perguntarAoAssistente(termo)">
              <Sparkles class="size-4" aria-hidden="true" /> Pergunte ao assistente
            </Botao>
          </EstadoVazio>
        </div>
      </section>

      <!-- Tópico aberto -->
      <article v-else-if="topico" aria-labelledby="t-topico" :data-topico-aberto="topico.id">
        <header class="mb-5">
          <h2 id="t-topico" ref="tituloTopico" tabindex="-1" class="text-xl font-bold text-texto focus:outline-none sm:text-2xl">{{ topico.titulo }}</h2>
          <p v-if="topico.resumo" class="mt-1.5 max-w-2xl text-[0.95rem] text-texto-suave">{{ topico.resumo }}</p>
        </header>
        <div class="flex flex-col gap-4">
          <SecaoAjuda v-for="s in topico.secoes" :key="s.id" :secao="s" />
        </div>
      </article>

      <aside
        v-if="assistente.disponivel"
        class="mt-8 flex flex-col items-start gap-3 rounded-cartao border border-dashed border-borda-forte p-5 sm:flex-row sm:items-center sm:justify-between"
        data-rodape-ajuda
      >
        <p class="text-sm text-texto-suave">
          <strong class="font-semibold text-texto">Ainda com dúvida?</strong> O assistente responde sobre o uso do Toqqi e sobre os resultados dos seus clientes.
        </p>
        <Botao variante="secundario" class="shrink-0" @click="perguntarAoAssistente()">
          <Sparkles class="size-4" aria-hidden="true" /> Pergunte ao assistente
        </Botao>
      </aside>
    </div>
  </div>
</template>
