<script setup lang="ts">
// Edição de uma pergunta (docs/api-etapa-5l.md §5.3): título e descrição com "Inserir" (variáveis e respostas
// anteriores), as configurações do tipo, "Obrigatória" e a seção "Lógica". Trocar o tipo pelo menu "Tipo" mantém
// título, descrição e lógica, e avisa quando condições deixam de valer. Renomear ou excluir uma opção atualiza as
// condições que usam a opção.
import { computed } from 'vue'
import { ChevronDown, Info } from 'lucide-vue-next'
import type { ExibicaoEscolha, FormatoTexto, Pergunta } from '@/api/tipos'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { indicePrincipal, respondivel } from '@/pesquisa/logica'
import ItemMenu from '@/components/app/ItemMenu.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import Selecao from '@/components/ui/Selecao.vue'
import { condicoesQueDeixamDeValer, numerosDasPerguntas, removerOpcao, renomearOpcao, usosDaOpcao } from '../logicaEditor'
import { INFO_TIPO, OPCOES_ADICIONAR, type OpcaoAdicionar } from '../tiposPergunta'
import { usarEditor } from './documento'
import CabecalhoEdicao from './CabecalhoEdicao.vue'
import CampoVariaveis from './CampoVariaveis.vue'
import EditorOpcoes from './EditorOpcoes.vue'
import ProblemasDoItem from './ProblemasDoItem.vue'
import SecaoLogica from './SecaoLogica.vue'

const props = defineProps<{ item: Pergunta; indice: number; podeEditar: boolean; nomeEmpresa: string }>()
const emit = defineEmits<{ duplicar: []; excluir: [] }>()
const editor = usarEditor()

const p = computed(() => props.item)
const itens = computed(() => editor.doc.perguntas)
const numeros = computed(() => numerosDasPerguntas(itens.value))
const ehPrincipal = computed(() => indicePrincipal(itens.value) === props.indice)
/** As perguntas antes deste item (as que dá para citar). */
const anteriores = computed(() => itens.value.slice(0, props.indice).filter((x) => respondivel(x.tipo)))
const problemas = computed(() => editor.problemas.value.filter((x) => 'id' in x.alvo && x.alvo.id === p.value.id))
const erro = (campo: string) => problemas.value.find((x) => x.campo === campo && !x.aviso)?.mensagem ?? null
const aviso = (campo: string) => problemas.value.find((x) => x.campo === campo && x.aviso)?.mensagem ?? null

const rotulo = computed(() => {
  const n = numeros.value.get(p.value.id)
  const tipo = opcaoAtual.value?.rotulo ?? INFO_TIPO[p.value.tipo]?.rotulo ?? p.value.tipo
  return n ? `P${n} · ${tipo}` : tipo
})
/** A opção do menu que corresponde a este tipo (e formato, na resposta curta). */
const opcaoAtual = computed(() =>
  OPCOES_ADICIONAR.find((o) => o.tipo === p.value.tipo && (o.tipo !== 'texto_curto' || (o.criar().formato ?? 'texto') === (p.value.formato ?? 'texto'))),
)
const TIPOS = OPCOES_ADICIONAR.filter((o) => respondivel(o.tipo))

const FORMATOS: { valor: FormatoTexto; rotulo: string }[] = [
  { valor: 'texto', rotulo: 'Texto livre' },
  { valor: 'email', rotulo: 'E-mail' },
  { valor: 'telefone', rotulo: 'Telefone' },
  { valor: 'numero', rotulo: 'Número' },
]
const MAXIMOS = computed(() => {
  const min = p.value.min ?? 1
  return Array.from({ length: 10 - (min + 2) + 1 }, (_, i) => ({ valor: min + 2 + i, rotulo: String(min + 2 + i) }))
})
const maximosSelecao = computed(() => {
  const n = (p.value.opcoes ?? []).length
  return Array.from({ length: Math.max(0, n - 1) }, (_, i) => ({ valor: i + 2, rotulo: `Até ${i + 2}` }))
})

function mudarMin(v: number | '') {
  p.value.min = Number(v)
  if ((p.value.max ?? 5) <= p.value.min + 1) p.value.max = p.value.min + 2
}

