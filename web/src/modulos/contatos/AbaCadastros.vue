<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import ListaCadastro from './ListaCadastro.vue'

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const carregando = ref(true)
const erro = ref(false)
const podeEditar = computed(() => sessao.pode('contatos.editar'))
const podeExcluir = computed(() => sessao.pode('contatos.excluir'))

async function carregar() {
  carregando.value = true
  erro.value = false
  try {
    await Promise.all((['grupos', 'segmentos', 'perfis', 'cargos'] as const).map((t) => cadastros.carregar(t)))
  } catch {
    erro.value = true
  } finally {
    carregando.value = false
  }
}
onMounted(carregar)
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="max-w-3xl text-[0.95rem] text-texto-suave">Listas que ajudam a organizar e filtrar seus clientes. Você pode renomear quando quiser: tudo que usa o item é atualizado junto.</p>
    <Carregando v-if="carregando" :linhas="4" />
    <Alerta v-else-if="erro" tom="erro">
      Não conseguimos carregar as listas. <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <div v-else class="grid gap-4 md:grid-cols-2">
      <ListaCadastro tipo="grupos" titulo="Grupos" descricao="Ex.: Rede Sul, Clientes VIP. Juntam empresas parecidas." singular="grupo" usado-por="empresas" :pode-editar="podeEditar" :pode-excluir="podeExcluir" />
      <ListaCadastro tipo="segmentos" titulo="Segmentos" descricao="Ex.: Supermercado, Farmácia. O ramo de cada empresa." singular="segmento" usado-por="empresas" :pode-editar="podeEditar" :pode-excluir="podeExcluir" />
      <ListaCadastro tipo="perfis" titulo="Perfis de contato" descricao="Ex.: Decisor, Influenciador. O papel da pessoa na compra." singular="perfil" usado-por="contatos" :pode-editar="podeEditar" :pode-excluir="podeExcluir" />
      <ListaCadastro tipo="cargos" titulo="Cargos" descricao="Ex.: Comprador, Gerente de loja." singular="cargo" usado-por="contatos" :pode-editar="podeEditar" :pode-excluir="podeExcluir" />
    </div>
  </div>
</template>
