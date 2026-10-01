# Toqqi API · etapas 1, 2, 3a, 3b e 4a + dados da empresa

FastAPI + SQLAlchemy 2 (psycopg 3) + Alembic + PostgreSQL 16.
Contratos implementados (base `/api/v1`):
- `../docs/api-etapa-1.md`: acesso, equipe, sessões, auditoria;
- `../docs/api-etapa-2.md`: cadastros auxiliares, responsáveis, empresas, contatos, importação de planilha,
  formulários (modelos, resultados, CSV) e páginas públicas de pesquisa;
- `../docs/api-etapa-3.md`: envios por e-mail (fila, disparo manual, robô, lembretes, agradecimento),
  histórico, convite por WhatsApp (link wa.me), descadastro e exclusão de conta pela plataforma;
- `../docs/api-etapa-3b.md`: chave de integração, disparo por evento, webhooks de saída e WhatsApp automático;
- `../docs/api-etapa-4a.md`: respostas (lista, análise, registro à mão, arquivar, excluir, CSV), temas por
  palavras-chave, planos de ação (quadro, ação automática, alerta de risco), painel e importação de respostas antigas;
- `../docs/api-dados-empresa.md`: dados da empresa (Configurações › Empresa) e imagens (logo da conta e dos
  formulários) nas pesquisas e nos e-mails.

## Isolamento entre contas (RLS)
O isolamento é garantido pelo próprio PostgreSQL:

- funções `app_conta()` e `app_sistema()` leem `app.conta_id` e `app.sistema`, definidos pela aplicação
  com `set_config(..., true)` (valem só dentro da transação);
- todas as tabelas com `conta_id` (e `contas`, pelo `id`) têm `ENABLE` + `FORCE ROW LEVEL SECURITY`
  e a política `conta_id = app_conta() OR app_sistema()`;
- a aplicação conecta com um papel **sem** superusuário, **sem** `BYPASSRLS` e que não é dono das
  tabelas (`toqqi_app`). Sem contexto, ele não enxerga nenhuma linha. Até o dono das tabelas fica sujeito
  às políticas (`FORCE`).

No código: `with em_conta(conta_id) as s:` para o trabalho normal (a conta vem da sessão do usuário) e
`with modo_sistema() as s:` apenas onde não existe conta conhecida: busca do e-mail no login, busca de
tokens de e-mail, cadastro, pedido de acesso, checagem de domínio de outra conta, área da plataforma e,
nas páginas públicas de pesquisa, só a busca da conta pelo hash do token do convite ou pelo código público
do formulário (todo o resto da página pública roda em `em_conta`). A limpeza das análises de importação
vencidas também roda em modo sistema.

Referências entre tabelas da conta (contato → empresa, empresa → grupo, resposta → formulário...) usam
chave estrangeira composta `(id, conta_id)`: como a checagem de FK do PostgreSQL ignora o RLS, isso impede
apontar para uma linha de outra conta mesmo conhecendo o id.

## Preparar o banco (uma vez)
```bash
sudo -u postgres psql -f scripts/preparar_banco.sql   # papéis toqqi (dono) e toqqi_app, bancos toqqi_dev e toqqi_test
```
Troque as senhas em produção. As migrações concedem os GRANTs ao papel `APP_DB_ROLE` (padrão `toqqi_app`).

## Rodar
```bash
pip install -r requirements.txt
cp .env.example .env         # ajuste JWT_SECRET e demais valores
uvicorn toqqi.main:app --reload
```
Com `AUTO_MIGRATE=1`, a aplicação roda `alembic upgrade head` (usando `MIGRATION_DATABASE_URL`) ao iniciar.
Para migrar manualmente: `alembic upgrade head` nesta pasta.

Documentação interativa: `http://localhost:8000/api/v1/docs`.

Atrás de proxy/balanceador, rode com `uvicorn toqqi.main:app --proxy-headers --forwarded-allow-ips=<ip do proxy>`
para que o IP real do cliente seja usado no limite de tentativas, nas sessões e na auditoria.

