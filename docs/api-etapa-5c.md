# Toqqi · Etapa 5c (Crescimento: indicações e oportunidades)

Mesmas convenções das etapas anteriores: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, `requer(...)`,
listas paginadas `{itens,total,pagina,por_pagina}`, datas ISO 8601, dias de regra em America/Sao_Paulo (`toqqi.core.relogio`),
valores em reais como decimal, NPS com **meio para cima** (`respostas/indicadores.py`), RLS por conta em toda tabela nova.

## 0. Decisões desta etapa
- Proposta (Marcelo, 02/10): o Toqqi retém clientes e ganha uma camada de atração: **"retenha quem está insatisfeito e cresça
  com quem está feliz"**. As empresas que usam o Toqqi conquistam clientes por um misto de canais (representantes, indicação,
  marketing digital), então o módulo escolhe **quem** abordar e entrega ao canal certo; não compete com CRM nem e-mail marketing.
- Módulo **Crescimento** com duas partes: **Indicações** (promotores indicam outras empresas) e **Oportunidades** (clientes
  felizes para receber uma oferta).
- Respostas do Marcelo: a **recompensa só é registrada** (texto livre no convite; a empresa paga do jeito dela); a **oferta sai
  1:1 pelo WhatsApp do representante** (link com o texto pronto, como o WhatsApp por link das pesquisas) e a lista **sai em CSV**;
  envio em massa pelo Toqqi fica para depois (pediria outro provedor de e-mail, consentimento de marketing e descadastro próprio).
- Regra de ouro: oportunidade nunca inclui empresa com detrator recente ou plano de ação aberto, nem contato descadastrado.

## 1. Banco (migração `0012_crescimento`, depois das `0010_aceites` e `0011_revogacao_aceite` do aceite LGPD)
- `config_crescimento` (uma linha por conta, como `config_acoes`): `indicacoes_ativas bool default false`, `titulo_convite`,
  `texto_convite`, `recompensa text null`, `texto_oferta`, `atualizado_em`. Sem linha = valores padrão (§5).
- `indicacoes`: `id`, `conta_id`, `origem` ('pesquisa' | 'manual'), `convite_id null`, `resposta_id null`,
  `indicador_contato_id null`, `indicador_empresa_id null`, `pode_identificar bool`, `nome`, `empresa null`, `telefone null`,
  `email citext null`, `observacao null` (até 500), `situacao` ('nova' | 'em_contato' | 'cliente' | 'nao_avancou', padrão
  'nova'), `responsavel_id null` (FK `responsaveis`, `on delete set null`), `valor_mensal numeric(12,2) null`, `motivo null`,
  `criada_em`, `atualizada_em`, `criada_por null` e `atualizada_por null` (usuários). CHECK: telefone ou e-mail presente;
  `valor_mensal` só com 'cliente' (>= 0). FKs de contato/empresa/resposta com `on delete set null` (apagar o contato não apaga
  a indicação). Índices `(conta_id, situacao, criada_em)` e `(conta_id, criada_em)`.
- `ofertas`: `id`, `conta_id`, `empresa_id` (FK, `on delete cascade`), `contato_id null` (`on delete set null`), `lista`
  ('pode_crescer' | 'promotores'), `canal` ('whatsapp'), `texto`, `usuario_id null`, `criada_em`, `resultado null` ('aceitou' |
  'recusou' | 'sem_resposta'), `valor numeric(12,2) null` (só com 'aceitou'), `resultado_em null`. Índice
  `(conta_id, empresa_id, criada_em)`.
- Permissões novas no catálogo (grupo "Crescimento"): `crescimento.ver` ("Ver indicações e oportunidades") e
  `crescimento.tratar` ("Tratar indicações e registrar ofertas"). Padrão: gestor as duas, consulta só `ver`; a migração semeia
  as linhas de `perfil_permissoes` nas contas que já existem (em modo sistema, por causa do RLS forçado).
- Todas as tabelas novas com RLS forçado e a política de sempre. Downgrade desfaz tudo.

## 2. Convite de indicação na pesquisa (público)
- `POST /publico/convites/{token}/responder` passa a devolver também `indicacao: null | {titulo, texto, recompensa}` (textos
  com as variáveis de §5 trocadas) quando: indicações ligadas na conta, conta liberada (`assinatura.regras.liberada`), e a nota
  principal da resposta gravada é de promotor (NPS 9–10) ou CSAT 5. Só no convite (o link público sem contato não tem a quem
  atribuir).
