# Toqqi · API da etapa 3b (integrações e WhatsApp automático)

Mesmas convenções das etapas anteriores. Contrato da 3a em `api-etapa-3.md` (envios, descadastro, pré-condições, tarefas).

## 1. Chave da conta (para ERP, Zapier, Make, n8n)
- Formato `tq_live_<40 caracteres url-safe>`. Guardada só como hash (sha256); mostrada **uma vez**, ao gerar.
- `GET /integracoes/chave` (perfil admin) → `{existe: bool, prefixo: "tq_live_ab12…"|null, criada_em|null, ultimo_uso|null}`.
- `POST /integracoes/chave` (perfil admin) → 201 `{chave, prefixo, criada_em}`; se já existia, a anterior para de valer na hora.
  Auditoria `chave_gerada` (gravidade atencao, só o prefixo).
- `DELETE /integracoes/chave` (perfil admin) → 204 (revoga; auditoria `chave_revogada`).
- Autenticação nas rotas de integração: cabeçalho `X-Api-Key: <chave>` (também aceita `Authorization: Bearer tq_live_...`).
  401 `chave_invalida` ("Chave de integração inválida ou revogada."). Limite: 120 chamadas/min por chave (429).
  A chave age como a conta (sem usuário): auditoria com `usuario: null` e `detalhe.origem = "integracao"`.

## 2. Disparo por evento (entrada)
`POST /integracao/pesquisas` (chave) — "o pedido foi entregue, pesquise este cliente":
```
{ "email"?: str, "telefone"?: str, "nome"?: str (≤120),
  "empresa"?: {"nome"?: str, "documento"?: str, "codigo_externo"?: str},
  "codigo_externo"?: str (id do contato no ERP),
  "evento"?: str (≤60, ex. "pedido_entregue"), "referencia"?: str (≤120, ex. nº do pedido),
  "contexto"?: {pedido?, nota_fiscal?, rota?, motorista?, filial?, transportadora?},
  "formulario_id"?: int, "tipo"?: "nps"|"csat" (usa o formulário padrão do tipo; padrão "csat" se houver referencia, senão "nps"),
  "canal"?: "auto"|"email"|"whatsapp"|"link" (padrão "auto"), "enviar"?: bool (padrão true),
  "ignorar_descanso"?: bool (padrão false), "id_evento"?: str (≤100, idempotência por 24 h) }
```
→ 201 `{situacao, convite_id|null, link|null, canal|null, contato_id|null, mensagem}`; com o mesmo `id_evento` em 24 h → 200 com a mesma resposta.
`situacao`: `enviado` | `link_gerado` | `ignorado_descadastrado` | `ignorado_descanso` | `ignorado_inativo` | `sem_canal` | `erro`.
- Precisa de e-mail ou telefone (422). Contato: procura por `codigo_externo`, depois e-mail, depois telefone; se não existe, cria
  (respeita limite do plano → 402). Empresa: procura por `codigo_externo`, documento ou nome; cria se vier nome.
- `canal: "auto"`: WhatsApp automático se a conta tiver WhatsApp ativo, franquia disponível e o contato tiver telefone; senão e-mail;
  senão `link` (só gera o link, para o ERP mandar como quiser). `enviar: false` → só gera o link.
- Respeita pré-condições (assinatura sempre; provedor/`envios_ativos` só quando for enviar e-mail), descadastro e descanso.
  Não respeita a janela de horário nem o intervalo (o evento é imediato e ligado a um pedido); a proteção é o descanso.
- O convite guarda `evento`, `referencia` e `contexto`; a resposta herda o contexto (relatórios por motorista/rota na etapa 4).
`POST /integracao/csat` (chave): mesmo corpo, compatível com o Rakiti (`enviar_email` = `enviar`, `assunto` vira `contexto.assunto`); `tipo` padrão "csat".
`GET /integracao/teste` (chave) → `{conta: nome, ok: true}` (para o Zapier/Make validarem a chave).

## 3. Webhooks de saída
`Webhook` = `{id, url, eventos: ["resposta.criada" | "contato.descadastrado"], ativo, segredo_prefixo, criado_em, ultima_entrega: {quando, status_http|null, ok}|null, falhas_seguidas}`.
- `GET /integracoes/webhooks`, `POST /integracoes/webhooks` `{url, eventos}` → 201 com `segredo` (mostrado uma vez), `PATCH /integracoes/webhooks/{id}` `{url?, eventos?, ativo?}`,
  `DELETE /integracoes/webhooks/{id}`, `POST /integracoes/webhooks/{id}/novo-segredo` → `{segredo}`, `POST /integracoes/webhooks/{id}/testar` → `{ok, status_http|null, mensagem}`
  (perfil admin; até 5 por conta). `GET /integracoes/webhooks/{id}/entregas?pagina=` → `[{id, evento, criado_em, tentativas, status_http, ok, erro}]` (últimos 30 dias).
- URL: só `https://` com endereço público (mesma regra do Teams: resolve DNS e recusa IP privado/loopback/link-local; conecta no IP verificado; sem redirecionamento; timeout 10 s).
- Envio: POST JSON `{id: "<uuid da entrega>", evento, criado_em, conta: {id, nome}, dados: {...}}` com cabeçalhos
  `X-Toqqi-Evento`, `X-Toqqi-Entrega`, `X-Toqqi-Assinatura: t=<unix>,v1=<hex HMAC-SHA256(segredo, "<t>.<corpo>")>`.
  `resposta.criada`: `dados` = Resposta (formato da etapa 2) + `convite: {evento, referencia}`; `contato.descadastrado`: `{email_mascarado, contato_id, origem}`.
