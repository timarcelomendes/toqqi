"""Retirar o aceite dos Termos de uso e da Política de privacidade (LGPD).

`aceites_termos` ganha `revogado_em`, `revogado_ip` e `revogado_agente` (até 400 caracteres). O UNIQUE
`(usuario_id, versao)` vira um índice único parcial `WHERE revogado_em IS NULL`: aceitar de novo depois de retirar cria
uma linha nova, e o histórico (aceite antigo + data da retirada) fica inteiro, como prova.

O downgrade volta o UNIQUE: antes, apaga as linhas revogadas que repetem `(usuario_id, versao)` (fica a linha em vigor
ou, sem ela, a mais recente).

Revision ID: 0011_revogacao_aceite
Revises: 0010_aceites
Create Date: 2026-10-02
"""
from alembic import op

revision = "0011_revogacao_aceite"
down_revision = "0010_aceites"
branch_labels = None
depends_on = None

AGENTE_MAX = 400
UNICO_ANTIGO = "aceites_termos_usuario_id_versao_key"
INDICE_VIGENTE = "aceites_termos_vigente_uq"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE aceites_termos
            ADD COLUMN revogado_em timestamptz,
            ADD COLUMN revogado_ip text,
            ADD COLUMN revogado_agente text CHECK (length(revogado_agente) <= {AGENTE_MAX})
    """)
    op.execute(f"ALTER TABLE aceites_termos DROP CONSTRAINT {UNICO_ANTIGO}")
    # também atende a busca da maior versão em vigor do usuário
    op.execute(f"CREATE UNIQUE INDEX {INDICE_VIGENTE} ON aceites_termos (usuario_id, versao) "
               "WHERE revogado_em IS NULL")


def downgrade() -> None:
    # a tabela tem RLS forçado: o dono da migração só enxerga as linhas em modo sistema
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute("""
        DELETE FROM aceites_termos a
         USING (SELECT id, row_number() OVER (PARTITION BY usuario_id, versao
                                              ORDER BY (revogado_em IS NULL) DESC, id DESC) AS n
                  FROM aceites_termos
                 WHERE usuario_id IS NOT NULL) d
         WHERE a.id = d.id AND d.n > 1 AND a.revogado_em IS NOT NULL
    """)
    # Sem as colunas, um aceite retirado voltaria a valer: não desce enquanto houver retiradas sem um aceite novo.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM aceites_termos a
                        WHERE a.revogado_em IS NOT NULL
                          AND NOT EXISTS (SELECT 1 FROM aceites_termos b
                                           WHERE b.usuario_id = a.usuario_id AND b.versao = a.versao
                                             AND b.revogado_em IS NULL)) THEN
                RAISE EXCEPTION 'Há aceites retirados sem um aceite novo; o downgrade da 0011 os faria voltar a valer.';
            END IF;
        END $$
    """)
    op.execute(f"DROP INDEX IF EXISTS {INDICE_VIGENTE}")
    op.execute(f"ALTER TABLE aceites_termos ADD CONSTRAINT {UNICO_ANTIGO} UNIQUE (usuario_id, versao)")
    op.execute("""
        ALTER TABLE aceites_termos
            DROP COLUMN revogado_em,
            DROP COLUMN revogado_ip,
            DROP COLUMN revogado_agente
    """)
