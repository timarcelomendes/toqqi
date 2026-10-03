# Toqqi · Backup do banco

Todo dia, uma cópia criptografada do banco de produção vai para o Cloudflare R2 e é restaurada num banco de teste, para
provar que a cópia funciona. Aqui está o que roda, o que você configura uma vez, como restaurar numa emergência e o que
fazer se o backup falhar.

## 1. O que roda e quando
A rotina do GitHub **Backup do banco** (`.github/workflows/backup.yml`) roda todo dia às **03:23 em Brasília** (06:23 UTC) e
quando você clica em *Actions › Backup do banco › Run workflow*. Ela executa `scripts/backup/backup.sh`, que:

1. copia o banco inteiro (`pg_dump`) numa foto única, lendo todas as contas;
2. criptografa a cópia com a senha `BACKUP_PASSPHRASE` (gpg, AES256);
3. envia ao R2, em `toqqi/AAAA/MM/toqqi-AAAA-MM-DDTHHMMSSZ.dump.gpg`;
4. baixa a cópia de volta, decifra e restaura num PostgreSQL 16 vazio (um serviço descartável do GitHub);
5. confere que as tabelas, a versão das migrações (`alembic_version`) e o número de linhas de cada tabela são os mesmos do banco,
   na mesma foto. Termina com `ok: N tabelas conferidas`;
6. apaga as cópias com mais de 30 dias, sempre deixando as 7 mais novas (se o backup parar por semanas, as últimas não somem).

Se algum passo falhar, a rotina fica vermelha e a cópia do dia é apagada do R2: **só ficam no R2 cópias que foram restauradas
com sucesso**. O GitHub avisa por e-mail quem mudou por último a linha `cron` do arquivo `backup.yml` (confira em *Settings ›
Notifications › Actions*, na conta dessa pessoa, que o aviso de execuções com falha está ligado).

O repositório é público e o log também. Por isso o script não escreve nada do banco: nem dados, nem número de linhas; só nomes de
tabelas quando algo não bate. As mensagens de erro das ferramentas (que podem trazer valores) ficam fora do log, e a rotina não
guarda artefatos nem cache.

**Não entram na cópia:** os papéis e senhas do PostgreSQL, as variáveis do painel do Render (`SEGREDOS_KEY`, `JWT_SECRET`, chaves
de API) e o código (está no GitHub). Veja a seção 3, passo 7, sobre guardar as variáveis.

## 2. Configurar (uma vez)

### 2.1 Cloudflare (R2)
1. **R2 Object Storage › Create bucket.** Nome, por exemplo, `toqqi-backups`. Deixe **privado** (não ligue o acesso público).
2. Copie o **Account ID** (na tela inicial do R2): é o `R2_ACCOUNT_ID`.
3. **R2 › Manage API Tokens › Create API token.** Permissão **Object Read & Write**, restrita a esse bucket (*Specify bucket*).
   Ao criar, o Cloudflare mostra o **Access Key ID** e o **Secret Access Key** uma única vez: copie os dois.
4. No bucket, **Settings › Object lifecycle rules › Add rule**: prefixo `toqqi/`, apagar objetos **35 dias** depois de criados.
   É uma rede de segurança caso a limpeza do script não funcione. Atenção: essa regra não conta cópias; se o backup ficar
   vermelho por mais de cinco dias, resolva antes que as cópias antigas desapareçam.

(Os nomes dos botões podem mudar um pouco; o que vale é: bucket privado, token só desse bucket, regra de 35 dias.)

### 2.2 Render
1. No banco (`toqqi-db`), copie a **External Database URL**. Ela traz usuário e senha do dono do banco: é segredo.
   Use a do dono do banco (a mesma conta que roda as migrações), nunca a do `toqqi_app`.
2. Em *Access Control* (ou *Networking*) do banco, confira que as conexões externas são aceitas de **qualquer IP**
   (`0.0.0.0/0`). O GitHub não tem IP fixo, então não dá para liberar só o dele.

### 2.3 GitHub
1. Gere a senha da criptografia no terminal: `openssl rand -base64 48`. **Guarde uma cópia no gerenciador de senhas agora.**
   **Sem essa senha as cópias são inúteis**, e o GitHub não mostra um segredo depois de salvo.
