<script setup lang="ts">
// Aba "Perguntas" do editor (docs/api-etapa-5l.md §5.3): estrutura à esquerda (~300 px), edição do item ao centro e a
// prévia à direita (~400 px) a partir de 1280 px. De 768 a 1279 px: estrutura e edição, com a prévia num painel
// lateral. Abaixo de 768 px: a lista; tocar num item abre a edição em tela cheia, com "Voltar".
// Aqui ficam as operações nos itens (adicionar, mover, duplicar, excluir) e nos finais; cada uma é um passo do desfazer.
import { computed, nextTick, ref, watch } from 'vue'
import { ChevronLeft, Eye, X } from 'lucide-vue-next'
import type { Final, Id } from '@/api/tipos'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useMidia } from '@/composables/midia'
import { respondivel, tipoPrincipal } from '@/pesquisa/logica'
import { FOCO_FINAL_PADRAO } from '@/pesquisa/tipos'
import Botao from '@/components/ui/Botao.vue'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import { cortar, descreverGrupo, MAX_FINAIS, nomeDoItem, numerosDasPerguntas, quemUsa, removerReferencias } from '../logicaEditor'
import { criarDaOpcao, criarFinal, duplicarPergunta, type OpcaoAdicionar } from '../tiposPergunta'
import { LIMITE_CONTEUDOS, LIMITE_ITENS, LIMITE_PERGUNTAS, type Problema } from '../validacaoFormulario'
import { usarEditor } from './documento'
import EditorItem from './EditorItem.vue'
import Estrutura from './Estrutura.vue'
import MenuAdicionar from './MenuAdicionar.vue'
import ModalMoverPara from './ModalMoverPara.vue'
import PreVisualizacao from './PreVisualizacao.vue'

const props = defineProps<{
  podeEditar: boolean
  nomeEmpresa: string
  formularioId: Id
  prefixoImagens: string | null
  nome: string
}>()

const editor = usarEditor()
const xl = useMidia('(min-width: 1280px)')
const md = useMidia('(min-width: 768px)')
const previaAberta = ref(false)
/** Celular: a edição do item em tela cheia (com "Voltar"). */
const edicaoAberta = ref(false)
const menuAberto = ref(false)
/** Onde o item novo entra (índice); null = depois do selecionado, ou no fim. */
const posicaoMenu = ref<number | null>(null)
const moverAberto = ref(false)
const moverId = ref<string | null>(null)
/** Itens cuja lógica quebrou no último mover: a faixa some sozinha quando todos forem ajustados (ou ao desfazer). */
const quebrados = ref<string[]>([])
const anuncio = ref('')
const estrutura = ref<InstanceType<typeof Estrutura> | null>(null)

const itens = computed(() => editor.doc.perguntas)
const finais = computed(() => editor.doc.finais)
const numeros = computed(() => numerosDasPerguntas(itens.value))
const tipo = computed(() => tipoPrincipal(itens.value))
const selecionadoItem = computed(() => itens.value.find((p) => p.id === editor.selecionado.value) ?? null)
const selecionadoFinal = computed(() => finais.value.find((f) => f.id === editor.selecionado.value) ?? null)

/** O que a prévia mostra: o item (ou final) selecionado, e por que ele aparece. */
const focoPrevia = computed(() => {
  const id = editor.selecionado.value
  if (!id) return null
  if (selecionadoItem.value?.tipo === 'quebra_pagina') return null
  return id
})
const motivoFoco = computed(() => {
  const p = selecionadoItem.value
  if (p) return p.logica?.mostrar_se?.condicoes?.length ? descreverGrupo(p.logica.mostrar_se, itens.value) : 'as respostas anteriores não pulam este item'
  const f = selecionadoFinal.value
  return f?.mostrar_se?.condicoes?.length ? descreverGrupo(f.mostrar_se, itens.value) : null
})

function selecionar(id: string) {
  editor.selecionado.value = id
  if (!md.value) edicaoAberta.value = true
}
watch(md, (v) => {
  if (v) edicaoAberta.value = false
})

function anunciar(t: string) {
  anuncio.value = ''
  void nextTick(() => (anuncio.value = t))
}

// ── adicionar ──

