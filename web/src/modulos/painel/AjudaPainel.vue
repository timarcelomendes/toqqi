<script setup lang="ts">
import { HelpCircle } from 'lucide-vue-next'

const aberta = defineModel<boolean>('aberta', { default: false })

const itens: { termo: string; explicacao: string }[] = [
  {
    termo: 'NPS',
    explicacao:
      'Vai de −100 a 100. É a porcentagem de promotores (notas 9 e 10) menos a de detratores (notas 0 a 6). Os neutros (7 e 8) só contam no total de respostas.',
  },
  { termo: 'Faixas do NPS', explicacao: 'Excelente: 75 ou mais. Muito bom: de 50 a 74. Pode melhorar: de 0 a 49. Crítico: abaixo de 0.' },
  { termo: 'NPS dos decisores', explicacao: 'A mesma conta, só com os contatos que têm o perfil "Decisor" no cadastro, ou seja, quem decide a compra.' },
  {
    termo: 'Variação',
    explicacao: 'Quanto o NPS subiu ou caiu em relação ao período anterior, de mesmo tamanho. Só aparece quando você escolhe um período.',
  },
  { termo: 'Satisfação (CSAT)', explicacao: 'Pesquisa com notas de 1 a 5. Mostra quantos por cento deram 4 ou 5 e a média. Verde a partir de 80%, âmbar a partir de 60%.' },
  {
    termo: 'Taxa de resposta',
    explicacao: 'Dos contatos que receberam a pesquisa no período, quantos responderam. Abaixo de 20%, a amostra é pequena e os números podem mudar bastante.',
  },
  {
    termo: 'Movimentação',
    explicacao:
      'Compara a última nota de cada contato com a anterior. Resgatado: era detrator e passou a dar 9 ou 10. Deixou de ser promotor: dava 9 ou 10 e agora deu 8 ou menos.',
  },
  {
    termo: 'Precisa de atenção',
    explicacao: 'Ações ainda não concluídas, de qualquer data. Vencidas são as que passaram do prazo. "Tratar" abre a ação mais urgente da empresa.',
  },
  { termo: 'Receita em risco', explicacao: 'A soma do valor mensal do contrato das empresas que tiveram pelo menos um detrator no período.' },
  {
    termo: 'Assuntos mais citados',
    explicacao: 'Achados por palavras nos comentários (por exemplo, "atrasou" conta como Prazo e entrega). A nota média é a das respostas que falam do assunto.',
  },
  { termo: 'Só empresas ativas', explicacao: 'Tira as respostas de empresas desativadas. Respostas sem empresa sempre contam.' },
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
