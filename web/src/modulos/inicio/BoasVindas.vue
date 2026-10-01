<script setup lang="ts">
// Início para quem não tem acesso ao painel: boas-vindas e atalhos.
import { computed } from 'vue'
import { CheckCircle2, Circle, Sparkles } from 'lucide-vue-next'
import { useSessaoStore } from '@/stores/sessao'
import CabecalhoPagina from '@/components/app/CabecalhoPagina.vue'

const sessao = useSessaoStore()
const primeiroNome = computed(() => sessao.usuario?.nome?.split(' ')[0] ?? '')

const saudacao = computed(() => {
  const hora = Number(new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', hour: 'numeric', hour12: false }).format(new Date()))
  return hora < 12 ? 'Bom dia' : hora < 18 ? 'Boa tarde' : 'Boa noite'
})

// Lista ilustrativa: os passos ganham vida conforme as próximas etapas forem entregues.
const passos = computed(() => [
  { titulo: 'Criar sua conta', descricao: 'Pronto! Você já está dentro do Toqqi.', feito: true },
  { titulo: 'Chamar sua equipe', descricao: 'Convide quem vai acompanhar os clientes com você.', feito: false, para: sessao.pode('equipe.gerenciar') ? '/equipe' : undefined },
  {
    titulo: 'Cadastrar seus clientes',
    descricao: 'Importe sua lista de contatos de uma planilha.',
    feito: false,
    para: sessao.pode('importacao.usar') ? '/contatos/importar' : sessao.pode('contatos.ver') ? '/contatos' : undefined,
  },
  {
    titulo: 'Montar sua primeira pesquisa',
    descricao: 'Escolha entre NPS e CSAT com modelos prontos.',
    feito: false,
    para: sessao.pode('formularios.ver') ? '/formularios' : undefined,
  },
  {
    titulo: 'Enviar e ver as respostas chegando',
    descricao: 'Por e-mail ou WhatsApp, do jeito que seu cliente prefere.',
    feito: false,
    para: sessao.pode('envios.ver') ? '/envios' : undefined,
  },
])
const feitos = computed(() => passos.value.filter((p) => p.feito).length)
</script>

<template>
  <CabecalhoPagina :titulo="`${saudacao}, ${primeiroNome}!`" descricao="Aqui é o seu ponto de partida para cuidar da satisfação dos seus clientes." />

  <div class="grid gap-6 lg:grid-cols-5">
    <section class="cartao p-6 lg:col-span-3" aria-labelledby="titulo-passos">
      <div class="flex items-center justify-between gap-4">
        <h2 id="titulo-passos" class="text-lg font-bold text-texto">Primeiros passos</h2>
        <span class="text-sm font-semibold text-texto-fraco">{{ feitos }} de {{ passos.length }}</span>
      </div>
      <div class="mt-3 h-2 overflow-hidden rounded-full bg-superficie-2" role="progressbar" :aria-valuenow="feitos" aria-valuemin="0" :aria-valuemax="passos.length" aria-label="Progresso dos primeiros passos">
        <div class="h-full rounded-full bg-marca transition-all" :style="{ width: `${(feitos / passos.length) * 100}%` }" />
      </div>
      <ol class="mt-5 flex flex-col divide-y divide-borda">
        <li v-for="p in passos" :key="p.titulo" class="flex items-start gap-3 py-3.5">
          <CheckCircle2 v-if="p.feito" class="mt-0.5 size-5 shrink-0 text-sucesso" aria-hidden="true" />
          <Circle v-else class="mt-0.5 size-5 shrink-0 text-borda-forte" aria-hidden="true" />
          <div class="min-w-0 flex-1">
            <p class="font-semibold" :class="p.feito ? 'text-texto-fraco line-through decoration-texto-fraco/40' : 'text-texto'">
              <RouterLink v-if="p.para" :to="p.para" class="link">{{ p.titulo }}</RouterLink>
              <template v-else>{{ p.titulo }}</template>
              <span class="sr-only">{{ p.feito ? '(feito)' : '(a fazer)' }}</span>
            </p>
            <p class="text-sm text-texto-suave">{{ p.descricao }}</p>
          </div>
        </li>
      </ol>
    </section>

    <aside class="flex flex-col gap-6 lg:col-span-2">
      <section class="rounded-cartao bg-linear-to-br from-coral-500 to-coral-700 p-6 text-white shadow-cartao">
        <Sparkles class="size-7" aria-hidden="true" />
        <h2 class="mt-3 text-lg font-bold">Vem muita coisa por aí</h2>
        <p class="mt-1.5 text-sm leading-relaxed text-white/90">
          Contatos, formulários, envios, respostas e planos de ação já estão aqui. Em breve chegam os relatórios,
          aparecendo aqui no menu.
        </p>
      </section>
      <section class="cartao p-6">
        <h2 class="text-base font-bold text-texto">Sua conta</h2>
        <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt class="text-texto-fraco">Empresa</dt>
          <dd class="font-medium text-texto">{{ sessao.conta?.nome ?? '—' }}</dd>
          <dt class="text-texto-fraco">Seu e-mail</dt>
          <dd class="truncate font-medium text-texto">{{ sessao.usuario?.email }}</dd>
        </dl>
        <RouterLink to="/minha-conta" class="link mt-4 inline-block text-sm">Ver minha conta</RouterLink>
      </section>
    </aside>
  </div>
</template>
