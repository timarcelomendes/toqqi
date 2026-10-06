<script setup lang="ts">
// Minha conta › Administradores da conta (GET /conta/administradores, qualquer perfil): quem administra a conta, para
// todos saberem a quem pedir outro perfil, mais permissões ou um novo usuário. O administrador lê que é um deles e tem o
// atalho para Equipe, onde adiciona e remove administradores.
import { computed, onMounted, ref } from 'vue'
import { contaApi, mensagemDoErro, type AdministradorConta } from '@/api'
import { useSessaoStore } from '@/stores/sessao'
import { iniciais } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import SecaoCartao from './SecaoCartao.vue'

const sessao = useSessaoStore()
const admins = ref<AdministradorConta[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)

const descricao = computed(() =>
  sessao.admin
    ? 'Quem pode tudo no Toqqi, inclusive cuidar da equipe e da assinatura. Você é um deles.'
    : 'Fale com um deles para mudar seu perfil, pedir mais permissões ou chamar alguém para a equipe.',
)

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    admins.value = await contaApi.administradores()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <SecaoCartao titulo="Administradores da conta" :descricao="descricao">
    <template #lateral>
      <RouterLink v-if="sessao.pode('equipe.gerenciar')" to="/equipe" class="link mt-2 inline-block text-sm" data-ir-equipe>
        Adicionar ou remover em Equipe
      </RouterLink>
    </template>
    <Carregando v-if="carregando" :linhas="2" rotulo="Carregando os administradores" />
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <p v-else-if="!admins.length" class="text-sm text-texto-suave">Nenhum administrador ativo agora. Fale com o suporte do Toqqi.</p>
    <ul v-else class="flex flex-col gap-4" aria-label="Administradores da conta">
      <li v-for="a in admins" :key="a.id" class="flex items-center gap-3" data-admin-conta>
        <span class="flex size-9 shrink-0 items-center justify-center rounded-full bg-marca-suave text-xs font-bold text-marca-texto" aria-hidden="true">
          {{ iniciais(a.nome) }}
        </span>
        <div class="min-w-0 text-sm">
          <p class="truncate font-semibold text-texto">
            {{ a.nome }} <span v-if="a.voce" class="font-normal text-texto-fraco">(você)</span>
          </p>
          <p v-if="a.cargo" class="truncate text-texto-suave">{{ a.cargo }}</p>
          <a v-if="a.email && !a.voce" :href="`mailto:${a.email}`" class="link block truncate">{{ a.email }}</a>
          <p v-else-if="a.email" class="truncate text-texto-fraco">{{ a.email }}</p>
        </div>
      </li>
    </ul>
  </SecaoCartao>
</template>
