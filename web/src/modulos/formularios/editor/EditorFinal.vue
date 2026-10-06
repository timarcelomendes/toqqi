<script setup lang="ts">
// Edição de um final (docs/api-etapa-5l.md §1.4 e §5.3): nome interno, título (com "Inserir"), texto (Visual/HTML),
// botão opcional (texto + endereço https) e "Mostrar este final quando…" (a fonte pode ser qualquer pergunta). Vale o
// primeiro final que combinar: um final sem condição antes de outros esconde os de baixo.
import { computed, ref } from 'vue'
import { Flag, TriangleAlert } from 'lucide-vue-next'
import type { Final, Id } from '@/api/tipos'
import { respondivel } from '@/pesquisa/logica'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Campo from '@/components/ui/Campo.vue'
import Interruptor from '@/components/ui/Interruptor.vue'
import { condicaoPadrao, fontesPara } from '../logicaEditor'
import { errosDaLogica } from '../validacaoFormulario'
import { usarEditor } from './documento'
import CabecalhoEdicao from './CabecalhoEdicao.vue'
import CampoVariaveis from './CampoVariaveis.vue'
import ConstrutorGrupo from './ConstrutorGrupo.vue'
import EditorHtml from './EditorHtml.vue'
import ProblemasDoItem from './ProblemasDoItem.vue'

const props = defineProps<{ final: Final; indice: number; podeEditar: boolean; nomeEmpresa: string; formularioId: Id; prefixoImagens: string | null }>()
const emit = defineEmits<{ duplicar: []; excluir: [] }>()
const editor = usarEditor()

const f = computed(() => props.final)
const itens = computed(() => editor.doc.perguntas)
const perguntas = computed(() => itens.value.filter((p) => respondivel(p.tipo)))
const fontes = computed(() => fontesPara(itens.value, 'final'))
const problemas = computed(() => editor.problemas.value.filter((x) => 'id' in x.alvo && x.alvo.id === f.value.id))
const erro = (campo: string) => problemas.value.find((x) => x.campo === campo && !x.aviso)?.mensagem ?? null
const aviso = (campo: string) => problemas.value.find((x) => x.campo === campo && x.aviso)?.mensagem ?? null
const errosCondicao = computed(() => errosDaLogica(problemas.value, 'mostrar_se'))
/** A aba do texto (o final não guarda a dica de aba). */
const modoTexto = ref<'visual' | 'html'>('visual')

const semCondicao = computed(() => !f.value.mostrar_se?.condicoes?.length)
const naoEhUltimo = computed(() => props.indice < editor.doc.finais.length - 1)
/** Um final sem condição acima deste: este nunca aparece. */
const escondidoPorOutro = computed(() => editor.doc.finais.slice(0, props.indice).find((x) => !x.mostrar_se?.condicoes?.length) ?? null)

type Modo = 'sempre' | 'so_se'
const MODOS: { valor: Modo; rotulo: string }[] = [
  { valor: 'sempre', rotulo: 'Sempre' },
  { valor: 'so_se', rotulo: 'Só se…' },
]
const modo = computed<Modo>({
  get: () => (f.value.mostrar_se ? 'so_se' : 'sempre'),
  set: (m) => {
    if (m === 'sempre') f.value.mostrar_se = null
    else {
      const fonte = perguntas.value[0]
      if (fonte) f.value.mostrar_se = { juncao: 'todas', condicoes: [condicaoPadrao(fonte)] }
    }
  },
})

const temBotao = computed({
  get: () => !!f.value.botao,
  set: (v: boolean) => (f.value.botao = v ? { texto: '', url: 'https://' } : null),
})
</script>

