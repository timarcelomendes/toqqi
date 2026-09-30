# Toqqi API · etapa 1 (acesso, equipe, sessões, auditoria)

FastAPI + SQLAlchemy 2 (psycopg 3) + Alembic + PostgreSQL 16.
Contrato implementado: `../docs/api-etapa-1.md` (base `/api/v1`).

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
tokens de e-mail, cadastro, pedido de acesso, checagem de domínio de outra conta e área da plataforma.

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

## Testes
```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```
Usam o banco real `toqqi_test`: o esquema é recriado e migrado com o papel dono
(`TEST_OWNER_DATABASE_URL`, padrão `toqqi:toqqi`) e a aplicação conecta como `toqqi_app`
(`TEST_DATABASE_URL`), então o RLS é exercitado de verdade. E-mails vão para a caixa em memória.

## Estrutura
```
toqqi/
  main.py                 create_app, CORS, id da requisição, handlers de erro, auto-migração
  modelos.py              modelos ORM
  apresentacao.py         formato JSON de Usuario e Conta
  core/                   config, db (em_conta / modo_sistema), security (argon2id, JWT, tokens),
                          errors, validacao, email, rate_limit, auditoria, permissoes, deps (requer)
  modulos/acesso/         cadastro, entrar, sair, confirmar, reenviar, esqueci, redefinir, pedir-acesso, /eu
  modulos/equipe/         usuários da conta e matriz de permissões
  modulos/conta/          segurança: duração da sessão e domínios liberados
  modulos/auditoria/      registro de atividades
  modulos/plataforma/     área do superadmin
alembic/versions/0001_inicial.py   esquema completo + RLS + GRANTs
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
