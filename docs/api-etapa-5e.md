# Toqqi · Etapa 5e (e-mails: visual guiado, banco de imagens, e-mails do sistema na cor da marca, e-mails enviados)

Mesmas convenções das etapas anteriores: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, `requer(...)`,
listas paginadas `{itens,total,pagina,por_pagina}`, datas ISO 8601, dias de regra em America/Sao_Paulo (`toqqi.core.relogio`),
RLS por conta em toda tabela nova. Reaproveite `modulos/envios/{mensagens,configuracao,servico}.py`, `modulos/imagens/servico.py`
(validação PNG/JPEG pelos bytes, chave aleatória, `/publico/imagens/{chave}`), `core/email.py`, `core/auditoria.py`.

## 0. Decisões desta etapa
- Especificação (Configurações › E-mail): modelos de convite, lembretes e agradecimentos com prévia e e-mail de teste, e banco
  de imagens da conta; agradecimento por grupo com `{nome}`, `{empresa}`, `{nota}` e `{motivo}`; auditoria com "E-mails
  enviados: destinatário, assunto, situação, data e erro, com alerta de falhas".
- **Marcelo (02/10): visual guiado, sem HTML.** A conta escolhe cor de destaque, logo, imagem de topo, assinatura e rodapé num
  formulário; o Toqqi monta o e-mail (o mesmo layout de tabelas de hoje, que funciona no Gmail, Outlook e celular). Os textos
  continuam texto puro com variáveis. Nenhum HTML da conta entra no e-mail.
- E-mails do sistema (confirmação, senha, alertas, resumo semanal, indicação, avisos) passam do azul para o coral da marca
  (design-system: botão `#D63A18` com texto branco, links `#B02F13`).
- O registro de e-mails enviados guarda 90 dias (dado pessoal: o endereço de quem recebeu).

## 1. Banco (migração `0014_emails`, depois da `0013_ia_sob_demanda`)
- `config_envios`: `email_cor text null` (`#RRGGBB`; nulo = a cor do formulário do envio), `email_mostrar_logo boolean not
  null default true`, `email_imagem_topo_id bigint null` (FK `imagens`, `on delete set null`), `email_assinatura text null` (até
  300), `email_rodape text null` (até 500).
- `imagens`: `uso` passa a aceitar `'banco'` (ajuste o CHECK, se houver) e ganha `nome text null` (nome do arquivo enviado,
  limpo, até 120), `largura int null`, `altura int null` (lidos do cabeçalho PNG/JPEG; nulos se não der para ler).
- `emails_enviados`: `id`, `conta_id` (FK `contas` `on delete cascade`), `tipo text` (ver §5), `destinatario citext`, `assunto
  text` (até 300), `situacao text` ('enviado' | 'falhou'), `erro text null` (o texto simples de `email.traduzir_falha`, nunca o
  corpo do provedor), `criado_em timestamptz not null default now()`. Índices `(conta_id, criado_em desc)` e `(conta_id,
  situacao, criado_em desc)`. RLS forçado + política de sempre, grants como as outras tabelas.
- Downgrade desfaz tudo (as imagens `banco` são apagadas antes de voltar o CHECK).

## 2. Visual dos e-mails de pesquisa (convite, lembrete, agradecimento e o e-mail de teste)
### 2.1 Configuração
- `GET /envios/configuracao` ganha `email_cor`, `email_mostrar_logo`, `email_imagem_topo: {id, url, largura, altura} | null`,
  `email_assinatura`, `email_rodape`.
- `PUT /envios/configuracao` aceita `email_cor` (`#RRGGBB`, maiúsculas ou minúsculas, ou nulo), `email_mostrar_logo`,
  `email_imagem_topo_id` (id de uma imagem `banco` da conta, ou nulo; outra → 422 no campo), `email_assinatura` e `email_rodape`
  (texto puro, sem caracteres de controle além de quebra de linha; vazio = nulo; acima do limite → 422 no campo). Auditoria
  `config_envios` como hoje.
