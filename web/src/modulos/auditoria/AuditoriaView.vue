<script setup lang="ts">
// Auditoria. Etapa 5e: duas abas. "Atividades" (a tela de antes: quem fez o quê e quando) e "E-mails enviados" (cada
// e-mail que saiu em nome da conta, com a situação e o erro). A aba fica no endereço: /auditoria e /auditoria/emails
// (/auditoria?aba=emails também abre a dos e-mails). Cada aba guarda os filtros dela enquanto a pessoa alterna.
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'
import Abas from '@/components/ui/Abas.vue'
import AbaAtividades from './AbaAtividades.vue'
import AbaEmails from './AbaEmails.vue'
import { ABAS_AUDITORIA, abaAuditoriaDaRota, type AbaAuditoria } from './emails'

const rota = useRoute()
const router = useRouter()

const daRota = () => abaAuditoriaDaRota(rota.params.aba, rota.query.aba)
const aba = ref<AbaAuditoria>(daRota())
const visitadas = ref(new Set<AbaAuditoria>([aba.value]))

/** O endereço certo de cada aba (Atividades sem nada; os e-mails em /auditoria/emails). */
function escreverEndereco(a: AbaAuditoria) {
  const certo = a === 'emails' ? 'emails' : undefined
  const resto = Object.fromEntries(Object.entries(rota.query).filter(([k]) => k !== 'aba'))
  if ((rota.params.aba || undefined) !== certo || 'aba' in rota.query) {
    void router.replace({ name: 'auditoria', params: certo ? { aba: certo } : {}, query: resto })
  }
}

// /auditoria?aba=emails e /auditoria/atividades viram o endereço de sempre.
if (rota.params.aba === 'atividades' || 'aba' in rota.query) escreverEndereco(aba.value)

watch(aba, (a) => {
  visitadas.value.add(a)
  escreverEndereco(a)
})
// Voltar e avançar do navegador (ou um link de outra tela, como /auditoria?aba=emails): a aba acompanha.
watch(
  () => [rota.params.aba, rota.query.aba],
  () => {
    if (rota.name !== 'auditoria') return
    const nova = daRota()
    if (nova !== aba.value) aba.value = nova
    else escreverEndereco(nova)
  },
)
</script>

<template>
  <CabecalhoPagina titulo="Auditoria" descricao="Tudo o que aconteceu de importante na sua conta e os e-mails que saíram em nome dela." />

  <Abas v-model="aba" :abas="ABAS_AUDITORIA" rotulo="Seções da auditoria">
    <AbaAtividades v-if="visitadas.has('atividades')" v-show="aba === 'atividades'" />
    <AbaEmails v-if="visitadas.has('emails')" v-show="aba === 'emails'" />
  </Abas>
</template>