function abrirAdicionar(posicao?: number) {
  if (!props.podeEditar) return
  posicaoMenu.value = posicao ?? null
  menuAberto.value = true
}

const descricaoPosicao = computed(() => {
  const i = posicaoMenu.value
  if (i !== null) {
    const antes = itens.value[i - 1]
    return antes ? `Entra depois de “${cortar(nomeDoItem(antes, numeros.value), 50)}”.` : 'Entra no começo do formulário.'
  }
  const s = selecionadoItem.value
  return s ? `Entra depois de “${cortar(nomeDoItem(s, numeros.value), 50)}”.` : 'Entra no fim do formulário.'
})

function cabeMais(tipoNovo: string): string | null {
  if (itens.value.length >= LIMITE_ITENS) return `Use no máximo ${LIMITE_ITENS} itens (perguntas, blocos de conteúdo e quebras).`
  if (respondivel(tipoNovo) && itens.value.filter((p) => respondivel(p.tipo)).length >= LIMITE_PERGUNTAS) return `Use no máximo ${LIMITE_PERGUNTAS} perguntas.`
  if (tipoNovo === 'conteudo' && itens.value.filter((p) => p.tipo === 'conteudo').length >= LIMITE_CONTEUDOS) return `Use no máximo ${LIMITE_CONTEUDOS} blocos de conteúdo.`
  return null
}

function adicionar(opcao: OpcaoAdicionar) {
  menuAberto.value = false
  const limite = cabeMais(opcao.tipo)
  if (limite) {
    avisar.atencao(limite)
    return
  }
  const novo = criarDaOpcao(opcao, itens.value)
  const doSelecionado = selecionadoItem.value ? itens.value.indexOf(selecionadoItem.value) + 1 : itens.value.length
  const i = Math.min(posicaoMenu.value ?? doSelecionado, itens.value.length)
  editor.mudar(() => editor.doc.perguntas.splice(i, 0, novo))
  selecionar(novo.id)
  anunciar(`${opcao.rotulo} adicionado na posição ${i + 1}.`)
  focarCampo(novo.tipo === 'conteudo' ? 'html' : novo.tipo === 'quebra_pagina' ? null : 'titulo')
}

// ── mover ──

/** Itens (e finais) com problema de lógica: para avisar quando mover quebrar alguma. */
function comProblemaDeLogica(): Set<string> {
  return new Set(
    editor.problemasLocais.value.filter((p) => !p.aviso && 'id' in p.alvo && (p.campo === 'logica' || p.campo === 'mostrar_se')).map((p) => (p.alvo as { id: string }).id),
  )
}

function avisarSeQuebrou(antes: Set<string>) {
  quebrados.value = [...comProblemaDeLogica()].filter((id) => !antes.has(id))
}

const avisoLogica = computed(() => {
  if (!quebrados.value.length) return null
  const atuais = comProblemaDeLogica()
  const n = quebrados.value.filter((id) => atuais.has(id)).length
  return n ? `A lógica de ${n} ${n === 1 ? 'item' : 'itens'} precisa de ajuste` : null
})

function moverItem(de: number, para: number) {
  const n = itens.value.length
  if (de === para || de < 0 || para < 0 || de >= n || para >= n) return
  const antes = comProblemaDeLogica()
  editor.mudar(() => {
    const [item] = editor.doc.perguntas.splice(de, 1)
    editor.doc.perguntas.splice(para, 0, item!)
  })
  anunciar(`Item movido para a posição ${para + 1} de ${n}.`)
  avisarSeQuebrou(antes)
}

function moverPorId(id: string, delta: number) {
  const i = itens.value.findIndex((p) => p.id === id)
  if (i < 0) return
  moverItem(i, i + delta)
  void nextTick(() => estrutura.value?.focarLinha(id))
}

function abrirMoverPara(id: string) {
  moverId.value = id
  moverAberto.value = true
}

function moverPara(id: string, depoisDe: string | null) {
  const de = itens.value.findIndex((p) => p.id === id)
  if (de < 0) return
  // "No começo": posição 0; "depois de X": logo depois de X na lista sem o item movido.
  const semEle = itens.value.filter((p) => p.id !== id)
  const para = depoisDe ? semEle.findIndex((p) => p.id === depoisDe) + 1 : 0
  moverItem(de, para)
  void nextTick(() => estrutura.value?.focarLinha(id))
}