## Variáveis de ambiente
| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Conexão da aplicação (papel `toqqi_app`), formato `postgresql+psycopg://...` |
| `MIGRATION_DATABASE_URL` | Conexão das migrações (papel dono). Vazia = usa `DATABASE_URL` |
| `APP_DB_ROLE` | Papel que recebe os GRANTs nas migrações (padrão `toqqi_app`) |
| `AUTO_MIGRATE` | `1` aplica migrações ao iniciar |
| `JWT_SECRET` | Segredo do token de acesso (obrigatório, mínimo 16 caracteres) |
| `FRONTEND_URL` | Base dos links enviados por e-mail (`/confirmar-email`, `/redefinir-senha`, `/entrar`) |
| `API_PUBLIC_URL` | Endereço público da API (base das URLs das imagens/logos e do descadastro de um clique) |
| `ALLOWED_ORIGINS` | Origens liberadas no CORS, separadas por vírgula |
| `EMAIL_PROVIDER` | `console` (imprime), `memory` (testes), `zeptomail` ou `resend` |
| `ZEPTOMAIL_TOKEN` / `RESEND_API_KEY` | Credenciais do provedor de e-mail |
| `EMAIL_FROM` | Remetente, ex.: `Toqqi <nao-responda@toqqi.com>` |
| `SUPERADMIN_EMAILS` | E-mails com acesso à área `/plataforma`, separados por vírgula |
| `RATE_LIMIT_ENABLED` | `0` desliga o limite de tentativas (usado nos testes) |
| `AMBIENTE` | `desenvolvimento` (padrão) ou `producao`; em produção o provedor `console` não conta como configurado |
| `TAREFAS_TOKEN` | Segredo do cabeçalho `X-Tarefas-Token` de `POST /api/v1/interno/tarefas` (vazio = rota desligada, 404) |
| `SEGREDOS_KEY` | Cifra (Fernet, chave = sha256) o token do WhatsApp e os segredos dos webhooks. Obrigatória em produção; fora dela, vazia usa o `JWT_SECRET` |
| `WHATSAPP_GRAPH_VERSION` | Versão da Graph API da Meta (padrão `v23.0`); `WHATSAPP_GRAPH_URL` muda o endereço base |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificação do webhook da Meta (`GET /api/v1/publico/whatsapp/webhook`) |
| `WHATSAPP_APP_SECRET` | App Secret do app da Meta: confere `X-Hub-Signature-256` dos avisos |

A etapa 2 não criou variáveis novas. `FRONTEND_URL` também é a base dos links de convite (`/r/{token}`)
e `JWT_SECRET` entra no sal diário do hash de IP das respostas públicas.

## Testes
```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```
Usam o banco real `toqqi_test`: o esquema é recriado e migrado com o papel dono
(`TEST_OWNER_DATABASE_URL`, padrão `toqqi:toqqi`) e a aplicação conecta como `toqqi_app`
(`TEST_DATABASE_URL`), então o RLS é exercitado de verdade. E-mails vão para a caixa em memória.

## Etapa 2: pontos de atenção
- **Limite de contatos ativos** (essencial 300, profissional 1500, empresa/cortesia ilimitado; em teste vale o
  plano): a API confere antes (importação) e o banco garante com o gatilho `contatos_limite_plano`
  (`BEFORE INSERT OR UPDATE OF ativo`, trava consultiva por conta). O gatilho levanta SQLSTATE `TQ402`, que a
  aplicação converte em 402 `limite_do_plano`. Editar um contato que já estava ativo não conta.
- **Convites**: o token só aparece no link; o banco guarda o sha256 (`convites.token_hash`). Criação:
  `toqqi.modulos.respostas.convites.novo_convite(...)` / `criar_convite(...)`.
- **Resposta registrada**: toda resposta nova passa por `toqqi.modulos.respostas.eventos.ao_registrar_resposta`
  (lista `GANCHOS`; a etapa 3a pendura ali o agradecimento), na mesma transação da gravação.
- **Respostas públicas repetidas**: `ip_hash = sha256(JWT_SECRET | dia UTC | ip)` (o IP não é guardado). A mesma
  resposta do mesmo IP em 10 minutos recebe a mesma resposta 201, sem gravar de novo.
