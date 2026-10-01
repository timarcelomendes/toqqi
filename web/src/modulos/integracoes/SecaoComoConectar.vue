<script setup lang="ts">
import { computed } from 'vue'
import { PackageCheck, Plug, Wrench } from 'lucide-vue-next'
import { API_URL } from '@/api'
import Alerta from '@/components/ui/Alerta.vue'
import BlocoCodigo from './BlocoCodigo.vue'
import { CAMPOS_PESQUISA, CHAVE_EXEMPLO, EXEMPLO_PESQUISA, exemploCurl, exemploCurlTeste, urlApi } from './logica'

const urlPesquisas = computed(() => urlApi(API_URL, '/integracao/pesquisas'))
const curl = computed(() => exemploCurl(API_URL))
const curlTeste = computed(() => exemploCurlTeste(API_URL))
const corpo = JSON.stringify(EXEMPLO_PESQUISA, null, 2)

const ferramentas = computed(() => [
  {
    nome: 'Zapier',
    passos: [
      'Crie um Zap com o gatilho do seu sistema (ex.: "pedido entregue").',
      'Na ação, escolha "Webhooks by Zapier" e depois "POST".',
      `Em URL, cole ${urlPesquisas.value}`,
      'Em "Payload Type", escolha "json" e preencha os campos (email, telefone, nome, referencia...).',
      `Em "Headers", adicione X-Api-Key com a sua chave.`,
    ],
  },
  {
    nome: 'Make',
    passos: [
      'No cenário, depois do módulo do seu sistema, adicione "HTTP" e escolha "Make a request".',
      `Method: POST. URL: ${urlPesquisas.value}`,
      'Em Headers, adicione X-Api-Key com a sua chave.',
      'Body type: Raw, Content type: JSON (application/json). Cole o corpo de exemplo e troque pelos dados do pedido.',
    ],
  },
  {
    nome: 'n8n',
    passos: [
      'Adicione o nó "HTTP Request" depois do gatilho do seu sistema.',
      `Method: POST. URL: ${urlPesquisas.value}`,
      'Em Authentication, escolha "Generic Credential Type" → "Header Auth", com Name X-Api-Key e Value a sua chave.',
      'Ligue "Send Body", escolha JSON e preencha os campos.',
    ],
  },
])
</script>

