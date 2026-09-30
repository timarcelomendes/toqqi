<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Laptop, LogOut, Smartphone } from 'lucide-vue-next'
import { euApi, mensagemDoErro, type SessaoAparelho } from '@/api'
import { avisar } from '@/composables/avisos'
import { confirmar } from '@/composables/confirmacao'
import { useSessaoStore } from '@/stores/sessao'
import { formatarDataHora } from '@/utils/datas'
import Alerta from '@/components/ui/Alerta.vue'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import Etiqueta from '@/components/ui/Etiqueta.vue'
import SecaoCartao from './SecaoCartao.vue'

const sessao = useSessaoStore()
const router = useRouter()
const lista = ref<SessaoAparelho[]>([])
const carregando = ref(true)
const erro = ref<string | null>(null)
const ocupado = ref<string | number | null>(null)

// O aparelho atual primeiro; depois do uso mais recente para o mais antigo.
const ordenada = computed(() =>
  [...lista.value].sort((a, b) =>
    a.atual !== b.atual ? (a.atual ? -1 : 1) : String(b.ultimo_uso ?? b.criada_em).localeCompare(String(a.ultimo_uso ?? a.criada_em)),
  ),
)
const outras = computed(() => lista.value.filter((s) => !s.atual).length)

function ehCelular(aparelho: string) {
  return /android|iphone|ipad|celular|mobile/i.test(aparelho)
}

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    lista.value = await euApi.sessoes()
  } catch (e) {
    erro.value = mensagemDoErro(e)
  } finally {
    carregando.value = false
  }
}

async function encerrar(s: SessaoAparelho) {
  if (s.atual) {
    if (!(await confirmar({ titulo: 'Sair deste aparelho?', mensagem: 'Você vai precisar entrar de novo aqui.', confirmar: 'Sair' }))) return
    await sessao.sair()
    router.push({ name: 'entrar' })
    return
  }
  const ok = await confirmar({
    titulo: 'Encerrar esta conexão?',
    mensagem: `Quem estiver usando "${s.aparelho}" vai precisar entrar de novo.`,
    confirmar: 'Encerrar',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = s.id
  try {
    await euApi.encerrarSessao(s.id)
    lista.value = lista.value.filter((x) => x.id !== s.id)
    avisar.sucesso('Conexão encerrada.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

async function encerrarOutras() {
  const ok = await confirmar({
    titulo: 'Encerrar os outros aparelhos?',
    mensagem: 'Você continua conectado só neste aparelho. Nos outros, será preciso entrar de novo.',
    confirmar: 'Encerrar os outros',
    perigo: true,
  })
  if (!ok) return
  ocupado.value = 'todas'
  try {
    await euApi.encerrarOutras()
    lista.value = lista.value.filter((x) => x.atual)
    avisar.sucesso('Pronto! Só este aparelho continua conectado.')
  } catch (e) {
    avisar.erro(mensagemDoErro(e))
  } finally {
    ocupado.value = null
  }
}

onMounted(carregar)
defineExpose({ carregar })
</script>

<template>
  <SecaoCartao titulo="Aparelhos conectados" descricao="Onde sua conta está aberta agora. Não reconhece algum? Encerre e troque sua senha.">
    <template #lateral>
      <Botao
        v-if="outras > 0"
        class="mt-4"
        variante="secundario"
        tamanho="sm"
        :carregando="ocupado === 'todas'"
        @click="encerrarOutras"
      >
        Encerrar os outros
      </Botao>
    </template>

    <Carregando v-if="carregando" :linhas="2" />
    <Alerta v-else-if="erro" tom="erro">
      {{ erro }} <button type="button" class="link ml-1" @click="carregar">Tentar de novo</button>
    </Alerta>
    <ul v-else class="flex flex-col divide-y divide-borda rounded-xl border border-borda">
      <li v-for="s in ordenada" :key="s.id" class="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <div class="flex min-w-0 flex-1 items-start gap-3">
          <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-superficie-2 text-texto-suave">
            <Smartphone v-if="ehCelular(s.aparelho)" class="size-5" aria-hidden="true" />
            <Laptop v-else class="size-5" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <p class="flex flex-wrap items-center gap-2 font-semibold text-texto">
              <span class="truncate">{{ s.aparelho || 'Aparelho desconhecido' }}</span>
              <Etiqueta v-if="s.atual" tom="sucesso" ponto>Este aparelho</Etiqueta>
            </p>
            <p class="text-sm text-texto-fraco">
              <span v-if="s.ip">IP {{ s.ip }} · </span>Último uso {{ formatarDataHora(s.ultimo_uso ?? s.criada_em) }}
            </p>
            <p class="text-xs text-texto-fraco">Conectado desde {{ formatarDataHora(s.criada_em) }}</p>
          </div>
        </div>
        <Botao
          :variante="s.atual ? 'fantasma' : 'perigo-suave'"
          tamanho="sm"
          :carregando="ocupado === s.id"
          :desabilitado="ocupado === 'todas'"
          @click="encerrar(s)"
        >
          <LogOut v-if="s.atual" class="size-4" aria-hidden="true" />
          {{ s.atual ? 'Sair' : 'Encerrar' }}
          <span class="sr-only">: {{ s.aparelho }}</span>
        </Botao>
      </li>
    </ul>
  </SecaoCartao>
</template>
