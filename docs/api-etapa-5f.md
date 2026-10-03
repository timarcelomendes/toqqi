# Toqqi · Etapa 5f (dados da conta: exportação, zona de risco, auditoria, registros de acesso, exclusão automática)

Mesmas convenções das etapas anteriores: base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, `requer(...)`, datas
ISO 8601, dias de regra em America/Sao_Paulo (`toqqi.core.relogio`), RLS por conta em toda tabela nova (exceção no §1). CSV como
os de hoje (`relatorios.regras.gerar_csv`/`num`/`data_br`, `formularios.servico._celula`): `;`, UTF-8 com BOM, CRLF, datas de São
Paulo, vírgula decimal, "Sim"/"Não", proteção contra fórmula, rótulos das telas. Módulo novo `modulos/dados/`.

## 0. Decisões desta etapa
- Especificação (zona de risco, auditoria, LGPD) e **Marcelo**: exclusão **automática** 90 dias depois do fim do período pago
  (ou do teste não assinado), com e-mail aos administradores 7 dias antes; backup fora. **Decididas aqui (Marcelo pode mudar):**
  - Zona › Respostas apaga NPS **e** personalizadas (tudo menos CSAT), inclusive arquivadas, manuais e importadas. "Manter CSAT":
    ficam, sem o contato (e sem a empresa, em Recomeçar) e sem cópia de nome, e-mail ou telefone; convites sem contato (links de
    CSAT da integração) seguem respondíveis. Recomeçar também apaga indicações e ofertas; responsáveis e cadastros ficam.
  - Exportação só para o administrador, também com a conta encerrada; sem imagens, sem os pareceres da IA do painel e
    dos relatórios e sem registros de acesso (a análise da IA de cada resposta, "Sentimento" e "Resumo da IA", vai em
    `respostas.csv`, como no CSV de Respostas).
  - Registro de acesso: entradas e tentativas, cadastro, pedido de acesso, senha trocada pelo link e envios públicos de resposta
    e indicação; abrir páginas e chamadas da sessão não; só o IP (a porta de origem não chega ao Toqqi).
  - Assinatura ativa (mesmo atrasada há meses) impede a exclusão (só entra no log); cobranças, aceites e auditoria saem junto.
  - Freios: até 20 exclusões por dia (contadas pelos eventos do dia, não pela rodada), nenhuma conta com menos de 100
    dias, 7 dias de aviso também pelo relógio do banco, aviso que chegou a um administrador e `EXCLUSAO_AUTOMATICA`
    (`ligada` age; `simular` só conta e loga; qualquer outro valor, como "desligada", vale `simular` com um aviso no log,
    sem impedir a API de subir). Padrão do código: `simular`; no `render.yaml`: `ligada` (com os freios, nenhuma conta de
    hoje se qualifica antes de janeiro de 2027; trocar para `simular` suspende).
  - IP pelo `CF-Connecting-IP` (sem conferir faixas da Cloudflare); modelo do WhatsApp só com SAIR; APAGAR em qualquer caixa.

## 1. Banco (migração `0015_dados_conta`, depois da `0014_emails`)
- `registros_acesso`: `id bigserial`, `criado_em timestamptz not null default now()`, `evento text not null` (CHECK 'login' |
  'login_falhou' | 'cadastro' | 'pedido_acesso' | 'senha_redefinida' | 'resposta' | 'indicacao'), `conta_id bigint null`,
  `usuario_id bigint null`, `item_id bigint null` (resposta ou indicação), `ip text null` (até 64) — **sem FK**: sobrevive à
  exclusão do usuário e da conta. Índice `(criado_em)`. RLS ENABLE + FORCE sem a política de sempre: `gravar` FOR INSERT WITH
  CHECK (`app_sistema() OR conta_id = app_conta()`), `ler` FOR SELECT e `apagar` FOR DELETE USING (`app_sistema()`), nenhuma
  de UPDATE. Papel da aplicação: SELECT, INSERT, DELETE e `REVOKE UPDATE` (os privilégios padrão da 0001 dariam UPDATE).
- `contas`: `exclusao_avisada_para date null` e `exclusao_avisada_em timestamptz null` (CHECK os dois nulos ou os dois não).
- Índices parciais `WHERE <coluna> IS NOT NULL`, para os SET NULL/CASCADE não varrerem a tabela por linha apagada: `envios
  (resposta_id)`, `indicacoes (resposta_id)`, `indicacoes (indicador_contato_id)`, `indicacoes (indicador_empresa_id)`, `ofertas
  (contato_id)`, `convites (empresa_id)`. Downgrade desfaz tudo.

