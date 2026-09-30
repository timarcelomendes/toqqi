<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Hammer } from 'lucide-vue-next'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Botao from '@/components/ui/Botao.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'

const rota = useRoute()
const titulo = computed(() => rota.meta.titulo ?? 'Em construção')
</script>

<template>
  <CabecalhoPagina :titulo="titulo" />
  <div class="cartao">
    <EstadoVazio
      :icone="Hammer"
      titulo="Em construção"
      :descricao="`Estamos preparando ${titulo} com carinho. Em breve essa área vai estar aqui para você.`"
    >
      <Botao para="/inicio" variante="secundario">Voltar para o início</Botao>
    </EstadoVazio>
  </div>
</template>