- Entrega fora da requisição (fila `webhook_entregas`): 2xx = ok; senão novas tentativas em 1 min, 5 min, 30 min, 2 h, 6 h (5 no total) pela rotina de tarefas.
  10 falhas seguidas → webhook desativado e aviso por e-mail aos admins.

## 4. WhatsApp automático (API oficial da Meta — Cloud API)
Modelo de negócio: a Toqqi é Tech Provider; cada conta conecta o próprio número (WABA). Nesta etapa a conexão é por formulário
(o "Conectar com o Facebook" — Embedded Signup — entra quando a Meta aprovar o app).
- `GET /integracoes/whatsapp` (perfil admin; leitura também com `envios.ver`) → `{conectado, numero_exibicao|null, nome_verificado|null,
  phone_number_id|null, waba_id|null, modelo: {nome, idioma}|null, ativo, franquia: {plano, limite, usadas_mes, excedente_ativo, excedentes_mes, valor_excedente: 1.50},
  ultimo_erro|null, webhook_url, webhook_verificacao}` (`webhook_url` e `webhook_verificacao` são para colar no painel da Meta).
- `PUT /integracoes/whatsapp` (perfil admin) `{phone_number_id, waba_id, token (permanente, de usuário do sistema), modelo_nome, modelo_idioma ("pt_BR")}` →
  valida chamando a Graph API (`GET /{phone_number_id}?fields=display_phone_number,verified_name`) e o modelo
  (`GET /{waba_id}/message_templates?name=...`, status APPROVED, categoria; precisa ter botão URL dinâmico); 422 com mensagem simples se falhar.
  Token guardado cifrado (Fernet; chave derivada de `SEGREDOS_KEY`), nunca devolvido.
- `PATCH /integracoes/whatsapp` `{ativo?, excedente_ativo?}` · `DELETE /integracoes/whatsapp` (desconecta e apaga o token) · `POST /integracoes/whatsapp/teste` `{telefone}` → envia o modelo para o número.
- Modelo esperado (o cliente cria no WhatsApp Manager; a tela mostra o texto sugerido, categoria Utilidade):
  corpo com `{{1}}` = primeiro nome, `{{2}}` = nome da conta, `{{3}}` = referência ("seu pedido 1234" / "nosso atendimento");
  botão de URL dinâmica `https://<FRONTEND_URL>/r/{{1}}` (o sufixo é o token do convite).
- Envio: `POST https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}/{phone_number_id}/messages` com `type: template`.
  Guarda o `wamid` no envio; situação `enviado` → atualizada pelo webhook para `entregue`, `lido` ou `erro` (erro com texto simples).
- Canal na configuração de envios (`ConfigEnvios.canal`): `"email"` (padrão) | `"whatsapp"` (WhatsApp; sem telefone → e-mail) |
  `"whatsapp_e_email"` (WhatsApp; se falhar ou sem telefone → e-mail). Vale para o robô, o envio manual e o evento `auto`.
  Lembretes: no máximo 1 por WhatsApp (o 1º); os demais por e-mail se houver e-mail.
- Franquia por mês (calendário, America/Sao_Paulo) por conta: essencial 40, profissional 90, empresa 200, cortesia 200, teste 20
  (conta convites por WhatsApp automático, não o "link pronto"). Aviso por e-mail aos admins aos 80% e aos 100%.
  Acabou: envio cai para e-mail (se houver), salvo `excedente_ativo` (cobrado R$ 1,50 cada, registrado em `excedentes_mes`).
- Webhook da Meta (público): `GET /publico/whatsapp/webhook` (hub.mode/hub.verify_token/hub.challenge; token = `WHATSAPP_VERIFY_TOKEN`) e
  `POST /publico/whatsapp/webhook` (valida `X-Hub-Signature-256` com `WHATSAPP_APP_SECRET`; 401 se inválida). Trata:
  `statuses` (atualiza o envio pelo `wamid`) e `messages` de texto: "SAIR", "PARAR", "STOP", "CANCELAR" (sem diferenciar maiúsculas/acentos)
  → descadastro do telefone na conta dona do `phone_number_id` (origem `whatsapp`) e resposta automática de confirmação
  (mensagem de sessão, dentro das 24 h). Descadastro por telefone vale como o por e-mail (tabela `descadastros` ganha `telefone`).
- Variáveis de ambiente: `SEGREDOS_KEY` (Render gera), `WHATSAPP_GRAPH_VERSION` (padrão `v23.0`), `WHATSAPP_VERIFY_TOKEN` (Render gera), `WHATSAPP_APP_SECRET` (do app da Meta).

## 5. Telas
- **Integrações** (`/integracoes`, menu Administração; perfil admin): chave da conta (gerar, copiar uma vez, revogar), exemplos prontos
  (cURL, e explicação para Zapier/Make/n8n: "Webhooks by Zapier → POST"), webhooks de saída (lista, criar, testar, entregas), WhatsApp
  (passo a passo para conectar, campos, modelo sugerido para copiar, franquia do mês com barra e aviso, ligar/desligar, excedente, teste).
- **Configurações de envio**: escolha do canal (e-mail / WhatsApp / WhatsApp com e-mail de reserva) — só habilita WhatsApp se conectado.
- **Envios**: histórico mostra situação do WhatsApp (Enviado, Entregue, Lido, Não saiu) e canal; resumo mostra franquia usada no mês.
