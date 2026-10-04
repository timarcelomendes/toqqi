"""Etapa 5g: parâmetros da plataforma (preços, limites, IA, WhatsApp e teste editáveis pela equipe Toqqi).

- `parametros` (sem conta): só o que difere do padrão (tabela vazia = tudo como antes). `chave` no formato
  `grupo.nome[.nome]` (grupos planos, ia, whatsapp e teste) e `valor` jsonb (texto "149.00", inteiro, null = sem
  limite, ou texto). Só isso: quem alterou e quando ficam no histórico (a conta lê as linhas dos limites pela
  `ler_limites` e não deve ver o e-mail de quem alterou).
- `parametros_historico`: cada alteração salva (grupo, quem e `[{chave, de, para}]` com os valores efetivos), imutável.
  Sem FK: sobrevive à exclusão de quem alterou. Índice `(grupo, id DESC)` para a lista da tela.
- RLS forçado nas duas, com a política `sistema` (só o modo sistema lê e grava); em `parametros`, também `ler_limites`
  (SELECT das linhas `planos.%.contatos`, que o gatilho do limite de contatos lê no contexto da conta: são números
  públicos). Papel da aplicação: SELECT, INSERT, UPDATE e DELETE em `parametros`; só SELECT e INSERT no histórico
  (`REVOKE UPDATE, DELETE, TRUNCATE`, como `registros_acesso` na 0015: nem o modo sistema muda o histórico).
- `limite_contatos(p_plano, p_situacao)` (0002) passa de IMMUTABLE a STABLE (lê a tabela): cortesia → NULL; com a
  linha `planos.{plano}.contatos` válida (JSON null = sem limite, ou número inteiro de 1 a 1.000.000, como o Python
  aceita) → o valor dela; sem ela (ou com ela fora do formato: texto, booleano, fração, fora da faixa), os padrões de
  antes (essencial 300, profissional 1500, outro NULL). O gatilho `contatos_checar_limite` (0008) não muda.

O downgrade volta a função antiga (IMMUTABLE) e apaga as duas tabelas.

Revision ID: 0016_parametros
Revises: 0015_dados_conta
Create Date: 2026-10-03
"""
import os
import re

from alembic import op

revision = "0016_parametros"
down_revision = "0015_dados_conta"
branch_labels = None
depends_on = None

GRUPOS = ("planos", "ia", "whatsapp", "teste")
CHAVE = r"^(planos|ia|whatsapp|teste)\.[a-z_]+(\.[a-z_]+)?$"

# A linha vale só como o Python a aceita (`core.parametros`, tipo `contatos`): JSON null (sem limite) ou número
# inteiro de 1 a 1.000.000 escrito só com dígitos (o texto "300", true, 2.5, 2.0, 0 e -1 valem o padrão). O CASE
# garante que o texto só vira inteiro depois de conferido.
FUNCAO_NOVA = """
    CREATE OR REPLACE FUNCTION limite_contatos(p_plano text, p_situacao text) RETURNS integer
    LANGUAGE sql STABLE AS $$
        WITH linha AS (
            SELECT CASE WHEN jsonb_typeof(valor) = 'number' AND valor::text ~ '^[0-9]{1,7}$'
                        THEN (valor::text)::integer END AS limite
              FROM parametros
             WHERE chave = 'planos.' || p_plano || '.contatos'
               AND CASE WHEN jsonb_typeof(valor) = 'null' THEN true
                        WHEN jsonb_typeof(valor) = 'number' AND valor::text ~ '^[0-9]{1,7}$'
                            THEN (valor::text)::integer BETWEEN 1 AND 1000000
                        ELSE false
                   END
        )
        SELECT CASE
            WHEN p_situacao = 'cortesia' THEN NULL
            WHEN EXISTS (SELECT 1 FROM linha) THEN (SELECT limite FROM linha)
            WHEN p_plano = 'essencial' THEN 300
            WHEN p_plano = 'profissional' THEN 1500
            ELSE NULL
        END
    $$
"""
FUNCAO_ANTIGA = """
    CREATE OR REPLACE FUNCTION limite_contatos(p_plano text, p_situacao text) RETURNS integer
    LANGUAGE sql IMMUTABLE AS $$
        SELECT CASE
            WHEN p_situacao = 'cortesia' THEN NULL
            WHEN p_plano = 'essencial' THEN 300
            WHEN p_plano = 'profissional' THEN 1500
            ELSE NULL
        END
    $$
"""


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE parametros (
            chave text PRIMARY KEY CHECK (chave ~ '{CHAVE}'),
            valor jsonb NOT NULL
        )
    """)
    grupos = ",".join(f"'{g}'" for g in GRUPOS)
    op.execute(f"""
        CREATE TABLE parametros_historico (
            id bigserial PRIMARY KEY,
            criado_em timestamptz NOT NULL DEFAULT now(),
            grupo text NOT NULL CHECK (grupo IN ({grupos})),
            por text NOT NULL CHECK (length(por) BETWEEN 1 AND 254),
            mudancas jsonb NOT NULL CHECK (jsonb_typeof(mudancas) = 'array')
        )
    """)
    op.execute("CREATE INDEX parametros_historico_grupo_idx ON parametros_historico (grupo, id DESC)")
    for tabela in ("parametros", "parametros_historico"):
        op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY sistema ON {tabela} FOR ALL USING (app_sistema()) WITH CHECK (app_sistema())")
    op.execute("CREATE POLICY ler_limites ON parametros FOR SELECT USING (chave LIKE 'planos.%.contatos')")

    op.execute(FUNCAO_NOVA)

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON parametros TO {papel};
                GRANT SELECT, INSERT ON parametros_historico TO {papel};
                REVOKE UPDATE, DELETE, TRUNCATE ON parametros_historico FROM {papel};
                GRANT USAGE, SELECT ON SEQUENCE parametros_historico_id_seq TO {papel};
                GRANT EXECUTE ON FUNCTION limite_contatos(text, text) TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute(FUNCAO_ANTIGA)
    op.execute("DROP TABLE IF EXISTS parametros_historico CASCADE")
    op.execute("DROP TABLE IF EXISTS parametros CASCADE")