- **Limites por IP nas páginas públicas**: abrir 30/min, responder convite 10/min, responder link 5/min.
- **Webhook do Teams**: ao salvar, só `https://` sem IP/nome interno; ao testar, o nome é resolvido, todos os IPs
  precisam ser públicos e a conexão é feita direto no IP conferido (Host/SNI com o nome), timeout 10 s, sem
  seguir redirecionamento (`toqqi/core/rede.py`).
- **Importação**: .csv (`;` `,` ou tab; UTF-8 com/sem BOM, senão cp1252/latin-1), .xlsx (openpyxl) e .xls (xlrd),
  até 5 MB e 20.000 linhas. A análise fica em `importacoes` por 1 hora; importar é tudo ou nada e apaga a análise.
- Contas novas (cadastro e plataforma) recebem os perfis Decisor/Influenciador e os formulários
  "Pesquisa NPS" (padrão NPS) e "Satisfação pós-entrega" (padrão CSAT); a migração 0002 faz o mesmo nas contas
  que já existiam.

## Etapa 3a: envios
- **Tarefas periódicas**: `python -m toqqi.tarefas [robo|lembretes|pendentes|webhooks|tudo]` ou
  `POST /api/v1/interno/tarefas` com `X-Tarefas-Token` (comparação em tempo constante). Em produção, o Cron Job
  `toqqi-tarefas` do Render roda o comando a cada 15 minutos; cada conta decide se é hora (janela, dias úteis, 6 h entre rodadas do robô, lembretes uma vez
  por dia a partir das 10:00). A lista de contas sai do modo sistema (só ids); o trabalho de cada conta roda em
  `em_conta`.
- **Envio em segundo plano**: o envio nasce `pendente` na transação que o decide e sai depois do commit
  (`BackgroundTasks` nas rotas; direto na tarefa). A chamada ao provedor fica fora da transação. Pendentes há mais
  de 10 minutos (queda do processo) são retomados pela tarefa `pendentes`.
- **Situação do contato** (`na_fila`, `aguardando`, `respondeu`...) é calculada no banco
  (`modulos/envios/fila.py`) e usada na fila, nos filtros e em Contatos.
- **Mesmo link no lembrete**: convites por e-mail/WhatsApp guardam `token_semente`; o token é
  `HMAC(JWT_SECRET, semente)` e o banco continua só com o sha256 do token.
