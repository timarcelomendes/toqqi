"""O cliente pode mudar a resposta (docs/api-editar-resposta.md), pedido do Marcelo em 06/10/2026.

- `formularios.permite_editar` (padrão: não): com ele ligado, quem respondeu muda a resposta até 7 dias depois — no
  convite, reabrindo o link (ou clicando de novo numa nota do e-mail); no link público, só logo depois de enviar, pela
  chave que a API devolve (`respostas.edicao_hash` guarda o sha256 dela).
- `respostas.editada_em` e `respostas.edicoes`: a última vez que o cliente mudou e quantas vezes.
- `acoes.nota_editada` e `acoes.nota_editada_em`: o plano de ação de uma resposta cuja nota o cliente mudou (o plano
  fica aberto; a tela mostra "o cliente mudou a nota de N para M").
- `webhooks.eventos` aceita `resposta.atualizada`.

Revision ID: 0028_editar_resposta
Revises: 0027_feedback
"""
from alembic import op

revision = "0028_editar_resposta"
down_revision = "0027_feedback"
branch_labels = None
depends_on = None

EVENTOS_ANTES = ("'resposta.criada','contato.descadastrado','indicacao.criada','indicacao.atualizada',"
                 "'empresa.perdida','empresa.reativada'")
EVENTO_NOVO = "'resposta.atualizada'"


def _check_eventos(eventos: str) -> None:
    op.execute(f"""
        ALTER TABLE webhooks DROP CONSTRAINT IF EXISTS webhooks_eventos_check,
            ADD CONSTRAINT webhooks_eventos_check CHECK (cardinality(eventos) >= 1 AND eventos <@ ARRAY[{eventos}])
    """)


def upgrade() -> None:
    op.execute("ALTER TABLE formularios ADD COLUMN permite_editar boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE respostas ADD COLUMN editada_em timestamptz, "
               "ADD COLUMN edicoes smallint NOT NULL DEFAULT 0 CHECK (edicoes >= 0), "
               "ADD COLUMN edicao_hash text CHECK (length(edicao_hash) = 64)")
    op.execute("ALTER TABLE acoes ADD COLUMN nota_editada smallint, ADD COLUMN nota_editada_em timestamptz, "
               "ADD CONSTRAINT acoes_nota_editada_junto CHECK ((nota_editada IS NULL) = (nota_editada_em IS NULL))")
    _check_eventos(f"{EVENTOS_ANTES},{EVENTO_NOVO}")


def downgrade() -> None:
    op.execute(f"DELETE FROM webhook_entregas WHERE evento = {EVENTO_NOVO}")
    op.execute(f"DELETE FROM webhooks WHERE eventos = ARRAY[{EVENTO_NOVO}]")  # só tinham o evento novo
    op.execute(f"UPDATE webhooks SET eventos = array_remove(eventos, {EVENTO_NOVO}) WHERE {EVENTO_NOVO} = ANY(eventos)")
    _check_eventos(EVENTOS_ANTES)
    op.execute("ALTER TABLE acoes DROP CONSTRAINT acoes_nota_editada_junto, DROP COLUMN nota_editada_em, "
               "DROP COLUMN nota_editada")
    op.execute("ALTER TABLE respostas DROP COLUMN edicao_hash, DROP COLUMN edicoes, DROP COLUMN editada_em")
    op.execute("ALTER TABLE formularios DROP COLUMN permite_editar")
