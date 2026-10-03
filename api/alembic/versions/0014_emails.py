"""Etapa 5e: e-mails (visual guiado dos e-mails de pesquisa, banco de imagens da conta e registro de e-mails enviados).

- `config_envios`: o visual dos e-mails de pesquisa — cor de destaque (`email_cor`, `#RRGGBB` em maiúsculas; nula = a cor
  do formulário do envio), mostrar o logo (ligado), imagem de topo (`email_imagem_topo_id`, chave composta com
  `imagens` e SET NULL quando a imagem some), assinatura (até 300) e rodapé (até 500). DEFAULT constante: não
  reescreve a tabela.
- `imagens`: `uso` passa a aceitar 'banco' (o banco de imagens da conta); o tamanho vai até 1 MB no banco e continua
  até 300 KB nos logos; ganha `nome` (nome do arquivo enviado, limpo, até 120), `largura` e `altura` (lidas do
  cabeçalho PNG/JPEG; nulas se não deu para ler) e o único `(id, conta_id)` da chave composta acima. Índice parcial das
  imagens do banco por conta (a lista, das mais novas para as mais antigas).
- `emails_enviados`: uma linha por e-mail que saiu (ou tentou sair) em nome de uma conta — tipo, destinatário, assunto
  (até 300), situação ('enviado' | 'falhou') e o texto simples do erro (só com 'falhou'). Guardado por 90 dias (a
  tarefa `limpeza` apaga o resto). Padrão das etapas anteriores: conta_id DEFAULT app_conta() com CASCADE na conta, RLS
  com FORCE e a política de sempre, permissões do papel da aplicação só se ele existir.

O downgrade apaga a tabela nova, as colunas novas e as imagens do banco (antes de voltar o CHECK de `uso`).

Revision ID: 0014_emails
Revises: 0013_ia_sob_demanda
Create Date: 2026-10-02
"""
import os
import re

from alembic import op

revision = "0014_emails"
down_revision = "0013_ia_sob_demanda"
branch_labels = None
depends_on = None

NOVAS = ["emails_enviados"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
LIMITE_LOGO = 300 * 1024  # 307200 bytes (como na 0006)
LIMITE_BANCO = 1024 * 1024  # 1048576 bytes
TIPOS = ("convite", "lembrete", "agradecimento", "teste", "confirmacao", "senha", "boas_vindas", "alerta_risco",
         "resumo_semanal", "pico", "indicacao", "aviso", "cobranca")
COLUNAS_CONFIG = ("email_cor", "email_mostrar_logo", "email_imagem_topo_id", "email_assinatura", "email_rodape")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _lista(valores) -> str:
    return ",".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE imagens
            DROP CONSTRAINT imagens_uso_check,
            ADD CONSTRAINT imagens_uso_check CHECK (uso IN ('logo_conta','logo_formulario','banco')),
            DROP CONSTRAINT imagens_tamanho_check,
            ADD CONSTRAINT imagens_tamanho_check
                CHECK (tamanho >= 1 AND tamanho <= CASE WHEN uso = 'banco' THEN {LIMITE_BANCO} ELSE {LIMITE_LOGO} END),
            ADD COLUMN nome text CHECK (length(nome) BETWEEN 1 AND 120),
            ADD COLUMN largura integer CHECK (largura > 0),
            ADD COLUMN altura integer CHECK (altura > 0),
            ADD CONSTRAINT imagens_id_conta_key UNIQUE (id, conta_id)
    """)
    op.execute("CREATE INDEX imagens_banco_idx ON imagens (conta_id, criada_em DESC) WHERE uso = 'banco'")

    op.execute("""
        ALTER TABLE config_envios
            ADD COLUMN email_cor text CHECK (email_cor ~ '^#[0-9A-F]{6}$'),
            ADD COLUMN email_mostrar_logo boolean NOT NULL DEFAULT true,
            ADD COLUMN email_imagem_topo_id bigint,
            ADD COLUMN email_assinatura text CHECK (length(email_assinatura) BETWEEN 1 AND 300),
            ADD COLUMN email_rodape text CHECK (length(email_rodape) BETWEEN 1 AND 500),
            ADD CONSTRAINT config_envios_imagem_topo_fkey FOREIGN KEY (email_imagem_topo_id, conta_id)
                REFERENCES imagens(id, conta_id) ON DELETE SET NULL (email_imagem_topo_id)
    """)
    # o SET NULL quando a imagem é apagada (e a conferência "em uso" do banco de imagens)
    op.execute("CREATE INDEX config_envios_imagem_topo_idx ON config_envios (email_imagem_topo_id) "
               "WHERE email_imagem_topo_id IS NOT NULL")

    op.execute(f"""
        CREATE TABLE emails_enviados (
            id bigserial PRIMARY KEY,
            {CONTA},
            tipo text NOT NULL CHECK (tipo IN ({_lista(TIPOS)})),
            destinatario citext NOT NULL CHECK (length(destinatario) >= 1),
            assunto text NOT NULL CHECK (length(assunto) <= 300),
            situacao text NOT NULL CHECK (situacao IN ('enviado','falhou')),
            erro text CHECK (length(erro) BETWEEN 1 AND 500),
            criado_em timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT emails_enviados_erro_so_falhou CHECK ((situacao = 'falhou') = (erro IS NOT NULL))
        )
    """)
    op.execute("CREATE INDEX emails_enviados_recentes_idx ON emails_enviados (conta_id, criado_em DESC)")
    op.execute("CREATE INDEX emails_enviados_situacao_idx ON emails_enviados (conta_id, situacao, criado_em DESC)")
    # a limpeza (linhas com mais de 90 dias, de todas as contas) não percorre a tabela inteira a cada rodada
    op.execute("CREATE INDEX emails_enviados_criado_idx ON emails_enviados (criado_em)")

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
    op.execute("SELECT set_config('app.sistema', 'on', true)")  # RLS forçado: o DELETE das imagens precisa dele
    for t in reversed(NOVAS):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("DROP INDEX IF EXISTS config_envios_imagem_topo_idx")
    op.execute("ALTER TABLE config_envios DROP CONSTRAINT IF EXISTS config_envios_imagem_topo_fkey, "
               + ", ".join(f"DROP COLUMN IF EXISTS {c}" for c in COLUNAS_CONFIG))
    op.execute("DELETE FROM imagens WHERE uso = 'banco'")
    op.execute("DROP INDEX IF EXISTS imagens_banco_idx")
    op.execute(f"""
        ALTER TABLE imagens
            DROP CONSTRAINT IF EXISTS imagens_id_conta_key,
            DROP COLUMN IF EXISTS nome,
            DROP COLUMN IF EXISTS largura,
            DROP COLUMN IF EXISTS altura,
            DROP CONSTRAINT imagens_uso_check,
            ADD CONSTRAINT imagens_uso_check CHECK (uso IN ('logo_conta','logo_formulario')),
            DROP CONSTRAINT imagens_tamanho_check,
            ADD CONSTRAINT imagens_tamanho_check CHECK (tamanho >= 1 AND tamanho <= {LIMITE_LOGO})
    """)
