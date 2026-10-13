<script setup lang="ts">
// Plano Grátis (docs/api-plano-gratis.md): só entram os primeiros usuários (1, o administrador mais antigo); o aviso
// diz isso e, com 1 usuário, "Novo usuário" fica desligado (a API recusa com 403 `recurso_do_plano`).
import { computed, ref } from 'vue'
import { UserPlus } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import AvisoPlanoGratis from '@/components/app/AvisoPlanoGratis.vue'
import Abas from '@/components/ui/Abas.vue'
import Botao from '@/components/ui/Botao.vue'
import { textoUsuarios } from '@/modulos/assinatura/gratis'
import AbaPermissoes from './AbaPermissoes.vue'
import AbaUsuarios from './AbaUsuarios.vue'

type Aba = 'usuarios' | 'permissoes'
const aba = ref<Aba>('usuarios')
const usuarios = ref<InstanceType<typeof AbaUsuarios> | null>(null)
const abas: { valor: Aba; rotulo: string }[] = [
  { valor: 'usuarios', rotulo: 'Pessoas' },
  { valor: 'permissoes', rotulo: 'Permissões' },
]
const sessao = useSessaoStore()
const gratis = computed(() => sessao.conta?.gratis ?? null)
const textoGratis = computed(() =>
  gratis.value
    ? gratis.value.usuarios === 1
      ? 'No plano Grátis, só o administrador mais antigo entra no Toqqi. As outras pessoas da equipe voltam a entrar quando a conta assinar um plano a partir do Essencial.'
      : `No plano Grátis, entram ${textoUsuarios(gratis.value.usuarios)}: os mais antigos, administradores primeiro. Para ter mais pessoas, assine um plano a partir do Essencial.`
    : '',
)
</script>

<template>
  <CabecalhoPagina titulo="Equipe" descricao="Quem da sua empresa usa o Toqqi e o que cada perfil pode fazer.">
    <template v-if="aba === 'usuarios'" #acoes>
      <Botao :desabilitado="gratis?.usuarios === 1" @click="usuarios?.novo()"><UserPlus class="size-4" aria-hidden="true" /> Novo usuário</Botao>
    </template>
  </CabecalhoPagina>

  <AvisoPlanoGratis v-if="gratis" :texto="textoGratis" :recurso="false" class="mb-4" data-gratis-equipe />

  <Abas v-model="aba" :abas="abas" rotulo="Seções da equipe">
    <AbaUsuarios v-show="aba === 'usuarios'" ref="usuarios" />
    <AbaPermissoes v-show="aba === 'permissoes'" />
  </Abas>
</template>
