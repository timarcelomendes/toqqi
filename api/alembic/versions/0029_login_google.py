"""Entrar com o Google (docs/api-login-google.md), pedido do Marcelo em 08/10/2026.

- `usuarios.google_sub`: o identificador da conta do Google (`sub` do token) ligada ao usuário na primeira entrada pelo
  Google. Depois disso, só essa conta do Google entra por ele (outra conta do Google com o mesmo e-mail é recusada).
  Único entre todos os usuários.

Revision ID: 0029_login_google
Revises: 0028_editar_resposta
"""
from alembic import op

revision = "0029_login_google"
down_revision = "0028_editar_resposta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE usuarios ADD COLUMN google_sub text CHECK (length(google_sub) BETWEEN 1 AND 255)")
    op.execute("CREATE UNIQUE INDEX usuarios_google_sub_key ON usuarios (google_sub) WHERE google_sub IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX usuarios_google_sub_key")
    op.execute("ALTER TABLE usuarios DROP COLUMN google_sub")
