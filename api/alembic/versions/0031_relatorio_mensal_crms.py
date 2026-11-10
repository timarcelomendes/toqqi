"""Relatório mensal em PDF e os conectores do Pipedrive e do HubSpot (pedido do Marcelo em 10/11/2026).

- `relatorios_mensais`: o e-mail do relatório do mês (PDF anexo) que saiu para a conta, um por conta e mês (`mes` = o
  dia 1 do mês relatado; o UNIQUE impede duplicar, como `resumos_semanais`). RLS por conta;
- `usuarios.recebe_relatorio_mensal` (padrão ligado): a preferência em Minha conta › E-mails do Toqqi;
- `conectores.provedor` aceita `pipedrive` e `hubspot`;
- `emails_enviados.tipo` aceita `relatorio_mensal`.

Revision ID: 0031_relatorio_mensal_crms
Revises: 0030_plano_gratis
"""
import os
import re

from alembic import op

revision = "0031_relatorio_mensal_crms"
down_revision = "0030_plano_gratis"
branch_labels = None
depends_on = None

CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
PROVEDORES_NOVOS = ("rdstation_crm", "omie", "bling", "pipedrive", "hubspot")
PROVEDORES_ANTIGOS = ("rdstation_crm", "omie", "bling")
EMAILS = ("convite", "lembrete", "agradecimento", "teste", "confirmacao", "senha", "boas_vindas", "alerta_risco",
          "resumo_semanal", "pico", "indicacao", "aviso", "cobranca", "retorno", "feedback")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _emails(lista: tuple[str, ...]) -> None:
    op.execute("ALTER TABLE emails_enviados DROP CONSTRAINT emails_enviados_tipo_check")
    op.execute("ALTER TABLE emails_enviados ADD CONSTRAINT emails_enviados_tipo_check "
               f"CHECK (tipo IN ({', '.join(repr(t) for t in lista)}))")


def _provedores(lista: tuple[str, ...]) -> None:
    op.execute("ALTER TABLE conectores DROP CONSTRAINT conectores_provedor_check")
    op.execute("ALTER TABLE conectores ADD CONSTRAINT conectores_provedor_check "
               f"CHECK (provedor IN ({', '.join(repr(p) for p in lista)}))")


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE relatorios_mensais (
            id bigserial PRIMARY KEY,
            {CONTA},
            mes date NOT NULL CHECK (extract(day FROM mes) = 1),
            enviado_em timestamptz,
            destinatarios integer NOT NULL DEFAULT 0 CHECK (destinatarios >= 0),
            UNIQUE (conta_id, mes)
        )
    """)
    op.execute("ALTER TABLE relatorios_mensais ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE relatorios_mensais FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY isolamento_conta ON relatorios_mensais
            USING (conta_id = app_conta() OR app_sistema())
            WITH CHECK (conta_id = app_conta() OR app_sistema())
    """)
    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON relatorios_mensais TO {papel};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE usuarios ADD COLUMN recebe_relatorio_mensal boolean NOT NULL DEFAULT true")
    _provedores(PROVEDORES_NOVOS)
    _emails(EMAILS + ("relatorio_mensal",))


def downgrade() -> None:
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute("DELETE FROM conectores WHERE provedor IN ('pipedrive', 'hubspot')")
    op.execute("DELETE FROM emails_enviados WHERE tipo = 'relatorio_mensal'")
    _emails(EMAILS)
    _provedores(PROVEDORES_ANTIGOS)
    op.execute("ALTER TABLE usuarios DROP COLUMN recebe_relatorio_mensal")
    op.execute("DROP TABLE IF EXISTS relatorios_mensais CASCADE")
