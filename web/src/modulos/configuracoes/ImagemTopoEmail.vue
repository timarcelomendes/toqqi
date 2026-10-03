<script setup lang="ts">
// Imagem de topo dos e-mails (Configurações › Envios › Visual dos e-mails): nenhuma, ou a miniatura da escolhida com
// "Trocar" e "Remover". "Escolher imagem" e "Trocar" abrem o banco de imagens. É sempre o mesmo botão (só o texto
// muda), para o foco voltar a ele quando o banco fecha; ao remover, o foco também vai para ele.
import { computed, nextTick, ref, useId } from 'vue'
import { Images, X } from 'lucide-vue-next'
import type { Id, ImagemBanco, ImagemTopoEmail } from '@/api/tipos'
import Botao from '@/components/ui/Botao.vue'
import BancoImagens from './BancoImagens.vue'
import { DICA_TAMANHO_TOPO, mesmaImagem, paraImagemTopo } from './bancoImagens'
import { textoDimensoes } from './visualEmail'

// `salva`: a imagem de topo que está salva (a que a API não deixa excluir, porque está em uso).
const props = defineProps<{ erro?: string | null; salva?: ImagemTopoEmail | null }>()
const imagem = defineModel<ImagemTopoEmail | null>({ default: null })
const id = useId()
const bancoAberto = ref(false)
const gatilho = ref<HTMLElement | null>(null)
const dimensoes = computed(() => (imagem.value ? textoDimensoes(imagem.value.largura, imagem.value.altura) : null))

function focarGatilho() {
  gatilho.value?.querySelector<HTMLElement>('button')?.focus()
}

function escolher(i: ImagemBanco) {
  imagem.value = paraImagemTopo(i)
}

/** A imagem escolhida (e ainda não salva) foi excluída no banco: volta a que está salva (ou nenhuma), para salvar
 *  depois não tirar dos e-mails uma imagem que a pessoa não pediu para tirar. */
function aoExcluir(excluida: Id) {
  if (!mesmaImagem(imagem.value, excluida)) return
  imagem.value = props.salva && !mesmaImagem(props.salva, excluida) ? props.salva : null
}

async function remover() {
  imagem.value = null
  await nextTick()
  focarGatilho()
}
</script>

<template>
  <div class="flex flex-col gap-2" role="group" :aria-labelledby="`${id}-rotulo`" data-imagem-topo>
    <p :id="`${id}-rotulo`" class="text-sm font-semibold text-texto">Imagem de topo <span class="font-normal text-texto-fraco">(opcional)</span></p>
    <figure v-if="imagem" class="flex flex-col gap-1.5">
      <!-- Fundo branco: é o fundo do e-mail -->
      <div class="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <img :src="imagem.url" alt="Imagem de topo escolhida" class="block max-h-40 w-full object-contain" data-imagem-topo-escolhida />
      </div>
      <figcaption v-if="dimensoes" class="text-xs text-texto-fraco">{{ dimensoes }}</figcaption>
    </figure>
    <p v-else class="rounded-xl border border-dashed border-borda-forte px-4 py-5 text-center text-sm text-texto-suave" data-sem-imagem-topo>
      Nenhuma imagem. O e-mail começa pelo logo e pelo texto.
    </p>
    <div class="flex flex-wrap gap-2">
      <span ref="gatilho" class="contents">
        <Botao variante="secundario" :aria-describedby="`${id}-dica`" data-abrir-banco @click="bancoAberto = true">
          <Images class="size-4" aria-hidden="true" />
          <template v-if="imagem">Trocar<span class="sr-only"> a imagem de topo</span></template>
          <template v-else>Escolher imagem<span class="sr-only"> de topo</span></template>
        </Botao>
      </span>
      <Botao v-if="imagem" variante="perigo-suave" data-remover-imagem @click="remover">
        <X class="size-4" aria-hidden="true" /> Remover<span class="sr-only"> a imagem de topo</span>
      </Botao>
    </div>
    <p :id="`${id}-dica`" class="text-sm text-texto-fraco">Aparece no topo do e-mail, na largura toda, sem link. {{ DICA_TAMANHO_TOPO }}</p>
    <p v-if="erro" class="text-sm font-medium text-erro" data-erro-imagem-topo>{{ erro }}</p>
    <BancoImagens v-model:aberto="bancoAberto" :escolhida-id="imagem?.id ?? null" @escolher="escolher" @excluida="aoExcluir" />
  </div>
</template>
