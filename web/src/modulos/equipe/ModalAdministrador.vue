<script setup lang="ts">
// Equipe › Pessoas › "Adicionar administrador": escolher alguém ativo da equipe que ainda não é administrador.
// Sem ninguém para escolher, o botão leva ao Novo usuário (que já abre com o perfil Administrador).
import { ref, watch } from 'vue'
import { equipeApi, type Usuario } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { iniciais, PERFIS } from '@/utils/rotulos'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Modal from '@/components/ui/Modal.vue'

const props = defineProps<{ candidatos: Usuario[] }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [Usuario]; novo: [] }>()

const { enviando, erroGeral, executar, limpar } = useFormulario()
const escolhido = ref('')

watch(aberto, (v) => {
  if (!v) return
  limpar()
  escolhido.value = props.candidatos.length === 1 ? String(props.candidatos[0]!.id) : ''
})

async function salvar() {
  const alvo = props.candidatos.find((u) => String(u.id) === escolhido.value)
  if (!alvo) return
  const u = await executar(() => equipeApi.atualizar(alvo.id, { perfil: 'admin' }))
  if (!u) return
  emit('salvo', u)
  avisar.sucesso(`${u.nome} agora administra a conta.`)
  aberto.value = false
}

function novoUsuario() {
  aberto.value = false
  emit('novo')
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    titulo="Adicionar administrador"
    descricao="A pessoa passa a poder tudo no Toqqi, inclusive cuidar da equipe, das configurações e da assinatura."
    :bloqueado="enviando"
  >
    <form id="form-administrador" class="flex flex-col gap-3" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <fieldset v-if="candidatos.length">
        <legend class="mb-2 text-sm font-semibold text-texto">Quem vai administrar a conta</legend>
        <div class="flex max-h-80 flex-col gap-2 overflow-y-auto p-0.5">
          <label
            v-for="u in candidatos"
            :key="u.id"
            class="flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
            :class="escolhido === String(u.id) ? 'border-marca bg-marca-suave' : 'border-borda-forte hover:bg-superficie-2'"
            data-candidato-admin
          >
            <input v-model="escolhido" type="radio" name="novo-administrador" :value="String(u.id)" class="sr-only" />
            <span class="flex size-9 shrink-0 items-center justify-center rounded-full bg-superficie-2 text-xs font-bold text-texto-suave" aria-hidden="true">
              {{ iniciais(u.nome) }}
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate font-semibold text-texto">{{ u.nome }}</span>
              <span class="block truncate text-sm text-texto-fraco">{{ u.email }} · hoje {{ PERFIS[u.perfil]?.rotulo ?? u.perfil }}</span>
            </span>
          </label>
        </div>
      </fieldset>
      <p v-else class="text-sm text-texto-suave" data-sem-candidatos>
        Ninguém da equipe pode virar administrador agora: só quem está ativo e ainda não administra a conta. Para chamar
        alguém de fora, crie um novo usuário, que já vem com o perfil Administrador.
      </p>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao v-if="candidatos.length" tipo="submit" form="form-administrador" :carregando="enviando" :desabilitado="!escolhido">
        Tornar administrador
      </Botao>
      <Botao v-else @click="novoUsuario">Novo usuário</Botao>
    </template>
  </Modal>
</template>
