"""Etapa 5j: conectores com sistemas do cliente (começando pelo RD Station CRM).

`conectores`: um por conta e provedor, com o token do cliente cifrado (`core/segredos`), o hash do segredo do endereço
que recebe os avisos do provedor (o segredo em si só existe no endereço cadastrado no provedor), as opções e o
resultado da última sincronização. RLS por conta, como as outras tabelas; a busca pelo segredo do aviso roda em modo
sistema. Sai em cascata com a conta.

Revision ID: 0019_conectores
Revises: 0018_desfecho_saude_origem
"""
import os
import re

from alembic import op

revision = "0019_conectores"
down_revision = "0018_desfecho_saude_origem"
branch_labels = None
depends_on = None

PROVEDORES = ("rdstation_crm",)


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    provedores = ",".join(f"'{p}'" for p in PROVEDORES)
    op.execute(f"""
        CREATE TABLE conectores (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas ON DELETE CASCADE,
            provedor text NOT NULL CHECK (provedor IN ({provedores})),
            token_cifrado text NOT NULL,
            segredo_hash text NOT NULL UNIQUE CHECK (length(segredo_hash) = 64),
            webhook_externo text CHECK (length(webhook_externo) <= 100),
            opcoes jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(opcoes) = 'object'),
            sincronizado_em timestamptz,
            resumo jsonb,
            erro text CHECK (length(erro) <= 300),
            criado_em timestamptz NOT NULL DEFAULT now(),
            atualizado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (conta_id, provedor)
        )
    """)
    op.execute("ALTER TABLE conectores ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conectores FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY isolamento_conta ON conectores
            USING (conta_id = app_conta() OR app_sistema())
            WITH CHECK (conta_id = app_conta() OR app_sistema())
    """)
    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON conectores TO {papel};
                GRANT USAGE, SELECT ON SEQUENCE conectores_id_seq TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conectores CASCADE")