- **Descadastro**: por conta + e-mail (`descadastros`), token `base64url(conta_id:email).HMAC(JWT_SECRET)`, sem
  validade. Todo envio confere o descadastro na hora de sair. Cabeçalhos `List-Unsubscribe` (URL da API) e
  `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058).
- **Erros do provedor** viram texto simples no histórico (`toqqi/core/email.py`); o detalhe técnico vai ao log.
- **Relógio**: as regras usam `toqqi.core.relogio.agora()` (São Paulo); os testes trocam essa função.
- **Exclusão de conta** (plataforma): apaga os dados em ordem, em modo sistema, e grava auditoria global
  (`auditoria.conta_id` nulo, visível só em modo sistema).

## Etapa 3b: integrações e WhatsApp automático
- **Chave da conta** (`modulos/integracoes/chave.py`): só o sha256 no banco; a conta sai do hash em modo sistema e
  o resto roda em `em_conta`. Limite de 120 chamadas/min por chave (slowapi, chaveado pelo hash).
- **Disparo por evento** (`modulos/integracoes/pesquisas.py`): uma transação por evento; `id_evento` trava
  (`pg_advisory_xact_lock`) e guarda a resposta por 24 h em `eventos_idempotencia`.
- **Canal**: `ConfigEnvios.canal` define a ordem (`processamento.ordem_canais`). O WhatsApp reserva a franquia ao
  criar o envio, com a linha do mês (`whatsapp_uso`) travada; se a mensagem não sai (na hora ou pelo aviso
  `failed` da Meta), a reserva volta (`envios.cobranca`) e, com `whatsapp_e_email`, o mesmo convite vai por e-mail.
  Lembretes: só o 1º de um convite por WhatsApp vai por WhatsApp.
- **Webhooks de saída** (`modulos/integracoes/webhooks.py`): fila `webhook_entregas`; entrega logo depois da
  resposta (`coletar_entregas` + `BackgroundTasks`) e na tarefa `webhooks`. POST pelo `core/rede.py` (IP público
  conferido, sem redirecionamento, 10 s), assinado `t=<unix>,v1=HMAC(segredo, "<t>.<corpo>")`. Novas tentativas em
  1 min, 5 min, 30 min, 2 h e 6 h; 10 falhas seguidas (tentativas) desativam o webhook e avisam os admins.
- **Graph API** (`modulos/whatsapp/graph.py`): httpx sem redirecionamento, timeout 10 s; os testes trocam
  `graph.transporte` por um `httpx.MockTransport` (o `conftest` bloqueia a rede por padrão).
- **Webhook da Meta** (`modulos/whatsapp/webhook.py`): assinatura conferida no corpo cru; a conta sai do
  `phone_number_id` em modo sistema. "SAIR" descadastra o telefone (forma canônica com o nono dígito).
- **Avisos aos admins** (`core/avisos.py`) saem depois do commit (`core.db.apos_commit`).

## Etapa 4a: respostas, planos de ação e painel
- **Data da resposta**: `respostas.data_resposta` é coluna gerada (`coalesce(respondida_em, criada_em)`) e é a data
  de toda regra de período: lista de respostas, painel, resultados/respostas/CSV do formulário, histórico do contato e
  a situação "respondeu" da fila de envios. Resposta à mão com data anterior a hoje e resposta importada ficam às
  12:00 de São Paulo daquele dia; à mão com a data de hoje (a tela sempre manda), vale a hora real de entrada
  (`respondida_em` vazio: 12:00 poderia ficar no futuro). Como no resto da API, os horários saem em UTC (ISO 8601 com
  fuso).
- **Filtros de data** (`core/filtros.py`: `DataFiltro` nos modelos de query, `data_filtro` nas rotas que recebem
  texto): AAAA-MM-DD de 01/01/2000 a 31/12/2100 em todas as rotas com período (respostas e CSV, ações e quadro,
  painel e exportação, resultados/respostas do formulário, fila e histórico de envios, auditoria). Fora disso, 422 com
  o campo (`de`, `ate`, `ultimo_ate`...): "Use uma data entre 01/01/2000 e 31/12/2100." (9999-12-31 estourava o
  calendário no fim do dia ou no período anterior).
- **Origem e ponto único**: `gravar_resposta(..., origem=)` grava grupo e temas e chama `ao_registrar_resposta`. Os
  ganchos conferem a origem: `pesquisa` tem tudo; `manual` (POST /respostas) tem fila, ação automática, alerta e
  webhook, sem agradecimento; `importacao` não tem nenhum efeito (a importação grava em lote e nem chama os
  ganchos). A fila de envios ignora as respostas importadas.
- **Comentário do cliente** (`respostas.comentario_cliente`, gravado com a resposta): só o que o cliente escreveu. Nas
  respostas de pesquisa, as respostas das perguntas de comentário, na ordem do formulário, separadas por " · "
  (`registro.comentario_do_cliente`, lidas do JSON das respostas e não do resumo "Pergunta: resposta | ...": um " | "
  no texto do cliente não atrapalha); nome, e-mail, telefone e número (texto curto), nota, escala, data, sim/não e
  opções marcadas não entram. Nas manuais e importadas, o comentário. Editado na análise, vale o texto como ficou
  (mudar só a nota, ou salvar com o mesmo comentário, não mexe nele). O painel usa só ele (comentários recentes,
  último comentário de detrator e palavras); a lista de respostas e os CSV continuam com `comentario` (o resumo da
  etapa 2).
- **Temas** (`modulos/respostas/temas.py`, funções puras): comentário do cliente + opções marcadas nas perguntas de
  escolha + "o que faltou". Recalculados ao gravar, quando o comentário ou "o que faltou" mudam na análise e quando a
  importação traz comentário, salvo `temas_manuais`. A migração 0005 preenche o comentário do cliente e os temas das
  respostas que já existiam com uma cópia congelada dessas regras (não importa código da aplicação, que pode mudar).
- **Última nota do contato** = nota da resposta não arquivada mais recente pela data da resposta; recalculada ao
  gravar, mudar a nota, arquivar/restaurar, excluir e importar (uma resposta à mão com data antiga não a troca).
- **Ação automática e alerta** (`modulos/acoes/automatica.py`): uma ação automática por resposta (índice único
  parcial). O "Alerta de risco" é coletado na transação (`coletar_alertas()`) e sai por `BackgroundTasks` depois do
  commit, nas rotas públicas e em POST /respostas; sem coletor não sai. E-mail do sistema (`core.email.enviar`): não
  entra no histórico de envios. Só sai com provedor de e-mail configurado pela mesma regra dos envios de pesquisa
  (`provedor_ok`: o `console` não conta em produção, para o comentário e os dados do cliente não irem para o log; a
  ação é criada do mesmo jeito). Descrição da ação e alerta trazem o contato só pelo nome (sem e-mail e telefone).
- **Arredondamento** (`modulos/respostas/indicadores.py`): `Decimal` + `ROUND_HALF_UP` sobre o valor exato
  (NPS 12,5 → 13, −12,5 → −13; CSAT 12,5% → 13%).
- **Painel** (`modulos/painel/servico.py`): cerca de 12 consultas agregadas no banco. Medido no teste de desempenho
  (5.000 contatos, 50.000 respostas, 8.000 convites, 3.000 ações): 250–400 ms com 90 dias e 450–600 ms com todo o
  histórico; lista de respostas ~120 ms e quadro ~160 ms. Duas medidas foram necessárias: `core.db.sem_jit`
  (`SET LOCAL jit = off` no painel, nas listas e nos CSV: o JIT do PostgreSQL gastava 300–500 ms compilando
  consultas que rodam em ~50 ms) e o filtro explícito `conta_id = ...` nessas consultas (a política RLS tem
  `OR app_sistema()`, que impede o planejador de usar os índices `(conta_id, ...)`; o RLS continua valendo igual).
  A lista de respostas busca primeiro os ids da página e só depois os detalhes e a ação de cada uma. O mesmo filtro
  explícito vale na última nota do contato (`registro.atualizar_ultima_nota`) e nas subconsultas correlacionadas da
  fila de envios (`envios/fila.py`); no EXPLAIN ANALYZE com 5.000 contatos: última nota 0,50 → 0,05 ms, contagem da
  fila 788 → 29 ms.
- **Importação de respostas antigas** (`modulos/importacao/respostas.py`): o tipo vem do campo `tipo` da análise e
  fica em `importacoes.tipo`; conferir/importar decidem por ele. As linhas novas entram num INSERT só, com um vetor
  por coluna desfeito por `unnest` (`COPY` não é aceito em tabela com RLS, e milhares de `VALUES` custam caro para
  montar): 20.000 linhas em cerca de 1 s nos testes. O e-mail de um contato cadastrado não é validado de novo.
  Datas de 2000 até hoje (ano anterior a 2000 vira linha com problema: pega ano digitado errado).
  "Mesma data" de uma resposta já importada = o dia dela em São Paulo. Ao atualizar as que já existem, nota e grupo
  sempre mudam; comentário (e temas) só quando a célula tem texto (vazia ou coluna não ligada = fica como está).
  Uma importação por vez em cada conta (`core.db.travar` no início de importar, contatos e respostas): a mesma
  planilha enviada duas vezes e importada ao mesmo tempo não grava em dobro (a segunda espera e encontra as linhas).
- **Exclusões**: excluir resposta (só perfil admin) apaga as ações ligadas a ela. Excluir contato apaga as respostas
  dele (regra da etapa 2) e mantém as ações, sem a referência; excluir empresa, responsável ou usuário mantém ações e
  respostas, só sem a referência (`ON DELETE SET NULL` nas chaves compostas).

### Etapa 4a: decisões tomadas aqui (além da seção 0 do contrato)
- `metricas` de GET /respostas usam exatamente o filtro da lista, inclusive `arquivadas=true|todas`.
- GET /respostas e /respostas.csv aceitam `so_ativos` (padrão `false`), com a regra do painel (tira as respostas de
  empresas inativas; resposta sem empresa sempre conta). Com os mesmos `de`, `ate`, `grupo_id`, `so_ativos` e
  `tipo_nota=nps`, as métricas da lista batem com o NPS do painel (há teste para isso).
- PATCH /respostas: mudar a nota também troca a nota guardada em `respostas` (pergunta principal), para os resultados
  por pergunta do formulário continuarem batendo; `temas: null` é ignorado (não volta para o automático).
- Arquivar e restaurar recalculam a última nota do contato ("arquivada sai de todos os indicadores").
- POST /acoes: sem empresa, usa a da resposta (ou a do contato); sem contato, o da resposta; copia grupo, tipo e nota da
  resposta. PATCH numa ação já concluída que mexe no responsável ou na resolução confere de novo as regras de conclusão.
- Descrição da ação automática: "Comentário do cliente" (o `comentario_cliente`; "(sem comentário)" se vazio), "O
  cliente marcou: ..." com as opções escolhidas (se houver), "Contato: nome" e o contexto do pedido.
- Painel: `temas` traz só temas com menção (até 5); `empresas` divide as empresas com 3+ respostas entre as duas listas
  (metade, arredondada para cima, em `menor`, até 6 cada, sem repetir); `desde`, `data_anterior` e `data_atual` são
  data e hora (ISO), como `data` das respostas; `primeira_resposta` conta qualquer resposta.
- Formato `Resposta` da etapa 2 (formulário e webhook `resposta.criada`) ganha `data` e `origem`; o histórico do
  contato ganha `id`, `tipo_nota`, `canal`, `origem` e `arquivada` (só acréscimos).
- Downgrade da 0005: a data informada passa para `criada_em` e o canal volta a `manual`/`importacao` pela origem; ações
  e configuração de prazos são apagadas.
- Testes que dependem de "hoje" usam o fixture `relogio_estavel` (relógio das regras ao meio-dia do dia corrente),
  para não falharem quando a suíte cruza a meia-noite.

## Dados da empresa e imagens (logo)
- **Migração `0006_dados_empresa`**: colunas novas em `contas` (CHECK de formato e tamanho; vazio = NULL) e a tabela
  `imagens` (RLS com FORCE, chave composta com `formularios` ON DELETE CASCADE, um logo por conta e um por formulário
  por índice único parcial). Os bytes não ficam em `contas`, lida a cada requisição; `GET /eu` busca o logo à parte.
- **Validação** (`modulos/conta/esquemas.py`): reusa `Documento` (CPF ou CNPJ, com máscara), `Telefone` (regra dos
  contatos), `EmailOpcional` e `TextoAte`. Site sem esquema ganha `https://` (esquema e domínio em minúsculas; aceita
  domínio com acento); CEP aceita hífen e ponto; UF sem diferenciar maiúsculas. O PUT leva todos os campos: o que vem
  nulo, vazio ou falta fica sem valor. Salvar sem mudança não grava nem audita; `atualizado_em`
  (`contas.dados_atualizados_em`) muda quando algum dado muda e quando o logo é trocado ou removido.
