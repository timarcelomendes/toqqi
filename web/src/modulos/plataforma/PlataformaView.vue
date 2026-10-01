<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Building2, CalendarPlus, Gift, Plus, Search, Trash2 } from 'lucide-vue-next'
import { mensagemDoErro, plataformaApi, type ContaPlataforma } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { situacaoConta } from '@/utils/rotulos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Campo from '@/components/ui/Campo.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import Tabela, { type Coluna } from '@/components/ui/Tabela.vue'
import ModalExcluirConta from './ModalExcluirConta.vue'
import ModalNovaConta from './ModalNovaConta.vue'

const contas = ref<ContaPlataforma[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const busca = ref('')
const ocupado = ref<string | null>(null)
const modalAberto = ref(false)
const sessao = useSessaoStore()
const excluirAberto = ref(false)
const paraExcluir = ref<ContaPlataforma | null>(null)

/** A conta do próprio superadmin não pode ser excluída por aqui. */
const propria = (c: ContaPlataforma) => !!sessao.conta && String(sessao.conta.id) === String(c.id)

function pedirExclusao(c: ContaPlataforma) {
  paraExcluir.value = c
  excluirAberto.value = true
}

function aoExcluir(c: ContaPlataforma) {
  contas.value = contas.value.filter((x) => String(x.id) !== String(c.id))
}

const colunas: Coluna[] = [
  { chave: 'nome', rotulo: 'Empresa' },
  { chave: 'situacao', rotulo: 'Situação', classe: 'hidden sm:table-cell' },
  { chave: 'teste_ate', rotulo: 'Teste até', classe: 'hidden md:table-cell' },
  { chave: 'usuarios', rotulo: 'Usuários', classe: 'hidden lg:table-cell', alinhar: 'direita' },
  { chave: 'criada_em', rotulo: 'Criada em', classe: 'hidden lg:table-cell' },
  { chave: 'acoes', rotulo: 'Ações', rotuloOculto: true, alinhar: 'direita' },
]

const filtradas = computed(() => {
  const t = busca.value.trim().toLowerCase()
  return t ? contas.value.filter((c) => c.nome.toLowerCase().includes(t)) : contas.value
})

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    contas.value = await plataformaApi.contas()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function substituir(c: ContaPlataforma) {
  const i = contas.value.findIndex((x) => String(x.id) === String(c.id))
  // A resposta pode não trazer todos os campos da listagem (ex.: usuarios): mescla.
  if (i >= 0) contas.value.splice(i, 1, { ...contas.value[i]!, ...c })
}

async function estender(c: ContaPlataforma) {
  const ok = await confirmar({
    titulo: `Dar mais 14 dias para ${c.nome}?`,
    mensagem: c.teste_ate
      ? `O teste vai até ${formatarData(c.teste_ate)}. Os 14 dias contam a partir dessa data.`
      : 'Os 14 dias contam a partir do fim do teste atual.',
    confirmar: '+14 dias',
  })
  if (!ok) return
  ocupado.value = `estender-${c.id}`
  try {
    const r = await plataformaApi.estenderTeste(c.id, 14)
    substituir(r)
    avisar.sucesso(r?.teste_ate ? `Teste de ${c.nome} vai até ${formatarData(r.teste_ate)}.` : 'Teste estendido.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function cortesia(c: ContaPlataforma) {
  const ok = await confirmar({
    titulo: `Dar cortesia para ${c.nome}?`,
    mensagem: 'A conta passa a usar o Toqqi sem cobrança, sem data para acabar.',
    confirmar: 'Dar cortesia',
  })
  if (!ok) return
  ocupado.value = `cortesia-${c.id}`
  try {
    substituir(await plataformaApi.cortesia(c.id))
    avisar.sucesso(`${c.nome} agora é cortesia.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
</script>

<template>
  <CabecalhoPagina titulo="Plataforma" descricao="Contas de clientes do Toqqi. Área exclusiva da nossa equipe.">
    <template #acoes>
      <Botao @click="modalAberto = true"><Plus class="size-4" aria-hidden="true" /> Nova conta</Botao>
    </template>
  </CabecalhoPagina>

  <div class="cartao">
    <div class="flex flex-col gap-3 border-b border-borda p-4 sm:flex-row sm:items-center sm:px-5">
      <Campo v-model="busca" rotulo="Buscar conta" rotulo-oculto tipo="search" placeholder="Buscar por empresa" class="sm:max-w-sm sm:flex-1">
        <template #antes><Search class="size-4" aria-hidden="true" /></template>
      </Campo>
      <p class="text-sm text-texto-fraco sm:ml-auto">{{ filtradas.length }} {{ filtradas.length === 1 ? 'conta' : 'contas' }}</p>
    </div>

    <Alerta v-if="erro" tom="erro" class="m-4">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <Tabela v-else :colunas="colunas" :linhas="filtradas" :chave="(c) => c.id" :carregando="carregando" legenda="Contas da plataforma">
      <template #cel-nome="{ linha: c }">
        <p class="font-semibold text-texto">{{ c.nome }}</p>
        <p class="text-texto-fraco">{{ c.plano || 'Sem plano' }}</p>
        <div class="mt-1 sm:hidden"><Etiqueta :tom="situacaoConta(c.situacao).tom">{{ situacaoConta(c.situacao).rotulo }}</Etiqueta></div>
      </template>
      <template #cel-situacao="{ linha: c }">
        <Etiqueta :tom="situacaoConta(c.situacao).tom">{{ situacaoConta(c.situacao).rotulo }}</Etiqueta>
      </template>
      <template #cel-teste_ate="{ linha: c }">
        <span class="whitespace-nowrap text-texto-suave">{{ formatarData(c.teste_ate) }}</span>
      </template>
      <template #cel-usuarios="{ linha: c }">
        <span class="tabular-nums text-texto-suave">{{ c.usuarios ?? '—' }}</span>
      </template>
      <template #cel-criada_em="{ linha: c }">
        <span class="whitespace-nowrap text-texto-suave">{{ formatarData(c.criada_em) }}</span>
      </template>
      <template #cel-acoes="{ linha: c }">
        <div class="flex flex-wrap justify-end gap-1.5">
          <Botao
            v-if="c.situacao !== 'cortesia'"
            variante="secundario"
            tamanho="sm"
            :carregando="ocupado === `estender-${c.id}`"
            :desabilitado="!!ocupado"
            @click="estender(c)"
          >
            <CalendarPlus class="size-4" aria-hidden="true" /> +14 dias<span class="sr-only"> para {{ c.nome }}</span>
          </Botao>
          <Botao
            v-if="c.situacao !== 'cortesia'"
            variante="fantasma"
            tamanho="sm"
            :carregando="ocupado === `cortesia-${c.id}`"
            :desabilitado="!!ocupado"
            @click="cortesia(c)"
          >
            <Gift class="size-4" aria-hidden="true" /> Cortesia<span class="sr-only"> para {{ c.nome }}</span>
          </Botao>
          <Botao v-if="!propria(c)" variante="perigo-suave" tamanho="sm" :desabilitado="!!ocupado" @click="pedirExclusao(c)">
            <Trash2 class="size-4" aria-hidden="true" /> Excluir<span class="sr-only"> a conta {{ c.nome }}</span>
          </Botao>
        </div>
      </template>
      <template #vazio>
        <EstadoVazio :icone="Building2" :titulo="busca ? 'Nenhuma conta encontrada' : 'Nenhuma conta ainda'" />
      </template>
    </Tabela>
  </div>

  <ModalNovaConta v-model:aberto="modalAberto" @criada="carregar" />
  <ModalExcluirConta v-model:aberto="excluirAberto" :conta="paraExcluir" @excluida="aoExcluir" />
</template>
