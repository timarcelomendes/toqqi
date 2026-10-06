<script setup lang="ts">
// Estrutura do formulário (coluna da esquerda, docs/api-etapa-5l.md §5.3): cada item com alça de arrastar, ícone do
// tipo e número (P1, P2… só perguntas), título com as citações como "[resposta de P2]", marcas (obrigatória, lógica,
// problema) e o menu "Mais ações" (duplicar, "Mover para…", excluir); a quebra de página vira a divisória "Página 2";
// depois, os finais. O ícone do tipo é a alça: arrastar com mouse e toque (SortableJS, carregado só no editor); pelo
// teclado, Alt+↑/↓ na linha.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type Sortable from 'sortablejs'
import { ArrowDown, ArrowUp, ArrowUpDown, Copy, Flag, GitBranch, GripVertical, MoreHorizontal, Plus, Trash2, TriangleAlert } from 'lucide-vue-next'
import type { Pergunta } from '@/api/tipos'
import { indicePrincipal } from '@/pesquisa/logica'
import { FOCO_FINAL_PADRAO } from '@/pesquisa/tipos'
import { renderizarVariaveis } from '@/pesquisa/variaveis'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Botao from '@/components/ui/Botao.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import { cortar, descreverGrupo, descreverMostrarSe, descreverRegra, numerosDasPerguntas, textoComCitacoes, textoSemTags, temLogica } from '../logicaEditor'
import { INFO_TIPO } from '../tiposPergunta'
import { usarEditor } from './documento'
import { tecla } from './textos'

const props = defineProps<{ podeEditar: boolean; nomeEmpresa: string }>()
const emit = defineEmits<{
  selecionar: [id: string]
  adicionar: [posicao?: number]
  duplicar: [id: string]
  excluir: [id: string]
  mover: [de: number, para: number]
  moverPorId: [id: string, delta: number]
  moverPara: [id: string]
  adicionarFinal: []
  duplicarFinal: [id: string]
  excluirFinal: [id: string]
  moverFinal: [de: number, para: number]
}>()

const editor = usarEditor()
const lista = ref<HTMLElement | null>(null)
const listaFinais = ref<HTMLElement | null>(null)
let sortables: Sortable[] = []

const itens = computed(() => editor.doc.perguntas)
const finais = computed(() => editor.doc.finais)
const numeros = computed(() => numerosDasPerguntas(itens.value))
const ip = computed(() => indicePrincipal(itens.value))
const selecionado = computed(() => editor.selecionado.value)

/** Ids com problema (ponto vermelho): só erros, não avisos. */
const comProblema = computed(() => new Set(editor.erros.value.flatMap((p) => ('id' in p.alvo ? [p.alvo.id] : []))))
const comAviso = computed(() => new Set(editor.problemas.value.filter((p) => p.aviso).flatMap((p) => ('id' in p.alvo ? [p.alvo.id] : []))))

/** O número da página que começa em cada quebra ("Página 2", "Página 3"…). */
const paginaDaQuebra = computed(() => {
  const mapa = new Map<string, number>()
  let n = 1
  for (const p of itens.value) if (p.tipo === 'quebra_pagina') mapa.set(p.id, ++n)
  return mapa
})

function titulo(p: Pergunta): string {
  if (p.tipo === 'conteudo') return cortar(p.titulo?.trim() || textoComCitacoes(textoSemTags(p.html), numeros.value), 80) || 'Bloco de conteúdo vazio'
  const t = renderizarVariaveis(textoComCitacoes(p.titulo, numeros.value), { empresa: props.nomeEmpresa, nome: 'Maria' })
  return t || 'Pergunta sem título'
}

/** A dica do ícone de lógica: as regras em frases. */
function dicaLogica(p: Pergunta): string {
  const partes: string[] = []
  const mostrar = descreverMostrarSe(p.logica?.mostrar_se, itens.value)
  if (mostrar) partes.push(mostrar)
  for (const r of p.logica?.pular ?? []) partes.push(descreverRegra(r, itens.value))
  return partes.join('\n')
}

