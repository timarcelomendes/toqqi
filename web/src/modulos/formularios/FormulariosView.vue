<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Copy, FilePlus2, FileText, Globe, Lock, MessageSquareText, MoreHorizontal, Pencil, Trash2 } from 'lucide-vue-next'
import { formulariosApi, mensagemDoErro, type FormularioResumo, type Id } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { formatarData } from '@/utils/datas'
import { plural } from '@/utils/formatos'
import { TIPOS_FORMULARIO } from '@/utils/rotulos'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import ItemMenu from '@/components/app/ItemMenu.vue'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import MenuSuspenso from '@/components/ui/MenuSuspenso.vue'
import ModalNovoFormulario from './ModalNovoFormulario.vue'

const sessao = useSessaoStore()
const router = useRouter()
const formularios = ref<FormularioResumo[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const ocupado = ref<Id | null>(null)
const novoAberto = ref(false)
const podeEditar = computed(() => sessao.pode('formularios.editar'))

const ordenados = computed(() =>
  [...formularios.value].sort(
    (a, b) =>
      Number(b.ativo) - Number(a.ativo) ||
      Number(b.padrao_nps || b.padrao_csat) - Number(a.padrao_nps || a.padrao_csat) ||
      (b.atualizado_em ?? '').localeCompare(a.atualizado_em ?? ''),
  ),
)

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    formularios.value = await formulariosApi.listar()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function duplicar(f: FormularioResumo) {
  ocupado.value = f.id
  try {
    const novo = await formulariosApi.duplicar(f.id)
    avisar.sucesso(`Cópia criada: ${novo.nome}.`)
    router.push(`/formularios/${novo.id}`)
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function excluir(f: FormularioResumo) {
  if (f.padrao_nps || f.padrao_csat) {
    avisar.atencao('Este é um formulário padrão. Escolha outro como padrão antes de excluir.')
    return
  }
  const comRespostas = f.respostas > 0
  const ok = await confirmar({
    titulo: comRespostas ? `Arquivar “${f.nome}”?` : `Excluir “${f.nome}”?`,
    mensagem: comRespostas
      ? `Ele já tem ${plural(f.respostas, 'resposta', 'respostas')}, então vai ser arquivado: sai da lista e para de aceitar respostas, mas os resultados continuam guardados.`
      : 'O formulário é apagado. Não dá para desfazer.',
    confirmar: comRespostas ? 'Arquivar' : 'Excluir',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = f.id
  try {
    await formulariosApi.excluir(f.id)
    formularios.value = formularios.value.filter((x) => String(x.id) !== String(f.id))
    avisar.sucesso(comRespostas ? 'Formulário arquivado.' : 'Formulário excluído.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
</script>

<template>
  <CabecalhoPagina titulo="Formulários" descricao="As pesquisas que seus clientes respondem: perguntas, visual e onde compartilhar.">
    <template v-if="podeEditar" #acoes>
      <Botao @click="novoAberto = true"><FilePlus2 class="size-4" aria-hidden="true" /> Novo formulário</Botao>
    </template>
  </CabecalhoPagina>

  <Carregando v-if="carregando" :linhas="4" />
  <Alerta v-else-if="erro" tom="erro">
    {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
  </Alerta>
  <div v-else-if="!formularios.length" class="cartao">
    <EstadoVazio :icone="FileText" titulo="Nenhum formulário ainda" descricao="Crie sua primeira pesquisa a partir de um modelo pronto de NPS ou CSAT.">
      <Botao v-if="podeEditar" @click="novoAberto = true">Novo formulário</Botao>
    </EstadoVazio>
  </div>
  <ul v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
    <li v-for="f in ordenados" :key="String(f.id)" class="cartao relative flex flex-col p-5 transition-shadow focus-within:ring-2 focus-within:ring-foco hover:shadow-md" :class="{ 'opacity-70': !f.ativo }">
      <div class="flex items-start gap-3">
        <span
          class="flex size-10 shrink-0 items-center justify-center rounded-xl"
          :style="{ backgroundColor: `color-mix(in srgb, ${f.tema?.cor ?? '#ff5a36'} 14%, transparent)`, color: f.tema?.cor ?? undefined }"
          aria-hidden="true"
        >
          <FileText class="size-5" :class="f.tema?.cor ? '' : 'text-marca-texto'" />
        </span>
        <div class="min-w-0 flex-1">
          <h2 class="font-bold text-texto">
            <RouterLink :to="`/formularios/${f.id}`" class="after:absolute after:inset-0 focus:outline-none">{{ f.nome }}</RouterLink>
          </h2>
          <p v-if="f.descricao" class="mt-0.5 line-clamp-2 text-sm text-texto-suave">{{ f.descricao }}</p>
        </div>
        <!-- Sem z-index: o menu aberto (z-40) fica acima do botão do assistente (z-[25]); "relative" já põe o gatilho acima do link do cartão. -->
        <MenuSuspenso v-if="podeEditar" :rotulo="`Ações para ${f.nome}`" class="relative">
          <template #gatilho="{ props }">
            <button v-bind="props" type="button" class="-mr-2 -mt-1 flex size-9 items-center justify-center rounded-lg text-texto-fraco hover:bg-superficie-2 hover:text-texto disabled:opacity-50" :disabled="ocupado === f.id">
              <MoreHorizontal class="size-5" aria-hidden="true" />
            </button>
          </template>
          <ItemMenu :icone="Pencil" :para="`/formularios/${f.id}`">Editar</ItemMenu>
          <ItemMenu :icone="Copy" @click="duplicar(f)">Duplicar</ItemMenu>
          <ItemMenu :icone="Trash2" perigo @click="excluir(f)">{{ f.respostas > 0 ? 'Arquivar' : 'Excluir' }}</ItemMenu>
        </MenuSuspenso>
      </div>
      <div class="mt-4 flex flex-wrap gap-1.5">
        <Etiqueta :tom="TIPOS_FORMULARIO[f.tipo_principal]?.tom">{{ TIPOS_FORMULARIO[f.tipo_principal]?.rotulo ?? f.tipo_principal }}</Etiqueta>
        <Etiqueta v-if="f.padrao_nps" tom="sucesso">Padrão NPS</Etiqueta>
        <Etiqueta v-if="f.padrao_csat" tom="sucesso">Padrão CSAT</Etiqueta>
        <Etiqueta v-if="!f.ativo" tom="neutro" ponto>Desativado</Etiqueta>
      </div>
      <div class="flex-1" />
      <div class="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-borda pt-3 text-sm text-texto-fraco">
        <span class="inline-flex items-center gap-1.5"><MessageSquareText class="size-4" aria-hidden="true" /> {{ plural(f.respostas, 'resposta', 'respostas') }}</span>
        <span class="inline-flex items-center gap-1.5">
          <Globe v-if="f.publico" class="size-4" aria-hidden="true" /><Lock v-else class="size-4" aria-hidden="true" />
          {{ f.publico ? 'Link público' : 'Só por convite' }}
        </span>
        <span class="ml-auto text-xs">Alterado em {{ formatarData(f.atualizado_em) }}</span>
      </div>
    </li>
  </ul>

  <ModalNovoFormulario v-model:aberto="novoAberto" />
</template>
