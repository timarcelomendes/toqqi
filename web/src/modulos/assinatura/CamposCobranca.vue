<script setup lang="ts">
// Os dados de cobrança (cliente no Asaas): razão social, CPF/CNPJ e telefone com as máscaras de Configurações ›
// Empresa, e o e-mail que recebe as faturas. Usado ao assinar e ao editar os dados.
import Campo from '@/components/ui/Campo.vue'
import { mascaraDocumento, mascaraTelefone } from '@/modulos/configuracoes/empresa'
import { MAX_RAZAO_SOCIAL, type FormCobranca } from './logica'

defineProps<{ erros: Partial<Record<keyof FormCobranca, string | null | undefined>>; desabilitado?: boolean }>()
const form = defineModel<FormCobranca>({ required: true })

function mudar<K extends keyof FormCobranca>(campo: K, valor: string) {
  form.value = { ...form.value, [campo]: valor }
}
</script>

<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
    <Campo
      :model-value="form.razao_social"
      rotulo="Razão social"
      obrigatorio
      :maxlength="MAX_RAZAO_SOCIAL"
      autocomplete="organization"
      dica="Para CPF, o nome completo."
      :erro="erros.razao_social"
      :desabilitado="desabilitado"
      class="sm:col-span-2"
      data-campo="razao_social"
      @update:model-value="mudar('razao_social', $event)"
    />
    <Campo
      :model-value="form.documento"
      rotulo="CPF ou CNPJ"
      obrigatorio
      autocapitalize="characters"
      autocomplete="off"
      spellcheck="false"
      placeholder="00.000.000/0000-00"
      dica="O CNPJ pode ter letras (CNPJ alfanumérico)."
      :mascara="mascaraDocumento"
      :erro="erros.documento"
      :desabilitado="desabilitado"
      data-campo="documento"
      @update:model-value="mudar('documento', $event)"
    />
    <Campo
      :model-value="form.telefone"
      rotulo="Telefone"
      obrigatorio
      tipo="tel"
      inputmode="tel"
      autocomplete="tel-national"
      placeholder="(11) 91234-5678"
      dica="Com DDD."
      :mascara="mascaraTelefone"
      :erro="erros.telefone"
      :desabilitado="desabilitado"
      data-campo="telefone"
      @update:model-value="mudar('telefone', $event)"
    />
    <Campo
      :model-value="form.email_cobranca"
      rotulo="E-mail de cobrança"
      obrigatorio
      tipo="email"
      inputmode="email"
      autocomplete="email"
      maxlength="254"
      placeholder="financeiro@suaempresa.com.br"
      dica="Para onde vão as faturas."
      :erro="erros.email_cobranca"
      :desabilitado="desabilitado"
      class="sm:col-span-2"
      data-campo="email_cobranca"
      @update:model-value="mudar('email_cobranca', $event)"
    />
  </div>
</template>
