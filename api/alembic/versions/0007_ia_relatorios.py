"""Etapa 4b: IA por resposta (situação, temas com sentimento, resumo), reclamações e elogios por tema, teto mensal
de análises, alertas de pico, resumo semanal e preferências de e-mail dos usuários.

Mesmo padrão das etapas anteriores: conta_id DEFAULT app_conta(), RLS com FORCE e permissões do papel da
aplicação só se ele existir.

`temas_reclamacao` e `temas_elogio` são colunas geradas por funções SQL IMMUTABLE de (temas, ia_temas,
ia_situacao, grupo): nunca ficam fora de sincronia com a análise. Regra (`classe_tema`): se a IA analisou a
resposta e citou o tema, vale o sentimento dela (negativo = reclamação, positivo = elogio); senão vale o grupo da
nota (detrator/insatisfeito = reclamação, promotor/satisfeito = elogio). Corpo SQL padrão (BEGIN ATOMIC/RETURN):
as referências ficam resolvidas na criação, sem depender do search_path (restauração de backup).

Revision ID: 0007_ia_relatorios
Revises: 0006_dados_empresa
Create Date: 2026-10-01
"""
import os
import re

from alembic import op

revision = "0007_ia_relatorios"
down_revision = "0006_dados_empresa"
branch_labels = None
depends_on = None

