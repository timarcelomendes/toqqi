# Toqqi · API da etapa 3a (envios por e-mail, lembretes, robô, descadastro)

Mesmas convenções das etapas 1 e 2: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, `requer(...)`,
listas paginadas `{itens,total,pagina,por_pagina}`, datas ISO 8601. Horários de regra em America/Sao_Paulo.
Fica para a 3b: disparo por evento (API com chave, webhooks, Zapier/Make) e WhatsApp pela API oficial da Meta.

## 1. Conceitos
- **Convite**: e-mail (ou link de WhatsApp) que leva a `/r/{token}`. Usa a tabela `convites` da etapa 2 (+ colunas abaixo).
- **Envio**: cada mensagem de pesquisa que sai para um contato (convite, lembrete, agradecimento). Tabela nova `envios`.
  E-mails do sistema (confirmação, senha, convites de equipe) **não** entram no histórico de envios.
- **Intervalo** (`intervalo_dias`, padrão 90): depois de um convite, o contato só volta à fila em `proximo_envio = data do envio + intervalo`.
- **Descanso / anti-cansaço** (`descanso_dias`, padrão 30; 0 desliga): ninguém recebe um novo convite, em nenhum canal,
  se recebeu outro há menos de X dias. Vale para o robô; o envio manual avisa e pula, salvo `ignorar_descanso: true`.
- **Descadastro**: por conta + e-mail (tabela `descadastros`). Descadastrado não recebe nada da conta, em nenhum canal
  que use aquele e-mail; reimportar o contato não o recoloca na lista.

## 2. Pré-condições de qualquer envio
`GET /envios/pre-condicoes` (`envios.ver`) → `{pronto: bool, itens: [{chave, ok, mensagem, acao: {rotulo, rota}|null}]}`, na ordem:
| chave | ok quando | mensagem quando falta |
|---|---|---|
| `assinatura` | conta em `cortesia`, `ativa`, ou `teste` dentro do prazo | "O período de teste acabou. Assine um plano para voltar a enviar." (acao: Assinatura) |
| `provedor` | `EMAIL_PROVIDER` ∈ zeptomail, resend, memory; `console` só conta quando `AMBIENTE != producao` | "O envio de e-mails ainda não foi configurado na plataforma." |
| `formulario` | formulário de convite existe, ativo e não arquivado | "Escolha o formulário usado nos convites." (acao: Configurações de envio) |
| `envios_ativos` | chave geral ligada | "Os envios estão desligados. Ligue em Configurações de envio." |
O envio manual responde 409 `pre_condicao` com a `mensagem` do primeiro item que falta. O robô e os lembretes só registram e não enviam.

## 3. Configurações de envio (`envios.ver` lê, `configuracoes.gerenciar` grava)
`ConfigEnvios` = `{envios_ativos: false, envio_automatico: false, formulario_id (padrão NPS da conta), intervalo_dias: 90 (30–365),
descanso_dias: 30 (0–180), lembretes: 3 (0–3), dias_lembretes: [3,7,15] (crescentes, 1–30, tamanho = lembretes),
janela_inicio: "08:00", janela_fim: "18:00", so_dias_uteis: true, responder_para: email|null, remetente_nome: string|null (padrão: nome da conta),
assunto_convite: "{empresa} quer saber a sua opinião", texto_convite: "Olá, {nome}!\n\nSua opinião ajuda a {empresa} a melhorar. Leva menos de um minuto.",
assunto_lembrete: "Lembrete: {empresa} quer saber a sua opinião", texto_lembrete: "Olá, {nome}! Ainda dá tempo de responder...",
texto_whatsapp: "Olá, {nome}! Aqui é da {empresa}. Pode responder uma pesquisa rápida? Leva 1 minuto: {link}",
agradecimento_ativo: true, agradecimento: {promotor: "...", neutro: "...", detrator: "..."}}`.
- `GET /envios/configuracao` → `ConfigEnvios` (criada com os padrões na primeira leitura).
- `PUT /envios/configuracao` (corpo parcial aceito) → `ConfigEnvios` · 422 com `campos` (faixas, `janela_fim > janela_inicio`, dias crescentes,
  `texto_whatsapp` precisa conter `{link}`, assunto até 150, textos até 2000, formulário da conta e ativo). Auditoria `config_envios`.
