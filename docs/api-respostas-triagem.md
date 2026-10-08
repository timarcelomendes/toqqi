# Respostas: "Para analisar", "Com comentário" e "Do que falam"

Pedido do Marcelo (08/10/2026, 00h49): "melhore a tela enviar e respostas, assuma o papel de melhor arquiteto,
design e gestor de produtos". Em Respostas, a lista mostrava tudo junto: para achar o que pedia atenção era preciso
montar filtros, e nada dizia de que os clientes estavam falando.

## API

`GET /respostas` aceita dois filtros novos (também no CSV, `GET /respostas.csv`):

- `para_analisar=true`: nota baixa (detrator do NPS ou insatisfeito do CSAT) ou comentário do cliente
  (`comentario_cliente` não vazio), e ainda sem análise da equipe (`analisada_em` vazio; salvar a análise no painel
  marca a resposta como analisada);
- `com_comentario=true`: só as com comentário do cliente.

`metricas` passa a descrever os filtros **sem** esses dois atalhos (o NPS, o CSAT e o total não mudam ao trocar de
visão; a página e o `total` da lista, sim) e ganha:

```json
{"para_analisar": 34, "com_comentario": 25,
 "temas": [{"chave": "prazo_entrega", "rotulo": "Prazo e entrega", "mencoes": 6, "nota_baixa": 3}]}
```

`temas`: os temas das respostas do filtro (NPS e CSAT), dos mais citados aos menos (empate: a ordem da tabela de
temas), até 6, com quantas menções vieram de nota baixa. Sem migração.

## Site

- Acima da lista: "Todas", "Para analisar" e "Com comentário", cada uma com a contagem ("Para analisar" em destaque
  quando há alguma). Vai no endereço como `?visao=para_analisar` (dá para compartilhar o link); "Limpar filtros" não
  tira a visão; "Limpar busca e filtros" tira. Analisar uma resposta no painel a tira de "Para analisar" na hora.
  "Para analisar" vazio mostra "Nada para analisar", com "Ver todas as respostas".
- No cartão dos números: "Do que falam", os temas citados com uma barra dividida entre as menções de nota baixa
  (vermelho) e as outras (cinza), com legenda, a contagem escrita e "N com nota baixa"; um clique filtra a lista pelo
  tema (o mesmo filtro "Tema" da área Filtros), outro tira. No celular, os 3 primeiros e "Ver mais N temas".
- Ajuda ("Ver e filtrar as respostas") atualizada.
