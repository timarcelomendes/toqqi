"""Etapa 5b: cota de IA do plano (assistente).

`ia_uso_mensal` (da 0007, já com RLS por conta e com as permissões do papel da aplicação na tabela inteira) ganha a
cota do plano, separada do teto de segurança da análise por resposta (`analises`):
- `cota_usada`: análises da cota do plano gastas no mês (hoje, só as perguntas ao assistente), nunca negativa;
- `cota_tokens_entrada` e `cota_tokens_saida`: tokens dessas análises (todas as chamadas de cada pergunta).
O downgrade remove as três colunas.

Revision ID: 0009_assistente
Revises: 0008_assinaturas
Create Date: 2026-10-02
"""
from alembic import op

revision = "0009_assistente"
down_revision = "0008_assinaturas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ia_uso_mensal
            ADD COLUMN cota_usada integer NOT NULL DEFAULT 0,
            ADD COLUMN cota_tokens_entrada bigint NOT NULL DEFAULT 0,
            ADD COLUMN cota_tokens_saida bigint NOT NULL DEFAULT 0,
            ADD CONSTRAINT ia_uso_mensal_cota_usada_check CHECK (cota_usada >= 0)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ia_uso_mensal
            DROP CONSTRAINT IF EXISTS ia_uso_mensal_cota_usada_check,
            DROP COLUMN IF EXISTS cota_usada,
            DROP COLUMN IF EXISTS cota_tokens_entrada,
            DROP COLUMN IF EXISTS cota_tokens_saida
    """)
