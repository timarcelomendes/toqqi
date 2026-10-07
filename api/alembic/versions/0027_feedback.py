"""Feedback (docs/api-feedback.md): quem usa o Toqqi relata um erro, dá uma ideia, pede uma melhoria ou elogia, e a
equipe Toqqi (superadmins) responde em Plataforma › Feedback.

- `feedbacks`: um por relato, de um usuário da conta (`usuario_id`; nulo quando ele sai da conta em Equipe), com o tipo,
  a situação, o impacto (só erro), a autorização de usar o elogio como depoimento (só elogio), o contexto da tela (página,
  título, navegador, tamanho da tela, versão do site e o diagnóstico dos últimos erros, só com "Enviar detalhes
  técnicos"), a nota interna da equipe e as marcas de leitura de cada lado (`ultima_do_usuario_em` ×
  `visto_pela_equipe_em`; `ultima_da_equipe_em` × `visto_pelo_usuario_em`).
- `feedback_mensagens`: a conversa, a primeira é o próprio relato. Autor `usuario` (o usuário da conta) ou `equipe`
  (nome de quem respondeu guardado no momento: o superadmin é usuário de outra conta). Uma mudança de situação pela equipe
  entra como mensagem com `situacao` (com ou sem texto).
- `feedback_imagens`: até 3 por mensagem, PNG ou JPG de até 1 MB, privadas (só quem enviou e a equipe; nunca por URL
  pública).
- `emails_enviados.tipo` aceita `feedback` (a resposta da equipe que chega à pessoa).

RLS por conta, como as outras tabelas; a Plataforma lê e responde em modo sistema. As três saem em cascata com a conta.
As chaves estrangeiras entre elas levam a conta junto (id, conta_id), e a do usuário segue o padrão (ON DELETE SET NULL
só da coluna).

Revision ID: 0027_feedback
Revises: 0026_formularios_v2
"""
import os
import re

from alembic import op

revision = "0027_feedback"
down_revision = "0026_formularios_v2"
branch_labels = None
depends_on = None

TIPOS = ("erro", "sugestao", "melhoria", "elogio")
SITUACOES = ("recebido", "em_analise", "planejado", "concluido", "encerrado")
IMPACTOS = ("bloqueia", "atrapalha", "detalhe")
TABELAS = ("feedbacks", "feedback_mensagens", "feedback_imagens")
# tipos do registro de e-mails enviados até a 0026 (0022 juntou `retorno`); esta junta `feedback` (resposta da equipe)
EMAILS = ("convite", "lembrete", "agradecimento", "teste", "confirmacao", "senha", "boas_vindas", "alerta_risco",
          "resumo_semanal", "pico", "indicacao", "aviso", "cobranca", "retorno")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _lista(valores: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE feedbacks (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas ON DELETE CASCADE,
            usuario_id bigint,
            tipo text NOT NULL CHECK (tipo IN ({_lista(TIPOS)})),
            situacao text NOT NULL DEFAULT 'recebido' CHECK (situacao IN ({_lista(SITUACOES)})),
            impacto text CHECK (impacto IN ({_lista(IMPACTOS)})),
            autoriza_depoimento boolean NOT NULL DEFAULT false,
            pagina text CHECK (length(pagina) <= 200),
            pagina_titulo text CHECK (length(pagina_titulo) <= 120),
            navegador text CHECK (length(navegador) <= 400),
            tela text CHECK (length(tela) <= 20),
            versao_site text CHECK (length(versao_site) <= 40),
            diagnostico jsonb CHECK (jsonb_typeof(diagnostico) = 'object'),
            nota_interna text NOT NULL DEFAULT '' CHECK (length(nota_interna) <= 5000),
            criado_em timestamptz NOT NULL DEFAULT now(),
            atualizado_em timestamptz NOT NULL DEFAULT now(),
            ultima_do_usuario_em timestamptz NOT NULL DEFAULT now(),
            ultima_da_equipe_em timestamptz,
            visto_pelo_usuario_em timestamptz,
            visto_pela_equipe_em timestamptz,
            UNIQUE (id, conta_id),
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id),
            CHECK (impacto IS NULL OR tipo = 'erro'),
            CHECK (NOT autoriza_depoimento OR tipo = 'elogio')
        )
    """)
    op.execute("CREATE INDEX feedbacks_usuario_idx ON feedbacks (conta_id, usuario_id, atualizado_em DESC)")
    op.execute("CREATE INDEX feedbacks_atualizado_idx ON feedbacks (atualizado_em DESC)")
    op.execute(f"""
        CREATE TABLE feedback_mensagens (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas ON DELETE CASCADE,
            feedback_id bigint NOT NULL,
            autor text NOT NULL CHECK (autor IN ('usuario','equipe')),
            usuario_id bigint,
            autor_nome text CHECK (length(autor_nome) <= 120),
            texto text NOT NULL DEFAULT '' CHECK (length(texto) <= 5000),
            situacao text CHECK (situacao IN ({_lista(SITUACOES)})),
            criado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (id, conta_id),
            FOREIGN KEY (feedback_id, conta_id) REFERENCES feedbacks(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id),
            CHECK (situacao IS NULL OR autor = 'equipe')
        )
    """)
    op.execute("CREATE INDEX feedback_mensagens_idx ON feedback_mensagens (feedback_id, id)")
    op.execute("""
        CREATE TABLE feedback_imagens (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas ON DELETE CASCADE,
            feedback_id bigint NOT NULL,
            mensagem_id bigint NOT NULL,
            tipo text NOT NULL CHECK (tipo IN ('image/png','image/jpeg')),
            dados bytea NOT NULL,
            tamanho integer NOT NULL CHECK (tamanho BETWEEN 1 AND 1048576),
            largura integer CHECK (largura > 0),
            altura integer CHECK (altura > 0),
            nome text CHECK (length(nome) <= 120),
            criada_em timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (feedback_id, conta_id) REFERENCES feedbacks(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (mensagem_id, conta_id) REFERENCES feedback_mensagens(id, conta_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX feedback_imagens_idx ON feedback_imagens (feedback_id, mensagem_id, id)")

    papel = _papel_app()
    for tabela in TABELAS:
        op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY isolamento_conta ON {tabela}
                USING (conta_id = app_conta() OR app_sistema())
                WITH CHECK (conta_id = app_conta() OR app_sistema())
        """)
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON {tabela} TO {papel};
                    GRANT USAGE, SELECT ON SEQUENCE {tabela}_id_seq TO {papel};
                ELSE
                    RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
                END IF;
            END $$
        """)
    op.execute("ALTER TABLE emails_enviados DROP CONSTRAINT emails_enviados_tipo_check")
    op.execute(f"ALTER TABLE emails_enviados ADD CONSTRAINT emails_enviados_tipo_check "
               f"CHECK (tipo IN ({_lista(EMAILS + ('feedback',))}))")


def downgrade() -> None:
    op.execute("DELETE FROM emails_enviados WHERE tipo = 'feedback'")
    op.execute("ALTER TABLE emails_enviados DROP CONSTRAINT emails_enviados_tipo_check")
    op.execute(f"ALTER TABLE emails_enviados ADD CONSTRAINT emails_enviados_tipo_check CHECK (tipo IN ({_lista(EMAILS)}))")
    for tabela in reversed(TABELAS):
        op.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")
