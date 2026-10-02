# Toqqi API · etapas 1, 2, 3a, 3b, 4a, 4b e 5a + dados da empresa

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
  formulários) nas pesquisas e nos e-mails;
- `../docs/api-etapa-4b.md`: IA por resposta (OpenAI), reclamações e picos por tema, relatórios (empresas, grupos de
  clientes, temas, entregas, responsáveis, operação, histórico de uma empresa) e resumo semanal por e-mail;
- `../docs/api-etapa-5a.md`: assinatura e cobrança pelo Asaas (planos, assinar, trocar de plano, cancelar, webhook,
  situação da conta e liberação dos envios, conferência diária, plataforma).
- `../docs/api-aceite-lgpd.md`: aceite dos Termos de uso e da Política de privacidade (`aceite` em `GET /eu` e no
  entrar, `POST /eu/aceite`, aceite gravado no cadastro; versão em `toqqi/modulos/acesso/termos.py`).

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
| `OPENAI_API_KEY` | Chave da OpenAI (da plataforma) para a análise dos comentários. Vazia = sem IA (temas por palavras-chave) |
| `IA_PROVEDOR` | `openai` (padrão), `memoria` (testes) ou `desligado` |
| `IA_MODELO` | Modelo da OpenAI (padrão `gpt-5-mini`) |
| `IA_ESFORCO` | `reasoning.effort` enviado (padrão `minimal`; vazio = não manda `reasoning`) |
| `IA_BASE_URL` | Endereço base da API da OpenAI (padrão `https://api.openai.com`) |
| `ASAAS_API_KEY` | Chave de API do Asaas (da plataforma), na toqqi-api (e no toqqi-tarefas, se o Cron Job estiver ligado). Vazia = sem cobrança online |
| `ASAAS_WEBHOOK_TOKEN` | Token do webhook do Asaas (cabeçalho `asaas-access-token`), só em toqqi-api. Vazio = webhook desligado (404) |
| `ASAAS_URL` | Opcional: sobrepõe o endereço da API do Asaas (Asaas falso local). Vazio = o endereço segue a chave |

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
- **Tarefas periódicas**: `python -m toqqi.tarefas [assinaturas|robo|lembretes|pendentes|webhooks|ia|picos|resumo|tudo]` ou
  `POST /api/v1/interno/tarefas` com `X-Tarefas-Token` (comparação em tempo constante). Em produção, a rotina do GitHub
  (`.github/workflows/tarefas.yml`) chama a rota a cada 30 minutos (o Cron Job `toqqi-tarefas` do Render, que roda o
  comando direto no banco, está comentado no `render.yaml` para quando valer o custo); cada conta decide se é hora (janela, dias úteis, 6 h entre rodadas do robô, lembretes uma vez
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

## Etapa 4b: IA por resposta, relatórios, picos e resumo semanal
- **Chave da OpenAI no Render**: `OPENAI_API_KEY` vai no painel do Render (Environment) da **toqqi-api** (análise logo
  depois de gravar a resposta e, pela rotina do GitHub, a tarefa `ia`: fila, novas tentativas e "analisar os últimos 90
  dias"; se o Cron Job `toqqi-tarefas` estiver ligado, nele também), e não no `render.yaml` (o Blueprint não apaga variáveis que ele não declara).
  `IA_MODELO` e `IA_ESFORCO` só se quiser trocar o padrão. Sem a chave, tudo funciona como antes (temas por
  palavras-chave) e `conta.ia_ativa` sai `false` para a tela esconder as partes de IA.
- **Migração `0007_ia_relatorios`**: colunas `ia_*` em `respostas`, `contas.ia_analise_respostas`, as preferências de
  e-mail em `usuarios` e as tabelas `ia_uso_mensal`, `alertas_pico` e `resumos_semanais` (RLS com FORCE, grants
  condicionais, `ON DELETE CASCADE` na conta; a exclusão de conta pela plataforma também as apaga). `temas_reclamacao`
  e `temas_elogio` são colunas geradas (`STORED`) por funções SQL `IMMUTABLE` com corpo padrão (`RETURN`: referências
  resolvidas na criação, sem depender do `search_path` numa restauração): `classe_tema` aplica a regra do §3 tema a
  tema quando a IA analisou; sem análise, um atalho usa só o grupo da nota (importar 20.000 respostas passou de
  ~1,1–1,2 s para ~1,35 s nos testes). Índices: fila da IA (parcial, pendentes) e `(conta_id, empresa_id,
  data_resposta DESC) WHERE NOT arquivada` para os relatórios por empresa.
- **Adaptador** (`core/ia.py`): Responses API por httpx (sem SDK), 30 s, sem redirecionamento; os testes trocam
  `ia.transporte` por um `httpx.MockTransport` e o `conftest` usa `IA_PROVEDOR=memoria` (rede bloqueada). Falhas:
  `configuracao` (401, 403, 404 e os demais 4xx, menos 408/409/429: chave, modelo ou parâmetro recusados) não conta
  tentativa, deixa pendente e para a rodada com um `log.error`; `transitoria` (429, 5xx, 408/409, tempo, rede, JSON
  inválido, `incomplete`, formato fora do esquema) conta tentativa; `definitiva` (`refusal` ou 400 `invalid_prompt`)
  vira `falhou` na hora. O log leva só o status HTTP e o código do erro, nunca a chave nem o texto do cliente.
- **Fila** (`modulos/ia/servico.py`): o gancho de `ao_registrar_resposta` marca `pendente`; POST /respostas, PATCH
  /respostas/{id} e as rotas públicas juntam as pendentes com `coletar_analises()` e chamam `analisar` por
  `BackgroundTasks` depois do commit (como o "Alerta de risco"); o resto fica para a tarefa `ia`. Reserva com
  `FOR UPDATE SKIP LOCKED` + `ia_reservada_em` (5 min), teto do mês por `INSERT ... ON CONFLICT DO UPDATE ... WHERE
  analises < teto` (sem saldo = `limite`), chamada fora da transação e gravação só se o sha256 do texto enviado
  (`ia_texto_hash`) ainda é o do texto atual. Falha devolve o saldo. Tokens somados em `ia_uso_mensal`.
- **Reclamação e pico** (`modulos/relatorios/picos.py`): contagem no banco por `unnest(temas_reclamacao)`; o painel,
  o relatório de temas, o alerta e o resumo usam a mesma função. Alerta de pico: trava consultiva por conta e tema +
  conferência dos últimos 7 dias na mesma transação; grava `alertas_pico` e manda depois do commit. Resumo semanal:
  `INSERT ... ON CONFLICT DO NOTHING RETURNING` em `resumos_semanais` antes de mandar. As duas tarefas pegam as contas
  em modo sistema (só ids) e trabalham em `em_conta`; uma conta com erro não derruba as outras
  (`modulos/relatorios/emails.py`, visual do "Alerta de risco": `core.email.enviar` ganhou subtítulos, links e
  rodapé).
- **Relatórios** (`modulos/relatorios/`): poucas consultas agregadas no banco (por empresa, tema, semana ou valor do
  contexto), com `conta_id` explícito e `sem_jit`, como no painel; o que é por empresa (até alguns milhares de linhas)
  é montado em Python. CSV como os da 4a (`gerar_csv`: `;`, BOM, células protegidas; número negativo sai como número).
  Medido no teste de desempenho (5.000 contatos, 1.000 empresas, 50.000 respostas, 8.000 convites, 3.000 ações):
  empresas ~110–210 ms, grupos ~50 ms, temas ~145 ms (todo o histórico ~300 ms), entregas ~60 ms, responsáveis
  ~40 ms, operação ~120 ms, histórico ~50 ms, painel ~270 ms.

### Etapa 4b: decisões tomadas aqui (além da seção 0 do contrato)
- Temas depois da análise (sem `temas_manuais`) = temas da IA + os de "o que faltou" por palavra-chave (escrito pela
  equipe na análise, a IA não vê). Comentário editado numa resposta que já tinha passado pela IA (inclusive importada
  marcada por "analisar os últimos 90 dias") volta para `pendente`; se não passa mais, a análise antiga é apagada.
- Filtro `sentimento=sem_analise` = respostas com texto do cliente e sem análise concluída. `ia_em` também é gravado em
  `falhou` e `limite` (é o que conta em `falharam_no_mes`). `POST /conta/ia/analisar-recentes` também responde 409
  `ia_indisponivel` com a assinatura vencida. `provedor` é "Memória" com `IA_PROVEDOR=memoria` (só testes).
- O alerta de pico é gravado mesmo sem destinatários (`destinatarios = 0`) e conta para a janela de 7 dias.
- Preferências de e-mail só em `/eu` e no login (a lista da equipe não mostra).
- Relatórios: percentuais inteiros (como no painel); em Empresas, `busca`, `respostas` e `quadrante` mexem só na tabela
  (resumo e matriz seguem os filtros de empresa); ordens `valor` e `respostas` = maior primeiro, `cobertura` = menor
  primeiro. Grupos de clientes: `empresas` = empresas com respostas NPS no período. Entregas: respostas NPS e CSAT;
  `reclamacoes` = respostas com alguma reclamação; `ultima_resposta` = data e hora (ISO). Responsáveis: ações abertas e
  vencidas das empresas da carteira. Histórico: `acoes.concluidas` = concluídas no período. Operação: "último convite
  que saiu" = `contatos.ultimo_envio`.

## Etapa 5a: assinatura e cobrança (Asaas)
- **Chaves só no painel do Render** (Environment), nunca no `render.yaml` (o Blueprint não apaga variáveis que ele não
  declara): `ASAAS_API_KEY` na **toqqi-api** (e no toqqi-tarefas, se o Cron Job estiver ligado: a tarefa `assinaturas` reprocessa
  avisos e confere as cobranças); `ASAAS_WEBHOOK_TOKEN` **só na toqqi-api** (32 a 255 caracteres, sem espaços nem acentos, diferente da
  chave; fora disso o webhook fica desligado e o log diz por quê). Gere o token com
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. O endereço e o **ambiente** seguem a chave:
  `$aact_prod_…` → produção (`https://api.asaas.com/v3`); qualquer outra (`$aact_hmlg_…`) → sandbox (uma chave de
  formato desconhecido nunca cobra de verdade). `ASAAS_URL` só para o Asaas falso. Sem a chave, `GET /assinatura` sai
  com `disponivel: false` (a tela avisa que a cobrança online não está disponível) e o resto funciona; sem o token, o
  webhook responde 404. Num `.env` local, ponha a chave entre aspas simples se o seu carregador expande `$`.
- **No Asaas** (sandbox primeiro, depois produção): *Integrações › Chaves de API* → gerar a chave (`ASAAS_API_KEY`).
  *Integrações › Webhooks* → criar o webhook com a URL `https://<api>/api/v1/asaas/webhook`, os **eventos de
  cobranças** (Payments), o mesmo token em "Token de autenticação" (`ASAAS_WEBHOOK_TOKEN`), versão da API **v3** e a
  fila de sincronização ativada (a ordem dos avisos não importa: a API sempre consulta o Asaas). O Asaas espera 200
  depressa: a API grava o aviso e responde; o resto roda depois da resposta. **Uma conta do Asaas por instalação do
  Toqqi**: não use a mesma chave em duas instalações (homologação e produção, por exemplo) — a conciliação reconhece
  as assinaturas pela referência `toqqi-conta-{id}` e trataria as da outra instalação como suas.
- **Migração `0008_assinaturas`**: `contas` ganha `asaas_cliente_id` + `asaas_ambiente` (`sandbox` | `producao`, os
  dois juntos ou nenhum), `asaas_conferida_em`, `pago_ate`, `atrasada_desde` e `primeiro_vencimento` (cópia do da
  assinatura ativa); tabelas `assinaturas` (com o `ambiente`; uma ativa por conta, índice único parcial;
  `nao_encontrada_desde` para o 404 na conferência), `cobrancas` (RLS com FORCE, chaves compostas), `asaas_eventos`
  (tabela da plataforma: RLS com FORCE e política só para o modo sistema; guarda só ids e tipo, nunca o corpo do aviso)
  e `asaas_remocoes` (assinaturas a remover no Asaas que falharam; RLS da conta; a linha fica se a conta for excluída).
  Também troca a função do gatilho do limite de contatos (a trava antes de ler o plano) e os CHECKs de `documento`
  (CNPJ alfanumérico) de `empresas` e `contas`; o downgrade volta os dois (documento alfanumérico fica sem valor).
- **Adaptador** (`core/asaas.py`): httpx sem SDK, 20 s, sem redirecionamento, `User-Agent: Toqqi/1.0`; os testes
  trocam `asaas.transporte` por um `httpx.MockTransport` (o `conftest` bloqueia a rede). Falhas: `recusado` (400 →
  422 `cobranca_recusada`, CPF/CNPJ, e-mail e telefone no campo), `configuracao` (401/403, log de erro → 503),
  `nao_encontrado` (404), `indisponivel` (429, 5xx, tempo, rede → 503 `cobranca_indisponivel`). O log leva só método,
  caminho, status e códigos de erro do Asaas: nunca a chave, o CPF/CNPJ nem as descrições dos erros. Celular vai em
  `mobilePhone` e fixo em `phone`, sempre com o outro campo vazio (trocar um pelo outro apaga o antigo no Asaas). As
  listas pela referência (`GET /customers` e `GET /subscriptions` com `externalReference`) são paginadas e só aceitam
  os itens com a referência exata.
- **Situação da conta** (`modulos/assinatura/servico.recalcular`, chamada depois de assinar, trocar, cancelar, de cada
  aviso, da conferência e pela tarefa) e **liberada** (`modulos/assinatura/regras.liberada`: a única regra de envios,
  robô, lembretes, CSAT, IA e e-mails do painel; sai só da linha da conta, sem consulta a mais por requisição). Dias no
  fuso de São Paulo. Sem assinatura ativa: período pago valendo → `cancelada`; senão teste valendo → `teste`; senão já
  pagou → `cancelada`; senão `teste_expirado` (e quem fica sem assinatura sem nunca ter pago volta ao plano do teste,
  `profissional`). `teste` e `cancelada` ficam liberadas até o mais tarde entre o fim do teste e o fim do dia
  `pago_ate`; quem assinou no teste e ainda não pagou segue liberado até o fim do 7º dia depois do primeiro vencimento
  (o mesmo prazo de quando a tarefa marca `atrasada`: sem buraco). `conta.cobranca` em `/eu` e no login:
  `{liberada, assinada, pago_ate, atrasada_desde, pausa_em, aviso}`; `assinada` = tem assinatura ativa; o aviso
  `aguardando_pagamento` (quem já assinou e ainda não pagou; no teste, só a 5 dias do primeiro vencimento; sem teste
  válido, sempre) toma o lugar dos de teste e de cancelada.
- **Fonte da verdade é o Asaas**: o webhook só avisa; a API consulta a cobrança (`GET /payments/{id}`) com a conta
  travada antes de gravar (aviso fora de ordem, repetido ou forjado não muda nada). Erro ao processar → 200 mesmo assim,
  o aviso fica com `erro` e a tarefa tenta de novo depois de 2 minutos: até 5 tentativas, mas o Asaas fora do ar (ou a
  chave recusada) não gasta tentativa (a tarefa só para e retoma na próxima vez). Aviso de uma **assinatura
  desconhecida** não é ignorado: fica pendente, a API pergunta ao Asaas de quem ela é (cobrança → assinatura →
  referência `toqqi-conta-{id}`), espera o que estiver em andamento na conta (um assinar ainda gravando) e, se ela
  continua desconhecida, concilia a conta (log de erro). Sem resolver em 1 hora, fica ignorado (log de erro). Aviso de
  assinatura de outro sistema ou de outro ambiente → ignorado.
- **Nunca duas assinaturas vivas no Asaas** para a mesma conta (um tempo esgotado pode criar lá sem a API saber; o
  processo pode cair entre criar lá e gravar aqui):
  - assinar é feito em duas transações: (1) o cliente — o guardado deste ambiente, senão um já criado com a
    referência da conta (`GET /customers?externalReference=`), senão um novo; tempo esgotado ao criar → procura de novo
    —, gravado na conta; (2) a assinatura — antes de criar, lista as da referência da conta: a desconhecida com o valor
    pedido é adotada (sem criar outra) e as outras são removidas; tempo esgotado ao criar → lista de novo e adota a que
    chegou a ser criada (sem ela, 503);
  - se a gravação falhar depois de criar no Asaas, ela é removida lá; remoção que falha fica em `asaas_remocoes` e a
    tarefa tenta de novo (404 = já removida; até 20 vezes, depois log de erro). Uma assinatura com a remoção pendente
    nunca é adotada;
  - a conferência diária concilia cada conta (adota a desconhecida se a conta não tem assinatura ativa, não é cortesia e
    o valor é o de um plano; senão remove; remove também a cancelada aqui que segue viva lá), com auditoria
    (`assinatura_adotada`, `assinatura_removida_no_asaas`, gravidade atenção);
  - a exclusão de conta pela plataforma remove todas as vivas com a referência da conta (falhou → 503, nada é apagado).
- **Troca de plano**: tempo esgotado no `PUT` → a API lê a assinatura no Asaas; com o valor novo já lá, conclui aqui
  (200), senão 503. A conferência diária compara o valor do Asaas com o daqui e, se diferente, volta o do Asaas para o
  daqui (`PUT` com `updatePendingPayments`; auditoria `valor_realinhado`, atenção).
- **Tarefa `assinaturas`** (primeira em `tudo`, para a liberação valer antes dos envios): recalcula as contas que mudam
  pela data (teste que acabou; fatura pendente que passou do vencimento; período pago que acabou com o teste ainda
  valendo); com o Asaas configurado, descarta o que era de sandbox se a chave é de produção, tenta de novo as remoções
  pendentes, reprocessa avisos e, a partir das 6h, faz a **conferência diária** (uma vez por dia por conta com
  assinatura ativa ou cancelada há menos de 40 dias no ambiente atual, e por conta com cliente no Asaas ainda não
  conferida): concilia; lê a assinatura ativa — removida, `INACTIVE` ou `EXPIRED` → cancelada aqui; 404 → log de erro a
  cada dia e, no 3º dia seguido, cancelada aqui (auditoria com `motivo: nao_encontrada_no_asaas`, atenção); valor
  diferente → realinha —; busca as cobranças (pega webhook perdido); recalcula (também quando para no meio, com o
  Asaas fora) e verifica a sanidade (ativa, paga só até mais de 40 dias atrás e sem fatura em aberto → log de erro).
  Para no primeiro erro do Asaas. Sem `ASAAS_API_KEY`, só a parte das datas. Devolve `{testes_expirados,
  contas_de_outro_ambiente, remocoes_no_asaas, eventos_reprocessados, contas_conferidas}`.
- **Plataforma**: cortesia e exclusão de conta removem antes a assinatura no Asaas (falhou → 503 e nada muda);
  "+14 dias" → 409 `assinatura_ativa` com assinatura ativa ou cortesia, e recalcula a situação (com o período pago
  mais longo que o teste, a conta segue `cancelada` até ele acabar).

### Trocar a chave do sandbox para a produção
1. No Asaas de produção: gere a chave e crie o webhook (mesma URL, eventos de cobranças, v3) com um token novo.
2. No Render: troque `ASAAS_API_KEY` na **toqqi-api** (e no toqqi-tarefas, se o Cron Job estiver ligado) e
   `ASAAS_WEBHOOK_TOKEN` na toqqi-api, e reimplante.
3. Para a chave de produção, o que foi feito no sandbox não existe: a próxima execução da tarefa `assinaturas` (ou o
   próximo assinar da conta) cancela aqui a assinatura ativa de sandbox (sem chamar o Asaas), esquece o cliente de
   sandbox, zera `pago_ate` e `atrasada_desde` (pagamento de sandbox não vale em produção), recalcula a conta e audita
   (`ambiente_asaas_trocado`, atenção). Quem tinha assinado no sandbox assina de novo (cliente e assinatura novos em
   produção). O histórico de cobranças de sandbox fica no banco, mas não aparece mais.
4. O contrário (chave de sandbox com dados de produção, por engano) não apaga nada: a tarefa registra um log de erro
   a cada execução, as assinaturas de produção ficam como estão (sem conferência) e assinar de novo responde 503 até a
   chave certa voltar.

### CNPJ alfanumérico
Desde 31/07/2026 a Receita emite CNPJ com 12 caracteres `[0-9A-Z]` + 2 dígitos verificadores (cada caractere vale o
código ASCII − 48; pesos 5,4,3,2,9,8,7,6,5,4,3,2 e 6,5,4,3,2,9,8,7,6,5,4,3,2; resto < 2 → 0, senão 11 − resto; ex.:
`12.ABC.345/01DE-35`). `core/texto.normalizar_documento` (e o tipo `Documento` das entradas) aceita máscara e
minúsculas e guarda em maiúsculas, sem pontuação, em empresas (e na busca), dados da empresa, integrações, importação
de empresas e assinatura; o CPF segue só com dígitos; as mensagens de erro não mudaram. Os CHECKs do banco
(`empresas`, `contas`, `assinaturas`) aceitam `^([0-9]{11}|[0-9A-Z]{12}[0-9]{2})$`. O documento vai para o Asaas
como está (`cpfCnpj` em maiúsculas): confira no sandbox que ele aceita um CNPJ alfanumérico.

### Limitação conhecida
As chamadas ao Asaas (até 20 s cada; assinar faz várias) acontecem com as travas da conta pegas (`assinatura:{conta}`,
a linha da conta em `FOR NO KEY UPDATE` — que não segura as inclusões que só apontam para a conta, como contatos e
respostas — e, enquanto o plano muda, a trava das inclusões de contatos). Com o Asaas lento, outra operação de
assinatura da mesma conta (e, ao assinar ou trocar de plano, a inclusão de contatos dela) espera.

### O que conferir no sandbox antes da produção
- `PUT /subscriptions/{id}` com `value` e `updatePendingPayments: true` muda também a fatura em aberto (a troca de
  plano e o realinhamento contam com isso).
- Primeiro vencimento nos dias 29, 30 e 31: em que dia caem as faturas dos meses mais curtos (a API calcula o período
  pago como vencimento + 1 mês − 1 dia, com o dia ajustado ao fim do mês).
- Os filtros `externalReference` de `GET /customers` e `GET /subscriptions` (a API confere a referência de cada item
  mesmo assim) e as situações `INACTIVE`/`EXPIRED` de uma assinatura.
- Um CNPJ alfanumérico em `cpfCnpj`; celular trocado por fixo (`mobilePhone` vazio) apaga o celular antigo.

### Asaas falso (desenvolvimento local)
`scripts/asaas_falso.py` é um FastAPI pequeno, em memória, com o que o adaptador usa (clientes, assinaturas, cobranças)
e rotas para simular o Asaas: cada uma manda o webhook (com `asaas-access-token`) para a API.
```bash
# terminal 1 (pasta api/): o Asaas falso na porta 8010
ASAAS_FALSO_WEBHOOK_TOKEN=token-local-do-webhook-com-32-caracteres-ou-mais python scripts/asaas_falso.py
# terminal 2: a API apontando para ele
ASAAS_URL=http://localhost:8010/v3 ASAAS_API_KEY=chave-local \
ASAAS_WEBHOOK_TOKEN=token-local-do-webhook-com-32-caracteres-ou-mais uvicorn toqqi.main:app --reload
```
Assine pela tela (ou `POST /api/v1/assinatura`); o link da fatura abre `http://localhost:8010/fatura/{id}`, com
botões para pagar (Pix, boleto, cartão). Também por `curl -X POST`:
`/simular/pagar/{payment_id}?forma=PIX|BOLETO|CREDIT_CARD`, `/simular/vencer/{payment_id}`,
`/simular/estornar/{payment_id}`, `/simular/proxima/{subscription_id}` (fatura do mês seguinte),
`/simular/inativar/{subscription_id}?status=INACTIVE|EXPIRED` (sem aviso), `/simular/reenviar/{evento_id}` (aviso
repetido) e `GET /simular/estado`. Aceita também as listas pela referência (`GET /v3/customers` e
`GET /v3/subscriptions` com `externalReference`) e `GET /v3/customers/{id}`. `ASAAS_FALSO_WEBHOOK_URL` (padrão
`http://localhost:8000/api/v1/asaas/webhook`), `ASAAS_FALSO_URL` (padrão `http://localhost:8010`) e
`ASAAS_FALSO_PORTA` mudam os endereços. Os testes usam o mesmo Asaas falso atrás do adaptador (`asaas_falso` no
`conftest`, `tests/test_asaas_integrado.py` com o fluxo inteiro).

### Etapa 5a: decisões tomadas aqui (além da seção 0 do contrato)
- **Carência só para quem estava coberto**: a fatura vencida dá os 7 dias de `atrasada` (e "já houve cobrança paga" vale
  `ativa`) só se a assinatura começou coberta — pelo teste (assinou durante ele) ou por um período pago que ela continua
  (assinou de novo antes do fim do `pago_ate`) — ou se ela já teve fatura paga. Quem assina sem teste válido e não paga
  fica `teste_expirado` (ou `cancelada`, se já pagou um dia), sem envios até pagar ("os envios voltam quando o pagamento
  for confirmado"); sem isso, atrasar o pagamento liberaria os envios.
- **Fatura pendente com o vencimento passado conta como em atraso** (`atrasada_desde`) e sai como `vencida` na tela: o
  Asaas só marca `OVERDUE` de madrugada, e a tarefa recalcula na virada do dia (sem buraco entre o fim do teste e o aviso).
- O teste "estica" até o fim da carência da primeira fatura (7 dias depois do primeiro vencimento) só para quem assinou
  durante o teste (primeiro vencimento até o último dia dele); quem assina depois começa sem envios.
- Colunas a mais que o contrato não listava: `contas.primeiro_vencimento` (cópia do da assinatura ativa),
  `contas.asaas_ambiente`, `contas.asaas_conferida_em` (conferência diária, por conta), `assinaturas.ambiente`,
  `assinaturas.nao_encontrada_desde`, `asaas_eventos.ignorado` e `asaas_eventos.assinatura_asaas_id`; a tabela
  `asaas_remocoes`.
- `pago_ate` nunca diminui (estorno não tira o período já coberto); o estorno é auditado.
- `assinatura` (em `GET /assinatura` e na plataforma) é só a ativa: depois de cancelar volta `null` (a tela mostra a
  situação `cancelada` da conta). `POST /assinatura` responde 201.
- Telefone de cobrança: regra brasileira estrita só nos dados de cobrança (DDD de 11 a 99; celular com 9 dígitos
  começando com 9, fixo com 8 começando com 2 a 5; "+1 415 555 0100" → 422); celular vai em `mobilePhone`, fixo em
  `phone` (sem o 55), o outro campo vazio.
- `dados_sugeridos`: razão social (ou o nome da conta), CPF/CNPJ e telefone dos dados da empresa (sem telefone, o do
  cadastro do admin), e-mail do admin. `pago_em` = dia do pagamento no Asaas às 12:00 de São Paulo.
- Erro 402 `limite_do_plano` (contatos) e o 422 de assinar/trocar levam `campos.limite`.
- Situações do Asaas que o contrato não citava: `DUNNING_REQUESTED` → vencida, `DUNNING_RECEIVED` → paga; desconhecida
  mantém a situação local (log de aviso).
- Exclusão de conta pela plataforma também remove as assinaturas vivas da conta no Asaas (senão ele seguiria cobrando).
- A conferência diária também lê a assinatura no Asaas (`GET /subscriptions/{id}`): removida lá (`deleted: true`,
  `INACTIVE` ou `EXPIRED`) → cancelada aqui (auditoria com `motivo: removida_no_asaas`); 404 → cancelada só no 3º dia
  seguido.
- Assinatura desconhecida com a referência de uma conta que não existe aqui: só o log de erro (nada é removido no
  Asaas por um aviso). Com a chave de sandbox e dados de produção, nada é apagado (ver "Trocar a chave").
- Quem fica sem assinatura sem nunca ter pago volta ao plano `profissional` (o do teste), em qualquer caminho
  (cancelar, removida no Asaas, troca de ambiente).

## Estrutura
```
toqqi/
  main.py                 create_app, CORS, id da requisição, handlers de erro, auto-migração
  modelos.py              modelos ORM
  apresentacao.py         formato JSON de Usuario e Conta
  core/                   config, db (em_conta / modo_sistema), security (argon2id, JWT, tokens), relogio,
                          errors, validacao, email, rate_limit, auditoria, permissoes, deps (requer),
                          texto (telefone, CNPJ/CPF, valores, datas), planos, paginacao, filtros, rede,
                          ia (adaptador da OpenAI e provedor de testes), asaas (adaptador do Asaas)
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
  modulos/ia/             IA por resposta: quem passa, fila, reserva, teto do mês, configuração da conta
  modulos/relatorios/     relatórios, picos de reclamação, alerta de pico e resumo semanal por e-mail
  modulos/assinatura/     planos, assinatura e cobranças (Asaas), situação da conta e "liberada", webhook,
                          conciliação e conferência diária (tarefa)
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
alembic/versions/0007_ia_relatorios.py   IA por resposta, reclamação/elogio por tema, uso da IA, picos, resumos + RLS
alembic/versions/0008_assinaturas.py   cobrança em `contas`, assinaturas, cobranças e avisos do Asaas + RLS
scripts/asaas_falso.py             Asaas falso (desenvolvimento local e testes)
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
