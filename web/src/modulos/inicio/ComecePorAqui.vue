<script setup lang="ts">
// "Comece por aqui" (etapa 5h, docs/api-etapa-5h.md §1): o Início de quem tem painel.ver enquanto a conta não tem
// nenhuma resposta. Os 4 passos de `montarPassos` como uma lista grande (número, título, descrição, feito/a fazer e o
// botão do passo quando o perfil abre a tela; o próximo a fazer em destaque) e, ao lado, "Sua marca nas pesquisas"
// (só configuracoes.gerenciar; opcional, fora dos 4 passos) e "Veja como fica com dados" (liga o modo exemplo).
import { computed, ref } from 'vue'
import { ArrowRight, Check, Eye } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import Botao from '@/components/ui/Botao.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MedidorNps from '@/modulos/painel/MedidorNps.vue'
import type { PassoInicial } from '@/modulos/painel/logica'
import CartaoMarca from './CartaoMarca.vue'
import { progressoPassos, proximoPasso } from './logica'

const props = defineProps<{ passos: PassoInicial[] }>()
const emit = defineEmits<{ exemplo: [] }>()
const sessao = useSessaoStore()

const proximo = computed(() => proximoPasso(props.passos))
const progresso = computed(() => progressoPassos(props.passos))
const botaoExemplo = ref<InstanceType<typeof Botao> | null>(null)

/** Volta o foco ao botão do exemplo (ao sair do modo exemplo). */
function focarExemplo() {
  const el = (botaoExemplo.value?.$el ?? null) as HTMLElement | null
  el?.focus()
}
defineExpose({ focarExemplo })

function estado(p: PassoInicial): { rotulo: string; tom: 'sucesso' | 'marca' | 'neutro' } {
  if (p.feito) return { rotulo: 'Feito', tom: 'sucesso' }
  if (proximo.value?.chave === p.chave) return { rotulo: 'Próximo passo', tom: 'marca' }
  return { rotulo: 'A fazer', tom: 'neutro' }
}
</script>

<template>
  <div class="grid grid-cols-1 items-start gap-4 pb-28 sm:gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)]" data-comece>
    <!-- Os 4 passos -->
    <section class="cartao overflow-hidden" aria-labelledby="t-comece">
      <header class="flex flex-col gap-3 border-b border-borda px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div class="min-w-0">
          <p class="text-xs font-bold uppercase tracking-wider text-marca-texto">Comece por aqui</p>
          <h2 id="t-comece" class="mt-0.5 text-lg font-bold text-texto">Do cadastro à primeira resposta</h2>
        </div>
        <div class="flex shrink-0 items-center gap-3">
          <ol class="flex gap-1" aria-hidden="true">
            <li v-for="p in passos" :key="p.chave" class="h-1.5 w-6 rounded-full" :class="p.feito ? 'bg-sucesso' : 'bg-borda-forte'" />
          </ol>
          <p class="text-sm font-semibold text-texto-suave" data-progresso>{{ progresso.texto }}</p>
        </div>
      </header>

      <ol class="flex flex-col" aria-label="Os 4 passos">
        <li
          v-for="(p, i) in passos"
          :key="p.chave"
          class="relative flex gap-4 px-5 py-5 sm:px-6"
          :class="[proximo?.chave === p.chave ? 'bg-marca-suave/70' : '', i > 0 ? 'border-t border-borda' : '']"
          :data-passo="p.chave"
          :data-proximo="proximo?.chave === p.chave || undefined"
        >
          <span
            class="flex size-10 shrink-0 items-center justify-center rounded-full text-base font-extrabold tabular-nums"
            :class="
              p.feito
                ? 'bg-sucesso-suave text-sucesso ring-1 ring-inset ring-sucesso/30'
                : proximo?.chave === p.chave
                  ? 'bg-marca-forte text-white shadow-sm'
                  : 'bg-superficie text-texto-suave ring-1 ring-inset ring-borda-forte'
            "
            aria-hidden="true"
          >
            <Check v-if="p.feito" class="size-5" stroke-width="3" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          <div class="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <h3 class="text-base font-bold" :class="p.feito ? 'text-texto-suave' : 'text-texto'">
                  <span class="sr-only">Passo {{ i + 1 }}: </span>{{ p.titulo }}
                </h3>
                <Etiqueta :tom="estado(p).tom">{{ estado(p).rotulo }}</Etiqueta>
              </div>
              <p class="mt-1 text-sm text-texto-suave">{{ p.descricao }}</p>
            </div>
            <Botao
              v-if="!p.feito && p.para"
              :para="p.para"
              :variante="proximo?.chave === p.chave ? 'primario' : 'secundario'"
              class="self-start sm:self-auto"
              :data-acao-passo="p.chave"
            >
              {{ p.acao }} <ArrowRight class="size-4" aria-hidden="true" />
            </Botao>
          </div>
        </li>
      </ol>
    </section>

    <!-- Ao lado: a marca (opcional) e o exemplo -->
    <div class="flex min-w-0 flex-col gap-4 sm:gap-5">
      <CartaoMarca v-if="sessao.pode('configuracoes.gerenciar')" />

      <section class="cartao overflow-hidden" aria-labelledby="t-exemplo" data-cartao-exemplo>
        <!-- Prévia decorativa do painel com dados -->
        <div class="relative h-32 overflow-hidden border-b border-borda bg-linear-to-br from-marca-suave via-superficie-2 to-superficie-2 px-5 pt-4" aria-hidden="true">
          <div class="mx-auto flex max-w-64 items-end gap-3 rounded-t-xl border border-b-0 border-borda bg-superficie px-3 pt-3 shadow-cartao">
            <div class="w-24 shrink-0"><MedidorNps :valor="27" /></div>
            <div class="flex min-w-0 flex-1 flex-col gap-1.5 pb-3">
              <span class="h-2 w-[42%] rounded-full bg-grafico-detrator" />
              <span class="h-2 w-[30%] rounded-full bg-grafico-neutro" />
              <span class="h-2 w-[88%] rounded-full bg-grafico-promotor" />
              <span class="mt-1 h-1.5 w-[70%] rounded-full bg-borda-forte" />
            </div>
          </div>
        </div>
        <div class="flex flex-col gap-3 p-5">
          <div>
            <h2 id="t-exemplo" class="text-base font-bold text-texto">Veja como fica com dados</h2>
            <p class="mt-0.5 text-sm text-texto-suave">
              O Início com respostas de exemplo: NPS, o que mudou, temas, tom dos comentários e empresas. Nada é gravado na sua conta.
            </p>
          </div>
          <Botao ref="botaoExemplo" variante="secundario" class="self-start" data-ver-exemplo @click="emit('exemplo')">
            <Eye class="size-4" aria-hidden="true" /> Ver com dados de exemplo
          </Botao>
        </div>
      </section>
    </div>
  </div>
</template>
