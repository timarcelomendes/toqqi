<script setup lang="ts">
// Seção "Lógica" da pergunta ou do bloco de conteúdo (docs/api-etapa-5l.md §5.3), recolhível (aberta se o item tiver
// lógica): "Quando mostrar" (Sempre / Só se…) e, nas perguntas que podem pular, "Depois desta pergunta" (as regras).
// Na nota principal: "A nota principal sempre aparece" e os atalhos de segmento.
import { computed, ref, watch } from 'vue'
import { ChevronDown, GitBranch, Sparkles } from 'lucide-vue-next'
import type { Pergunta } from '@/api/tipos'
import { avisar } from '@/composables/avisos'
import { indicePrincipal, respondivel } from '@/pesquisa/logica'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Botao from '@/components/ui/Botao.vue'
import { condicaoPadrao, descreverGrupo, fontesPara, MAX_FINAIS, temLogica } from '../logicaEditor'
import { errosDaLogica, LIMITE_PERGUNTAS } from '../validacaoFormulario'
import { usarEditor } from './documento'
import ConstrutorGrupo from './ConstrutorGrupo.vue'
import RegrasPular from './RegrasPular.vue'
import { finaisPorSegmento, perguntasPorSegmento, posicaoParaFinalComCondicao } from './segmentos'

const props = defineProps<{ item: Pergunta; indice: number }>()
const editor = usarEditor()

const itens = computed(() => editor.doc.perguntas)
const ip = computed(() => indicePrincipal(itens.value))
const ehPrincipal = computed(() => props.indice === ip.value)
const antesDaPrincipal = computed(() => ip.value >= 0 && props.indice < ip.value)
const ehPergunta = computed(() => respondivel(props.item.tipo))
const fontes = computed(() => fontesPara(itens.value, 'mostrar_se', props.indice))
const problemas = computed(() => editor.problemas.value.filter((p) => 'id' in p.alvo && p.alvo.id === props.item.id))
const errosMostrar = computed(() => errosDaLogica(problemas.value, 'mostrar_se'))
const errosPular = computed(() => errosDaLogica(problemas.value, 'pular').geral)
const qtdRegras = computed(() => props.item.logica?.pular?.length ?? 0)

const aberta = ref(temLogica(props.item) || ehPrincipal.value)
watch(
  () => editor.pedidoFoco.value,
  (p) => {
    if (p?.id === props.item.id && p.campo === 'logica') aberta.value = true
  },
)

/** Resumo com a seção fechada. */
const resumo = computed(() => {
  const partes: string[] = []
  const g = props.item.logica?.mostrar_se
  if (g?.condicoes?.length) partes.push(`Mostrar se: ${descreverGrupo(g, itens.value)}`)
  if (qtdRegras.value) partes.push(qtdRegras.value === 1 ? '1 regra de pular' : `${qtdRegras.value} regras de pular`)
  return partes.join(' · ') || (ehPrincipal.value ? 'A nota principal sempre aparece' : 'Sempre aparece')
})

type Modo = 'sempre' | 'so_se'
const MODOS: { valor: Modo; rotulo: string }[] = [
  { valor: 'sempre', rotulo: 'Sempre' },
  { valor: 'so_se', rotulo: 'Só se…' },
]
const modo = computed<Modo>({
  get: () => (props.item.logica?.mostrar_se ? 'so_se' : 'sempre'),
  set: (m) => {
    if (m === 'sempre') return tirarMostrar()
    // A condição nova usa a nota principal (o caso mais comum), se ela vier antes; senão a pergunta anterior.
    const fonte = fontes.value.find((p) => p.id === itens.value[ip.value]?.id) ?? fontes.value[fontes.value.length - 1]
    if (!fonte) return
    props.item.logica = { ...(props.item.logica ?? {}), mostrar_se: { juncao: 'todas', condicoes: [condicaoPadrao(fonte)] } }
  },
})

function tirarMostrar() {
  if (!props.item.logica) return
  if (props.item.logica.pular?.length) props.item.logica.mostrar_se = null
  else delete props.item.logica
}

// ── atalhos da nota principal ──
function criarAcompanhamento() {
  const novos = perguntasPorSegmento(props.item, itens.value)
  if (itens.value.filter((p) => respondivel(p.tipo)).length + novos.length > LIMITE_PERGUNTAS) {
    avisar.atencao(`Use no máximo ${LIMITE_PERGUNTAS} perguntas.`)
    return
  }
  editor.mudar(() => editor.doc.perguntas.splice(props.indice + 1, 0, ...novos))
  editor.selecionado.value = novos[0]!.id
  avisar.sucesso('Pronto: uma pergunta para quem não gostou e outra para quem gostou, logo depois da nota.')
}

function criarFinais() {
  const novos = finaisPorSegmento(props.item, editor.doc.finais)
  if (editor.doc.finais.length + novos.length > MAX_FINAIS) {
    avisar.atencao(`Use no máximo ${MAX_FINAIS} finais.`)
    return
  }
  const pos = posicaoParaFinalComCondicao(editor.doc.finais)
  editor.mudar(() => editor.doc.finais.splice(pos, 0, ...novos))
  editor.selecionado.value = novos[0]!.id
  avisar.sucesso('Pronto: um final para cada segmento. Ajuste os textos e, se quiser, ponha um botão.')
}
</script>