- **Imagens** (`modulos/imagens/servico.py`): tipo pelos primeiros bytes (PNG `89 50 4E 47 0D 0A 1A 0A`, JPEG
  `FF D8 FF`), até 300 KB, lendo no máximo 300 KB + 1 byte do upload. Chave `secrets.token_urlsafe(32)` (43
  caracteres); trocar apaga a anterior e grava outra com chave nova, com o dono travado (a conta ou o formulário).
  `GET /publico/imagens/{chave}` busca em modo sistema só pela chave; o `ETag` é o sha256 entre aspas (como o HTTP
  pede) e `If-None-Match` aceita lista, `W/` e `*`; o 304 não lê os bytes. O logo de formulário não é auditado.
- **Logo que o cliente vê** (`logo_para_cliente`, páginas públicas e e-mails de pesquisa): o do formulário; sem ele, o
  da conta. Também cai no da conta quando o `tema.logo_url` salvo aponta para uma imagem da plataforma que não existe
  mais (ex.: logo enviado de novo no editor e o formulário não foi salvo) ou que é de outra conta. Copiar um
  formulário copia também a imagem enviada (chave nova): trocar o logo de um não mexe no outro.
- **E-mails**: cabeçalho com `<img height="48">` (o Outlook ignora `max-height`) e `alt` = nome da conta; sem logo, o
  HTML é o mesmo de antes, e o texto puro não muda. A exclusão de conta pela plataforma apaga as imagens junto.

