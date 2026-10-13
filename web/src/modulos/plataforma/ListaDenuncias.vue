<script setup lang="ts">
// Plataforma › Feedback › Denúncias (Plano Grátis, docs/api-plano-gratis.md): o que chegou pelo "Denunciar esta
// pesquisa" das contas Grátis, das mais novas às mais antigas (as abertas ou todas). A equipe marca "Procedente" ou
// "Descartar" (e pode reabrir) e escreve uma nota interna. A conta denunciada não vê nada disso. O número de abertas
// sobe em `abertas`, para o rótulo do seletor.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Flag, RefreshCw } from 'lucide-vue-next'
import { mensagemDoErro, plataformaApi, type DenunciaPlataforma, type SituacaoDenuncia } from '@/api'
import { avisar } from '@/composables/avisos'
import Alerta from '@/components/ui/Alerta.vue'
import AreaTexto from '@/components/ui/AreaTexto.vue'
import Botao from '@/components/ui/Botao.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import Carregando from '@/components/ui/Carregando.vue'
import EstadoVazio from '@/components/ui/EstadoVazio.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import { rotuloQuando } from '@/modulos/feedback/logica'
import { situacaoConta } from '@/utils/rotulos'
import {
  FILTROS_DENUNCIAS,
  infoSituacaoDenuncia,
  linkDaConta,
  mensagemSituacao,
  rotuloMotivo,
  rotuloOrigem,
  textoAbertas,
  type FiltroDenuncias,
} from './denuncias'

const emit = defineEmits<{ abertas: [number] }>()

const filtro = ref<FiltroDenuncias>('abertas')
const itens = ref<DenunciaPlataforma[]>([])
const abertas = ref(0)
const carregando = ref(true)
const carregou = ref(false)
const erro = ref<string | null>(null)
/** A denúncia com um pedido em andamento (botões dela desligados). */
const ocupado = ref<DenunciaPlataforma['id'] | null>(null)
/** A denúncia com a nota aberta para editar, e o texto. */
const editando = ref<DenunciaPlataforma['id'] | null>(null)
const textoNota = ref('')
let controlador: AbortController | null = null

function contar(n: number) {
  abertas.value = n
  emit('abertas', n)
}

