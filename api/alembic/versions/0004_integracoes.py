"""Etapa 3b: chave de integração, webhooks de saída (com fila de entregas), WhatsApp automático (conta,
uso mensal da franquia), idempotência dos eventos; colunas novas em convites, envios, descadastros e
config_envios.

Mesmo padrão das etapas anteriores: conta_id DEFAULT app_conta(), RLS com FORCE e chaves compostas
(id, conta_id) nas referências entre tabelas da conta. As buscas feitas antes de a conta ser conhecida
(hash da chave, phone_number_id) rodam em modo sistema.

Revision ID: 0004_integracoes
Revises: 0003_envios
Create Date: 2026-09-30
"""
import os
import re

from alembic import op

revision = "0004_integracoes"
down_revision = "0003_envios"
branch_labels = None
depends_on = None

NOVAS = ["integracao_chaves", "webhooks", "webhook_entregas", "whatsapp_contas", "whatsapp_uso",
         "eventos_idempotencia"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute("ALTER TABLE convites ADD COLUMN evento text CHECK (length(evento) <= 60)")
    op.execute("DROP INDEX convites_abertos_idx")
    op.execute("CREATE INDEX convites_abertos_idx ON convites (conta_id, criado_em) "
               "WHERE respondido_em IS NULL AND canal IN ('email', 'whatsapp')")

    # cobranca: o envio por WhatsApp automático gastou franquia ou excedente (devolvido se não sair)
    op.execute("ALTER TABLE envios ADD COLUMN wamid text, "
               "ADD COLUMN cobranca text CHECK (cobranca IN ('franquia','excedente'))")
    op.execute("ALTER TABLE envios DROP CONSTRAINT envios_situacao_check")
    op.execute("ALTER TABLE envios ADD CONSTRAINT envios_situacao_check "
               "CHECK (situacao IN ('pendente','enviado','entregue','lido','erro','aberto_no_whatsapp'))")
    op.execute("CREATE UNIQUE INDEX envios_wamid_idx ON envios (wamid) WHERE wamid IS NOT NULL")

    op.execute("""
        ALTER TABLE descadastros
            ALTER COLUMN email DROP NOT NULL,
            ADD COLUMN telefone text CHECK (telefone ~ '^[0-9]{10,13}$'),
            ADD CONSTRAINT descadastros_email_ou_telefone CHECK (email IS NOT NULL OR telefone IS NOT NULL),
            DROP CONSTRAINT descadastros_origem_check,
            ADD CONSTRAINT descadastros_origem_check CHECK (origem IN ('link','um_clique','manual','whatsapp'))
    """)
    op.execute("CREATE UNIQUE INDEX descadastros_telefone_key ON descadastros (conta_id, telefone) "
               "WHERE telefone IS NOT NULL")

    op.execute("ALTER TABLE config_envios ADD COLUMN canal text NOT NULL DEFAULT 'email' "
               "CHECK (canal IN ('email','whatsapp','whatsapp_e_email'))")

    op.execute("""
        CREATE TABLE integracao_chaves (
            conta_id bigint PRIMARY KEY DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            hash text NOT NULL UNIQUE,
            prefixo text NOT NULL,
            usuario_id bigint,
            criada_em timestamptz NOT NULL DEFAULT now(),
            ultimo_uso timestamptz,
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id)
        )
    """)

    op.execute(f"""
        CREATE TABLE webhooks (
            id bigserial PRIMARY KEY,
            {CONTA},
            url text NOT NULL CHECK (url LIKE 'https://%' AND length(url) <= 500),
            eventos text[] NOT NULL
                CHECK (cardinality(eventos) >= 1 AND eventos <@ ARRAY['resposta.criada','contato.descadastrado']),
            ativo boolean NOT NULL DEFAULT true,
            segredo_cifrado text NOT NULL,
            segredo_prefixo text NOT NULL,
            falhas_seguidas integer NOT NULL DEFAULT 0 CHECK (falhas_seguidas >= 0),
            ultima_entrega_em timestamptz,
            ultimo_status_http integer,
            ultima_ok boolean,
            criado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (id, conta_id)
        )
    """)
    op.execute("CREATE INDEX webhooks_conta_idx ON webhooks (conta_id)")

    op.execute(f"""
        CREATE TABLE webhook_entregas (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {CONTA},
            webhook_id bigint NOT NULL,
            evento text NOT NULL,
            corpo jsonb NOT NULL,
            status text NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','ok','falhou')),
            tentativas smallint NOT NULL DEFAULT 0 CHECK (tentativas >= 0),
            proxima_tentativa timestamptz NOT NULL DEFAULT now(),
            status_http integer,
            erro text,
            criado_em timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (webhook_id, conta_id) REFERENCES webhooks(id, conta_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX webhook_entregas_webhook_idx ON webhook_entregas (conta_id, webhook_id, criado_em DESC)")
    op.execute("CREATE INDEX webhook_entregas_fila_idx ON webhook_entregas (proxima_tentativa) "
               "WHERE status = 'pendente'")

    op.execute("""
        CREATE TABLE whatsapp_contas (
            conta_id bigint PRIMARY KEY DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            phone_number_id text NOT NULL UNIQUE CHECK (phone_number_id ~ '^[0-9]{5,30}$'),
            waba_id text NOT NULL CHECK (waba_id ~ '^[0-9]{5,30}$'),
            token_cifrado text NOT NULL,
            modelo_nome text NOT NULL,
            modelo_idioma text NOT NULL,
            modelo_botao smallint NOT NULL DEFAULT 0,
            ativo boolean NOT NULL DEFAULT true,
            excedente_ativo boolean NOT NULL DEFAULT false,
            ultimo_erro text,
            numero_exibicao text,
            nome_verificado text,
            conectado_em timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute(f"""
        CREATE TABLE whatsapp_uso (
            {CONTA},
            mes text NOT NULL CHECK (mes ~ '^[0-9]{{4}}-[0-9]{{2}}$'),
            usadas integer NOT NULL DEFAULT 0 CHECK (usadas >= 0),
            excedentes integer NOT NULL DEFAULT 0 CHECK (excedentes >= 0),
            avisou_80 boolean NOT NULL DEFAULT false,
            avisou_100 boolean NOT NULL DEFAULT false,
            PRIMARY KEY (conta_id, mes)
        )
    """)

    op.execute(f"""
        CREATE TABLE eventos_idempotencia (
            {CONTA},
            id_evento text NOT NULL CHECK (length(id_evento) <= 100),
            resposta jsonb NOT NULL,
            expira timestamptz NOT NULL,
            PRIMARY KEY (conta_id, id_evento)
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
    op.execute("ALTER TABLE config_envios DROP COLUMN canal")
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute("DELETE FROM descadastros WHERE email IS NULL OR origem = 'whatsapp'")
    op.execute("DROP INDEX IF EXISTS descadastros_telefone_key")
    op.execute("""
        ALTER TABLE descadastros
            DROP CONSTRAINT descadastros_email_ou_telefone,
            DROP COLUMN telefone,
            ALTER COLUMN email SET NOT NULL,
            DROP CONSTRAINT descadastros_origem_check,
            ADD CONSTRAINT descadastros_origem_check CHECK (origem IN ('link','um_clique','manual'))
    """)
    op.execute("DROP INDEX IF EXISTS envios_wamid_idx")
    op.execute("UPDATE envios SET situacao = 'enviado' WHERE situacao IN ('entregue','lido')")
    op.execute("ALTER TABLE envios DROP CONSTRAINT envios_situacao_check")
    op.execute("ALTER TABLE envios ADD CONSTRAINT envios_situacao_check "
               "CHECK (situacao IN ('pendente','enviado','erro','aberto_no_whatsapp'))")
    op.execute("ALTER TABLE envios DROP COLUMN wamid, DROP COLUMN cobranca")
    op.execute("DROP INDEX IF EXISTS convites_abertos_idx")
    op.execute("CREATE INDEX convites_abertos_idx ON convites (conta_id, criado_em) "
               "WHERE respondido_em IS NULL AND canal = 'email'")
    op.execute("ALTER TABLE convites DROP COLUMN evento")
