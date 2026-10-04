<script setup lang="ts">
// Cartão de uma jornada da Ajuda (docs/ajuda-jornadas.md §3): o número (só no ciclo), o título, "Só administrador" e o
// objetivo; as três paradas ligadas por uma linha (Onde, com o caminho e o botão "Abrir <tela>"; Como, os passos; e o
// Resultado, num quadro de sucesso); no rodapé, "Saiba mais" e, no ciclo, a próxima jornada.
import { computed } from 'vue'
import { ArrowRight, CircleCheck, Compass, ListOrdered, MapPin } from 'lucide-vue-next'
import type { JornadaAjuda } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import Botao from '@/components/ui/Botao.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { abrirAncora, destinoJornada, destinoSecao } from './ancora'
import { atalhoConhecido, atalhoPermitido } from './atalhos'
import type { ReferenciaAjuda } from './logica'

const props = defineProps<{
  jornada: JornadaAjuda
  /** 1 a N no ciclo; null nas "para ir além". */
  numero: number | null
  /** As seções do "Saiba mais" que existem no conteúdo. */
  referencias: ReferenciaAjuda[]
  /** A próxima do ciclo; null na última e nas "para ir além". */
  proxima: JornadaAjuda | null
}>()

const sessao = useSessaoStore()
const atalho = computed(() => atalhoPermitido(props.jornada.atalho, { pode: sessao.pode, admin: sessao.admin }))
/** A tela existe, mas o perfil não a abre (chave desconhecida não conta: aí não há o que dizer). */
const semAcesso = computed(() => !atalho.value && atalhoConhecido(props.jornada.atalho))
const idProxima = computed(() => props.proxima?.id ?? '')

/**
 * Cada parada: o círculo do ícone à esquerda e, nas duas primeiras, a linha tracejada até o círculo seguinte. Os
 * círculos ficam no eixo do número do cabeçalho (16 px no celular, 18 px a partir de `sm`) e o texto, na coluna do título.
 */
const PARADA = 'relative pl-11 sm:pl-[3.125rem]'
const LINHA =
  'pb-6 before:absolute before:bottom-1.5 before:left-[0.9375rem] before:top-[2.375rem] before:border-l-2 before:border-dashed before:border-borda-forte sm:before:left-[1.0625rem]'
const CIRCULO = 'absolute left-0 top-0 flex size-8 items-center justify-center rounded-full ring-1 ring-inset sm:left-0.5'
const ROTULO = 'flex min-h-8 items-center text-xs font-semibold uppercase tracking-wider text-texto-fraco'
</script>

