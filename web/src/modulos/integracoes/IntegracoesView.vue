<script setup lang="ts">
// Integrações em 3 abas, da mais simples para a mais técnica:
// - "Sistemas" (padrão): o catálogo de conectores prontos (CRM e ERP), sem programar;
// - "WhatsApp automático";
// - "API e avisos", para quem cuida do sistema da empresa: a chave, como usar (com Zapier, Make e n8n) e os avisos
//   (webhooks), num seletor dentro da aba para não virar uma página longa.
// Endereços antigos (?aba=chave|conectar|webhooks) abrem a parte certa de "API e avisos".
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import BotoesSegmentados from '@/components/ui/BotoesSegmentados.vue'
import CatalogoConectores from './CatalogoConectores.vue'
import SecaoChave from './SecaoChave.vue'
import SecaoComoConectar from './SecaoComoConectar.vue'
import SecaoWebhooks from './SecaoWebhooks.vue'
import SecaoWhatsapp from './SecaoWhatsapp.vue'

type Aba = 'crm' | 'whatsapp' | 'api'
type Parte = 'chave' | 'conectar' | 'webhooks'
const abas: { valor: Aba; rotulo: string }[] = [
  { valor: 'crm', rotulo: 'Sistemas' },
  { valor: 'whatsapp', rotulo: 'WhatsApp automático' },
  { valor: 'api', rotulo: 'API e avisos' },
]
const partes: { valor: Parte; rotulo: string }[] = [
  { valor: 'chave', rotulo: 'Chave' },
  { valor: 'conectar', rotulo: 'Como usar' },
  { valor: 'webhooks', rotulo: 'Avisos (webhooks)' },
]
const ANTIGAS: Record<string, Parte> = { chave: 'chave', conectar: 'conectar', webhooks: 'webhooks' }

const rota = useRoute()
const router = useRouter()
const valida = (v: unknown): Aba => (typeof v === 'string' && v in ANTIGAS ? 'api' : abas.some((a) => a.valor === v) ? (v as Aba) : 'crm')
const parteDe = (aba: unknown, parte: unknown): Parte =>
  typeof aba === 'string' && aba in ANTIGAS ? (ANTIGAS[aba] as Parte) : partes.some((p) => p.valor === parte) ? (parte as Parte) : 'chave'

const aba = ref<Aba>(valida(rota.query.aba))
const parte = ref<Parte>(parteDe(rota.query.aba, rota.query.parte))
const consulta = computed(() => {
  const { aba: _a, parte: _p, ...resto } = rota.query
  return { ...resto, ...(aba.value !== 'crm' ? { aba: aba.value } : {}), ...(aba.value === 'api' && parte.value !== 'chave' ? { parte: parte.value } : {}) }
})
watch([aba, parte], () => {
  if (JSON.stringify(consulta.value) !== JSON.stringify(rota.query)) router.replace({ query: consulta.value })
})
watch(
  () => [rota.query.aba, rota.query.parte],
  ([a, p]) => {
    aba.value = valida(a)
    parte.value = parteDe(a, p)
  },
)
const visitadas = ref(new Set<string>([aba.value, parte.value]))
watch([aba, parte], ([a, p]) => {
  visitadas.value.add(a)
  if (a === 'api') visitadas.value.add(p)
})
function irPara(p: Parte) {
  aba.value = 'api'
  parte.value = p
}
</script>

<template>
  <CabecalhoPagina
    titulo="Integrações"
    descricao="Ligue o Toqqi ao sistema da sua empresa e ao WhatsApp para a pesquisa sair sozinha, na hora certa."
  />

  <Abas v-model="aba" :abas="abas" rotulo="Seções de integrações">
    <CatalogoConectores v-if="visitadas.has('crm')" v-show="aba === 'crm'" @ir-para-api="irPara('conectar')" />
    <!-- A seção tem mais de uma raiz: o v-show precisa de um elemento em volta (senão ela aparece nas outras abas). -->
    <div v-if="visitadas.has('whatsapp')" v-show="aba === 'whatsapp'"><SecaoWhatsapp /></div>
    <div v-if="visitadas.has('api')" v-show="aba === 'api'" class="flex flex-col gap-4" data-aba-api>
      <div class="flex flex-col gap-2">
        <BotoesSegmentados v-model="parte" :opcoes="partes" rotulo="Parte da API" class="self-start" />
        <p class="text-sm text-texto-suave">Para quem cuida do sistema da empresa: ligue qualquer sistema pela API ou por Zapier, Make e n8n.</p>
      </div>
      <SecaoChave v-if="visitadas.has('chave')" v-show="parte === 'chave'" @ir-para="irPara" />
      <SecaoComoConectar v-if="visitadas.has('conectar')" v-show="parte === 'conectar'" />
      <SecaoWebhooks v-if="visitadas.has('webhooks')" v-show="parte === 'webhooks'" />
    </div>
  </Abas>
</template>
