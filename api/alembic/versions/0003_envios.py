"""Etapa 3a: configurações de envio, envios (histórico), descadastros; colunas de fila nos contatos e de
lembretes nos convites; auditoria global (sem conta) para eventos da plataforma.

Mesmo padrão das etapas anteriores: conta_id DEFAULT app_conta(), RLS com FORCE e chaves compostas
(id, conta_id) nas referências entre tabelas da conta.

Revision ID: 0003_envios
Revises: 0002_cadastros_formularios
Create Date: 2026-09-30
"""
import os
import re

from alembic import op

revision = "0003_envios"
down_revision = "0002_cadastros_formularios"
branch_labels = None
depends_on = None

NOVAS = ["config_envios", "envios", "descadastros"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    # Eventos da plataforma (ex.: conta excluída) ficam sem conta: só o modo sistema os enxerga.
    op.execute("ALTER TABLE auditoria ALTER COLUMN conta_id DROP NOT NULL")

    op.execute("""
        ALTER TABLE contatos
            ADD COLUMN proximo_envio date,
            ADD COLUMN ultimo_envio timestamptz,
            ADD COLUMN falhas integer NOT NULL DEFAULT 0 CHECK (falhas >= 0)
    """)
    op.execute("CREATE INDEX contatos_fila_idx ON contatos (conta_id, proximo_envio NULLS FIRST) WHERE ativo")

    # token_semente: permite refazer o mesmo link no lembrete (token = HMAC(JWT_SECRET, semente));
    # só com o banco não dá para montar o link.
    op.execute("""
        ALTER TABLE convites
            ADD COLUMN lembretes_enviados smallint NOT NULL DEFAULT 0 CHECK (lembretes_enviados BETWEEN 0 AND 3),
            ADD COLUMN ultimo_lembrete_em timestamptz,
            ADD COLUMN token_semente text
    """)
    op.execute("DROP INDEX convites_contato_idx")
    op.execute("CREATE INDEX convites_contato_idx ON convites (conta_id, contato_id, criado_em DESC)")
    op.execute("CREATE INDEX convites_abertos_idx ON convites (conta_id, criado_em) "
                "WHERE respondido_em IS NULL AND canal = 'email'")

    op.execute("""
        CREATE TABLE config_envios (
            conta_id bigint PRIMARY KEY DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            envios_ativos boolean NOT NULL DEFAULT false,
            envio_automatico boolean NOT NULL DEFAULT false,
            formulario_id bigint,
            intervalo_dias integer NOT NULL DEFAULT 90 CHECK (intervalo_dias BETWEEN 30 AND 365),
            descanso_dias integer NOT NULL DEFAULT 30 CHECK (descanso_dias BETWEEN 0 AND 180),
            lembretes integer NOT NULL DEFAULT 3 CHECK (lembretes BETWEEN 0 AND 3),
            dias_lembretes integer[] NOT NULL DEFAULT '{3,7,15}',
            janela_inicio time NOT NULL DEFAULT '08:00',
            janela_fim time NOT NULL DEFAULT '18:00',
            so_dias_uteis boolean NOT NULL DEFAULT true,
            responder_para citext,
            remetente_nome text,
            assunto_convite text NOT NULL,
            texto_convite text NOT NULL,
            assunto_lembrete text NOT NULL,
            texto_lembrete text NOT NULL,
            texto_whatsapp text NOT NULL,
            agradecimento_ativo boolean NOT NULL DEFAULT true,
            agradecimento jsonb NOT NULL,
            robo_rodou_em timestamptz,
            lembretes_rodou_em date,
            atualizado_em timestamptz NOT NULL DEFAULT now(),
            CHECK (janela_fim > janela_inicio),
            CHECK (cardinality(dias_lembretes) = lembretes),
            FOREIGN KEY (formulario_id, conta_id) REFERENCES formularios(id, conta_id)
                ON DELETE SET NULL (formulario_id)
        )
    """)
    op.execute("CREATE INDEX config_envios_ativos_idx ON config_envios (conta_id) WHERE envios_ativos")

    op.execute("ALTER TABLE respostas ADD CONSTRAINT respostas_id_conta_key UNIQUE (id, conta_id)")
    op.execute(f"""
        CREATE TABLE envios (
            id bigserial PRIMARY KEY,
            {CONTA},
            contato_id bigint,
            convite_id bigint,
            resposta_id bigint,
            usuario_id bigint,
            canal text NOT NULL CHECK (canal IN ('email','whatsapp')),
            tipo text NOT NULL CHECK (tipo IN ('convite','lembrete','agradecimento')),
            origem text NOT NULL CHECK (origem IN ('manual','automatico','lembrete','resposta')),
            situacao text NOT NULL DEFAULT 'pendente'
                CHECK (situacao IN ('pendente','enviado','erro','aberto_no_whatsapp')),
            para text NOT NULL,
            erro text,
            lembrete smallint CHECK (lembrete BETWEEN 1 AND 3),
            criado_em timestamptz NOT NULL DEFAULT now(),
            tentativa_em timestamptz,
            enviado_em timestamptz,
            UNIQUE (id, conta_id),
            FOREIGN KEY (contato_id, conta_id) REFERENCES contatos(id, conta_id) ON DELETE SET NULL (contato_id),
            FOREIGN KEY (convite_id, conta_id) REFERENCES convites(id, conta_id) ON DELETE SET NULL (convite_id),
            FOREIGN KEY (resposta_id, conta_id) REFERENCES respostas(id, conta_id) ON DELETE SET NULL (resposta_id),
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id)
        )
    """)
    op.execute("CREATE INDEX envios_conta_data_idx ON envios (conta_id, criado_em DESC)")
    op.execute("CREATE INDEX envios_contato_idx ON envios (conta_id, contato_id, id DESC)")
    op.execute("CREATE INDEX envios_convite_idx ON envios (conta_id, convite_id, id DESC)")
    op.execute("CREATE INDEX envios_pendentes_idx ON envios (criado_em) WHERE situacao = 'pendente'")

    op.execute(f"""
        CREATE TABLE descadastros (
            id bigserial PRIMARY KEY,
            {CONTA},
            email citext NOT NULL,
            motivo text CHECK (length(motivo) <= 300),
            origem text NOT NULL CHECK (origem IN ('link','um_clique','manual')),
            usuario_id bigint,
            criado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (conta_id, email),
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id)
        )
    """)

    for t in NOVAS:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY isolamento_conta ON {t}
                USING (conta_id = app_conta() OR app_sistema())
                WITH CHECK (conta_id = app_conta() OR app_sistema())
        """)

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {", ".join(NOVAS)} TO {papel};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    for t in reversed(NOVAS):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("ALTER TABLE respostas DROP CONSTRAINT IF EXISTS respostas_id_conta_key")
    op.execute("DROP INDEX IF EXISTS convites_abertos_idx")
    op.execute("DROP INDEX IF EXISTS convites_contato_idx")
    op.execute("CREATE INDEX convites_contato_idx ON convites (conta_id, contato_id)")
    op.execute("ALTER TABLE convites DROP COLUMN lembretes_enviados, DROP COLUMN ultimo_lembrete_em, "
               "DROP COLUMN token_semente")
    op.execute("DROP INDEX IF EXISTS contatos_fila_idx")
    op.execute("ALTER TABLE contatos DROP COLUMN proximo_envio, DROP COLUMN ultimo_envio, DROP COLUMN falhas")
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute("DELETE FROM auditoria WHERE conta_id IS NULL")
    op.execute("ALTER TABLE auditoria ALTER COLUMN conta_id SET NOT NULL")
