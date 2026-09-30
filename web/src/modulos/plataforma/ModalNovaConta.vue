<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Wand2 } from 'lucide-vue-next'
import { plataformaApi } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useRegrasSenha } from '@/composables/regrasSenha'
import { gerarSenhaForte } from '@/utils/senha'
import { emailValido } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import Modal from '@/components/ui/Modal.vue'

const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ criada: [] }>()
const regras = useRegrasSenha()
const { enviando, erroGeral, erros, executar, limpar } = useFormulario()
const dados = reactive({ empresa: '', admin_nome: '', admin_email: '', admin_senha: '', situacao: 'teste' as 'teste' | 'cortesia' })
const senhaOk = ref(false)
const locais = reactive<Record<string, string | undefined>>({})

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  Object.assign(dados, { empresa: '', admin_nome: '', admin_email: '', admin_senha: '', situacao: 'teste' })
})

function erro(c: string) {
  return locais[c] ?? erros[c]
}

async function salvar() {
  locais.empresa = dados.empresa.trim() ? undefined : 'Informe o nome da empresa.'
  locais.admin_nome = dados.admin_nome.trim() ? undefined : 'Informe o nome do administrador.'
  locais.admin_email = emailValido(dados.admin_email) ? undefined : 'Informe um e-mail válido.'
  locais.admin_senha = senhaOk.value ? undefined : 'A senha ainda não cumpre todas as regras.'
  if (Object.values(locais).some(Boolean)) return
  const r = await executar(async () => {
    await plataformaApi.criarConta({
      empresa: dados.empresa.trim(),
      admin_nome: dados.admin_nome.trim(),
      admin_email: dados.admin_email.trim(),
      admin_senha: dados.admin_senha,
      situacao: dados.situacao,
    })
    return true
  })
  if (!r) return
  avisar.sucesso(`Conta ${dados.empresa.trim()} criada.`)
  emit('criada')
  aberto.value = false
}
</script>

<template>
  <Modal v-model:aberto="aberto" titulo="Nova conta" descricao="Cria a empresa e o primeiro administrador." :bloqueado="enviando" tamanho="lg">
    <form id="form-nova-conta" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroGeral" tom="erro">{{ erroGeral }}</Alerta>
      <Campo v-model="dados.empresa" rotulo="Empresa" obrigatorio data-autofoco :erro="erro('empresa')" />
      <div class="grid gap-4 sm:grid-cols-2">
        <Campo v-model="dados.admin_nome" rotulo="Nome do administrador" obrigatorio :erro="erro('admin_nome')" />
        <Campo v-model="dados.admin_email" rotulo="E-mail do administrador" tipo="email" inputmode="email" autocomplete="off" obrigatorio :erro="erro('admin_email')" />
      </div>
      <div class="flex flex-col gap-2">
        <CampoSenha v-model="dados.admin_senha" v-model:valida="senhaOk" rotulo="Senha inicial" autocomplete="new-password" com-regras :erro="erro('admin_senha')" />
        <div>
          <Botao variante="secundario" tamanho="sm" @click="dados.admin_senha = gerarSenhaForte(regras)">
            <Wand2 class="size-4" aria-hidden="true" /> Gerar senha forte
          </Botao>
        </div>
      </div>
      <fieldset>
        <legend class="mb-2 text-sm font-semibold text-texto">Tipo de conta</legend>
        <div class="grid gap-2 sm:grid-cols-2">
          <label
            v-for="op in [
              { valor: 'teste' as const, rotulo: 'Teste grátis', desc: '14 dias para conhecer o Toqqi.' },
              { valor: 'cortesia' as const, rotulo: 'Cortesia', desc: 'Sem cobrança e sem data para acabar.' },
            ]"
            :key="op.valor"
            class="flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
            :class="dados.situacao === op.valor ? 'border-marca bg-marca-suave' : 'border-borda-forte hover:bg-superficie-2'"
          >
            <input v-model="dados.situacao" type="radio" name="situacao" :value="op.valor" class="sr-only" />
            <span class="text-sm font-bold text-texto">{{ op.rotulo }}</span>
            <span class="text-xs text-texto-suave">{{ op.desc }}</span>
          </label>
        </div>
        <p v-if="erro('situacao')" class="mt-1.5 text-sm font-medium text-erro">{{ erro('situacao') }}</p>
      </fieldset>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-nova-conta" :carregando="enviando">Criar conta</Botao>
    </template>
  </Modal>
</template>
