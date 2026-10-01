"""Etapa 4a: respostas (data informada, origem, temas, análise e arquivamento), planos de ação, prazos das
ações automáticas e tipo da importação (contatos ou respostas antigas).

Mesmo padrão das etapas anteriores: conta_id DEFAULT app_conta(), RLS com FORCE e chaves compostas
(id, conta_id) nas referências entre tabelas da conta.

`data_resposta` (coluna gerada: data informada, senão a de entrada) é a data de toda regra de período.
`comentario_cliente` guarda só o que o cliente escreveu (nas respostas de pesquisa, as perguntas de comentário;
nas outras, o comentário). As respostas que já existem recebem origem (pelo canal), comentário do cliente e
temas. A detecção de temas está COPIADA aqui (congelada): mudar a da aplicação não muda esta migração.

Revision ID: 0005_respostas_acoes
Revises: 0004_integracoes
Create Date: 2026-09-30
"""
import os
import re
import unicodedata

from sqlalchemy import text

from alembic import op

revision = "0005_respostas_acoes"
down_revision = "0004_integracoes"
branch_labels = None
depends_on = None

NOVAS = ["acoes", "config_acoes"]
CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
CANAIS_ANTES = "'email','whatsapp','link','qr','widget','api','importacao','manual'"
CANAIS = CANAIS_ANTES + ",'telefone','reuniao'"
TEMAS = "'prazo_entrega','produto_avarias','atendimento','preco_condicoes','comunicacao','sistema_pedidos'"
GRUPOS = "'detrator','neutro','promotor','insatisfeito','satisfeito'"
LOTE = 5000


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def upgrade() -> None:
    op.execute("ALTER TABLE respostas ADD COLUMN respondida_em timestamptz")
    op.execute("ALTER TABLE respostas ADD COLUMN data_resposta timestamptz "
               "GENERATED ALWAYS AS (coalesce(respondida_em, criada_em)) STORED")
    op.execute(f"""
        ALTER TABLE respostas
            ADD COLUMN origem text NOT NULL DEFAULT 'pesquisa' CHECK (origem IN ('pesquisa','manual','importacao')),
            ADD COLUMN temas text[] NOT NULL DEFAULT '{{}}' CHECK (temas <@ ARRAY[{TEMAS}]::text[]),
            ADD COLUMN temas_manuais boolean NOT NULL DEFAULT false,
            ADD COLUMN o_que_faltou text CHECK (length(o_que_faltou) <= 2000),
            ADD COLUMN o_que_combinamos text CHECK (length(o_que_combinamos) <= 2000),
            ADD COLUMN analisada_em timestamptz,
            ADD COLUMN analisada_por bigint,
            ADD COLUMN registrada_por bigint,
            ADD COLUMN arquivada_em timestamptz,
            ADD COLUMN comentario_cliente text NOT NULL DEFAULT '',
            ADD CONSTRAINT respostas_analisada_por_fkey FOREIGN KEY (analisada_por, conta_id)
                REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (analisada_por),
            ADD CONSTRAINT respostas_registrada_por_fkey FOREIGN KEY (registrada_por, conta_id)
                REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (registrada_por),
            DROP CONSTRAINT respostas_canal_check,
            ADD CONSTRAINT respostas_canal_check CHECK (canal IN ({CANAIS}))
    """)
    op.execute("CREATE INDEX respostas_data_idx ON respostas (conta_id, data_resposta DESC) WHERE NOT arquivada")

    op.execute(f"""
        CREATE TABLE acoes (
            id bigserial PRIMARY KEY,
            {CONTA},
            resposta_id bigint,
            empresa_id bigint,
            contato_id bigint,
            responsavel_id bigint,
            titulo text NOT NULL CHECK (length(titulo) BETWEEN 1 AND 200),
            descricao text NOT NULL DEFAULT '' CHECK (length(descricao) <= 4000),
            resolucao text CHECK (length(resolucao) <= 4000),
            prioridade text NOT NULL CHECK (prioridade IN ('alta','media','baixa')),
            prazo date,
            situacao text NOT NULL DEFAULT 'a_fazer' CHECK (situacao IN ('a_fazer','em_andamento','concluida')),
            origem text NOT NULL DEFAULT 'manual' CHECK (origem IN ('automatica','manual')),
            grupo text CHECK (grupo IN ({GRUPOS})),
            tipo_nota text CHECK (tipo_nota IN ('nps','csat')),
            nota smallint,
            criado_por bigint,
            criada_em timestamptz NOT NULL DEFAULT now(),
            atualizada_em timestamptz NOT NULL DEFAULT now(),
            iniciada_em timestamptz,
            concluida_em timestamptz,
            concluida_por bigint,
            UNIQUE (id, conta_id),
            FOREIGN KEY (resposta_id, conta_id) REFERENCES respostas(id, conta_id) ON DELETE SET NULL (resposta_id),
            FOREIGN KEY (empresa_id, conta_id) REFERENCES empresas(id, conta_id) ON DELETE SET NULL (empresa_id),
            FOREIGN KEY (contato_id, conta_id) REFERENCES contatos(id, conta_id) ON DELETE SET NULL (contato_id),
            FOREIGN KEY (responsavel_id, conta_id) REFERENCES responsaveis(id, conta_id)
                ON DELETE SET NULL (responsavel_id),
            FOREIGN KEY (criado_por, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (criado_por),
            FOREIGN KEY (concluida_por, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (concluida_por)
        )
    """)
    # uma ação automática por resposta
    op.execute("CREATE UNIQUE INDEX acoes_automatica_resposta_key ON acoes (conta_id, resposta_id) "
               "WHERE origem = 'automatica'")
    op.execute("CREATE INDEX acoes_quadro_idx ON acoes (conta_id, situacao, prazo)")
    op.execute("CREATE INDEX acoes_empresa_idx ON acoes (conta_id, empresa_id)")
    op.execute("CREATE INDEX acoes_resposta_idx ON acoes (conta_id, resposta_id)")
    op.execute("CREATE INDEX acoes_contato_idx ON acoes (conta_id, contato_id)")

    op.execute("""
        CREATE TABLE config_acoes (
            conta_id bigint PRIMARY KEY DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            prazo_detrator integer NOT NULL DEFAULT 2 CHECK (prazo_detrator BETWEEN 1 AND 90),
            prazo_neutro integer NOT NULL DEFAULT 5 CHECK (prazo_neutro BETWEEN 1 AND 90),
            prazo_promotor integer NOT NULL DEFAULT 7 CHECK (prazo_promotor BETWEEN 1 AND 90),
            acao_promotor boolean NOT NULL DEFAULT false,
            atualizado_em timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("ALTER TABLE importacoes ADD COLUMN tipo text NOT NULL DEFAULT 'contatos' "
               "CHECK (tipo IN ('contatos','respostas'))")

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

    _preencher_respostas_existentes()


# ---- cópia congelada (etapa 4a) da extração do texto do cliente e da detecção de temas -----------------------
# Não importe código da aplicação aqui: instalações novas e os testes rodam todas as migrações, e a aplicação
# pode mudar depois. Mesmo conteúdo de toqqi.modulos.respostas.temas e registro na data desta migração.

_TEMAS_CONGELADOS = (
    ("prazo_entrega", ("atras", "demor", "prazo", "entreg", "chegou", "chegada", "frete", "transportadora",
                       "motorista", "coleta", "logistica")),
    ("produto_avarias", ("avaria", "quebrad", "danificad", "amassad", "estragad", "vencid", "validade", "defeito",
                         "qualidade", "embalage", "produto errado", "faltando", "troca", "devoluc", "devolv")),
    ("atendimento", ("atendiment", "atendente", "atencios", "vendedor", "representante", "educad", "grosseir",
                     "simpati", "cordial", "prestativ", "suporte", "sac", "pos venda")),
    ("preco_condicoes", ("preco", "caro", "valor", "desconto", "promoc", "condic", "pagamento", "boleto", "parcel",
                         "juros", "credito", "tabela", "custo", "barat")),
    ("comunicacao", ("comunica", "informac", "inform", "avis", "retorno", "contato", "ligac", "telefone",
                     "whatsapp", "email", "e mail", "rastre", "acompanhament", "atualizac")),
    ("sistema_pedidos", ("sistema", "site", "aplicativo", "app", "portal", "plataforma", "fazer pedido",
                         "tirar pedido", "pedido errado", "pedido incompleto", "erro no pedido", "digitac",
                         "nota fiscal", "nf", "nfe", "faturament", "cadastro", "login", "senha")),
)
_PADROES = [(c, re.compile(r"\b(?:" + "|".join(re.escape(p) for p in ps) + ")")) for c, ps in _TEMAS_CONGELADOS]


def _detectar(texto: str) -> list[str]:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = re.sub(r"[^a-z0-9]+", " ", "".join(ch for ch in t if unicodedata.category(ch) != "Mn")).strip()
    return [c for c, padrao in _PADROES if padrao.search(t)] if t else []


def _texto(v) -> str:
    return ", ".join(str(x) for x in v) if isinstance(v, list) else str(v)


def _comentario_cliente(origem: str, comentario: str, perguntas, respostas) -> str:
    if origem != "pesquisa":
        return (comentario or "").strip()
    partes = [respostas[p["id"]].strip() for p in perguntas or []
              if p.get("tipo") == "comentario" and isinstance((respostas or {}).get(p.get("id")), str)
              and respostas[p["id"]].strip()]
    return " · ".join(partes)


def _escolhas(perguntas, respostas) -> str:
    return " ".join(_texto(respostas[p["id"]]) for p in perguntas or []
                    if p.get("tipo") in ("escolha_unica", "escolha_multipla") and p.get("id") in (respostas or {}))


def _preencher_respostas_existentes() -> None:
    """Origem pelo canal; comentário do cliente e temas pela cópia congelada acima (RLS com FORCE: modo sistema)."""
    conn = op.get_bind()
    conn.execute(text("select set_config('app.sistema', 'on', true)"))
    conn.execute(text("UPDATE respostas SET origem = canal WHERE canal IN ('manual', 'importacao')"))
    perguntas = dict(conn.execute(text("select id, perguntas from formularios")).all())
    ultimo = 0
    while True:
        linhas = conn.execute(text("""
            select id, formulario_id, origem, comentario, respostas from respostas
             where id > :ultimo order by id limit :lote
        """), {"ultimo": ultimo, "lote": LOTE}).all()
        if not linhas:
            break
        ids, comentarios, temas = [], [], []
        for rid, formulario_id, origem, comentario, respostas in linhas:
            p = perguntas.get(formulario_id)
            cliente = _comentario_cliente(origem, comentario, p, respostas)
            escolhas = _escolhas(p, respostas) if origem == "pesquisa" else ""
            ids.append(rid)
            comentarios.append(cliente)
            temas.append(",".join(_detectar(f"{cliente}\n{escolhas}")))
        conn.execute(text("""
            UPDATE respostas r SET comentario_cliente = x.comentario, temas = string_to_array(x.temas, ',')
              FROM unnest(CAST(:ids AS bigint[]), CAST(:comentarios AS text[]), CAST(:temas AS text[]))
                   AS x(id, comentario, temas)
             WHERE r.id = x.id
        """), {"ids": ids, "comentarios": comentarios, "temas": temas})
        ultimo = linhas[-1][0]


def downgrade() -> None:
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    for t in reversed(NOVAS):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("DELETE FROM importacoes WHERE tipo = 'respostas'")
    op.execute("ALTER TABLE importacoes DROP COLUMN tipo")
    # A etapa anterior só conhece criada_em (como data da resposta) e o canal (manual/importacao como origem).
    op.execute("UPDATE respostas SET criada_em = respondida_em WHERE respondida_em IS NOT NULL")
    op.execute("UPDATE respostas SET canal = origem WHERE origem IN ('manual', 'importacao')")
    op.execute("UPDATE respostas SET canal = 'manual' WHERE canal IN ('telefone', 'reuniao')")
    op.execute("DROP INDEX IF EXISTS respostas_data_idx")
    op.execute("ALTER TABLE respostas DROP COLUMN data_resposta")
    op.execute(f"""
        ALTER TABLE respostas
            DROP CONSTRAINT respostas_canal_check,
            ADD CONSTRAINT respostas_canal_check CHECK (canal IN ({CANAIS_ANTES})),
            DROP COLUMN respondida_em,
            DROP COLUMN origem,
            DROP COLUMN temas,
            DROP COLUMN temas_manuais,
            DROP COLUMN o_que_faltou,
            DROP COLUMN o_que_combinamos,
            DROP COLUMN analisada_em,
            DROP COLUMN analisada_por,
            DROP COLUMN registrada_por,
            DROP COLUMN arquivada_em,
            DROP COLUMN comentario_cliente
    """)