<template>
  <div class="flex flex-col gap-5" :data-editor-final="f.id">
    <CabecalhoEdicao :icone="Flag" :rotulo="`Final · ${f.nome || 'sem nome'}`" detalhe="O que a pessoa vê depois de enviar." :pode-editar="podeEditar" @duplicar="emit('duplicar')" @excluir="emit('excluir')" />
    <ProblemasDoItem :problemas="problemas" />
    <p v-if="escondidoPorOutro" class="flex gap-2 rounded-xl border border-atencao/30 bg-atencao-suave p-3 text-sm text-texto" data-final-escondido>
      <TriangleAlert class="mt-0.5 size-4 shrink-0 text-atencao" aria-hidden="true" />
      Este final nunca aparece: o final “{{ escondidoPorOutro.nome }}”, acima, não tem condição e vale antes dele. Mude a ordem ou ponha uma condição nele.
    </p>
    <p v-else-if="semCondicao && naoEhUltimo" class="flex gap-2 rounded-xl border border-atencao/30 bg-atencao-suave p-3 text-sm text-texto" data-aviso-finais-abaixo>
      <TriangleAlert class="mt-0.5 size-4 shrink-0 text-atencao" aria-hidden="true" />
      Os finais abaixo deste nunca aparecem. Vale o primeiro que combinar: deixe o final sem condição por último.
    </p>

    <Campo :model-value="f.nome" rotulo="Nome interno" maxlength="60" placeholder="Ex.: Promotores" dica="Só a sua equipe vê (na estrutura e nos relatórios)." :erro="erro('nome')" data-campo="nome" @update:model-value="(v: string) => (f.nome = v)" />
    <CampoVariaveis v-model="f.titulo" rotulo="Título" campo="titulo" :maximo="120" contador :erro="erro('titulo')" :aviso="aviso('titulo')" :citaveis="perguntas" :itens="itens" :nome-empresa="nomeEmpresa" />
    <EditorHtml
      v-model:html="f.html"
      v-model:modo="modoTexto"
      :id-item="f.id"
      rotulo="Texto"
      :formulario-id="formularioId"
      :prefixo-imagens="prefixoImagens"
      :pode-editar="podeEditar"
      :citaveis="perguntas"
      :itens="itens"
      :nome-empresa="nomeEmpresa"
      :erro="erro('html')"
      :aviso="aviso('html')"
      placeholder="Escreva o agradecimento (opcional)…"
    />

    <div class="@container flex flex-col gap-3 rounded-xl border border-borda p-3" data-campo="botao">
      <Interruptor v-model="temBotao" rotulo="Botão" descricao="Um botão que abre um link em nova aba." />
      <template v-if="f.botao">
        <div class="grid gap-3 @lg:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]">
          <Campo :model-value="f.botao.texto" rotulo="Texto do botão" maxlength="40" placeholder="Avaliar no Google" :erro="erro('botao.texto')" data-campo="botao.texto" @update:model-value="(v: string) => f.botao && (f.botao.texto = v)" />
          <Campo
            :model-value="f.botao.url"
            rotulo="Endereço"
            tipo="url"
            maxlength="500"
            placeholder="https://"
            dica="Ex.: o link para avaliarem a sua empresa no Google"
            :erro="erro('botao.url')"
            data-campo="botao.url"
            @update:model-value="(v: string) => f.botao && (f.botao.url = v.trim())"
          />
        </div>
      </template>
    </div>

    <section class="flex flex-col gap-3 rounded-2xl border border-borda p-4" data-logica-onde="mostrar_se" data-secao-logica>
      <h3 class="text-sm font-bold text-texto">Mostrar este final quando…</h3>
      <BotoesSegmentados v-model="modo" :opcoes="MODOS" rotulo="Quando mostrar este final" :desabilitado="!perguntas.length && modo === 'sempre'" />
      <ConstrutorGrupo v-if="f.mostrar_se" :grupo="f.mostrar_se" :fontes="fontes" :itens="itens" prefixo="Mostrar este final quando" :erros="errosCondicao" @vazio="f.mostrar_se = null" />
      <ul v-if="errosCondicao.geral.length" class="flex flex-col gap-0.5">
        <li v-for="m in errosCondicao.geral" :key="m" class="text-sm font-medium text-erro">{{ m }}</li>
      </ul>
      <p class="text-xs text-texto-fraco">Vale o primeiro final que combinar, de cima para baixo. Se nenhum combinar, vale o final padrão.</p>
    </section>
  </div>
</template>
