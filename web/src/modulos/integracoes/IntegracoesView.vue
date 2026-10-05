<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import SecaoChave from './SecaoChave.vue'
import SecaoComoConectar from './SecaoComoConectar.vue'
import SecaoWebhooks from './SecaoWebhooks.vue'
import SecaoWhatsapp from './SecaoWhatsapp.vue'
import SecaoRdStation from './SecaoRdStation.vue'

type Aba = 'chave' | 'conectar' | 'webhooks' | 'whatsapp' | 'crm'
const abas: { valor: Aba; rotulo: string }[] = [
  { valor: 'chave', rotulo: 'Chave de integração' },
  { valor: 'conectar', rotulo: 'Como conectar' },
  { valor: 'webhooks', rotulo: 'Avisos (webhooks)' },
  { valor: 'whatsapp', rotulo: 'WhatsApp automático' },
  { valor: 'crm', rotulo: 'CRM' },
]

const rota = useRoute()
const router = useRouter()
const valida = (v: unknown): Aba => (abas.some((a) => a.valor === v) ? (v as Aba) : 'chave')
const aba = ref<Aba>(valida(rota.query.aba))
watch(aba, (a) => {
  if (valida(rota.query.aba) !== a) router.replace({ query: a === 'chave' ? {} : { ...rota.query, aba: a } })
})
watch(
  () => rota.query.aba,
  (v) => (aba.value = valida(v)),
)
const visitadas = ref(new Set<Aba>([aba.value]))
watch(aba, (a) => visitadas.value.add(a))
</script>

<template>
  <CabecalhoPagina
    titulo="Integrações"
    descricao="Ligue o Toqqi ao sistema da sua empresa e ao WhatsApp para a pesquisa sair sozinha, na hora certa."
  />

  <Abas v-model="aba" :abas="abas" rotulo="Seções de integrações">
    <SecaoChave v-if="visitadas.has('chave')" v-show="aba === 'chave'" @ir-para="(a) => (aba = a)" />
    <SecaoComoConectar v-if="visitadas.has('conectar')" v-show="aba === 'conectar'" />
    <SecaoWebhooks v-if="visitadas.has('webhooks')" v-show="aba === 'webhooks'" />
    <!-- A seção tem mais de uma raiz: o v-show precisa de um elemento em volta (senão ela aparece nas outras abas). -->
    <div v-if="visitadas.has('whatsapp')" v-show="aba === 'whatsapp'"><SecaoWhatsapp /></div>
    <SecaoRdStation v-if="visitadas.has('crm')" v-show="aba === 'crm'" />
  </Abas>
</template>
