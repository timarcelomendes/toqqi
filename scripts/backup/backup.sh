#!/usr/bin/env bash
# Backup diário do banco do Toqqi (PostgreSQL 16 no Render) para o Cloudflare R2.
# Roda no GitHub (.github/workflows/backup.yml) e também na sua máquina. Guia completo: docs/backup.md.
#
# O que faz, nesta ordem:
#   1. copia o banco inteiro (pg_dump) numa foto única, lendo todas as contas (modo sistema do RLS);
#   2. criptografa com a senha BACKUP_PASSPHRASE (gpg, AES256);
#   3. envia ao R2 (ou a uma pasta local, em BACKUP_DESTINO=local:/pasta, para testar);
#   4. baixa a cópia de volta, decifra e restaura num banco vazio (RESTAURACAO_DATABASE_URL);
#   5. confere: mesmas tabelas, mesma versão das migrações e mesmo número de linhas em cada tabela;
#   6. apaga cópias com mais de 30 dias, sempre deixando pelo menos 7.
#
# Variáveis (no GitHub, são segredos do repositório; veja docs/backup.md):
#   BACKUP_DATABASE_URL       endereço externo do banco no Render (usuário dono, não o toqqi_app)
#   BACKUP_PASSPHRASE         senha da criptografia (gere com: openssl rand -base64 48)
#   R2_ACCOUNT_ID             ID da conta no Cloudflare
#   R2_BUCKET                 nome do bucket do R2
#   R2_ACCESS_KEY_ID          chave de acesso do token do R2
#   R2_SECRET_ACCESS_KEY      chave secreta do token do R2
#   RESTAURACAO_DATABASE_URL  banco PostgreSQL 16 VAZIO onde a cópia é restaurada para teste (no GitHub, um
#                             serviço postgres:16 descartável)
# Opcionais:
#   BACKUP_DESTINO            "r2" (padrão) ou "local:/pasta" (copia para a pasta; não precisa das variáveis R2_*)
#   RESTAURACAO_PASSPHRASE    senha usada para decifrar no teste (padrão: BACKUP_PASSPHRASE). Serve para provar que
#                             a senha guardada no seu gerenciador de senhas abre as cópias.
#   BACKUP_DETALHES=1         mostra os erros das ferramentas (só fora do GitHub; veja abaixo)
#
# Sem nenhuma das variáveis obrigatórias, avisa que o backup ainda não está configurado e sai sem erro.
# Com algumas, mas não todas, sai com erro (configuração pela metade).
#
# O repositório é público, e os logs também: NADA do banco vai para a tela (nem contagens de linhas). A saída de
# erro das ferramentas (psql, pg_dump, pg_restore, gpg, aws) fica em arquivos temporários, que podem trazer valores
# das linhas, e só é mostrada com BACKUP_DETALHES=1 fora do GitHub Actions. Nunca use `set -x` aqui.
set -euo pipefail
set +x
umask 077
export LC_ALL=C

# ---------------------------------------------------------------------------------------------------------------
# Mensagens
# ---------------------------------------------------------------------------------------------------------------
EM_ACTIONS="${GITHUB_ACTIONS:-}"
TMP=""             # pasta temporária (apagada na saída)
OBJETO_ENVIADO=""  # chave da cópia enviada nesta execução
CONFERIDO=0        # 1 depois que a cópia passou em todas as conferências

info() { printf '%s\n' "$*"; }
aviso() {
  if [[ -n $EM_ACTIONS ]]; then printf '::warning::%s\n' "$*"; else printf 'AVISO: %s\n' "$*" >&2; fi
}
erro() {
  if [[ -n $EM_ACTIONS ]]; then printf '::error::%s\n' "$*"; else printf 'ERRO: %s\n' "$*" >&2; fi
}
falhar() { erro "$*"; exit 1; }

# Erros das ferramentas: só na sua máquina e só com BACKUP_DETALHES=1 (no GitHub o log é público).
mostrar_detalhes() {
  local arquivo
  for arquivo in "$@"; do
    if [[ -n ${BACKUP_DETALHES:-} && -z $EM_ACTIONS && -s $arquivo ]]; then
      printf -- '--- detalhes (só aparecem na sua máquina) ---\n' >&2
      cat "$arquivo" >&2
      printf -- '---\n' >&2
    fi
  done
}

