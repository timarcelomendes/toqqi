<script setup lang="ts">
// "Final padrão" (docs/api-etapa-5l.md §1.4): o agradecimento do tema (título e texto puros, como antes), que vale
// quando nenhum final da lista vale. Estes dois campos saíram da aba Aparência.
import { computed } from 'vue'
import { Flag } from 'lucide-vue-next'
import { respondivel } from '@/pesquisa/logica'
import { usarEditor } from './documento'
import CabecalhoEdicao from './CabecalhoEdicao.vue'
import CampoVariaveis from './CampoVariaveis.vue'

defineProps<{ podeEditar: boolean; nomeEmpresa: string }>()
const editor = usarEditor()
const tema = computed(() => editor.doc.tema)
const itens = computed(() => editor.doc.perguntas)
const perguntas = computed(() => itens.value.filter((p) => respondivel(p.tipo)))
const erro = (campo: string) => editor.problemas.value.find((p) => p.alvo.tipo === 'tema' && p.campo === campo)?.mensagem ?? null
</script>

<template>
  <div class="flex flex-col gap-5" data-editor-final-padrao>
    <CabecalhoEdicao :icone="Flag" rotulo="Final padrão" :detalhe="editor.doc.finais.length ? 'Vale quando nenhum outro final vale.' : 'O agradecimento depois de enviar.'" :pode-editar="false" />
    <CampoVariaveis v-model="tema.titulo_final" rotulo="Título do agradecimento" campo="titulo_final" :maximo="120" placeholder="Obrigado!" :erro="erro('titulo_final')" :citaveis="perguntas" :itens="itens" :nome-empresa="nomeEmpresa" />
    <CampoVariaveis v-model="tema.texto_final" rotulo="Texto do agradecimento" campo="texto_final" multilinha :maximo="1000" :erro="erro('texto_final')" :citaveis="perguntas" :itens="itens" :nome-empresa="nomeEmpresa" />
    <p class="text-sm text-texto-fraco">Para um agradecimento diferente por grupo (promotores, detratores…), use “Adicionar final” na estrutura.</p>
  </div>
</template>
