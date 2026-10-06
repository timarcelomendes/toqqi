"""Etapa 5l (docs/api-etapa-5l.md §1.5, §4.6 e §4.7): construtor de formulários com lógica, conteúdo/HTML, finais,
rascunho e publicação.

- `formularios`: `finais` (jsonb, lista; os finais publicados), `rascunho` (jsonb {perguntas, tema, finais} ou nulo),
  `rascunho_rev` (controle de concorrência), `rascunho_em`/`rascunho_por`, `versao` (sobe a cada publicação),
  `publicado_em`/`publicado_por`. As FKs de usuário seguem o padrão da conta: chave composta (id, conta_id) com
  ON DELETE SET NULL só da coluna. Nos formulários que já existem, `versao` = 1 e `publicado_em` = `atualizado_em`
  (depois, o padrão de `publicado_em` é now()).
- `respostas.formulario_versao`: a versão publicada quando a resposta chegou (nula nas antigas e nas importadas).
- `imagens`: `uso` aceita 'conteudo_formulario' (imagens dos blocos de conteúdo, até 1 MB como o banco de imagens);
  `formulario_id` preenchido nos dois usos de formulário (e só neles); o índice único "um logo por formulário" vira um
  índice comum (o rascunho pode trocar o logo sem apagar o que está no ar).
- A `condicao` antiga das perguntas (etapa 2) vira `logica.mostrar_se` com a fonte na nota principal, por um conversor
  daqui (não importa o código vivo), nas perguntas publicadas e no rascunho.

RLS: só colunas novas em tabelas que já têm RLS com FORCE e a política de sempre; os GRANTs da tabela valem para elas.

O downgrade volta tudo: a lógica de uma condição só na nota principal (grupo, ≤ ou ≥) volta a ser `condicao`, o resto
da lógica, os blocos de conteúdo, os finais e os rascunhos saem; as imagens de conteúdo são apagadas e fica um logo por
formulário (o do tema, senão o mais novo).

Revision ID: 0026_formularios_v2
Revises: 0025_planos_5k
"""
import json

from sqlalchemy import text

from alembic import op

revision = "0026_formularios_v2"
down_revision = "0025_planos_5k"
branch_labels = None
depends_on = None

LIMITE_LOGO = 300 * 1024  # 307200 bytes (como na 0006)
LIMITE_GRANDE = 1024 * 1024  # 1048576 bytes: banco de imagens (0014) e imagens de conteúdo
COLUNAS = ("finais", "rascunho", "rascunho_rev", "rascunho_em", "rascunho_por", "versao", "publicado_em",
           "publicado_por")
_OPERADORES_ANTIGOS = {"<=": "menor_igual", ">=": "maior_igual"}


# ---- conversores (cópia congelada: mudar o código da aplicação não muda esta migração) ----------

def _principal(perguntas: list) -> int | None:
    for tipos in (("nps",), ("csat", "estrelas")):
        for i, p in enumerate(perguntas):
            if isinstance(p, dict) and p.get("tipo") in tipos:
                return i
    return None


def _para_logica(perguntas):
    """`condicao` → `logica.mostrar_se` (fonte na nota principal). Devolve a lista nova, ou None se nada mudou."""
    if not isinstance(perguntas, list) or not any(isinstance(p, dict) and "condicao" in p for p in perguntas):
        return None
    ip = _principal(perguntas)
    saida = []
    for i, p in enumerate(perguntas):
        if not isinstance(p, dict) or "condicao" not in p:
            saida.append(p)
            continue
        p = dict(p)
        cond = p.pop("condicao")
        logica = p.get("logica") if isinstance(p.get("logica"), dict) else {}
        mostrar_se = None
        if ip is not None and i > ip and isinstance(cond, dict) and not logica.get("mostrar_se"):
            fonte = perguntas[ip].get("id")
            if cond.get("tipo") == "grupo" and isinstance(cond.get("grupos"), list):
                mostrar_se = {"juncao": "todas",
                              "condicoes": [{"fonte": fonte, "op": "grupo_e", "valor": list(cond["grupos"])}]}
            elif cond.get("tipo") == "nota" and cond.get("operador") in _OPERADORES_ANTIGOS:
                mostrar_se = {"juncao": "todas", "condicoes": [
                    {"fonte": fonte, "op": _OPERADORES_ANTIGOS[cond["operador"]], "valor": cond.get("valor")}]}
        if mostrar_se is not None:
            p["logica"] = {"mostrar_se": mostrar_se, "pular": logica.get("pular") or []}
        saida.append(p)
    return saida


