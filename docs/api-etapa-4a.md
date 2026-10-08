# Toqqi · API da etapa 4a (respostas, planos de ação e painel)

Mesmas convenções das etapas anteriores: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, `requer(...)`,
listas paginadas `{itens,total,pagina,por_pagina}`, datas ISO 8601, valores em reais como decimal. Dias e meses de regra em
America/Sao_Paulo (`toqqi.core.relogio`). A etapa 4b trará relatórios, IA por resposta e resumo semanal.

## 0. Decisões desta etapa (itens "a decidir" da especificação)
- **Grupo ≠ tema.** `grupo` (detrator/neutro/promotor; insatisfeito/neutro/satisfeito no CSAT) vem sempre da nota.
  O assunto do comentário vai em `temas` (lista). Na interface, o grupo se chama **Categoria**.
- **Ação automática**: detrator e neutro sempre; promotor só se `acao_promotor` (padrão **desligado**). CSAT: só insatisfeito
  (nota 1–2), com o prazo do detrator. Prazos configuráveis de 1 a 90 dias (padrão 2/5/7).
- **NPS** = % promotores − % detratores, arredondado com **meio para cima, longe do zero** (12,5 → 13; −12,5 → −13; como o ARRED do
  Excel). Use `Decimal` com `ROUND_HALF_UP` sobre o valor exato `(p − d) × 100 / total`. Mesma regra no CSAT (%).
- **Resposta registrada à mão** segue o mesmo fluxo (grupo, temas, ação, alerta, webhook), **sem** e-mail de agradecimento.
- **Resposta importada** (histórico) ganha grupo, temas e atualiza a última nota do contato, mas **não** cria ação, alerta,
  agradecimento nem webhook, e não mexe na fila de envios.
- Importação: "9,0" vira 9; **"8,7" é recusada** (linha com problema).
- **Concluir ação** exige responsável e "o que foi feito"; o servidor confere (422).
- **Taxa de resposta** = contatos que responderam no período ÷ contatos ativos que **receberam convite** no período.
- Sem período escolhido, o painel **não mostra variação**.
- **Só ativos** tira respostas de empresas inativas (respostas sem empresa sempre contam), no painel e, na 4b, nos relatórios.
- **Excluir resposta de vez**: só perfil admin; apaga as ações ligadas a ela; auditoria.
- **Alerta ao responsável**: quando uma ação de prioridade alta nasce de uma resposta e o responsável da empresa tem e-mail, sai o
  e-mail "Alerta de risco" pelo provedor da plataforma, depois do commit. É e-mail do sistema: não entra no histórico de envios.

## 1. Banco (migração `0005_respostas_acoes`)
`respostas` ganha:
- `respondida_em timestamptz` — data informada (resposta à mão com data, importação). Vazia nas respostas de pesquisa.
- `data_resposta timestamptz GENERATED ALWAYS AS (coalesce(respondida_em, criada_em)) STORED` — **a data de toda regra de período**.
  Índice `(conta_id, data_resposta DESC) WHERE NOT arquivada`.
- `origem text NOT NULL DEFAULT 'pesquisa' CHECK (origem IN ('pesquisa','manual','importacao'))` (as existentes com canal
  `importacao` viram `importacao`; `manual` viram `manual`).
- `temas text[] NOT NULL DEFAULT '{}'`, `temas_manuais boolean NOT NULL DEFAULT false`.
- `o_que_faltou text` (≤ 2000), `o_que_combinamos text` (≤ 2000), `analisada_em timestamptz`, `analisada_por bigint`
  (FK composta para usuarios, `ON DELETE SET NULL (analisada_por)`), `registrada_por bigint` (idem), `arquivada_em timestamptz`.
- `canal` aceita também `telefone` e `reuniao`.
- As respostas que já existem recebem `temas` calculados pela migração (mesma função de palavras-chave).