## 2. Exportação
### 2.1 Todos os dados: `GET /conta/exportacao.zip` (`requer_admin`; vale com a conta encerrada, sem `liberada`)
- `application/zip` `toqqi-{slug da conta}-{AAAA-MM-DD}.zip` (slug como o do CSV do formulário; vazio → `conta`) com
  `LEIA-ME.txt` (quando foi gerado, o que é cada arquivo, a convenção, o que não vai) e um CSV por assunto, em ordem de id:

| Arquivo | Colunas |
|---|---|
| `empresas.csv` / `responsaveis.csv` / `cadastros.csv` | ID, Nome, CPF/CNPJ, Grupo, Segmento, Responsável, Valor mensal, Cliente desde, Código externo, Ativa, Criada em / ID, Nome, Função, E-mail, Criado em / Tipo (Grupo, Segmento, Perfil de contato, Cargo), Nome, Criado em |
| `contatos.csv` | ID, Código, Nome, E-mail, Telefone, ID da empresa, Empresa, Cargo, Perfil, Código externo, Recebe pesquisas, Ativo, Última nota, Último envio, Próximo envio, Criado em |
| `formularios.csv` | ID, Nome, Descrição, Tipo (NPS, CSAT, Personalizado), Ativo, Público, Padrão, Arquivado, Link público, Criado em, Atualizado em, Perguntas (JSON), Tema (JSON) |
| `respostas.csv` / `respostas-perguntas.csv` | ID, Formulário, ID do contato, ID da empresa, ID do convite, as colunas de `respostas.servico.CABECALHO_CSV`, Data de entrada (todas, inclusive arquivadas) / ID da resposta, Formulário, ID da pergunta, Pergunta (título com as variáveis, como no CSV do formulário), Resposta (`formatar_valor`): uma linha por pergunta respondida |
| `planos-de-acao.csv` | ID, Título, Descrição, Prioridade, Situação, Prazo, Origem, Categoria, Tipo, Nota, ID da resposta, ID da empresa, Empresa, ID do contato, Contato, Responsável, Resolução, Passos da IA (" \| "), Criada por, Criada em, Iniciada em, Concluída em, Concluída por |
| `convites.csv` / `envios.csv` | ID, Data, Formulário, ID do contato, Contato, E-mail, ID da empresa, Canal, Assunto, Referência, Evento, os 6 campos de contexto, Lembretes enviados, Respondido em / ID, Data, ID do convite, ID do contato, Contato, Para, Canal, Tipo, Origem, Situação, Erro, Lembrete, Enviado em, Enviado por |
| `descadastros.csv` / `cobrancas.csv` | E-mail, Telefone, Motivo, Origem, Data, Registrado por / Vencimento, Valor, Situação, Forma, Pago em (do ambiente atual do Asaas) |
| `indicacoes.csv` / `ofertas.csv` | ID + as colunas de `crescimento.indicacoes.CABECALHO_CSV` / ID, Data, ID da empresa, Empresa, Contato, Lista, Canal, Texto, Feita por, Resultado, Valor, Resultado em |
| `equipe.csv` / `aceites-dos-termos.csv` | ID, Nome, E-mail, Cargo, Telefone, Perfil, Situação, E-mail confirmado, Último acesso, Criado em, Recebe resumo semanal, Recebe alertas / Nome, E-mail, Versão, Aceito em, Origem, Retirado em |
| `auditoria.csv` / `emails-enviados.csv` | Data, Evento (rótulo), Código, Grupo, Gravidade, Usuário, Detalhe (JSON), IP / Data, Tipo, Destinatário, Assunto, Situação, Erro |
| `configuracoes.csv` | Seção, Item, Valor: dados da empresa; plano e situação; segurança e domínios; os campos de `GET /envios/configuracao`; planos de ação; crescimento; IA; permissões de Gestor e Consulta; webhooks (endereço, eventos, ativo); WhatsApp (número, nome verificado, modelo, ativo); chave (só o prefixo) |

- **Nunca** vão: `senha_hash`, `token_hash`, `token_semente`, hashes e segredos cifrados (chave, webhooks, WhatsApp),
  `teams_webhook`, `foto_url`, `ip_hash`, `wamid`, ids do Asaas, IP e navegador dos aceites, imagens, os pareceres da IA
  do painel e dos relatórios (`ia_pareceres`). A análise da IA de cada resposta ("Sentimento", "Resumo da IA" de
  `CABECALHO_CSV`) vai em `respostas.csv`: é dado da resposta, como no CSV de Respostas.
