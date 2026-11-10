"""Instalação do Toqqi pela loja do Bling (Central de Extensões), pedido do Marcelo em 10/11/2026.

Quem instala pela loja chega à volta da autorização sem o `state` do Toqqi (não começou no Toqqi): a API troca o código
pelos tokens na hora (o código vence em minutos) e guarda aqui, cifrados, até a pessoa entrar (ou criar a conta) e ligar
a uma conta do Toqqi (`POST /integracoes/conectores/bling/instalacao`). Só o hash do código da instalação fica no banco;
vale 24 horas e some ao ser usado (a tarefa `limpeza` apaga os vencidos). Tabela da plataforma: só em modo sistema.

Revision ID: 0032_bling_instalacoes
Revises: 0031_relatorio_mensal_crms
"""
import os
import re

from alembic import op

revision = "0032_bling_instalacoes"
down_revision = "0031_relatorio_mensal_crms"
branch_labels = None
depends_on = None


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute("""
        CREATE TABLE bling_instalacoes (
            id bigserial PRIMARY KEY,
            codigo_hash text NOT NULL UNIQUE CHECK (length(codigo_hash) = 64),
            tokens_cifrado text NOT NULL,
            empresa_bling text,
            criado_em timestamptz NOT NULL DEFAULT now(),
            expira_em timestamptz NOT NULL
        )
    """)
    op.execute("ALTER TABLE bling_instalacoes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bling_instalacoes FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY so_sistema ON bling_instalacoes USING (app_sistema()) WITH CHECK (app_sistema())")
    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON bling_instalacoes TO {papel};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bling_instalacoes CASCADE")