// ── opções ──
const opcoes = computed({
  get: () => p.value.opcoes ?? [],
  set: (v: string[]) => {
    p.value.opcoes = v
    // O máximo de opções não passa do número de opções.
    if (typeof p.value.max_selecoes === 'number' && p.value.max_selecoes > Math.max(v.length, 2)) p.value.max_selecoes = Math.max(v.length, 2)
  },
})
function aoRenomear(antiga: string, nova: string) {
  if (antiga.trim()) renomearOpcao(p.value.id, antiga, nova, editor.doc.perguntas, editor.doc.finais)
}
async function antesDeRemover(opcao: string): Promise<boolean> {
  const n = usosDaOpcao(p.value.id, opcao, editor.doc.perguntas, editor.doc.finais)
  if (!n) return true
  return confirmar({
    titulo: 'Excluir esta opção?',
    mensagem: `A opção “${opcao}” é usada em ${n === 1 ? '1 condição' : `${n} condições`}. Ela sai dessas condições, e a condição que ficar sem nenhuma opção sai também.`,
    confirmar: 'Excluir a opção',
    perigo: true,
  })
}
function aoRemover(opcao: string) {
  if (opcao.trim()) removerOpcao(p.value.id, opcao, editor.doc.perguntas, editor.doc.finais)
}

// ── tipo ──
async function trocarTipo(o: OpcaoAdicionar) {
  const base = o.criar()
  const formato = base.formato
  if (o.tipo === p.value.tipo && (o.tipo !== 'texto_curto' || formato === (p.value.formato ?? 'texto'))) return
  const quebradas = condicoesQueDeixamDeValer(p.value.id, { tipo: o.tipo, formato }, editor.doc.perguntas, editor.doc.finais)
  if (quebradas) {
    const ok = await confirmar({
      titulo: 'Trocar o tipo da pergunta?',
      mensagem: `${quebradas === 1 ? '1 condição usa' : `${quebradas} condições usam`} esta pergunta e ${quebradas === 1 ? 'deixa' : 'deixam'} de valer com o tipo novo. Elas ficam marcadas para você ajustar.`,
      confirmar: 'Trocar o tipo',
    })
    if (!ok) return
  }
  const atual = p.value
  const escolha = (t: string) => t === 'escolha_unica' || t === 'escolha_multipla'
  const novo: Pergunta = {
    ...base,
    id: atual.id,
    tipo: o.tipo,
    titulo: atual.titulo,
    descricao: atual.descricao ?? null,
    obrigatoria: atual.obrigatoria,
    ...(escolha(atual.tipo) && escolha(o.tipo) ? { opcoes: [...(atual.opcoes ?? [])], aleatorizar: atual.aleatorizar } : {}),
    ...(atual.logica ? { logica: atual.logica } : {}),
  } as Pergunta
  editor.mudar(() => editor.doc.perguntas.splice(props.indice, 1, novo))
  if (quebradas) avisar.atencao('Algumas condições deixaram de valer. Confira os itens marcados.')
}
</script>

