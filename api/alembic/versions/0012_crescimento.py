"""Etapa 5c: Crescimento (indicações de promotores e oportunidades de oferta).

Tabelas novas, no padrão das etapas anteriores (conta_id DEFAULT app_conta(), RLS com FORCE e a política de sempre,
chaves compostas (id, conta_id) nas referências entre tabelas da conta, permissões do papel da aplicação só se ele
existir):
- `config_crescimento`: uma linha por conta (como `config_acoes`); sem linha valem os padrões (os mesmos DEFAULTs);
- `indicacoes`: pessoas indicadas por um promotor (pela pesquisa) ou registradas à mão. Apagar o contato, a empresa, a
  resposta ou o convite de quem indicou não apaga a indicação (SET NULL); telefone (só dígitos, com 55) ou e-mail
  presente; `valor_mensal` só com a situação 'cliente'; `motivo` só com 'nao_avancou';
- `ofertas`: oferta feita a um cliente feliz (link do WhatsApp com o texto pronto ou e-mail), com o resultado; some
  junto com a empresa (CASCADE);
- `convites.indicacoes_feitas`: tentativas de indicação aceitas pela página pública daquele convite, contadas sob o
  FOR UPDATE do convite; a repetida (mesmo telefone ou e-mail de uma indicação aberta) também conta, para o limite de 3
  não revelar se um número já está no funil.

Também aqui: os eventos `indicacao.criada` e `indicacao.atualizada` entram no CHECK de `webhooks.eventos`, e as
permissões novas (`crescimento.ver` para gestor e consulta, `crescimento.tratar` para gestor) são semeadas em
`perfil_permissoes` nas contas que já existem (modo sistema: o RLS é forçado).

O downgrade apaga as tabelas e a coluna nova dos convites, tira os eventos novos dos webhooks (os que só tinham eles
somem, com as entregas desses eventos) e as linhas das permissões novas.

Revision ID: 0012_crescimento
Revises: 0011_revogacao_aceite
Create Date: 2026-10-02
"""
import os
import re

from alembic import op

revision = "0012_crescimento"
down_revision = "0011_revogacao_aceite"
branch_labels = None
depends_on = None

