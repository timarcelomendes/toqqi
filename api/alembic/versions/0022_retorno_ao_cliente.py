"""Melhoria 4, retorno ao cliente: ao concluir um plano de ação de uma resposta, avisar a pessoa do que foi feito
("você falou, nós fizemos"). O texto e a data ficam na ação; o e-mail sai pela fila de envios (tipo `retorno`, com
`acao_id`) e entra no registro de e-mails enviados.

Revision ID: 0022_retorno_ao_cliente
Revises: 0021_conector_bling
"""
from alembic import op

revision = "0022_retorno_ao_cliente"
down_revision = "0021_conector_bling"
branch_labels = None
depends_on = None

EMAILS = ("convite", "lembrete", "agradecimento", "teste", "confirmacao", "senha", "boas_vindas", "alerta_risco",
          "resumo_semanal", "pico", "indicacao", "aviso", "cobranca")


def _lista(itens) -> str:
    return ",".join(f"'{i}'" for i in itens)


def upgrade() -> None:
    op.execute("ALTER TABLE acoes ADD COLUMN retorno_texto text CHECK (length(retorno_texto) <= 1000), "
               "ADD COLUMN retorno_em timestamptz")
    op.execute("ALTER TABLE envios ADD COLUMN acao_id bigint")
    op.execute("ALTER TABLE envios ADD CONSTRAINT envios_acao_fk FOREIGN KEY (acao_id, conta_id) "
               "REFERENCES acoes (id, conta_id) ON DELETE SET NULL (acao_id)")
    op.execute("CREATE INDEX envios_acao_idx ON envios (acao_id) WHERE acao_id IS NOT NULL")
    op.execute("ALTER TABLE envios DROP CONSTRAINT envios_tipo_check")
    op.execute("ALTER TABLE envios ADD CONSTRAINT envios_tipo_check "
               "CHECK (tipo IN ('convite','lembrete','agradecimento','retorno'))")
    op.execute("ALTER TABLE emails_enviados DROP CONSTRAINT emails_enviados_tipo_check")
    op.execute(f"ALTER TABLE emails_enviados ADD CONSTRAINT emails_enviados_tipo_check "
               f"CHECK (tipo IN ({_lista(EMAILS + ('retorno',))}))")


def downgrade() -> None:
    op.execute("DELETE FROM emails_enviados WHERE tipo = 'retorno'")
    op.execute("ALTER TABLE emails_enviados DROP CONSTRAINT emails_enviados_tipo_check")
    op.execute(f"ALTER TABLE emails_enviados ADD CONSTRAINT emails_enviados_tipo_check CHECK (tipo IN ({_lista(EMAILS)}))")
    op.execute("DELETE FROM envios WHERE tipo = 'retorno'")
    op.execute("ALTER TABLE envios DROP CONSTRAINT envios_tipo_check")
    op.execute("ALTER TABLE envios ADD CONSTRAINT envios_tipo_check CHECK (tipo IN ('convite','lembrete','agradecimento'))")
    op.execute("ALTER TABLE envios DROP COLUMN acao_id")
    op.execute("ALTER TABLE acoes DROP COLUMN retorno_texto, DROP COLUMN retorno_em")
