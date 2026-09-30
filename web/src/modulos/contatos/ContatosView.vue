<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Building2, Upload, UserPlus, UserRoundPlus } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import Botao from '@/components/ui/Botao.vue'
import AbaCadastros from './AbaCadastros.vue'
import AbaContatos from './AbaContatos.vue'
import AbaEmpresas from './AbaEmpresas.vue'
import AbaResponsaveis from './AbaResponsaveis.vue'

type Aba = 'contatos' | 'empresas' | 'responsaveis' | 'cadastros'
const abas: { valor: Aba; rotulo: string }[] = [
  { valor: 'contatos', rotulo: 'Contatos' },
  { valor: 'empresas', rotulo: 'Empresas' },
  { valor: 'responsaveis', rotulo: 'Responsáveis' },
  { valor: 'cadastros', rotulo: 'Mais cadastros' },
]

const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()
const valida = (v: unknown): Aba => (abas.some((a) => a.valor === v) ? (v as Aba) : 'contatos')
const aba = ref<Aba>(valida(rota.query.aba))
watch(aba, (a) => router.replace({ query: a === 'contatos' ? {} : { aba: a } }))
watch(
  () => rota.query.aba,
  (v) => (aba.value = valida(v)),
)

// Só monta cada aba na primeira visita (evita buscar tudo de uma vez).
const visitadas = ref(new Set<Aba>([aba.value]))
watch(aba, (a) => visitadas.value.add(a))

const contatos = ref<InstanceType<typeof AbaContatos> | null>(null)
const empresas = ref<InstanceType<typeof AbaEmpresas> | null>(null)
const responsaveis = ref<InstanceType<typeof AbaResponsaveis> | null>(null)
const podeEditar = computed(() => sessao.pode('contatos.editar'))
</script>

<template>
  <CabecalhoPagina titulo="Contatos" descricao="Seus clientes, as empresas deles e quem cuida de cada carteira.">
    <template #acoes>
      <template v-if="aba === 'contatos'">
        <Botao v-if="sessao.pode('importacao.usar')" variante="secundario" para="/contatos/importar"><Upload class="size-4" aria-hidden="true" /> Importar planilha</Botao>
        <Botao v-if="podeEditar" @click="contatos?.novo()"><UserPlus class="size-4" aria-hidden="true" /> Novo contato</Botao>
      </template>
      <Botao v-else-if="aba === 'empresas' && podeEditar" @click="empresas?.novo()"><Building2 class="size-4" aria-hidden="true" /> Nova empresa</Botao>
      <Botao v-else-if="aba === 'responsaveis' && podeEditar" @click="responsaveis?.novo()"><UserRoundPlus class="size-4" aria-hidden="true" /> Novo responsável</Botao>
    </template>
  </CabecalhoPagina>

  <Abas v-model="aba" :abas="abas" rotulo="Seções de contatos">
    <AbaContatos v-if="visitadas.has('contatos')" v-show="aba === 'contatos'" ref="contatos" />
    <AbaEmpresas v-if="visitadas.has('empresas')" v-show="aba === 'empresas'" ref="empresas" />
    <AbaResponsaveis v-if="visitadas.has('responsaveis')" v-show="aba === 'responsaveis'" ref="responsaveis" />
    <AbaCadastros v-if="visitadas.has('cadastros')" v-show="aba === 'cadastros'" />
  </Abas>
</template>
