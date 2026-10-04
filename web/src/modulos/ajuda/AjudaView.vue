<script setup lang="ts">
// Ajuda (docs/api-etapa-5b.md §6.1 e docs/ajuda-jornadas.md §3): o conteúdo de GET /ajuda em jornadas, tópicos e seções,
// com busca sem acento em tudo. Endereços: /ajuda e /ajuda/jornadas (a página Jornadas; sem jornadas no conteúdo, /ajuda
// abre o primeiro tópico), /ajuda/:topico e as âncoras (/ajuda/contatos#importar-planilha, /ajuda/jornadas#<id>).
// Telas largas: "Jornadas" e os tópicos à esquerda (fixos ao rolar); celular: a lista em pílulas e o conteúdo abaixo.
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { Route, Search, SearchX } from 'lucide-vue-next'
import { ajudaApi, mensagemDoErro, type TopicoAjuda } from '@/api'
import { useAssistenteStore } from '@/stores/assistente'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import IconeToqqiAI from '@/components/app/IconeToqqiAI.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import ChamadaJornada from './ChamadaJornada.vue'
import JornadasAjuda from './JornadasAjuda.vue'
import SecaoAjuda from './SecaoAjuda.vue'
import { comportamento, irParaSecao, type Navegar } from './ancora'
import { buscarNaAjuda, ID_JORNADAS, jornadasDoTopico, lerConteudo, TITULO_JORNADAS, type ConteudoLido, type ResultadoAjuda } from './logica'

const rota = useRoute()
const router = useRouter()
const assistente = useAssistenteStore()

const conteudo = ref<ConteudoLido | null>(null)
const carregando = ref(true)
const erro = ref<string | null>(null)
const busca = ref('')
const tituloTopico = ref<HTMLElement | null>(null)

const parametro = computed(() => {
  const t = rota.params.topico
  return (Array.isArray(t) ? t[0] : t) || null
})
const topicos = computed(() => conteudo.value?.topicos ?? [])
const jornadas = computed(() => conteudo.value?.jornadas ?? [])
/** /ajuda e /ajuda/jornadas mostram a página Jornadas, quando o conteúdo tem jornadas. */
const naJornadas = computed(() => jornadas.value.length > 0 && (!parametro.value || parametro.value === ID_JORNADAS))
/** O tópico do endereço; em /ajuda sem jornadas, o primeiro. */
const topico = computed<TopicoAjuda | null>(() =>
  naJornadas.value ? null : (topicos.value.find((t) => t.id === parametro.value) ?? topicos.value[0] ?? null),
)
/** As chamadas no topo do tópico aberto: as jornadas cujo primeiro "Saiba mais" é dele. */
const chamadas = computed(() => (topico.value ? jornadasDoTopico(jornadas.value, topico.value.id) : []))
const termo = computed(() => busca.value.trim())
const resultados = computed<ResultadoAjuda[]>(() => (conteudo.value && termo.value ? buscarNaAjuda(conteudo.value, termo.value) : []))
const anuncioBusca = computed(() => {
  if (!termo.value) return ''
  const total = resultados.value.length
  if (!total) return 'Nenhum resultado'
  const nJornadas = resultados.value.filter((r) => r.jornada).length
  const nSecoes = total - nJornadas
  const partes = [
    nJornadas ? `${nJornadas} ${nJornadas === 1 ? 'jornada' : 'jornadas'}` : '',
    nSecoes ? `${nSecoes} ${nSecoes === 1 ? 'seção' : 'seções'}` : '',
  ].filter(Boolean)
  return `${partes.join(' e ')} ${total === 1 ? 'encontrada' : 'encontradas'}`
})

const telaLarga = () => typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 1024px)').matches

