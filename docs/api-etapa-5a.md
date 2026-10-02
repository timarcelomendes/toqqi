# Toqqi · Etapa 5a (assinatura e cobrança pelo Asaas)

Mesmas convenções das etapas anteriores: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, `requer(...)`,
datas ISO 8601, valores em reais como decimal, dias de regra em America/Sao_Paulo (`toqqi.core.relogio`), RLS por conta.
A etapa 5 foi dividida: **5a = assinatura e cobrança** (esta); depois IA sob demanda e assistente, Teams e Fillout, modelos de
e-mail e banco de imagens, auditoria completa, zona de risco e exportação (LGPD).
Pronto quando: teste grátis, assinatura e pagamento funcionam no ambiente de testes (sandbox) do Asaas.

## 0. Decisões
- **Preços e limites** (especificação): Essencial R$ 149/mês até 300 contatos ativos; Profissional R$ 349 até 1.500; Empresa
  R$ 799 sem limite. Cobrança mensal pelo Asaas numa **fatura em que o cliente escolhe Pix, boleto ou cartão**
  (`billingType: UNDEFINED`).
- **Assinar durante o teste**: o teste continua e a **primeira fatura vence no último dia do teste** (decisão do Marcelo em 01/10).
  Assinar sem teste válido (expirado ou cancelada sem período pago): a primeira fatura vence amanhã, e os envios voltam quando o
  pagamento for confirmado (Pix e cartão em segundos; boleto em até 3 dias úteis).
- **Ativa** só com pagamento confirmado (`CONFIRMED` ou `RECEIVED`, o que vier primeiro: no cartão o `RECEIVED` chega ~32 dias depois).
- **Atrasada**: envios liberados por 7 dias depois do vencimento da fatura em aberto; depois, pausados até pagar.
- **Cancelar**: remove a assinatura no Asaas (o Asaas apaga junto as faturas pendentes e vencidas); o uso continua até o fim do
  período pago, sem multa e sem devolução. Quem cancela durante o teste, antes de pagar, volta para o teste até ele acabar.
- **Trocar de plano**: muda o valor também das faturas em aberto (`updatePendingPayments: true`) e o limite de contatos na hora.
  Plano menor com mais contatos ativos que o limite novo é recusado (desative contatos antes).
- **Fonte da verdade do pagamento é o Asaas**: o webhook só avisa; a API consulta a cobrança no Asaas (`GET /payments/{id}`) antes
  de mudar a situação da conta (evento fora de ordem ou forjado não muda nada).
- **Fica para depois** (decisões do Marcelo em 01/10): nota fiscal (NFS-e) automática (quando o Asaas estiver habilitado com os
  dados do contador) e cobrança do excedente de WhatsApp (quando o WhatsApp automático estiver no ar).
- Superadmin "+14 dias": conta a partir do fim do teste atual (o código já faz assim), e não vale para conta com assinatura ativa.

## 1. Banco (migração `0008_assinaturas`)
`contas` ganha: `asaas_cliente_id text` (cliente no Asaas, reaproveitado), `pago_ate date` (último dia coberto por pagamento,
inclusivo), `atrasada_desde date` (vencimento da fatura vencida mais antiga em aberto).

Tabelas novas (`conta_id DEFAULT app_conta()`, ENABLE + FORCE RLS, política padrão, grants condicionais, FKs compostas):
- `assinaturas (id, conta_id, asaas_id text UNIQUE, plano, valor numeric(10,2), situacao 'ativa'|'cancelada', razao_social
  (≤ 200), documento (CPF 11 ou CNPJ 14 dígitos), email_cobranca citext, telefone (10–13 dígitos), primeiro_vencimento date,
  criada_em, criada_por (usuário, SET NULL), cancelada_em, cancelada_por)`. Uma ativa por conta (índice único parcial).
- `cobrancas (id, conta_id, assinatura_id (SET NULL), asaas_id text UNIQUE, valor, valor_liquido, vencimento date,
  situacao 'pendente'|'paga'|'vencida'|'estornada'|'removida', situacao_asaas text, forma 'pix'|'boleto'|'cartao'|null,
  pago_em timestamptz, link text (fatura), criada_em, atualizada_em)`. Índice `(conta_id, vencimento DESC)`.
- `asaas_eventos (id text PK (o id do evento, "evt_…"), tipo text, conta_id bigint null, cobranca_asaas_id text, recebido_em,
  processado_em, tentativas smallint, erro text)` — tabela da plataforma: sem `conta_id` obrigatório, lida e gravada só em
  modo sistema (RLS FORCE com política só para `app_sistema()`). Guarda o mínimo (ids e tipo), não o corpo inteiro do evento.