- `POST /publico/convites/{token}/indicacoes` `{nome, empresa, telefone, email, observacao, pode_identificar, confirmo}` → 201
  `{mensagem: "Obrigado pela indicação!"}`. Regras: o convite já foi respondido com nota que dá direito (a mesma regra acima) e
  as indicações seguem ligadas; `nome` 2–120; `empresa` até 120; `telefone` com a validação brasileira de sempre (celular ou
  fixo) e/ou `email` válido — pelo menos um; `observacao` até 500; `confirmo` precisa ser `true` ("Confirmo que essa pessoa
  aceita receber um contato de {empresa}."). No máximo 3 indicações por convite (a 4ª → 409 `limite_indicacoes`, "Você já fez
  3 indicações. Obrigado!"). Mesmo telefone ou e-mail de uma indicação ainda aberta (nova ou em contato) na conta: não cria
  outra e responde 201 igual (não revela que já existe). Limite por IP como o de responder convite. Texto sem caracteres de
  controle; nada disso vai para o log.
- Ao criar: `responsavel_id` = responsável da empresa de quem indicou; aviso por e-mail ao responsável (se tiver e-mail), senão
  aos administradores da conta com e-mail confirmado ("Nova indicação de {empresa do indicador}: {nome}, {empresa}") com o link
  para a tela; webhook `indicacao.criada`. Tudo depois do commit (como os outros coletores).

## 3. Indicações (`crescimento.ver`; alterar com `crescimento.tratar`)
- `GET /crescimento/indicacoes?situacao=&responsavel_id=&de=&ate=&busca=&pagina=&por_pagina=` → página com
  `itens: [{id, origem, nome, empresa, telefone, email, observacao, indicador: {contato: ref|null, empresa: ref|null},
  pode_identificar, responsavel: ref|null, situacao, valor_mensal, motivo, criada_em, atualizada_em}]` (mais novas primeiro;
  `busca` no nome, empresa, telefone e e-mail, sem acento) e `resumo: {novas, em_contato, clientes, nao_avancou,
  receita_mensal}` (com os mesmos filtros de período e responsável).
- `POST /crescimento/indicacoes` (manual, "veio por telefone") `{nome, empresa, telefone, email, observacao,
  indicador_contato_id, indicador_empresa_id, responsavel_id}` → 201 (sem `confirmo`; quem registra responde por isso).
- `PATCH /crescimento/indicacoes/{id}` `{situacao, valor_mensal, motivo, responsavel_id}`: 'cliente' pede `valor_mensal`
  (>= 0; 422 sem ele); 'nao_avancou' aceita `motivo` (até 300); outras situações limpam `valor_mensal`. Webhook
  `indicacao.atualizada` quando a situação muda.
- `DELETE /crescimento/indicacoes/{id}` → 204 (pedido da pessoa indicada, LGPD); auditoria `indicacao_excluida` sem dados
  pessoais.
- `GET /crescimento/indicacoes.csv` (com `painel.exportar`) com os filtros da lista.
- Auditoria: `indicacao_registrada` (manual), `indicacao_atualizada` (situação); sem dados pessoais no detalhe.

## 4. Oportunidades (`crescimento.ver`; registrar oferta com `crescimento.tratar`)
- `GET /crescimento/oportunidades?lista=pode_crescer|promotores&grupo_id=&responsavel_id=&pagina=` → página de empresas:
  `itens: [{empresa: {id, nome, valor_mensal}, grupo: ref|null, responsavel: ref|null, nps: {valor, total}, contato: {id,
  nome, telefone, email}|null, ultima_resposta: {data, nota, tipo_nota}|null, ultima_oferta: {id, criada_em, resultado}|null}]`.
  - `pode_crescer`: o quadrante "Pode crescer" da matriz NPS × valor de Relatórios › Empresas (NPS >= 0 e valor abaixo da
    mediana) nos **últimos 90 dias**, com as mesmas regras e funções do relatório; ordem: maior NPS, depois menor valor.
  - `promotores`: empresas com resposta de promotor (NPS 9–10) nos **últimos 30 dias**; ordem: promotor mais recente primeiro.
  - Fora das duas: empresa inativa; com detrator (NPS 0–6) nos últimos 90 dias; com plano de ação aberto. `contato` = quem deu a
    resposta mais recente da empresa no período, ativo e não descadastrado, com telefone ou e-mail (senão `null`).
- `POST /crescimento/ofertas` `{empresa_id, contato_id, lista, texto}` → 201 oferta (a tela registra ao abrir o WhatsApp;
  `texto` até 2.000). `PATCH /crescimento/ofertas/{id}` `{resultado, valor}` ('aceitou' aceita `valor` >= 0).
- `GET /crescimento/oportunidades.csv?lista=` (com `painel.exportar`): empresa, grupo, responsável, valor, NPS, respostas,
  contato, telefone, e-mail, última resposta, última oferta.
- `GET /crescimento/resumo?de=&ate=` → `{indicacoes: {recebidas, clientes, taxa, receita_mensal}, ofertas: {feitas, aceitas,
  taxa, receita}}` (padrão: últimos 90 dias).

## 5. Configurações › Crescimento (`configuracoes.gerenciar`)
- `GET /crescimento/configuracao` (também com `crescimento.ver`, para a tela) e `PUT` (só `configuracoes.gerenciar`):
  `{indicacoes_ativas, titulo_convite (até 120), texto_convite (até 500), recompensa (até 300, opcional), texto_oferta (até
  1.000)}`. Padrões: título "Que bom que você gostou!"; convite "Conhece outra empresa que ganharia com a {empresa}? Indique e
  a gente entra em contato com cuidado."; recompensa vazia (exemplo no campo: "Se a indicação virar cliente, você ganha 10% no
  próximo pedido."); oferta "Olá, {nome}! Aqui é {representante}, da {empresa}. Obrigado pela ótima avaliação! Preparei uma
  condição especial para a {empresa_cliente}. Posso te contar?".
- Variáveis: convite e recompensa com `{empresa}` (nome da conta) e `{nome}` (primeiro nome de quem respondeu); oferta com
  `{nome}`, `{empresa}`, `{empresa_cliente}` e `{representante}` (primeiro nome de quem está logado). Auditoria
  `config_crescimento`.

## 6. Telas (web)
- **Menu**: "Crescimento" (com `crescimento.ver`), depois de "Planos de ação"; rota `/crescimento/:aba` com abas
  **Indicações** (padrão) e **Oportunidades**; no topo, o resumo dos últimos 90 dias (indicações recebidas, viraram cliente,
  receita mensal vinda delas; ofertas feitas, aceitas). Desde 08/10/2026, o panorama de `docs/api-crescimento-panorama.md`.
- **Indicações**: filtros (situação, responsável, período, busca), lista (tabela a partir de 640 px, cartões no celular) com
  nome, empresa, contato (telefone/e-mail), quem indicou ("Mercado Bom Preço · Ana" ou "Não quis se identificar"), responsável,
  situação (selo) e data; abrir uma linha → painel lateral com os dados, a observação, botões de WhatsApp/e-mail para falar
  com a pessoa, troca de situação (com valor mensal ao virar cliente e motivo ao não avançar), troca de responsável e
  "Excluir (pedido da pessoa)"; "Registrar indicação" (manual); "Exportar CSV" (com `painel.exportar`). Vazio: explica como
  ligar o convite (link para Configurações › Crescimento para quem pode).
- **Oportunidades**: alternar "Pode crescer" e "Promotores recentes" (com uma frase do critério de cada uma e da regra de ouro),
  filtros de grupo e responsável, lista de empresas com NPS, valor, contato e última oferta; **"Oferecer pelo WhatsApp"** abre
  `https://wa.me/55…?text=…` com o texto da oferta já preenchido (sem telefone: só e-mail → `mailto:`) e registra a oferta;
  depois, "Registrar resultado" (aceitou com valor, recusou, sem resposta); "Exportar CSV" (com `painel.exportar`).
- **Configurações › Crescimento** (aba nova): ligar o convite de indicação, título, texto, recompensa e texto da oferta, com
  "Inserir" variáveis (o mesmo componente de Configurações › Envios) e prévia (o cartão do convite como na pesquisa e o balão
  do WhatsApp da oferta).
- **Pesquisa (página pública)**: na tela final, se `indicacao` vier, um cartão com o título, o texto e a recompensa, e o
  formulário (nome, empresa, WhatsApp ou telefone, e-mail, observação, "Pode dizer que fui eu que indiquei" marcado, e a
  confirmação obrigatória); depois de enviar, "Obrigado pela indicação!" e "Indicar outra pessoa" (até 3). Na pré-visualização
  do editor, o cartão aparece como exemplo, com o envio desligado.
- **Integrações**: os eventos `indicacao.criada` e `indicacao.atualizada` aparecem na escolha de eventos do webhook.
- **Ajuda e assistente**: tópico novo "Crescimento" na Ajuda (antes de "Integrações") e atalho `crescimento` (Crescimento,
  /crescimento/indicacoes, `crescimento.ver`) na lista de atalhos da 5b (API e web).
- Tudo no celular, claro e escuro, sem `v-html` com texto de cliente ou de indicação.

## 7. Testes (critério de pronto)
- API: migração (sobe e desce; permissões semeadas nas contas existentes); convite de indicação (aparece só com as regras de
  §2; NPS 8 e CSAT 4 não; conta pausada não; link público não); indicação pública (validações, limite de 3, duplicada sem
  revelar, roteamento ao responsável, e-mail, webhook, RLS); lista, filtros, resumo, PATCH com regras de valor e motivo, DELETE,
  CSV; oportunidades (as duas listas batem com o relatório de empresas e com as respostas; exclusões de detrator, ação aberta,
  inativa, descadastrado; contato sugerido); ofertas e resultados; configuração (padrões, variáveis, permissões); permissões
  por perfil em todas as rotas.
- Web: Crescimento (abas, filtros, painel da indicação, mudanças de situação, oferta pelo WhatsApp com o link certo e o
  registro), Configurações › Crescimento (prévia, variáveis), cartão de indicação na pesquisa (envio, limite, erros, "Indicar
  outra pessoa"), menu e permissões, Integrações (eventos novos).
- Integrado (pilha local): ligar as indicações; responder um convite com 10 → cartão → indicar → aparece em Crescimento com o
  responsável certo e o e-mail no log; Oportunidades bate com a matriz de Relatórios; oferta pelo WhatsApp registra; telas em
  1280 e 390 px, claro e escuro, sem erro no console.

## 8. Ajustes feitos na construção (revisão e teste integrado)
- **Indicação pública**: a repetida (mesmo telefone ou e-mail ainda aberto) também gasta uma das 3 vagas do convite
  (`convites.indicacoes_feitas`, sob trava), para ninguém descobrir quem já está no funil; 409 `indicacao_indisponivel` quando
  não há direito, as indicações estão desligadas, a conta está pausada, a resposta foi arquivada ou o formulário desativado;
  404 `link_invalido` para token que não existe; 413 `pedido_grande_demais` acima de 20 KB; textos sem caracteres de controle
  nem controles bidirecionais (que disfarçam nomes no e-mail e no CSV). A indicação registrada à mão dispara o webhook, mas não o
  e-mail. Sem e-mail do responsável, o aviso vai aos administradores com e-mail confirmado.
- **Exclusão (LGPD)**: apagar uma indicação apaga também as entregas de webhook ainda pendentes dela; as já terminadas ficam no
  histórico de Integrações só com o envelope (`dados: {id, excluido: true}`).
- **Permissões**: alterar (indicação, oferta, resultado) exige `crescimento.ver` **e** `crescimento.tratar`.
- **Oportunidades**: grupo e responsável só filtram a lista (o quadrante é o da carteira toda, 90 dias, empresas ativas);
  `responsavel_id=0` = "sem responsável" (também em Indicações); `nps`, `ultima_resposta` e `contato` usam o período de cada
  lista. `ultima_oferta` traz `valor`. `POST /crescimento/ofertas` aceita `canal` ('whatsapp' | 'email', padrão 'whatsapp') e
  recusa com 422 contato de outra empresa, inativo ou descadastrado e empresa que saiu das oportunidades pela regra de ouro.
  No PATCH, com 'aceitou', `valor` ausente ou nulo mantém o valor atual; outro resultado limpa o valor.
- **Formatos**: telefones saem só com dígitos e já com 55 (o link é `wa.me/<telefone>`); a oferta devolve `empresa`, `contato`
  e `usuario` como ref; `resumo` traz também `periodo`; no webhook `indicacao.atualizada` vem `situacao_anterior`.
- **API inteira**: ids fora do bigint e textos com NUL (e os SQLSTATE 22003, 22P02, 22021, 22001) viram 422 "Confira os dados
  enviados." em vez de 500 (era um pendente antigo).
- **Telas**: Configurações › Crescimento abre também para quem só tem `crescimento.ver` (só leitura); a oferta por e-mail abre o
  `mailto:` com assunto e é registrada com `canal: 'email'`; clique duplo não abre dois WhatsApp nem registra duas ofertas;
  sem a configuração carregada, "Oferecer" fica desligado (com "Tentar de novo" em erro); "Mudar resultado" abre com o valor
  que já estava; "1.250" em campos de valor agora é mil duzentos e cinquenta (antes virava 1,25, em todas as telas); e-mails em
  tabelas quebram depois do "@" e dos pontos (componente `TextoEmail`).
- **Teste integrado** (pilha local): convite com nota 10 → cartão → 3 indicações → 4ª recusada; responsável certo; e-mail
  "Nova indicação" aos administradores (o responsável não tinha e-mail); "Pode crescer" igual ao quadrante do relatório tirando
  as 5 empresas da regra de ouro; oferta pelo WhatsApp com o número certo (sem 55 repetido) e o texto com as variáveis
  trocadas; resultado "aceitou" com R$ 1.250,00 preservado ao reabrir; telas em 1280 e 390 px, claro e escuro, sem erro no
  console.
- **Para depois**: o `--forwarded-allow-ips "*"` do `render.yaml` confia no primeiro IP do `X-Forwarded-For`, que o cliente
  escolhe; o limite por IP das rotas públicas só vale se a Render sobrescrever esse cabeçalho (conferir e, se preciso, declarar
  só a rede do proxy).

