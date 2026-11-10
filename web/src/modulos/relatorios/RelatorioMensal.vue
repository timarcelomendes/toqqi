<script setup lang="ts">
// Relatório mensal em PDF: o botão no cabeçalho de Relatórios abre a janela com o mês (os últimos 12 meses e o atual;
// padrão: o mês anterior) e baixa o PDF de GET /relatorios/mensal.pdf. No dia 1, o Toqqi também manda o do mês anterior
// por e-mail (Minha conta › E-mails do Toqqi).
import { computed, ref } from 'vue'
import { FileText } from 'lucide-vue-next'
import { mensagemDoErro, relatoriosApi } from '@/api'
import { avisar } from '@/composables/avisos'
import Botao from '@/components/ui/Botao.vue'
import Modal from '@/components/ui/Modal.vue'
import Selecao from '@/components/ui/Selecao.vue'
import { mesesDoRelatorio } from './logica'

const props = defineProps<{ hoje: string }>()

const aberto = ref(false)
const baixando = ref(false)
const opcoes = computed(() => mesesDoRelatorio(props.hoje))
const mes = ref('')

function abrir() {
  mes.value = opcoes.value[1]?.valor ?? opcoes.value[0]!.valor
  aberto.value = true
}

async function baixar() {
  if (baixando.value) return
  baixando.value = true
  try {
    await relatoriosApi.baixarMensal(mes.value)
    aberto.value = false
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    baixando.value = false
  }
}
</script>

<template>
  <Botao variante="secundario" data-relatorio-mensal @click="abrir">
    <FileText class="size-4" aria-hidden="true" /> Relatório mensal (PDF)
  </Botao>
  <Modal
    v-model:aberto="aberto"
    titulo="Relatório mensal em PDF"
    descricao="NPS, respostas, temas, empresas, planos de ação e o que os clientes disseram no mês. Só empresas ativas."
    tamanho="sm"
    :bloqueado="baixando"
  >
    <div class="flex flex-col gap-3">
      <Selecao v-model="mes" rotulo="Mês" :opcoes="opcoes" data-mes-relatorio />
      <p class="text-sm text-texto-suave">
        No dia 1 de cada mês, o Toqqi também manda o relatório do mês anterior por e-mail. Para não receber, desligue em
        <RouterLink to="/minha-conta" class="link" @click="aberto = false">Minha conta</RouterLink>.
      </p>
    </div>
    <template #rodape>
      <Botao variante="secundario" :desabilitado="baixando" @click="aberto = false">Cancelar</Botao>
      <Botao :carregando="baixando" data-baixar-mensal @click="baixar">Baixar PDF</Botao>
    </template>
  </Modal>
</template>
