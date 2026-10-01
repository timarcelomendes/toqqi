"""Dados da empresa e imagens (logo): identificação, contato e endereço da conta; tabela `imagens` com o logo da
conta e os logos de formulário, servidos por uma URL pública com chave aleatória.

Os bytes da imagem ficam em `imagens`, não em `contas` (lida a cada requisição autenticada). Mesmo padrão das
etapas anteriores: conta_id DEFAULT app_conta(), RLS com FORCE, chave composta (formulario_id, conta_id) e
permissões do papel da aplicação só se ele existir. A busca pela chave (página pública da imagem) roda em modo
sistema.

Revision ID: 0006_dados_empresa
Revises: 0005_respostas_acoes
Create Date: 2026-10-01
"""
import os
import re

from alembic import op

revision = "0006_dados_empresa"
down_revision = "0005_respostas_acoes"
branch_labels = None
depends_on = None

UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO")
LIMITE_IMAGEM = 300 * 1024  # 307200 bytes
COLUNAS_CONTA = ("razao_social", "documento", "telefone", "email_contato", "site", "cep", "logradouro", "numero",
                 "complemento", "bairro", "cidade", "uf", "dados_atualizados_em")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    ufs = ",".join(f"'{u}'" for u in UFS)
    op.execute(f"""
        ALTER TABLE contas
            ADD COLUMN razao_social text CHECK (length(razao_social) BETWEEN 1 AND 200),
            ADD COLUMN documento text CHECK (documento ~ '^([0-9]{{11}}|[0-9]{{14}})$'),
            ADD COLUMN telefone text CHECK (telefone ~ '^[0-9]{{10,13}}$'),
            ADD COLUMN email_contato citext CHECK (length(email_contato) BETWEEN 3 AND 254),
            ADD COLUMN site text CHECK (length(site) <= 200 AND site ~* '^https?://'),
            ADD COLUMN cep text CHECK (cep ~ '^[0-9]{{8}}$'),
            ADD COLUMN logradouro text CHECK (length(logradouro) BETWEEN 1 AND 150),
            ADD COLUMN numero text CHECK (length(numero) BETWEEN 1 AND 20),
            ADD COLUMN complemento text CHECK (length(complemento) BETWEEN 1 AND 80),
            ADD COLUMN bairro text CHECK (length(bairro) BETWEEN 1 AND 80),
            ADD COLUMN cidade text CHECK (length(cidade) BETWEEN 1 AND 80),
            ADD COLUMN uf text CHECK (uf IN ({ufs})),
            ADD COLUMN dados_atualizados_em timestamptz
    """)

    op.execute(f"""
        CREATE TABLE imagens (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            uso text NOT NULL CHECK (uso IN ('logo_conta','logo_formulario')),
            formulario_id bigint,
            chave text NOT NULL UNIQUE CHECK (chave ~ '^[A-Za-z0-9_-]{{32,128}}$'),
            tipo text NOT NULL CHECK (tipo IN ('image/png','image/jpeg')),
            dados bytea NOT NULL,
            tamanho integer NOT NULL CHECK (tamanho BETWEEN 1 AND {LIMITE_IMAGEM}),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{{64}}$'),
            criada_em timestamptz NOT NULL DEFAULT now(),
            CHECK (octet_length(dados) = tamanho),
            -- logo de formulário sempre aponta para o formulário; logo da conta, nunca
            CHECK ((uso = 'logo_formulario') = (formulario_id IS NOT NULL)),
            FOREIGN KEY (formulario_id, conta_id) REFERENCES formularios(id, conta_id) ON DELETE CASCADE
        )
    """)
    # uma imagem por uso: trocar = apagar a anterior e gravar outra (com chave nova)
    op.execute("CREATE UNIQUE INDEX imagens_logo_conta_key ON imagens (conta_id) WHERE uso = 'logo_conta'")
    op.execute("CREATE UNIQUE INDEX imagens_logo_formulario_key ON imagens (formulario_id) "
               "WHERE uso = 'logo_formulario'")

    op.execute("ALTER TABLE imagens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE imagens FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY isolamento_conta ON imagens
            USING (conta_id = app_conta() OR app_sistema())
            WITH CHECK (conta_id = app_conta() OR app_sistema())
    """)

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON imagens TO {papel};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS imagens CASCADE")
    op.execute("ALTER TABLE contas " + ", ".join(f"DROP COLUMN IF EXISTS {c}" for c in COLUNAS_CONTA))