## 2. Adaptador (`toqqi/core/asaas.py`, httpx, sem SDK)
Variáveis: `ASAAS_API_KEY`; `ASAAS_WEBHOOK_TOKEN`; `ASAAS_URL` (opcional, para testes). O endereço segue a chave:
`$aact_prod_…` → `https://api.asaas.com/v3`; `$aact_hmlg_…` → `https://api-sandbox.asaas.com/v3`; `ASAAS_URL` sobrepõe.
`disponivel()` = chave preenchida. Cabeçalhos: `access_token: <chave>`, `User-Agent: Toqqi/1.0` (obrigatório para contas novas),
`Content-Type: application/json`. Tempo limite 20 s. `transporte` trocável nos testes (como `core/ia.py`).
Funções: `criar_cliente(dados) -> id`, `atualizar_cliente(id, dados)`, `criar_assinatura(cliente, valor, vencimento, descricao,
referencia) -> id`, `atualizar_assinatura(id, valor, descricao)` (`PUT /subscriptions/{id}` com `updatePendingPayments: true`),
`remover_assinatura(id)` (`DELETE /subscriptions/{id}`), `cobrancas_da_assinatura(id) -> list` (`GET /subscriptions/{id}/payments`),
`obter_cobranca(id) -> dict` (`GET /payments/{id}`).
- Cliente: `{name: razão social, cpfCnpj, email, mobilePhone (DDD + número, sem 55), externalReference: "toqqi-conta-{id}"}`.
- Assinatura: `{customer, billingType: "UNDEFINED", value, nextDueDate: "AAAA-MM-DD", cycle: "MONTHLY",
  description: "Toqqi – plano Profissional", externalReference: "toqqi-conta-{id}"}`.