# Nomes de tabelas para mostrar: só letras, números, "_" e ".".
nomes_seguros() { tr -c 'A-Za-z0-9_.\n' '?'; }

# ---------------------------------------------------------------------------------------------------------------
# Saída: apaga os temporários; se a cópia já foi enviada e não passou na conferência, tira do destino
# ---------------------------------------------------------------------------------------------------------------
limpar() {
  local codigo=$?
  trap - EXIT
  set +e
  if (( codigo != 0 )) && [[ -n $OBJETO_ENVIADO ]] && (( CONFERIDO != 1 )); then
    if destino_apagar "$OBJETO_ENVIADO" >/dev/null 2>&1; then
      aviso "A cópia enviada nesta execução não passou na conferência e foi apagada do destino."
    else
      aviso "A cópia enviada nesta execução ($OBJETO_ENVIADO) não passou na conferência e NÃO foi apagada do destino: não use essa."
    fi
  fi
  if [[ -n $TMP && -d $TMP ]]; then
    GNUPGHOME="$TMP/gnupg" gpgconf --kill gpg-agent >/dev/null 2>&1
    rm -rf "$TMP"
  fi
  exit "$codigo"
}

# ---------------------------------------------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------------------------------------------
verificar_configuracao() {
  local destino="${BACKUP_DESTINO:-r2}" v presentes=0 faltam=""
  local lista="BACKUP_DATABASE_URL BACKUP_PASSPHRASE"
  case $destino in
    r2) lista="$lista R2_ACCOUNT_ID R2_BUCKET R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY" ;;
    local:?*) ;;
    *) falhar "BACKUP_DESTINO inválido: use r2 ou local:/pasta." ;;
  esac
  for v in $lista; do
    if [[ -n ${!v:-} ]]; then presentes=$((presentes + 1)); else faltam="$faltam $v"; fi
  done
  if (( presentes == 0 )); then
    info "Backup ainda não configurado: os segredos do repositório não foram criados. Nada a fazer (veja docs/backup.md)."
    exit 0
  fi
  if [[ -n $faltam ]]; then
    falhar "Backup configurado pela metade: faltam$faltam (veja docs/backup.md)."
  fi
  if [[ -z ${RESTAURACAO_DATABASE_URL:-} ]]; then
    falhar "RESTAURACAO_DATABASE_URL não definida: sem um banco vazio para restaurar, a cópia não pode ser testada."
  fi
}

verificar_ferramentas() {
  local f
  for f in psql pg_dump pg_restore gpg gpgconf awk cmp sed tr sort mktemp date find; do
    command -v "$f" >/dev/null 2>&1 || falhar "Falta o programa '$f' (veja docs/backup.md)."
  done
  if ! destino_local; then
    command -v aws >/dev/null 2>&1 || falhar "Falta o AWS CLI ('aws'), usado para falar com o R2 (veja docs/backup.md)."
  fi
}

# Um Enter colado no fim do segredo não conta; no meio, sim (o gpg leria só até ele).
aparar_senha() {
  local senha=$1
  senha=${senha%$'\n'}
  senha=${senha%$'\r'}
  printf '%s' "$senha"
}

