<script setup lang="ts">
// Painel de edição de uma pergunta. Edita o objeto da pergunta no rascunho do editor.
import { computed } from 'vue'
import { Info } from 'lucide-vue-next'
import type { CondicaoPergunta, FormatoTexto, GrupoNota, Pergunta } from '@/api/tipos'
import { faixa, gruposDoTipo, indicePrincipal, podeTerCondicao } from '@/pesquisa/logica'
import Interruptor from '@/components/ui/Interruptor.vue'
import Selecao from '@/components/ui/Selecao.vue'
import CampoVariaveis from './CampoVariaveis.vue'
import EditorOpcoes from './EditorOpcoes.vue'

const props = defineProps<{
  pergunta: Pergunta
  indice: number
  perguntas: Pergunta[]
  erros?: Record<string, string>
}>()

const p = computed(() => props.pergunta)
const ip = computed(() => indicePrincipal(props.perguntas))
const principal = computed(() => (ip.value >= 0 ? props.perguntas[ip.value]! : null))
const ehPrincipal = computed(() => ip.value === props.indice)
const condicaoPermitida = computed(() => podeTerCondicao(props.indice, props.perguntas))
const grupos = computed(() => gruposDoTipo(principal.value?.tipo))
const notasPrincipal = computed(() => {
  if (!principal.value) return []
  const { min, max } = faixa(principal.value)
  return Array.from({ length: max - min + 1 }, (_, i) => ({ valor: min + i, rotulo: String(min + i) }))
})
const erro = (campo: string) => props.erros?.[campo] ?? null

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

type ModoCondicao = 'todos' | 'grupo' | 'nota'
const modoCondicao = computed<ModoCondicao>({
  get: () => (p.value.condicao ? p.value.condicao.tipo : 'todos'),
  set: (m) => {
    if (m === 'todos') p.value.condicao = null
    else if (m === 'grupo') p.value.condicao = { tipo: 'grupo', grupos: grupos.value.slice(0, 1).map((g) => g.valor) }
    else {
      const f = principal.value ? faixa(principal.value) : { min: 0, max: 10 }
      const ehNps = principal.value?.tipo === 'nps'
      p.value.condicao = { tipo: 'nota', operador: '<=', valor: ehNps ? 6 : Math.min(2, f.max) }
    }
  },
})

function alternarGrupo(g: GrupoNota) {
  const c = p.value.condicao
  if (!c || c.tipo !== 'grupo') return
  const atual = c.grupos ?? []
  p.value.condicao = { tipo: 'grupo', grupos: atual.includes(g) ? atual.filter((x) => x !== g) : [...atual, g] }
}

function atualizarNota(campo: 'operador' | 'valor', v: string | number) {
  const c = p.value.condicao
  if (!c || c.tipo !== 'nota') return
  p.value.condicao = { ...c, [campo]: campo === 'valor' ? Number(v) : v } as CondicaoPergunta
}

const opcoes = computed({
  get: () => p.value.opcoes ?? [],
  set: (v: string[]) => (p.value.opcoes = v),
})