2. *Settings › Secrets and variables › Actions › New repository secret*, um para cada linha:

| Segredo | O que é |
|---|---|
| `BACKUP_DATABASE_URL` | External Database URL do banco no Render (usuário dono) |
| `BACKUP_PASSPHRASE` | a senha do passo 1 |
| `R2_ACCOUNT_ID` | Account ID do Cloudflare |
| `R2_BUCKET` | nome do bucket (`toqqi-backups`) |
| `R2_ACCESS_KEY_ID` | Access Key ID do token do R2 |
| `R2_SECRET_ACCESS_KEY` | Secret Access Key do token do R2 |

3. Com o `backup.yml` já no ramo principal (o agendamento e o botão só passam a existir lá), rode **Actions › Backup do banco ›
   Run workflow** e espere ficar verde. No log, o fim tem que ser `ok: N tabelas conferidas` e `Backup concluído: toqqi/…`.
   Se aparecer `Backup ainda não configurado`, falta criar os segredos (verde não quer dizer que o backup rodou);
   `configurado pela metade` diz quais faltam. Confira também que o arquivo apareceu no bucket.
4. Faça o **ensaio de restauração** da seção 4 uma vez, antes do lançamento.

## 3. Emergência: restaurar num banco novo do Render
Perde-se só o que foi gravado depois da última cópia (até um dia). Você precisa do computador com `psql` e `pg_restore` **do
PostgreSQL 16** (`pg_restore --version` mostra 16), `gpg` e o `aws` (AWS CLI v2), da senha do gerenciador de senhas e das chaves do
token do R2 (se perdeu, crie outro token com a mesma permissão).

**1. Banco novo.** No Render, crie um PostgreSQL 16 novo (mesma região da API). Não restaure por cima do antigo. Copie a
*External Database URL* do novo:
```bash
export NOVO='postgresql://...'
```

**2. Escolher e baixar a cópia.** Uma cópia só está no R2 se passou na conferência; use a mais recente.
```bash
export AWS_ACCESS_KEY_ID='...' AWS_SECRET_ACCESS_KEY='...'
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
R2="https://SEU_ACCOUNT_ID.r2.cloudflarestorage.com"
aws s3 ls s3://SEU_BUCKET/toqqi/ --recursive --endpoint-url "$R2" --region auto      # a última linha é a mais nova
aws s3 cp s3://SEU_BUCKET/toqqi/AAAA/MM/ARQUIVO.dump.gpg copia.dump.gpg --endpoint-url "$R2" --region auto
```

**3. Decifrar** (pede a senha do gerenciador de senhas) **e conferir o arquivo.**
```bash
gpg --output copia.dump --decrypt copia.dump.gpg
pg_restore --list copia.dump > /dev/null && echo "arquivo ok"
```

**4. Restaurar.** Tudo ou nada: se der erro, nada fica no banco novo e a mensagem diz o motivo. O `PGOPTIONS` liga o modo sistema do
RLS; para restaurar não faz diferença (os dados entram antes de o RLS ser ligado), mas é ele que deixa o dono do banco *ler* as
tabelas depois (passo 6).
```bash
PGOPTIONS='-c app.sistema=on' pg_restore --no-owner --no-acl --exit-on-error --single-transaction --dbname="$NOVO" copia.dump
```
`--no-owner --no-acl` fazem a restauração não depender de nenhum papel do banco antigo: só existe o dono do banco novo.

**5. Papel da API.** A cópia não leva as permissões do `toqqi_app`, e a API, ao subir, só cria o papel e acerta a senha: ela não
refaz as permissões das tabelas (as migrações já estão aplicadas). Sem este passo a API sobe e toda consulta falha com
`permission denied`. Cole inteiro:
```bash
psql "$NOVO" -v ON_ERROR_STOP=1 <<'SQL'
-- papel restrito da API; a API troca a senha dele para a APP_DB_PASSWORD quando subir
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'toqqi_app') THEN
    CREATE ROLE toqqi_app WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD 'provisoria-a-API-troca';
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO toqqi_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO toqqi_app;
REVOKE ALL ON TABLE alembic_version FROM toqqi_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO toqqi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO toqqi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO toqqi_app;
SQL
```
(É o que as migrações fazem. Se uma migração futura der permissões diferentes a alguma tabela, ajuste este bloco. Se mudou
`APP_DB_ROLE`, troque o nome.)

