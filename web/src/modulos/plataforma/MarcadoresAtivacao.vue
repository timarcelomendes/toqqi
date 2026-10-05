<script setup lang="ts">
// Os 4 passos da ativação de uma conta (contatos, envios ligados, primeiro envio, primeira resposta), em ordem, como
// uma barra de 4 pedaços: verde = feito, cinza = a fazer, com "2/4" ao lado. O leitor de tela ouve a frase inteira
// ("Ativação: 2 de 4. Feitos: contatos e envios ligados."); o `title` mostra o mesmo ao passar o mouse.
import { computed } from 'vue'
import type { AtivacaoConta } from '@/api/tipos'
import { PASSOS_ATIVACAO, passosFeitos, rotuloAtivacao } from './visao'

const props = defineProps<{ ativacao: AtivacaoConta | null | undefined }>()

const feitos = computed(() => passosFeitos(props.ativacao))
const rotulo = computed(() => rotuloAtivacao(props.ativacao))
</script>

<template>
  <span class="inline-flex items-center gap-2" role="img" :aria-label="rotulo" :title="rotulo" data-ativacao>
    <span class="flex gap-0.5" aria-hidden="true">
      <span
        v-for="p in PASSOS_ATIVACAO"
        :key="p.chave"
        class="h-2 w-4 rounded-full first:rounded-l-full"
        :class="ativacao?.[p.chave] ? 'bg-sucesso' : 'bg-borda-forte'"
        :data-passo="p.chave"
        :data-feito="ativacao?.[p.chave] ? '' : undefined"
      />
    </span>
    <span class="text-xs font-semibold tabular-nums" :class="feitos === 4 ? 'text-sucesso' : 'text-texto-suave'" aria-hidden="true">{{ feitos }}/4</span>
  </span>
</template>
