# Envios: o resumo do topo (envio automático, próximos 14 dias e taxa de resposta)

Pedido do Marcelo (08/10/2026, 00h49): "melhore a tela enviar e respostas, assuma o papel de melhor arquiteto,
design e gestor de produtos.. e planos de ação também". Em Envios, a pergunta que a tela não respondia era "as
pesquisas estão saindo? quando sai a próxima? e as pessoas estão respondendo?".

## API

`GET /envios/panorama` (com `envios.ver`).

```json
{
  "automatico": {"estado": "ligado", "proxima_rodada": "2026-10-08T14:00:00-03:00", "na_fila": 12,
                 "fora_da_rodada": 3, "por_rodada": 100, "proximo_contato": null, "janela_inicio": "08:00",
                 "janela_fim": "18:00", "so_dias_uteis": true, "intervalo_dias": 90, "canal": "email", "lembretes": 3},
  "agenda": [{"dia": "2026-10-08", "pesquisas": 12, "lembretes": 3, "sai": true}, "… 14 dias"],
  "respostas": {"de": "2026-09-09", "ate": "2026-10-08", "enviadas": 36, "respondidas": 17, "taxa": 47,
                "horas_ate_metade": 30.0, "canais": [{"canal": "email", "enviadas": 36, "respondidas": 17, "taxa": 47}],
                "anterior": {"…": "o mesmo nos 30 dias anteriores"}}
}
```

- `estado`: `desligado` (envios desligados), `parado` (falta uma pré-condição: assinatura, provedor ou formulário),
  `manual` (envios ligados sem o envio automático; os lembretes continuam saindo) ou `ligado`.
- `proxima_rodada` (só `ligado`): dentro da janela e dos dias úteis, 6 horas depois da última rodada (a regra do
  robô). As tarefas passam a cada 30 minutos, então a rodada sai até meia hora depois.
- `na_fila`: quem a rodada leva (ativo, na fila ou com erro, próximo envio vencido, com canal, fora do descanso e
  com menos de 3 falhas seguidas), até `por_rodada` por vez; `fora_da_rodada`: os da fila que não podem receber.
  Fila vazia: `proximo_contato` é o dia em que o próximo entra nela.
- `agenda`: hoje = `na_fila`; depois, quem tem o próximo envio no dia; `lembretes` = o próximo lembrete devido de
  cada convite. O que cairia num dia sem envio (fim de semana com "só dias úteis", ou hoje depois da janela) vai para
  o próximo dia em que sai; `sai` diz se o dia tem envio.
- `respostas`: convites por e-mail e WhatsApp criados no período que saíram de fato (enviado, entregue ou lido);
  `taxa` em %; `horas_ate_metade` = mediana do tempo até a resposta.

Sem migração.

## Site

- Topo de Envios: o estado com um ponto colorido, a frase do que acontece ("Próxima rodada hoje às 14h, para 12
  contatos", "Ninguém na fila agora. O próximo contato entra na fila em 23/11.", "As pesquisas só saem quando alguém
  envia por aqui"…), quem fica de fora, as regras em uma linha com "Mudar as regras" e a agenda de 14 dias em barras
  empilhadas (pesquisas em laranja, lembretes em azul, conferidas com o validador de paleta nos dois modos; dias sem
  envio listrados; dica por dia e tabela para leitores de tela; no celular, só o dia do mês). Ao lado, a taxa de
  resposta dos 30 dias, a comparação em pontos, o tempo até a metade responder e, com os dois canais, a taxa de
  cada um. Atualiza depois de um envio, de "Enviar lembretes agora" e de "Rodar envio automático agora".
- Aba Contatos: os cinco cartões viraram botões de filtro com a contagem dentro do cartão da lista ("Com erro" em
  vermelho quando há algum); a linha "N pesquisas enviadas… · N lembretes previstos" saiu (está no topo).
- Aba Histórico: "Como saiu" foi para baixo de "O quê" (a tabela cabia mal e o "Tentar de novo" ficava cortado); sem
  o botão, a célula fica vazia.
