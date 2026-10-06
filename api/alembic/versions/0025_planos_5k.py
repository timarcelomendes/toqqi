"""Etapa 5k (docs/api-etapa-5k.md §5): ciclo anual, Pix com desconto e plano Personalizado.

- `assinaturas`: `ciclo` (mensal | anual), `forma` (pix | qualquer), `contatos` e `cota_ia` (só no Personalizado); o
  CHECK do plano aceita `personalizado` (com contatos e cota preenchidos);
- `contas`: `contatos_personalizado` e `cota_ia_personalizada` (o contratado, gravado ao assinar ou trocar);
- `parametros`: a chave aceita dígitos (`planos.personalizado.ate_1500`, `ia_500`…);
- `limite_contatos(p_plano, p_situacao)`: o padrão do Empresa passa de sem limite a 5.000;
- gatilho `contatos_checar_limite`: no Personalizado (fora da cortesia), o limite é `contas.contatos_personalizado`.

O downgrade volta tudo; assinaturas Personalizado ou anuais impedem (o CHECK antigo recusa).

Revision ID: 0025_planos_5k
Revises: 0024_depoimentos
"""
from alembic import op

revision = "0025_planos_5k"
down_revision = "0024_depoimentos"
branch_labels = None
depends_on = None

CHAVE_NOVA = r"^(planos|ia|whatsapp|teste)\.[a-z0-9_]+(\.[a-z0-9_]+)?$"
CHAVE_ANTIGA = r"^(planos|ia|whatsapp|teste)\.[a-z_]+(\.[a-z_]+)?$"

LIMITE = """
    CREATE OR REPLACE FUNCTION limite_contatos(p_plano text, p_situacao text) RETURNS integer
    LANGUAGE sql STABLE AS $$
        WITH linha AS (
            SELECT CASE WHEN jsonb_typeof(valor) = 'number' AND valor::text ~ '^[0-9]{{1,7}}$'
                        THEN (valor::text)::integer END AS limite
              FROM parametros
             WHERE chave = 'planos.' || p_plano || '.contatos'
               AND CASE WHEN jsonb_typeof(valor) = 'null' THEN true
                        WHEN jsonb_typeof(valor) = 'number' AND valor::text ~ '^[0-9]{{1,7}}$'
                            THEN (valor::text)::integer BETWEEN 1 AND 1000000
                        ELSE false
                   END
        )
        SELECT CASE
            WHEN p_situacao = 'cortesia' THEN NULL
            WHEN EXISTS (SELECT 1 FROM linha) THEN (SELECT limite FROM linha)
            WHEN p_plano = 'essencial' THEN 300
            WHEN p_plano = 'profissional' THEN 1500
            {empresa}
            ELSE NULL
        END
    $$
"""

GATILHO = """
    CREATE OR REPLACE FUNCTION contatos_checar_limite() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_limite integer;
        v_ativos integer;
    BEGIN
        IF NOT NEW.ativo THEN
            RETURN NEW;
        END IF;
        IF TG_OP = 'UPDATE' AND OLD.ativo AND OLD.conta_id = NEW.conta_id THEN
            RETURN NEW;  -- já era ativo: não muda a contagem
        END IF;
        -- Trava ANTES de ler o plano (sempre): a troca de plano segura a mesma trava enquanto confere os contatos
        -- ativos e grava o plano novo; quem esperou aqui lê o plano já trocado.
        PERFORM pg_advisory_xact_lock(740221, NEW.conta_id::integer);
        SELECT {limite} INTO v_limite FROM contas c WHERE c.id = NEW.conta_id;
        IF v_limite IS NULL THEN
            RETURN NEW;
        END IF;
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
    END $$
"""
LIMITE_NOVO = ("CASE WHEN c.plano = 'personalizado' AND c.situacao <> 'cortesia' THEN c.contatos_personalizado "
               "ELSE limite_contatos(c.plano, c.situacao) END")
LIMITE_ANTIGO = "limite_contatos(c.plano, c.situacao)"


def upgrade() -> None:
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS parametros_chave_check")
    op.execute(f"ALTER TABLE parametros ADD CONSTRAINT parametros_chave_check CHECK (chave ~ '{CHAVE_NOVA}')")
    op.execute("ALTER TABLE contas ADD COLUMN contatos_personalizado integer "
               "CHECK (contatos_personalizado BETWEEN 100 AND 100000), "
               "ADD COLUMN cota_ia_personalizada integer CHECK (cota_ia_personalizada IN (100, 500, 2000, 5000))")
    op.execute("ALTER TABLE assinaturas DROP CONSTRAINT IF EXISTS assinaturas_plano_check")
    op.execute("ALTER TABLE assinaturas "
               "ADD COLUMN ciclo text NOT NULL DEFAULT 'mensal' CHECK (ciclo IN ('mensal','anual')), "
               "ADD COLUMN forma text NOT NULL DEFAULT 'qualquer' CHECK (forma IN ('pix','qualquer')), "
               "ADD COLUMN contatos integer CHECK (contatos BETWEEN 100 AND 100000), "
               "ADD COLUMN cota_ia integer CHECK (cota_ia IN (100, 500, 2000, 5000)), "
               "ADD CONSTRAINT assinaturas_plano_check CHECK ("
               "(plano IN ('essencial','profissional','empresa') AND contatos IS NULL AND cota_ia IS NULL) OR "
               "(plano = 'personalizado' AND contatos IS NOT NULL AND cota_ia IS NOT NULL)), "
               "ADD CONSTRAINT assinaturas_anual_qualquer CHECK (ciclo = 'mensal' OR forma = 'qualquer')")
    op.execute(LIMITE.format(empresa="WHEN p_plano = 'empresa' THEN 5000"))
    op.execute(GATILHO.format(limite=LIMITE_NOVO))


def downgrade() -> None:
    op.execute(GATILHO.format(limite=LIMITE_ANTIGO))
    op.execute(LIMITE.format(empresa=""))
    op.execute("ALTER TABLE assinaturas DROP CONSTRAINT assinaturas_anual_qualquer, "
               "DROP CONSTRAINT assinaturas_plano_check, DROP COLUMN cota_ia, DROP COLUMN contatos, "
               "DROP COLUMN forma, DROP COLUMN ciclo")
    op.execute("ALTER TABLE assinaturas ADD CONSTRAINT assinaturas_plano_check "
               "CHECK (plano IN ('essencial','profissional','empresa'))")
    op.execute("ALTER TABLE contas DROP COLUMN cota_ia_personalizada, DROP COLUMN contatos_personalizado")
    op.execute("DELETE FROM parametros WHERE chave !~ '" + CHAVE_ANTIGA + "'")
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS parametros_chave_check")
    op.execute(f"ALTER TABLE parametros ADD CONSTRAINT parametros_chave_check CHECK (chave ~ '{CHAVE_ANTIGA}')")
