# Toqqi API · etapas 1 e 2

FastAPI + SQLAlchemy 2 (psycopg 3) + Alembic + PostgreSQL 16.
Contratos implementados (base `/api/v1`):
- `../docs/api-etapa-1.md`: acesso, equipe, sessões, auditoria;
- `../docs/api-etapa-2.md`: cadastros auxiliares, responsáveis, empresas, contatos, importação de planilha,
  formulários (modelos, resultados, CSV) e páginas públicas de pesquisa.

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
| `API_PUBLIC_URL` | Endereço público da API |
| `ALLOWED_ORIGINS` | Origens liberadas no CORS, separadas por vírgula |
| `EMAIL_PROVIDER` | `console` (imprime), `memory` (testes), `zeptomail` ou `resend` |
| `ZEPTOMAIL_TOKEN` / `RESEND_API_KEY` | Credenciais do provedor de e-mail |
| `EMAIL_FROM` | Remetente, ex.: `Toqqi <nao-responda@toqqi.com>` |
| `SUPERADMIN_EMAILS` | E-mails com acesso à área `/plataforma`, separados por vírgula |
| `RATE_LIMIT_ENABLED` | `0` desliga o limite de tentativas (usado nos testes) |

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
- **Convites**: o token só aparece no link; o banco guarda o sha256 (`convites.token_hash`). A etapa 3 cria
  convites com `toqqi.modulos.respostas.convites.criar_convite(sessao, formulario_id, contato_id=..., canal=...)`.
- **Resposta registrada**: toda resposta nova passa por `toqqi.modulos.respostas.eventos.ao_registrar_resposta`
  (lista `GANCHOS`, vazia por enquanto), na mesma transação da gravação.
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

## Estrutura
```
toqqi/
  main.py                 create_app, CORS, id da requisição, handlers de erro, auto-migração
  modelos.py              modelos ORM
  apresentacao.py         formato JSON de Usuario e Conta
  core/                   config, db (em_conta / modo_sistema), security (argon2id, JWT, tokens),
                          errors, validacao, email, rate_limit, auditoria, permissoes, deps (requer),
                          texto (telefone, CNPJ/CPF, valores, datas), planos, paginacao, filtros, rede
  modulos/acesso/         cadastro, entrar, sair, confirmar, reenviar, esqueci, redefinir, pedir-acesso, /eu
  modulos/equipe/         usuários da conta e matriz de permissões
  modulos/conta/          segurança: duração da sessão e domínios liberados
  modulos/auditoria/      registro de atividades
  modulos/plataforma/     área do superadmin
  modulos/cadastros/      grupos, segmentos, perfis, cargos e responsáveis (teste do Teams)
  modulos/empresas/       empresas (clientes da conta)
  modulos/contatos/       contatos e link de pesquisa manual
  modulos/importacao/     leitura de planilhas, nomes equivalentes, conferir e importar
  modulos/formularios/    modelos prontos, validação das perguntas, padrões, resultados, CSV
  modulos/respostas/      convites, validação/gravação de respostas, variáveis, "resposta registrada"
  modulos/publico/        páginas públicas (convite e link público)
alembic/versions/0001_inicial.py   esquema da etapa 1 + RLS + GRANTs
alembic/versions/0002_cadastros_formularios.py   tabelas da etapa 2 + RLS + limite do plano + dados iniciais
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
