<script setup lang="ts">
import { HelpCircle } from 'lucide-vue-next'

const aberta = defineModel<boolean>('aberta', { default: false })

const itens: { termo: string; explicacao: string }[] = [
  {
    termo: 'NPS e o medidor',
    explicacao:
      'Vai de −100 a 100: a porcentagem de promotores (notas 9 e 10) menos a de detratores (notas 0 a 6). Os neutros (7 e 8) só contam no total. No medidor, o marcador fica no valor; as faixas coloridas são detrator (abaixo de 0), neutro (0 a 49) e promotor (50 ou mais).',
  },
  { termo: 'Faixas do NPS', explicacao: 'Excelente: 75 ou mais. Muito bom: de 50 a 74. Pode melhorar: de 0 a 49. Crítico: abaixo de 0.' },
  {
    termo: 'Variação',
    explicacao: 'Embaixo do medidor: quanto o NPS subiu (▲) ou caiu (▼) em relação ao período anterior de mesmo tamanho, com o NPS de antes entre parênteses. Só aparece quando há um período escolhido.',
  },
  {
    termo: 'O que mudou',
    explicacao:
      'Uma frase montada por regras, sem IA: primeiro um pico de reclamações num tema; senão, uma queda ou alta de 5 pontos ou mais; senão, a receita das empresas com detrator; senão, "tudo estável". A linha de baixo traz o assunto seguinte. Os botões levam às respostas ou aos planos, ou criam de uma vez os planos das empresas com detrator e sem plano aberto (conforme o seu perfil).',
  },
  { termo: 'NPS dos decisores', explicacao: 'A mesma conta, só com os contatos que têm o perfil "Decisor" no cadastro, ou seja, quem decide a compra.' },
  {
    termo: 'Receita em risco',
    explicacao:
      'A soma do valor mensal do contrato das empresas que tiveram pelo menos um detrator no período. A porcentagem compara com a soma de todas as empresas do filtro que têm valor cadastrado (a carteira).',
  },
  { termo: 'Planos de ação', explicacao: 'Ações ainda não concluídas, de qualquer data. Vencidas são as que passaram do prazo. "Tratar" abre a ação mais urgente.' },
  {
    termo: 'Satisfação (CSAT) e taxa de resposta',
    explicacao:
      'CSAT: quantos por cento deram 4 ou 5 na pergunta de 1 a 5 (verde a partir de 80%, âmbar a partir de 60%). Taxa: dos contatos que receberam a pesquisa no período, quantos responderam; abaixo de 20%, a amostra é pequena. Sem dados, o cartão fica apagado com o atalho para resolver.',
  },
  {
    termo: 'NPS nos últimos 12 meses',
    explicacao:
      'Os 12 meses que terminam no fim do período escolhido (o grupo e "só ativas" valem; o período não). O fundo claro marca os meses do período; a faixa verde clara fica acima de 50; o menor e o maior mês têm o valor escrito. Mês sem resposta não tem ponto e a linha se interrompe. "Ver em tabela" mostra os mesmos números.',
  },
  {
    termo: 'Quem mudou de lado',
    explicacao:
      'Compara a última nota de cada contato com a anterior. Resgatados: eram detratores e passaram a dar 9 ou 10. Deixaram de ser promotores: davam 9 ou 10 e agora deram 8 ou menos.',
  },
  {
    termo: 'Do que estão falando',
    explicacao:
      'Os assuntos dos comentários de NPS. Na barra, as reclamações ficam à esquerda (vermelho) e as demais menções à direita (cinza), na mesma escala para todos os temas. ▲ e ▼ mostram quantas menções a mais ou a menos que no período anterior; a nota é a média de quem falou do assunto.',
  },
  {
    termo: 'Tom dos comentários',
    explicacao:
      'Pela análise da IA de cada comentário: negativo, misto (elogio e reclamação), neutro ou positivo. O número grande é a porcentagem de negativos entre os analisados, com a diferença em pontos para o período anterior. Só aparece com a análise por IA ligada; se a IA ainda não leu os comentários do período, o bloco avisa.',
  },
  { termo: 'Palavras que mais aparecem', explicacao: 'Quanto maior a palavra, em mais comentários ela aparece (contando uma vez por resposta).' },
  { termo: 'Empresas', explicacao: 'Só entram empresas com 3 ou mais respostas de NPS no período. A régua vai de −100 a 100: a barra sai do zero até o NPS da empresa.' },
  { termo: 'Só ativas', explicacao: 'Tira as respostas de empresas desativadas. Respostas sem empresa sempre contam.' },
  { termo: 'Respostas arquivadas', explicacao: 'Não entram em nenhum número do painel. Você arquiva e restaura na tela Respostas.' },
]
</script>

<template>
  <section id="ajuda-painel" class="cartao scroll-mt-24" aria-labelledby="t-ajuda">
    <details :open="aberta" @toggle="aberta = ($event.target as HTMLDetailsElement).open">
      <summary class="flex min-h-14 cursor-pointer list-none items-center gap-3 rounded-cartao px-5 py-3 sm:px-6 [&::-webkit-details-marker]:hidden">
        <HelpCircle class="size-5 shrink-0 text-marca-texto" aria-hidden="true" />
        <h2 id="t-ajuda" class="flex-1 text-base font-bold text-texto">Como ler o painel</h2>
        <span class="text-sm font-semibold text-marca-texto">{{ aberta ? 'Fechar' : 'Abrir' }}</span>
      </summary>
      <dl class="grid grid-cols-1 gap-x-8 gap-y-4 border-t border-borda px-5 py-5 sm:px-6 md:grid-cols-2">
        <div v-for="i in itens" :key="i.termo">
          <dt class="text-sm font-bold text-texto">{{ i.termo }}</dt>
          <dd class="mt-0.5 text-sm text-texto-suave">{{ i.explicacao }}</dd>
        </div>
      </dl>
    </details>
  </section>
</template>
