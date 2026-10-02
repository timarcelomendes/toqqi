<script setup lang="ts" generic="C">
// Botão de gerar o resumo ou o parecer (etapa 5d): "Gerar resumo" / "Gerar de novo", ocupado enquanto gera e com a
// contagem ("Gerar de novo em 25 s") até poder gerar de novo. Continua no Tab quando desliga (aria-disabled): o foco
// não cai no <body> ao clicar. O nome que o leitor de tela lê é fixo: a contagem fica fora dele (aria-hidden), senão o
// leitor anunciaria cada segundo enquanto o botão tem o foco; o fim da espera é anunciado à parte ("Já dá para gerar de novo.").
import { Sparkles } from 'lucide-vue-next'
import Botao from '@/components/ui/Botao.vue'
import type { GeracaoIa } from './usarGeracaoIa'

withDefaults(defineProps<{ geracao: GeracaoIa<C>; variante?: 'primario' | 'secundario' }>(), { variante: 'secundario' })
</script>

<template>
  <Botao
    v-if="geracao.mostrarBotao"
    :id="geracao.idBotao"
    :variante="variante"
    :carregando="geracao.gerando"
    :desabilitado="!geracao.podeGerar"
    focavel
    data-gerar-ia
    @click="geracao.gerar()"
  >
    <Sparkles v-if="!geracao.gerando" class="size-4" aria-hidden="true" />
    <span class="tabular-nums">{{ geracao.rotuloBotao }}<span v-if="geracao.segundos > 0" aria-hidden="true" data-contagem> em {{ geracao.segundos }} s</span></span>
  </Botao>
</template>