Tabela nova `acoes` (RLS FORCE, política padrão, grants condicionais, FKs compostas `(id, conta_id)`):
`id, conta_id, resposta_id (SET NULL), empresa_id (SET NULL), contato_id (SET NULL), responsavel_id (SET NULL),
titulo text NOT NULL (1–200), descricao text NOT NULL DEFAULT '' (≤ 4000), resolucao text (≤ 4000),
prioridade text NOT NULL CHECK IN ('alta','media','baixa'), prazo date,
situacao text NOT NULL DEFAULT 'a_fazer' CHECK IN ('a_fazer','em_andamento','concluida'),
origem text NOT NULL DEFAULT 'manual' CHECK IN ('automatica','manual'), grupo text, tipo_nota text, nota smallint,
criado_por (usuario, SET NULL), criada_em, atualizada_em, iniciada_em, concluida_em, concluida_por (usuario, SET NULL)`.
Índice único parcial: uma ação **automática** por resposta (`(conta_id, resposta_id) WHERE origem = 'automatica'`).
Índices para o quadro: `(conta_id, situacao, prazo)`, `(conta_id, empresa_id)`.

Tabela nova `config_acoes` (1 linha por conta, criada com os padrões na primeira leitura, RLS FORCE):
`prazo_detrator 2, prazo_neutro 5, prazo_promotor 7 (cada um 1–90), acao_promotor false, atualizado_em`.

`importacoes` ganha `tipo text NOT NULL DEFAULT 'contatos' CHECK IN ('contatos','respostas')`.

## 2. Temas (palavras-chave, sem IA)
`GET /respostas/temas` (`respostas.ver`) → `[{chave, rotulo}]`, nesta ordem:
| chave | rótulo | palavras (início de palavra, sem acento, sem maiúsculas) |
|---|---|---|
| `prazo_entrega` | Prazo e entrega | atras, demor, prazo, entreg, chegou, chegada, frete, transportadora, motorista, coleta, logistica |
| `produto_avarias` | Produto e avarias | avaria, quebrad, danificad, amassad, estragad, vencid, validade, defeito, qualidade, embalage, produto errado, faltando, troca, devoluc, devolv |
| `atendimento` | Atendimento | atendiment, atendente, atencios, vendedor, representante, educad, grosseir, simpati, cordial, prestativ, suporte, sac, pos venda |
| `preco_condicoes` | Preço e condições | preco, caro, valor, desconto, promoc, condic, pagamento, boleto, parcel, juros, credito, tabela, custo, barat |
| `comunicacao` | Comunicação | comunica, informac, inform, avis, retorno, contato, ligac, telefone, whatsapp, email, e mail, rastre, acompanhament, atualizac |
| `sistema_pedidos` | Sistema e pedidos | sistema, site, aplicativo, app, portal, plataforma, fazer pedido, tirar pedido, pedido errado, pedido incompleto, erro no pedido, digitac, nota fiscal, nf, nfe, faturament, cadastro, login, senha |
- Texto analisado: `comentario` + `o_que_faltou`. Normalização: minúsculas, sem acento, hífen e pontuação viram espaço.
  Palavra simples casa com início de palavra (`\bentreg`); expressão com espaço casa a sequência inteira.
- Recalcula ao gravar e ao editar o comentário, **salvo** `temas_manuais` (alguém marcou à mão na análise).
- Uma resposta pode ter vários temas (ou nenhum). Funções puras em `toqqi/modulos/respostas/temas.py` (`detectar(texto) -> list[str]`).

## 3. Respostas (`respostas.ver` para ler)
`Resposta` (lista) = formato da etapa 2 +
`{data (= data_resposta), respondida_em|null, origem, temas: [chave], temas_manuais, o_que_faltou|null, o_que_combinamos|null,
analisada_em|null, analisada_por: {id,nome}|null, registrada_por: {id,nome}|null, arquivada,
contato: {id, nome, email, perfil: {id,nome}|null}|null, empresa: {id, nome, grupo: {id,nome}|null}|null,
acao: {id, situacao, prazo, prazo_selo}|null}` (a ação automática da resposta; senão a mais recente ligada a ela).

- `GET /respostas?busca=&categoria=&tipo_nota=nps|csat&grupo_id=&empresa_id=&contato_id=&tema=&perfil_id=&canal=&origem=&formulario_id=&de=&ate=&data_por=resposta|entrada&arquivadas=false|true|todas&pagina=&por_pagina=`
  → paginado + `metricas: {nps: {valor, faixa, promotores, neutros, detratores, total}|null, csat: {percentual, media, total}|null, total}`
  calculadas sobre o mesmo filtro (todas as páginas). Ordem: `data_resposta` desc, `id` desc.
  `busca`: nome/e-mail do contato, empresa, comentário, referência. `categoria`: grupo da nota. `grupo_id`: grupo de empresas.
  `data_por=entrada` filtra por `criada_em`; padrão `resposta` (`data_resposta`). `arquivadas` padrão `false`.
