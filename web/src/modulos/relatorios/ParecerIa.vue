<script setup lang="ts">
// Relatórios (etapa 5d, docs/api-etapa-5d.md §6.2): botão "Parecer da IA" nas ações do cabeçalho e o painel lateral com o
// parecer dos filtros comuns da tela (período, grupo, só ativas): o resumo do recorte e as recomendações da semana. O
// estado vem de quem usa (usarGeracaoIa), que sabe se o botão aparece (some sem IA na plataforma).
import { Sparkles } from 'lucide-vue-next'
import type { ConteudoParecerIa } from '@/api'
import Botao from '@/components/ui/Botao.vue'
import Carregando from '@/components/ui/Carregando.vue'
import PainelLateral from '@/components/ui/PainelLateral.vue'
import BotaoGerarIa from '@/modulos/ia/BotaoGerarIa.vue'
import ConteudoGeracaoIa from '@/modulos/ia/ConteudoGeracaoIa.vue'
import MetaGeracaoIa from '@/modulos/ia/MetaGeracaoIa.vue'
import type { GeracaoIa } from '@/modulos/ia/usarGeracaoIa'

defineProps<{
  geracao: GeracaoIa<ConteudoParecerIa>
  /** Os filtros que o parecer leva em conta ("Últimos 90 dias · Todos os grupos · Só empresas ativas"). */
  descricao: string
  /** Datas escolhidas incompletas: não dá para abrir. */
  desabilitado?: boolean
}>()
const aberto = defineModel<boolean>('aberto', { default: false })
</script>

<template>
  <Botao variante="secundario" :desabilitado="desabilitado" aria-haspopup="dialog" data-abrir-parecer @click="aberto = true">
    <Sparkles class="size-4" aria-hidden="true" /> Parecer da IA
  </Botao>

  <PainelLateral v-model:aberto="aberto" titulo="Parecer da IA" :descricao="descricao">
    <!-- Lendo de novo depois de uma falha, o aviso fica (com o "Tentar de novo", que guarda o foco) no lugar do esqueleto -->
    <Carregando v-if="geracao.lendo && !geracao.atual && !geracao.erroLeitura" :linhas="4" rotulo="Carregando o parecer" />
    <div v-else class="flex flex-col gap-5" data-parecer-ia>
      <ConteudoGeracaoIa :geracao="geracao">
        <template #item="{ conteudo }">
          <section v-if="conteudo.resumo" aria-labelledby="t-parecer-resumo">
            <h3 id="t-parecer-resumo" class="mb-1.5 text-sm font-bold uppercase tracking-wide text-texto-fraco">Resumo</h3>
            <p class="break-words text-[0.95rem] leading-relaxed text-texto" data-resumo>{{ conteudo.resumo }}</p>
          </section>
          <section v-if="conteudo.recomendacoes.length" aria-labelledby="t-parecer-recomendacoes">
            <h3 id="t-parecer-recomendacoes" class="mb-1.5 text-sm font-bold uppercase tracking-wide text-texto-fraco">Recomendações da semana</h3>
            <ol class="flex list-decimal flex-col gap-2 pl-5 text-[0.95rem] leading-relaxed text-texto marker:font-semibold marker:text-texto-suave" data-recomendacoes>
              <li v-for="(r, i) in conteudo.recomendacoes" :key="i" class="break-words pl-1">{{ r }}</li>
            </ol>
          </section>
        </template>
      </ConteudoGeracaoIa>
      <MetaGeracaoIa :geracao="geracao" />
    </div>

    <!-- Para leitores de tela: o parecer gerado (inteiro) e o fim da espera (os avisos de erro já são regiões vivas) -->
    <p class="sr-only" aria-live="polite" aria-atomic="true" data-anuncio>{{ geracao.anuncio }}</p>

    <template v-if="geracao.mostrarBotao" #rodape>
      <BotaoGerarIa :geracao="geracao" variante="primario" class="flex-1 sm:flex-none" />
    </template>
  </PainelLateral>
</template>