<template>
  <div class="flex flex-col gap-5" :data-editor-pergunta="p.id">
    <CabecalhoEdicao :icone="INFO_TIPO[p.tipo]?.icone" :rotulo="rotulo" :detalhe="ehPrincipal ? 'Nota principal' : undefined" :pode-editar="podeEditar" @duplicar="emit('duplicar')" @excluir="emit('excluir')">
      <MenuSuspenso v-if="podeEditar" rotulo="Tipo da pergunta" class="shrink-0">
        <template #gatilho="{ props: gatilho }">
          <button v-bind="gatilho" type="button" class="inline-flex h-8 items-center gap-1 rounded-lg border border-borda-forte px-2.5 text-sm font-semibold text-texto-suave hover:bg-superficie-2" data-menu-tipo>
            Tipo <ChevronDown class="size-4" aria-hidden="true" />
          </button>
        </template>
        <div class="max-h-80 overflow-y-auto">
          <ItemMenu v-for="o in TIPOS" :key="o.chave" :icone="o.icone" :data-tipo-opcao="o.chave" @click="trocarTipo(o)">
            <span class="flex-1">{{ o.rotulo }}</span>
            <span v-if="opcaoAtual?.chave === o.chave" class="text-xs font-semibold text-marca-texto">atual</span>
          </ItemMenu>
        </div>
      </MenuSuspenso>
    </CabecalhoEdicao>

    <div v-if="ehPrincipal" class="flex gap-2 rounded-xl bg-info-suave p-3 text-sm">
      <Info class="mt-0.5 size-4 shrink-0 text-info" aria-hidden="true" />
      <p class="text-texto-suave">
        Esta é a <strong class="text-texto">nota principal</strong> do formulário. É ela que entra no cálculo de
        {{ p.tipo === 'nps' ? 'NPS' : 'satisfação (CSAT)' }} e define os grupos usados nas condições.
      </p>
    </div>

    <ProblemasDoItem :problemas="problemas" />

    <CampoVariaveis
      v-model="p.titulo"
      rotulo="Pergunta"
      campo="titulo"
      :erro="erro('titulo')"
      :aviso="aviso('titulo')"
      :maximo="300"
      contador
      :citaveis="anteriores"
      :itens="itens"
      :nome-empresa="nomeEmpresa"
    />
    <CampoVariaveis
      v-model="p.descricao"
      rotulo="Texto de apoio"
      campo="descricao"
      opcional
      multilinha
      :erro="erro('descricao')"
      :aviso="aviso('descricao')"
      :maximo="1000"
      :citaveis="anteriores"
      :itens="itens"
      :nome-empresa="nomeEmpresa"
      dica="Aparece em letras menores, embaixo da pergunta."
    />

    <!-- Configurações do tipo -->
    <div v-if="p.tipo === 'nps' || p.tipo === 'escala'" class="grid gap-3 sm:grid-cols-2" data-campo="rotulos">
      <template v-if="p.tipo === 'escala'">
        <Selecao :model-value="p.min ?? 1" rotulo="Começa em" :opcoes="[{ valor: 0, rotulo: '0' }, { valor: 1, rotulo: '1' }]" :erro="erro('min')" data-campo="min" @update:model-value="mudarMin" />
        <Selecao :model-value="p.max ?? 5" rotulo="Termina em" :opcoes="MAXIMOS" :erro="erro('max')" data-campo="max" @update:model-value="(v) => (p.max = Number(v))" />
      </template>
      <Campo :model-value="p.rotulo_min ?? ''" rotulo="Legenda da menor nota" opcional maxlength="60" :placeholder="p.tipo === 'nps' ? 'Nada provável' : ''" :erro="erro('rotulo_min')" @update:model-value="(v: string) => (p.rotulo_min = v || null)" />
      <Campo :model-value="p.rotulo_max ?? ''" rotulo="Legenda da maior nota" opcional maxlength="60" :placeholder="p.tipo === 'nps' ? 'Muito provável' : ''" :erro="erro('rotulo_max')" @update:model-value="(v: string) => (p.rotulo_max = v || null)" />
    </div>

    <template v-if="p.tipo === 'escolha_unica' || p.tipo === 'escolha_multipla'">
      <div data-campo="opcoes">
        <EditorOpcoes v-model="opcoes" :erro="erro('opcoes')" :rotulo-pergunta="p.titulo" :ao-renomear="aoRenomear" :antes-de-remover="antesDeRemover" :ao-remover="aoRemover" />
      </div>
      <div class="flex flex-col gap-3 rounded-xl bg-superficie-2/60 p-3">
        <CaixaSelecao :model-value="!!p.aleatorizar" rotulo="Embaralhar a ordem" descricao="Cada pessoa vê as opções numa ordem diferente (evita que a primeira seja escolhida só por estar no alto)." data-campo="aleatorizar" @update:model-value="(v: boolean) => (v ? (p.aleatorizar = true) : delete p.aleatorizar)" />
        <CaixaSelecao
          v-if="p.tipo === 'escolha_unica'"
          :model-value="p.exibicao === 'lista'"
          rotulo="Mostrar como lista suspensa"
          descricao="Bom para muitas opções (ex.: cidades)."
          data-campo="exibicao"
          @update:model-value="(v: boolean) => (v ? (p.exibicao = 'lista' as ExibicaoEscolha) : delete p.exibicao)"
        />
        <Selecao
          v-if="p.tipo === 'escolha_multipla'"
          :model-value="p.max_selecoes ?? ''"
          rotulo="Máximo de opções"
          vazio="Sem limite"
          :opcoes="maximosSelecao"
          :erro="erro('max_selecoes')"
          data-campo="max_selecoes"
          @update:model-value="(v) => (v === '' ? delete p.max_selecoes : (p.max_selecoes = Number(v)))"
        />
      </div>
    </template>

    <Selecao
      v-if="p.tipo === 'texto_curto'"
      :model-value="p.formato ?? 'texto'"
      rotulo="Tipo de resposta"
      :opcoes="FORMATOS"
      :erro="erro('formato')"
      dica="Com e-mail, a resposta é ligada ao contato que tiver esse e-mail."
      data-campo="formato"
      @update:model-value="(v) => (p.formato = (v || 'texto') as FormatoTexto)"
    />
    <Campo
      v-if="p.tipo === 'texto_curto' || p.tipo === 'comentario'"
      :model-value="p.placeholder ?? ''"
      rotulo="Texto de exemplo"
      opcional
      maxlength="120"
      :placeholder="p.tipo === 'comentario' ? 'Escreva aqui, se quiser' : 'Sua resposta'"
      dica="Aparece apagado dentro do campo, antes de a pessoa escrever."
      :erro="erro('placeholder')"
      data-campo="placeholder"
      @update:model-value="(v: string) => (v ? (p.placeholder = v) : delete p.placeholder)"
    />

    <div class="rounded-xl border border-borda p-3" data-campo="obrigatoria">
      <Interruptor v-model="p.obrigatoria" rotulo="Obrigatória" descricao="A pessoa só avança depois de responder." />
    </div>

    <SecaoLogica :item="p" :indice="indice" />
  </div>
</template>