async function carregar() {
  controlador?.abort()
  controlador = new AbortController()
  carregando.value = true
  erro.value = null
  try {
    const r = await plataformaApi.denuncias(filtro.value, controlador.signal)
    itens.value = r.itens
    contar(r.abertas)
    carregou.value = true
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function substituir(novo: DenunciaPlataforma, antes: DenunciaPlataforma) {
  if (antes.situacao === 'aberta' && novo.situacao !== 'aberta') contar(Math.max(0, abertas.value - 1))
  else if (antes.situacao !== 'aberta' && novo.situacao === 'aberta') contar(abertas.value + 1)
  // Em "Abertas", a que fechou sai da lista.
  itens.value =
    filtro.value === 'abertas' && novo.situacao !== 'aberta'
      ? itens.value.filter((x) => String(x.id) !== String(novo.id))
      : itens.value.map((x) => (String(x.id) === String(novo.id) ? novo : x))
}

async function mudar(d: DenunciaPlataforma, situacao: SituacaoDenuncia) {
  ocupado.value = d.id
  try {
    substituir(await plataformaApi.alterarDenuncia(d.id, { situacao }), d)
    avisar.sucesso(mensagemSituacao(situacao))
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

function editarNota(d: DenunciaPlataforma) {
  editando.value = d.id
  textoNota.value = d.nota_interna ?? ''
}

async function salvarNota(d: DenunciaPlataforma) {
  ocupado.value = d.id
  try {
    substituir(await plataformaApi.alterarDenuncia(d.id, { nota_interna: textoNota.value.trim() || null }), d)
    editando.value = null
    avisar.sucesso('Nota interna salva.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

watch(filtro, () => void carregar())
onMounted(carregar)
onBeforeUnmount(() => controlador?.abort())
</script>

<template>
  <div class="flex flex-col gap-4" data-denuncias>
    <div class="cartao">
      <div class="flex min-h-12 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-borda px-4 py-3 text-sm sm:px-5">
        <div class="flex flex-wrap items-center gap-3">
          <BotoesSegmentados v-model="filtro" :opcoes="FILTROS_DENUNCIAS" rotulo="Quais denúncias" />
          <p class="text-texto-suave" aria-live="polite" data-total-denuncias>
            <template v-if="carregando && !carregou">Carregando…</template>
            <template v-else-if="!erro">{{ textoAbertas(abertas) }}</template>
          </p>
        </div>
        <Botao variante="secundario" tamanho="sm" :carregando="carregando && carregou" @click="carregar">
          <RefreshCw class="size-4" aria-hidden="true" /> Atualizar
        </Botao>
      </div>

      <div v-if="carregando && !carregou" class="p-5"><Carregando :linhas="3" rotulo="Carregando as denúncias" /></div>
      <Alerta v-else-if="erro" tom="erro" class="m-4">
        {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
      </Alerta>
      <EstadoVazio
        v-else-if="!itens.length"
        :icone="Flag"
        :titulo="filtro === 'abertas' ? 'Nenhuma denúncia aberta' : 'Nenhuma denúncia ainda'"
        descricao="Quem recebe uma pesquisa de conta Grátis pode denunciá-la. As denúncias aparecem aqui."
        data-vazio-denuncias
      />
      <ul v-else class="divide-y divide-borda" :class="{ 'opacity-60 transition-opacity': carregando }" :aria-busy="carregando" aria-label="Denúncias">
        <li v-for="d in itens" :key="String(d.id)" class="flex flex-col gap-2.5 px-4 py-4 sm:px-5" :data-denuncia="d.id">
          <div class="flex flex-wrap items-center gap-2">
            <Etiqueta :tom="infoSituacaoDenuncia(d.situacao).tom" ponto data-situacao-denuncia>{{ infoSituacaoDenuncia(d.situacao).rotulo }}</Etiqueta>
            <span class="font-semibold text-texto">{{ rotuloMotivo(d.motivo) }}</span>
            <span class="text-xs text-texto-fraco">#{{ d.id }}</span>
          </div>
          <p v-if="d.detalhe" class="whitespace-pre-line text-sm text-texto [overflow-wrap:anywhere]" data-detalhe>“{{ d.detalhe }}”</p>
          <p class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-texto-fraco">
            <RouterLink v-if="linkDaConta(d)" :to="linkDaConta(d)!" class="link font-semibold">{{ d.conta.nome }}</RouterLink>
            <span v-else class="font-semibold text-texto-suave">Conta excluída</span>
            <span v-if="d.conta.situacao">{{ situacaoConta(d.conta.situacao).rotulo }}</span>
            <span>Formulário “{{ d.formulario.nome ?? '—' }}”</span>
            <span>{{ rotuloOrigem(d.origem) }}</span>
            <span>{{ rotuloQuando(d.criada_em) }}</span>
            <span v-if="d.resolvida_em">resolvida {{ rotuloQuando(d.resolvida_em) }}</span>
          </p>

          <div v-if="editando === d.id" class="flex flex-col gap-2 sm:max-w-xl">
            <AreaTexto v-model="textoNota" rotulo="Nota interna" dica="Só a equipe Toqqi vê." :linhas="2" :maximo="2000" :disabled="ocupado === d.id" />
            <div class="flex gap-2 self-end">
              <Botao variante="fantasma" tamanho="sm" :desabilitado="ocupado === d.id" @click="editando = null">Cancelar</Botao>
              <Botao variante="secundario" tamanho="sm" :carregando="ocupado === d.id" data-salvar-nota-denuncia @click="salvarNota(d)">Salvar nota</Botao>
            </div>
          </div>
          <p v-else-if="d.nota_interna" class="rounded-lg bg-superficie-2 px-3 py-2 text-sm text-texto-suave sm:max-w-xl" data-nota-denuncia>
            <span class="font-semibold text-texto">Nota interna:</span> {{ d.nota_interna }}
          </p>

          <div class="flex flex-wrap gap-2">
            <template v-if="d.situacao === 'aberta'">
              <Botao variante="secundario" tamanho="sm" :desabilitado="ocupado === d.id" data-procedente @click="mudar(d, 'procedente')">Marcar procedente</Botao>
              <Botao variante="secundario" tamanho="sm" :desabilitado="ocupado === d.id" data-descartar @click="mudar(d, 'descartada')">Descartar</Botao>
            </template>
            <Botao v-else variante="fantasma" tamanho="sm" :desabilitado="ocupado === d.id" data-reabrir @click="mudar(d, 'aberta')">Reabrir</Botao>
            <Botao v-if="editando !== d.id" variante="fantasma" tamanho="sm" :desabilitado="ocupado === d.id" @click="editarNota(d)">
              {{ d.nota_interna ? 'Editar a nota' : 'Escrever uma nota' }}
            </Botao>
          </div>
        </li>
      </ul>
    </div>

    <p class="text-sm text-texto-fraco">
      As denúncias chegam pelo “Denunciar esta pesquisa”, que aparece nas pesquisas das contas Grátis, e por e-mail aos superadmins. A conta denunciada não vê.
      Cada denúncia que não foi descartada pesa na nota de risco da conta por 30 dias: com 2 pessoas diferentes, os envios dela pausam na próxima rodada, até a
      equipe liberar em Contas. Descartar tira o peso.
    </p>
  </div>
</template>