// ── duplicar e excluir ──

function duplicar(id: string) {
  const i = itens.value.findIndex((p) => p.id === id)
  const p = itens.value[i]
  if (!p) return
  const limite = cabeMais(p.tipo)
  if (limite) {
    avisar.atencao(limite)
    return
  }
  const copia = duplicarPergunta(p, itens.value)
  editor.mudar(() => editor.doc.perguntas.splice(i + 1, 0, copia))
  selecionar(copia.id)
  anunciar('Item duplicado. A cópia vem sem as regras de pular.')
}

function juntarNomes(nomes: string[]): string {
  return nomes.length <= 1 ? (nomes[0] ?? '') : `${nomes.slice(0, -1).join(', ')} e ${nomes[nomes.length - 1]}`
}

async function excluir(id: string) {
  const i = itens.value.findIndex((p) => p.id === id)
  const p = itens.value[i]
  if (!p) return
  const nome = nomeDoItem(p, numeros.value, 60)
  if (p.tipo !== 'quebra_pagina') {
    const usos = quemUsa(id, itens.value, finais.value)
    const nomes = [...new Set(usos.map((u) => (u.tipo === 'final' ? `o final “${finais.value.find((f) => f.id === u.id)?.nome ?? ''}”` : `“${nomeDoItem(itens.value.find((x) => x.id === u.id)!, numeros.value, 40)}”`)))]
    const ok = await confirmar(
      usos.length
        ? {
            titulo: 'Excluir este item?',
            mensagem: `“${nome}” é usado na lógica de ${juntarNomes(nomes)}.`,
            complemento: ['As condições e regras que usam este item saem junto. Dá para desfazer.'],
            confirmar: 'Excluir e remover as condições que usam este item',
            perigo: true,
          }
        : {
            titulo: 'Excluir este item?',
            mensagem: `“${nome}” sai do formulário. As respostas antigas continuam guardadas. Dá para desfazer.`,
            confirmar: 'Excluir',
            perigo: true,
          },
    )
    if (!ok) return
  }
  editor.mudar(() => {
    removerReferencias(id, editor.doc.perguntas, editor.doc.finais)
    editor.doc.perguntas.splice(
      editor.doc.perguntas.findIndex((x) => x.id === id),
      1,
    )
  })
  const vizinho = itens.value[i] ?? itens.value[i - 1] ?? null
  editor.selecionado.value = vizinho?.id ?? null
  if (!md.value) edicaoAberta.value = false
  anunciar('Item excluído.')
  if (vizinho) void nextTick(() => estrutura.value?.focarLinha(vizinho.id))
}

// ── finais ──

function adicionarFinal() {
  if (finais.value.length >= MAX_FINAIS) {
    avisar.atencao(`Use no máximo ${MAX_FINAIS} finais.`)
    return
  }
  const novo = criarFinal(finais.value)
  editor.mudar(() => editor.doc.finais.push(novo))
  selecionar(novo.id)
  anunciar('Final adicionado.')
  focarCampo('nome')
}

function moverFinal(de: number, para: number) {
  const n = finais.value.length
  if (de === para || de < 0 || para < 0 || de >= n || para >= n) return
  editor.mudar(() => {
    const [f] = editor.doc.finais.splice(de, 1)
    editor.doc.finais.splice(para, 0, f!)
  })
  anunciar(`Final movido para a posição ${para + 1} de ${n}.`)
}

async function excluirFinal(id: string) {
  const f = finais.value.find((x) => x.id === id)
  if (!f) return
  const ok = await confirmar({ titulo: 'Excluir este final?', mensagem: `O final “${f.nome}” sai do formulário. Dá para desfazer.`, confirmar: 'Excluir', perigo: true })
  if (!ok) return
  const i = finais.value.indexOf(f)
  editor.mudar(() => editor.doc.finais.splice(i, 1))
  editor.selecionado.value = (finais.value[i] ?? finais.value[i - 1])?.id ?? FOCO_FINAL_PADRAO
  anunciar('Final excluído.')
}