/** Finais que nunca aparecem: depois de um final sem condição. */
const inalcancaveis = computed(() => {
  const saida = new Set<string>()
  let semCondicao = false
  for (const f of finais.value) {
    if (semCondicao) saida.add(f.id)
    if (!f.mostrar_se?.condicoes?.length) semCondicao = true
  }
  return saida
})

function teclasDaLinha(e: KeyboardEvent, id: string, i: number) {
  if (!props.podeEditar) return
  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    e.preventDefault()
    e.stopPropagation()
    emit('moverPorId', id, e.key === 'ArrowUp' ? -1 : 1)
  } else if (e.key === 'Delete' && !e.altKey && !e.ctrlKey && !e.metaKey) {
    e.preventDefault()
    emit('excluir', id)
  } else if (!e.altKey && !e.ctrlKey && !e.metaKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    // Setas andam entre as linhas (sem selecionar).
    e.preventDefault()
    const linhas = [...(lista.value?.querySelectorAll<HTMLElement>('[data-linha]') ?? [])]
    linhas[Math.max(0, Math.min(linhas.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))]?.focus()
  }
}

function teclasDoFinal(e: KeyboardEvent, i: number) {
  if (!props.podeEditar) return
  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    e.preventDefault()
    e.stopPropagation()
    const id = finais.value[i]!.id
    emit('moverFinal', i, i + (e.key === 'ArrowUp' ? -1 : 1))
    void nextTick(() => focarLinha(id))
  } else if (e.key === 'Delete' && !e.altKey && !e.ctrlKey && !e.metaKey) {
    e.preventDefault()
    emit('excluirFinal', finais.value[i]!.id)
  }
}

/** Leva o foco à linha do item (depois de mover ou excluir). */
function focarLinha(id: string) {
  const raiz = lista.value?.closest('[data-estrutura]')
  raiz?.querySelector<HTMLElement>(`[data-item="${id}"] [data-linha], [data-final="${id}"] [data-linha]`)?.focus()
}

// ── Arrastar (SortableJS) ──
// O SortableJS mexe no DOM; o Vue precisa continuar dono da ordem: no fim do arraste, o elemento volta para onde
// estava e a lista do documento muda (o Vue redesenha na ordem nova).
function desfazerNoDom(evt: Sortable.SortableEvent) {
  const { from, item, oldIndex } = evt
  if (oldIndex === undefined) return
  from.removeChild(item)
  // Depois do irmão anterior (e não "antes do próximo"): o último item volta para antes da âncora de texto que o Vue
  // usa no fim da lista; senão, o próximo item adicionado entraria antes dele.
  const referencia = oldIndex === 0 ? (from.children[0] ?? null) : (from.children[oldIndex - 1]?.nextSibling ?? null)
  from.insertBefore(item, referencia)
}

async function ligarArraste() {
  if (!props.podeEditar) return
  const { default: Sortable } = await import('sortablejs')
  const opcoes = {
    handle: '[data-alca]',
    animation: 150,
    // Toque: segura um instante antes de arrastar (a rolagem da lista continua natural).
    delay: 120,
    delayOnTouchOnly: true,
    ghostClass: 'opacity-40',
    chosenClass: 'ring-2',
    forceFallback: false,
  }
  if (lista.value) {
    sortables.push(
      Sortable.create(lista.value, {
        ...opcoes,
        draggable: '[data-item]',
        onEnd: (evt) => {
          const { oldDraggableIndex: de, newDraggableIndex: para } = evt
          desfazerNoDom(evt)
          if (de !== undefined && para !== undefined && de !== para) emit('mover', de, para)
        },
      }),
    )
  }
  if (listaFinais.value) {
    sortables.push(
      Sortable.create(listaFinais.value, {
        ...opcoes,
        draggable: '[data-final]',
        onEnd: (evt) => {
          const { oldDraggableIndex: de, newDraggableIndex: para } = evt
          desfazerNoDom(evt)
          if (de !== undefined && para !== undefined && de !== para) emit('moverFinal', de, para)
        },
      }),
    )
  }
}

