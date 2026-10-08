# Planos de ação: o resumo do topo (prazos, quem está com quantas e o que foi concluído)

Pedido do Marcelo (08/10/2026, 00h49): "melhore a tela enviar e respostas, assuma o papel de melhor arquiteto,
design e gestor de produtos.. e planos de ação também". O quadro mostrava os cartões, mas não respondia às perguntas
de quem cuida da equipe: "quanto está atrasado?", "com quem está o atraso?" e "a gente está resolvendo, e o cliente
fica sabendo?".

## API

`GET /acoes/panorama?<filtros>` (com `acoes.ver`), com os mesmos filtros do quadro (`docs/api-etapa-4a.md`, seção 5).

```json
{
  "prazos": {"abertas": 7, "vencidas": 4, "hoje": 1, "proximos_7_dias": 1, "depois": 1, "sem_prazo": 0},
  "responsaveis": [
    {"responsavel": {"id": 3, "nome": "Paula Souza"}, "abertas": 2, "vencidas": 2},
    {"responsavel": null, "abertas": 1, "vencidas": 0}
  ],
  "concluidas": {"de": "2026-09-09", "ate": "2026-10-08", "total": 3, "mediana_dias": 5.6, "com_retorno": 1,
                 "anterior": {"de": "2026-08-10", "ate": "2026-09-08", "total": 1, "mediana_dias": 2.0, "com_retorno": 0}}
}
```

- `prazos`: as abertas (a fazer e em andamento) por prazo: vencidas (prazo antes de hoje), vencem hoje, nos próximos
  7 dias, depois e sem prazo. "Hoje" é o dia em São Paulo, como no selo do cartão.
- `responsaveis`: as abertas de cada responsável (`null` = sem responsável), com as vencidas. Primeiro quem tem mais
  vencidas, depois quem tem mais abertas, depois o nome (sem responsável por último no empate). Até 8.
- `concluidas`: as concluídas nos últimos 30 dias (hoje incluído), a mediana de dias da criação à conclusão (uma casa)
  e quantas tiveram retorno ao cliente (o e-mail "Avisar o cliente", `retorno_em`); `anterior` é o mesmo nos 30 dias
  antes desses.
- Filtros: valem todos os do quadro, menos `so_vencidas` (é um jeito de ver o quadro, não um recorte: o resumo
  continua mostrando as em dia). A lista `responsaveis` ignora também `responsavel_id`, porque é nela que se escolhe
  a pessoa; os prazos e as concluídas seguem o filtro.

Sem migração.

## Site

- Topo de Planos de ação, acima dos filtros: a frase dos prazos ("4 de 7 ações abertas estão vencidas", em vermelho;
  "Nenhuma vencida, mas 2 vencem hoje"; "As 7 ações abertas estão em dia") e uma barra das abertas por prazo
  (vencidas em vermelho, hoje em âmbar, em dia em cinza, sem prazo em cinza claro), com a legenda escrita. Clicar em
  "4 vencidas" liga e desliga o "Só vencidas" do quadro.
- "Por responsável": cada pessoa com "3 abertas, 2 vencidas" e uma barra (a parte vencida em vermelho). Clicar
  filtra o quadro por ela (o filtro "Responsável" e o endereço mudam junto); a pessoa fica destacada, a frase ganha
  "Só as de Paula Souza. Ver de todos" e outro clique tira. Mostra 5 e "Ver mais".
- "Concluídas nos últimos 30 dias": o número, a comparação com os 30 dias anteriores, "Metade concluída em até N
  dias" e quantas tiveram retorno ao cliente. Em telas a partir de 1280 px fica ao lado; abaixo disso, embaixo.
- O resumo acompanha o quadro: busca de novo a cada carga dele (filtros, mover, salvar, concluir). Some quando a
  conta ainda não tem nenhuma ação (o quadro já mostra o convite) e tem o próprio aviso de erro, com "Tentar de novo".
- Cartão da ação: quando veio de uma resposta com comentário, mostra o comentário do cliente (até duas linhas) logo
  abaixo do título: dá para priorizar sem abrir o cartão.
- A coluna "A fazer" não mostra mais "N vencidas no quadro" (o resumo e o botão "Só vencidas N" já dizem).

## Testes

- `api/tests/test_acoes_panorama.py`: conta sem ações, prazos e responsáveis (com a ordem), filtros do quadro,
  mediana e retorno das concluídas (e o período anterior), permissão e isolamento entre contas.
- `web/tests/acoesPanorama.test.ts`: as regras (frase, barra, carga, concluídas) e o componente.
- `web/tests/kanbanComponente.test.ts`: o resumo na tela, seguindo os filtros, buscando de novo e filtrando por
  responsável e por vencidas.