NOVAS = ["ia_uso_mensal", "alertas_pico", "resumos_semanais"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
TEMAS = "'prazo_entrega','produto_avarias','atendimento','preco_condicoes','comunicacao','sistema_pedidos'"


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute("""
        ALTER TABLE respostas
            ADD COLUMN ia_situacao text CHECK (ia_situacao IN ('pendente','analisada','falhou','limite')),
            ADD COLUMN ia_temas jsonb CHECK (jsonb_typeof(ia_temas) = 'array'),
            ADD COLUMN ia_sentimento text CHECK (ia_sentimento IN ('positivo','neutro','negativo','misto')),
            ADD COLUMN ia_resumo text CHECK (length(ia_resumo) <= 160),
            ADD COLUMN ia_modelo text CHECK (length(ia_modelo) <= 100),
            ADD COLUMN ia_em timestamptz,
            ADD COLUMN ia_tentativas smallint NOT NULL DEFAULT 0 CHECK (ia_tentativas BETWEEN 0 AND 100),
            ADD COLUMN ia_reservada_em timestamptz,
            ADD COLUMN ia_texto_hash text CHECK (ia_texto_hash ~ '^[0-9a-f]{64}$')
    """)
    # 'reclamacao' | 'elogio' | null para um tema da resposta (regra no cabeçalho)
    op.execute("""
        CREATE FUNCTION classe_tema(p_tema text, p_ia_temas jsonb, p_ia_situacao text, p_grupo text)
        RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE
        RETURN CASE coalesce(
                   (SELECT e ->> 'sentimento'
                      FROM jsonb_array_elements(CASE WHEN p_ia_situacao = 'analisada'
                                                          AND jsonb_typeof(p_ia_temas) = 'array'
                                                     THEN p_ia_temas ELSE '[]'::jsonb END) AS e
                     WHERE e ->> 'tema' = p_tema
                     LIMIT 1),
                   CASE WHEN p_grupo IN ('detrator', 'insatisfeito') THEN 'negativo'
                        WHEN p_grupo IN ('promotor', 'satisfeito') THEN 'positivo' END)
                 WHEN 'negativo' THEN 'reclamacao'
                 WHEN 'positivo' THEN 'elogio'
               END
    """)
    # sem análise da IA, a classe é a mesma para todos os temas (pela nota): atalho sem olhar tema a tema
    for nome, classe, grupos in (("temas_reclamacao", "reclamacao", "'detrator', 'insatisfeito'"),
                                 ("temas_elogio", "elogio", "'promotor', 'satisfeito'")):
        op.execute(f"""
            CREATE FUNCTION {nome}(p_temas text[], p_ia_temas jsonb, p_ia_situacao text, p_grupo text)
            RETURNS text[] LANGUAGE sql IMMUTABLE PARALLEL SAFE
            RETURN CASE
                WHEN p_ia_situacao = 'analisada' THEN
                    (SELECT coalesce(array_agg(u.t ORDER BY u.o), '{{}}'::text[])
                       FROM unnest(p_temas) WITH ORDINALITY AS u(t, o)
                      WHERE classe_tema(u.t, p_ia_temas, p_ia_situacao, p_grupo) = '{classe}')
                WHEN p_grupo IN ({grupos}) THEN coalesce(p_temas, '{{}}'::text[])
                ELSE '{{}}'::text[]
            END
        """)
        op.execute(f"ALTER TABLE respostas ADD COLUMN {nome} text[] NOT NULL "
                   f"GENERATED ALWAYS AS ({nome}(temas, ia_temas, ia_situacao, grupo)) STORED")

    # fila da IA: pendentes sem reserva primeiro, das mais antigas para as mais novas
    op.execute("CREATE INDEX respostas_ia_fila_idx ON respostas (ia_reservada_em NULLS FIRST, criada_em) "
               "WHERE ia_situacao = 'pendente'")
    # relatórios: respostas de cada empresa no período (histórico, empresas, responsáveis)
    op.execute("CREATE INDEX respostas_empresa_data_idx ON respostas (conta_id, empresa_id, data_resposta DESC) "
               "WHERE NOT arquivada")

    op.execute("ALTER TABLE contas ADD COLUMN ia_analise_respostas boolean NOT NULL DEFAULT true")
    op.execute("ALTER TABLE usuarios ADD COLUMN recebe_resumo_semanal boolean NOT NULL DEFAULT true, "
               "ADD COLUMN recebe_alertas boolean NOT NULL DEFAULT true")

    op.execute(f"""
        CREATE TABLE ia_uso_mensal (
            {CONTA},
            mes date NOT NULL CHECK (extract(day FROM mes) = 1),
            analises integer NOT NULL DEFAULT 0 CHECK (analises >= 0),
            tokens_entrada bigint NOT NULL DEFAULT 0 CHECK (tokens_entrada >= 0),
            tokens_saida bigint NOT NULL DEFAULT 0 CHECK (tokens_saida >= 0),
            PRIMARY KEY (conta_id, mes)
        )
    """)
    op.execute(f"""
        CREATE TABLE alertas_pico (
            id bigserial PRIMARY KEY,
            {CONTA},
            tema text NOT NULL CHECK (tema IN ({TEMAS})),
            reclamacoes integer NOT NULL CHECK (reclamacoes >= 0),
            media_anterior numeric(6,1) NOT NULL CHECK (media_anterior >= 0),
            detectado_em timestamptz NOT NULL DEFAULT now(),
            enviado_em timestamptz,
            destinatarios integer NOT NULL DEFAULT 0 CHECK (destinatarios >= 0)
        )
    """)
    op.execute("CREATE INDEX alertas_pico_tema_idx ON alertas_pico (conta_id, tema, detectado_em DESC)")
    op.execute(f"""
        CREATE TABLE resumos_semanais (
            id bigserial PRIMARY KEY,
            {CONTA},
            semana date NOT NULL CHECK (extract(isodow FROM semana) = 1),
            enviado_em timestamptz,
            destinatarios integer NOT NULL DEFAULT 0 CHECK (destinatarios >= 0),
            UNIQUE (conta_id, semana)
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
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    for t in reversed(NOVAS):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("ALTER TABLE usuarios DROP COLUMN recebe_resumo_semanal, DROP COLUMN recebe_alertas")
    op.execute("ALTER TABLE contas DROP COLUMN ia_analise_respostas")
    op.execute("DROP INDEX IF EXISTS respostas_empresa_data_idx")
    op.execute("DROP INDEX IF EXISTS respostas_ia_fila_idx")
    op.execute("ALTER TABLE respostas DROP COLUMN temas_reclamacao, DROP COLUMN temas_elogio")
    op.execute("DROP FUNCTION temas_reclamacao(text[], jsonb, text, text)")
    op.execute("DROP FUNCTION temas_elogio(text[], jsonb, text, text)")
    op.execute("DROP FUNCTION classe_tema(text, jsonb, text, text)")
    op.execute("""
        ALTER TABLE respostas
            DROP COLUMN ia_situacao,
            DROP COLUMN ia_temas,
            DROP COLUMN ia_sentimento,
            DROP COLUMN ia_resumo,
            DROP COLUMN ia_modelo,
            DROP COLUMN ia_em,
            DROP COLUMN ia_tentativas,
            DROP COLUMN ia_reservada_em,
            DROP COLUMN ia_texto_hash
    """)
