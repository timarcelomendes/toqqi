"""Etapa 5f: dados da conta (registros de acesso, aviso da exclusão automática e índices da zona de risco).

- `registros_acesso` (Marco Civil da Internet, art. 15: data, hora e IP de cada acesso, guardados por 6 meses, em
  sigilo): entradas e tentativas, cadastro, pedido de acesso, senha trocada pelo link e envios públicos de resposta e
  indicação. **Sem FK**: a linha sobrevive à exclusão do usuário e da conta. RLS forçado **sem** a política de sempre:
  a aplicação grava na transação do evento (em conta, só com a própria conta; em modo sistema, qualquer uma), mas só o
  modo sistema lê e apaga (a limpeza de 6 meses e a equipe técnica, por SQL, para ordem judicial); nenhuma política de
  UPDATE e `REVOKE UPDATE` do papel da aplicação (os privilégios padrão da 0001 dariam UPDATE). Índice `(criado_em)`
  para a limpeza.
- `contas`: `exclusao_avisada_para` (o dia da exclusão automática avisado aos administradores) e `exclusao_avisada_em`
  (quando o aviso saiu, pelo relógio do banco); os dois nulos ou os dois preenchidos.
- Índices parciais `WHERE <coluna> IS NOT NULL` nas colunas que apontam para respostas, contatos e empresas sem índice
  próprio, para os SET NULL/CASCADE da zona de risco e da exclusão da conta não varrerem a tabela a cada linha apagada:
  `envios (resposta_id)`, `indicacoes (resposta_id)`, `indicacoes (indicador_contato_id)`,
  `indicacoes (indicador_empresa_id)`, `ofertas (contato_id)` e `convites (empresa_id)`.

O downgrade desfaz tudo (a tabela, as colunas e os índices).

Revision ID: 0015_dados_conta
Revises: 0014_emails
Create Date: 2026-10-03
"""
import os
import re

from alembic import op

revision = "0015_dados_conta"
down_revision = "0014_emails"
branch_labels = None
depends_on = None

EVENTOS = ("login", "login_falhou", "cadastro", "pedido_acesso", "senha_redefinida", "resposta", "indicacao")
INDICES = (
    ("envios_resposta_idx", "envios", "resposta_id"),
    ("indicacoes_resposta_idx", "indicacoes", "resposta_id"),
    ("indicacoes_indicador_contato_idx", "indicacoes", "indicador_contato_id"),
    ("indicacoes_indicador_empresa_idx", "indicacoes", "indicador_empresa_id"),
    ("ofertas_contato_idx", "ofertas", "contato_id"),
    ("convites_empresa_idx", "convites", "empresa_id"),
)


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _lista(valores) -> str:
    return ",".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE registros_acesso (
            id bigserial PRIMARY KEY,
            criado_em timestamptz NOT NULL DEFAULT now(),
            evento text NOT NULL CHECK (evento IN ({_lista(EVENTOS)})),
            conta_id bigint,
            usuario_id bigint,
            item_id bigint,
            ip text CHECK (length(ip) <= 64)
        )
    """)
    op.execute("CREATE INDEX registros_acesso_criado_idx ON registros_acesso (criado_em)")
    op.execute("ALTER TABLE registros_acesso ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE registros_acesso FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY gravar ON registros_acesso FOR INSERT
            WITH CHECK (app_sistema() OR conta_id = app_conta())
    """)
    op.execute("CREATE POLICY ler ON registros_acesso FOR SELECT USING (app_sistema())")
    op.execute("CREATE POLICY apagar ON registros_acesso FOR DELETE USING (app_sistema())")

    op.execute("""
        ALTER TABLE contas
            ADD COLUMN exclusao_avisada_para date,
            ADD COLUMN exclusao_avisada_em timestamptz,
            ADD CONSTRAINT contas_exclusao_avisada_check
                CHECK ((exclusao_avisada_para IS NULL) = (exclusao_avisada_em IS NULL))
    """)

    for nome, tabela, coluna in INDICES:
        op.execute(f"CREATE INDEX {nome} ON {tabela} ({coluna}) WHERE {coluna} IS NOT NULL")

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, DELETE ON registros_acesso TO {papel};
                REVOKE UPDATE, TRUNCATE ON registros_acesso FROM {papel};
                GRANT USAGE, SELECT ON SEQUENCE registros_acesso_id_seq TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    for nome, _, _ in reversed(INDICES):
        op.execute(f"DROP INDEX IF EXISTS {nome}")
    op.execute("""
        ALTER TABLE contas
            DROP CONSTRAINT IF EXISTS contas_exclusao_avisada_check,
            DROP COLUMN IF EXISTS exclusao_avisada_para,
            DROP COLUMN IF EXISTS exclusao_avisada_em
    """)
    op.execute("DROP TABLE IF EXISTS registros_acesso CASCADE")
