<script setup lang="ts" generic="C">
// O miolo do resumo do painel e do parecer dos relatórios (etapa 5d, §6.1 e §6.2): gerando, o que está salvo (pelo slot
// `item`), o texto de quando não há nada (com o custo do nível: "Usa 2 análises de IA."), o aviso do erro da geração e
// por que não dá para gerar (conta pausada, cota esgotada ou insuficiente para o nível). O botão e o rodapé ficam com
// quem usa (o lugar muda no cartão e no painel lateral).
import { nextTick } from 'vue'
import { useSessaoStore } from '@/stores/sessao'
import Alerta from '@/components/ui/Alerta.vue'
import Carregando from '@/components/ui/Carregando.vue'
import { TEXTO_GERANDO } from './logica'
import type { GeracaoIa } from './usarGeracaoIa'

const props = defineProps<{
  geracao: GeracaoIa<C>
  /**
   * id do título que recebe o foco quando o aviso com "Tentar de novo" some e o botão de gerar não está na tela (o título
   * precisa de tabindex="-1"). Sem ele, o painel lateral em volta.
   */
  titulo?: string
}>()
defineSlots<{ item(props: { conteudo: C }): unknown }>()
const sessao = useSessaoStore()

function perdeuFoco(): boolean {
  const a = document.activeElement
  return !a || a === document.body || !a.isConnected
}

/** O foco vai para o botão de gerar ou, sem ele, para o título (ou o painel lateral): nunca fica no <body>. */
function focar(painel: HTMLElement | null) {
  const alvo = document.getElementById(props.geracao.idBotao) ?? (props.titulo ? document.getElementById(props.titulo) : null) ?? painel
  if (alvo?.isConnected) alvo.focus()
}

/** O painel lateral em volta do botão clicado (guardado antes: o aviso com o botão sai da página). */
const painelEmVolta = (e: Event) => (e.currentTarget instanceof HTMLElement ? e.currentTarget.closest<HTMLElement>('[role="dialog"]') : null)

/** A leitura falhou: lê de novo. Deu certo, o aviso some e o foco vai para o botão de gerar; falhou, fica no aviso. */
async function tentarLer(e: Event) {
  if (props.geracao.lendo) return
  const painel = painelEmVolta(e)
  await props.geracao.ler()
  await nextTick()
  if (perdeuFoco()) focar(painel)
}

/** A geração falhou (503): o foco vai antes para o botão de gerar (o aviso some na hora) e fica nele enquanto gera. */
async function tentarGerar(e: Event) {
  if (!props.geracao.podeGerar) return
  const painel = painelEmVolta(e)
  focar(painel)
  await props.geracao.gerar()
  await nextTick()
  // O botão saiu com a resposta (cota esgotada, conta pausada): o foco vai para o título.
  if (perdeuFoco()) focar(painel)
}
</script>

<template>
  <Alerta v-if="geracao.erroLeitura" tom="erro" data-erro-leitura>
    {{ geracao.erroLeitura }}
    <!-- aria-disabled (não disabled) enquanto lê: o foco fica no botão se a leitura falhar de novo -->
    <button
      type="button"
      class="link ml-1 aria-disabled:cursor-not-allowed aria-disabled:opacity-55"
      :aria-disabled="geracao.lendo || undefined"
      data-tentar-ler
      @click="tentarLer"
    >
      Tentar de novo
    </button>
  </Alerta>

  <div v-else class="flex flex-col gap-4">
    <div v-if="geracao.gerando" class="flex flex-col gap-3" data-gerando>
      <Carregando :linhas="3" :rotulo="TEXTO_GERANDO" />
      <p class="text-sm text-texto-suave" aria-hidden="true">{{ TEXTO_GERANDO }}</p>
    </div>
    <slot v-else-if="geracao.item" name="item" :conteudo="geracao.item.conteudo" />
    <p v-else-if="geracao.disponivel" class="text-sm text-texto-suave" data-vazio>{{ geracao.textoVazio }}</p>

    <Alerta v-if="geracao.prontoAnterior" tom="info" data-pronto-anterior>{{ geracao.prontoAnterior }}</Alerta>

    <Alerta v-if="geracao.erro" :tom="geracao.erro.tom" data-erro-geracao>
      {{ geracao.erro.mensagem }}
      <button v-if="geracao.erro.repetir" type="button" class="link ml-1" :disabled="!geracao.podeGerar" data-tentar-de-novo @click="tentarGerar">
        Tentar de novo
      </button>
    </Alerta>

    <Alerta v-if="geracao.bloqueio" tom="atencao" data-bloqueio>
      {{ geracao.bloqueio }}
      <RouterLink v-if="geracao.cotaEsgotada && sessao.pode('configuracoes.gerenciar')" to="/configuracoes/ia" class="link mt-1 block" data-link-config-ia>
        Configurações › IA
      </RouterLink>
      <RouterLink
        v-else-if="geracao.cotaInsuficiente && sessao.pode('configuracoes.gerenciar')"
        to="/configuracoes/ia"
        class="link mt-1 block"
        data-link-trocar-nivel
      >
        Trocar o nível
      </RouterLink>
    </Alerta>
  </div>
</template>
