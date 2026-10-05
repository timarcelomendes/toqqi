"""Melhoria 5, prova social: o promotor que deixou comentário autoriza publicar o comentário como depoimento (tela final
da pesquisa); a equipe aprova ou oculta em Crescimento › Depoimentos. E o link para avaliar a empresa (Google ou outro)
aparece para o promotor na tela final.

Revision ID: 0024_depoimentos
Revises: 0023_nota_no_crm
"""
from alembic import op

revision = "0024_depoimentos"
down_revision = "0023_nota_no_crm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE config_crescimento ADD COLUMN depoimentos_ativos boolean NOT NULL DEFAULT false, "
               "ADD COLUMN link_avaliacao text CHECK (link_avaliacao ~ '^https://' AND length(link_avaliacao) <= 500)")
    op.execute("ALTER TABLE respostas ADD COLUMN depoimento_em timestamptz, ADD COLUMN depoimento_situacao text "
               "CHECK (depoimento_situacao IN ('pendente','aprovado','oculto')), "
               "ADD CONSTRAINT respostas_depoimento_junto CHECK ((depoimento_em IS NULL) = (depoimento_situacao IS NULL))")
    op.execute("CREATE INDEX respostas_depoimentos_idx ON respostas (conta_id, depoimento_em DESC) "
               "WHERE depoimento_em IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS respostas_depoimentos_idx")
    op.execute("ALTER TABLE respostas DROP CONSTRAINT respostas_depoimento_junto, DROP COLUMN depoimento_situacao, "
               "DROP COLUMN depoimento_em")
    op.execute("ALTER TABLE config_crescimento DROP COLUMN link_avaliacao, DROP COLUMN depoimentos_ativos")