verificar_senha() {
  local senha
  senha=$(aparar_senha "$BACKUP_PASSPHRASE")
  case $senha in
    *$'\n'* | *$'\r'*) falhar "BACKUP_PASSPHRASE tem quebra de linha no meio. Gere de novo com: openssl rand -base64 48" ;;
  esac
  if (( ${#senha} < 20 )); then
    falhar "BACKUP_PASSPHRASE é curta demais (mínimo 20 caracteres). Gere uma com: openssl rand -base64 48"
  fi
  BACKUP_PASSPHRASE=$senha
  RESTAURACAO_PASSPHRASE=$(aparar_senha "${RESTAURACAO_PASSPHRASE:-$senha}")
}

# ---------------------------------------------------------------------------------------------------------------
# Endereços do banco
# ---------------------------------------------------------------------------------------------------------------
host_da_url() {
  local r=${1#*://}
  r=${r%%[/?#]*}   # só usuário:senha@host:porta
  r=${r##*@}
  if [[ $r == \[* ]]; then r=${r#\[}; r=${r%%\]*}; else r=${r%%:*}; fi
  printf '%s' "$r"
}

host_local() {
  case ${1:-} in
    "" | localhost | 127.* | ::1 | /*) return 0 ;;
    *) return 1 ;;
  esac
}

# host:porta/banco, para saber se dois endereços apontam para o mesmo banco.
identidade_da_url() {
  local u=${1#*://} autoridade restante hostporta porta=5432 banco
  autoridade=${u%%[/?#]*}
  restante=${u#"$autoridade"}
  restante=${restante#/}
  banco=${restante%%[?#]*}
  hostporta=${autoridade##*@}
  if [[ $hostporta == \[*\]:* ]]; then porta=${hostporta##*]:}
  elif [[ $hostporta != \[* && $hostporta == *:* ]]; then porta=${hostporta##*:}; fi
  printf '%s:%s/%s' "$(printf '%s' "$(host_da_url "$1")" | tr '[:upper:]' '[:lower:]')" "$porta" "$banco"
}

# Aceita o endereço como o Render entrega. Só acrescenta sslmode=require se não houver sslmode e o host não for local.
normalizar_url() {
  local u=$1
  u=${u//[$'\r\n\t ']/}
  case $u in
    postgres://* | postgresql://*) ;;
    postgres+*://* | postgresql+*://*) u="postgresql://${u#*://}" ;;   # postgresql+psycopg:// (formato da API)
    *) return 1 ;;
  esac
  if [[ $u != *sslmode=* ]] && ! host_local "$(host_da_url "$u")"; then
    if [[ $u == *\?* ]]; then u="$u&sslmode=require"; else u="$u?sslmode=require"; fi
  fi
  printf '%s' "$u"
}

# No GitHub, o que for derivado do endereço e não aparecer inteiro nos segredos também fica escondido do log.
esconder_no_log() {
  [[ -n $EM_ACTIONS ]] || return 0
  local u=${1#*://} credenciais senha host
  credenciais=${u%%[/?#]*}
  if [[ $credenciais == *@* ]]; then
    credenciais=${credenciais%%@*}
    if [[ $credenciais == *:* ]]; then
      senha=${credenciais#*:}
      [[ -z $senha ]] || printf '::add-mask::%s\n' "$senha"
    fi
  fi
  host=$(host_da_url "$1")
  host_local "$host" || printf '::add-mask::%s\n' "$host"
}

# ---------------------------------------------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------------------------------------------
major_da_ferramenta() { "$1" --version 2>/dev/null | sed -n 's/^[^0-9]*\([0-9][0-9]*\).*/\1/p' | head -n 1; }

# Conecta (3 tentativas, para aguentar um solavanco de rede) e imprime a versão principal do servidor.
major_do_servidor() {
  local url=$1 arquivo_erro=$2 numero tentativa
  for tentativa in 1 2 3; do
    if numero=$(psql -X -q -At "$url" -c 'SHOW server_version_num' 2>"$arquivo_erro") && [[ $numero =~ ^[0-9]+$ ]]; then
      printf '%s' $((numero / 10000))
      return 0
    fi
    (( tentativa == 3 )) || sleep 5
  done
  return 1
}

conferir_versoes() {
  local origem_major resto_major ferramenta cliente
  origem_major=$(major_do_servidor "$ORIGEM" "$TMP/erro-conexao-origem.txt") || {
    mostrar_detalhes "$TMP/erro-conexao-origem.txt"
    # Conecta sem o modo sistema? Então o banco (ou um pooler na frente dele) recusa o parâmetro de início.
    if PGOPTIONS='' psql -X -q -At "$ORIGEM" -c 'SELECT 1' >/dev/null 2>&1; then
      falhar "O banco de origem recusou a opção de conexão do modo sistema (app.sistema). Use a URL direta do banco, não a de um pooler (pgbouncer)."
    fi
    falhar "Não consegui conectar no banco de origem. Confira BACKUP_DATABASE_URL (tem que ser a External Database URL do Render, não a Internal) e se o Render aceita conexões externas (veja docs/backup.md)."
  }
  for ferramenta in pg_dump pg_restore psql; do
    cliente=$(major_da_ferramenta "$ferramenta")
    if [[ $cliente != "$origem_major" ]]; then
      falhar "O $ferramenta é da versão ${cliente:-?} e o banco de origem é PostgreSQL $origem_major: instale o postgresql-client-$origem_major (veja docs/backup.md)."
    fi
  done
  resto_major=$(major_do_servidor "$RESTAURACAO" "$TMP/erro-conexao-restauracao.txt") || {
    mostrar_detalhes "$TMP/erro-conexao-restauracao.txt"
    falhar "Não consegui conectar no banco de restauração (RESTAURACAO_DATABASE_URL)."
  }
  if [[ $resto_major != "$origem_major" ]]; then
    falhar "O banco de restauração é PostgreSQL $resto_major e o de origem é $origem_major: precisam ser da mesma versão."
  fi
}

# O dump só enxerga todas as linhas se cada tabela com RLS tiver uma política que libere o modo sistema.
conferir_politicas() {
  local sem_politica
  cat > "$TMP/politicas.sql" <<'SQL'
SELECT format('%I.%I', n.nspname, c.relname)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind IN ('r', 'p')
   AND c.relrowsecurity
   AND n.nspname NOT IN ('pg_catalog', 'information_schema')
   AND NOT EXISTS (SELECT 1
                     FROM pg_policy p
                    WHERE p.polrelid = c.oid
                      AND p.polpermissive
                      AND p.polcmd IN ('*', 'r')
                      AND pg_get_expr(p.polqual, p.polrelid) LIKE '%app\_sistema()%')
 ORDER BY 1;
SQL
  sem_politica=$(psql -X -q -At -v ON_ERROR_STOP=1 -f "$TMP/politicas.sql" "$ORIGEM" 2>"$TMP/erro-politicas.txt") || {
    mostrar_detalhes "$TMP/erro-politicas.txt"
    falhar "Não consegui ler as políticas de RLS da origem."
  }
  if [[ -n $sem_politica ]]; then
    falhar "Estas tabelas têm RLS sem política para o modo sistema, e o backup não enxergaria todas as linhas: $(printf '%s' "$sem_politica" | nomes_seguros | tr '\n' ' ')"
  fi
}

conferir_restauracao_vazia() {
  local objetos
  cat > "$TMP/vazio.sql" <<'SQL'
SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
           AND n.nspname NOT LIKE 'pg\_toast%' AND n.nspname NOT LIKE 'pg\_temp%')
     + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname NOT IN ('pg_catalog', 'information_schema'))
     + (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
         WHERE t.typtype IN ('e', 'd', 'r', 'm') AND n.nspname NOT IN ('pg_catalog', 'information_schema'))
     + (SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql');
SQL
  objetos=$(psql -X -q -At -v ON_ERROR_STOP=1 -f "$TMP/vazio.sql" "$RESTAURACAO" 2>"$TMP/erro-vazio.txt") || {
    mostrar_detalhes "$TMP/erro-vazio.txt"
    falhar "Não consegui olhar o banco de restauração."
  }
  [[ $objetos =~ ^[0-9]+$ ]] || falhar "Não consegui olhar o banco de restauração."
  if (( objetos != 0 )); then
    falhar "O banco de restauração não está vazio. Use um banco novo e vazio (no GitHub, o serviço postgres:16 já é)."
  fi
}

# Uma foto única do banco (REPEATABLE READ + pg_export_snapshot): as contagens e o pg_dump enxergam exatamente o
# mesmo instante, mesmo com o sistema no ar. PGOPTIONS liga o modo sistema e --enable-row-security deixa o dono
# do banco (FORCE RLS) ler as tabelas: sem os dois, o pg_dump falha ou copia as tabelas vazias.
# O pg_dump roda dentro da sessão do psql (\!), que segura a foto até ele terminar.
copiar_o_banco() {
  cat > "$TMP/contagens.sql" <<'SQL'
SELECT format('%I.%I', n.nspname, c.relname) AS tabela,
       (xpath('/row/n/text()',
              query_to_xml(format('SELECT count(*) AS n FROM %I.%I', n.nspname, c.relname), false, true, '')))[1]::text AS linhas
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind IN ('r', 'p')
   AND n.nspname NOT IN ('pg_catalog', 'information_schema')
   AND n.nspname NOT LIKE 'pg\_toast%'
 ORDER BY 1;
SQL
  cat > "$TMP/versao.sql" <<'SQL'
SELECT version_num FROM alembic_version ORDER BY version_num;
SQL
  cat > "$TMP/foto.sql" <<'SQL'
SET idle_in_transaction_session_timeout = 0;
SET statement_timeout = 0;
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT pg_export_snapshot() AS foto \gset
\setenv BACKUP_FOTO :foto
\o :arq_contagens
\i :arq_contagens_sql
\o :arq_versao
\i :arq_versao_sql
\o
\! pg_dump --format=custom --no-password --enable-row-security --lock-wait-timeout=2min --snapshot="$BACKUP_FOTO" --file="$BACKUP_ARQ_DUMP" "$BACKUP_ORIGEM" 2>"$BACKUP_ARQ_ERRO"; echo $? >"$BACKUP_ARQ_STATUS"
COMMIT;
SQL
  BACKUP_ORIGEM="$ORIGEM" BACKUP_ARQ_DUMP="$TMP/banco.dump" BACKUP_ARQ_ERRO="$TMP/erro-pg_dump.txt" \
    BACKUP_ARQ_STATUS="$TMP/status-pg_dump.txt" \
    psql -X -q -At -v ON_ERROR_STOP=1 \
      -v arq_contagens="$TMP/contagens-origem.txt" -v arq_contagens_sql="$TMP/contagens.sql" \
      -v arq_versao="$TMP/versao-origem.txt" -v arq_versao_sql="$TMP/versao.sql" \
      -f "$TMP/foto.sql" "$ORIGEM" >/dev/null 2>"$TMP/erro-foto.txt" || {
    mostrar_detalhes "$TMP/erro-foto.txt" "$TMP/erro-pg_dump.txt"
    falhar "Não consegui ler o banco de origem. Confira se BACKUP_DATABASE_URL é a do dono do banco (não a do toqqi_app)."
  }
  if [[ ! -s $TMP/status-pg_dump.txt ]] || [[ $(cat "$TMP/status-pg_dump.txt") != 0 ]] || [[ ! -s $TMP/banco.dump ]]; then
    mostrar_detalhes "$TMP/erro-pg_dump.txt"
    falhar "A cópia do banco (pg_dump) falhou."
  fi
  conferir_lista_de_tabelas "$TMP/contagens-origem.txt" "da origem"
  if [[ ! -s $TMP/versao-origem.txt ]]; then
    falhar "A tabela alembic_version da origem está vazia: não sei em que versão das migrações o banco está."
  fi
}

# A lista tem de ter "tabela|número" em todas as linhas, com a alembic_version entre elas. Vazio = não consegui olhar.
conferir_lista_de_tabelas() {
  local arquivo=$1 quem=$2
  if [[ ! -s $arquivo ]] || grep -q -v -E '^[^|]+\|[0-9]+$' "$arquivo"; then
    falhar "Não consegui ler a lista de tabelas $quem."
  fi
  if ! grep -q -E '^public\.alembic_version\|' "$arquivo"; then
    falhar "A tabela alembic_version não está na lista de tabelas $quem."
  fi
}

# ---------------------------------------------------------------------------------------------------------------
# Criptografia
# ---------------------------------------------------------------------------------------------------------------
# A senha entra pelo descritor 0 (nunca na linha de comando) e o gpg guarda suas coisas numa pasta temporária.
criptografar() {
  mkdir -m 700 "$TMP/gnupg"
  export GNUPGHOME="$TMP/gnupg"
  printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --quiet --no-tty --pinentry-mode loopback --passphrase-fd 0 \
    --symmetric --cipher-algo AES256 --s2k-mode 3 --s2k-digest-algo SHA512 --s2k-count 65011712 \
    --compress-algo none --output "$TMP/banco.dump.gpg" "$TMP/banco.dump" >/dev/null 2>"$TMP/erro-gpg.txt" || {
    mostrar_detalhes "$TMP/erro-gpg.txt"
    falhar "Não consegui criptografar a cópia (gpg)."
  }
  [[ -s $TMP/banco.dump.gpg ]] || falhar "Não consegui criptografar a cópia (gpg)."
  rm -f "$TMP/banco.dump"   # o arquivo sem criptografia não fica no disco
}

decifrar() {
  printf '%s' "$RESTAURACAO_PASSPHRASE" | gpg --batch --yes --quiet --no-tty --pinentry-mode loopback --passphrase-fd 0 \
    --decrypt --output "$TMP/restaurar.dump" "$TMP/baixado.dump.gpg" >/dev/null 2>"$TMP/erro-gpg-decifrar.txt" || {
    mostrar_detalhes "$TMP/erro-gpg-decifrar.txt"
    falhar "Não consegui decifrar a cópia baixada: a senha está errada ou o arquivo está corrompido."
  }
  [[ -s $TMP/restaurar.dump ]] || falhar "Não consegui decifrar a cópia baixada: a senha está errada ou o arquivo está corrompido."
  rm -f "$TMP/baixado.dump.gpg"
}

# ---------------------------------------------------------------------------------------------------------------
# Destino (R2 ou pasta local)
# ---------------------------------------------------------------------------------------------------------------
destino_local() { [[ ${BACKUP_DESTINO:-r2} == local:* ]]; }
pasta_local() { printf '%s' "${BACKUP_DESTINO#local:}"; }

aws_r2() {
  AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
    aws --endpoint-url "https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" --region auto \
    --cli-connect-timeout 30 --cli-read-timeout 300 "$@"
}

destino_enviar() {   # arquivo chave
  if destino_local; then
    mkdir -p "$(dirname "$(pasta_local)/$2")" && cp "$1" "$(pasta_local)/$2"
  else
    aws_r2 s3 cp "$1" "s3://${R2_BUCKET}/$2" --only-show-errors
  fi
}

destino_baixar() {   # chave arquivo
  if destino_local; then
    cp "$(pasta_local)/$1" "$2"
  else
    aws_r2 s3 cp "s3://${R2_BUCKET}/$1" "$2" --only-show-errors
  fi
}

destino_apagar() {   # chave
  if destino_local; then
    rm -f "$(pasta_local)/$1"
    rmdir "$(dirname "$(pasta_local)/$1")" 2>/dev/null || true
  else
    aws_r2 s3api delete-object --bucket "$R2_BUCKET" --key "$1" >/dev/null
  fi
}

destino_listar() {   # imprime as chaves sob toqqi/, uma por linha
  if destino_local; then
    if [[ -d "$(pasta_local)/toqqi" ]]; then (cd "$(pasta_local)" && find toqqi -type f); fi
  else
    aws_r2 s3api list-objects-v2 --bucket "$R2_BUCKET" --prefix toqqi/ --query 'Contents[].Key' --output text |
      tr '\t' '\n'
  fi
}

# ---------------------------------------------------------------------------------------------------------------
# Etapas
# ---------------------------------------------------------------------------------------------------------------
enviar_a_copia() {
  local agora
  agora=$(date -u +%Y-%m-%dT%H%M%SZ)
  CHAVE="toqqi/${agora:0:4}/${agora:5:2}/toqqi-${agora}.dump.gpg"
  destino_enviar "$TMP/banco.dump.gpg" "$CHAVE" 2>"$TMP/erro-envio.txt" || {
    mostrar_detalhes "$TMP/erro-envio.txt"
    falhar "Não consegui enviar a cópia ao destino. No R2, confira o token e o nome do bucket (segredos R2_*)."
  }
  OBJETO_ENVIADO=$CHAVE
}

# Baixa de volta o que foi enviado (prova o envio), confere que é idêntico, decifra e vê se o arquivo é um backup.
baixar_e_abrir() {
  destino_baixar "$CHAVE" "$TMP/baixado.dump.gpg" 2>"$TMP/erro-download.txt" || {
    mostrar_detalhes "$TMP/erro-download.txt"
    falhar "Não consegui baixar de volta a cópia enviada."
  }
  cmp -s "$TMP/banco.dump.gpg" "$TMP/baixado.dump.gpg" || falhar "A cópia baixada é diferente da que foi enviada."
  decifrar
  pg_restore --list "$TMP/restaurar.dump" >/dev/null 2>"$TMP/erro-lista.txt" || {
    mostrar_detalhes "$TMP/erro-lista.txt"
    falhar "A cópia decifrada não é um arquivo de backup válido do PostgreSQL."
  }
}

# --no-owner e --no-acl: a restauração não depende de nenhum papel do banco de origem (no Render só existe o dono).
restaurar() {
  pg_restore --no-owner --no-acl --exit-on-error --single-transaction --no-password \
    --dbname="$RESTAURACAO" "$TMP/restaurar.dump" >/dev/null 2>"$TMP/erro-restauracao.txt" || {
    mostrar_detalhes "$TMP/erro-restauracao.txt"
    falhar "A restauração num banco vazio falhou."
  }
}

conferir_restauracao() {
  local diferencas total
  if ! psql -X -q -At -v ON_ERROR_STOP=1 -f "$TMP/contagens.sql" "$RESTAURACAO" >"$TMP/contagens-restauro.txt" 2>"$TMP/erro-conf1.txt" ||
    ! psql -X -q -At -v ON_ERROR_STOP=1 -f "$TMP/versao.sql" "$RESTAURACAO" >"$TMP/versao-restauro.txt" 2>"$TMP/erro-conf2.txt"; then
    mostrar_detalhes "$TMP/erro-conf1.txt" "$TMP/erro-conf2.txt"
    falhar "Não consegui ler o banco restaurado para conferir."
  fi
  conferir_lista_de_tabelas "$TMP/contagens-restauro.txt" "do banco restaurado"
  # Só nomes de tabelas na saída (com os caracteres limpos), nunca números.
  diferencas=$(awk -F'|' '
    function seguro(t) { gsub(/[^A-Za-z0-9_.]/, "?", t); return t }
    NR == FNR { origem[$1] = $2; next }
    { resto[$1] = $2 }
    END {
      for (t in origem) {
        if (!(t in resto)) print seguro(t) " (só na origem)"
        else if (origem[t] != resto[t]) print seguro(t) " (linhas diferentes)"
      }
      for (t in resto) if (!(t in origem)) print seguro(t) " (só no restauro)"
    }' "$TMP/contagens-origem.txt" "$TMP/contagens-restauro.txt" | sort) || falhar "Não consegui comparar as tabelas."
  if [[ -n $diferencas ]]; then
    falhar "A restauração não bate com a origem nestas tabelas: $(printf '%s' "$diferencas" | tr '\n' ';' | sed 's/;/; /g; s/; $//')"
  fi
  if ! cmp -s "$TMP/versao-origem.txt" "$TMP/versao-restauro.txt"; then
    falhar "A restauração não bate com a origem: alembic_version diferente."
  fi
  total=$(wc -l < "$TMP/contagens-origem.txt" | tr -d ' ')
  info "ok: $total tabelas conferidas"
}

# Apaga o que tem mais de 30 dias, mas nunca deixa menos de 7 cópias: se o backup parar por semanas, as últimas ficam.
# Só mexe em arquivos com o nome que este script dá; qualquer outra coisa sob toqqi/ é ignorada.
retencao() {
  local dias=30 minimo=7 listagem chaves corte posicao=0 apagadas=0 chave carimbo
  listagem=$(destino_listar 2>"$TMP/erro-lista-destino.txt") || {
    mostrar_detalhes "$TMP/erro-lista-destino.txt"
    return 1
  }
  chaves=$(printf '%s\n' "$listagem" |
    { grep -E '^toqqi/[0-9]{4}/[0-9]{2}/toqqi-[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z\.dump\.gpg$' || true; } | sort -r)
  corte=$(carimbo_de_ha_dias "$dias") || return 1
  while IFS= read -r chave; do
    [[ -n $chave ]] || continue
    posicao=$((posicao + 1))
    (( posicao > minimo )) || continue
    carimbo=${chave##*/toqqi-}
    carimbo=${carimbo%.dump.gpg}
    if [[ $carimbo < $corte ]]; then
      destino_apagar "$chave" 2>"$TMP/erro-apagar.txt" || {
        mostrar_detalhes "$TMP/erro-apagar.txt"
        return 1
      }
      apagadas=$((apagadas + 1))
    fi
  done <<< "$chaves"
  info "Cópias antigas apagadas: $apagadas (sempre ficam pelo menos $minimo)."
}

# Carimbo (AAAA-MM-DDTHHMMSSZ) de N dias atrás, igual ao dos nomes dos arquivos.
carimbo_de_ha_dias() {
  local epoca
  epoca=$(( $(date -u +%s) - $1 * 86400 ))
  date -u -d "@$epoca" +%Y-%m-%dT%H%M%SZ 2>/dev/null || date -u -r "$epoca" +%Y-%m-%dT%H%M%SZ
}

# ---------------------------------------------------------------------------------------------------------------
main() {
  case ${1:-} in
    -h | --help | --ajuda) sed -n '2,40p' "$0"; exit 0 ;;
  esac

  verificar_configuracao
  trap limpar EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  verificar_ferramentas
  verificar_senha
  if ! destino_local; then   # espaço ou Enter colado junto do segredo
    R2_ACCOUNT_ID=${R2_ACCOUNT_ID//[[:space:]]/}
    R2_BUCKET=${R2_BUCKET//[[:space:]]/}
    R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID//[[:space:]]/}
    R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY//[[:space:]]/}
  fi
  # Os segredos ficam só nesta shell: os programas filhos (psql, pg_dump, gpg...) não os recebem no ambiente.
  export -n BACKUP_DATABASE_URL BACKUP_PASSPHRASE RESTAURACAO_PASSPHRASE RESTAURACAO_DATABASE_URL R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY

  ORIGEM=$(normalizar_url "$BACKUP_DATABASE_URL") ||
    falhar "BACKUP_DATABASE_URL não parece um endereço do PostgreSQL (precisa começar com postgresql://)."
  RESTAURACAO=$(normalizar_url "$RESTAURACAO_DATABASE_URL") ||
    falhar "RESTAURACAO_DATABASE_URL não parece um endereço do PostgreSQL (precisa começar com postgresql://)."
  esconder_no_log "$ORIGEM"
  if [[ $(identidade_da_url "$ORIGEM") == "$(identidade_da_url "$RESTAURACAO")" ]]; then
    falhar "RESTAURACAO_DATABASE_URL aponta para o mesmo banco da origem. Use um banco vazio e separado."
  fi

  TMP=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/toqqi-backup.XXXXXX") || falhar "Não consegui criar a pasta temporária."
  case $TMP in *[[:space:]]*) falhar "O caminho da pasta temporária não pode ter espaços (use TMPDIR=/tmp)." ;; esac

  # Modo sistema do RLS (para ler todas as contas) e ajustes das ferramentas. Nenhum segredo entra aqui.
  export PGOPTIONS='-c app.sistema=on'
  export PGCONNECT_TIMEOUT=30
  export PGAPPNAME=toqqi-backup
  # R2 recusa os cabeçalhos de checagem que as versões novas do AWS CLI mandam por padrão.
  export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
  export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
  export AWS_MAX_ATTEMPTS=5 AWS_RETRY_MODE=standard AWS_PAGER="" AWS_EC2_METADATA_DISABLED=true
  export AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null
  unset AWS_PROFILE AWS_DEFAULT_PROFILE AWS_SESSION_TOKEN AWS_ENDPOINT_URL AWS_ENDPOINT_URL_S3

  info "Conferindo o ambiente..."
  conferir_versoes
  conferir_politicas
  conferir_restauracao_vazia

  info "Copiando o banco (pg_dump)..."
  copiar_o_banco
  info "Criptografando..."
  criptografar
  info "Enviando para o destino..."
  enviar_a_copia
  info "Baixando a cópia enviada e abrindo o arquivo..."
  baixar_e_abrir
  info "Restaurando num banco vazio e conferindo..."
  restaurar
  conferir_restauracao
  CONFERIDO=1

  info "Limpando cópias antigas..."
  retencao || falhar "A cópia de hoje está conferida, mas não consegui limpar as cópias antigas do destino."

  info "Backup concluído: $CHAVE"
  if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
    printf 'Backup concluído e conferido: %s\n' "$CHAVE" >> "$GITHUB_STEP_SUMMARY"
  fi
}

# Rodando direto, executa; com `source`, só carrega as funções (útil para testá-las).
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
