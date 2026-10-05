"""Etapa 5j: o conector do Omie (ERP) na lista de provedores de `conectores`.

Revision ID: 0020_conector_omie
Revises: 0019_conectores
"""
from alembic import op

revision = "0020_conector_omie"
down_revision = "0019_conectores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conectores DROP CONSTRAINT conectores_provedor_check")
    op.execute("ALTER TABLE conectores ADD CONSTRAINT conectores_provedor_check "
               "CHECK (provedor IN ('rdstation_crm', 'omie'))")


def downgrade() -> None:
    op.execute("DELETE FROM conectores WHERE provedor = 'omie'")
    op.execute("ALTER TABLE conectores DROP CONSTRAINT conectores_provedor_check")
    op.execute("ALTER TABLE conectores ADD CONSTRAINT conectores_provedor_check "
               "CHECK (provedor IN ('rdstation_crm'))")
