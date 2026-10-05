"""Etapa 5j: o conector do Bling (ERP, OAuth do aplicativo do Toqqi) na lista de provedores de `conectores`. O id da
empresa no Bling (`companyId` dos avisos) fica em `opcoes.empresa_bling`, com índice para achar a conta do aviso.

Revision ID: 0021_conector_bling
Revises: 0020_conector_omie
"""
from alembic import op

revision = "0021_conector_bling"
down_revision = "0020_conector_omie"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conectores DROP CONSTRAINT conectores_provedor_check")
    op.execute("ALTER TABLE conectores ADD CONSTRAINT conectores_provedor_check "
               "CHECK (provedor IN ('rdstation_crm', 'omie', 'bling'))")
    op.execute("CREATE INDEX conectores_empresa_bling_idx ON conectores ((opcoes->>'empresa_bling')) "
               "WHERE provedor = 'bling'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS conectores_empresa_bling_idx")
    op.execute("DELETE FROM conectores WHERE provedor = 'bling'")
    op.execute("ALTER TABLE conectores DROP CONSTRAINT conectores_provedor_check")
    op.execute("ALTER TABLE conectores ADD CONSTRAINT conectores_provedor_check "
               "CHECK (provedor IN ('rdstation_crm', 'omie'))")