### 2.2 Montagem (`mensagens.py`)
- Ordem no cartão de 600 px: faixa de 4 px na cor de destaque no topo do cartão → logo (como hoje, se houver e
  `email_mostrar_logo`) → imagem de topo (se houver: largura total do cartão, `width="544"` e `max-width:100%`, altura
  proporcional, `alt` vazio, sem link) → textos → bloco da nota → assinatura (parágrafos escapados, cor `#4b5563`) → rodapé.
- Rodapé: o `email_rodape` da conta (escapado, quebras de linha viram `<br>`) e, sempre, as duas linhas fixas de hoje ("Você
  recebeu esta pesquisa porque é cliente de {empresa}." e o descadastro).
- Cor de destaque: `email_cor` ou, se nula, a cor do tema do formulário do envio (`tema.cor`); se nenhuma for válida, `#D63A18`.
  Vale para a faixa do topo, o botão "Responder pesquisa" (formulário personalizado) e os links do corpo. Texto do botão: branco
  se o contraste com a cor for ≥ 4,5:1, senão `#111827`. Os botões de nota continuam vermelho/amarelo/verde.
- Versão em texto puro: assinatura e rodapé da conta entram antes das linhas fixas.
- Agradecimento: nova variável `{motivo}` = o comentário do cliente numa linha, cortado em 200 caracteres (vazio sem
  comentário). Os textos por grupo continuam como estão.
- O e-mail de teste (`POST /envios/configuracao/teste`) usa a configuração salva, como hoje.

## 3. Banco de imagens da conta (`configuracoes.gerenciar`)
- `GET /imagens` → `{itens: [{id, url, nome, tipo, tamanho, largura, altura, criada_em, em_uso}], limite: 30}` (só `uso =
  'banco'`, mais novas primeiro; `em_uso` = é a imagem de topo dos e-mails).
- `POST /imagens` (multipart `arquivo`): PNG ou JPEG pelos bytes, até 1 MB → 201 com o item. Tipo ou tamanho errado → 422 no
  campo `arquivo` ("Use uma imagem PNG ou JPG de até 1 MB."); 30 imagens → 409 `limite_imagens` ("O banco de imagens tem até 30
  imagens. Exclua uma para enviar outra.").
- `DELETE /imagens/{id}` → 204; em uso → 409 `imagem_em_uso` ("Esta imagem está no visual dos e-mails. Troque a imagem de
  topo antes de excluir."); de outra conta ou inexistente → 404.
- Auditoria: `imagem_enviada` e `imagem_excluida` (com o nome). Servidas sem login pelo `/publico/imagens/{chave}` de sempre.
- Os logos (conta e formulário) continuam com 300 KB e não aparecem no banco.

## 4. E-mails do sistema na cor da marca
- `core/email._html`: botão com fundo `#D63A18` e texto branco; links e o "copie este endereço" com `#B02F13`. Nada mais muda
  (assinatura "Equipe Toqqi", rodapé de "Minha conta").

## 5. Registro de e-mails enviados e Auditoria › E-mails enviados
- Todo e-mail que sai em nome de uma conta grava uma linha em `emails_enviados`, depois da tentativa: pesquisas
  (`email.enviar_mensagem`: `convite`, `lembrete`, `agradecimento`, `teste`) e do sistema (`email.enviar` ganha os parâmetros
  opcionais `conta_id` e `tipo`; quem chama passa os dois). Tipos do sistema: `confirmacao` (confirmar e-mail), `senha`
  (redefinir senha), `boas_vindas` (usuário criado pela equipe), `alerta_risco` (ação alta), `resumo_semanal`, `pico`
  (reclamações), `indicacao`, `aviso` (`core.avisos.avisar_admins`: webhooks, franquia do WhatsApp, cobrança…), `cobranca`
  (e-mails da assinatura, se houver). Procure todas as chamadas de `email.enviar` e `enviar_mensagem`; e-mail sem conta
  conhecida não é registrado.
- Situação: `enviado` (o provedor aceitou; com `console`/`memory` também) ou `falhou` (com o texto simples do erro). Gravar o
  registro nunca derruba nem atrasa o envio: transação própria (`em_conta(conta_id)`), e falha ao gravar só vai para o log.
- Assunto gravado como saiu (cortado em 300). Nada do corpo.
- `GET /auditoria/emails?de=&ate=&situacao=&tipo=&busca=&pagina=&por_pagina=` (`auditoria.ver`) → página com `itens: [{id,
  tipo, tipo_rotulo, destinatario, assunto, situacao, erro, criado_em}]` (mais novos primeiro; `busca` no destinatário e no
  assunto, sem acento; período padrão: últimos 30 dias, até 90) e `falhas_7_dias: n` (falhas da conta nos últimos 7 dias, sem
  os filtros). Rótulos dos tipos em português ("Convite de pesquisa", "Lembrete", "Agradecimento", "E-mail de teste",
  "Confirmação de e-mail", "Redefinição de senha", "Boas-vindas", "Alerta de risco", "Resumo semanal", "Pico de reclamações",
  "Nova indicação", "Aviso aos administradores", "Cobrança").
- Limpeza: nova tarefa `limpeza` (`python -m toqqi.tarefas limpeza`, também em `tudo`, por último) apaga as linhas com mais de
  90 dias, em lotes; devolve `{emails_apagados}`. (A etapa 5f acrescenta outras limpezas a ela.)

## 6. Site
### 6.1 Configurações › Envios: "Visual dos e-mails"
- Nova seção, perto dos textos do e-mail: cor de destaque (opção "Usar a cor do formulário" ligada por padrão; desligada,
  aparece um seletor de cor com o campo `#RRGGBB` e 6 sugestões, e um aviso quando o texto do botão vai ficar escuro por
  contraste), "Mostrar o logo" (interruptor, com a nota de qual logo vale: o do formulário, senão o da empresa), imagem de topo
  (nenhuma | miniatura da escolhida com "Trocar" e "Remover"), assinatura (área de texto, 300) e rodapé (área de texto, 500,
  com a nota de que as linhas de descadastro entram sempre).
- A prévia do e-mail (`PreviaEmail.vue` / `mensagens.ts`) mostra o visual na hora, para convite, lembrete e agradecimento,
  com a mesma ordem e regras de §2.2 (inclusive a cor de contraste do botão). A prévia por canal do editor de formulários
  (`PreVisualizacao.vue`) também.
- "Enviar e-mail de teste" usa o que está salvo: com mudanças não salvas, o botão fica desabilitado com a dica "Salve as
  mudanças para enviar o teste.".
### 6.2 Banco de imagens
- "Trocar"/"Escolher imagem" abre um `Modal` com o banco: grade de miniaturas (nome, dimensões, "Em uso"), "Enviar imagem"
  (PNG/JPG até 1 MB; a dica "Para o topo do e-mail, use 1200 × 400 px"), escolher e excluir (confirmação; em uso → a mensagem da
  API). Mostra "X de 30 imagens". Teclado: as miniaturas são botões; foco volta ao gatilho ao fechar.
### 6.3 Auditoria › E-mails enviados
- A tela de Auditoria ganha abas "Atividades" (a de hoje) e "E-mails enviados" (rota `/auditoria/emails` ou `?aba=emails`).
- Com `falhas_7_dias > 0`: `Alerta` de atenção "{n} e-mails falharam nos últimos 7 dias." com o botão "Ver só as falhas" (filtra
  situação = falhou e os últimos 7 dias).
- Filtros: período (padrão 30 dias), situação, tipo, busca; tabela (Data, Tipo, Destinatário, Assunto, Situação com etiqueta,
  Erro) e, no celular, cartões; paginação; estado vazio. Nota curta: "Enviado = o provedor aceitou o e-mail. Devoluções da caixa
  de quem recebe não aparecem aqui." e "Guardamos os últimos 90 dias."
### 6.4 Ajuda e Política
- Ajuda (`api/toqqi/modulos/ajuda/conteudo.json`): atualizar os tópicos de envios (visual, banco de imagens, e-mail de teste)
  e auditoria (e-mails enviados).
- Política de privacidade: citar o registro de e-mails enviados (destinatário, assunto, situação; 90 dias). Mudança relevante:
  `VERSAO_DOCUMENTOS` = 3 nos dois lugares (API e site), vigente na data da entrega.

## 7. Testes
- API: PUT do visual (validações, imagem de outra conta, nulos), montagem (ordem, cor do formulário vs. da conta vs. padrão,
  contraste do texto do botão, escapes de assinatura e rodapé, sem HTML da conta, texto puro), `{motivo}`, banco de imagens
  (tipos, 1 MB, 30, em uso, RLS, auditoria), registro de e-mails (pesquisa e sistema, enviado e falhou, falha ao gravar não
  derruba, sem conta não grava), `GET /auditoria/emails` (filtros, busca sem acento, `falhas_7_dias`, permissão), tarefa
  `limpeza`, cor dos e-mails do sistema, migração e downgrade.
- Site (vitest): seção do visual (cor do formulário ou própria, aviso de contraste, logo, imagem, assinatura, rodapé, dica do
  teste com mudanças não salvas), prévia com o visual, modal do banco (enviar, escolher, excluir em uso, limite), aba de e-mails
  (alerta e "Ver só as falhas", filtros, tabela, cartões no celular, vazio, paginação).

## 8. Ajustes na construção e na revisão (02/10)
- `email_cor` é guardada e devolvida em maiúsculas (`#RRGGBB`; CHECK `^#[0-9A-F]{6}$`).
- Assinatura e rodapé: na API, caracteres de controle e de direção do texto são **removidos** (tab vira espaço, CRLF vira
  LF) e o limite conta depois da limpeza; texto com mais de 4× o limite é recusado. O site é mais estrito: recusa tab e
  caracteres invisíveis com a mensagem no campo.
- `{motivo}`: corte seco em 200 caracteres, sem reticências.
- `GET /auditoria/emails` também devolve `periodo: {de, ate}`; `por_pagina` padrão 50 (até 200); período acima de 90 dias
  ou `de` depois de `ate` → 422 no campo `de`. `falhas_7_dias` conta de 00:00 de (hoje − 6), horário de São Paulo, até
  agora — a mesma janela do "Ver só as falhas".
- **Privacidade:** o registro de e-mails grava `assunto_no_log` quando o envio tem um (hoje só o aviso de indicação, que
  fica "Nova indicação"), para excluir a indicação a pedido da pessoa não deixar o nome dela no registro.
- "Você já tem uma conta no Toqqi" entra como `confirmacao` na conta de quem já existe. `boas_vindas` e `cobranca` existem
  na API, mas nenhum e-mail sai com eles hoje (usuário criado pela equipe e a assinatura não mandam e-mail): o filtro do site
  não os oferece.
- E-mails de pesquisa não têm outros links no corpo (`{link}` só vale no WhatsApp): a cor de destaque vale para a faixa e o
  botão "Responder pesquisa". Nos e-mails do sistema, o endereço do "copie este endereço" virou link `#B02F13`.
- Imagem de topo: `height` com teto de 1088 px (o dobro da largura) na API e na prévia, para imagem de proporção absurda.
- Texto puro do agradecimento ganhou a linha "Você recebeu esta pesquisa porque é cliente de {empresa}." (faltava antes da 5e).
- Corpo grande demais para antes do login: `POST /imagens` (1 MB + 64 KB), logos da conta e do formulário (300 KB + 64 KB) e
  `POST /importacao/analisar` (5 MB + 64 KB) entram no limite de corpo (413 `pedido_grande_demais`); um arquivo pouco acima
  do limite ainda chega à rota e recebe a mensagem de sempre.
- Índice `emails_enviados (criado_em)` para a `limpeza` não percorrer a tabela inteira.
- Prévia: o bloco da nota mostra o título da pergunta principal (com `{empresa}`/`{nome}`) e os rótulos dela (CSAT também),
  com as cores do e-mail (`#dc2626`, `#d97706`, `#16a34a`, número em branco). Excluir no banco a imagem escolhida e ainda não
  salva volta à imagem salva (ou a nenhuma).
- Site: período 7, 30 ou 90 dias ou "Escolher as datas" (até 90 dias, até hoje); "Ver só as falhas" vira "Ver todos os
  e-mails"; o aviso de contraste só aparece com cor própria da conta; a imagem enviada ao banco não fica escolhida sozinha;
  o botão "Enviar e-mail de teste" ficou no cabeçalho da página (saiu o "salvar e enviar").