- `GET /respostas/{id}` → `Resposta` + `{respostas, perguntas: [{id, titulo, tipo, resposta (texto pronto, ex.: "Sim", "31/12/2025")}],
  convite: {evento, referencia, assunto}|null, acoes: [Acao resumida: {id, titulo, situacao, prazo, prazo_selo}]}`.
- `POST /respostas` (`respostas.editar`) — registrar à mão: `{contato_id, nota (0–10), canal: "manual"|"whatsapp"|"telefone"|"email"|"reuniao" (padrão manual),
  comentario? (≤ 4000), data? (AAAA-MM-DD, padrão hoje; não pode ser futura nem antes de 2000)}` → 201 `Resposta`.
  Usa o formulário padrão de NPS (`respostas = {id da pergunta principal: nota}`), `origem manual`, `registrada_por`,
  `respondida_em` = data às 12:00 (só quando `data` veio). Passa pelo ponto único `ao_registrar_resposta`.
  422 contato inexistente ou nota fora de 0–10.
- `PATCH /respostas/{id}` (`respostas.editar`) — analisar: `{nota?, comentario?, o_que_faltou?, o_que_combinamos?, temas?: [chave]}`.
  Nota dentro da faixa do tipo (NPS 0–10, CSAT 1–5; 422 se a resposta não tem nota); muda a nota → recalcula o grupo e, se for a
  resposta mais recente do contato, `ultima_nota`. `temas` informado → `temas_manuais = true`. Grava `analisada_em/por`.
  Auditoria `resposta_editada` quando muda nota ou comentário (`{antes: {nota}, depois: {nota}, comentario_alterado}`).
  A ação já criada não muda.
- `POST /respostas/{id}/arquivar` e `/restaurar` (`respostas.editar`) → `Resposta`. Arquivada sai de todos os indicadores.
- `DELETE /respostas/{id}` (perfil admin) → 204. Apaga as ações ligadas e a resposta; recalcula `ultima_nota` do contato.
  Auditoria `resposta_excluida` (`{resposta_id, contato, nota, acoes_apagadas}`), gravidade atencao.
- `GET /respostas.csv` (`painel.exportar`), mesmos filtros da lista → CSV `;`, UTF-8 com BOM, células protegidas contra fórmula:
  `Data;Contato;E-mail;Empresa;Grupo de empresas;Perfil;Tipo;Nota;Categoria;Temas;Comentário;O que faltou;O que combinamos;Canal;Origem;Referência;Pedido;Nota fiscal;Rota;Motorista;Filial;Transportadora;Arquivada`.
- Nas telas da etapa 2 (resultados e respostas do formulário, histórico do contato) o período e a ordem passam a usar `data_resposta`.

## 4. Importação de respostas antigas (`importacao.usar`)
Mesmo fluxo da etapa 2, com `tipo`:
- `GET /importacao/modelo?tipo=respostas` → CSV `email;empresa;data;nota;comentario` (com uma linha de exemplo).
- `POST /importacao/analisar` multipart `arquivo` + campo `tipo` (`contatos` padrão | `respostas`) → mesmo formato; para respostas,
  `campos` = email (obrigatório), data (obrigatório), nota (obrigatório), empresa, comentario. Equivalentes: e-mail/email_cliente → email;
  data_resposta/dt → data; nps/nota_nps/score → nota; motivo/comentário/observação/obs → comentario; razão social/cliente → empresa.
- `POST /importacao/{id}/conferir` e `/importar`: o `tipo` vem da análise; para respostas o corpo usa só `mapeamento`,
  `atualizar_existentes` e (no importar) `ignorar_com_problema`; `chave` e `grupo_id` são ignorados.
