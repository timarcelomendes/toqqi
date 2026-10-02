"""Etapa 5a: assinatura e cobrança pelo Asaas.

`contas` ganha o cliente no Asaas (e o ambiente dele: sandbox | producao), `pago_ate` (último dia coberto por
pagamento), `atrasada_desde` (vencimento da fatura em atraso mais antiga), `primeiro_vencimento` (cópia do primeiro
vencimento da assinatura ativa, para a regra de "liberada" sair só da linha da conta) e `asaas_conferida_em` (última
conferência diária com o Asaas). Tabelas novas:
- `assinaturas` (com o ambiente do Asaas em que existe) e `cobrancas`: padrão das etapas anteriores (conta_id DEFAULT
  app_conta(), RLS com FORCE, chaves compostas (id, conta_id), permissões do papel da aplicação só se ele existir).
  Uma assinatura ativa por conta (índice único parcial).
- `asaas_eventos`: tabela da plataforma (avisos do webhook, sem conta obrigatória). RLS com FORCE e política só para
  o modo sistema: com o contexto de uma conta não se lê nem se grava nada. Guarda só ids e tipo, nunca o corpo.
- `asaas_remocoes`: assinaturas que precisam ser removidas no Asaas e ainda não foram (a tarefa tenta de novo). Conta
  opcional (a linha fica se a conta for excluída): RLS com a política padrão (sem conta, só o modo sistema vê).

Também aqui:
- o gatilho do limite de contatos (`contatos_checar_limite`, da 0002) passa a pegar a trava da conta ANTES de ler o
  plano (sempre, mesmo sem limite): a troca para um plano menor segura a mesma trava enquanto confere os contatos
  ativos e grava o plano, e a inclusão que esperou lê o plano novo;
- CNPJ alfanumérico (Receita Federal, desde 31/07/2026): `documento` de `empresas`, `contas` e `assinaturas` aceita
  12 caracteres [0-9A-Z] + 2 dígitos verificadores (o CPF segue com 11 dígitos).
O downgrade volta a função e os CHECKs antigos (documentos alfanuméricos ficam sem valor).

Revision ID: 0008_assinaturas
Revises: 0007_ia_relatorios
Create Date: 2026-10-01
"""
import os
import re

from alembic import op

revision = "0008_assinaturas"
down_revision = "0007_ia_relatorios"
branch_labels = None
depends_on = None

