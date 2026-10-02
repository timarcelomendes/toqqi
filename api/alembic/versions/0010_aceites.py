"""Aceite dos Termos de uso e da Política de privacidade (LGPD).

Tabela `aceites_termos`: um registro por usuário e versão dos documentos (quem, quando, versão, IP, navegador e
origem: `cadastro` ou `tela`). Aceitar de novo a mesma versão não cria linha (único `(usuario_id, versao)`); quando o
texto muda, a versão sobe e o histórico fica. Mesmo padrão das etapas anteriores: conta_id DEFAULT app_conta(), RLS
com FORCE, chave composta (usuario_id, conta_id) e permissões do papel da aplicação só se ele existir.

A prova do aceite não some quando um membro é removido em Equipe: a chave composta é ON DELETE SET NULL (usuario_id)
(Postgres 15+) e a linha guarda uma cópia do e-mail e do nome do momento do aceite. A exclusão da conta inteira (pela
Plataforma) continua apagando tudo (conta_id ON DELETE CASCADE).

Revision ID: 0010_aceites
Revises: 0009_assistente
Create Date: 2026-10-02
"""
import os
import re

from alembic import op

revision = "0010_aceites"
down_revision = "0009_assistente"
branch_labels = None
depends_on = None

AGENTE_MAX = 400


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE aceites_termos (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            usuario_id bigint,
            usuario_email citext NOT NULL,
            usuario_nome text NOT NULL,
            versao integer NOT NULL CHECK (versao >= 1),
            aceito_em timestamptz NOT NULL DEFAULT now(),
            ip text,
            agente text CHECK (length(agente) <= {AGENTE_MAX}),
            origem text NOT NULL CHECK (origem IN ('cadastro','tela')),
            UNIQUE (usuario_id, versao),
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id)
                ON DELETE SET NULL (usuario_id)
        )
    """)
    # (usuario_id, versao) já tem o índice do UNIQUE
    op.execute("CREATE INDEX aceites_termos_conta_idx ON aceites_termos (conta_id)")

    op.execute("ALTER TABLE aceites_termos ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aceites_termos FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY isolamento_conta ON aceites_termos
            USING (conta_id = app_conta() OR app_sistema())
            WITH CHECK (conta_id = app_conta() OR app_sistema())
    """)

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON aceites_termos TO {papel};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aceites_termos CASCADE")
