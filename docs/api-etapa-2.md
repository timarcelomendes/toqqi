# Toqqi · API da etapa 2 (cadastros, importação, formulários e páginas públicas)

Mesmas convenções da etapa 1: base `/api/v1`, Bearer, formato de erro `{"erro":{codigo,mensagem,campos}}`,
permissões pelo `requer(...)`. Listas paginadas: `?pagina=1&por_pagina=50` → `{itens, total, pagina, por_pagina}`.
Datas em ISO 8601; valores em reais como número decimal (ex.: `1250.00`).

## 1. Cadastros auxiliares (`contatos.ver` para ler, `contatos.editar` para escrever)
Tipos: `grupos`, `segmentos`, `perfis`, `cargos`. Cada item: `{id, nome, em_uso: int}` (quantas empresas/contatos usam).
- `GET /cadastros/{tipo}` → `[Item]` (sem paginação, ordenado por nome)
- `POST /cadastros/{tipo}` `{nome}` → 201 `Item` · 409 `nome_em_uso`
- `PATCH /cadastros/{tipo}/{id}` `{nome}` → `Item`
- `DELETE /cadastros/{tipo}/{id}` (`contatos.excluir`) → 204; quem usava fica sem o item.
Conta nova já recebe perfis "Decisor" e "Influenciador".

## 2. Responsáveis (pessoas da empresa que cuidam de uma carteira)
`Responsavel` = `{id, nome, funcao, email, foto_url, teams_webhook, empresas: int}`.
- `GET /responsaveis`, `POST /responsaveis`, `PATCH /responsaveis/{id}`, `DELETE /responsaveis/{id}` (`contatos.excluir`).
- `teams_webhook`: só `https://` com endereço público (422 `campos.teams_webhook`).
- `POST /responsaveis/{id}/testar-teams` → 200 `{mensagem}` · 422 se o Teams recusar (timeout 10 s, sem seguir redirecionamento).

## 3. Empresas (clientes da conta)
`Empresa` = `{id, nome, documento (CNPJ/CPF, só dígitos, opcional), grupo: {id,nome}|null, segmento: {id,nome}|null,
responsavel: {id,nome}|null, valor_mensal (R$|null), cliente_desde (data|null), codigo_externo (id no ERP, opcional),
ativa: bool, contatos: int, criada_em}`.
- `GET /empresas?busca=&grupo_id=&segmento_id=&responsavel_id=&ativa=true|false|todas&pagina=` → paginado.
- `POST /empresas` `{nome, documento?, grupo_id?, segmento_id?, responsavel_id?, valor_mensal?, cliente_desde?, codigo_externo?, ativa?}` → 201 · 409 `nome_em_uso` · 422 documento inválido (dígitos verificadores).
- `GET /empresas/{id}`, `PATCH /empresas/{id}` (mesmos campos), `DELETE /empresas/{id}` (`contatos.excluir`, só admin na prática: exige também perfil admin) → contatos ficam sem empresa; auditoria.

## 4. Contatos
`Contato` = `{id, codigo (9 dígitos, gerado), nome, email|null, telefone|null (só dígitos, com DDI 55), empresa: {id,nome}|null,
cargo: {id,nome}|null, perfil: {id,nome}|null, codigo_externo|null, recebe_pesquisas: bool, ativo: bool,
situacao: "na_fila"|"aguardando"|"respondeu"|"nao_saiu"|"saiu_da_lista"|"inativo"|"nunca_enviado",
ultimo_envio|null, proximo_envio|null, ultima_nota|null, criado_em}`.
Na etapa 2, sem envios ainda, a situação é `nunca_enviado`, `respondeu` (se houver resposta) ou `inativo`.
- `GET /contatos?busca=&empresa_id=&grupo_id=&responsavel_id=&perfil_id=&ativo=true|false|todos&pagina=` → paginado.
- `POST /contatos` `{nome, email?, telefone?, empresa_id?, cargo_id?, perfil_id?, codigo_externo?, recebe_pesquisas?, ativo?}` → 201.
  Regras: e-mail OU telefone obrigatório; e-mail único na conta (409 `email_em_uso`); telefone com 10–13 dígitos
  (10/11 dígitos ganham 55); limite do plano (402 `limite_do_plano`: "Seu plano permite até N contatos ativos.").
