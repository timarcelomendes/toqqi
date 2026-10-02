<script setup lang="ts">
// Uma seção da Ajuda: título (com "Só administrador" quando for o caso), os blocos de texto (parágrafo, passos
// numerados, lista e dica) e o botão "Abrir <tela>" quando a pessoa pode abrir a tela indicada.
import { computed } from 'vue'
import { ArrowRight } from 'lucide-vue-next'
import type { SecaoAjuda } from '@/api/tipos'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { atalhoPermitido } from './atalhos'

const props = defineProps<{ secao: SecaoAjuda }>()
const sessao = useSessaoStore()
const atalho = computed(() => atalhoPermitido(props.secao.atalho, { pode: sessao.pode, admin: sessao.admin }))
</script>

<template>
  <section :id="`ajuda-${secao.id}`" class="cartao p-5 sm:p-6" :aria-labelledby="`t-ajuda-${secao.id}`" :data-secao="secao.id">
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <h3 :id="`t-ajuda-${secao.id}`" tabindex="-1" class="text-base font-bold text-texto focus:outline-none sm:text-lg">{{ secao.titulo }}</h3>
      <Etiqueta v-if="secao.somente_admin" tom="marca" data-somente-admin>Só administrador</Etiqueta>
    </div>
    <div class="mt-3 flex flex-col gap-3 text-[0.95rem] leading-relaxed text-texto-suave">
      <template v-for="(b, i) in secao.blocos" :key="i">
        <p v-if="b.tipo === 'paragrafo'">{{ b.texto }}</p>
        <ol v-else-if="b.tipo === 'passos'" class="flex list-decimal flex-col gap-1.5 pl-6 marker:font-semibold marker:text-texto">
          <li v-for="(item, j) in b.itens" :key="j" class="pl-1">{{ item }}</li>
        </ol>
        <ul v-else-if="b.tipo === 'lista'" class="flex list-disc flex-col gap-1.5 pl-6 marker:text-texto-fraco">
          <li v-for="(item, j) in b.itens" :key="j" class="pl-1">{{ item }}</li>
        </ul>
        <Alerta v-else-if="b.tipo === 'dica'" tom="info" titulo="Dica">{{ b.texto }}</Alerta>
      </template>
    </div>
    <div v-if="atalho" class="mt-4">
      <Botao :para="atalho.caminho" variante="secundario" tamanho="sm" data-atalho>
        Abrir {{ atalho.rotulo }} <ArrowRight class="size-4" aria-hidden="true" />
      </Botao>
    </div>
  </section>
</template>