<template>
  <article :id="`ajuda-${jornada.id}`" class="cartao p-4 sm:p-6" :aria-labelledby="`t-ajuda-${jornada.id}`" :data-jornada="jornada.id">
    <header class="flex items-start gap-3 sm:gap-3.5">
      <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-marca-forte text-sm font-bold text-white sm:size-9" aria-hidden="true" data-numero>
        <template v-if="numero">{{ numero }}</template>
        <Compass v-else class="size-[1.125rem]" />
      </span>
      <div class="min-w-0 flex-1 pt-1">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <h4 :id="`t-ajuda-${jornada.id}`" tabindex="-1" class="min-w-0 break-words text-base font-bold text-texto focus:outline-none sm:text-lg">
            <span v-if="numero" class="sr-only">{{ numero }}. </span>{{ jornada.titulo }}
          </h4>
          <Etiqueta v-if="jornada.somente_admin" tom="marca" data-somente-admin>Só administrador</Etiqueta>
        </div>
        <p v-if="jornada.objetivo" class="mt-1 break-words text-[0.95rem] leading-relaxed text-texto-suave" data-objetivo>{{ jornada.objetivo }}</p>
      </div>
    </header>

    <dl class="mt-5">
      <div :class="[PARADA, LINHA]" data-parada="onde">
        <dt :class="ROTULO">
          <span :class="CIRCULO" class="bg-marca-suave text-marca-texto ring-marca/25" aria-hidden="true"><MapPin class="size-4" /></span>
          Onde
        </dt>
        <dd class="mt-1">
          <div class="flex flex-wrap items-center gap-x-4 gap-y-2.5">
            <ol role="list" class="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1.5" aria-label="Caminho até a tela" data-onde>
              <li v-for="(pedaco, i) in jornada.onde" :key="i" class="flex min-w-0 items-center gap-1.5">
                <span v-if="i" class="text-texto-fraco" aria-hidden="true">›</span>
                <span class="min-w-0 break-words rounded-lg bg-superficie-2 px-2 py-0.5 text-[0.8125rem] font-semibold text-texto ring-1 ring-inset ring-borda-forte/60">{{ pedaco }}</span>
              </li>
            </ol>
            <Botao v-if="atalho" :para="atalho.caminho" variante="secundario" tamanho="sm" data-atalho>
              Abrir {{ atalho.rotulo }} <ArrowRight class="size-4" aria-hidden="true" />
            </Botao>
          </div>
          <p v-if="semAcesso" class="mt-2 text-sm text-texto-fraco" data-sem-acesso>Seu perfil não abre esta tela. Peça acesso a um administrador.</p>
        </dd>
      </div>

      <div :class="[PARADA, LINHA]" data-parada="como">
        <dt :class="ROTULO">
          <span :class="CIRCULO" class="bg-marca-suave text-marca-texto ring-marca/25" aria-hidden="true"><ListOrdered class="size-4" /></span>
          Como
        </dt>
        <dd class="mt-1">
          <ol class="flex list-decimal flex-col gap-1.5 pl-5 text-[0.95rem] leading-relaxed text-texto-suave marker:font-semibold marker:text-texto">
            <li v-for="(passo, i) in jornada.como" :key="i" class="break-words pl-1">{{ passo }}</li>
          </ol>
        </dd>
      </div>

      <div :class="PARADA" data-parada="resultado">
        <dt :class="ROTULO">
          <span :class="CIRCULO" class="bg-sucesso-suave text-sucesso ring-sucesso/30" aria-hidden="true"><CircleCheck class="size-4" /></span>
          Resultado
        </dt>
        <dd class="mt-1.5">
          <p class="break-words rounded-xl border border-sucesso/25 bg-sucesso-suave px-4 py-3 text-[0.95rem] leading-relaxed text-texto">{{ jornada.resultado }}</p>
        </dd>
      </div>
    </dl>

    <footer
      v-if="referencias.length || proxima"
      class="mt-6 flex flex-col gap-4 border-t border-borda pt-4 text-sm"
    >
      <div v-if="referencias.length" class="min-w-0">
        <p :id="`jornada-saiba-${jornada.id}`" class="font-semibold text-texto">Saiba mais:</p>
        <ul role="list" class="mt-1.5 flex flex-col items-start gap-1.5" :aria-labelledby="`jornada-saiba-${jornada.id}`">
          <li v-for="r in referencias" :key="`${r.topico.id}#${r.secao.id}`" class="min-w-0 max-w-full">
            <RouterLink :to="destinoSecao(r.topico.id, r.secao.id)" class="link break-words" :data-saiba-mais="`${r.topico.id}#${r.secao.id}`">{{ r.secao.titulo }}</RouterLink>
          </li>
        </ul>
      </div>
      <RouterLink v-if="proxima" v-slot="{ href, navigate }" :to="destinoJornada(proxima.id)" custom>
        <a
          :href="href"
          class="link inline-flex max-w-full items-baseline gap-1.5 self-start sm:self-end"
          data-proxima
          @click="(e: MouseEvent) => abrirAncora(navigate, e, idProxima)"
        >
          <span class="min-w-0 break-words"><span class="font-normal text-texto-suave">Próxima jornada:</span> {{ proxima.titulo }}</span>
          <ArrowRight class="size-4 shrink-0 self-center" aria-hidden="true" />
        </a>
      </RouterLink>
    </footer>
  </article>
</template>