function desligarArraste() {
  for (const s of sortables) s.destroy()
  sortables = []
}

onMounted(() => void ligarArraste())
onBeforeUnmount(desligarArraste)
// A lista de finais aparece e some (sem finais não há <ol>): religa quando ela muda de existência.
watch(
  () => finais.value.length > 0,
  async () => {
    desligarArraste()
    await nextTick()
    await ligarArraste()
  },
)

const rotuloItem = (p: Pergunta) => (p.tipo === 'conteudo' ? 'Conteúdo' : INFO_TIPO[p.tipo]?.rotulo ?? p.tipo)

defineExpose({ focarLinha })
</script>

<template>
  <div class="flex flex-col gap-4" data-estrutura>
    <!-- Itens -->
    <div class="cartao p-2">
      <div class="flex items-center justify-between gap-2 px-2 pb-1.5 pt-1">
        <h2 class="text-xs font-bold uppercase tracking-wide text-texto-fraco">Perguntas e conteúdo</h2>
        <span class="text-xs tabular-nums text-texto-fraco">{{ numeros.size }} {{ numeros.size === 1 ? 'pergunta' : 'perguntas' }}</span>
      </div>
      <p v-if="!itens.length" class="px-2 py-6 text-center text-sm text-texto-fraco">Nenhum item ainda. Comece por uma nota NPS ou CSAT.</p>
      <ol ref="lista" class="flex flex-col" aria-label="Itens do formulário">
        <li
          v-for="(p, i) in itens"
          :key="p.id"
          :data-item="p.id"
          :data-tipo="p.tipo"
          class="group relative"
        >
          <!-- Quebra de página: a divisória "Página N" -->
          <div
            v-if="p.tipo === 'quebra_pagina'"
            class="flex items-center gap-1 rounded-lg py-1 pl-1 pr-1.5"
            :class="selecionado === p.id ? 'bg-marca-suave' : 'hover:bg-superficie-2/70'"
          >
            <span v-if="podeEditar" data-alca class="flex size-7 shrink-0 cursor-grab touch-none items-center justify-center rounded-md text-texto-fraco hover:bg-superficie-2 active:cursor-grabbing" title="Arraste para mudar a ordem" aria-hidden="true">
              <GripVertical class="size-4" />
            </span>
            <button
              type="button"
              data-linha
              class="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1 py-1 text-left text-xs font-bold uppercase tracking-wide text-texto-fraco focus-visible:outline-2 focus-visible:outline-foco"
              :aria-current="selecionado === p.id ? 'true' : undefined"
              @click="emit('selecionar', p.id)"
              @keydown="teclasDaLinha($event, p.id, i)"
            >
              <span class="h-px flex-1 bg-borda-forte" aria-hidden="true" />
              <span>Página {{ paginaDaQuebra.get(p.id) }}</span>
              <span class="h-px flex-1 bg-borda-forte" aria-hidden="true" />
            </button>
            <button
              v-if="podeEditar"
              type="button"
              class="flex size-7 items-center justify-center rounded-md text-texto-fraco hover:bg-erro-suave hover:text-erro group-hover:visible group-focus-within:visible"
              :class="selecionado === p.id ? 'visible' : 'invisible'"
              :aria-label="`Excluir a quebra da página ${paginaDaQuebra.get(p.id)}`"
              data-acao="excluir"
              @click="emit('excluir', p.id)"
            >
              <Trash2 class="size-3.5" aria-hidden="true" />
            </button>
          </div>

          <!-- Pergunta ou conteúdo -->
          <div
            v-else
            class="flex items-start gap-1 rounded-xl py-1 pl-1 pr-1 transition-colors"
            :class="selecionado === p.id ? 'bg-marca-suave ring-1 ring-marca/40' : 'hover:bg-superficie-2/70'"
          >
            <!-- O ícone do tipo é a alça de arrastar (vira a "pegada" ao passar o mouse) -->
            <span
              v-if="podeEditar"
              data-alca
              class="mt-1 flex size-7 shrink-0 cursor-grab touch-none items-center justify-center rounded-md bg-superficie-2 text-texto-suave hover:bg-borda active:cursor-grabbing"
              :class="p.tipo === 'conteudo' ? 'text-info' : ''"
              title="Arraste para mudar a ordem"
              aria-hidden="true"
              @click="emit('selecionar', p.id)"
            >
              <component :is="INFO_TIPO[p.tipo]?.icone" class="size-3.5 group-hover:hidden" />
              <GripVertical class="hidden size-4 group-hover:block" />
            </span>
            <span v-else class="mt-1 flex size-7 shrink-0 items-center justify-center rounded-md bg-superficie-2 text-texto-suave" :class="p.tipo === 'conteudo' ? 'text-info' : ''" aria-hidden="true">
              <component :is="INFO_TIPO[p.tipo]?.icone" class="size-3.5" />
            </span>
            <button
              type="button"
              data-linha
              class="flex min-w-0 flex-1 items-start gap-2 rounded-lg px-1 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-foco"
              :aria-current="selecionado === p.id ? 'true' : undefined"
              :aria-describedby="`estrutura-${p.id}-marcas`"
              @click="emit('selecionar', p.id)"
              @keydown="teclasDaLinha($event, p.id, i)"
            >
              <span class="min-w-0 flex-1">
                <span class="flex items-baseline gap-1.5">
                  <span class="sr-only">{{ rotuloItem(p) }}:</span>
                  <span v-if="numeros.get(p.id)" class="shrink-0 text-xs font-bold tabular-nums text-texto-fraco" data-numero>P{{ numeros.get(p.id) }}</span>
                  <span v-else class="shrink-0 text-xs font-bold text-info" aria-hidden="true">{{ rotuloItem(p) }}</span>
                  <span class="line-clamp-2 text-sm font-medium leading-snug text-texto" data-titulo-linha>{{ titulo(p) }}</span>
                </span>
              </span>
              <span :id="`estrutura-${p.id}-marcas`" class="mt-0.5 flex shrink-0 items-center gap-1">
                <span v-if="i === ip" class="sr-only">Nota principal.</span>
                <span v-if="p.obrigatoria && p.tipo !== 'conteudo'" class="text-sm font-bold text-erro" title="Obrigatória" aria-hidden="true">*</span>
                <span v-if="p.obrigatoria && p.tipo !== 'conteudo'" class="sr-only">Obrigatória.</span>
                <span v-if="temLogica(p)" class="flex text-info" :title="dicaLogica(p)" data-marca-logica>
                  <GitBranch class="size-3.5" aria-hidden="true" />
                  <span class="sr-only">Com lógica: {{ dicaLogica(p) }}.</span>
                </span>
                <span v-if="comProblema.has(p.id)" class="size-2 rounded-full bg-erro" title="Precisa de ajuste" data-marca-problema>
                  <span class="sr-only">Precisa de ajuste.</span>
                </span>
                <span v-else-if="comAviso.has(p.id)" class="size-2 rounded-full bg-atencao" title="Tem um aviso">
                  <span class="sr-only">Tem um aviso.</span>
                </span>
              </span>
            </button>
            <!-- Mais ações: aparece ao passar o mouse, com o foco na linha ou no item selecionado (escondido, não ocupa clique) -->
            <MenuSuspenso
              v-if="podeEditar"
              :rotulo="`Mais ações: ${titulo(p)}`"
              fixo
              class="mt-1 shrink-0 group-hover:visible group-focus-within:visible"
              :class="selecionado === p.id ? 'visible' : 'invisible'"
            >
              <template #gatilho="{ props: gatilho }">
                <button v-bind="gatilho" type="button" class="flex size-7 items-center justify-center rounded-md text-texto-fraco hover:bg-superficie-2 hover:text-texto" :title="`Mais ações`" data-mais-acoes>
                  <MoreHorizontal class="size-4" aria-hidden="true" />
                </button>
              </template>
              <ItemMenu :icone="Copy" data-acao="duplicar" @click="emit('duplicar', p.id)">
                <span class="flex-1">Duplicar</span><kbd class="text-xs font-normal text-texto-fraco">{{ tecla('Ctrl+D') }}</kbd>
              </ItemMenu>
              <ItemMenu :icone="ArrowUpDown" data-acao="mover-para" @click="emit('moverPara', p.id)">
                <span class="flex-1">Mover para…</span><kbd class="text-xs font-normal text-texto-fraco">{{ tecla('Alt+↑/↓') }}</kbd>
              </ItemMenu>
              <ItemMenu :icone="Trash2" perigo data-acao="excluir" @click="emit('excluir', p.id)">
                <span class="flex-1">Excluir</span><kbd class="text-xs font-normal opacity-70">Delete</kbd>
              </ItemMenu>
            </MenuSuspenso>
          </div>
          <!-- "+" entre dois itens -->
          <button
            v-if="podeEditar && i < itens.length - 1"
            type="button"
            class="invisible absolute -bottom-2.5 left-1/2 z-10 flex size-5 -translate-x-1/2 items-center justify-center rounded-full border border-borda-forte bg-superficie text-texto-suave shadow-sm hover:border-marca hover:text-marca-texto group-hover:visible group-focus-within:visible"
            :aria-label="`Adicionar item depois de ${titulo(p)}`"
            data-inserir-entre
            @click="emit('adicionar', i + 1)"
          >
            <Plus class="size-3" aria-hidden="true" />
          </button>
        </li>
      </ol>
      <div v-if="podeEditar" class="px-1 pb-1 pt-2">
        <Botao variante="secundario" tamanho="sm" bloco data-adicionar :title="`Adicionar (/)`" @click="emit('adicionar')">
          <Plus class="size-4" aria-hidden="true" /> Adicionar
        </Botao>
      </div>
    </div>

    <!-- Finais -->
    <section class="cartao p-2" aria-labelledby="titulo-finais" data-secao-finais>
      <div class="flex items-center justify-between gap-2 px-2 pb-1.5 pt-1">
        <h2 id="titulo-finais" class="text-xs font-bold uppercase tracking-wide text-texto-fraco">Finais</h2>
        <span class="text-xs text-texto-fraco">vale o primeiro que combinar</span>
      </div>
      <ol v-if="finais.length" ref="listaFinais" class="flex flex-col" aria-label="Finais por condição">
        <li v-for="(f, j) in finais" :key="f.id" :data-final="f.id" class="group">
          <div class="flex items-start gap-1 rounded-xl py-1 pl-1 pr-1" :class="selecionado === f.id ? 'bg-marca-suave ring-1 ring-marca/40' : 'hover:bg-superficie-2/70'">
            <span
              v-if="podeEditar"
              data-alca
              class="mt-1 flex size-7 shrink-0 cursor-grab touch-none items-center justify-center rounded-md bg-superficie-2 text-texto-suave hover:bg-borda active:cursor-grabbing"
              title="Arraste para mudar a ordem"
              aria-hidden="true"
              @click="emit('selecionar', f.id)"
            >
              <Flag class="size-3.5 group-hover:hidden" />
              <GripVertical class="hidden size-4 group-hover:block" />
            </span>
            <span v-else class="mt-1 flex size-7 shrink-0 items-center justify-center rounded-md bg-superficie-2 text-texto-suave" aria-hidden="true"><Flag class="size-3.5" /></span>
            <button
              type="button"
              data-linha
              class="flex min-w-0 flex-1 items-start gap-2 rounded-lg px-1 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-foco"
              :aria-current="selecionado === f.id ? 'true' : undefined"
              @click="emit('selecionar', f.id)"
              @keydown="teclasDoFinal($event, j)"
            >
              <span class="min-w-0 flex-1">
                <span class="line-clamp-1 text-sm font-medium text-texto">{{ f.nome || 'Final sem nome' }}</span>
                <span class="line-clamp-2 text-xs text-texto-fraco" data-condicao-final>{{ f.mostrar_se?.condicoes?.length ? `Quando ${descreverGrupo(f.mostrar_se, itens)}` : 'Sempre (pega o resto)' }}</span>
                <span v-if="inalcancaveis.has(f.id)" class="mt-0.5 inline-flex items-center gap-1 text-xs font-semibold text-atencao"><TriangleAlert class="size-3" aria-hidden="true" /> Nunca aparece</span>
              </span>
              <span v-if="comProblema.has(f.id)" class="mt-1.5 size-2 shrink-0 rounded-full bg-erro" title="Precisa de ajuste" data-marca-problema><span class="sr-only">Precisa de ajuste.</span></span>
            </button>
            <MenuSuspenso
              v-if="podeEditar"
              :rotulo="`Mais ações: final ${f.nome}`"
              fixo
              class="mt-1 shrink-0 group-hover:visible group-focus-within:visible"
              :class="selecionado === f.id ? 'visible' : 'invisible'"
            >
              <template #gatilho="{ props: gatilho }">
                <button v-bind="gatilho" type="button" class="flex size-7 items-center justify-center rounded-md text-texto-fraco hover:bg-superficie-2 hover:text-texto" title="Mais ações" data-mais-acoes>
                  <MoreHorizontal class="size-4" aria-hidden="true" />
                </button>
              </template>
              <ItemMenu v-if="j > 0" :icone="ArrowUp" data-acao="subir" @click="emit('moverFinal', j, j - 1)">Subir</ItemMenu>
              <ItemMenu v-if="j < finais.length - 1" :icone="ArrowDown" data-acao="descer" @click="emit('moverFinal', j, j + 1)">Descer</ItemMenu>
              <ItemMenu :icone="Copy" data-acao="duplicar" @click="emit('duplicarFinal', f.id)">Duplicar</ItemMenu>
              <ItemMenu :icone="Trash2" perigo data-acao="excluir" @click="emit('excluirFinal', f.id)">Excluir</ItemMenu>
            </MenuSuspenso>
          </div>
        </li>
      </ol>
      <!-- Final padrão: sempre existe; vale quando nenhum outro vale -->
      <div class="flex items-start gap-1 rounded-xl py-1 pl-1 pr-1" :class="selecionado === FOCO_FINAL_PADRAO ? 'bg-marca-suave ring-1 ring-marca/40' : 'hover:bg-superficie-2/70'" data-final-padrao>
        <span class="mt-1 flex size-7 shrink-0 items-center justify-center rounded-md bg-superficie-2 text-texto-suave" aria-hidden="true"><Flag class="size-3.5" /></span>
        <button
          type="button"
          data-linha
          class="flex min-w-0 flex-1 items-start gap-2 rounded-lg px-1 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-foco"
          :aria-current="selecionado === FOCO_FINAL_PADRAO ? 'true' : undefined"
          @click="emit('selecionar', FOCO_FINAL_PADRAO)"
        >
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-medium text-texto">Final padrão</span>
            <span class="block text-xs text-texto-fraco">{{ finais.length ? 'Quando nenhum outro vale' : 'O agradecimento de sempre' }}</span>
          </span>
          <span v-if="comProblema.has(FOCO_FINAL_PADRAO)" class="mt-1.5 size-2 shrink-0 rounded-full bg-erro" aria-hidden="true" />
        </button>
      </div>
      <div v-if="podeEditar" class="px-1 pb-1 pt-1.5">
        <Botao variante="fantasma" tamanho="sm" bloco :desabilitado="finais.length >= 10" data-adicionar-final @click="emit('adicionarFinal')">
          <Plus class="size-4" aria-hidden="true" /> Adicionar final
        </Botao>
      </div>
    </section>
  </div>
</template>