- `POST /envios/configuracao/teste` → 200 `{mensagem: "Enviamos um exemplo para voce@..."}`: envia um convite de exemplo para o e-mail do
  usuário logado (não cria convite real; link aponta para o formulário público com `?canal=link`). Não entra no histórico.
Variáveis nos textos: `{nome}` (primeiro nome; vazio remove ", " antes), `{empresa}` (nome da conta — mesmo sentido das páginas públicas),
`{empresa_cliente}` (empresa do contato), `{link}` (só WhatsApp), `{nota}` (só agradecimento). Textos são texto puro (sem HTML);
o layout do e-mail é da plataforma.

## 4. Conteúdo do e-mail de convite / lembrete
- De: `"{remetente_nome} via Toqqi" <EMAIL_FROM>`; Responder-para: `responder_para` se houver.
- Corpo: texto da conta (parágrafos) + bloco de nota: formulário NPS → botões 0–10 (0–6 vermelho, 7–8 amarelo, 9–10 verde),
  cada um com link `/r/{token}?nota=N`; CSAT/estrelas → 5 botões (1–5); personalizado → botão "Responder pesquisa".
  Rótulos "Nada provável" / "Muito provável" no NPS. Versão texto com o link.
- Rodapé: "Você recebeu esta pesquisa porque é cliente de {empresa}." + link "Não quero mais receber pesquisas" (`/sair/{token_descadastro}`).
- Cabeçalhos: `List-Unsubscribe: <{API_PUBLIC_URL}/api/v1/publico/descadastro/{token}>, <mailto:...>` (mailto opcional) e
  `List-Unsubscribe-Post: List-Unsubscribe=One-Click`. ZeptoMail via `mime_headers`, Resend via `headers`.
- Lembrete: mesmo link do convite (mesmo token), assunto/texto de lembrete.
- `token_descadastro`: assinado (HMAC com JWT_SECRET) com conta_id e e-mail; não expira.

## 5. Fila e envio manual
`ContatoEnvio` = `{id, nome, email|null, telefone|null, empresa: {id,nome}|null, grupo: {id,nome}|null, responsavel: {id,nome}|null,
ativo, situacao, ultimo_envio|null, proximo_envio (data)|null, lembretes_enviados, proximo_lembrete (data)|null, descanso_ate (data)|null,
ultimo_erro|null, enviando: bool}`.
`situacao` (mesma usada em `Contato.situacao`, agora calculada de verdade), por ordem de prioridade:
`inativo` → `saiu_da_lista` (descadastrado ou `recebe_pesquisas=false`) → `nao_saiu` (último convite com erro) → `enviando` (pendente)
→ `aguardando` (convite enviado, sem resposta, ainda dentro de maior prazo de lembrete + 7 dias) → `respondeu` (respondeu o último convite
e `proximo_envio` no futuro) → `na_fila` (nunca recebeu, ou `proximo_envio <= hoje`, ou convite expirou sem resposta e passou o intervalo)
→ senão `aguardando_intervalo` ("Próximo envio em dd/mm"). O valor `nunca_enviado` da etapa 2 deixa de existir (vira `na_fila`).

- `GET /envios/resumo` → `{na_fila, aguardando, responderam, com_erro, saiu_da_lista, lembretes_hoje, enviados_30d}` (só ativos, exceto saiu_da_lista).
- `GET /envios/contatos?situacao=&busca=&grupo_id=&responsavel_id=&empresa_id=&proximo_de=&proximo_ate=&ultimo_de=&ultimo_ate=&lembrete=hoje|amanha&mostrar_inativos=false&pagina=`
  → paginado `ContatoEnvio`, ordenado por mais atrasado primeiro (proximo_envio nulo primeiro).