function duplicarFinal(id: string) {
  const f = finais.value.find((x) => x.id === id)
  if (!f) return
  if (finais.value.length >= MAX_FINAIS) {
    avisar.atencao(`Use no máximo ${MAX_FINAIS} finais.`)
    return
  }
  const { id: _original, ...resto } = JSON.parse(JSON.stringify(f)) as Final
  const copia: Final = criarFinal(finais.value, { ...resto, nome: `${f.nome} (cópia)`.slice(0, 60) })
  editor.mudar(() => editor.doc.finais.splice(finais.value.indexOf(f) + 1, 0, copia))
  selecionar(copia.id)
}

// ── foco num campo (item novo, painel de problemas) ──

async function focarCampo(campo: string | null, logica: Problema['logica'] | null = null) {
  const id = editor.selecionado.value
  if (!id) return
  editor.pedirFoco(id, campo, logica)
  if (!md.value) edicaoAberta.value = true
  // A edição pode montar partes assíncronas (o editor de texto): espera um pouco antes de procurar o campo.
  for (let tentativa = 0; tentativa < 10; tentativa++) {
    await nextTick()
    const painel = document.querySelector<HTMLElement>('[data-painel-edicao]')
    if (!painel) return
    const alvo = buscarCampo(painel, campo, logica)
    if (alvo) {
      alvo.focus()
      if ('select' in alvo && campo === 'titulo' && typeof (alvo as HTMLInputElement).select === 'function') (alvo as HTMLInputElement).select()
      alvo.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
      return
    }
    await new Promise((r) => setTimeout(r, 30))
  }
}

function buscarCampo(painel: HTMLElement, campo: string | null, logica: Problema['logica'] | null): HTMLElement | null {
  const focavel = (el: Element | null) =>
    (el?.matches?.('input, textarea, select, button, [contenteditable="true"]') ? el : el?.querySelector('input, textarea, select, [contenteditable="true"], button')) as HTMLElement | null
  if (!campo) return painel.querySelector<HTMLElement>('[data-titulo-edicao]')
  if (campo === 'logica' || campo === 'mostrar_se') {
    const onde = logica?.onde ?? 'mostrar_se'
    const bloco = onde === 'pular' && logica?.regra ? painel.querySelector(`[data-regra="${logica.regra}"]`) : painel.querySelector(`[data-logica-onde="${onde}"]`)
    const linha = logica?.condicao ? bloco?.querySelector(`[data-condicao="${logica.condicao}"]`) : null
    return focavel(linha ?? bloco ?? painel.querySelector('[data-secao-logica]'))
  }
  const base = campo.split('.')[0]!
  return focavel(painel.querySelector(`[data-campo="${campo}"]`) ?? painel.querySelector(`[data-campo="${base}"]`))
}

// ── atalhos (a tela chama) ──

function duplicarSelecionado() {
  const id = editor.selecionado.value
  if (!id || !props.podeEditar) return
  if (selecionadoItem.value) duplicar(id)
  else if (selecionadoFinal.value) duplicarFinal(id)
}

function moverSelecionado(delta: number) {
  const id = editor.selecionado.value
  if (!id || !props.podeEditar) return
  if (selecionadoItem.value) moverPorId(id, delta)
  else if (selecionadoFinal.value) {
    const i = finais.value.indexOf(selecionadoFinal.value)
    moverFinal(i, i + delta)
  }
}

function verProblemas() {
  quebrados.value = []
  editor.painelProblemas.value = true
}

defineExpose({ abrirAdicionar, duplicarSelecionado, moverSelecionado, focarCampo })
</script>