def _para_condicao(perguntas):
    """Volta para a etapa 2: sem blocos de conteúdo; a lógica de uma condição só (grupo, ≤ ou ≥) na nota principal,
    em pergunta depois dela, vira `condicao`; o resto da lógica sai."""
    if not isinstance(perguntas, list):
        return None
    itens = [p for p in perguntas if not (isinstance(p, dict) and p.get("tipo") == "conteudo")]
    ip = _principal(itens)
    volta = {v: k for k, v in _OPERADORES_ANTIGOS.items()}
    saida = []
    for i, p in enumerate(itens):
        if not isinstance(p, dict) or "logica" not in p:
            saida.append(p)
            continue
        p = dict(p)
        logica = p.pop("logica") or {}
        grupo = logica.get("mostrar_se") if isinstance(logica, dict) else None
        condicoes = grupo.get("condicoes") if isinstance(grupo, dict) else None
        if ip is not None and i > ip and isinstance(condicoes, list) and len(condicoes) == 1:
            c = condicoes[0]
            if c.get("fonte") == itens[ip].get("id") and c.get("op") == "grupo_e" and isinstance(c.get("valor"), list):
                p["condicao"] = {"tipo": "grupo", "grupos": c["valor"]}
            elif c.get("fonte") == itens[ip].get("id") and c.get("op") in volta:
                p["condicao"] = {"tipo": "nota", "operador": volta[c["op"]], "valor": c.get("valor")}
        saida.append(p)
    return saida if saida != perguntas else None


def _converter(conn, coluna: str, converter) -> None:
    """Aplica o conversor nas perguntas (`perguntas` publicadas ou `rascunho`→perguntas) de todos os formulários."""
    for fid, valor in conn.execute(text(f"SELECT id, {coluna} FROM formularios WHERE {coluna} IS NOT NULL")).all():
        if coluna == "perguntas":
            novo = converter(valor)
            if novo is not None:
                conn.execute(text("UPDATE formularios SET perguntas = CAST(:v AS jsonb) WHERE id = :id"),
                             {"v": json.dumps(novo), "id": fid})
            continue
        perguntas = converter(valor.get("perguntas")) if isinstance(valor, dict) else None
        if perguntas is not None:
            conn.execute(text("UPDATE formularios SET rascunho = CAST(:v AS jsonb) WHERE id = :id"),
                         {"v": json.dumps({**valor, "perguntas": perguntas}), "id": fid})