- `POST /envios/disparar` (`envios.disparar`) `{contato_ids?: [int] (1–500), toda_fila?: bool, filtros?: {mesmos filtros da lista}, ignorar_descanso?: false}`
  → 202 `{agendados: int, ignorados: [{contato_id, nome, motivo}] (até 500)}`. Exatamente um de `contato_ids` / `toda_fila`.
  Motivos: "Contato inativo", "Saiu da lista", "Sem e-mail", "Recebeu uma pesquisa há N dias (descanso de X dias)", "Já está sendo enviado".
  Ignora o intervalo (é manual). Cria convites + envios `pendente` e processa em segundo plano (BackgroundTasks), 1 a 1;
  a tela recarrega a lista a cada 3 s enquanto houver `enviando`. Auditoria `envio_manual` com a quantidade.
  409 `pre_condicao` se faltar pré-condição; 422 se mais de 500 ids.
- `POST /envios/{envio_id}/tentar-de-novo` (`envios.disparar`) → 202 · 409 se não for o erro mais recente do contato ou se ele não pode receber.
- `POST /contatos/{id}/whatsapp` (`envios.disparar`) `{formulario_id?}` → 201 `{url: "https://wa.me/55...?text=...", mensagem, link}`.
  Exige telefone (422 "Este contato não tem telefone."), ativo e não descadastrado (409). Cria convite canal `whatsapp` e envio
  `aberto_no_whatsapp` (conta como enviado para intervalo e descanso; a tela explica que a confirmação depende de quem enviou).
  Não exige provedor de e-mail nem `envios_ativos`, só assinatura.

## 6. Histórico (`envios.ver`)
`Envio` = `{id, criado_em, contato: {id,nome}|null, para, canal: "email"|"whatsapp", tipo: "convite"|"lembrete"|"agradecimento",
origem: "manual"|"automatico"|"lembrete"|"resposta", situacao: "pendente"|"enviado"|"erro"|"aberto_no_whatsapp", erro|null (texto simples),
usuario: {id,nome}|null, pode_tentar_de_novo: bool}`.
- `GET /envios/historico?de=&ate=&tipo=&canal=&situacao=&busca=&contato_id=&pagina=` → paginado, mais novo primeiro.
Erros em linguagem simples: "O endereço de e-mail não existe ou recusou a mensagem.", "O provedor de e-mail está fora do ar; tentaremos de novo.",
"Limite de envio do provedor atingido; tentaremos de novo." (nunca o texto técnico do provedor; ele vai para o log).

## 7. Robô e lembretes
Rodam fora da requisição: `python -m toqqi.tarefas [robo|lembretes|pendentes|tudo]` (padrão `tudo`), ou
`POST /api/v1/interno/tarefas` com cabeçalho `X-Tarefas-Token: <TAREFAS_TOKEN>` (comparação em tempo constante; 404 se o token não
estiver configurado; 401 se errado) → `{robo: {...}, lembretes: {...}, pendentes: n}`. Em produção, o Cron Job `toqqi-tarefas` do
Render roda `python -m toqqi.tarefas` a cada 15 minutos (etapa 4a; antes era uma rotina do GitHub Actions); a rota fica para rodar à mão.
- **Robô** (por conta, em modo sistema e depois `em_conta`): só se pré-condições ok **e** `envio_automatico`; só dentro da janela e
  (se `so_dias_uteis`) de segunda a sexta; no máximo 1 rodada a cada 6 h por conta (`robo_rodou_em`); até 100 contatos por rodada,
  mais atrasados primeiro. Elegível: ativo, com e-mail, não descadastrado, `recebe_pesquisas`, `na_fila`, fora do descanso, sem
  convite pendente, menos de 3 falhas seguidas. Sucesso: `proximo_envio = hoje + intervalo`, zera falhas. Erro: `falhas += 1`
  (com 3, sai da fila automática até um envio manual dar certo).
