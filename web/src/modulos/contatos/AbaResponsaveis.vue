<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Mail, MoreHorizontal, Pencil, Send, Trash2, UserRoundCog } from 'lucide-vue-next'
import { mensagemDoErro, responsaveisApi, type Id, type Responsavel } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useCadastrosStore } from '@/stores/cadastros'
import { useSessaoStore } from '@/stores/sessao'
import { plural } from '@/utils/formatos'
import { iniciais } from '@/utils/rotulos'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import ModalResponsavel from './ModalResponsavel.vue'

const sessao = useSessaoStore()
const cadastros = useCadastrosStore()
const carregando = ref(true)
const erro = ref<string | null>(null)
const testando = ref<Id | null>(null)
const modalAberto = ref(false)
const emEdicao = ref<Responsavel | null>(null)
const fotoQuebrada = ref(new Set<string>())

const lista = computed(() => cadastros.listas.responsaveis)
const podeEditar = computed(() => sessao.pode('contatos.editar'))
const podeExcluir = computed(() => sessao.pode('contatos.excluir'))

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    await cadastros.carregar('responsaveis')
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function novo() {
  emEdicao.value = null
  modalAberto.value = true
}
function editar(r: Responsavel) {
  emEdicao.value = r
  modalAberto.value = true
}

async function testar(r: Responsavel) {
  testando.value = r.id
  try {
    const resp = await responsaveisApi.testarTeams(r.id)
    avisar.sucesso(resp?.mensagem || `Mensagem de teste enviada para o Teams de ${r.nome}.`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e), 'O Teams não aceitou o teste')
  } finally {
    testando.value = null
  }
}

async function excluir(r: Responsavel) {
  const ok = await confirmar({
    titulo: `Excluir ${r.nome}?`,
    mensagem:
      r.empresas > 0
        ? `${plural(r.empresas, 'empresa fica', 'empresas ficam')} sem responsável. Os contatos e respostas continuam. Não dá para desfazer.`
        : 'A pessoa sai da lista de responsáveis. Não dá para desfazer.',
    confirmar: 'Excluir',
    perigo: true,
  })
  if (!ok) return
  try {
    await responsaveisApi.excluir(r.id)
    cadastros.tirarResponsavel(r.id)
    avisar.sucesso(`${r.nome} foi excluído(a).`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  }
}

onMounted(carregar)
defineExpose({ novo })
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="max-w-3xl text-[0.95rem] text-texto-suave">
      Responsáveis são as pessoas da sua empresa que cuidam de cada carteira de clientes. Eles não precisam ter acesso ao Toqqi.
    </p>
    <Carregando v-if="carregando && !lista.length" :linhas="3" />
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <div v-else-if="!lista.length" class="cartao">
      <EstadoVazio :icone="UserRoundCog" titulo="Nenhum responsável ainda" descricao="Cadastre quem cuida dos clientes para filtrar resultados por carteira e avisar a pessoa certa.">
        <Botao v-if="podeEditar" @click="novo">Novo responsável</Botao>
      </EstadoVazio>
    </div>
    <ul v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <li v-for="r in lista" :key="String(r.id)" class="cartao flex flex-col gap-4 p-5">
        <div class="flex items-start gap-3">
          <img
            v-if="r.foto_url && !fotoQuebrada.has(String(r.id))"
            :src="r.foto_url"
            alt=""
            class="size-12 shrink-0 rounded-full object-cover"
            loading="lazy"
            @error="fotoQuebrada.add(String(r.id))"
          />
          <span v-else class="flex size-12 shrink-0 items-center justify-center rounded-full bg-marca-suave text-sm font-bold text-marca-texto" aria-hidden="true">{{ iniciais(r.nome) }}</span>
          <div class="min-w-0 flex-1">
            <h3 class="truncate font-bold text-texto">{{ r.nome }}</h3>
            <p class="truncate text-sm text-texto-suave">{{ r.funcao || 'Sem função informada' }}</p>
          </div>
          <MenuSuspenso v-if="podeEditar || podeExcluir" :rotulo="`Ações para ${r.nome}`">
            <template #gatilho="{ props }">
              <button v-bind="props" type="button" class="-mr-2 -mt-1 flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto">
                <MoreHorizontal class="size-5" aria-hidden="true" />
              </button>
            </template>
            <ItemMenu v-if="podeEditar" :icone="Pencil" @click="editar(r)">Editar</ItemMenu>
            <ItemMenu v-if="podeExcluir" :icone="Trash2" perigo @click="excluir(r)">Excluir</ItemMenu>
          </MenuSuspenso>
        </div>
        <dl class="flex flex-col gap-1.5 text-sm">
          <div class="flex items-center gap-2 text-texto-suave">
            <dt class="sr-only">E-mail</dt>
            <Mail class="size-4 shrink-0 text-texto-fraco" aria-hidden="true" />
            <dd class="truncate">{{ r.email || '—' }}</dd>
          </div>
          <div class="flex items-center gap-2 text-texto-suave">
            <dt class="sr-only">Carteira</dt>
            <dd>{{ plural(r.empresas, 'empresa na carteira', 'empresas na carteira') }}</dd>
          </div>
        </dl>
        <div class="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-borda pt-4">
          <Etiqueta :tom="r.teams_webhook ? 'sucesso' : 'neutro'" ponto>{{ r.teams_webhook ? 'Teams configurado' : 'Sem Teams' }}</Etiqueta>
          <Botao v-if="r.teams_webhook && podeEditar" variante="secundario" tamanho="sm" :carregando="testando === r.id" @click="testar(r)">
            <Send class="size-4" aria-hidden="true" /> Testar Teams
          </Botao>
        </div>
      </li>
    </ul>
    <ModalResponsavel v-model:aberto="modalAberto" :responsavel="emEdicao" @salvo="cadastros.colocarResponsavel" />
  </div>
</template>