<template>
  <section class="rounded-2xl border border-borda" data-secao-logica>
    <h3>
      <button
        type="button"
        class="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left hover:bg-superficie-2/60"
        :aria-expanded="aberta"
        :aria-controls="`logica-${item.id}`"
        data-alternar-logica
        @click="aberta = !aberta"
      >
        <span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-info-suave text-info" aria-hidden="true"><GitBranch class="size-4" /></span>
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-bold text-texto">Lógica</span>
          <span class="line-clamp-2 block text-xs text-texto-fraco">{{ resumo }}</span>
        </span>
        <span v-if="problemas.some((p) => p.campo === 'logica' && !p.aviso)" class="size-2 shrink-0 rounded-full bg-erro" aria-hidden="true" />
        <ChevronDown class="size-4 shrink-0 text-texto-fraco transition-transform" :class="aberta ? 'rotate-180' : ''" aria-hidden="true" />
      </button>
    </h3>

    <div v-show="aberta" :id="`logica-${item.id}`" class="flex flex-col gap-5 border-t border-borda px-4 pb-4 pt-4">
      <!-- Quando mostrar -->
      <div class="flex flex-col gap-3" data-logica-onde="mostrar_se">
        <h4 class="text-sm font-bold text-texto">Quando mostrar</h4>
        <template v-if="ehPrincipal">
          <p class="text-sm text-texto-suave">A nota principal sempre aparece. É ela que vai para o NPS (ou CSAT), os relatórios e o e-mail, por isso não tem condição.</p>
          <p v-if="errosMostrar.geral.length" class="text-sm font-medium text-erro">{{ errosMostrar.geral[0] }} <button type="button" class="link ml-1" @click="tirarMostrar">Tirar a condição</button></p>
          <div class="rounded-xl bg-superficie-2/70 p-3">
            <p class="flex items-center gap-1.5 text-sm font-semibold text-texto"><Sparkles class="size-4 text-marca-texto" aria-hidden="true" /> Atalhos</p>
            <div class="mt-2 flex flex-wrap gap-2">
              <Botao variante="secundario" tamanho="sm" data-criar-acompanhamento @click="criarAcompanhamento">Criar acompanhamento por segmento</Botao>
              <Botao variante="secundario" tamanho="sm" data-criar-finais @click="criarFinais">Criar finais por segmento</Botao>
            </div>
            <p class="mt-2 text-xs text-texto-fraco">
              {{ item.tipo === 'nps' ? 'Uma pergunta e um final para promotores e outros para detratores.' : 'Uma pergunta e um final para quem ficou satisfeito e outros para quem ficou insatisfeito.' }}
            </p>
          </div>
        </template>
        <template v-else>
          <BotoesSegmentados v-model="modo" :opcoes="MODOS" rotulo="Quando mostrar" :desabilitado="!fontes.length && modo === 'sempre'" />
          <p v-if="!fontes.length && modo === 'sempre'" class="text-sm text-texto-fraco">Só dá para usar condição com perguntas antes deste item.</p>
          <ConstrutorGrupo
            v-if="item.logica?.mostrar_se"
            :grupo="item.logica.mostrar_se"
            :fontes="fontes"
            :itens="itens"
            prefixo="Mostrar quando"
            :erros="errosMostrar"
            @vazio="tirarMostrar"
          />
          <ul v-if="errosMostrar.geral.length" class="flex flex-col gap-0.5">
            <li v-for="m in errosMostrar.geral" :key="m" class="text-sm font-medium text-erro">{{ m }}</li>
          </ul>
        </template>
      </div>

      <!-- Depois desta pergunta -->
      <div v-if="ehPergunta" class="flex flex-col gap-3 border-t border-borda pt-4">
        <h4 class="text-sm font-bold text-texto">Depois desta pergunta</h4>
        <template v-if="antesDaPrincipal">
          <p class="text-sm text-texto-fraco">Perguntas antes da nota principal não podem pular (a nota principal não pode ficar de fora).</p>
          <ul v-if="errosPular.length" class="flex flex-col gap-0.5">
            <li v-for="m in errosPular" :key="m" class="text-sm font-medium text-erro">{{ m }}</li>
          </ul>
          <!-- Regras que ficaram aqui (ex.: a pergunta foi movida para antes da nota): dá para tirar -->
          <RegrasPular v-if="qtdRegras" :item="item" :indice="indice" />
        </template>
        <template v-else>
          <ul v-if="errosPular.length" class="flex flex-col gap-0.5">
            <li v-for="m in errosPular" :key="m" class="text-sm font-medium text-erro">{{ m }}</li>
          </ul>
          <RegrasPular :item="item" :indice="indice" />
        </template>
      </div>
    </div>
  </section>
</template>
