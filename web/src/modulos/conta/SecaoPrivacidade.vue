<script setup lang="ts">
// Cartão "Privacidade" em Minha conta (docs/api-aceite-lgpd.md §3): quando a pessoa aceitou os documentos e os links.
import { computed } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import { textoAceiteRegistrado } from '@/modulos/geral/legal/aceite'
import SecaoCartao from './SecaoCartao.vue'

const sessao = useSessaoStore()
const texto = computed(() => textoAceiteRegistrado(sessao.usuario?.aceite, (v) => formatarDataHora(v)))
</script>

<template>
  <SecaoCartao titulo="Privacidade" descricao="Como o Toqqi trata os seus dados e os dos seus clientes.">
    <p class="text-sm leading-relaxed text-texto-suave" data-teste="aceite">{{ texto }}</p>
    <ul class="mt-4 flex flex-col gap-2 text-sm sm:flex-row sm:gap-6">
      <li><RouterLink to="/termos" target="_blank" class="link">Termos de uso</RouterLink></li>
      <li><RouterLink to="/privacidade" target="_blank" class="link">Política de privacidade</RouterLink></li>
    </ul>
    <p class="mt-4 text-sm text-texto-fraco">
      Dúvidas ou pedidos sobre os seus dados:
      <a class="link break-all" href="mailto:privacidade@toqqi.com">privacidade@toqqi.com</a>.
    </p>
  </SecaoCartao>
</template>