def _tamanho(usos_grandes: str) -> str:
    return (f"CHECK (tamanho >= 1 AND tamanho <= CASE WHEN uso IN ({usos_grandes}) THEN {LIMITE_GRANDE} "
            f"ELSE {LIMITE_LOGO} END)")


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("SELECT set_config('app.sistema', 'on', true)"))  # RLS forçado: os UPDATEs abaixo precisam
    op.execute("""
        ALTER TABLE formularios
            ADD COLUMN finais jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(finais) = 'array'),
            ADD COLUMN rascunho jsonb CHECK (rascunho IS NULL OR jsonb_typeof(rascunho) = 'object'),
            ADD COLUMN rascunho_rev integer NOT NULL DEFAULT 0 CHECK (rascunho_rev >= 0),
            ADD COLUMN rascunho_em timestamptz,
            ADD COLUMN rascunho_por bigint,
            ADD COLUMN versao integer NOT NULL DEFAULT 1 CHECK (versao >= 1),
            ADD COLUMN publicado_em timestamptz,
            ADD COLUMN publicado_por bigint,
            ADD CONSTRAINT formularios_rascunho_por_fkey FOREIGN KEY (rascunho_por, conta_id)
                REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (rascunho_por),
            ADD CONSTRAINT formularios_publicado_por_fkey FOREIGN KEY (publicado_por, conta_id)
                REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (publicado_por)
    """)
    op.execute("UPDATE formularios SET publicado_em = atualizado_em")
    op.execute("ALTER TABLE formularios ALTER COLUMN publicado_em SET DEFAULT now()")
    op.execute("ALTER TABLE respostas ADD COLUMN formulario_versao integer CHECK (formulario_versao >= 1)")

    # imagens: o CHECK sem nome da 0006 (logo de formulário ⇔ formulario_id) é achado pela definição
    op.execute("""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT conname FROM pg_constraint
                      WHERE conrelid = 'imagens'::regclass AND contype = 'c'
                        AND pg_get_constraintdef(oid) LIKE '%formulario_id IS NOT NULL%'
            LOOP
                EXECUTE format('ALTER TABLE imagens DROP CONSTRAINT %I', r.conname);
            END LOOP;
        END $$
    """)
    op.execute(f"""
        ALTER TABLE imagens
            DROP CONSTRAINT imagens_uso_check,
            ADD CONSTRAINT imagens_uso_check
                CHECK (uso IN ('logo_conta','logo_formulario','banco','conteudo_formulario')),
            DROP CONSTRAINT imagens_tamanho_check,
            ADD CONSTRAINT imagens_tamanho_check {_tamanho("'banco','conteudo_formulario'")},
            ADD CONSTRAINT imagens_formulario_check
                CHECK ((uso IN ('logo_formulario','conteudo_formulario')) = (formulario_id IS NOT NULL))
    """)
    op.execute("DROP INDEX IF EXISTS imagens_logo_formulario_key")
    op.execute("CREATE INDEX imagens_formulario_idx ON imagens (formulario_id) WHERE formulario_id IS NOT NULL")

    _converter(conn, "perguntas", _para_logica)
    _converter(conn, "rascunho", _para_logica)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("SELECT set_config('app.sistema', 'on', true)"))
    _converter(conn, "perguntas", _para_condicao)
    op.execute("DELETE FROM imagens WHERE uso = 'conteudo_formulario'")
    # um logo por formulário: fica o do tema publicado; sem ele, o mais novo
    op.execute("""
        DELETE FROM imagens i
         USING formularios f
         WHERE i.uso = 'logo_formulario' AND f.id = i.formulario_id
           AND i.id <> coalesce(
               (SELECT x.id FROM imagens x WHERE x.formulario_id = f.id AND x.uso = 'logo_formulario'
                   AND right(f.tema->>'logo_url', length(x.chave) + 1) = '/' || x.chave LIMIT 1),
               (SELECT x.id FROM imagens x WHERE x.formulario_id = f.id AND x.uso = 'logo_formulario'
                 ORDER BY x.criada_em DESC, x.id DESC LIMIT 1))
    """)
    op.execute("DROP INDEX IF EXISTS imagens_formulario_idx")
    op.execute("CREATE UNIQUE INDEX imagens_logo_formulario_key ON imagens (formulario_id) "
               "WHERE uso = 'logo_formulario'")
    op.execute(f"""
        ALTER TABLE imagens
            DROP CONSTRAINT imagens_formulario_check,
            DROP CONSTRAINT imagens_tamanho_check,
            ADD CONSTRAINT imagens_tamanho_check {_tamanho("'banco'")},
            DROP CONSTRAINT imagens_uso_check,
            ADD CONSTRAINT imagens_uso_check CHECK (uso IN ('logo_conta','logo_formulario','banco')),
            ADD CONSTRAINT imagens_check1 CHECK ((uso = 'logo_formulario') = (formulario_id IS NOT NULL))
    """)
    op.execute("ALTER TABLE respostas DROP COLUMN IF EXISTS formulario_versao")
    op.execute("ALTER TABLE formularios DROP CONSTRAINT IF EXISTS formularios_rascunho_por_fkey, "
               "DROP CONSTRAINT IF EXISTS formularios_publicado_por_fkey, "
               + ", ".join(f"DROP COLUMN IF EXISTS {c}" for c in COLUNAS))
