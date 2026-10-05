"""Etapa 5h: aviso de erros (tabela `erros`).

- `erros` (sem conta na RLS): um registro por falha diferente, achada pela `impressao` (sha256 de origem + tipo +
  local + a primeira linha útil da pilha, `core.erros`), com a contagem de ocorrências, a primeira e a última vez.
  Guarda só o que diagnostica, **sem dados pessoais**: `origem` (`api` | `site` | `tarefa`), `tipo` (≤ 80), `mensagem`
  (≤ 300, já limpa), `local` (≤ 200: a rota com o modelo do caminho, a tela sem query nem hash ou o nome da tarefa),
  `pilha` (≤ 1.000, limpa), `versao` (≤ 40), `ultimo_request_id` (≤ 64) e `conta_id` (nulo; **sem FK**: a linha
  sobrevive à exclusão da conta). `resolvido_em` nulo = aberto; uma ocorrência nova reabre. Índice `(ultima_em DESC)`
  para a lista, o e-mail diário e a limpeza de 30 dias.
- RLS forçado com só a política `sistema` (só o modo sistema lê e grava; em conta, nada). Papel da aplicação: SELECT,
  INSERT, UPDATE e DELETE (a limpeza apaga, "Resolver" e "Reabrir" mudam).

O downgrade apaga a tabela.

Revision ID: 0017_erros
Revises: 0016_parametros
Create Date: 2026-10-04
"""
import os
import re

from alembic import op

revision = "0017_erros"
down_revision = "0016_parametros"
branch_labels = None
depends_on = None

ORIGENS = ("api", "site", "tarefa")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    origens = ",".join(f"'{o}'" for o in ORIGENS)
    op.execute(f"""
        CREATE TABLE erros (
            id bigserial PRIMARY KEY,
            impressao text NOT NULL UNIQUE CHECK (length(impressao) = 64),
            origem text NOT NULL CHECK (origem IN ({origens})),
            tipo text NOT NULL CHECK (length(tipo) BETWEEN 1 AND 80),
            mensagem text NOT NULL DEFAULT '' CHECK (length(mensagem) <= 300),
            local text NOT NULL DEFAULT '' CHECK (length(local) <= 200),
            pilha text NOT NULL DEFAULT '' CHECK (length(pilha) <= 1000),
            versao text NOT NULL CHECK (length(versao) BETWEEN 1 AND 40),
            ocorrencias integer NOT NULL DEFAULT 1 CHECK (ocorrencias >= 1),
            primeira_em timestamptz NOT NULL DEFAULT now(),
            ultima_em timestamptz NOT NULL DEFAULT now(),
            ultimo_request_id text CHECK (length(ultimo_request_id) <= 64),
            conta_id bigint,
            resolvido_em timestamptz
        )
    """)
    op.execute("CREATE INDEX erros_ultima_idx ON erros (ultima_em DESC)")
    op.execute("ALTER TABLE erros ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE erros FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY sistema ON erros FOR ALL USING (app_sistema()) WITH CHECK (app_sistema())")

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON erros TO {papel};
                GRANT USAGE, SELECT ON SEQUENCE erros_id_seq TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS erros CASCADE")