function mudarMin(v: number | '') {
  p.value.min = Number(v)
  if ((p.value.max ?? 5) <= p.value.min + 1) p.value.max = p.value.min + 2
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div v-if="ehPrincipal" class="flex gap-2 rounded-xl bg-info-suave p-3 text-sm text-info">
      <Info class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p class="text-texto-suave">
        Esta é a <strong class="text-texto">nota principal</strong> do formulário. É ela que entra no cálculo de
        {{ p.tipo === 'nps' ? 'NPS' : 'satisfação (CSAT)' }} e define os grupos usados nas condições.
      </p>
    </div>

    <template v-if="p.tipo === 'quebra_pagina'">
      <p class="text-sm text-texto-suave">
        A quebra divide a pesquisa em páginas quando o modo é <strong class="text-texto">páginas</strong> (em Aparência). No modo
        uma pergunta por vez, ela não muda nada.
      </p>
    </template>

    <template v-else>
      <CampoVariaveis v-model="p.titulo" rotulo="Pergunta" :erro="erro('titulo')" :maximo="300" />
      <CampoVariaveis v-model="p.descricao" rotulo="Texto de apoio" opcional multilinha :erro="erro('descricao')" :maximo="500" dica="Aparece em letras menores, embaixo da pergunta." />
      <Interruptor v-model="p.obrigatoria" rotulo="Resposta obrigatória" descricao="A pessoa só avança depois de responder." />

      <!-- Específicos por tipo -->
      <div v-if="p.tipo === 'nps' || p.tipo === 'escala'" class="grid gap-3 sm:grid-cols-2">
        <template v-if="p.tipo === 'escala'">
          <Selecao
            :model-value="p.min ?? 1"
            rotulo="Começa em"
            :opcoes="[{ valor: 0, rotulo: '0' }, { valor: 1, rotulo: '1' }]"
            :erro="erro('min')"
            @update:model-value="mudarMin"
          />
          <Selecao :model-value="p.max ?? 5" rotulo="Termina em" :opcoes="MAXIMOS" :erro="erro('max')" @update:model-value="(v) => (p.max = Number(v))" />
        </template>
        <CampoVariaveis v-model="p.rotulo_min" rotulo="Legenda da menor nota" opcional sem-variaveis :maximo="60" :placeholder="p.tipo === 'nps' ? 'Nada provável' : ''" />
        <CampoVariaveis v-model="p.rotulo_max" rotulo="Legenda da maior nota" opcional sem-variaveis :maximo="60" :placeholder="p.tipo === 'nps' ? 'Muito provável' : ''" />
      </div>

      <Selecao
        v-if="p.tipo === 'texto_curto'"
        :model-value="p.formato ?? 'texto'"
        rotulo="Tipo de resposta"
        :opcoes="FORMATOS"
        :erro="erro('formato')"
        dica="Com e-mail, a resposta é ligada ao contato que tiver esse e-mail."
        @update:model-value="(v) => (p.formato = (v || 'texto') as FormatoTexto)"
      />

      <EditorOpcoes v-if="p.tipo === 'escolha_unica' || p.tipo === 'escolha_multipla'" v-model="opcoes" :erro="erro('opcoes')" :rotulo-pergunta="p.titulo" />

      <!-- Condição -->
      <fieldset class="rounded-xl border border-borda p-4" :disabled="!condicaoPermitida && !p.condicao">
        <legend class="px-1 text-sm font-semibold text-texto">Mostrar só para</legend>
        <p v-if="!condicaoPermitida" class="mb-3 text-sm text-texto-fraco">
          <template v-if="!principal">Para usar condições, o formulário precisa de uma pergunta de nota (NPS, carinhas ou estrelas).</template>
          <template v-else-if="ehPrincipal">A nota principal aparece para todo mundo.</template>
          <template v-else>Só dá para usar em perguntas <strong>depois</strong> da nota principal. Mova esta pergunta para baixo dela.</template>
        </p>
        <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="Quem vê esta pergunta">
          <label
            v-for="o in ([{ v: 'todos', t: 'Todo mundo' }, { v: 'grupo', t: 'Alguns grupos' }, { v: 'nota', t: 'Pela nota' }] as const)"
            :key="o.v"
            class="cursor-pointer rounded-lg border px-3 py-1.5 text-sm font-semibold transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-foco has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50"
            :class="modoCondicao === o.v ? 'border-marca bg-marca-suave text-marca-texto' : 'border-borda-forte text-texto-suave hover:bg-superficie-2'"
          >
            <input v-model="modoCondicao" type="radio" :value="o.v" class="sr-only" :disabled="o.v !== 'todos' && !condicaoPermitida" />
            {{ o.t }}
          </label>
        </div>

        <div v-if="p.condicao?.tipo === 'grupo'" class="mt-3 flex flex-wrap gap-2" role="group" aria-label="Grupos que veem esta pergunta">
          <button
            v-for="g in grupos"
            :key="g.valor"
            type="button"
            :aria-pressed="p.condicao.grupos.includes(g.valor)"
            class="rounded-full border px-3 py-1 text-sm font-semibold transition-colors"
            :class="p.condicao.grupos.includes(g.valor) ? 'border-marca-forte bg-marca-forte text-white' : 'border-borda-forte text-texto-suave hover:bg-superficie-2'"
            @click="alternarGrupo(g.valor)"
          >
            {{ g.rotulo }}
          </button>
        </div>
        <div v-else-if="p.condicao?.tipo === 'nota'" class="mt-3 flex flex-wrap items-end gap-2">
          <Selecao
            :model-value="p.condicao.operador"
            rotulo="Nota"
            :opcoes="[{ valor: '<=', rotulo: 'até (menor ou igual a)' }, { valor: '>=', rotulo: 'a partir de (maior ou igual a)' }]"
            @update:model-value="(v) => atualizarNota('operador', v)"
          />
          <Selecao :model-value="p.condicao.valor" rotulo="Valor" rotulo-oculto :opcoes="notasPrincipal" @update:model-value="(v) => atualizarNota('valor', v)" />
        </div>
        <p v-if="erro('condicao')" class="mt-2 text-sm font-medium text-erro">
          {{ erro('condicao') }}
          <button v-if="!condicaoPermitida && p.condicao" type="button" class="link ml-1" @click="p.condicao = null">Tirar a condição</button>
        </p>
        <p v-else-if="!condicaoPermitida && p.condicao" class="mt-2 text-sm font-medium text-atencao">
          Esta condição não vale mais aqui. <button type="button" class="link ml-1" @click="p.condicao = null">Tirar a condição</button>
        </p>
      </fieldset>
    </template>
    <p v-if="erro('_')" class="text-sm font-medium text-erro">{{ erro('_') }}</p>
  </div>
</template>
