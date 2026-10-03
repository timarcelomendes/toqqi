<script setup lang="ts">
// Como o e-mail chega para o cliente (aparência aproximada; o layout final é da plataforma), na mesma ordem do e-mail
// de verdade (docs/api-etapa-5e.md §2.2): faixa na cor de destaque → logo → imagem de topo → textos → bloco da nota →
// assinatura → rodapé da conta e as duas linhas fixas. O e-mail é sempre claro, como numa caixa de entrada: a prévia
// não acompanha o modo escuro do site. Tudo é texto (o Vue escapa): nada de HTML vindo da conta.
import { computed } from 'vue'
import type { CorNota, PreviaEmail } from './mensagens'
import { LARGURA_IMAGEM_TOPO, alturaImagemTopo } from './visualEmail'

const props = withDefaults(defineProps<{ previa: PreviaEmail; empresa?: string }>(), { empresa: '' })

// As cores dos botões de nota do e-mail de verdade: #dc2626, #d97706 e #16a34a, com o número em branco.
const cores: Record<CorNota, string> = {
  vermelho: 'bg-red-600 text-white',
  amarelo: 'bg-amber-600 text-white',
  verde: 'bg-green-600 text-white',
}
const alturaTopo = computed(() => {
  const i = props.previa.imagemTopo
  return i ? (alturaImagemTopo(i.largura, i.altura) ?? undefined) : undefined
})
</script>

<template>
  <article class="overflow-hidden rounded-2xl border border-borda bg-white text-slate-900 shadow-sm" aria-label="Prévia do e-mail" :data-qual="previa.qual">
    <header class="border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm">
      <p class="truncate text-slate-600"><span class="text-slate-500">De:</span> <strong class="font-semibold text-slate-800">{{ previa.de }}</strong></p>
      <p v-if="previa.responderPara" class="truncate text-slate-600"><span class="text-slate-500">Responder para:</span> {{ previa.responderPara }}</p>
      <p class="mt-1 break-words font-bold text-slate-900" data-teste="assunto">{{ previa.assunto || '(sem assunto)' }}</p>
    </header>
    <!-- O fundo cinza do e-mail e o cartão branco (até 600 px) no meio, como chega na caixa de entrada -->
    <div class="bg-[#f3f4f6] p-2 sm:p-3">
      <div class="mx-auto max-w-[600px] overflow-hidden rounded-lg bg-white" data-teste="cartao">
        <!-- `data-cor-faixa` (e não `data-cor`, que marca os botões de nota) -->
        <div class="h-1" :style="{ backgroundColor: previa.cor }" aria-hidden="true" data-teste="faixa" :data-cor-faixa="previa.cor" />
        <div v-if="previa.logo" class="flex justify-center px-4 pt-6 sm:px-6" data-teste="logo">
          <img :src="previa.logo" :alt="empresa" class="h-12 max-w-full object-contain" />
        </div>
        <div v-if="previa.imagemTopo" class="px-4 pt-6 sm:px-6" data-teste="imagem-topo">
          <span class="sr-only">Imagem de topo.</span>
          <!-- Como no e-mail: largura toda do cartão (544 px), altura proporcional, sem texto alternativo e sem link -->
          <img :src="previa.imagemTopo.url" alt="" :width="LARGURA_IMAGEM_TOPO" :height="alturaTopo" class="block h-auto w-full max-w-full" />
        </div>
        <div class="flex flex-col gap-3 px-4 py-5 text-[0.95rem] leading-relaxed sm:px-6" data-teste="corpo">
          <p v-for="(p, i) in previa.paragrafos" :key="i" class="whitespace-pre-line break-words">{{ p }}</p>

          <div v-if="previa.bloco" class="mt-2 rounded-xl bg-slate-50 p-3 sm:p-4" data-teste="bloco-nota">
            <p v-if="previa.bloco.tipo !== 'botao' && previa.bloco.titulo" class="mb-3 text-center text-base font-bold text-slate-900" data-teste="pergunta">
              {{ previa.bloco.titulo }}
            </p>
            <template v-if="previa.bloco.tipo === 'nps'">
              <p class="sr-only">Botões de 0 a 10 para a pessoa escolher a nota: 0 a 6 em vermelho, 7 e 8 em amarelo, 9 e 10 em verde.</p>
              <div class="grid grid-cols-11 gap-1" aria-hidden="true">
                <span
                  v-for="b in previa.bloco.botoes"
                  :key="b.nota"
                  class="flex aspect-square min-w-0 items-center justify-center rounded-md text-xs font-bold sm:text-sm"
                  :class="cores[b.cor]"
                  :data-cor="b.cor"
                >{{ b.nota }}</span>
              </div>
              <div class="mt-1.5 flex justify-between text-xs text-slate-500" aria-hidden="true">
                <span>{{ previa.bloco.rotuloMin }}</span><span>{{ previa.bloco.rotuloMax }}</span>
              </div>
            </template>
            <template v-else-if="previa.bloco.tipo === 'csat'">
              <p class="sr-only">Botões de 1 a 5 para a pessoa escolher a nota.</p>
              <div class="mx-auto grid max-w-xs grid-cols-5 gap-2" aria-hidden="true">
                <span v-for="b in previa.bloco.botoes" :key="b.nota" class="flex h-10 items-center justify-center rounded-lg font-bold" :class="cores[b.cor]" :data-cor="b.cor">{{ b.nota }}</span>
              </div>
              <div class="mx-auto mt-1.5 flex max-w-xs justify-between text-xs text-slate-500" aria-hidden="true">
                <span>{{ previa.bloco.rotuloMin }}</span><span>{{ previa.bloco.rotuloMax }}</span>
              </div>
            </template>
            <div v-else class="flex justify-center">
              <span
                class="rounded-md px-6 py-3 text-base font-bold"
                :style="{ backgroundColor: previa.cor, color: previa.corTextoBotao }"
                data-teste="botao-responder"
                :data-cor-texto="previa.corTextoBotao"
              >{{ previa.bloco.texto }}</span>
            </div>
          </div>

          <div v-if="previa.assinatura.length" class="mt-2 flex flex-col gap-3 text-[#4b5563]" data-teste="assinatura">
            <p v-for="(p, i) in previa.assinatura" :key="i" class="whitespace-pre-line break-words">{{ p }}</p>
          </div>
        </div>
        <footer class="border-t border-slate-200 px-4 py-3 text-xs leading-relaxed text-slate-500 sm:px-6" data-teste="rodape">
          <p v-if="previa.rodapeConta" class="mb-1.5 whitespace-pre-line break-words" data-teste="rodape-conta">{{ previa.rodapeConta }}</p>
          <p data-teste="rodape-fixo">{{ previa.rodape }}</p>
          <p class="mt-1 underline" data-teste="descadastro">{{ previa.descadastro }}</p>
        </footer>
      </div>
    </div>
  </article>
</template>