DA_CONTA = ["assinaturas", "cobrancas", "asaas_remocoes"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
ID_ASAAS = "CHECK (length({c}) BETWEEN 1 AND 100)"
AMBIENTE = "CHECK ({c} IN ('sandbox','producao'))"
DOCUMENTO_NOVO = "^([0-9]{11}|[0-9A-Z]{12}[0-9]{2})$"
DOCUMENTO_ANTIGO = "^([0-9]{11}|[0-9]{14})$"

LIMITE_ANTES = """
    IF NOT NEW.ativo THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.ativo AND OLD.conta_id = NEW.conta_id THEN
        RETURN NEW;  -- já era ativo: não muda a contagem
    END IF;
"""
LIMITE_CONTAGEM = """
    SELECT count(*) INTO v_ativos FROM (
        SELECT 1 FROM contatos
         WHERE conta_id = NEW.conta_id AND ativo AND id <> NEW.id
         LIMIT v_limite
    ) x;
    IF v_ativos >= v_limite THEN
        RAISE EXCEPTION 'Seu plano permite até % contatos ativos.', v_limite
            USING ERRCODE = 'TQ402', DETAIL = v_limite::text;
    END IF;
    RETURN NEW;
"""
FUNCAO_NOVA = f"""
    CREATE OR REPLACE FUNCTION contatos_checar_limite() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_limite integer;
        v_ativos integer;
    BEGIN
        {LIMITE_ANTES}
        -- Trava ANTES de ler o plano (sempre): a troca de plano segura a mesma trava enquanto confere os contatos
        -- ativos e grava o plano novo; quem esperou aqui lê o plano já trocado.
        PERFORM pg_advisory_xact_lock(740221, NEW.conta_id::integer);
        SELECT limite_contatos(c.plano, c.situacao) INTO v_limite FROM contas c WHERE c.id = NEW.conta_id;
        IF v_limite IS NULL THEN
            RETURN NEW;
        END IF;
        {LIMITE_CONTAGEM}
    END $$
"""
FUNCAO_ANTIGA = f"""
    CREATE OR REPLACE FUNCTION contatos_checar_limite() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_limite integer;
        v_ativos integer;
    BEGIN
        {LIMITE_ANTES}
        SELECT limite_contatos(c.plano, c.situacao) INTO v_limite FROM contas c WHERE c.id = NEW.conta_id;
        IF v_limite IS NULL THEN
            RETURN NEW;
        END IF;
        -- Serializa inclusões da mesma conta para a contagem não correr.
        PERFORM pg_advisory_xact_lock(740221, NEW.conta_id::integer);
        {LIMITE_CONTAGEM}
    END $$
"""


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _check_documento(tabela: str, padrao: str) -> None:
    op.execute(f"ALTER TABLE {tabela} DROP CONSTRAINT IF EXISTS {tabela}_documento_check, "
               f"ADD CONSTRAINT {tabela}_documento_check CHECK (documento ~ '{padrao}')")


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE contas
            ADD COLUMN asaas_cliente_id text {ID_ASAAS.format(c="asaas_cliente_id")},
            ADD COLUMN asaas_ambiente text {AMBIENTE.format(c="asaas_ambiente")},
            ADD COLUMN asaas_conferida_em date,
            ADD COLUMN pago_ate date,
            ADD COLUMN atrasada_desde date,
            ADD COLUMN primeiro_vencimento date,
            ADD CONSTRAINT contas_asaas_cliente_ambiente CHECK ((asaas_cliente_id IS NULL) = (asaas_ambiente IS NULL))
    """)
    op.execute("CREATE UNIQUE INDEX contas_asaas_cliente_key ON contas (asaas_cliente_id) "
               "WHERE asaas_cliente_id IS NOT NULL")

    op.execute(f"""
        CREATE TABLE assinaturas (
            id bigserial PRIMARY KEY,
            {CONTA},
            asaas_id text NOT NULL UNIQUE {ID_ASAAS.format(c="asaas_id")},
            ambiente text NOT NULL {AMBIENTE.format(c="ambiente")},
            plano text NOT NULL CHECK (plano IN ('essencial','profissional','empresa')),
            valor numeric(10,2) NOT NULL CHECK (valor > 0),
            situacao text NOT NULL DEFAULT 'ativa' CHECK (situacao IN ('ativa','cancelada')),
            razao_social text NOT NULL CHECK (length(razao_social) BETWEEN 1 AND 200),
            documento text NOT NULL CHECK (documento ~ '{DOCUMENTO_NOVO}'),
            email_cobranca citext NOT NULL CHECK (length(email_cobranca) BETWEEN 3 AND 254),
            telefone text NOT NULL CHECK (telefone ~ '^[0-9]{{10,13}}$'),
            primeiro_vencimento date NOT NULL,
            criada_em timestamptz NOT NULL DEFAULT now(),
            criada_por bigint,
            cancelada_em timestamptz,
            cancelada_por bigint,
            nao_encontrada_desde date,
            UNIQUE (id, conta_id),
            CHECK ((situacao = 'cancelada') = (cancelada_em IS NOT NULL)),
            FOREIGN KEY (criada_por, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (criada_por),
            FOREIGN KEY (cancelada_por, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (cancelada_por)
        )
    """)
    op.execute("CREATE UNIQUE INDEX assinaturas_uma_ativa ON assinaturas (conta_id) WHERE situacao = 'ativa'")
    op.execute("CREATE INDEX assinaturas_conta_idx ON assinaturas (conta_id, criada_em DESC)")

    op.execute(f"""
        CREATE TABLE cobrancas (
            id bigserial PRIMARY KEY,
            {CONTA},
            assinatura_id bigint,
            asaas_id text NOT NULL UNIQUE {ID_ASAAS.format(c="asaas_id")},
            valor numeric(10,2) NOT NULL CHECK (valor >= 0),
            valor_liquido numeric(10,2),
            vencimento date NOT NULL,
            situacao text NOT NULL CHECK (situacao IN ('pendente','paga','vencida','estornada','removida')),
            situacao_asaas text CHECK (length(situacao_asaas) <= 60),
            forma text CHECK (forma IN ('pix','boleto','cartao')),
            pago_em timestamptz,
            link text CHECK (length(link) <= 500),
            criada_em timestamptz NOT NULL DEFAULT now(),
            atualizada_em timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (assinatura_id, conta_id) REFERENCES assinaturas(id, conta_id)
                ON DELETE SET NULL (assinatura_id)
        )
    """)
    op.execute("CREATE INDEX cobrancas_conta_vencimento_idx ON cobrancas (conta_id, vencimento DESC)")
    op.execute("CREATE INDEX cobrancas_assinatura_idx ON cobrancas (assinatura_id)")

    op.execute(f"""
        CREATE TABLE asaas_remocoes (
            asaas_id text PRIMARY KEY {ID_ASAAS.format(c="asaas_id")},
            ambiente text NOT NULL {AMBIENTE.format(c="ambiente")},
            conta_id bigint DEFAULT app_conta() REFERENCES contas(id) ON DELETE SET NULL,
            motivo text NOT NULL CHECK (length(motivo) BETWEEN 1 AND 60),
            criada_em timestamptz NOT NULL DEFAULT now(),
            tentativas smallint NOT NULL DEFAULT 0 CHECK (tentativas BETWEEN 0 AND 10000),
            erro text CHECK (length(erro) <= 300),
            removida_em timestamptz
        )
    """)
    op.execute("CREATE INDEX asaas_remocoes_pendentes_idx ON asaas_remocoes (criada_em) WHERE removida_em IS NULL")

    op.execute(f"""
        CREATE TABLE asaas_eventos (
            id text PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 200),
            tipo text NOT NULL CHECK (length(tipo) BETWEEN 1 AND 100),
            conta_id bigint REFERENCES contas(id) ON DELETE SET NULL,
            cobranca_asaas_id text {ID_ASAAS.format(c="cobranca_asaas_id")},
            assinatura_asaas_id text {ID_ASAAS.format(c="assinatura_asaas_id")},
            recebido_em timestamptz NOT NULL DEFAULT now(),
            processado_em timestamptz,
            ignorado boolean NOT NULL DEFAULT false,
            tentativas smallint NOT NULL DEFAULT 0 CHECK (tentativas BETWEEN 0 AND 100),
            erro text CHECK (length(erro) <= 300)
        )
    """)
    # reprocessamento pela tarefa: os que ainda não foram processados
    op.execute("CREATE INDEX asaas_eventos_pendentes_idx ON asaas_eventos (recebido_em) WHERE processado_em IS NULL")

    for t in DA_CONTA:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY isolamento_conta ON {t}
                USING (conta_id = app_conta() OR app_sistema())
                WITH CHECK (conta_id = app_conta() OR app_sistema())
        """)
    op.execute("ALTER TABLE asaas_eventos ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE asaas_eventos FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY so_sistema ON asaas_eventos USING (app_sistema()) WITH CHECK (app_sistema())")

    op.execute(FUNCAO_NOVA)
    for tabela in ("empresas", "contas"):
        _check_documento(tabela, DOCUMENTO_NOVO)

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON assinaturas, cobrancas, asaas_eventos, asaas_remocoes
                    TO {papel};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute(FUNCAO_ANTIGA)
    for tabela in ("empresas", "contas"):
        op.execute(f"UPDATE {tabela} SET documento = NULL WHERE documento !~ '{DOCUMENTO_ANTIGO}'")
        _check_documento(tabela, DOCUMENTO_ANTIGO)
    op.execute("DROP TABLE IF EXISTS asaas_eventos CASCADE")
    op.execute("DROP TABLE IF EXISTS asaas_remocoes CASCADE")
    op.execute("DROP TABLE IF EXISTS cobrancas CASCADE")
    op.execute("DROP TABLE IF EXISTS assinaturas CASCADE")
    op.execute("DROP INDEX IF EXISTS contas_asaas_cliente_key")
    op.execute("ALTER TABLE contas DROP CONSTRAINT IF EXISTS contas_asaas_cliente_ambiente, "
               "DROP COLUMN asaas_cliente_id, DROP COLUMN asaas_ambiente, DROP COLUMN asaas_conferida_em, "
               "DROP COLUMN pago_ate, DROP COLUMN atrasada_desde, DROP COLUMN primeiro_vencimento")
