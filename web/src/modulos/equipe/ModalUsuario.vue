<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Check, Copy, Wand2 } from 'lucide-vue-next'
import { equipeApi, type Perfil, type Usuario } from '@/api'
import { avisar } from '@/composables/avisos'
import { useFormulario } from '@/composables/formulario'
import { useRegrasSenha } from '@/composables/regrasSenha'
import { gerarSenhaForte } from '@/utils/senha'
import { PERFIS } from '@/utils/rotulos'
import { emailValido } from '@/utils/validacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import CampoSenha from '@/components/ui/CampoSenha.vue'
import Modal from '@/components/ui/Modal.vue'

// `perfilInicial`: o perfil já marcado num usuário novo ("Novo usuário" do Adicionar administrador traz Administrador).
const props = defineProps<{ usuario: Usuario | null; ehVoce?: boolean; perfilInicial?: Perfil }>()
const aberto = defineModel<boolean>('aberto', { default: false })
const emit = defineEmits<{ salvo: [Usuario] }>()

const regras = useRegrasSenha()
const { enviando, erroGeral, codigoErro, erros, executar, limpar } = useFormulario()
const novo = computed(() => !props.usuario)
const dados = reactive({ nome: '', email: '', cargo: '', perfil: 'gestor' as Perfil, senha: '' })
const senhaOk = ref(false)
const locais = reactive<Record<string, string | undefined>>({})
const copiado = ref(false)
const perfis = Object.entries(PERFIS) as [Perfil, (typeof PERFIS)[Perfil]][]

watch(aberto, (v) => {
  if (!v) return
  limpar()
  for (const k of Object.keys(locais)) delete locais[k]
  copiado.value = false
  const u = props.usuario
  Object.assign(dados, {
    nome: u?.nome ?? '',
    email: u?.email ?? '',
    cargo: u?.cargo ?? '',
    perfil: u?.perfil ?? props.perfilInicial ?? 'gestor',
    senha: '',
  })
})

function gerar() {
  dados.senha = gerarSenhaForte(regras.value)
  copiado.value = false
}

async function copiar() {
  try {
    await navigator.clipboard.writeText(dados.senha)
    copiado.value = true
    setTimeout(() => (copiado.value = false), 2500)
  } catch {
    avisar.atencao('Não foi possível copiar. Selecione a senha e copie manualmente.')
  }
}

function erro(campo: string) {
  if (locais[campo]) return locais[campo]
  if (erros[campo]) return erros[campo]
  if (campo === 'email' && codigoErro.value === 'email_em_uso') return erroGeral.value
  return undefined
}
const erroTopo = computed(() => (codigoErro.value === 'email_em_uso' && !erros.email ? null : erroGeral.value))

async function salvar() {
  locais.nome = dados.nome.trim() ? undefined : 'Informe o nome.'
  if (novo.value) {
    locais.email = emailValido(dados.email) ? undefined : 'Informe um e-mail válido.'
    locais.senha = senhaOk.value ? undefined : 'A senha ainda não cumpre todas as regras.'
  }
  if (Object.values(locais).some(Boolean)) return

  const u = await executar(() =>
    novo.value
      ? equipeApi.criar({
          nome: dados.nome.trim(),
          email: dados.email.trim(),
          ...(dados.cargo.trim() ? { cargo: dados.cargo.trim() } : {}),
          perfil: dados.perfil,
          senha: dados.senha,
        })
      : equipeApi.atualizar(props.usuario!.id, {
          nome: dados.nome.trim(),
          cargo: dados.cargo.trim() || null,
          ...(props.ehVoce || dados.perfil === props.usuario!.perfil ? {} : { perfil: dados.perfil }),
        }),
  )
  if (!u) return
  emit('salvo', u)
  avisar.sucesso(novo.value ? `${u.nome} já pode entrar no Toqqi.` : 'Alterações salvas.')
  aberto.value = false
}
</script>

<template>
  <Modal
    v-model:aberto="aberto"
    :titulo="novo ? 'Novo usuário' : 'Editar usuário'"
    :descricao="novo ? 'A pessoa entra já ativa, com o e-mail confirmado.' : usuario?.email"
    :bloqueado="enviando"
  >
    <form id="form-usuario" class="flex flex-col gap-4" novalidate @submit.prevent="salvar">
      <Alerta v-if="erroTopo" tom="erro">{{ erroTopo }}</Alerta>
      <Campo v-model="dados.nome" rotulo="Nome" autocomplete="off" obrigatorio data-autofoco :erro="erro('nome')" />
      <Campo v-if="novo" v-model="dados.email" rotulo="E-mail" tipo="email" autocomplete="off" inputmode="email" obrigatorio :erro="erro('email')" />
      <Campo v-model="dados.cargo" rotulo="Cargo" opcional placeholder="Ex.: Analista de atendimento" :erro="erro('cargo')" />

      <fieldset>
        <legend class="mb-2 text-sm font-semibold text-texto">Perfil</legend>
        <p v-if="ehVoce" class="mb-2 text-sm text-texto-fraco">Você não pode mudar o seu próprio perfil.</p>
        <div class="grid gap-2 sm:grid-cols-3">
          <label
            v-for="[valor, p] in perfis"
            :key="valor"
            class="relative flex cursor-pointer flex-col gap-0.5 rounded-xl border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-foco"
            :class="[
              dados.perfil === valor ? 'border-marca bg-marca-suave' : 'border-borda-forte hover:bg-superficie-2',
              ehVoce ? 'cursor-not-allowed opacity-60' : '',
            ]"
          >
            <input v-model="dados.perfil" type="radio" name="perfil" :value="valor" class="sr-only" :disabled="ehVoce" />
            <span class="text-sm font-bold text-texto">{{ p.rotulo }}</span>
            <span class="text-xs text-texto-suave">{{ p.descricao }}</span>
          </label>
        </div>
        <p v-if="erro('perfil')" class="mt-1.5 text-sm font-medium text-erro">{{ erro('perfil') }}</p>
      </fieldset>

      <div v-if="novo" class="flex flex-col gap-2">
        <CampoSenha
          v-model="dados.senha"
          v-model:valida="senhaOk"
          rotulo="Senha inicial"
          autocomplete="new-password"
          com-regras
          :erro="erro('senha')"
        />
        <div class="flex flex-wrap gap-2">
          <Botao variante="secundario" tamanho="sm" @click="gerar"><Wand2 class="size-4" aria-hidden="true" /> Gerar senha forte</Botao>
          <Botao v-if="dados.senha" variante="fantasma" tamanho="sm" @click="copiar">
            <Check v-if="copiado" class="size-4 text-sucesso" aria-hidden="true" />
            <Copy v-else class="size-4" aria-hidden="true" />
            {{ copiado ? 'Copiada!' : 'Copiar senha' }}
          </Botao>
        </div>
        <p class="text-sm text-texto-fraco">Passe a senha para a pessoa por um canal seguro. Ela pode trocar depois em Minha conta.</p>
      </div>
    </form>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="enviando" @click="aberto = false">Cancelar</Botao>
      <Botao tipo="submit" form="form-usuario" :carregando="enviando">{{ novo ? 'Criar usuário' : 'Salvar' }}</Botao>
    </template>
  </Modal>
</template>
