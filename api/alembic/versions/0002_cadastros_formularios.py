"""Etapa 2: cadastros auxiliares, responsáveis, empresas, contatos, formulários, convites, respostas e importações.

Todas as tabelas novas têm conta_id DEFAULT app_conta(), RLS com FORCE e a mesma política da etapa 1.
Referências entre tabelas da conta usam chave composta (id, conta_id): nem a checagem de FK
(que ignora o RLS) permite apontar para uma linha de outra conta.

Revision ID: 0002_cadastros_formularios
Revises: 0001_inicial
Create Date: 2026-09-30
"""
import json
import os
import re

from sqlalchemy import text

from alembic import op

revision = "0002_cadastros_formularios"
down_revision = "0001_inicial"
branch_labels = None
depends_on = None

AUXILIARES = ["grupos", "segmentos", "perfis_contato", "cargos"]
NOVAS = AUXILIARES + ["responsaveis", "empresas", "contatos", "formularios", "convites", "respostas", "importacoes"]


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"


def upgrade() -> None:
    for t in AUXILIARES:
        op.execute(f"""
            CREATE TABLE {t} (
                id bigserial PRIMARY KEY,
                {CONTA},
                nome citext NOT NULL CHECK (length(nome) BETWEEN 1 AND 80),
                criado_em timestamptz NOT NULL DEFAULT now(),
                UNIQUE (conta_id, nome),
                UNIQUE (id, conta_id)
            )
        """)

    op.execute(f"""
        CREATE TABLE responsaveis (
            id bigserial PRIMARY KEY,
            {CONTA},
            nome text NOT NULL,
            funcao text,
            email citext,
            foto_url text,
            teams_webhook text,
            criado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (id, conta_id)
        )
    """)
    op.execute("CREATE INDEX responsaveis_conta_idx ON responsaveis (conta_id)")

    op.execute(f"""
        CREATE TABLE empresas (
            id bigserial PRIMARY KEY,
            {CONTA},
            nome citext NOT NULL,
            documento text CHECK (documento ~ '^([0-9]{{11}}|[0-9]{{14}})$'),
            grupo_id bigint,
            segmento_id bigint,
            responsavel_id bigint,
            valor_mensal numeric(12,2),
            cliente_desde date,
            codigo_externo text,
            ativa boolean NOT NULL DEFAULT true,
            criada_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (conta_id, nome),
            UNIQUE (id, conta_id),
            FOREIGN KEY (grupo_id, conta_id) REFERENCES grupos(id, conta_id) ON DELETE SET NULL (grupo_id),
            FOREIGN KEY (segmento_id, conta_id) REFERENCES segmentos(id, conta_id) ON DELETE SET NULL (segmento_id),
            FOREIGN KEY (responsavel_id, conta_id) REFERENCES responsaveis(id, conta_id)
                ON DELETE SET NULL (responsavel_id)
        )
    """)
    op.execute("CREATE INDEX empresas_codigo_externo_idx ON empresas (conta_id, codigo_externo)")

    op.execute(f"""
        CREATE TABLE contatos (
            id bigserial PRIMARY KEY,
            {CONTA},
            codigo char(9) NOT NULL CHECK (codigo ~ '^[0-9]{{9}}$'),
            nome text NOT NULL,
            email citext,
            telefone text CHECK (telefone ~ '^[0-9]{{10,13}}$'),
            empresa_id bigint,
            cargo_id bigint,
            perfil_id bigint,
            codigo_externo text,
            recebe_pesquisas boolean NOT NULL DEFAULT true,
            ativo boolean NOT NULL DEFAULT true,
            ultima_nota smallint,
            criado_em timestamptz NOT NULL DEFAULT now(),
            CHECK (email IS NOT NULL OR telefone IS NOT NULL),
            UNIQUE (conta_id, codigo),
            UNIQUE (conta_id, email),
            UNIQUE (id, conta_id),
            FOREIGN KEY (empresa_id, conta_id) REFERENCES empresas(id, conta_id) ON DELETE SET NULL (empresa_id),
            FOREIGN KEY (cargo_id, conta_id) REFERENCES cargos(id, conta_id) ON DELETE SET NULL (cargo_id),
            FOREIGN KEY (perfil_id, conta_id) REFERENCES perfis_contato(id, conta_id) ON DELETE SET NULL (perfil_id)
        )
    """)
    op.execute("CREATE INDEX contatos_empresa_idx ON contatos (conta_id, empresa_id)")
    op.execute("CREATE INDEX contatos_telefone_idx ON contatos (conta_id, telefone)")
    op.execute("CREATE INDEX contatos_codigo_externo_idx ON contatos (conta_id, codigo_externo)")
    op.execute("CREATE INDEX contatos_ativos_idx ON contatos (conta_id) WHERE ativo")

    # ---- limite de contatos ativos por plano (garantido no banco) ----------
    op.execute("""
        CREATE FUNCTION limite_contatos(p_plano text, p_situacao text) RETURNS integer
        LANGUAGE sql IMMUTABLE AS $$
            SELECT CASE
                WHEN p_situacao = 'cortesia' THEN NULL
                WHEN p_plano = 'essencial' THEN 300
                WHEN p_plano = 'profissional' THEN 1500
                ELSE NULL
            END
        $$
    """)
    op.execute("""
        CREATE FUNCTION contatos_checar_limite() RETURNS trigger LANGUAGE plpgsql AS $$
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
            SELECT limite_contatos(c.plano, c.situacao) INTO v_limite FROM contas c WHERE c.id = NEW.conta_id;
            IF v_limite IS NULL THEN
                RETURN NEW;
            END IF;
            -- Serializa inclusões da mesma conta para a contagem não correr.
            PERFORM pg_advisory_xact_lock(740221, NEW.conta_id::integer);
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
    """)
    op.execute("""
        CREATE TRIGGER contatos_limite_plano
            BEFORE INSERT OR UPDATE OF ativo ON contatos
            FOR EACH ROW EXECUTE FUNCTION contatos_checar_limite()
    """)

    op.execute(f"""
        CREATE TABLE formularios (
            id bigserial PRIMARY KEY,
            {CONTA},
            nome text NOT NULL,
            descricao text NOT NULL DEFAULT '',
            perguntas jsonb NOT NULL DEFAULT '[]'::jsonb,
            tema jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            ativo boolean NOT NULL DEFAULT true,
            publico boolean NOT NULL DEFAULT true,
            codigo_publico char(8) NOT NULL UNIQUE,
            padrao_nps boolean NOT NULL DEFAULT false,
            padrao_csat boolean NOT NULL DEFAULT false,
            arquivado boolean NOT NULL DEFAULT false,
            criado_em timestamptz NOT NULL DEFAULT now(),
            atualizado_em timestamptz NOT NULL DEFAULT now(),
            UNIQUE (id, conta_id)
        )
    """)
    op.execute("CREATE INDEX formularios_conta_idx ON formularios (conta_id)")
    op.execute("CREATE UNIQUE INDEX formularios_um_padrao_nps ON formularios (conta_id) WHERE padrao_nps")
    op.execute("CREATE UNIQUE INDEX formularios_um_padrao_csat ON formularios (conta_id) WHERE padrao_csat")

    op.execute(f"""
        CREATE TABLE convites (
            id bigserial PRIMARY KEY,
            {CONTA},
            token_hash text NOT NULL UNIQUE,
            formulario_id bigint NOT NULL,
            contato_id bigint,
            empresa_id bigint,
            canal text NOT NULL CHECK (canal IN ('email','whatsapp','link_manual')),
            assunto text,
            referencia text,
            contexto jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            criado_em timestamptz NOT NULL DEFAULT now(),
            respondido_em timestamptz,
            UNIQUE (id, conta_id),
            FOREIGN KEY (formulario_id, conta_id) REFERENCES formularios(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (contato_id, conta_id) REFERENCES contatos(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (empresa_id, conta_id) REFERENCES empresas(id, conta_id) ON DELETE SET NULL (empresa_id)
        )
    """)
    op.execute("CREATE INDEX convites_contato_idx ON convites (conta_id, contato_id)")

    op.execute(f"""
        CREATE TABLE respostas (
            id bigserial PRIMARY KEY,
            {CONTA},
            formulario_id bigint NOT NULL,
            convite_id bigint UNIQUE,
            contato_id bigint,
            empresa_id bigint,
            canal text NOT NULL
                CHECK (canal IN ('email','whatsapp','link','qr','widget','api','importacao','manual')),
            nota smallint,
            tipo_nota text CHECK (tipo_nota IN ('nps','csat')),
            grupo text CHECK (grupo IN ('detrator','neutro','promotor','insatisfeito','satisfeito')),
            comentario text NOT NULL DEFAULT '',
            respostas jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            contexto jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            referencia text,
            ip_hash text,
            arquivada boolean NOT NULL DEFAULT false,
            criada_em timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (formulario_id, conta_id) REFERENCES formularios(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (convite_id, conta_id) REFERENCES convites(id, conta_id) ON DELETE SET NULL (convite_id),
            FOREIGN KEY (contato_id, conta_id) REFERENCES contatos(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (empresa_id, conta_id) REFERENCES empresas(id, conta_id) ON DELETE SET NULL (empresa_id)
        )
    """)
    op.execute("CREATE INDEX respostas_conta_data_idx ON respostas (conta_id, criada_em DESC)")
    op.execute("CREATE INDEX respostas_formulario_idx ON respostas (conta_id, formulario_id, criada_em DESC)")
    op.execute("CREATE INDEX respostas_empresa_idx ON respostas (conta_id, empresa_id)")
    op.execute("CREATE INDEX respostas_contato_idx ON respostas (conta_id, contato_id)")

    op.execute(f"""
        CREATE TABLE importacoes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            {CONTA},
            usuario_id bigint NOT NULL,
            arquivo_nome text NOT NULL,
            dados jsonb NOT NULL,
            colunas jsonb NOT NULL,
            criada_em timestamptz NOT NULL DEFAULT now(),
            expira_em timestamptz NOT NULL DEFAULT now() + interval '1 hour',
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX importacoes_expira_idx ON importacoes (expira_em)")

    # ---- RLS ---------------------------------------------------------------
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
                GRANT EXECUTE ON FUNCTION limite_contatos(text, text) TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)

    _semear_contas_existentes()


def _semear_contas_existentes() -> None:
    """Contas criadas na etapa 1 recebem os perfis e os dois formulários padrão."""
    from toqqi.modulos.formularios.semear import dados_iniciais

    conn = op.get_bind()
    conn.execute(text("select set_config('app.sistema', 'on', true)"))
    for (conta_id,) in conn.execute(text("select id from contas order by id")).all():
        perfis, formularios = dados_iniciais()
        for nome in perfis:
            conn.execute(text("insert into perfis_contato (conta_id, nome) values (:c, :n) on conflict do nothing"),
                         {"c": conta_id, "n": nome})
        for f in formularios:
            conn.execute(text("""
                insert into formularios (conta_id, nome, descricao, perguntas, tema, codigo_publico,
                                         padrao_nps, padrao_csat)
                values (:c, :nome, :descricao, cast(:perguntas as jsonb), cast(:tema as jsonb), :codigo,
                        :padrao_nps, :padrao_csat)
            """), {"c": conta_id, "nome": f["nome"], "descricao": f["descricao"],
                   "perguntas": json.dumps(f["perguntas"]), "tema": json.dumps(f["tema"]),
                   "codigo": f["codigo_publico"], "padrao_nps": f["padrao_nps"], "padrao_csat": f["padrao_csat"]})


def downgrade() -> None:
    for t in reversed(NOVAS):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS contatos_checar_limite()")
    op.execute("DROP FUNCTION IF EXISTS limite_contatos(text, text)")