- **Lembretes**: uma vez por dia por conta, a partir das 10:00, dentro da janela (`lembretes_rodou_em`); até 200 por conta.
  Para cada convite por e-mail sem resposta: envia o lembrete n quando `hoje >= data do convite + dias_lembretes[n-1]` e
  `lembretes_enviados < lembretes`. Não envia se: respondeu, contato inativo/descadastrado, `envios_ativos` desligado, existe convite
  mais novo para o contato, convite com mais de (maior prazo + 7) dias, convite por WhatsApp.
- **Pendentes**: envios `pendente` há mais de 10 min (queda do processo) são reprocessados.
- `GET /envios/lembretes/previa` → `{hoje: n, amanha: n}` · `POST /envios/lembretes/executar` (perfil admin) → `{enviados, ignorados}`
  (ignora horário e o "uma vez por dia"). · `POST /envios/robo/executar` (perfil admin) → `{agendados, ignorados}` (ignora janela e 6 h,
  respeita o resto).

## 8. Agradecimento automático
No ponto único `ao_registrar_resposta`: se `agradecimento_ativo`, a resposta tem grupo (NPS/CSAT), o contato tem e-mail e não está
descadastrado → cria envio `agradecimento` (origem `resposta`) e envia depois do commit (em segundo plano). Texto por grupo
(promotor/satisfeito → `promotor`, neutro → `neutro`, detrator/insatisfeito → `detrator`), com `{nome}`, `{empresa}`, `{nota}`.
Também atualiza o contato (situação passa a `respondeu`). Uma resposta sem contato identificado não gera agradecimento.

## 9. Descadastro (páginas públicas, sem login; 20/min por IP)
- `GET /publico/descadastro/{token}` → `{email_mascarado: "ma***@empresa.com.br", empresa (nome da conta), descadastrado: bool}` · 404 `link_invalido`.
- `POST /publico/descadastro/{token}` JSON `{motivo?: string (≤300)}` → `{descadastrado: true}`; JSON `{voltar: true}` → `{descadastrado: false}`.
  Corpo `application/x-www-form-urlencoded` `List-Unsubscribe=One-Click` → 200 (origem `um_clique`).
  Registra origem (`link`/`um_clique`) e motivo; auditoria na conta (`descadastro` / `descadastro_desfeito`), sem o e-mail completo.
- Página web `/sair/{token}` (entrada pública leve, como `/r` e `/f`): mostra e-mail mascarado e empresa, motivos rápidos
  ("Recebo pesquisas demais", "Não sou cliente", "Não quero informar") + campo livre, botão "Não quero mais receber";
  depois, confirmação com "Mudei de ideia, quero voltar a receber".
- Tela interna: `GET /envios/descadastros?busca=&pagina=` (`envios.ver`) → paginado `{email, contato: {id,nome}|null, motivo, origem, criado_em}`;
  `POST /envios/descadastros` (`contatos.editar`) `{email, motivo?}` → 201 (origem `manual`, ex.: pedido por telefone). Não há "recolocar"
  pela empresa: só a própria pessoa volta pela página.

## 10. Plataforma: excluir conta (superadmin)
- `DELETE /plataforma/contas/{id}` `{confirmar_nome: string}` → 204. 409 `nome_nao_confere` se o nome não bater (sem diferenciar
  maiúsculas); 409 `propria_conta` se for a conta do superadmin logado. Apaga a conta e tudo dela (usuários, sessões, contatos,
  respostas, envios...). Auditoria global `conta_excluida` com nome e id (registrada sem conta_id, visível só na plataforma).

## 11. Configuração da API (novas variáveis)
`AMBIENTE` (desenvolvimento|producao; Render: producao), `TAREFAS_TOKEN` (Render gera), `EMAIL_FROM` (ex.: `Toqqi <pesquisa@toqqi.com>`),
`ZEPTOMAIL_TOKEN` / `RESEND_API_KEY` já existentes.
