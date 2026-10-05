"""Conectores: devolver a nota ao CRM. O convite mandado por um conector guarda de onde veio (`origem_externa`, ex.:
`rd:<negociação>`) e quando a resposta foi anotada lá (`devolvida_em`); a tarefa `conectores` anota as respostas novas.

Revision ID: 0023_nota_no_crm
Revises: 0022_retorno_ao_cliente
"""
from alembic import op

revision = "0023_nota_no_crm"
down_revision = "0022_retorno_ao_cliente"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE convites ADD COLUMN origem_externa text CHECK (length(origem_externa) <= 100), "
               "ADD COLUMN devolvida_em timestamptz")
    op.execute("CREATE INDEX convites_a_devolver_idx ON convites (respondido_em) "
               "WHERE origem_externa IS NOT NULL AND devolvida_em IS NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS convites_a_devolver_idx")
    op.execute("ALTER TABLE convites DROP COLUMN devolvida_em, DROP COLUMN origem_externa")