**6. Conferir.**
```bash
PGOPTIONS='-c app.sistema=on' psql "$NOVO" -c "SELECT version_num FROM alembic_version" \
  -c "SELECT count(*) AS contas FROM contas" -c "SELECT count(*) AS usuarios FROM usuarios"
```
A versão tem que ser a das migrações mais recentes em `api/alembic/versions` (ou anterior: a API aplica as que faltarem ao subir).

**7. Apontar o Render para o banco novo.**
- Na `toqqi-api` (*Environment*), `DATABASE_URL` = a **Internal Database URL** do banco novo. Se a API foi criada pelo Blueprint, essa
  variável vem do banco `toqqi-db`: se o banco novo tiver outro nome, ajuste o nome em `render.yaml` (`databases` e `fromDatabase`),
  senão o próximo *Sync* do Blueprint volta ao antigo.
- Não mude `APP_DB_PASSWORD`, `SEGREDOS_KEY` nem `JWT_SECRET`. Sem a `SEGREDOS_KEY` de antes, os tokens do WhatsApp e os
  segredos dos webhooks gravados na cópia não abrem (é preciso cadastrar de novo); sem o `JWT_SECRET`, os links de descadastro e
  de convite já enviados deixam de valer. **Guarde uma cópia das duas no gerenciador de senhas** (*toqqi-api › Environment*):
  se o serviço for perdido junto com o banco, elas só existem lá.
- *Manual Deploy › Deploy latest commit*. No log da API devem aparecer `Papel restrito toqqi_app pronto` e `Aplicando migrações`.
  Teste `https://toqqi-api.onrender.com/api/v1/saude` e entre no site.
- No GitHub, troque o segredo `BACKUP_DATABASE_URL` pela External URL do banco novo, senão o backup de amanhã falha.
- Quando tudo estiver certo, apague o banco antigo e os arquivos `copia.dump*` do seu computador (têm dados de clientes).

## 4. Ensaio de restauração
Faça uma vez antes do lançamento e depois a cada três meses (ponha no calendário). É a seção 3, passos 2 a 6, num banco de teste, e
serve para provar que **a senha guardada no gerenciador de senhas abre as cópias**:

1. Banco de teste: um PostgreSQL 16 vazio, no Render por uma hora ou na sua máquina (`docker run --rm -e POSTGRES_PASSWORD=teste -p
   5433:5432 postgres:16`, com `NOVO='postgresql://postgres:teste@localhost:5433/postgres'`).
2. No passo 3, **digite a senha do gerenciador de senhas**; não copie do GitHub. Se o `gpg` abrir o arquivo, a senha guardada está certa.
3. Siga até o passo 6. Pule o passo 5 se o banco de teste não for ligar na API.
4. Apague o banco de teste e os arquivos `copia.dump*`.

Para rodar o script inteiro na sua máquina (por exemplo, depois de mexer nele), com um banco vazio para a restauração e as mesmas
variáveis dos segredos:
```bash
docker run -d --name restauro -e POSTGRES_PASSWORD=teste -p 5433:5432 postgres:16
export BACKUP_DATABASE_URL='...' BACKUP_PASSPHRASE='...' R2_ACCOUNT_ID='...' R2_BUCKET='...' R2_ACCESS_KEY_ID='...' R2_SECRET_ACCESS_KEY='...'
export RESTAURACAO_DATABASE_URL='postgresql://postgres:teste@localhost:5433/postgres'
bash scripts/backup/backup.sh
docker rm -f restauro
```
Opcionais: `BACKUP_DESTINO=local:/pasta` copia para uma pasta em vez do R2 (não precisa das variáveis `R2_*`);
`RESTAURACAO_PASSPHRASE` é a senha usada para decifrar no teste (padrão: a mesma `BACKUP_PASSPHRASE`; ponha a do gerenciador de
senhas para conferi-la); `BACKUP_DETALHES=1` mostra os erros das ferramentas (só funciona fora do GitHub). O banco de restauração
precisa estar vazio, e o script recusa um que não esteja.

