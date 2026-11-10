<script setup lang="ts">
// "E-mails do Toqqi" (etapa 4b): o resumo semanal, o alerta de pico de reclamações e o relatório mensal em PDF, para
// quem acompanha o painel.
// Liga e desliga na hora (PATCH /eu); se não der, volta como estava e avisa.
import { reactive, ref, watch } from 'vue'
import { euApi, mensagemDoErro } from '@/api'
import { avisar } from '@/composables/avisos'
import { useSessaoStore } from '@/stores/sessao'
import Interruptor from '@/components/ui/Interruptor.vue'
import SecaoCartao from './SecaoCartao.vue'

type Preferencia = 'recebe_resumo_semanal' | 'recebe_alertas' | 'recebe_relatorio_mensal'

const sessao = useSessaoStore()
const valores = reactive<Record<Preferencia, boolean>>({ recebe_resumo_semanal: true, recebe_alertas: true, recebe_relatorio_mensal: true })
const salvando = ref<Preferencia | null>(null)

watch(
  () => sessao.usuario,
  (u) => {
    // Sem o campo (servidor antigo), vale o padrão do contrato: ligado.
    valores.recebe_resumo_semanal = u?.recebe_resumo_semanal ?? true
    valores.recebe_alertas = u?.recebe_alertas ?? true
    valores.recebe_relatorio_mensal = u?.recebe_relatorio_mensal ?? true
  },
  { immediate: true },
)

const MENSAGENS: Record<Preferencia, [ligado: string, desligado: string]> = {
  recebe_resumo_semanal: ['Você vai receber o resumo toda segunda-feira.', 'Você não vai mais receber o resumo semanal.'],
  recebe_alertas: ['Você vai receber os alertas de pico de reclamações.', 'Você não vai mais receber os alertas de pico.'],
  recebe_relatorio_mensal: ['Você vai receber o relatório todo dia 1.', 'Você não vai mais receber o relatório mensal.'],
}

async function mudar(campo: Preferencia, valor: boolean) {
  if (salvando.value) return
  const antes = valores[campo]
  valores[campo] = valor
  salvando.value = campo
  try {
    const u = await euApi.atualizar({ [campo]: valor })
    if (u) sessao.atualizarUsuario({ ...sessao.usuario!, ...u, [campo]: u[campo] ?? valor })
    avisar.sucesso(MENSAGENS[campo][valor ? 0 : 1])
  } catch (e) {
    valores[campo] = antes
    avisar.erro(mensagemDoErro(e))
  } finally {
    salvando.value = null
  }
}
</script>

<template>
  <SecaoCartao titulo="E-mails do Toqqi" descricao="Avisos que chegam no seu e-mail sobre o painel da sua empresa.">
    <div class="flex flex-col divide-y divide-borda">
      <Interruptor
        :model-value="valores.recebe_resumo_semanal"
        rotulo="Resumo semanal"
        descricao="Toda segunda-feira de manhã: o NPS da semana, os detratores esperando tratamento, os temas em alta e o que os clientes disseram."
        :desabilitado="salvando !== null"
        class="pb-4"
        @update:model-value="mudar('recebe_resumo_semanal', $event)"
      />
      <Interruptor
        :model-value="valores.recebe_alertas"
        rotulo="Alerta de pico de reclamações"
        descricao="Quando um tema recebe muito mais reclamações que o normal nos últimos 7 dias, com as respostas que causaram o alerta."
        :desabilitado="salvando !== null"
        class="py-4"
        @update:model-value="mudar('recebe_alertas', $event)"
      />
      <Interruptor
        :model-value="valores.recebe_relatorio_mensal"
        rotulo="Relatório mensal (PDF)"
        descricao="No dia 1 de cada mês: o relatório do mês anterior em PDF, com NPS, temas, empresas e planos de ação, para encaminhar a quem precisa."
        :desabilitado="salvando !== null"
        class="pt-4"
        data-pref-relatorio-mensal
        @update:model-value="mudar('recebe_relatorio_mensal', $event)"
      />
    </div>
  </SecaoCartao>
</template>
