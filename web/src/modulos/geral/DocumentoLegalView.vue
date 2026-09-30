<script setup lang="ts">
import { computed } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import Botao from '@/components/ui/Botao.vue'

const props = defineProps<{ tipo: 'termos' | 'privacidade' }>()
const sessao = useSessaoStore()
const titulo = computed(() => (props.tipo === 'termos' ? 'Termos de uso' : 'Política de privacidade'))
</script>

<template>
  <article class="max-w-none">
    <h1 class="text-2xl font-bold tracking-tight text-texto">{{ titulo }}</h1>
    <p class="mt-2 text-sm text-texto-fraco">Versão provisória</p>
    <div class="mt-6 space-y-4 leading-relaxed text-texto-suave">
      <p>
        O texto completo {{ tipo === 'termos' ? 'dos termos de uso' : 'da política de privacidade' }} do Toqqi está sendo
        finalizado e vai aparecer aqui em breve.
      </p>
      <p v-if="tipo === 'privacidade'">
        Resumo do nosso compromisso: usamos os dados que você e seus clientes informam apenas para fazer o Toqqi funcionar,
        seguindo a LGPD. Não vendemos dados a ninguém.
      </p>
      <p v-else>
        Resumo: você usa o Toqqi para ouvir seus clientes com respeito; nós cuidamos para o serviço funcionar bem e com
        segurança. Dúvidas? Escreva para <a class="link" href="mailto:contato@toqqi.com">contato@toqqi.com</a>.
      </p>
    </div>
    <Botao :para="sessao.logado ? '/inicio' : '/entrar'" variante="secundario" class="mt-8">Voltar</Botao>
  </article>
</template>
