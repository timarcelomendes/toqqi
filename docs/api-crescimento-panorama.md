# Crescimento: o panorama do topo

Pedido do Marcelo (08/10/2026, 00h07): "faça a tela de crescimento ficar incrível, não me pergunte… execute…". O
resumo de dois cartões dos últimos 90 dias deu lugar a um panorama que responde, num período, quanto os clientes
felizes trouxeram, de onde veio, o que fazer agora, quem mais indica e o que estão dizendo.

## API

`GET /crescimento/panorama?de=&ate=` (com `crescimento.ver`, como o resto do Crescimento). Sem datas: os últimos 90
dias. Só `de`: até hoje. Só `ate`: sem começo e sem período anterior. Datas invertidas: 422, como no painel.

```json
{
  "periodo": {"de": "2026-07-11", "ate": "2026-10-08"},
  "anterior": {"de": "2026-04-12", "ate": "2026-07-10"},
  "receita": {"total": 23650.0, "indicacoes": 20880.0, "ofertas": 2770.0, "anterior": 8700.0},
  "indicacoes": {"promotores": 30, "recebidas": 20, "novas": 4, "em_contato": 6, "clientes": 7,
                 "nao_avancou": 3, "abordadas": 16, "esperando_contato": 5},
  "ofertas": {"feitas": 10, "aceitas": 4, "recusadas": 2, "sem_resposta": 1, "aguardando": 3,
              "prontas": 6, "sem_oferta": 1},
  "fas": [{"empresa": {"id": 1, "nome": "Rede Compre Bem"}, "indicacoes": 6, "clientes": 3, "receita_mensal": 12400.0}],
  "depoimentos": {"aprovados": 4, "pendentes": 2,
                  "destaque": {"resposta_id": 99, "comentario": "A entrega chega sempre no horário…",
                               "assinatura": "Juliana, Supermercado Ideal", "nota": 10, "tipo_nota": "nps",
                               "data_resposta": "2026-10-02T12:00:00-03:00"}},
  "meses": [{"mes": "2025-11", "indicacoes": 0, "ofertas": 0, "total": 0}, "… 12 meses, até o mês de hoje"],
  "tem_historico": true
}
```

- `receita`: a mesma conta da "Receita gerada pelo Toqqi" do Início (`GET /crescimento/resumo`): o valor mensal das
  indicações recebidas no período que viraram cliente + o valor das ofertas feitas no período que foram aceitas.
  `anterior` é a mesma soma no período anterior de mesmo tamanho (null sem começo).
- `indicacoes`: `promotores` = respostas de nota máxima no período (NPS 9–10 ou CSAT 5, a mesma regra do convite de
  indicação), não arquivadas; `recebidas` e as situações = indicações recebidas no período; `abordadas` = as que já
  saíram de "nova"; `esperando_contato` = as que estão em "nova" agora, de **qualquer** data (o próximo passo não
  esquece a indicação que ficou para trás).
- `ofertas`: as feitas no período, por resultado (`aguardando` = sem resultado); `prontas` = empresas nas listas de
  Oportunidades agora (Pode crescer ou Promotores recentes, com a regra de ouro); `sem_oferta` = delas, as sem oferta
  nos últimos 90 dias.
- `fas`: até 5 empresas que mais indicaram no período (indicações, depois clientes, depois receita, depois nome).
- `depoimentos`: aprovados e pendentes (de sempre) e o aprovado mais recente, não arquivado e com comentário, em
  destaque (espaços juntados, até 600 caracteres; a tela corta em 5 linhas).
- `meses`: a receita nova de cada um dos 12 meses de São Paulo que terminam no mês de hoje, pela mesma conta da
  `receita` (o mês de hoje vai até hoje). Não depende do período.
- `tem_historico`: a conta já teve um promotor, uma indicação ou uma oferta, em qualquer data.

Tudo dentro da conta (RLS); nada muda no banco (sem migração).

## Site (Crescimento, acima das abas)

- **Receita gerada pelo Toqqi** em número grande ("R$ 23,7 mil /mês", com o valor inteiro para leitores de tela e
  na dica), de onde veio ("7 indicações viraram cliente e 4 ofertas foram aceitas.") e a comparação com o período
  anterior (▲ em verde, ▼ em âmbar). Período: 30 dias, 90 dias (padrão) ou 12 meses, terminando hoje; trocar avisa o
  novo total aos leitores de tela e deixa os números antigos apagados até chegar o novo.
- **Mês a mês**: 12 barras da receita nova por mês; em destaque (coral), os meses do período escolhido; o mês de hoje
  mais claro (ainda não acabou); mês sem receita, um traço. Dica ao passar o mouse com o valor inteiro e a divisão
  entre indicações e ofertas; tabela escondida para leitores de tela.
- **As trilhas**, barras finas no mesmo começo, o resultado em coral e o resto em cinza:
  - Do promotor ao cliente: Promotores (notas 9 e 10) → Indicações recebidas → Abordadas (% das indicações) →
    Viraram cliente (% das indicações), com a receita das indicações no título.
  - Ofertas para clientes felizes: Ofertas feitas (quantas sem resultado) → Aceitas (% das feitas), com a receita das
    ofertas no título.
  - Só leva à lista o número que a lista mostra igual: "Indicações recebidas" abre Indicações com o mesmo período e
    "Viraram cliente" também com a situação; a tela rola até a lista (a troca de aba não rola mais a página:
    `manterRolagem` na rota).
- **Próximos passos** (até 3, nesta ordem): o convite de indicação desligado (quando a configuração diz isso), as
  indicações esperando o primeiro contato (Indicações › Novas), os clientes felizes sem oferta (Oportunidades) e os
  depoimentos esperando aprovação (Depoimentos).
- **Quem mais indica**: até 5 empresas, cada uma com uma barra dividida entre as indicações que viraram cliente (coral)
  e as outras (cinza), com legenda, a contagem escrita e a receita; o nome abre a empresa (com `contatos.ver`).
- **Depoimento mais recente**: a citação com a assinatura, a nota e a data, e "Ver os depoimentos". Aprovar, ocultar
  ou devolver um depoimento na aba atualiza o panorama.
- **Sem movimento no período**: o aviso "Nenhum promotor, indicação ou oferta nos últimos 30 dias." com "Ver os
  últimos 12 meses".
- **Conta que ainda não começou** (`tem_historico` falso): "Aqui aparece o que seus clientes felizes trazem", como
  funciona em 4 passos e os botões "Ligar o convite de indicação" (administrador, com o convite desligado) e "Enviar
  uma pesquisa".
- Tudo com os tokens do tema (claro e escuro), foco visível, sem rolagem lateral de 390 px para cima; as trilhas ficam
  lado a lado a partir de 1280 px e uma embaixo da outra abaixo disso.

## Fora

- Guardar o período escolhido (volta a 90 dias ao abrir a tela).
- Lista das ofertas feitas por período (as Oportunidades são uma lista de empresas; por isso os números das ofertas
  não levam a uma lista).
