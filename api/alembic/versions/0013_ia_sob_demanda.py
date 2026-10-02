"""Etapa 5d: IA sob demanda (resumo do painel, parecer dos relatórios), passos sugeridos nas ações, modelo e estilo.

- `contas`: o nível do modelo (`ia_modelo`: rapido | equilibrado | detalhado), o estilo do texto (`ia_estilo`:
  objetiva | equilibrada | criativa) e o interruptor dos passos das ações (`ia_passos_acoes`, ligado). DEFAULTs
  constantes: não reescrevem a tabela.
- `acoes`: os passos sugeridos pela IA (`ia_passos`: lista de 1 a 3 textos de até 200 caracteres, só com a situação
  'pronta'), a situação (pendente | pronta | falhou | limite; nula = sem passos), quando terminou, as tentativas e a
  marca da reserva (como `respostas.ia_reservada_em` da 4b). Índice parcial da fila (pendentes por conta e criação).
- `ia_pareceres`: o último resumo do painel / parecer dos relatórios gerado para cada recorte (`chave` = filtros
  canônicos); gerar de novo substitui (único `(conta_id, tipo, chave)`). Padrão das etapas anteriores: conta_id
  DEFAULT app_conta() com CASCADE na conta, RLS com FORCE e a política de sempre, chave composta para o usuário que
  gerou (SET NULL quando ele sai da equipe) e permissões do papel da aplicação só se ele existir.

O downgrade apaga a tabela, as colunas e o índice.

Revision ID: 0013_ia_sob_demanda
Revises: 0012_crescimento
Create Date: 2026-10-02
"""
import os
import re

from alembic import op

revision = "0013_ia_sob_demanda"
down_revision = "0012_crescimento"
branch_labels = None
depends_on = None

NOVAS = ["ia_pareceres"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
NIVEIS = "'rapido','equilibrado','detalhado'"
ESTILOS = "'objetiva','equilibrada','criativa'"
# lista de 1 a 3 textos, cada um com 1 a 200 caracteres
PASSOS_VALIDOS = ("jsonb_typeof(ia_passos) = 'array' AND jsonb_array_length(ia_passos) BETWEEN 1 AND 3 "
                  "AND NOT jsonb_path_exists(ia_passos, "
                  "'$[*] ? (@.type() != \"string\" || !(@ like_regex \"^.{1,200}$\" flag \"s\"))')")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE contas
            ADD COLUMN ia_modelo text NOT NULL DEFAULT 'equilibrado' CHECK (ia_modelo IN ({NIVEIS})),
            ADD COLUMN ia_estilo text NOT NULL DEFAULT 'equilibrada' CHECK (ia_estilo IN ({ESTILOS})),
            ADD COLUMN ia_passos_acoes boolean NOT NULL DEFAULT true
    """)
    op.execute(f"""
        ALTER TABLE acoes
            ADD COLUMN ia_passos jsonb CONSTRAINT acoes_ia_passos_check CHECK ({PASSOS_VALIDOS}),
            ADD COLUMN ia_passos_situacao text
                CHECK (ia_passos_situacao IN ('pendente','pronta','falhou','limite')),
            ADD COLUMN ia_passos_em timestamptz,
            ADD COLUMN ia_passos_tentativas smallint NOT NULL DEFAULT 0
                CHECK (ia_passos_tentativas BETWEEN 0 AND 100),
            ADD COLUMN ia_passos_reservada_em timestamptz,
            ADD CONSTRAINT acoes_ia_passos_so_pronta
                CHECK ((ia_passos IS NOT NULL) = coalesce(ia_passos_situacao = 'pronta', false))
    """)
    # fila dos passos: pendentes de cada conta, das mais antigas para as mais novas
    op.execute("CREATE INDEX acoes_ia_passos_fila_idx ON acoes (conta_id, criada_em) "
               "WHERE ia_passos_situacao = 'pendente'")

    op.execute(f"""
        CREATE TABLE ia_pareceres (
            id bigserial PRIMARY KEY,
            {CONTA},
            tipo text NOT NULL CHECK (tipo IN ('painel','relatorios')),
            chave text NOT NULL CHECK (length(chave) BETWEEN 1 AND 200),
            filtros jsonb NOT NULL CHECK (jsonb_typeof(filtros) = 'object'),
            conteudo jsonb NOT NULL CHECK (jsonb_typeof(conteudo) = 'object'),
            modelo text NOT NULL CHECK (modelo IN ({NIVEIS})),
            estilo text NOT NULL CHECK (estilo IN ({ESTILOS})),
            gerado_por bigint,
            gerado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (conta_id, tipo, chave),
            FOREIGN KEY (gerado_por, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (gerado_por)
        )
    """)
    op.execute("CREATE INDEX ia_pareceres_recentes_idx ON ia_pareceres (conta_id, tipo, gerado_em DESC)")
    # o SET NULL quando o usuário sai da equipe
    op.execute("CREATE INDEX ia_pareceres_usuario_idx ON ia_pareceres (gerado_por) WHERE gerado_por IS NOT NULL")

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
    op.execute("DROP INDEX IF EXISTS acoes_ia_passos_fila_idx")
    op.execute("""
        ALTER TABLE acoes
            DROP CONSTRAINT IF EXISTS acoes_ia_passos_so_pronta,
            DROP COLUMN IF EXISTS ia_passos,
            DROP COLUMN IF EXISTS ia_passos_situacao,
            DROP COLUMN IF EXISTS ia_passos_em,
            DROP COLUMN IF EXISTS ia_passos_tentativas,
            DROP COLUMN IF EXISTS ia_passos_reservada_em
    """)
    op.execute("""
        ALTER TABLE contas
            DROP COLUMN IF EXISTS ia_modelo,
            DROP COLUMN IF EXISTS ia_estilo,
            DROP COLUMN IF EXISTS ia_passos_acoes
    """)
