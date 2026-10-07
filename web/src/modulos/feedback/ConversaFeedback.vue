<script setup lang="ts">
// A conversa de um feedback, do ponto de vista de quem olha (`perspectiva`): as próprias mensagens à direita, as do
// outro lado à esquerda; a equipe sempre com o selo "Equipe Toqqi". Mudança de situação sem texto vira uma linha no
// meio ("Situação: Planejado"); com texto, a situação nova aparece embaixo da mensagem. As imagens carregam pelo
// `carregarImagem` (blob com o token).
import type { MensagemFeedback } from '@/api/feedback'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import ImagemFeedback from './ImagemFeedback.vue'
import { infoSituacao, rotuloQuando } from './logica'

const props = defineProps<{
  mensagens: MensagemFeedback[]
  perspectiva: 'usuario' | 'equipe'
  carregarImagem: (imagemId: number, sinal: AbortSignal) => Promise<Blob>
}>()

function minha(m: MensagemFeedback) {
  return m.autor === props.perspectiva
}

function nome(m: MensagemFeedback) {
  if (m.autor === 'usuario') {
    if (props.perspectiva === 'usuario') return 'Você'
    return m.autor_nome ?? 'Pessoa que saiu da conta'
  }
  return m.autor_nome || 'Equipe Toqqi'
}

function soMudanca(m: MensagemFeedback) {
  return !m.texto && !m.imagens.length && !!m.situacao
}
</script>

<template>
  <ol class="flex flex-col gap-5" aria-label="Conversa" data-conversa>
    <li v-for="m in mensagens" :key="m.id" :data-mensagem="m.id" :data-autor="m.autor">
      <div v-if="soMudanca(m)" class="flex items-center gap-3 text-xs text-texto-fraco" data-mudanca>
        <span class="h-px flex-1 bg-borda" aria-hidden="true" />
        <span class="flex flex-wrap items-center justify-center gap-1.5 text-center">
          <span>{{ m.autor_nome || 'Equipe Toqqi' }} mudou a situação para</span>
          <Etiqueta :tom="infoSituacao(m.situacao!).tom">{{ infoSituacao(m.situacao!).rotulo }}</Etiqueta>
          <span>· <time :datetime="m.criado_em">{{ rotuloQuando(m.criado_em) }}</time></span>
        </span>
        <span class="h-px flex-1 bg-borda" aria-hidden="true" />
      </div>
      <div v-else class="flex flex-col" :class="minha(m) ? 'items-end' : 'items-start'">
        <p class="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-texto-fraco">
          <span class="font-semibold text-texto" data-autor-nome>{{ nome(m) }}</span>
          <Etiqueta v-if="m.autor === 'equipe'" tom="marca">Equipe Toqqi</Etiqueta>
          <time :datetime="m.criado_em">{{ rotuloQuando(m.criado_em) }}</time>
        </p>
        <div
          class="flex max-w-[min(40rem,100%)] flex-col gap-3 rounded-2xl px-4 py-3"
          :class="minha(m) ? 'rounded-tr-md bg-marca-suave' : 'rounded-tl-md border border-borda bg-superficie'"
        >
          <p v-if="m.texto" class="whitespace-pre-wrap text-[0.95rem] leading-relaxed text-texto [overflow-wrap:anywhere]" data-texto-mensagem>{{ m.texto }}</p>
          <ul v-if="m.imagens.length" class="grid w-64 max-w-full grid-cols-2 gap-2 sm:w-80" :class="m.imagens.length === 1 ? 'grid-cols-1' : ''" aria-label="Imagens">
            <li v-for="i in m.imagens" :key="i.id">
              <ImagemFeedback :carregar="(sinal) => carregarImagem(i.id, sinal)" :nome="i.nome" />
            </li>
          </ul>
        </div>
        <p v-if="m.situacao" class="mt-1.5 flex items-center gap-1.5 text-xs text-texto-fraco">
          Situação: <Etiqueta :tom="infoSituacao(m.situacao).tom">{{ infoSituacao(m.situacao).rotulo }}</Etiqueta>
        </p>
      </div>
    </li>
  </ol>
</template>
