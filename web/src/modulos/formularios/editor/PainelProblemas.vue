<script setup lang="ts">
// Painel "Problemas" (docs/api-etapa-5l.md §5.3): o que o site confere na hora (as mesmas regras da API), o que voltou
// do último rascunho salvo e o que impediu de publicar, agrupado por item. Clicar seleciona o item e leva o foco ao
// campo. Avisos (citação que vai sair vazia) aparecem, mas não impedem publicar.
import { computed } from 'vue'
import { AlertTriangle, ChevronRight, CircleAlert } from 'lucide-vue-next'
import { FOCO_FINAL_PADRAO } from '@/pesquisa/tipos'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import { nomeDoItem, numerosDasPerguntas } from '../logicaEditor'
import type { Problema } from '../validacaoFormulario'
import { usarEditor } from './documento'

const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ ir: [problema: Problema] }>()
const editor = usarEditor()

const numeros = computed(() => numerosDasPerguntas(editor.doc.perguntas))

interface GrupoProblemas {
  chave: string
  titulo: string
  problemas: Problema[]
}

const grupos = computed<GrupoProblemas[]>(() => {
  const mapa = new Map<string, GrupoProblemas>()
  const ordem = (p: Problema) => (p.alvo.tipo === 'formulario' ? 0 : p.alvo.tipo === 'item' ? 1 + p.alvo.indice : p.alvo.tipo === 'final' ? 1000 + p.alvo.indice : 2000)
  for (const p of [...editor.problemas.value].sort((a, b) => ordem(a) - ordem(b))) {
    let chave = 'formulario'
    let titulo = 'Formulário'
    if (p.alvo.tipo === 'item') {
      const alvo = p.alvo
      const item = editor.doc.perguntas.find((x) => x.id === alvo.id)
      chave = `item:${alvo.id}`
      titulo = item ? nomeDoItem(item, numeros.value, 70) : 'Item'
    } else if (p.alvo.tipo === 'final') {
      const alvo = p.alvo
      chave = `final:${alvo.id}`
      titulo = `Final · ${editor.doc.finais.find((f) => f.id === alvo.id)?.nome || 'sem nome'}`
    } else if (p.alvo.tipo === 'tema') {
      chave = 'tema'
      titulo = p.campo === 'titulo_final' || p.campo === 'texto_final' ? 'Final padrão' : 'Aparência'
    }
    if (!mapa.has(chave)) mapa.set(chave, { chave, titulo, problemas: [] })
    mapa.get(chave)!.problemas.push(p)
  }
  return [...mapa.values()]
})
const qtdErros = computed(() => editor.erros.value.length)

function ir(p: Problema) {
  // O final padrão fica nos campos do tema, mas é editado na estrutura.
  if (p.alvo.tipo === 'tema' && (p.campo === 'titulo_final' || p.campo === 'texto_final')) {
    editor.selecionado.value = FOCO_FINAL_PADRAO
    emit('ir', { ...p, alvo: { tipo: 'final', id: FOCO_FINAL_PADRAO, indice: -1 } })
    return
  }
  emit('ir', p)
}
</script>

<template>
  <PainelLateral
    v-model:aberto="aberto"
    titulo="Problemas"
    :descricao="qtdErros ? 'Ajuste estes pontos para publicar. Clique para ir até o campo.' : 'Nada impede publicar. Os avisos são só para conferir.'"
  >
    <div class="flex flex-col gap-4" data-painel-problemas>
      <p v-if="!grupos.length" class="text-sm text-texto-suave">Tudo certo por aqui.</p>
      <section v-for="g in grupos" :key="g.chave" class="rounded-xl border border-borda" :data-grupo-problema="g.chave">
        <h3 class="border-b border-borda px-3.5 py-2.5 text-sm font-bold text-texto">{{ g.titulo }}</h3>
        <ul class="flex flex-col divide-y divide-borda">
          <li v-for="(p, i) in g.problemas" :key="i">
            <button type="button" class="flex w-full items-start gap-2.5 px-3.5 py-2.5 text-left text-sm hover:bg-superficie-2" data-ir-problema @click="ir(p)">
              <AlertTriangle v-if="p.aviso" class="mt-0.5 size-4 shrink-0 text-atencao" aria-hidden="true" />
              <CircleAlert v-else class="mt-0.5 size-4 shrink-0 text-erro" aria-hidden="true" />
              <span class="flex-1 text-texto-suave"><span class="sr-only">{{ p.aviso ? 'Aviso: ' : 'Problema: ' }}</span>{{ p.mensagem }}</span>
              <ChevronRight class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
            </button>
          </li>
        </ul>
      </section>
    </div>
  </PainelLateral>
</template>
