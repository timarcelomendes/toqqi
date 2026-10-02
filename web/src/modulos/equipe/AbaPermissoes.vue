<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Lock } from 'lucide-vue-next'
import { equipeApi, mensagemDoErro, type ItemCatalogoPermissao, type Permissao, type PermissoesEquipe } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import CaixaSelecao from '@/components/ui/CaixaSelecao.vue'

type PerfilEditavel = 'gestor' | 'consulta'

const carregando = ref(true)
const salvando = ref(false)
const erro = ref<string | null>(null)
const catalogo = ref<ItemCatalogoPermissao[]>([])
const original = reactive<Record<PerfilEditavel, Permissao[]>>({ gestor: [], consulta: [] })
const atual = reactive<Record<PerfilEditavel, Set<Permissao>>>({ gestor: new Set(), consulta: new Set() })

const grupos = computed(() => {
  const mapa = new Map<string, ItemCatalogoPermissao[]>()
  for (const item of catalogo.value) {
    const lista = mapa.get(item.grupo) ?? []
    lista.push(item)
    mapa.set(item.grupo, lista)
  }
  return [...mapa.entries()].map(([grupo, itens]) => ({ grupo, itens }))
})

const alterado = computed(
  () =>
    (['gestor', 'consulta'] as const).some(
      (p) => atual[p].size !== original[p].length || original[p].some((x) => !atual[p].has(x)),
    ),
)

function aplicar(d: PermissoesEquipe) {
  catalogo.value = d.catalogo
  original.gestor = [...d.gestor]
  original.consulta = [...d.consulta]
  atual.gestor = new Set(d.gestor)
  atual.consulta = new Set(d.consulta)
}

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    aplicar(await equipeApi.permissoes())
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

function marcado(perfil: PerfilEditavel, chave: Permissao) {
  return atual[perfil].has(chave)
}
function alternar(perfil: PerfilEditavel, chave: Permissao, valor: boolean) {
  const novo = new Set(atual[perfil])
  if (valor) novo.add(chave)
  else novo.delete(chave)
  atual[perfil] = novo
}

function descartar() {
  atual.gestor = new Set(original.gestor)
  atual.consulta = new Set(original.consulta)
}

async function salvar() {
  salvando.value = true
  try {
    // Mantém a ordem do catálogo ao enviar.
    const ordem = (p: PerfilEditavel) => catalogo.value.map((c) => c.chave).filter((c) => atual[p].has(c))
    aplicar(await equipeApi.salvarPermissoes({ gestor: ordem('gestor'), consulta: ordem('consulta') }))
    avisar.sucesso('Permissões salvas. Valem a partir do próximo clique de cada pessoa.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    salvando.value = false
  }
}

onBeforeRouteLeave(async () => {
  if (!alterado.value) return true
  return confirmar({
    titulo: 'Sair sem salvar?',
    mensagem: 'Você mudou permissões e ainda não salvou. Se sair agora, as mudanças se perdem.',
    confirmar: 'Sair sem salvar',
    cancelar: 'Continuar editando',
    perigo: true,
  })
})

onMounted(carregar)
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="max-w-3xl text-[0.95rem] text-texto-suave">
      Escolha o que <strong class="text-texto">Gestores</strong> e pessoas com perfil <strong class="text-texto">Consulta</strong>
      podem fazer. Administradores podem tudo, sempre.
    </p>

    <Carregando v-if="carregando" :linhas="5" />
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>

    <div v-else class="cartao overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full border-collapse text-sm">
          <caption class="sr-only">Permissões por perfil</caption>
          <thead>
            <tr class="border-b border-borda bg-superficie-2/60">
              <th scope="col" class="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-texto-fraco">Permissão</th>
              <th scope="col" class="w-28 px-3 py-3 text-center text-xs font-semibold uppercase tracking-wide text-texto-fraco sm:w-36">Gestor</th>
              <th scope="col" class="w-28 px-3 py-3 text-center text-xs font-semibold uppercase tracking-wide text-texto-fraco sm:w-36">Consulta</th>
            </tr>
          </thead>
          <tbody v-for="g in grupos" :key="g.grupo">
            <tr>
              <th scope="colgroup" colspan="3" class="border-b border-borda bg-superficie px-5 pb-2 pt-5 text-left text-sm font-bold text-texto">
                {{ g.grupo }}
              </th>
            </tr>
            <tr v-for="item in g.itens" :key="item.chave" class="border-b border-borda last:border-0" :class="{ 'bg-superficie-2/40': item.somente_admin }">
              <th scope="row" class="px-5 py-3 text-left font-medium" :class="item.somente_admin ? 'text-texto-fraco' : 'text-texto'">
                {{ item.rotulo }}
              </th>
              <template v-if="item.somente_admin">
                <td colspan="2" class="px-3 py-3 text-center">
                  <span class="inline-flex items-center gap-1.5 text-xs font-semibold text-texto-fraco">
                    <Lock class="size-3.5" aria-hidden="true" /> Só administrador
                  </span>
                </td>
              </template>
              <template v-else>
                <td v-for="perfil in (['gestor', 'consulta'] as const)" :key="perfil" class="px-3 py-3">
                  <div class="flex justify-center">
                    <CaixaSelecao
                      :model-value="marcado(perfil, item.chave)"
                      :rotulo="`${item.rotulo}: ${perfil === 'gestor' ? 'Gestor' : 'Consulta'}`"
                      rotulo-oculto
                      :desabilitado="salvando"
                      @update:model-value="(v: boolean) => alternar(perfil, item.chave, v)"
                    />
                  </div>
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Barra de salvar -->
    <Transition enter-from-class="translate-y-full opacity-0" enter-active-class="transition duration-200" leave-active-class="transition duration-150" leave-to-class="translate-y-full opacity-0">
      <div v-if="alterado" data-barra-fixa class="sticky bottom-4 z-20">
        <div class="flex flex-col gap-3 rounded-2xl border border-borda bg-superficie p-4 shadow-xl sm:flex-row sm:items-center" role="region" aria-label="Alterações não salvas">
          <p class="flex-1 text-sm font-semibold text-texto">Você tem alterações não salvas.</p>
          <div class="flex gap-2">
            <Botao variante="secundario" :desabilitado="salvando" @click="descartar">Descartar</Botao>
            <Botao :carregando="salvando" @click="salvar">Salvar permissões</Botao>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>