<template>
  <div class="flex flex-col gap-6">
    <section class="cartao p-5 sm:p-6" aria-labelledby="t-como-funciona">
      <div class="flex items-start gap-3">
        <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><Plug class="size-5" aria-hidden="true" /></div>
        <div>
          <h2 id="t-como-funciona" class="text-base font-bold text-texto">Como funciona</h2>
          <p class="mt-1 max-w-3xl text-sm text-texto-suave">
            Quando um pedido for entregue, o sistema da sua empresa avisa o Toqqi e o cliente recebe a pesquisa na hora, por WhatsApp ou e-mail.
            Ninguém precisa lembrar de enviar. Se o cliente ainda não estiver nos seus contatos, ele é cadastrado sozinho.
          </p>
        </div>
      </div>
      <ol class="mt-5 grid gap-3 sm:grid-cols-3">
        <li class="rounded-xl border border-borda p-4">
          <p class="text-sm font-bold text-texto">1. Gere a chave</p>
          <p class="mt-1 text-sm text-texto-suave">Na aba "Chave de integração". Ela aparece uma vez só.</p>
        </li>
        <li class="rounded-xl border border-borda p-4">
          <p class="text-sm font-bold text-texto">2. Entregue para o técnico</p>
          <p class="mt-1 text-sm text-texto-suave">Mande a chave e o link desta página para quem cuida do sistema da sua empresa.</p>
        </li>
        <li class="rounded-xl border border-borda p-4">
          <p class="text-sm font-bold text-texto">3. Pronto</p>
          <p class="mt-1 text-sm text-texto-suave">A cada entrega, o cliente recebe a pesquisa. As respostas aparecem aqui no Toqqi.</p>
        </li>
      </ol>
      <p class="mt-4 text-sm text-texto-fraco">
        O Toqqi respeita quem saiu da lista e o descanso entre pesquisas: um cliente que recebeu uma pesquisa há pouco tempo não recebe outra.
      </p>
    </section>

    <section class="cartao p-5 sm:p-6" aria-labelledby="t-tecnico">
      <div class="mb-5 flex items-start gap-3">
        <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-info-suave text-info"><Wrench class="size-5" aria-hidden="true" /></div>
        <div>
          <h2 id="t-tecnico" class="text-base font-bold text-texto">Para quem cuida do sistema da sua empresa</h2>
          <p class="mt-1 text-sm text-texto-suave">Exemplos prontos para copiar. Troque {{ CHAVE_EXEMPLO }} pela chave gerada.</p>
        </div>
      </div>

      <div class="flex flex-col gap-6">
        <div class="flex flex-col gap-2">
          <h3 class="text-sm font-bold text-texto">Enviar uma pesquisa quando o pedido for entregue</h3>
          <p class="text-sm text-texto-suave">
            <code class="rounded bg-superficie-2 px-1.5 py-0.5 font-mono text-xs">POST {{ urlPesquisas }}</code>, com a chave no cabeçalho
            <code class="rounded bg-superficie-2 px-1.5 py-0.5 font-mono text-xs">X-Api-Key</code>. Precisa de e-mail ou telefone do cliente.
          </p>
          <BlocoCodigo :texto="curl" rotulo="Copiar comando"><template #titulo>cURL</template></BlocoCodigo>
          <details class="group rounded-xl border border-borda">
            <summary class="cursor-pointer px-4 py-2.5 text-sm font-semibold text-texto">Só o corpo (JSON), para colar no Zapier, Make ou n8n</summary>
            <div class="px-4 pb-4"><BlocoCodigo :texto="corpo" rotulo="Copiar JSON"><template #titulo>JSON</template></BlocoCodigo></div>
          </details>
        </div>

        <div class="flex flex-col gap-2">
          <h3 class="text-sm font-bold text-texto">Conferir se a chave funciona</h3>
          <p class="text-sm text-texto-suave">Responde com o nome da sua conta e <code class="font-mono text-xs">"ok": true</code>. Não envia nada para clientes.</p>
          <BlocoCodigo :texto="curlTeste" rotulo="Copiar comando"><template #titulo>cURL</template></BlocoCodigo>
        </div>

        <div class="flex flex-col gap-2">
          <h3 class="text-sm font-bold text-texto">O que o Toqqi responde</h3>
          <p class="text-sm text-texto-suave">
            Um JSON com <code class="font-mono text-xs">situacao</code> (<code class="font-mono text-xs">enviado</code>,
            <code class="font-mono text-xs">link_gerado</code>, <code class="font-mono text-xs">ignorado_descadastrado</code>,
            <code class="font-mono text-xs">ignorado_descanso</code>, <code class="font-mono text-xs">ignorado_inativo</code>,
            <code class="font-mono text-xs">sem_canal</code> ou <code class="font-mono text-xs">erro</code>), o
            <code class="font-mono text-xs">link</code> da pesquisa, o <code class="font-mono text-xs">canal</code> usado e uma
            <code class="font-mono text-xs">mensagem</code> explicando. Limite de 120 chamadas por minuto.
          </p>
        </div>

        <div class="flex flex-col gap-2">
          <h3 class="text-sm font-bold text-texto">Campos aceitos</h3>
          <div class="overflow-x-auto rounded-xl border border-borda">
            <table class="w-full min-w-[36rem] text-left text-sm">
              <caption class="sr-only">Campos aceitos para enviar uma pesquisa</caption>
              <thead class="bg-superficie-2 text-xs uppercase tracking-wide text-texto-fraco">
                <tr>
                  <th scope="col" class="px-3 py-2 font-semibold">Campo</th>
                  <th scope="col" class="px-3 py-2 font-semibold">Exemplo</th>
                  <th scope="col" class="px-3 py-2 font-semibold">Para que serve</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-borda">
                <tr v-for="c in CAMPOS_PESQUISA" :key="c.campo">
                  <th scope="row" class="whitespace-nowrap px-3 py-2 font-mono text-xs font-semibold text-texto">{{ c.campo }}</th>
                  <td class="px-3 py-2 font-mono text-xs text-texto-suave">{{ c.exemplo }}</td>
                  <td class="px-3 py-2 text-texto-suave">{{ c.descricao }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <section class="cartao p-5 sm:p-6" aria-labelledby="t-ferramentas">
      <div class="mb-5 flex items-start gap-3">
        <div class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-marca-suave text-marca-texto"><PackageCheck class="size-5" aria-hidden="true" /></div>
        <div>
          <h2 id="t-ferramentas" class="text-base font-bold text-texto">Sem programar: Zapier, Make ou n8n</h2>
          <p class="mt-1 text-sm text-texto-suave">Se o seu sistema já conversa com uma dessas ferramentas, dá para ligar ao Toqqi em poucos minutos.</p>
        </div>
      </div>
      <div class="grid gap-4 lg:grid-cols-3">
        <div v-for="f in ferramentas" :key="f.nome" class="min-w-0 rounded-xl border border-borda p-4">
          <h3 class="font-bold text-texto">{{ f.nome }}</h3>
          <ol class="mt-2 flex list-decimal flex-col gap-1.5 pl-5 text-sm text-texto-suave">
            <li v-for="(p, i) in f.passos" :key="i" class="break-words">{{ p }}</li>
          </ol>
        </div>
      </div>
      <Alerta tom="info" class="mt-4">
        Para o Zapier ou o Make conferirem a chave na hora de conectar, use o endereço de teste: <span class="break-all font-mono text-xs">{{ urlApi(API_URL, '/integracao/teste') }}</span>
      </Alerta>
    </section>
  </div>
</template>