NOVAS = ["config_crescimento", "indicacoes", "ofertas"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
EVENTOS_ANTES = "'resposta.criada','contato.descadastrado'"
EVENTOS_NOVOS = "'indicacao.criada','indicacao.atualizada'"
# (perfil, permissão) semeados nas contas existentes; o mesmo que core.permissoes.PADRAO dá às contas novas
PERMISSOES = (("gestor", "crescimento.ver"), ("gestor", "crescimento.tratar"), ("consulta", "crescimento.ver"))

TITULO_PADRAO = "Que bom que você gostou!"
CONVITE_PADRAO = "Conhece outra empresa que ganharia com a {empresa}? Indique e a gente entra em contato com cuidado."
OFERTA_PADRAO = ("Olá, {nome}! Aqui é {representante}, da {empresa}. Obrigado pela ótima avaliação! Preparei uma "
                 "condição especial para a {empresa_cliente}. Posso te contar?")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _texto_sql(t: str) -> str:
    return "'" + t.replace("'", "''") + "'"


def _check_eventos(eventos: str) -> None:
    op.execute(f"""
        ALTER TABLE webhooks DROP CONSTRAINT IF EXISTS webhooks_eventos_check,
            ADD CONSTRAINT webhooks_eventos_check CHECK (cardinality(eventos) >= 1 AND eventos <@ ARRAY[{eventos}])
    """)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE config_crescimento (
            conta_id bigint PRIMARY KEY DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            indicacoes_ativas boolean NOT NULL DEFAULT false,
            titulo_convite text NOT NULL DEFAULT {_texto_sql(TITULO_PADRAO)}
                CHECK (length(titulo_convite) BETWEEN 1 AND 120),
            texto_convite text NOT NULL DEFAULT {_texto_sql(CONVITE_PADRAO)}
                CHECK (length(texto_convite) BETWEEN 1 AND 500),
            recompensa text CHECK (length(recompensa) BETWEEN 1 AND 300),
            texto_oferta text NOT NULL DEFAULT {_texto_sql(OFERTA_PADRAO)}
                CHECK (length(texto_oferta) BETWEEN 1 AND 1000),
            atualizado_em timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute(f"""
        CREATE TABLE indicacoes (
            id bigserial PRIMARY KEY,
            {CONTA},
            origem text NOT NULL CHECK (origem IN ('pesquisa','manual')),
            convite_id bigint,
            resposta_id bigint,
            indicador_contato_id bigint,
            indicador_empresa_id bigint,
            pode_identificar boolean NOT NULL DEFAULT true,
            nome text NOT NULL CHECK (length(nome) BETWEEN 2 AND 120),
            empresa text CHECK (length(empresa) BETWEEN 1 AND 120),
            telefone text CHECK (telefone ~ '^[0-9]{{12,13}}$'),
            email citext CHECK (length(email) BETWEEN 3 AND 254),
            observacao text CHECK (length(observacao) BETWEEN 1 AND 500),
            situacao text NOT NULL DEFAULT 'nova' CHECK (situacao IN ('nova','em_contato','cliente','nao_avancou')),
            responsavel_id bigint,
            valor_mensal numeric(12,2),
            motivo text CHECK (length(motivo) BETWEEN 1 AND 300),
            criada_em timestamptz NOT NULL DEFAULT now(),
            atualizada_em timestamptz NOT NULL DEFAULT now(),
            criada_por bigint,
            atualizada_por bigint,
            UNIQUE (id, conta_id),
            CONSTRAINT indicacoes_telefone_ou_email CHECK (telefone IS NOT NULL OR email IS NOT NULL),
            CONSTRAINT indicacoes_valor_so_cliente
                CHECK (valor_mensal IS NULL OR (situacao = 'cliente' AND valor_mensal >= 0)),
            CONSTRAINT indicacoes_motivo_so_nao_avancou CHECK (motivo IS NULL OR situacao = 'nao_avancou'),
            FOREIGN KEY (convite_id, conta_id) REFERENCES convites(id, conta_id) ON DELETE SET NULL (convite_id),
            FOREIGN KEY (resposta_id, conta_id) REFERENCES respostas(id, conta_id) ON DELETE SET NULL (resposta_id),
            FOREIGN KEY (indicador_contato_id, conta_id) REFERENCES contatos(id, conta_id)
                ON DELETE SET NULL (indicador_contato_id),
            FOREIGN KEY (indicador_empresa_id, conta_id) REFERENCES empresas(id, conta_id)
                ON DELETE SET NULL (indicador_empresa_id),
            FOREIGN KEY (responsavel_id, conta_id) REFERENCES responsaveis(id, conta_id)
                ON DELETE SET NULL (responsavel_id),
            FOREIGN KEY (criada_por, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (criada_por),
            FOREIGN KEY (atualizada_por, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (atualizada_por)
        )
    """)
    op.execute("CREATE INDEX indicacoes_situacao_idx ON indicacoes (conta_id, situacao, criada_em)")
    op.execute("CREATE INDEX indicacoes_data_idx ON indicacoes (conta_id, criada_em)")
    # o SET NULL quando o convite some (o limite de 3 por convite conta em `convites.indicacoes_feitas`)
    op.execute("CREATE INDEX indicacoes_convite_idx ON indicacoes (convite_id) WHERE convite_id IS NOT NULL")

    op.execute(f"""
        CREATE TABLE ofertas (
            id bigserial PRIMARY KEY,
            {CONTA},
            empresa_id bigint NOT NULL,
            contato_id bigint,
            lista text NOT NULL CHECK (lista IN ('pode_crescer','promotores')),
            canal text NOT NULL DEFAULT 'whatsapp' CHECK (canal IN ('whatsapp','email')),
            texto text NOT NULL CHECK (length(texto) BETWEEN 1 AND 2000),
            usuario_id bigint,
            criada_em timestamptz NOT NULL DEFAULT now(),
            resultado text CHECK (resultado IN ('aceitou','recusou','sem_resposta')),
            valor numeric(12,2),
            resultado_em timestamptz,
            UNIQUE (id, conta_id),
            CONSTRAINT ofertas_valor_so_aceitou CHECK (valor IS NULL OR (resultado = 'aceitou' AND valor >= 0)),
            CONSTRAINT ofertas_resultado_em CHECK ((resultado IS NULL) = (resultado_em IS NULL)),
            FOREIGN KEY (empresa_id, conta_id) REFERENCES empresas(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (contato_id, conta_id) REFERENCES contatos(id, conta_id) ON DELETE SET NULL (contato_id),
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id)
        )
    """)
    op.execute("CREATE INDEX ofertas_empresa_idx ON ofertas (conta_id, empresa_id, criada_em)")

    # limite de 3 tentativas por convite (inclusive as repetidas); default constante: não reescreve a tabela
    op.execute("ALTER TABLE convites ADD COLUMN indicacoes_feitas integer NOT NULL DEFAULT 0 "
               "CHECK (indicacoes_feitas >= 0)")

    for t in NOVAS:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY isolamento_conta ON {t}
                USING (conta_id = app_conta() OR app_sistema())
                WITH CHECK (conta_id = app_conta() OR app_sistema())
        """)

    _check_eventos(f"{EVENTOS_ANTES},{EVENTOS_NOVOS}")

    # permissões novas nas contas que já existem (RLS forçado em perfil_permissoes: modo sistema)
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    valores = ", ".join(f"('{perfil}', '{permissao}')" for perfil, permissao in PERMISSOES)
    op.execute(f"""
        INSERT INTO perfil_permissoes (conta_id, perfil, permissao)
        SELECT c.id, p.perfil, p.permissao FROM contas c CROSS JOIN (VALUES {valores}) AS p(perfil, permissao)
        ON CONFLICT DO NOTHING
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
    op.execute("ALTER TABLE convites DROP COLUMN IF EXISTS indicacoes_feitas")
    op.execute(f"DELETE FROM webhook_entregas WHERE evento IN ({EVENTOS_NOVOS})")
    op.execute(f"DELETE FROM webhooks WHERE eventos <@ ARRAY[{EVENTOS_NOVOS}]")  # só tinham os eventos novos
    op.execute("UPDATE webhooks SET eventos = array_remove(array_remove(eventos, 'indicacao.criada'), "
               f"'indicacao.atualizada') WHERE eventos && ARRAY[{EVENTOS_NOVOS}]")
    _check_eventos(EVENTOS_ANTES)
    permissoes = ", ".join(f"'{p}'" for p in sorted({p for _, p in PERMISSOES}))
    op.execute(f"DELETE FROM perfil_permissoes WHERE permissao IN ({permissoes})")