- `GET /contatos/{id}` → `Contato` + `historico: [{tipo: "resposta", data, nota, grupo, comentario, formulario}]`.
- `PATCH /contatos/{id}`, `DELETE /contatos/{id}` (`contatos.excluir`, apaga as respostas dele) → 204.
- `POST /contatos/{id}/link-pesquisa` `{formulario_id?, contexto?: {pedido?, nota_fiscal?, rota?, motorista?, filial?, transportadora?}, assunto?}`
  (`envios.disparar`) → 201 `{link, token, expira_em: null}`: cria um convite individual (sem e-mail) para enviar à mão.

Limites por plano (contatos ativos): essencial 300, profissional 1500, empresa ilimitado, cortesia ilimitado,
teste = do plano do teste. Garantido também no banco.

## 5. Importação de planilha (`importacao.usar`)
- `GET /importacao/modelo?tipo=contatos` → CSV (`;`, UTF-8 com BOM) com as colunas:
  `nome;email;telefone;empresa;documento_empresa;cargo;perfil;grupo;segmento;responsavel;valor_mensal;cliente_desde;codigo_externo;ativo`.
- `POST /importacao/analisar` (multipart `arquivo`: .csv/.xlsx/.xls, até 5 MB / 20.000 linhas) →
  `{id, colunas: [string], mapeamento_sugerido: {coluna_do_arquivo: campo|null}, total_linhas,
  amostra: [{linha, valores}] (10 primeiras), campos: [{chave, rotulo, obrigatorio}]}`.
  Aceita nomes equivalentes (e-mail, email_cliente → email; whatsapp, celular → telefone; razão social → empresa; cnpj → documento_empresa...).
- `POST /importacao/{id}/conferir` `{mapeamento: {coluna: campo}, chave: "email"|"codigo_externo"|"telefone", atualizar_existentes: bool, grupo_id?}` →
  `{prontas: int, com_problema: int, novos: int, atualizados: int, problemas: [{linha, motivo}] (até 500), avisos: [string]}`.
- `POST /importacao/{id}/importar` (mesmo corpo + `ignorar_com_problema: bool`) → `{novos, atualizados, ignorados, problemas}`.
  Tudo ou nada; cria empresas, grupos, segmentos, cargos, perfis e responsáveis que não existem (por nome, sem diferenciar maiúsculas);
  respeita o limite do plano (402 antes de gravar qualquer coisa). A análise fica guardada por 1 hora.

## 6. Formulários (`formularios.ver` / `formularios.editar`)
`Pergunta` = `{id (string curta, estável), tipo, titulo, descricao?, obrigatoria: bool, opcoes?: [string], min?, max?,
rotulo_min?, rotulo_max?, formato? ("texto"|"email"|"telefone"|"numero"), condicao?: {tipo: "grupo", grupos: [..]} | {tipo: "nota", operador: "<="|">=", valor}}`.
Tipos: `nps` (0–10), `csat` (1–5 rostos), `estrelas` (1–5), `escala` (min 0|1, max até 10), `texto_curto` (≤300), `comentario` (≤4000),
`escolha_unica`, `escolha_multipla` (2–30 opções únicas), `sim_nao`, `data`, `quebra_pagina`.
`Tema` = `{cor (#rrggbb), logo_url?, modo: "uma_por_vez"|"paginas", titulo_abertura?, texto_abertura?, texto_botao, titulo_final, texto_final}`.
`Formulario` = `{id, nome, descricao, tipo_principal: "nps"|"csat"|"personalizado" (calculado), perguntas, tema, ativo, publico,
codigo_publico (8 caracteres), padrao_nps: bool, padrao_csat: bool, respostas: int, atualizado_em}`.
- `GET /formularios` → `[Formulario resumido (sem perguntas)]` · `GET /formularios/modelos` → `[{chave, nome, descricao, perguntas, tema}]`.
- `POST /formularios` `{nome, modelo?: chave, perguntas?, tema?}` → 201.
- `GET/PATCH /formularios/{id}` · `POST /formularios/{id}/duplicar` · `DELETE /formularios/{id}` (com respostas: arquiva) ·
  `POST /formularios/{id}/padrao` `{uso: "nps"|"csat"}` · `POST /formularios/{id}/novo-codigo` (invalida o link público antigo).
- Validação (422 com `campos` apontando `perguntas.<indice>.<campo>`): até 60 perguntas; título obrigatório; condição só depois da
  nota principal; opções válidas; limites de faixa; quebras de página no início/fim/repetidas são removidas. Padrão não pode ser
  desativado, excluído nem mudar de tipo (409 `formulario_padrao`).