/** Endereço com um tópico que não existe (ou /ajuda/jornadas num conteúdo sem jornadas): volta para /ajuda. */
function conferirTopico() {
  if (!conteudo.value || !parametro.value) return
  if (parametro.value === ID_JORNADAS && jornadas.value.length) return
  if (!topicos.value.some((t) => t.id === parametro.value)) router.replace({ path: '/ajuda' })
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

// Voltar e avançar, ou um link com âncora: vai para a seção (ou para o cartão da jornada).
watch(
  () => [parametro.value, rota.hash] as const,
  async ([, hash]) => {
    if (!conteudo.value) return
    conferirTopico()
    await nextTick()
    if (hash) irParaSecao(hash)
  },
)

const destinoTopico = (t: Pick<TopicoAjuda, 'id'>): RouteLocationRaw => ({ path: `/ajuda/${encodeURIComponent(t.id)}` })
/** A seção no tópico dela; uma jornada, no cartão dela (/ajuda/jornadas#<id>). */
const destinoResultado = (r: ResultadoAjuda): RouteLocationRaw => ({
  path: `/ajuda/${encodeURIComponent(r.topico.id)}`,
  hash: `#${encodeURIComponent(r.secao.id)}`,
})

/** Escolher um tópico (ou "Jornadas"): some a busca e o título da página ganha o foco (no celular, a tela desce até o conteúdo). */
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

/** "Pergunte ao ToqqiAI": abre o chat com o que foi procurado na caixa de texto (sem enviar: cada pergunta gasta análises da cota). */
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
  <EstadoVazio v-else-if="!topicos.length && !jornadas.length" :icone="SearchX" titulo="A ajuda ainda não tem conteúdo" descricao="Volte em breve." />

  <div v-else class="grid grid-cols-1 gap-6 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-10">
    <!-- "Jornadas" e os tópicos: pílulas no celular, lista fixa ao rolar nas telas largas -->
    <nav aria-label="Tópicos da ajuda" class="min-w-0 lg:sticky lg:top-24 lg:max-h-[calc(100dvh-7rem)] lg:self-start lg:overflow-y-auto" data-topicos>
      <p v-if="!jornadas.length" class="mb-2 hidden px-3 text-xs font-semibold uppercase tracking-wider text-texto-fraco lg:block">Tópicos</p>
      <ul class="flex flex-wrap gap-2 lg:flex-col lg:gap-0.5">
        <li v-if="jornadas.length">
          <RouterLink v-slot="{ href, navigate }" :to="destinoTopico({ id: ID_JORNADAS })" custom>
            <a
              :href="href"
              :aria-current="!termo && naJornadas ? 'page' : undefined"
              class="flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-semibold transition-colors lg:rounded-xl lg:border-transparent lg:py-2"
              :class="
                !termo && naJornadas ? 'border-marca/30 bg-marca-suave text-marca-texto' : 'border-borda-forte text-texto-suave hover:bg-superficie-2 hover:text-texto'
              "
              :data-topico="ID_JORNADAS"
              @click="(e: MouseEvent) => abrirTopico(navigate, e)"
            >
              <Route class="size-4 shrink-0" aria-hidden="true" />
              {{ TITULO_JORNADAS }}
            </a>
          </RouterLink>
          <!-- Telas largas: o rótulo dos tópicos fica entre "Jornadas" e eles (o menu já se chama "Tópicos da ajuda"). -->
          <p class="mb-2 mt-5 hidden px-3 text-xs font-semibold uppercase tracking-wider text-texto-fraco lg:block" aria-hidden="true">Tópicos</p>
        </li>
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
              <IconeToqqiAI class="size-4" /> Pergunte ao ToqqiAI
            </Botao>
          </EstadoVazio>
        </div>
      </section>

      <!-- Jornadas: a abertura da Ajuda (docs/ajuda-jornadas.md §3) -->
      <article v-else-if="naJornadas" aria-labelledby="t-topico" data-pagina-jornadas>
        <header class="mb-6">
          <h2 id="t-topico" ref="tituloTopico" tabindex="-1" class="text-xl font-bold text-texto focus:outline-none sm:text-2xl">{{ TITULO_JORNADAS }}</h2>
          <p class="mt-1.5 max-w-2xl text-[0.95rem] text-texto-suave">
            Cada funcionalidade em três partes: onde fica, como fazer e o que você ganha. Na primeira vez, siga na ordem.
          </p>
        </header>
        <JornadasAjuda :jornadas="jornadas" :topicos="topicos" />
      </article>

      <!-- Tópico aberto -->
      <article v-else-if="topico" aria-labelledby="t-topico" :data-topico-aberto="topico.id">
        <header class="mb-5">
          <h2 id="t-topico" ref="tituloTopico" tabindex="-1" class="text-xl font-bold text-texto focus:outline-none sm:text-2xl">{{ topico.titulo }}</h2>
          <p v-if="topico.resumo" class="mt-1.5 max-w-2xl text-[0.95rem] text-texto-suave">{{ topico.resumo }}</p>
        </header>
        <div v-if="chamadas.length" class="mb-5 flex flex-col gap-3">
          <ChamadaJornada v-for="j in chamadas" :key="j.id" :jornada="j" />
        </div>
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
          <strong class="font-semibold text-texto">Ainda com dúvida?</strong> O ToqqiAI responde sobre o uso do Toqqi e sobre os resultados dos seus clientes.
        </p>
        <Botao variante="secundario" class="shrink-0" @click="perguntarAoAssistente()">
          <IconeToqqiAI class="size-4" /> Pergunte ao ToqqiAI
        </Botao>
      </aside>
    </div>
  </div>
</template>
