"""Esquema inicial: contas, usuários, sessões, tokens, permissões, domínios, auditoria + RLS.

Revision ID: 0001_inicial
Revises:
Create Date: 2026-09-30
"""
import os
import re

from alembic import op

revision = "0001_inicial"
down_revision = None
branch_labels = None
depends_on = None

TABELAS_COM_CONTA = ["usuarios", "sessoes", "tokens_uso_unico", "perfil_permissoes", "dominios_liberados", "auditoria"]


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # Contexto da transação: definido pela aplicação com set_config(..., true).
    op.execute("""
        CREATE FUNCTION app_conta() RETURNS bigint LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.conta_id', true), '')::bigint $$
    """)
    op.execute("""
        CREATE FUNCTION app_sistema() RETURNS boolean LANGUAGE sql STABLE AS
        $$ SELECT coalesce(current_setting('app.sistema', true), '') = 'on' $$
    """)

    op.execute("""
        CREATE TABLE contas (
            id bigserial PRIMARY KEY,
            nome text NOT NULL,
            plano text NOT NULL DEFAULT 'profissional',
            situacao text NOT NULL DEFAULT 'teste'
                CHECK (situacao IN ('teste','teste_expirado','ativa','atrasada','cancelada','cortesia')),
            teste_ate timestamptz,
            sessao_minutos integer NOT NULL DEFAULT 60 CHECK (sessao_minutos BETWEEN 30 AND 1440),
            termos_aceitos_em timestamptz,
            termos_versao text,
            termos_ip text,
            criada_em timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE usuarios (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            nome text NOT NULL,
            email citext NOT NULL UNIQUE,
            senha_hash text NOT NULL,
            cargo text,
            telefone text,
            perfil text NOT NULL CHECK (perfil IN ('admin','gestor','consulta')),
            situacao text NOT NULL DEFAULT 'ativo' CHECK (situacao IN ('ativo','pendente','bloqueado')),
            email_confirmado boolean NOT NULL DEFAULT false,
            ultimo_acesso timestamptz,
            criado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (id, conta_id)
        )
    """)
    op.execute("CREATE INDEX usuarios_conta_idx ON usuarios (conta_id)")

    op.execute("""
        CREATE TABLE sessoes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            usuario_id bigint NOT NULL,
            criada_em timestamptz NOT NULL DEFAULT now(),
            ultimo_uso timestamptz NOT NULL DEFAULT now(),
            expira_em timestamptz NOT NULL,
            ip text,
            agente text,
            revogada_em timestamptz,
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX sessoes_usuario_idx ON sessoes (usuario_id)")

    op.execute("""
        CREATE TABLE tokens_uso_unico (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            usuario_id bigint NOT NULL,
            finalidade text NOT NULL CHECK (finalidade IN ('confirmar_email','redefinir_senha')),
            token_hash text NOT NULL UNIQUE,
            criado_em timestamptz NOT NULL DEFAULT now(),
            expira_em timestamptz NOT NULL,
            usado_em timestamptz,
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX tokens_usuario_idx ON tokens_uso_unico (usuario_id, finalidade)")

    op.execute("""
        CREATE TABLE perfil_permissoes (
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            perfil text NOT NULL CHECK (perfil IN ('gestor','consulta')),
            permissao text NOT NULL,
            PRIMARY KEY (conta_id, perfil, permissao)
        )
    """)

    op.execute("""
        CREATE TABLE dominios_liberados (
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            dominio citext PRIMARY KEY
        )
    """)
    op.execute("CREATE INDEX dominios_conta_idx ON dominios_liberados (conta_id)")

    op.execute("""
        CREATE TABLE auditoria (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            usuario_id bigint,
            evento text NOT NULL,
            gravidade text NOT NULL CHECK (gravidade IN ('info','sucesso','atencao','erro')),
            detalhe jsonb NOT NULL DEFAULT '{}'::jsonb,
            ip text,
            criado_em timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id)
        )
    """)
    op.execute("CREATE INDEX auditoria_conta_data_idx ON auditoria (conta_id, criado_em DESC)")

    # ---- isolamento entre contas (RLS) -------------------------------------
    op.execute("ALTER TABLE contas ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE contas FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY isolamento_conta ON contas
            USING (id = app_conta() OR app_sistema())
            WITH CHECK (id = app_conta() OR app_sistema())
    """)
    for t in TABELAS_COM_CONTA:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY isolamento_conta ON {t}
                USING (conta_id = app_conta() OR app_sistema())
                WITH CHECK (conta_id = app_conta() OR app_sistema())
        """)

    # ---- permissões do papel da aplicação ----------------------------------
    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT USAGE ON SCHEMA public TO {papel};
                GRANT SELECT, INSERT, UPDATE, DELETE ON
                    contas, usuarios, sessoes, tokens_uso_unico, perfil_permissoes, dominios_liberados, auditoria
                    TO {papel};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel};
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {papel};
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    for t in ["auditoria", "dominios_liberados", "perfil_permissoes", "tokens_uso_unico", "sessoes", "usuarios", "contas"]:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS app_conta()")
    op.execute("DROP FUNCTION IF EXISTS app_sistema()")