- Sem tudo na memória: zip em arquivo temporário (`ZIP_DEFLATED`), CSV escrito direto na entrada (`zf.open(nome, "w",
  force_zip64=True)` + `TextIOWrapper`), consultas com `yield_per(2000)`, `FileResponse` que apaga o arquivo depois (e na falha);
  transação REPEATABLE READ somente leitura (`em_conta(conta, leitura=True)`, antes do `set_config`). Uma por vez por conta
  (`pg_try_advisory_xact_lock(hashtextextended('exportacao:{conta}', 0))` falso → 409 `exportacao_em_andamento`: "Já tem uma
  exportação sendo gerada nesta conta. Aguarde terminar."); 5/hora por usuário. Auditoria `exportacao_conta` (info) `{arquivos,
  linhas: {arquivo: n}, bytes}` em transação própria, depois de gerar (a da leitura é somente leitura).
### 2.2 "Exportar CSV" em Contatos e Empresas (`requer("contatos.ver", "painel.exportar")`, como os outros CSV)
- `GET /contatos.csv` e `GET /empresas.csv`: filtros, padrões e ordem de `GET /contatos`/`GET /empresas` (condições numa função
  comum), sem paginação; `contatos-{data}.csv`/`empresas-{data}.csv`; auditoria `exportacao_csv` `{lista, linhas}` (sem a busca).
  Contatos: Código, Nome, E-mail, Telefone, Empresa, Cargo, Perfil, Código externo, Recebe pesquisas, Ativo, Situação (rótulos
  de `SITUACOES_CONTATO` do site), Último envio, Próximo envio, Última nota, Criado em. Empresas: Nome, CPF/CNPJ, Grupo,
  Segmento, Responsável, Valor mensal, Cliente desde, Código externo, Ativa, Contatos, Criada em.

## 3. Zona de risco (`requer("zona_risco.usar")`: só administrador)
- `GET /conta/zona-de-risco` → `{opcoes: {respostas: {respostas, acoes_sem_vinculo}, contatos: {contatos, respostas, convites,
  envios, csat_sem_contato}, tudo: {as de contatos + empresas, acoes, indicacoes, ofertas}}, mantidos: {csat, descadastros,
  usuarios, formularios}}`. `POST` `{opcao: "respostas" | "contatos" | "tudo", confirmacao}` → 200 `{opcao, apagados,
  mantidos}`; confirmação diferente de APAGAR (sem espaços nas pontas, qualquer caixa) → 422 no campo ("Digite APAGAR para
  confirmar."); outra em andamento → 409 `zona_em_andamento`; tempo esgotado → 503 `zona_indisponivel` ("Não deu para apagar
  agora e nada foi apagado. Tente de novo em alguns minutos."). Limite 5/hora por usuário. Cumulativo, comandos por conjunto com
  `conta_id` explícito além do RLS, nesta ordem:

| Opção | Apaga | E o que fica |
|---|---|---|
| `respostas` | respostas com `tipo_nota` diferente de 'csat' (NPS e personalizadas, inclusive arquivadas, manuais e importadas) | ações, envios e indicações perdem o vínculo (SET NULL); convites continuam; `contatos.ultima_nota` recalculada em lote (regra de `atualizar_ultima_nota`) |
| `contatos` | o de cima + todos os `envios`, os `convites` com contato, `importacoes`, `eventos_idempotencia`, os `emails_enviados` de convite, lembrete, agradecimento, alerta_risco e indicacao e, por último, os `contatos` | antes de apagar os contatos, as CSAT ficam com `contato_id` nulo e ações, ofertas e indicações perdem o contato |
| `tudo` (Recomeçar do zero) | o de cima + `acoes`, `indicacoes`, `ofertas` e `empresas` | CSAT e convites sem contato ficam sem empresa |

- Em todas, também `ia_pareceres`, `alertas_pico` e `webhook_entregas`. Sempre fica: usuários, configurações (inclusive webhooks,
  WhatsApp e chave), formulários, imagens, responsáveis, cadastros, **descadastros**, auditoria, CSAT (nota, comentário, temas,
  análise, contexto, referência, datas), convites sem contato (o link segue respondível), uso de IA e WhatsApp, assinatura.
- Uma transação (tudo ou nada): `pg_try_advisory_xact_lock('zona_risco:{conta}')` (ocupada → 409), linha de `config_envios`
  travada (a do robô e dos lembretes), `SET LOCAL statement_timeout = '120s'` (estourou → desfaz, 503); com os índices do §1,
  5.000 contatos e 50.000 respostas saem em segundos. `apagados` = `rowcount`; auditoria `zona_risco` (atencao) `{opcao,
  apagados, mantidos}` na mesma transação; nada vai para webhooks nem e-mail. Ids não voltam (sequências de todas as contas).

## 4. Auditoria
- `GET /auditoria` já tem período, gravidade e busca; falta o **grupo**. `core.auditoria.GRUPOS`, nesta ordem, cada evento de
  `ROTULOS` em exatamente um: `acesso` "Acesso e segurança" (login_*, cadastro_conta, senha_*, sessao_encerrada,
  seguranca_alterada, termos_*); `equipe` "Equipe e permissões" (usuario_criado/alterado/bloqueado, permissoes_alteradas);
  `configuracoes` "Configurações" (config_*, dados_empresa_alterados, logo_*, formulario_padrao/arquivado, imagem_enviada,
  ia_analisar_recentes); `envios` "Envios e descadastros" (envio_*, lembretes_automaticos, descadastro*); `dados` "Importações,
  edições e exportações" (importacao*, resposta_editada, indicacao_registrada/atualizada, exportacao_*); `exclusoes` "Exclusões
  definitivas" (todo `*_excluido(a)` menos os globais `conta_excluida*`, e zona_risco); `integracoes` "Integrações" (chave_*,
  webhook_* menos webhook_excluido, whatsapp_*); `assinatura` "Assinatura e conta" (o resto, com exclusao_avisada e os globais).
  `GET /auditoria?grupo=` (outra chave → 422), `grupo` em cada item e `GET /auditoria/grupos` → `[{chave, rotulo}]`.
- Obrigatórios que **não** eram gravados (os outros da especificação já são): `envio_automatico` "Pesquisas enviadas pelo envio
  automático" (info), em `automacao.robo_conta`, na mesma transação, quando agendou algo ou foi "executar agora" (com o
  `usuario_id`) `{agendados, ignorados, executado_agora}`, e `lembretes_automaticos` "Lembretes enviados automaticamente", igual,
  em `lembretes_conta`; `chave_regerada` "Chave de integração gerada de novo (a anterior parou de valer)" (atencao) `{prefixo,
  prefixo_anterior}`; `webhook_criado`, `webhook_alterado` (`{webhook_id, campos}`; novo segredo = `segredo`), `webhook_excluido`
  (atencao, `{webhook_id, url}`); `exportacao_conta`, `exportacao_csv`, `zona_risco`, `exclusao_avisada` "Aviso de exclusão da
  conta enviado" e os globais `conta_excluida_automatica` "Conta excluída automaticamente" e `exclusao_automatica` "Rotina de
  exclusão de contas encerradas".

## 5. Registros de acesso (Marco Civil da Internet, art. 15: data, hora e IP, por 6 meses, em sigilo)
- `core/acessos.registrar(s, evento, *, conta_id, usuario_id=None, item_id=None)`: INSERT sem `RETURNING` (o RLS não deixa ler),
  IP de `ip_cliente` (§7), na transação do evento: `login`; `login_falhou` (senha errada, e-mail não confirmado, acesso pendente
  ou bloqueado; e-mail desconhecido → sem conta nem usuário, transação própria em modo sistema; nunca o e-mail digitado);
  `cadastro`; `pedido_acesso` (quando cria o usuário); `senha_redefinida` (pelo link); `resposta` (convite e link público,
  `item_id` = resposta); `indicacao` (pública, `item_id` = indicação; a rota passa a mandar o IP).
- Não entram páginas, imagens, descadastro, rotas da chave, avisos da Meta/Asaas e chamadas da sessão (o login identifica a
  sessão; a auditoria guarda o IP de cada ação). Nenhuma tela lê: só a equipe técnica, por SQL em modo sistema, para ordem
  judicial (arts. 10 e 15). A `limpeza` apaga o que passou de 184 dias (6 meses cheios), em lotes → `acessos_apagados`.

## 6. Exclusão automática das contas encerradas (passo diário da tarefa `limpeza`)
- Encerrada = `situacao` 'teste_expirado' ou 'cancelada', sem assinatura ativa (`primeiro_vencimento` nulo e nenhuma 'ativa' em
  `assinaturas`, de qualquer ambiente) e `regras.liberada(conta)` falso. Nunca: cortesia, ativa, atrasada, teste ou com assinatura
  ativa; quem assinou e não paga só entra no log (`em_atraso_90_dias`: `atrasada_desde` antes de hoje − 90).
- Fim do serviço = o mais tarde entre `teste_ate` e o início do dia seguinte ao `pago_ate` (sem os dois → nunca, `sem_data`);
  `encerrada_em` = o dia (São Paulo) do fim; `prevista` = `encerrada_em` + 90 dias. Funções puras em `assinatura/regras.py`:
  `encerramento(conta) -> (encerrada_em, prevista) | None` e `exclusao_em(conta)`.
- Aviso, uma vez por encerramento: `exclusao_avisada_para` nulo ou menor que `prevista` e hoje ≥ `prevista` − 7 → `data` =
  max(`prevista`, hoje + 7), grava `exclusao_avisada_para = data`, `exclusao_avisada_em = now()`, auditoria `exclusao_avisada`
  (atencao) `{exclusao_em, encerrada_em, admins}` e `avisar_admins` (tipo `aviso`) "Sua conta no Toqqi será excluída em
  dd/mm/aaaa": encerrada desde quando, tudo será excluído, como baixar uma cópia (Configurações › Dados da conta) e que assinar
  um plano cancela; botão "Baixar os dados".
- Exclusão: `exclusao_avisada_para` ≥ `prevista`, hoje ≥ `exclusao_avisada_para` **e**, pelo relógio do banco, aviso com 7 dias
  (`(exclusao_avisada_em AT TIME ZONE 'America/Sao_Paulo')::date <= (now() AT TIME ZONE 'America/Sao_Paulo')::date - 7`) e
  conta criada há 100 dias (`criada_em <= now() - interval '100 days'`). Em modo sistema, travada e conferida de novo:
  - o aviso só vale **entregue**: um e-mail da conta em `emails_enviados` com `tipo = 'aviso'`, `situacao = 'enviado'`, o
    assunto do aviso ("Sua conta no Toqqi será excluída em …") e `criado_em >= exclusao_avisada_em`. Sem ele (o provedor
    falhou) e com algum administrador ativo, o aviso é desfeito (`exclusao_avisada_para`/`_em` nulos) e a próxima rodada
    avisa de novo (data = max(`prevista`, hoje + 7)): `adiadas`. Sem nenhum administrador ativo (ninguém a avisar), exclui
    depois dos 7 dias sem o e-mail, com `admins: 0` no aviso (`exclusao_avisada`) e no global da exclusão;
  - assinaturas no Asaas que não dá para conferir: cliente no Asaas (`asaas_cliente_id`) sem chave do mesmo ambiente (sem
    chave, ou a de outro ambiente) → `adiadas` (o log leva só o id); exceção: cliente de **sandbox** com a chave de
    **produção** segue (as de sandbox são só de teste; a decisão da 5a é que a troca para produção as cancela);
  - `assinaturas.remover_vivas_no_asaas` (falhou → amanhã), `apagar_conta(s, conta_id)` (extraída de
    `plataforma.excluir_conta`, que passa a usá-la, com as tabelas das etapas 3b–5e) e o global `conta_excluida_automatica`
    `{conta_id, situacao, encerrada_em, avisada_em, exclusao_em, admins}` (`admins`: administradores ativos na hora; 0 =
    ninguém a avisar), sem dado pessoal (o log idem). Ficam `registros_acesso` e os eventos globais.
- Rodada: na `limpeza`, a partir das 9h, uma vez por dia (já há `exclusao_automatica` de hoje → pula); conta e loga; `simular`
  (padrão do código; também qualquer valor de `EXCLUSAO_AUTOMATICA` que não seja `ligada`, com um aviso no log quando não é
  `simular`) para aí; `ligada` age (das mais antigas). Limites **do dia** (São Paulo), contados pelos eventos já gravados hoje
  e não pela rodada: avisos = 100 − `exclusao_avisada` de hoje; exclusões = 20 − `conta_excluida_automatica` de hoje. Uma
  rodada que caiu no meio (sem o evento do dia) roda de novo na próxima chamada sem passar do limite; apagar o evento do dia
  também só faz rodar de novo. Cada aviso e cada exclusão na sua transação e no seu try/except: um erro numa conta vai para o
  log só com o id e o tipo do erro, a conta conta em `adiadas` e a rodada segue com as outras (e termina, com o evento do
  dia). `adiadas`: o que ficou para outro dia (passou do limite, erro, aviso que não chegou, Asaas sem conferência ou fora do
  ar). No fim, o global `exclusao_automatica` `{modo, avisadas, excluidas, adiadas, em_atraso_90_dias, sem_data}`, devolvido
  em `encerradas`; rodadas simultâneas não repetem nada. Pela linha de comando (`python -m toqqi.tarefas limpeza`), o log sai
  como na API (`core.logs.configurar`: INFO, mesmo formato).
- `exclusao_em(conta)` = `exclusao_avisada_para` enquanto vale (≥ `prevista`, ainda encerrada), senão nulo: vai em
  `conta.cobranca` (login e `/eu`) e na lista da Plataforma.

## 7. IP do cliente atrás do proxy do Render
- Hoje `--forwarded-allow-ips "*"` faz o uvicorn usar o **primeiro** endereço do `X-Forwarded-For`, que no Render chega como
  "o que o cliente mandou, cliente, borda da Cloudflare": qualquer um troca o IP do limite, da auditoria, das sessões e do
  aceite. A Cloudflare, na frente do Render, **sobrescreve** `CF-Connecting-IP` com o IP real. Fontes:
  [Render e X-Forwarded-For](https://rohitpaulk.com/articles/render-rails-remote-ip.html),
  [cabeçalhos no Render](https://github.com/arcjet/arcjet-js/issues/3899).
- Config `IP_CLIENTE_CABECALHO` (vazio = endereço da conexão, como em desenvolvimento e testes; Render: `CF-Connecting-IP`).
  Middleware ASGI `IpDoCliente` (`core/requisicao.py`), o mais externo, troca `scope["client"]` por `(ip, 0)`: cabeçalho com
  **um** IP válido (`ipaddress.ip_address`, até 45 caracteres; IPv4 mapeado vira IPv4; forma canônica) → ele; senão o endereço da
  conexão (aviso no log uma vez). Nunca lê `X-Forwarded-For` nem `X-Real-IP`; quem lê `request.client.host` recebe o IP certo.
- Chave do limite: `rate_limit.chave_ip(request)` → `ip:{IPv4}` ou, em IPv6, o prefixo /64 (`ip6:2001:db8:1:2::/64`), no lugar
  de `get_remote_address` (Limiter, `limite_por_usuario`, `limite_por_chave`); os registros guardam o endereço inteiro.
  `render.yaml`: `--no-proxy-headers` no lugar de `--proxy-headers --forwarded-allow-ips "*"`, `IP_CLIENTE_CABECALHO:
  CF-Connecting-IP` e `EXCLUSAO_AUTOMATICA: ligada` (também no cron comentado); README da API.

## 8. WhatsApp: "responda SAIR"
- Já existe (3b): "SAIR", "PARAR", "STOP" ou "CANCELAR" no webhook da Meta descadastram o telefone na conta do número, com
  confirmação; o modelo sugerido no site já traz o rodapé "Para não receber mais pesquisas, responda SAIR.". Variações: mensagem
  inteira normalizada (sem acento, minúsculas, só letras, números e espaços simples), até 40 caracteres, igual a: sair, sair da
  lista, quero sair, parar, pare, stop, cancelar, descadastrar, nao quero mais, nao quero mais receber, nao quero receber, nao
  quero receber mais; também resposta de botão (`button.text`, `interactive.button_reply.title`; ex.: a resposta rápida "Não
  quero receber" de um modelo). Outra mensagem é ignorada, sem resposta.
  `modelo.conferir` exige a palavra SAIR (inteira, qualquer caixa) no corpo ou no rodapé; sem ela → 422 "O modelo precisa dizer
  como parar de receber, por exemplo no rodapé: “Para não receber mais pesquisas, responda SAIR.”".

## 9. Correções pequenas
- Importação de contatos: "Será criada 1 empresa: X." / "Serão criadas 20 empresas: …" (grupo, segmento, cargo, perfil e
  responsável no masculino); até 5 nomes, o último depois de " e " ("A, B e C."); mais → "A, B, C, D, E e mais 15." (um ponto).
  Importação de respostas (`_linhas_texto`): "(linha 7)", "(linhas 7, 9 e 12)"; mais de 10 → os 10 primeiros "e mais 4".
- `teste_ate` do cadastro (`acesso.servico.cadastrar`), da Plataforma (`criar_conta`) e do "+14 dias" (`estender_teste`, hoje com
  `now()` do banco) usa `relogio.agora()`, como as regras que o leem; tokens e sessões seguem no relógio real.

## 10. Site
- **Configurações › Dados da conta** (`/configuracoes/dados-da-conta`, `meta.admin`; item "Dados da conta", ícone
  `DatabaseBackup`, no `NavConfiguracoes` só para administrador; em `ROTAS_LIVRES` do aceite; API em `web/src/api/etapa5f.ts`):
  - "Exportar todos os dados" ("Um arquivo .zip com uma planilha (CSV) por assunto. Senhas e chaves não vão."): "Baixar todos
    os dados" (`baixarArquivo`), ocupado com "Gerando o arquivo… pode levar até um minuto." (`aria-live`); 409/429 → `Alerta`.
  - "Zona de risco" (cartão com borda de erro): rádios (`fieldset`/`legend`) "Respostas", "Contatos" e "Recomeçar do zero", com
    o que apagam e as contagens do GET ("Apaga 1.234 respostas NPS e de formulários personalizados, inclusive arquivadas. 56
    planos de ação ficam sem o vínculo."), e "Sempre fica: usuários, configurações, formulários, {csat} respostas CSAT e a lista
    de descadastro ({d})."; "Apagar…" (perigo) desabilitado se a opção não apaga nada. Confirmação (`Modal` alertdialog, como
    `ModalExcluirConta.vue`): "Apagar {opção}?", `Alerta` "Isso não tem volta" com as contagens e o link "Baixar todos os dados
    antes", campo "Para confirmar, digite APAGAR" (sem autocompletar nem corretor), "Apagar para sempre" só com APAGAR; sucesso
    → "Pronto: apagamos {resumo}." e relê as contagens; erro → mensagem da API; foco volta ao gatilho.
- Contatos e Empresas: "Exportar CSV" (ícone `Download`) na barra de filtros, com `contatos.ver` e `painel.exportar`, levando os
  filtros da aba (no celular só o ícone, com `aria-label`). Auditoria › Atividades: `Selecao` "Grupo" (`/auditoria/grupos`,
  "Todos") entre Gravidade e Buscar; "Limpar filtros" limpa o grupo. Guia do WhatsApp: o rodapé com SAIR é obrigatório.
- Aviso do topo com `cobranca.exclusao_em`: admin — "Os dados desta conta serão excluídos em dd/mm/aaaa. Baixe uma cópia ou
  assine um plano." ("Baixar os dados", "Escolher plano"); demais — "… Fale com o administrador da conta."; Plataforma: selo.
- Ajuda (`conteudo.json`): `configuracoes` (seção nova "Dados da conta: exportar tudo e zona de risco"), `contatos` (exportar
  CSV), `equipe` (grupos e eventos da Auditoria), `assinatura` (90 dias, aviso, assinar cancela), `envios` e `integracoes` (SAIR).
- Política (`privacidade.ts`): registro de acesso em "Quais dados tratamos" (usuários: entradas, tentativas, cadastro, pedido de
  acesso e troca de senha; quem responde: envio da resposta ou indicação; data, hora e IP); "Por quanto tempo guardamos" sem os
  `[a confirmar]` de cancelamento, teste e acesso (90 dias depois do fim do período pago ou do teste, aviso 7 dias antes,
  exclusão definitiva e automática de tudo — auditoria, cobranças e aceites valem "enquanto a conta existir" —, registros de
  acesso por 6 meses, à parte, mesmo depois de excluídos o usuário ou a conta); "Como protegemos": acesso fora das telas, só a
  equipe técnica, para ordem judicial; "Seus direitos": portabilidade em Dados da conta. Termos (`termos.ts`): teste e "Fim do
  contrato" com as mesmas regras. `VERSAO_DOCUMENTOS` = 4 nos dois lugares; `VIGENTE_DESDE` = dia da entrega.
- Tudo no celular (390 px, sem rolagem lateral), claro e escuro, pelo teclado, sem erros no console.

## 11. Testes
- Exportação: arquivos e cabeçalhos exatos; convenção do CSV; ids que batem; nenhum segredo (valores reais de `senha_hash`,
  `token_hash`, `token_semente`, hash da chave, segredos cifrados, `teams_webhook`, `ip_hash`); encerrada exporta; gestor 403;
  409; 429; auditoria; só a própria conta; 5.000 contatos e 50.000 respostas em < 30 s e < 64 MB (`tracemalloc`); CSV = a lista.
- Zona: GET = `apagados`; por opção, cada tabela da conta antes e depois conforme o §3 (CSAT sem contato e sem empresa, convites
  sem contato ainda respondem, descadastros intactos); `ultima_nota`; outra conta intacta; falha forçada no meio → nada muda;
  APAGAR (vazio, errado, "apagar", " APAGAR "); 409; 503; gestor 403; auditoria; nenhum webhook nem e-mail.
- Auditoria: todo evento em um grupo só; filtro; cada evento novo. Registros de acesso: cada evento com o IP resolvido; ficam
  depois de excluir usuário e conta; RLS (em conta não lê nem a própria linha nem grava com outra conta; UPDATE não muda nada);
  limpeza. Exclusão: quem entra e quem nunca entra (teste vencido há 90 dias, cancelada com `pago_ate` + 90; assinatura ativa,
  atrasada, cortesia, teste, sem data, menos de 100 dias); aviso uma vez, data = max(prevista, hoje + 7); só exclui com 7 dias
  nos dois relógios (`exclusao_avisada_em` à mão); assinar depois cancela; novo encerramento avisa de novo; limite 20;
  `simular`; uma vez por dia; antes das 9h; Asaas fora; global e log sem dado pessoal. Revisão: limites do dia (rodada que
  caiu depois de 10 exclusões → só mais 10; evento do dia apagado → nenhuma; 99 avisos de hoje → só mais 1); erro num aviso e
  numa exclusão não para as outras (log só com id e tipo); aviso não entregue (nenhum, falhou, anterior ao aviso, outro
  assunto; e de ponta a ponta com o provedor falhando) → desfeito e refeito; sem administrador ativo → exclui com `admins: 0`;
  Asaas sem a chave do ambiente do cliente → adiada (sandbox com chave de produção segue); `EXCLUSAO_AUTOMATICA=desligada`
  sobe e simula com um aviso; a linha de comando mostra o log (subprocesso) sem duplicar o handler.
- IP: `X-Forwarded-For`/`X-Real-IP` ignorados; `CF-Connecting-IP` válido usado (lista, texto, vazio e longo → conexão); IPv4
  mapeado; o mesmo /64 divide o limite; 6º login com o mesmo `CF-Connecting-IP` e `X-Forwarded-For` diferentes → 429.
  WhatsApp: variações aceitas e recusadas, botão (inclusive "Não quero receber"), modelo sem SAIR → 422. Importação;
  `teste_ate` com relógio fixo; migração.
- Site (vitest): Dados da conta (baixar, 409, contagens, rádios, modal com APAGAR em qualquer caixa, sucesso relê, erros, foco,
  só admin, livre sem o aceite), "Exportar CSV" com os filtros e sem permissão, grupo na Auditoria, aviso de exclusão, versão 4.

## 12. Ajustes na construção e na revisão (03/10)
- Exclusão automática: limites de 20 exclusões e 100 avisos **por dia** (contados pelos eventos de hoje, não por rodada);
  cada aviso e cada exclusão em transação e `try/except` próprios (erro vai para `adiadas`, só id e tipo no log); só exclui
  com o aviso **entregue** (`emails_enviados` `aviso`/`enviado` com o assunto do aviso depois de `exclusao_avisada_em`; sem
  isso e com administrador ativo, o aviso é desfeito e refeito; sem nenhum administrador ativo, exclui com `admins: 0`);
  conta com cliente no Asaas sem chave do mesmo ambiente fica `adiada` (cliente de sandbox com chave de produção segue).
- `EXCLUSAO_AUTOMATICA` aceita qualquer texto: só `ligada` age; outro valor simula (com aviso no log).
- `python -m toqqi.tarefas` usa o mesmo log da API (`core/logs.py`).
- WhatsApp: "nao quero receber" e "nao quero receber mais" também descadastram.
- `respostas.csv` leva "Sentimento" e "Resumo da IA" de cada resposta; os pareceres da IA do painel e dos relatórios não vão.
- Envio público repetido grava o acesso sem `item_id`; `webhook_alterado` só com os campos que mudaram (nada mudou → não grava).
- Site: o aviso de exclusão toma o lugar do aviso de cobrança (não fecha) e aparece também em Assinatura e em Dados da conta;
  429 da exportação e da zona com texto de limite por hora; detalhes legíveis na Auditoria para os eventos da 5f; botão de
  exportar ao lado da busca em Contatos no celular.
