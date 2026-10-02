<script setup lang="ts">
// Plano de ação (etapa 5d, docs/api-etapa-5d.md §6.3): os passos que a IA sugeriu ao criar a ação a partir de uma
// resposta. Pendente: relê a ação a cada 5 s, até 6 vezes (para ao fechar o painel ou trocar de ação). Pronta: a lista
// numerada, para copiar. Sem situação (sem comentário, sem IA ou desligado na conta), nada aparece.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { LoaderCircle, Sparkles } from 'lucide-vue-next'
import { acoesApi, type Acao, type SituacaoPassosIa } from '@/api'
import BotaoCopiar from '@/components/ui/BotaoCopiar.vue'
import {
  INTERVALO_PASSOS,
  RELEITURAS_PASSOS,
  TEXTOS_PASSOS,
  listaDeTextos,
  situacaoPassos,
  textoPassos,
  type PassosAtualizados,
} from '@/modulos/ia/logica'

const props = defineProps<{ acao: Acao }>()
const emit = defineEmits<{ atualizada: [PassosAtualizados] }>()

const situacao = ref<SituacaoPassosIa | null>(null)
const passos = ref<string[]>([])
const releituras = ref(0)
let temporizador: ReturnType<typeof setTimeout> | undefined
/** Muda a cada troca de ação (ou ao sair): releituras que voltam depois são ignoradas. */
let vez = 0

/** Releu 6 vezes e continua pendente: a sugestão pode ficar pronta mais tarde (pela tarefa da IA). */
const esgotou = computed(() => situacao.value === 'pendente' && releituras.value >= RELEITURAS_PASSOS)
const visivel = computed(() => situacao.value !== null && (situacao.value !== 'pronta' || passos.value.length > 0))

function parar() {
  vez++
  if (temporizador !== undefined) clearTimeout(temporizador)
  temporizador = undefined
}

function agendar() {
  if (situacao.value !== 'pendente' || releituras.value >= RELEITURAS_PASSOS || temporizador !== undefined) return
  const minha = vez
  temporizador = setTimeout(() => {
    temporizador = undefined
    if (minha === vez) void reler(minha)
  }, INTERVALO_PASSOS)
}

async function reler(minha: number) {
  releituras.value++
  const id = props.acao.id
  try {
    const a = await acoesApi.obter(id)
    if (minha !== vez) return
    const s = situacaoPassos(a?.ia_passos_situacao)
    const p = listaDeTextos(a?.ia_passos)
    if (s !== situacao.value || p.join('\n') !== passos.value.join('\n')) {
      situacao.value = s
      passos.value = p
      // A tela guarda os passos na ação (cartão e painel), sem trocar o formulário que a pessoa pode estar editando.
      emit('atualizada', { id, ia_passos: p.length ? p : null, ia_passos_situacao: s })
    }
  } catch {
    // Sem conexão ou a ação sumiu: conta como uma releitura e tenta na próxima.
    if (minha !== vez) return
  }
  agendar()
}

// Outra ação no painel, ou a mesma com os passos mudados por fora: começa de novo a partir dela.
watch(
  () => [props.acao.id, props.acao.ia_passos_situacao, JSON.stringify(props.acao.ia_passos ?? null)],
  () => {
    parar()
    situacao.value = situacaoPassos(props.acao.ia_passos_situacao)
    passos.value = listaDeTextos(props.acao.ia_passos)
    releituras.value = 0
    agendar()
  },
  { immediate: true },
)

onBeforeUnmount(parar)
</script>

<template>
  <section v-if="visivel" aria-labelledby="t-passos-ia" data-passos-ia :data-situacao="situacao">
    <div class="mb-2 flex min-h-8 items-center justify-between gap-3">
      <h3 id="t-passos-ia" class="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wide text-texto-fraco">
        <Sparkles class="size-4 shrink-0" aria-hidden="true" /> {{ TEXTOS_PASSOS.titulo }}
      </h3>
      <BotaoCopiar v-if="situacao === 'pronta'" :texto="textoPassos(passos)" rotulo="Copiar passos" copiado="Copiados!" variante="fantasma" tamanho="sm" />
    </div>
    <div class="rounded-xl border border-borda p-4 text-sm" aria-live="polite">
      <template v-if="situacao === 'pronta'">
        <ol class="flex list-decimal flex-col gap-1.5 pl-5 leading-relaxed text-texto marker:font-semibold marker:text-texto-suave" data-lista-passos>
          <li v-for="(p, i) in passos" :key="i" class="break-words pl-1">{{ p }}</li>
        </ol>
        <p class="mt-3 text-xs text-texto-fraco">{{ TEXTOS_PASSOS.nota }}</p>
      </template>
      <div v-else-if="situacao === 'pendente'" class="flex items-start gap-2 text-texto-suave">
        <LoaderCircle v-if="!esgotou" class="mt-0.5 size-4 shrink-0 animate-spin" aria-hidden="true" />
        <div class="min-w-0">
          <p>{{ TEXTOS_PASSOS.pendente }}</p>
          <p v-if="esgotou" class="mt-1 text-xs text-texto-fraco" data-passos-demorando>{{ TEXTOS_PASSOS.demorando }}</p>
        </div>
      </div>
      <p v-else-if="situacao === 'falhou'" class="text-texto-suave">{{ TEXTOS_PASSOS.falhou }}</p>
      <p v-else class="text-texto-suave">{{ TEXTOS_PASSOS.limite }}</p>
    </div>
  </section>
</template>