- Nota principal: 1ª pergunta `nps`; senão a 1ª `csat`/`estrelas`; senão nenhuma (personalizado).
  Grupos: NPS 0–6 `detrator`, 7–8 `neutro`, 9–10 `promotor`; CSAT/estrelas 1–2 `insatisfeito`, 3 `neutro`, 4–5 `satisfeito`.
- Conta nova recebe "Pesquisa NPS" (padrão NPS) e "Satisfação pós-entrega" (padrão CSAT). Modelos: nps_simples, pos_entrega,
  pos_atendimento (CSAT + esforço 1–7), nps_distribuidora (NPS + motivos), pesquisa_rapida (NPS + nome/e-mail), em_branco.

Resultados:
- `GET /formularios/{id}/resultados?de=&ate=` → `{total, nps?: {valor, promotores, neutros, detratores}, csat?: {percentual, media},
  perguntas: [{id, tipo, titulo, respostas, distribuicao?: {valor: qtd}, media?, opcoes?: {opcao: qtd}, textos?: [{texto, data}] (50)}]}`.
- `GET /formularios/{id}/respostas?de=&ate=&pagina=` → paginado `[Resposta]`.
- `GET /formularios/{id}/respostas.csv?de=&ate=` → CSV `;` com Data, Contato, E-mail, Empresa, Canal, Referência, contexto e uma coluna por pergunta.

`Resposta` = `{id, formulario: {id,nome}, contato: {id,nome,email}|null, empresa: {id,nome}|null, canal
("email"|"whatsapp"|"link"|"qr"|"widget"|"api"|"importacao"|"manual"), nota|null, tipo_nota: "nps"|"csat"|null, grupo|null,
comentario (resumo "Pergunta: resposta"), respostas: {pergunta_id: valor}, contexto: {pedido?, nota_fiscal?, rota?, motorista?,
filial?, transportadora?}, referencia|null, criada_em}`.

## 7. Páginas públicas (sem login; limites por IP: abrir 30/min, responder convite 10/min, responder link 5/min)
- `GET /publico/convites/{token}` → `{formulario: {nome, perguntas, tema}, variaveis: {empresa, nome, assunto, referencia},
  ja_respondido: bool}` · 404 `link_invalido`.
- `POST /publico/convites/{token}/responder` `{respostas: {pergunta_id: valor}}` → 201 `{titulo_final, texto_final}` ·
  409 `ja_respondido` ("Você já respondeu esta pesquisa. Obrigado!") · 422 com `campos` por pergunta.
- `GET /publico/formularios/{codigo}` → mesmo formato (sem `ja_respondido`) · 404 se inativo ou não público.
- `POST /publico/formularios/{codigo}/responder` `{respostas, canal?: "link"|"qr"|"widget", referencia?, contexto?}` → 201.
  Um campo `texto_curto` com formato e-mail identifica o contato (se existir na conta). Não aceita a mesma resposta
  (mesmo conteúdo, mesmo IP) duas vezes em 10 minutos (200 silencioso, sem gravar).
- Variáveis nos textos das perguntas e do tema: `{empresa}` (nome da conta), `{nome}` (primeiro nome; vazio remove
  a vírgula e o espaço antes, "Olá, {nome}!" → "Olá!"), `{assunto}` (padrão "o nosso atendimento"), `{referencia}`.
- Validação no servidor: nota na faixa; obrigatórias visíveis respondidas; formatos (e-mail, número, telefone ≥ 8 dígitos,
  data AAAA-MM-DD); opção existente; ao menos uma resposta; respostas de perguntas escondidas pela lógica são descartadas.
- Ao gravar: resposta com nota principal e grupo; convite marcado como respondido; contato identificado recebe `ultima_nota`.
  Efeitos seguintes (plano de ação, alertas, agradecimento) virão nas etapas 3 e 4 por um ponto único "resposta registrada".

## 8. Widget e QR Code (frontend)
- QR Code do link público (`https://<app>/f/{codigo}?canal=qr`), para baixar em PNG e SVG.
- Widget: `<script src="https://<app>/widget.js" data-toqqi="{codigo}" async></script>` → botão flutuante "Avalie-nos"
  que abre a pesquisa numa janela sobreposta (`/f/{codigo}?canal=widget&embed=1`).
- Link com contexto: a tela Compartilhar monta links como `/f/{codigo}?pedido=123&rota=Sul&motorista=João`;
  esses parâmetros vão para `contexto` da resposta.