- Erros (`FalhaAsaas`): 400 com `errors: [{code, description}]` → **recusado** (vira 422; `invalid_cpfCnpj` → campo `documento`,
  `invalid_email` → `email_cobranca`, `invalid_mobilePhone`/`invalid_phone` → `telefone`, outros → mensagem geral com a
  `description` do Asaas); 401/403 → **configuração** (log de erro, 503 para a tela); 404 → **não encontrado**; 429, 5xx, tempo
  esgotado e rede → **indisponível** (503 `cobranca_indisponivel`: "A cobrança está temporariamente indisponível. Tente de novo em
  alguns minutos."). O log nunca leva a chave nem o CPF/CNPJ.
- Situação do Asaas → nossa: `PENDING`/`AWAITING_RISK_ANALYSIS` → pendente; `CONFIRMED`/`RECEIVED`/`RECEIVED_IN_CASH` → paga;
  `OVERDUE` → vencida; `REFUNDED`/`REFUND_REQUESTED`/`REFUND_IN_PROGRESS`/`CHARGEBACK_*`/`AWAITING_CHARGEBACK_REVERSAL` →
  estornada; cobrança removida (`deleted: true` ou evento `PAYMENT_DELETED`) → removida. `billingType` PIX/BOLETO/CREDIT_CARD →
  pix/boleto/cartao. `pago_em` = `clientPaymentDate` ou `paymentDate`.

## 3. Situações da conta e regras
`contas.situacao` (já existe o CHECK): `teste`, `teste_expirado`, `ativa`, `atrasada`, `cancelada`, `cortesia`.
Uma função única `recalcular(conta)` decide a situação depois de qualquer mudança (assinar, cancelar, webhook, tarefa):
- `cortesia` não muda por cobrança.
- Assinatura **ativa**: há cobrança vencida em aberto → `atrasada` (`atrasada_desde` = vencimento da mais antiga); senão, já houve
  cobrança paga → `ativa`; senão (primeira fatura ainda em aberto) → `teste` se o teste não acabou, senão `teste_expirado`.
- Assinatura **cancelada** (ou nenhuma, depois de ter tido) → `cancelada` se já houve pagamento; senão `teste`/`teste_expirado`.
- Sem assinatura → `teste` ou `teste_expirado` pelo `teste_ate`.
- Pagamento confirmado: `pago_ate = max(pago_ate, vencimento + 1 mês − 1 dia)`; `atrasada_desde` refeito.
**Liberada** (substitui `assinatura_ok`: envios, robô, lembretes, CSAT, análise por IA): `cortesia` e `ativa` sempre; `teste`
enquanto `agora < teste_ate` ou, com assinatura ativa, até o fim do dia do primeiro vencimento; `atrasada` até o fim do 7º dia
depois de `atrasada_desde`; `cancelada` até o fim do dia `pago_ate`; `teste_expirado` nunca. Os dados nunca são apagados.
`conta_json` (em `/eu` e no login) ganha `cobranca: {liberada, pago_ate, atrasada_desde, pausa_em|null, aviso|null}` com
`aviso = {tipo, data|null, dias|null}`, `tipo` ∈ `teste_acabando` (teste com 5 dias ou menos), `teste_expirado`, `atrasada`
(dentro dos 7 dias; `data` = quando os envios param), `pausada` (atrasada depois dos 7 dias), `cancelada` (ainda dentro do período
pago; `data` = `pago_ate`), `cancelada_encerrada`.

## 4. Rotas da assinatura
- `GET /assinatura/planos` (logado) → `[{chave, nome, preco, contatos|null}]` (os 3, na ordem).
- `GET /assinatura` (`assinatura.gerenciar`) → `{conta: {situacao, plano, teste_ate, pago_ate, atrasada_desde, liberada, pausa_em},
  contatos_ativos, disponivel (Asaas configurado), planos, dados_sugeridos: {razao_social, documento, email_cobranca, telefone}
  (dos dados da empresa e do e-mail do admin), assinatura: {plano, valor, situacao, criada_em, cancelada_em, primeiro_vencimento,
  dados: {razao_social, documento, email_cobranca, telefone}}|null, fatura_aberta: {valor, vencimento, situacao, link}|null
  (a pendente ou vencida mais antiga), cobrancas: [{valor, vencimento, situacao, forma, pago_em, link}] (12 mais recentes)}`.
- `POST /assinatura` (`assinatura.gerenciar`) `{plano, razao_social, documento, email_cobranca, telefone}` → mesmo formato.
  Valida como em Dados da empresa (CPF/CNPJ pelos dígitos, e-mail, telefone com DDD). 409 `ja_assinada` (assinatura ativa), 409
  `cortesia` ("Sua conta é cortesia: não precisa assinar."), 422 `limite_do_plano` (contatos ativos acima do limite do plano),
  503 se o Asaas não está configurado ou fora do ar. Cria (ou atualiza) o cliente, cria a assinatura com o primeiro vencimento
  da seção 0, busca a primeira cobrança (`fatura_aberta` com o link de pagamento), muda `contas.plano`, `recalcular`. Uma por vez
  por conta (trava); se o Asaas falhar depois de criar o cliente, o id do cliente fica guardado para a próxima tentativa.
  Auditoria `assinatura_criada` (`{plano, valor}`).
- `PUT /assinatura/plano` `{plano}` → mesmo formato. 409 `sem_assinatura`; 422 `limite_do_plano` ("Você tem N contatos ativos;
  o plano X permite até M. Desative contatos antes de trocar."). Auditoria `plano_alterado` (`{de, para}`).
- `PUT /assinatura/dados` `{razao_social, documento, email_cobranca, telefone}` → atualiza o cliente no Asaas e a assinatura
  local. Auditoria `dados_cobranca_alterados` (só os nomes dos campos).
- `POST /assinatura/cancelar` → remove no Asaas, marca `cancelada`, `recalcular`. Auditoria `assinatura_cancelada`
  (gravidade atencao). Assinar de novo depois: primeira fatura no dia seguinte ao `pago_ate` (se ainda no futuro) ou amanhã.
- Erro do limite de contatos (402 `limite_do_plano`, etapa 2) ganha `campos`/detalhe com o limite para a tela oferecer "Ver planos".

## 5. Webhook do Asaas
`POST /api/v1/asaas/webhook` (sem login). Sem `ASAAS_WEBHOOK_TOKEN` configurado → 404. Cabeçalho `asaas-access-token` diferente
(comparação de tempo constante) → 401. Corpo `{id, event, dateCreated, payment?}`.
1. Grava `asaas_eventos` (o `id` é a chave: repetido → 200 `{ok: true, repetido: true}` sem fazer nada).
2. Eventos `PAYMENT_*` com `payment.subscription` de uma assinatura nossa (senão: guarda, marca ignorado e responde 200): consulta
   `GET /payments/{id}` no Asaas, grava/atualiza a `cobrancas` (ou marca `removida` se o Asaas não acha mais), `recalcular`.
   Auditoria `pagamento_confirmado` (info), `pagamento_vencido` (atencao), `pagamento_estornado` (atencao) quando a situação muda.
3. Responde 200 depressa. Erro no passo 2 (Asaas fora, banco) → ainda 200, evento com `erro` e `tentativas`; a tarefa tenta de
   novo (até 5 vezes). Limite alto por IP (300/min).

## 6. Tarefa `assinaturas` (agendador, em `tudo`)
- Teste vencido sem assinatura ativa → `teste_expirado` (e qualquer conta cuja situação mude pelas datas é recalculada).
- Reprocessa eventos com erro (até 5 tentativas).
- **Conferência diária**: uma vez por dia por conta com assinatura ativa (ou cancelada há menos de 40 dias), busca as cobranças da
  assinatura no Asaas e atualiza as locais (pega webhook perdido). Sem Asaas configurado, só a primeira parte.
- Devolve `{testes_expirados, eventos_reprocessados, contas_conferidas}`.

## 7. Plataforma (superadmin)
- Lista ganha `pago_ate`, `atrasada_desde` e `assinatura: {plano, valor, situacao}|null`.
- "+14 dias" → 409 `assinatura_ativa` se a conta tem assinatura ativa ou é cortesia.
- "Cortesia": se houver assinatura ativa, remove no Asaas primeiro (falhou → 503, nada muda); marca `cortesia`.

## 8. Telas (web)
- **Assinatura** (`/assinatura`, só com `assinatura.gerenciar`; item no menu do usuário e em Administração):
  - Sem assinatura: situação atual (teste com a data de fim, teste encerrado, cancelada), uso (contatos ativos), os 3 planos em
    cartões (preço, limite de contatos, "envios, formulários e usuários ilimitados"), escolher um → formulário de cobrança
    preenchido com os dados da empresa (razão social, CPF/CNPJ com máscara, e-mail de cobrança, telefone com máscara) e o resumo
    ("Primeira fatura de R$ 349,00 com vencimento em 15/10/2026, no fim do teste. Depois, todo dia 15.") → "Assinar".
  - Com assinatura: plano e situação (selo), a fatura em aberto com "Pagar" (abre a fatura do Asaas em nova aba: Pix, boleto ou
    cartão), próximo vencimento, "Trocar de plano" (mostra o novo valor e o efeito nas faturas em aberto; plano menor com contatos
    demais avisa antes), "Dados de cobrança" (editar), "Cancelar assinatura" (confirmação: "Você continua usando até 14/11/2026.
    Sem multa."), histórico de cobranças (vencimento, valor, forma, situação, link).
  - Asaas não configurado (`disponivel: false`): aviso "A cobrança online ainda não está disponível. Fale com a equipe Toqqi."
  - Depois de assinar, a tela busca de novo a cada 10 s por até 2 min enquanto a fatura estiver em aberto (o Pix confirma rápido) e
    atualiza a sessão quando a conta fica ativa.
- **Avisos no topo** (todas as telas logadas), a partir de `conta.cobranca.aviso`: teste acabando ("Seu teste grátis termina em 3
  dias."), teste encerrado ("Seu teste grátis terminou. Os envios estão pausados; seus dados continuam guardados."), atrasada ("A
  fatura venceu em 10/10. Os envios param em 18/10 se ela não for paga."), pausada ("Envios pausados por falta de pagamento."),
  cancelada ("Assinatura cancelada. Você usa até 14/11.") e cancelada encerrada. Botão "Escolher plano" ou "Pagar agora" só para
  quem tem `assinatura.gerenciar`; os outros veem "Fale com o administrador da conta." O selo atual de teste no cabeçalho continua.
- **Limite de contatos**: a mensagem de limite (criar, importar, reativar) ganha "Ver planos" (admin) → `/assinatura`.
- **Plataforma**: selos das situações novas, "pago até", plano da assinatura; "+14 dias" desabilitado com assinatura ativa;
  confirmação de cortesia diz que a assinatura no Asaas será cancelada.
- Tudo no celular, em tema claro e escuro, sem erros no console.

## 9. Render e configuração (README)
`ASAAS_API_KEY` no painel do Render em **toqqi-api e toqqi-tarefas**; `ASAAS_WEBHOOK_TOKEN` só na toqqi-api (32 a 255
caracteres, sem espaços, diferente da chave). No Asaas (sandbox primeiro): gerar a chave de API; em Integrações › Webhooks,
criar o webhook com a URL `https://<api>/api/v1/asaas/webhook`, eventos de cobranças, o mesmo token, versão v3. Nenhum dos dois vai
no `render.yaml`. Sem eles, a tela de assinatura avisa que a cobrança online não está disponível e o resto funciona.

## 10. Testes (critério de pronto)
- Adaptador (MockTransport): cabeçalhos (`access_token`, `User-Agent`), endereço pela chave, corpos de cliente e assinatura,
  `updatePendingPayments`, erros (400 com campos, 401, 404, 5xx, tempo esgotado), chave e CPF fora do log.
- Assinar no teste (vencimento = último dia do teste) e depois dele (amanhã); 409 e 422; trocar de plano (valor e limite; plano
  menor com contatos demais); cancelar (no teste → volta ao teste; pago → até `pago_ate`); assinar de novo.
- Webhook: token, repetido, fora de ordem (vencida depois de paga continua ativa porque o Asaas diz paga), assinatura desconhecida,
  erro → 200 e a tarefa reprocessa; todas as transições de `recalcular` e os limites de data de "liberada" (7º dia, `pago_ate`,
  fim do dia do primeiro vencimento) em São Paulo.
- Tarefa: teste vencido → `teste_expirado`; conferência diária pega pagamento sem webhook; uma vez por dia.
- Envios, robô, lembretes e IA respeitam "liberada" nas situações novas. Plataforma (+14 dias, cortesia cancela no Asaas).
  `/eu` com cada aviso. Permissões (só admin). RLS das tabelas novas; `asaas_eventos` só em modo sistema. Migração.
- Web: lógica pura (avisos, datas, máscaras, resumo da primeira fatura), componentes e conferência visual em 1280 e 390 px,
  claro e escuro.

## 11. Ajustes feitos na construção (revisão e teste integrado)
Detalhes na seção "Etapa 5a" de `api/README.md` e `web/README.md`.
- **Liberação**: a carência de 7 dias e "ativa" sem pagamento só valem para quem já estava coberto ao assinar (assinou no
  teste ou antes de acabar o `pago_ate`) ou já pagou nessa assinatura; quem assina sem teste válido só volta a enviar
  pagando. Fatura pendente com o vencimento passado já conta como atraso (a tarefa muda à meia-noite). Sem buracos: `teste`
  e `cancelada` valem até o mais tarde entre o fim do teste e o fim do `pago_ate`; quem assinou no teste e não pagou fica
  liberado até o 7º dia depois do primeiro vencimento.
- **Sem assinatura ativa**: `pago_ate` ≥ hoje → `cancelada`; senão teste valendo → `teste`; senão já pagou → `cancelada`;
  senão `teste_expirado`. Quem nunca pagou volta ao plano Profissional (o do teste).
- **Aviso novo** `aguardando_pagamento` (já assinou e a primeira fatura está em aberto) e `cobranca.assinada`.
- **Asaas sem duplicar**: antes de criar cliente e assinatura (e depois de tempo esgotado) a API procura pela referência
  `toqqi-conta-{id}`, adota a que bate com o pedido e remove as outras; remoção que falha fica na tabela `asaas_remocoes` para
  a tarefa repetir. Troca de plano com tempo esgotado confere o valor no Asaas; a conferência diária realinha valores.
- **Ambiente**: assinaturas e cliente guardam o ambiente (sandbox/produção, pela chave); ao trocar a chave do sandbox para a
  de produção, a tarefa cancela as assinaturas de teste e zera `pago_ate` dessas contas. INACTIVE/EXPIRED = removida; 404 por
  3 dias seguidos cancela aqui.
- **Limite de contatos**: o gatilho trava antes de ler o plano (sem corrida com a troca para um plano menor).
- **CNPJ alfanumérico** (Receita, desde 31/07/2026) aceito em empresas, dados da empresa, integrações e cobrança.
- **Webhook**: assinatura desconhecida fica pendente por até 1 hora (o primeiro evento chega antes do fim da assinatura);
  Asaas fora não gasta tentativa. Telefone de cobrança com validação brasileira estrita (celular com 9, fixo de 2 a 5).
- **Telas**: depois de pagar, a confirmação vale para a fatura esperada mesmo com a do mês seguinte já em aberto, que
  aparece como "Próxima fatura"; a sessão (aviso do topo) acompanha a tela de Assinatura e é buscada de novo ao voltar para
  a aba (no máximo a cada 3 min); campos com máscara não cortam o que é colado; com a conta pausada, Envios não oferece o
  WhatsApp e quem não é admin lê "Fale com o administrador da conta." no lugar do atalho.
- **Para conferir no sandbox**: se o PUT com `value` muda a cobrança; vencimento nos dias 29–31; se o Asaas aceita o CNPJ
  alfanumérico. Limitação conhecida: as chamadas ao Asaas acontecem com a linha da conta travada (fica para depois).

