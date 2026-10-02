# Toqqi · Início (painel) v2: mais bonito e mais útil

Pedido do Marcelo (02/10, 16:34): "esse painel pode ficar mais bonito e interessante?". Proposta aprovada no canvas
"Toqqi · Novo painel (Início)" (https://claude.ai/artifact/CyTK4vXKTbDSAtwVY3AdSR), com o acréscimo dele do indicador
"Tom dos comentários" ao lado das palavras ("pode implementar", 17:03). O canvas é a referência visual; este arquivo diz o que
muda nos dados e nas telas. Mesmas convenções das etapas anteriores (base `/api/v1`, Bearer, RLS, design-system).

## 0. Decisões
- Nada de IA nova: a manchete "O que mudou" é montada por regras no site a partir do que o painel já devolve (variação, picos,
  receita em risco, planos de ação). Não gasta cota.
- Os mesmos filtros de hoje (período, grupo, só ativas) valem para tudo, salvo a evolução, que mostra **12 meses terminando no fim
  do período** com o período destacado.
- Componentes e tokens do design-system (`web/src/components/ui`, `main.css`); cores de gráfico pelos tokens `grafico-*`; tudo em
  claro e escuro, 390 px a 1440 px. Nenhum gráfico depende só de cor: números e nomes escritos ao lado; "Ver em tabela" continua
  na evolução.
- A ordem e o conteúdo dos blocos seguem o canvas (de cima para baixo): cabeçalho com filtros em pílulas; primeiros passos em uma
  linha; Resumo (medidor do NPS + O que mudou + distribuição); faixa de indicadores; evolução 12 meses + Quem mudou de lado; Do que
  estão falando (barras divergentes) + coluna com Tom dos comentários e Palavras; Comentários; Empresas.

## 1. API (`GET /painel`, mesmo esquema de permissões)
Acréscimos (nada é removido; quem lê hoje continua funcionando):
- `evolucao_12m`: `[{mes: "AAAA-MM", nps: int|null, total: int, no_periodo: bool}]` — sempre 12 itens, do mês de `ate` − 11 até
  o mês de `ate` (sem período: até hoje), meses sem resposta com `nps: null, total: 0`; aplica grupo e só ativas, **não** o
  período; `no_periodo` = o mês cruza o período do filtro. Fuso de São Paulo como a `evolucao`.
- `tom`: `{analisados: int, com_comentario: int, total_respostas: int, pendentes: int, negativo: int, misto: int, neutro: int, positivo: int,
  anterior: {analisados, negativo} | null}` — respostas do período (mesmos filtros e mesma base do NPS do painel, NPS e CSAT)
  com comentário do cliente; `analisados` = as que têm `ia_sentimento`; `pendentes` = com comentário e `ia_situacao='pendente'`; `anterior` = o mesmo no período anterior (quando há
  período). Reaproveite a contagem de sentimento de `relatorios/servico.py` se servir.
- `atencao.receita_em_risco.carteira`: soma de `valor_mensal` das empresas no filtro (só ativas se o filtro pedir; grupo), para
  o site mostrar a porcentagem; `null` se nenhuma tiver valor.
- `empresas.menor[]` e `empresas.maior[]` ganham `valor_mensal: number|null`.
- Testes: os 4 acréscimos, com e sem período, filtros de grupo/ativas, meses vazios, RLS.

## 2. Site (`web/src/modulos/painel`, `web/src/modulos/inicio`)
- **Cabeçalho**: data por extenso pequena acima da saudação ("Sexta, 2 de outubro"); filtros como pílulas (os mesmos controles
  de hoje, acessíveis) e "Exportar CSV" e "Como ler os números" discretos à direita; no celular quebram linha.
- **Primeiros passos** (enquanto não ocultado e incompleto): uma linha com 4 marcadores de progresso, "Primeiros passos: X de 4."
  e o próximo passo com o link; "Ocultar" continua. O cartão do teste grátis (`CartaoTeste`) fica como está, acima.
- **Faixa de picos**: deixa de ser faixa separada quando houver pico — vira a manchete do Resumo (abaixo). Sem pico, nada.
- **Resumo** (um cartão, duas áreas):
  - Esquerda: "NPS dos últimos N dias" (rótulo do período), **medidor semicircular** −100 a 100 com as faixas detrator
    (<0), neutro (0–49), promotor (≥50) em tons suaves e o marcador no valor; número grande no centro; selo da faixa (o mesmo de
    hoje: "Pode melhorar" etc.); variação "▼ 11 pontos sobre os N dias antes (34)" (▲ verde / ▼ vermelho / = cinza). Sem NPS no
    período: o estado vazio de hoje.
  - Direita: rótulo "O QUE MUDOU", **manchete** em 1–2 frases e uma linha de apoio, pelas regras de §3; até 3 botões de ação
    (primário/secundário/ToqqiAI) conforme a regra; a barra de distribuição (detratores/neutros/promotores com contagem e %),
    "N respostas" e "decisores: X" como hoje.
- **Indicadores** (faixa de cartões compactos, `auto-fit`): Receita em risco (valor/mês, "N empresas com detrator · X% da
  carteira" quando houver carteira); Planos de ação (abertos, vencidos); CSAT; Taxa de resposta. Indicador sem dado vira cartão
  apagado (fundo `superficie-2`, borda tracejada) com a frase curta e um atalho para resolver (CSAT → Formulários; taxa → Envios),
  só se o perfil puder.
- **NPS nos últimos 12 meses** (`evolucao_12m`): área + linha (`grafico-serie`), faixa de fundo suave acima de 50, linha do zero,
  meses do período com fundo `marca-suave`, menor e maior ponto marcados com o valor (vermelho/verde), meses sem resposta sem ponto
  (a linha quebra); dica ao passar/tocar com mês, NPS e respostas; "Ver em tabela" com os 12 meses. O `GraficoEvolucao` atual pode
  ser reescrito.
- **Quem mudou de lado** (movimentação): dois blocos (resgatados em fundo `sucesso-suave`, deixaram de ser promotores em
  `erro-suave`) com o número grande e os selos "detrator → promotor" / "promotor → 8 ou menos"; "Ver as N pessoas" abre a lista de
  hoje.
- **Do que estão falando** (temas): uma linha por tema (cor do tema no ponto), **barra divergente** com reclamações à esquerda
  (`grafico-detrator`) e demais menções à direita (`grafico-cinza`), escala comum ao maior valor; à direita a variação de menções
  (▲/▼/=) e a nota média; legenda; leitor de tela lê "Prazo e entrega: 13 menções, 8 reclamações, nota média 6,2, 9 a mais que
  no período anterior". No celular, nome acima da barra.
- **Coluna ao lado**: **Tom dos comentários** (`tom`) — % de negativos em destaque com a variação em pontos sobre o anterior,
  barra empilhada negativo/misto/neutro/positivo (tokens do sentimento do design-system), legenda com contagens, "N de M respostas
  vieram com comentário (X%)", nota "Pela análise da IA". Sem nenhum analisado (só pelo `tom` do painel, sem ler `GET /conta/ia`, e reagindo
  à troca de filtro): `pendentes > 0` → "Os comentários ainda estão sendo analisados"; `pendentes = 0` com comentários →
  "Ligue a análise por IA em Configurações › IA para ver o tom" (link só para `configuracoes.gerenciar`; para os outros, sem
  link: "A análise por IA está desligada ou ainda não chegou a estes comentários.").
  Abaixo, **Palavras que mais aparecem** como nuvem: tamanho por contagem (4 níveis), palavras de comentários negativos em
  `marca-texto`, de positivos em `sucesso`, demais em `texto-suave` — se a API não disser o tom da palavra, todas em
  `texto`/`texto-suave` pelo tamanho (não inventar).
- **Comentários**: cartões como citações, nota num selo com a cor do grupo, fundo suave do grupo, nome e empresa, data; clicar abre
  a resposta como hoje.
- **Empresas: onde cuidar e onde crescer**: duas colunas ("Cuidar primeiro" = menor, "Mais satisfeitas" = maior), cada linha com
  nome, "N respostas · R$ X mil/mês" (quando houver valor), **régua** −100 a 100 com marca no zero e barra do zero até o valor
  (vermelha/verde), e o NPS escrito.
- "Como ler o painel" continua (texto atualizado para os blocos novos).

## 3. Manchete "O que mudou" (regras, `logica.ts`, testadas)
Prioridade (a primeira que valer; a linha de apoio usa a seguinte que valer):
1. (Só quando o período termina hoje e não há grupo filtrado: os picos da API são sempre da conta inteira nos últimos 7 dias.)
   Pico de reclamações em um tema: "**{N} reclamações de {Tema}** em 7 dias, quando a média era {m} por semana." Se a variação do
   NPS for ≤ −5, antes: "O NPS caiu {x} pontos."
2. Variação ≤ −5: "O NPS caiu {x} pontos em relação aos {N} dias antes."
3. Variação ≥ +5: "O NPS subiu {x} pontos em relação aos {N} dias antes."
4. Receita em risco > 0: "{N} empresas tiveram detrator no período, somando **R$ {v} por mês** em contrato." + "Nenhuma tem plano
   de ação aberto." quando `acoes_abertas = 0`, ou "{a} planos abertos, {v} vencidos."
5. Nada disso: "Tudo estável: o NPS variou {x} pontos." (ou, sem anterior, "{N} respostas no período.").
Botões: com pico → "Ver as {N} reclamações" (Respostas filtradas pelo tema, como o "Ver respostas" de hoje); com detratores sem
plano → "Ver os detratores" (Respostas com grupo detrator) ou o que hoje leva aos planos; e "Perguntar ao ToqqiAI" (abre o chat
com a pergunta "O que explica a variação do NPS no período?") só se o ToqqiAI estiver disponível. Valores em moeda curta
("R$ 265,2 mil", "R$ 1,2 mi").
