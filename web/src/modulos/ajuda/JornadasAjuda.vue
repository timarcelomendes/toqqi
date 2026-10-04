<script setup lang="ts">
// Página Jornadas da Ajuda (docs/ajuda-jornadas.md §3), abaixo do título: o mapa com os dois grupos ("Do cadastro ao
// resultado", numeradas, e "Para ir além") em blocos que levam ao cartão (rola e põe o foco no título dele) e, depois,
// os cartões, com o nome do grupo antes de cada grupo.
import { computed } from 'vue'
import { Compass } from 'lucide-vue-next'
import type { JornadaAjuda as Jornada, TopicoAjuda } from '@/api/tipos'
import JornadaAjuda from './JornadaAjuda.vue'
import { abrirAncora, destinoJornada } from './ancora'
import { GRUPOS_JORNADA, jornadasDoGrupo, proximaJornada, referenciasDaJornada } from './logica'

const props = defineProps<{ jornadas: Jornada[]; topicos: TopicoAjuda[] }>()

/** Os grupos que têm jornadas, cada jornada com o número, o "Saiba mais" que existe e a próxima do ciclo. */
const grupos = computed(() =>
  GRUPOS_JORNADA.map((g) => ({
    ...g,
    itens: jornadasDoGrupo(props.jornadas, g.id).map((x) => ({
      ...x,
      referencias: referenciasDaJornada(props.topicos, x.jornada),
      proxima: proximaJornada(props.jornadas, x.jornada),
    })),
  })).filter((g) => g.itens.length),
)
</script>

<template>
  <div>
    <nav aria-label="Mapa das jornadas" class="flex flex-col gap-6" data-mapa-jornadas>
      <div v-for="g in grupos" :key="g.id">
        <p :id="`jornadas-mapa-${g.id}`" class="mb-2.5 text-xs font-semibold uppercase tracking-wider text-texto-fraco">{{ g.titulo }}</p>
        <!-- role="list": sem marcadores (grade), o Safari deixaria de anunciar a lista e a posição de cada jornada. -->
        <component
          :is="g.id === 'ciclo' ? 'ol' : 'ul'"
          role="list"
          :aria-labelledby="`jornadas-mapa-${g.id}`"
          class="grid grid-cols-1 gap-2.5 sm:grid-cols-2 sm:gap-3 xl:grid-cols-3"
          :data-mapa-grupo="g.id"
        >
          <li v-for="x in g.itens" :key="x.jornada.id" class="min-w-0">
            <RouterLink v-slot="{ href, navigate }" :to="destinoJornada(x.jornada.id)" custom>
              <a
                :href="href"
                class="flex h-full items-start gap-3 rounded-xl border border-borda bg-superficie p-3 shadow-cartao transition-colors hover:border-marca/40 hover:bg-superficie-2 sm:p-3.5"
                :data-mapa-jornada="x.jornada.id"
                @click="(e: MouseEvent) => abrirAncora(navigate, e, x.jornada.id)"
              >
                <span
                  class="flex size-7 shrink-0 items-center justify-center rounded-full bg-marca-suave text-xs font-bold text-marca-texto ring-1 ring-inset ring-marca/25"
                  aria-hidden="true"
                  data-mapa-numero
                >
                  <template v-if="x.numero">{{ x.numero }}</template>
                  <Compass v-else class="size-3.5" />
                </span>
                <span class="min-w-0 pt-0.5">
                  <span class="block break-words text-sm font-semibold leading-snug text-texto">{{ x.jornada.titulo }}</span
                  ><span class="sr-only">, </span>
                  <!-- O caminho do Onde: o leitor de tela ouve "Contatos, Importar planilha" (o "›", preso ao pedaço anterior, fica de fora). -->
                  <span class="mt-1 block break-words text-xs text-texto-fraco" data-mapa-onde
                    ><template v-for="(pedaco, i) in x.jornada.onde" :key="i"
                      ><template v-if="i"><span class="ml-1 mr-0.5" aria-hidden="true">›</span><span class="sr-only">,</span>{{ ' ' }}</template
                      >{{ pedaco }}</template
                    ></span
                  >
                </span>
              </a>
            </RouterLink>
          </li>
        </component>
      </div>
    </nav>

    <section v-for="g in grupos" :key="g.id" class="mt-10" :aria-labelledby="`jornadas-grupo-${g.id}`" :data-grupo-jornadas="g.id">
      <h3
        :id="`jornadas-grupo-${g.id}`"
        class="mb-4 flex items-center gap-3 text-xs font-semibold uppercase tracking-wider text-texto-fraco after:h-px after:flex-1 after:bg-borda"
      >
        {{ g.titulo }}
      </h3>
      <div class="flex flex-col gap-4">
        <JornadaAjuda v-for="x in g.itens" :key="x.jornada.id" :jornada="x.jornada" :numero="x.numero" :referencias="x.referencias" :proxima="x.proxima" />
      </div>
    </section>
  </div>
</template>