<template>
  <div data-aba-perguntas>
    <!-- Abaixo de 1280 px a prévia abre por botão; no celular, "Voltar" sai da edição -->
    <div class="mb-3 flex items-center gap-2 xl:hidden">
      <button
        v-if="!md && edicaoAberta"
        type="button"
        class="inline-flex h-10 items-center gap-1 rounded-xl px-2 text-sm font-semibold text-texto-suave hover:bg-superficie-2 hover:text-texto"
        data-voltar-lista
        @click="edicaoAberta = false"
      >
        <ChevronLeft class="size-4" aria-hidden="true" /> Voltar
      </button>
      <Botao variante="secundario" tamanho="sm" class="ml-auto" data-abrir-previa @click="previaAberta = true"><Eye class="size-4" aria-hidden="true" /> Prévia</Botao>
    </div>

    <div v-if="avisoLogica" class="mb-3 flex items-center gap-3 rounded-xl border border-atencao/30 bg-atencao-suave px-3.5 py-2.5 text-sm" role="status" data-aviso-logica>
      <p class="flex-1 font-medium text-texto">{{ avisoLogica }}.</p>
      <button type="button" class="link" @click="verProblemas">Ver</button>
      <button type="button" class="flex size-8 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2" aria-label="Fechar aviso" @click="quebrados = []">
        <X class="size-4" aria-hidden="true" />
      </button>
    </div>

    <div class="grid items-start gap-5 md:grid-cols-[16rem_minmax(0,1fr)] lg:grid-cols-[18rem_minmax(0,1fr)] xl:grid-cols-[18.75rem_minmax(0,1fr)_25rem]">
      <nav
        aria-label="Estrutura do formulário"
        class="min-w-0 md:sticky md:top-20 md:max-h-[calc(100dvh-6.5rem)] md:overflow-y-auto md:overscroll-contain md:pr-1"
        :class="!md && edicaoAberta ? 'hidden' : ''"
        data-coluna-estrutura
      >
        <Estrutura
          ref="estrutura"
          :pode-editar="podeEditar"
          :nome-empresa="nomeEmpresa"
          @selecionar="selecionar"
          @adicionar="abrirAdicionar"
          @duplicar="duplicar"
          @excluir="excluir"
          @mover="moverItem"
          @mover-por-id="moverPorId"
          @mover-para="abrirMoverPara"
          @adicionar-final="adicionarFinal"
          @duplicar-final="duplicarFinal"
          @excluir-final="excluirFinal"
          @mover-final="moverFinal"
        />
      </nav>

      <section aria-label="Edição do item" class="min-w-0" :class="!md && !edicaoAberta ? 'hidden' : ''" data-painel-edicao>
        <EditorItem
          :pode-editar="podeEditar"
          :nome-empresa="nomeEmpresa"
          :formulario-id="formularioId"
          :prefixo-imagens="prefixoImagens"
          @adicionar="abrirAdicionar()"
          @duplicar="duplicarSelecionado"
          @excluir="(id: string) => (selecionadoFinal ? excluirFinal(id) : excluir(id))"
          @selecionar="selecionar"
        />
      </section>

      <aside v-if="xl" class="sticky top-20 h-[calc(100dvh-9.5rem)] min-w-0" aria-label="Prévia" data-coluna-previa>
        <PreVisualizacao
          :nome="nome"
          :perguntas="editor.doc.perguntas"
          :tema="editor.doc.tema"
          :finais="editor.doc.finais"
          :nome-empresa="nomeEmpresa"
          :tipo="tipo"
          :prefixo-imagens="prefixoImagens"
          :foco-id="focoPrevia"
          :motivo-foco="motivoFoco"
        />
      </aside>
    </div>

    <MenuAdicionar v-model:aberto="menuAberto" :descricao="descricaoPosicao" @escolher="adicionar" />
    <ModalMoverPara v-model:aberto="moverAberto" :item-id="moverId" @mover="moverPara" />

    <PainelLateral v-if="!xl" v-model:aberto="previaAberta" titulo="Prévia" descricao="É assim que seu cliente vê. Nada é gravado." largura="lg">
      <div class="-mx-4 -my-5 h-[calc(100dvh-7rem)] sm:-mx-6">
        <PreVisualizacao
          :nome="nome"
          :perguntas="editor.doc.perguntas"
          :tema="editor.doc.tema"
          :finais="editor.doc.finais"
          :nome-empresa="nomeEmpresa"
          :tipo="tipo"
          :prefixo-imagens="prefixoImagens"
          :foco-id="focoPrevia"
          :motivo-foco="motivoFoco"
          :titulo="false"
        />
      </div>
    </PainelLateral>
    <p class="sr-only" aria-live="polite">{{ anuncio }}</p>
  </div>
</template>