## Estrutura
```
toqqi/
  main.py                 create_app, CORS, id da requisição, handlers de erro, auto-migração
  modelos.py              modelos ORM
  apresentacao.py         formato JSON de Usuario e Conta
  core/                   config, db (em_conta / modo_sistema), security (argon2id, JWT, tokens), relogio,
                          errors, validacao, email, rate_limit, auditoria, permissoes, deps (requer),
                          texto (telefone, CNPJ/CPF, valores, datas), planos, paginacao, filtros, rede
  modulos/acesso/         cadastro, entrar, sair, confirmar, reenviar, esqueci, redefinir, pedir-acesso, /eu
  modulos/equipe/         usuários da conta e matriz de permissões
  modulos/conta/          segurança (duração da sessão, domínios liberados), dados da empresa e logo da conta
  modulos/imagens/        imagens da conta (logo da empresa e dos formulários): envio, URL pública, logo do cliente
  modulos/auditoria/      registro de atividades
  modulos/plataforma/     área do superadmin
  modulos/cadastros/      grupos, segmentos, perfis, cargos e responsáveis (teste do Teams)
  modulos/empresas/       empresas (clientes da conta)
  modulos/contatos/       contatos e link de pesquisa manual
  modulos/importacao/     leitura de planilhas, nomes equivalentes, conferir e importar (contatos e respostas)
  modulos/formularios/    modelos prontos, validação das perguntas, padrões, resultados, CSV
  modulos/respostas/      convites, validação/gravação de respostas, variáveis, "resposta registrada",
                          temas (palavras-chave), indicadores (NPS/CSAT), tela Respostas (lista, análise, CSV)
  modulos/acoes/          planos de ação: quadro, regras (selo, urgência), ação automática + alerta, prazos
  modulos/painel/         painel (visão geral) e palavras mais citadas
  modulos/publico/        páginas públicas (convite, link público e descadastro)
  modulos/envios/         configuração e pré-condições, fila/situação, disparo, histórico, WhatsApp,
                          robô/lembretes/pendentes, agradecimento, descadastro, modelos de e-mail
  modulos/integracoes/     chave da conta, disparo por evento (/integracao) e webhooks de saída
  modulos/whatsapp/       conexão (Graph API), modelo, franquia, webhook da Meta
  tarefas.py              CLI das tarefas periódicas (python -m toqqi.tarefas)
alembic/versions/0001_inicial.py   esquema da etapa 1 + RLS + GRANTs
alembic/versions/0002_cadastros_formularios.py   tabelas da etapa 2 + RLS + limite do plano + dados iniciais
alembic/versions/0003_envios.py    config_envios, envios, descadastros + colunas de fila/lembrete + RLS
alembic/versions/0004_integracoes.py   chaves, webhooks, entregas, WhatsApp, franquia, idempotência + RLS
alembic/versions/0005_respostas_acoes.py   data/origem/temas/análise das respostas, ações, prazos, tipo da importação
alembic/versions/0006_dados_empresa.py   dados da empresa em `contas` e tabela `imagens` (logos) + RLS
tests/                             pytest
```

## Decisões
- Sessão: duração fixa definida no login (`lembrar` = 30 dias; senão `contas.sessao_minutos`).
  O `exp` do JWT é igual ao fim da sessão; a cada requisição a sessão é conferida no banco
  (encerrada, expirada ou usuário não ativo → 401 `sessao_invalida`).
- Permissões são lidas do banco a cada requisição: mudança de perfil ou da matriz vale na hora.
- Entrada: e-mail desconhecido e senha errada têm a mesma resposta e o mesmo custo (verificação argon2
  descartável). Situação da conta (`email_nao_confirmado`, `acesso_pendente`, `acesso_bloqueado`) só é
  revelada com a senha certa.
- Redefinir senha também marca o e-mail como confirmado (quem abriu o link provou ser dono do e-mail).
- `ultimo_admin` tem prioridade sobre `nao_pode_si_mesmo`: o único admin tentando se rebaixar recebe
  `ultimo_admin`; com outro admin ativo, recebe `nao_pode_si_mesmo`.
