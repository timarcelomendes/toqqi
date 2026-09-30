<script setup lang="ts">
import { ref } from 'vue'
import { UserPlus } from 'lucide-vue-next'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import Botao from '@/components/ui/Botao.vue'
import AbaPermissoes from './AbaPermissoes.vue'
import AbaUsuarios from './AbaUsuarios.vue'

type Aba = 'usuarios' | 'permissoes'
const aba = ref<Aba>('usuarios')
const usuarios = ref<InstanceType<typeof AbaUsuarios> | null>(null)
const abas: { valor: Aba; rotulo: string }[] = [
  { valor: 'usuarios', rotulo: 'Pessoas' },
  { valor: 'permissoes', rotulo: 'Permissões' },
]
</script>

<template>
  <CabecalhoPagina titulo="Equipe" descricao="Quem da sua empresa usa o Toqqi e o que cada perfil pode fazer.">
    <template v-if="aba === 'usuarios'" #acoes>
      <Botao @click="usuarios?.novo()"><UserPlus class="size-4" aria-hidden="true" /> Novo usuário</Botao>
    </template>
  </CabecalhoPagina>

  <Abas v-model="aba" :abas="abas" rotulo="Seções da equipe">
    <AbaUsuarios v-show="aba === 'usuarios'" ref="usuarios" />
    <AbaPermissoes v-show="aba === 'permissoes'" />
  </Abas>
</template>