- Regras por linha: o e-mail precisa ser de um contato já cadastrado ("Contato não encontrado: cadastre ou importe os contatos
  antes."); data dd/mm/aaaa ou aaaa-mm-dd, não futura; nota inteira 0–10 ("9,0" e "9.0" valem 9; "8,7" → "A nota precisa ser um
  número inteiro de 0 a 10."); comentário ≤ 4000; mesmo contato + mesma data repetidos no arquivo → "Linha repetida (mesmo contato e
  data)."; empresa diferente da empresa do contato → **aviso** (vale a do contato).
- Já existe resposta **importada** do mesmo contato na mesma data → atualiza (nota, comentário) se `atualizar_existentes`, senão mantém
  (conta em `ignorados`). Resultado `{novos, atualizados, ignorados, problemas}`.
- Grava tudo ou nada: `origem` e `canal` `importacao`, formulário padrão de NPS, `tipo_nota nps`, grupo pela nota, temas,
  `respondida_em` = data às 12:00. Atualiza `ultima_nota` do contato se for a resposta mais recente dele. Até 20.000 linhas
  (inserção em lote). Auditoria `importacao_respostas` (`{novos, atualizados}`).

## 5. Planos de ação
`Acao` = `{id, titulo, descricao, resolucao|null, situacao, prioridade, prazo|null, prazo_selo: "vencido"|"hoje"|"amanha"|null,
empresa: {id,nome}|null, contato: {id,nome}|null, responsavel: {id,nome,email,foto_url}|null,
resposta: {id, nota, tipo_nota, grupo, comentario, data}|null, origem, grupo|null, tipo_nota|null, nota|null,
criada_em, atualizada_em, iniciada_em|null, concluida_em|null, criado_por: {id,nome}|null, concluida_por: {id,nome}|null}`.
`prazo_selo`: só para ação não concluída com prazo; `vencido` se prazo < hoje, `hoje`, `amanha`; senão null.

Filtros comuns: `busca` (título, empresa, contato), `categoria` (grupo da nota da ação), `tipo_nota`, `responsavel_id`
(0 = sem responsável), `empresa_id`, `grupo_id` (grupo de empresas), `de`/`ate` (criada_em), `so_vencidas=true`.
- `GET /acoes/quadro?<filtros>` (`acoes.ver`) → `{colunas: {a_fazer: [Acao], em_andamento: [Acao], concluida: [Acao]},
  totais: {a_fazer, em_andamento, concluida, vencidas}}`. Abertas ordenadas por vencidas primeiro, prazo (vazio por último),
  prioridade (alta → baixa), criada_em; até 300 por coluna. `concluida`: as 15 concluídas mais recentes.
- `GET /acoes/panorama?<filtros>` (`acoes.ver`) → o resumo do topo (prazos, responsáveis, concluídas); desde
  08/10/2026, em `docs/api-acoes-panorama.md`.
- `GET /acoes?<filtros>&situacao=&pagina=` (`acoes.ver`) → paginado (para "ver todas as concluídas"; concluídas por concluida_em desc).
- `GET /acoes/{id}` (`acoes.ver`) → `Acao` (link direto).
- `POST /acoes` (`acoes.tratar`) `{titulo, descricao?, empresa_id?, contato_id?, resposta_id?, responsavel_id?, prioridade? (padrão media), prazo?}`
  → 201. Sem empresa e com resposta → empresa da resposta; com empresa e sem responsável → responsável da empresa. `origem manual`.
- `PATCH /acoes/{id}` (`acoes.tratar`) `{titulo?, descricao?, resolucao?, responsavel_id?, prioridade?, prazo?, situacao?, empresa_id?}`
  (null limpa os opcionais). Mover = mudar `situacao`. Ir para `concluida` exige, depois de aplicar o corpo, responsável e
  `resolucao` não vazia → 422 `{campos: {responsavel_id: "Escolha o responsável antes de concluir.", resolucao: "Conte o que foi feito para concluir."}}`.
  Concluir grava `concluida_em/por`; sair de concluída limpa os dois; `em_andamento` grava `iniciada_em` se vazio.
- `DELETE /acoes/{id}` (`acoes.excluir`) → 204; auditoria `acao_excluida` (`{acao_id, titulo}`).
- `GET /acoes/configuracao` (`acoes.ver`) → `{prazo_detrator, prazo_neutro, prazo_promotor, acao_promotor}` ·
  `PUT /acoes/configuracao` (`configuracoes.gerenciar`, corpo parcial) → mesmo formato; 422 fora de 1–90; auditoria `config_acoes`.

**Ação automática** (gancho em `ao_registrar_resposta`, origens `pesquisa` e `manual`; uma por resposta):
| Resposta | Prioridade | Prazo | Título |
|---|---|---|---|
| NPS detrator (0–6) | alta | hoje + prazo_detrator | `[Detrator NPS {nota}] Ação requerida: {alvo}` |
| NPS neutro (7–8) | media | hoje + prazo_neutro | `[Neutro NPS {nota}] Ação requerida: {alvo}` |
| NPS promotor (9–10), só com `acao_promotor` | baixa | hoje + prazo_promotor | `[Promotor NPS {nota}] Ação requerida: {alvo}` |
| CSAT insatisfeito (1–2) | alta | hoje + prazo_detrator | `[CSAT {nota}] Cliente insatisfeito: {assunto}` |
`alvo` = nome da empresa, senão nome do contato, senão "cliente sem cadastro". `assunto` = `contexto.assunto`, senão assunto do convite,
senão `alvo`. Responsável = responsável da empresa. Descrição: linhas "Comentário do cliente: …", "Contato: nome (e-mail/telefone)",
e o contexto que houver ("Pedido: …", "Rota: …", "Motorista: …"). Hoje = data em America/Sao_Paulo.
**Alerta ao responsável** (ação alta com responsável com e-mail): assunto `Alerta de risco: {alvo} deu nota {nota}`, texto com nota,
categoria, comentário, contato e botão "Tratar no Toqqi" → `{FRONTEND_URL}/planos-de-acao/{id}`. Coletado durante a transação
(`coletar_alertas()`, como `coletar_envios()`) e enviado em segundo plano depois do commit em todas as rotas que gravam resposta
(páginas públicas e `POST /respostas`); sem coletor, não envia.

## 6. Painel (`painel.ver`)
`GET /painel?de=&ate=&grupo_id=&so_ativos=true` — regras comuns: só respostas não arquivadas; data = `data_resposta`; período
inclusive em dias de São Paulo; sem `de`/`ate` = todo o histórico (a tela usa os últimos 90 dias por padrão); `grupo_id` = grupo de
empresas; `so_ativos` tira empresas inativas (respostas sem empresa contam). Responde em menos de 1 s com 5.000 contatos e 50.000
respostas (agregações no SQL).
```
{ periodo: {de|null, ate|null, anterior: {de, ate}|null},
  nps: {valor|null, faixa|null, promotores, neutros, detratores, total, pct: {promotores, neutros, detratores} (1 casa),
        decisores: {valor|null, total}},
  variacao: {valor, anterior}|null,
  csat: {percentual|null, media|null (2 casas), total, satisfeitos},
  taxa_resposta: {percentual|null, responderam, convidados, amostra_pequena},
  movimentacao: {resgatados, deixaram_de_ser_promotores, itens: [{tipo: "resgatado"|"deixou_de_ser_promotor", contato: {id,nome},
                 empresa: {id,nome}|null, nota_anterior, nota_atual, data_anterior, data_atual}] (até 20, mais recentes)},
  atencao: {acoes_abertas, acoes_vencidas, tudo_em_dia,
            empresas: [{empresa: {id,nome}, nps|null, acoes_abertas, acoes_vencidas, desde (data da ação aberta mais antiga),
                        responsavel: {id,nome}|null, ultimo_comentario_detrator|null, acao_id}] (até 5),
            receita_em_risco: {valor, empresas, sem_valor}},
  temas: [{chave, rotulo, mencoes, nota_media|null (1 casa)}] (até 5),
  comentarios: [{resposta_id, data, nota, tipo_nota, grupo, comentario, contato: {id,nome}|null, empresa: {id,nome}|null}] (6),
  evolucao: [{mes: "AAAA-MM", nps, total}],
  empresas: {menor: [{empresa: {id,nome}, nps, respostas}], maior: [...]},
  palavras: [{palavra, total}] (até 12),
  primeiros_passos: {contatos, envios_ligados, primeiro_envio, primeira_resposta} }
```
- **nps**: respostas `tipo_nota = nps`. `faixa`: ≥ 75 `excelente`, ≥ 50 `muito_bom`, ≥ 0 `pode_melhorar`, < 0 `critico`
  (cores: verde ≥ 50, âmbar 0–49, vermelho < 0). `decisores`: só contatos com perfil "Decisor" (sem diferenciar maiúsculas).
- **variacao**: só com `de` e `ate`; período anterior de mesmo tamanho, imediatamente antes; null se um dos dois não tem NPS.
- **csat**: respostas `tipo_nota = csat`; `percentual` = % de notas 4–5 (inteiro, meio para cima), `media` com 2 casas.
- **taxa_resposta**: `convidados` = contatos ativos (e de empresa ativa, com `so_ativos`) com convite criado no período que **saiu**
  (envio de convite `enviado`, ou convite de WhatsApp `aberto_no_whatsapp`); `responderam` = desses, os que têm resposta no período;
  `percentual` inteiro; `amostra_pequena` = percentual < 20. Sem convidados: percentual null.
- **movimentacao**: por contato, a última resposta NPS (no período, se houver período) contra a anterior a ela (qualquer data).
  Resgatado: anterior 0–6 e última 9–10. Deixou de ser promotor: anterior 9–10 e última ≤ 8.
- **atencao**: ações abertas (`a_fazer`, `em_andamento`) e vencidas (prazo < hoje), com os filtros de empresa e **sem** o período.
  `empresas`: as que têm ação aberta, vencidas primeiro e depois a mais antiga; `nps` da empresa no período; `acao_id` = a ação
  mais urgente (para o botão Tratar). `tudo_em_dia` = nenhuma ação aberta. `receita_em_risco`: soma do `valor_mensal` das empresas
  com ao menos um detrator no período; `sem_valor` = quantas delas não têm valor cadastrado.
- **temas**: só respostas NPS; menções por tema e nota média das respostas com o tema; os 5 mais citados (empate: ordem da tabela).
- **comentarios**: as 6 mais recentes (NPS e CSAT) com comentário.
- **evolucao**: NPS por mês de `data_resposta`. Sem período: os 6 meses mais recentes com dados. Com período: os meses do período com
  dados, até os 24 mais recentes. Ordem cronológica.
- **empresas**: empresas com 3+ respostas NPS no período, ordenadas por NPS; `menor` = as piores (até 6), `maior` = as melhores
  (até 6), sem repetir empresa entre as duas listas.
- **palavras**: dos comentários (até 5.000 mais recentes do filtro), palavras com 3+ letras fora de uma lista de palavras comuns
  do português; conta 1 por resposta; mostra a forma mais frequente (com acento).
- **primeiros_passos**: há contato; `envios_ativos` ligado; algum convite saiu; alguma resposta.
- `GET /painel/exportar.csv?de=&ate=&grupo_id=&so_ativos=` (`painel.exportar`) → mesmo CSV de `/respostas.csv` com os filtros do painel.

## 7. Telas (web)
- **Início = Painel** para quem tem `painel.ver` (senão, a tela de boas-vindas atual). Filtros: período (7, 30, 90 dias, 12 meses,
  tudo, personalizado; padrão 90 dias), grupo de empresas, "só ativos". Cartões: NPS (número grande, faixa, barra empilhada dos três
  grupos, total, NPS dos decisores), Variação, CSAT, Taxa de resposta (aviso "amostra pequena"), Movimentação (resgatados e quem
  deixou de ser promotor, com lista "o que mudou"). "Precisa de atenção" (abertas, vencidas, até 5 empresas com botão Tratar, receita
  em risco; "Tudo em dia" quando não há pendência). Blocos: assuntos mais citados (com nota média), comentários recentes, evolução
  mensal do NPS (gráfico), empresas de menor e maior NPS, 12 palavras mais citadas, "Primeiros passos" (4 passos, pode ocultar —
  guardado no navegador), ajuda das métricas, Exportar CSV (`painel.exportar`).
- **Respostas** (`/respostas`): métricas no topo (NPS e contagem por categoria), filtros (busca, período com "data da resposta / de
  entrada", categoria, tipo, grupo de empresas, empresa, tema, perfil, arquivadas), lista (tabela no computador, cartões no
  celular) com data, contato e empresa, nota colorida pela categoria, comentário, temas, canal e situação da ação. Ações: Analisar
  (painel lateral com todas as perguntas e respostas, contexto do pedido, edição de nota, comentário, "o que faltou", "o que
  combinamos" e temas; criar ou abrir a ação), Arquivar/Restaurar, Excluir (só admin, com confirmação que diz quantas ações somem),
  Registrar resposta (contato, nota 0–10, canal, data, comentário), Exportar CSV, Importar respostas antigas. Filtros na URL.
- **Planos de ação** (`/planos-de-acao` e `/planos-de-acao/:id`): quadro A fazer → Em andamento → Concluído; arrastar entre colunas
  ou menu "Mover para…"; no celular, uma coluna por vez (abas). Cartão: título, empresa, responsável, prioridade, selo de prazo,
  nota. Painel lateral para ver e editar tudo (título, descrição, resolução, responsável, prioridade, prazo, situação, empresa,
  resposta de origem); concluir pede responsável e o que foi feito (o campo aparece na hora). Filtros (categoria, tipo, responsável,
  empresa, grupo de empresas, período, só vencidas). "Nova ação". Concluído mostra as 15 mais recentes e "Ver todas". Excluir só com
  `acoes.excluir`.
- **Importar** (`/contatos/importar?tipo=respostas`): a tela pergunta "Contatos" ou "Respostas antigas" e adapta campos e textos.
- **Configurações › Planos de ação** (`/configuracoes/acoes`): prazos por grupo e "Criar ação também para promotores".
- **Contato**: atalho "Ver respostas" (`/respostas?contato_id=`) e "Registrar resposta".
- Menu: Respostas e Planos de ação deixam de ser "em breve"; Relatórios continua (4b).

## 8. Agendador (Cron Job do Render)
- `render.yaml` ganha o serviço `toqqi-tarefas` (`type: cron`, `*/15 * * * *` em UTC, `python -m toqqi.tarefas`). Conecta direto
  no banco e não acorda a API. As variáveis vêm da API por `fromService` (`APP_DB_PASSWORD`, `JWT_SECRET`, `SEGREDOS_KEY`,
  `FRONTEND_URL`, `API_PUBLIC_URL`, `EMAIL_PROVIDER`, `AMBIENTE`): os dois usam os mesmos segredos (o `JWT_SECRET` monta os links
  dos lembretes). Ao configurar o ZeptoMail, acrescentar `EMAIL_FROM` e `ZEPTOMAIL_TOKEN` do mesmo jeito.
- A rotina do GitHub Actions (`tarefas.yml`) saiu. `POST /interno/tarefas` (com `TAREFAS_TOKEN`) continua para rodar à mão.
- Custo: cobrança por segundo de execução, com mínimo de US$ 1 por mês.

## 9. Ajustes feitos na construção (revisão e teste integrado)
Detalhes de cada um na seção "Etapa 4a" de `api/README.md` e `web/README.md`.
- **Texto do cliente** (`respostas.comentario_cliente`, interno): só o que o cliente escreveu nas perguntas de comentário (nas
  respostas manuais e importadas, o comentário). O painel usa só ele em comentários recentes, último comentário de detrator e
  palavras, para não mostrar "6" (uma escala) ou "Seu nome: …" como comentário. A lista e os CSV continuam com `comentario`.
- **Temas** vêm do texto do cliente, das opções marcadas e de "o que faltou" (não dos títulos das perguntas).
- `GET /respostas` e `/respostas.csv` aceitam **`so_ativos`**, para os atalhos do painel abrirem exatamente o mesmo conjunto
  (com `tipo_nota=nps` nos blocos de NPS). A tela Respostas ganhou o filtro "Só empresas ativas".
- Datas de filtro fora de **2000–2100** → 422 (antes, `9999-12-31` dava erro 500). Importação aceita datas de 2000 até hoje.
- `POST /respostas` com `data` = hoje grava a hora real (`respondida_em` vazio); a tela só manda `data` quando é outro dia.
- Importação: atualizar só troca comentário e temas quando a célula tem texto; respeita `temas_manuais`; uma importação por vez
  em cada conta.
- Ação automática e alerta citam o contato só pelo nome; o alerta só sai com provedor de e-mail configurado (o `console` não conta
  em produção, para dados do cliente não irem para o log).
- Painel: `temas` só traz temas citados; `empresas` divide as empresas entre as duas listas (metade, arredondada para cima, em
  `menor`; até 6 cada); `desde`, `data_anterior` e `data_atual` são data e hora ISO.
- 409 `sem_formulario_nps` ao registrar à mão ou importar sem formulário padrão de NPS.
- A API expõe `Content-Disposition` no CORS, para os CSV baixarem com o nome certo.