## 5. Se o backup falhar
A mensagem aparece em vermelho no fim do log. As mais comuns:

| Mensagem | O que fazer |
|---|---|
| `Backup ainda não configurado` | Faltam os segredos (seção 2.3). Não é erro, mas também não há backup. |
| `configurado pela metade: faltam …` | Crie os segredos que a mensagem lista. |
| `Não consegui conectar no banco de origem` | `BACKUP_DATABASE_URL` errada ou trocada (o banco mudou?), ou o Render não aceita conexões externas (2.2). |
| `Não consegui ler o banco de origem` | A URL é de outro usuário que não o dono (por exemplo, o `toqqi_app`), ou o banco está em manutenção. |
| `O pg_dump é da versão X e o banco de origem é PostgreSQL Y` | O Render mudou a versão do PostgreSQL. Troque `postgres:16` e `postgresql-client-16` no `backup.yml` pela nova. |
| `Estas tabelas têm RLS sem política para o modo sistema` | Uma tabela nova foi criada com RLS sem a política `... OR app_sistema()`. Corrija a migração; sem isso o backup não enxerga as linhas. |
| `Não consegui enviar a cópia ao destino` | Token, bucket ou Account ID errados; token revogado ou sem permissão de escrita (2.1). |
| `Não consegui decifrar a cópia baixada` | `BACKUP_PASSPHRASE` mudou entre o envio e a conferência, ou o arquivo veio corrompido. |
| `A restauração não bate com a origem nestas tabelas` | O nome da tabela vem na mensagem. Rode o script na sua máquina com `BACKUP_DETALHES=1` (seção 4) e avise quem cuida do código. |
| `A restauração num banco vazio falhou` | Idem: o motivo só aparece rodando na sua máquina com `BACKUP_DETALHES=1`. |
| `não consegui limpar as cópias antigas` | A cópia de hoje está boa. O token precisa poder listar e apagar objetos do bucket. |

Para trocar a `BACKUP_PASSPHRASE`: as cópias antigas só abrem com a senha antiga. Guarde as duas no gerenciador de senhas até a
última cópia antiga sair do R2 (35 dias).

**Backup que parou sem aviso.** O GitHub desliga rotinas agendadas de repositório público depois de 60 dias sem commits (avisa por
e-mail; religue em *Actions › Backup do banco*). No primeiro dia do mês, abra o bucket e veja se existe uma cópia de ontem.

## 6. Para quem mexe no código
- **RLS.** Todas as tabelas têm `FORCE ROW LEVEL SECURITY`, e a política libera tudo quando `app.sistema` é `on` (`app_sistema()`,
  em `api/alembic/versions/0001_inicial.py`). O `pg_dump` roda como dono do banco com `PGOPTIONS='-c app.sistema=on'` e
  `--enable-row-security`. Sem o `PGOPTIONS`, as tabelas saem **vazias** (e sem o `--enable-row-security`, o `pg_dump` falha). Por
  isso o script confere, antes de copiar, que toda tabela com RLS tem uma política que libera o modo sistema.
- **Foto única.** Uma sessão do `psql` abre uma transação `REPEATABLE READ`, exporta a foto (`pg_export_snapshot`), conta as linhas de
  cada tabela e roda o `pg_dump --snapshot` dentro dela. Assim o número de linhas da origem é exato mesmo com o sistema no ar, e a
  restauração tem que ser igual a ele.
- **Restauração.** `pg_restore --no-owner --no-acl --exit-on-error --single-transaction`, sem depender de papéis. As permissões do
  `toqqi_app` voltam pelo bloco SQL da seção 3 (passo 5).
- **Segredos nunca na linha de comando** do gpg (a senha entra por descritor de arquivo); temporários em `RUNNER_TEMP` com
  `umask 077`, apagados na saída.
- **Retenção.** Só mexe em nomes `toqqi/AAAA/MM/toqqi-AAAA-MM-DDTHHMMSSZ.dump.gpg`: apaga os de mais de 30 dias que não estejam
  entre os 7 mais novos.
