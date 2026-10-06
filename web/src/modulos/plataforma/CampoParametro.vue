<script setup lang="ts">
// Um campo de Plataforma › Parâmetros (etapa 5g, §7): o valor em uso para editar, "Padrão: …" com a origem (ligado ao
// campo por aria-describedby), "Usar o padrão" quando o campo difere dele e o erro da validação (da tela ou da API).
// Dinheiro aceita "1.250,00" e "1250,5"; contatos têm a caixa "Sem limite"; esforço e plano são listas; a exclusão
// automática, dois rádios.
import { computed, nextTick, ref, useId } from 'vue'
import { Circle, CircleCheck } from 'lucide-vue-next'
import type { ValorParametro } from '@/api/tipos'
import Campo from '@/components/ui/Campo.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'
import Selecao from '@/components/ui/Selecao.vue'
import { OPCOES_ESFORCO, OPCOES_EXCLUSAO, OPCOES_PLANO, campoDaChave, difereDoPadrao, textoPadrao, type FormParametros } from './parametros'

const props = defineProps<{
  chave: string
  padrao: ValorParametro | undefined
  origem: string | undefined
  erro?: string | null
  desabilitado?: boolean
}>()
const texto = defineModel<string>('texto', { default: '' })
const semLimite = defineModel<boolean>('semLimite', { default: false })
const emit = defineEmits<{ usarPadrao: [] }>()

const campo = computed(() => campoDaChave(props.chave))
const tipo = computed(() => campo.value?.tipo ?? 'modelo')
const id = `p-${props.chave.replace(/[^a-z0-9]+/gi, '-')}`
const idUnico = useId()
const dica = computed(() => textoPadrao(props.chave, props.padrao, props.origem))
const difere = computed(() => {
  const form: FormParametros = { textos: { [props.chave]: texto.value }, semLimite: { [props.chave]: semLimite.value } }
  return difereDoPadrao(form, props.chave, props.padrao)
})
const raiz = ref<HTMLElement | null>(null)
/** Contatos: com "Sem limite", o campo (desligado) fica vazio com a dica; o número fica guardado para quem desmarcar. */
const textoContatos = computed({
  get: () => (semLimite.value ? '' : texto.value),
  set: (v: string) => {
    if (!semLimite.value) texto.value = v
  },
})

async function usarPadrao() {
  emit('usarPadrao')
  await nextTick()
  // O botão some (o campo ficou igual ao padrão): o foco vai para o campo (o rádio marcado; sem limite, a caixa).
  const r = raiz.value
  const alvo =
    r?.querySelector<HTMLElement>('input[type="radio"]:checked') ??
    r?.querySelector<HTMLElement>('input:not([type="checkbox"]):not([type="radio"]):not([disabled]), select:not([disabled])') ??
    r?.querySelector<HTMLElement>('input[type="checkbox"]')
  alvo?.focus()
}
</script>

<template>
  <div ref="raiz" class="flex min-w-0 flex-col gap-1.5" :data-parametro="chave">
    <Campo
      v-if="tipo === 'dinheiro'"
      :id="id"
      v-model="texto"
      :rotulo="campo?.rotulo ?? chave"
      inputmode="decimal"
      autocomplete="off"
      :erro="erro"
      :dica="dica"
      :desabilitado="desabilitado"
    >
      <template #antes><span class="text-sm font-semibold">R$</span></template>
    </Campo>

    <template v-else-if="tipo === 'contatos' || tipo === 'limite'">
      <Campo
        :id="id"
        v-model="textoContatos"
        :rotulo="campo?.rotulo ?? chave"
        inputmode="numeric"
        autocomplete="off"
        :placeholder="semLimite ? 'Sem limite' : undefined"
        :erro="semLimite ? null : erro"
        :dica="dica"
        :desabilitado="desabilitado || semLimite"
      />
      <CaixaSelecao v-model="semLimite" rotulo="Sem limite" :desabilitado="desabilitado" />
    </template>

    <Campo
      v-else-if="tipo === 'inteiro'"
      :id="id"
      v-model="texto"
      :rotulo="campo?.rotulo ?? chave"
      inputmode="numeric"
      autocomplete="off"
      :erro="erro"
      :dica="dica"
      :desabilitado="desabilitado"
    />

    <Selecao
      v-else-if="tipo === 'esforco' || tipo === 'plano'"
      v-model="texto"
      :rotulo="campo?.rotulo ?? chave"
      :opcoes="tipo === 'esforco' ? OPCOES_ESFORCO : OPCOES_PLANO"
      :erro="erro"
      :dica="dica"
      :desabilitado="desabilitado"
    />

    <fieldset
      v-else-if="tipo === 'exclusao'"
      class="m-0 min-w-0 border-0 p-0"
      :aria-describedby="[erro ? `${idUnico}-erro` : '', `${idUnico}-dica`].filter(Boolean).join(' ')"
    >
      <legend class="mb-1.5 text-sm font-semibold text-texto">{{ campo?.rotulo ?? chave }}</legend>
      <div class="grid gap-2 sm:grid-cols-2">
        <label
          v-for="o in OPCOES_EXCLUSAO"
          :key="o.valor"
          class="relative flex min-w-0 gap-2.5 rounded-xl border p-3 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
          :class="[texto === o.valor ? 'border-marca bg-marca-suave/50' : 'border-borda-forte hover:bg-superficie-2', desabilitado ? 'opacity-70' : 'cursor-pointer']"
          :data-opcao="o.valor"
        >
          <input v-model="texto" type="radio" :name="id" :value="o.valor" :disabled="desabilitado" class="sr-only" />
          <CircleCheck v-if="texto === o.valor" class="mt-0.5 size-4 shrink-0 text-marca-texto" aria-hidden="true" />
          <Circle v-else class="mt-0.5 size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
          <span class="min-w-0 text-texto">{{ o.rotulo }}</span>
        </label>
      </div>
      <p v-if="erro" :id="`${idUnico}-erro`" class="mt-1.5 text-sm font-medium text-erro">{{ erro }}</p>
      <p :id="`${idUnico}-dica`" class="mt-1.5 text-sm text-texto-fraco">{{ dica }}</p>
    </fieldset>

    <Campo
      v-else
      :id="id"
      v-model="texto"
      :rotulo="campo?.rotulo ?? chave"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      :erro="erro"
      :dica="dica"
      :desabilitado="desabilitado"
    />

    <button v-if="difere" type="button" class="link self-start text-sm" :disabled="desabilitado" data-usar-padrao @click="usarPadrao">
      Usar o padrão<span class="sr-only">: {{ campo?.nome ?? chave }}</span>
    </button>
  </div>
</template>
