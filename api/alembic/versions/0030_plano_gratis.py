"""Plano Grátis (docs/api-plano-gratis.md), pedido do Marcelo em 13/10/2026.

- `contas.situacao`: `gratis` entra no lugar de `teste_expirado`. Quem termina o teste sem assinar, quem cancelou e
  viu o período pago acabar e quem ficou 30 dias com a fatura vencida passa para o Grátis, em vez de ter os envios
  parados e a conta apagada. As contas `teste_expirado` que existirem viram `gratis` (motivo `teste`) e perdem o aviso
  de exclusão da etapa 5f (o Grátis não é apagado por data: só por falta de uso);
- `contas`: `gratis_desde` e `gratis_motivo` (teste | cancelamento | atraso), preenchidos só no Grátis; a nota de
  risco gravada pela tarefa (`risco_pontos`, `risco_em`) e a liberação da equipe (`risco_liberado_pontos`,
  `risco_liberado_em`): no Grátis, nota 60 ou mais pausa os envios até a equipe liberar;
- `envios_uso`: os e-mails de pesquisa (convites e lembretes) da conta Grátis no mês e no dia, contados ao agendar;
  `avisou_fim` = o e-mail "os envios do mês acabaram" já saiu neste mês;
- `denuncias`: "Denunciar esta pesquisa" nas pesquisas das contas Grátis. Só o modo sistema lê e grava (a conta
  denunciada nunca vê);
- `parametros` e `parametros_historico`: a chave e o histórico aceitam o grupo `gratis`;
- `limite_contatos(p_plano, p_situacao)`: no Grátis, `gratis.contatos` (padrão 100), qualquer que seja o plano (a
  política `ler_limites` deixa o papel da aplicação ler também essa linha); o gatilho `contatos_checar_limite` não usa
  o contratado do Personalizado no Grátis.

O downgrade volta tudo: Grátis que nunca pagou vira `teste_expirado`; o que já pagou, `cancelada`.

Revision ID: 0030_plano_gratis
Revises: 0029_login_google
"""
import os
import re

from alembic import op

revision = "0030_plano_gratis"
down_revision = "0029_login_google"
branch_labels = None
depends_on = None

SITUACOES_NOVAS = ("teste", "gratis", "ativa", "atrasada", "cancelada", "cortesia")
SITUACOES_ANTIGAS = ("teste", "teste_expirado", "ativa", "atrasada", "cancelada", "cortesia")
CHAVE_NOVA = r"^(planos|ia|whatsapp|teste|gratis)\.[a-z0-9_]+(\.[a-z0-9_]+)?$"
CHAVE_ANTIGA = r"^(planos|ia|whatsapp|teste)\.[a-z0-9_]+(\.[a-z0-9_]+)?$"
MOTIVOS_DENUNCIA = ("dados_pessoais", "golpe", "spam", "ofensa", "outro")
GRUPOS_ANTIGOS = ("planos", "ia", "whatsapp", "teste")

LIMITE = """
    CREATE OR REPLACE FUNCTION limite_contatos(p_plano text, p_situacao text) RETURNS integer
    LANGUAGE sql STABLE AS $$
        WITH linha AS (
            SELECT CASE WHEN jsonb_typeof(valor) = 'number' AND valor::text ~ '^[0-9]{{1,7}}$'
                        THEN (valor::text)::integer END AS limite
              FROM parametros
             WHERE chave = {chave}
               AND CASE WHEN jsonb_typeof(valor) = 'null' THEN {nulo}
                        WHEN jsonb_typeof(valor) = 'number' AND valor::text ~ '^[0-9]{{1,7}}$'
                            THEN (valor::text)::integer BETWEEN 1 AND 1000000
                        ELSE false
                   END
        )
        SELECT CASE
            WHEN p_situacao = 'cortesia' THEN NULL
            WHEN EXISTS (SELECT 1 FROM linha) THEN (SELECT limite FROM linha)
            {gratis}
            WHEN p_plano = 'essencial' THEN 300
            WHEN p_plano = 'profissional' THEN 1500
            WHEN p_plano = 'empresa' THEN 5000
            ELSE NULL
        END
    $$
"""
LIMITE_NOVO = LIMITE.format(
    chave="CASE WHEN p_situacao = 'gratis' THEN 'gratis.contatos' ELSE 'planos.' || p_plano || '.contatos' END",
    nulo="p_situacao <> 'gratis'",  # o Grátis sempre tem limite: null (sem limite) não vale para ele
    gratis="WHEN p_situacao = 'gratis' THEN 100")
LIMITE_ANTIGO = LIMITE.format(chave="'planos.' || p_plano || '.contatos'", nulo="true", gratis="")

GATILHO = """
    CREATE OR REPLACE FUNCTION contatos_checar_limite() RETURNS trigger LANGUAGE plpgsql AS $$
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
        -- Trava ANTES de ler o plano (sempre): a troca de plano segura a mesma trava enquanto confere os contatos
        -- ativos e grava o plano novo; quem esperou aqui lê o plano já trocado.
        PERFORM pg_advisory_xact_lock(740221, NEW.conta_id::integer);
        SELECT {limite} INTO v_limite FROM contas c WHERE c.id = NEW.conta_id;
        IF v_limite IS NULL THEN
            RETURN NEW;
        END IF;
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
"""
GATILHO_NOVO = GATILHO.format(
    limite="CASE WHEN c.plano = 'personalizado' AND c.situacao NOT IN ('cortesia', 'gratis') "
           "THEN c.contatos_personalizado ELSE limite_contatos(c.plano, c.situacao) END")
GATILHO_ANTIGO = GATILHO.format(
    limite="CASE WHEN c.plano = 'personalizado' AND c.situacao <> 'cortesia' THEN c.contatos_personalizado "
           "ELSE limite_contatos(c.plano, c.situacao) END")


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _lista(valores: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in valores)


def _check_situacao(valores: tuple[str, ...]) -> None:
    op.execute("ALTER TABLE contas DROP CONSTRAINT IF EXISTS contas_situacao_check")
    op.execute(f"ALTER TABLE contas ADD CONSTRAINT contas_situacao_check CHECK (situacao IN ({_lista(valores)}))")


def _check_chave(regex: str, grupos: tuple[str, ...]) -> None:
    op.execute("ALTER TABLE parametros DROP CONSTRAINT IF EXISTS parametros_chave_check")
    op.execute(f"ALTER TABLE parametros ADD CONSTRAINT parametros_chave_check CHECK (chave ~ '{regex}')")
    op.execute("ALTER TABLE parametros_historico DROP CONSTRAINT IF EXISTS parametros_historico_grupo_check")
    op.execute("ALTER TABLE parametros_historico ADD CONSTRAINT parametros_historico_grupo_check "
               f"CHECK (grupo IN ({_lista(grupos)}))")


def upgrade() -> None:
    op.execute("SELECT set_config('app.sistema', 'on', true)")  # as linhas de todas as contas (RLS)
    op.execute("ALTER TABLE contas "
               "ADD COLUMN gratis_desde timestamptz, "
               "ADD COLUMN gratis_motivo text CHECK (gratis_motivo IN ('teste','cancelamento','atraso')), "
               "ADD COLUMN risco_pontos smallint CHECK (risco_pontos BETWEEN 0 AND 100), "
               "ADD COLUMN risco_em timestamptz, "
               "ADD COLUMN risco_liberado_pontos smallint CHECK (risco_liberado_pontos BETWEEN 0 AND 100), "
               "ADD COLUMN risco_liberado_em timestamptz, "
               "ADD CONSTRAINT contas_risco_liberado_check "
               "CHECK ((risco_liberado_pontos IS NULL) = (risco_liberado_em IS NULL))")
    _check_situacao(SITUACOES_ANTIGAS + ("gratis",))
    op.execute("UPDATE contas SET situacao = 'gratis', gratis_desde = now(), "
               "gratis_motivo = CASE WHEN pago_ate IS NULL THEN 'teste' ELSE 'cancelamento' END, "
               "exclusao_avisada_para = NULL, exclusao_avisada_em = NULL "
               "WHERE situacao = 'teste_expirado'")
    # no Grátis, o descanso entre duas pesquisas para o mesmo contato é de pelo menos 30 dias
    op.execute("UPDATE config_envios SET descanso_dias = 30 WHERE descanso_dias < 30 "
               "AND conta_id IN (SELECT id FROM contas WHERE situacao = 'gratis')")
    _check_situacao(SITUACOES_NOVAS)
    op.execute("CREATE INDEX contas_gratis_idx ON contas (id) WHERE situacao = 'gratis'")

    op.execute("""
        CREATE TABLE envios_uso (
            conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE,
            mes date NOT NULL CHECK (extract(day FROM mes) = 1),
            emails integer NOT NULL DEFAULT 0 CHECK (emails >= 0),
            dia date NOT NULL,
            emails_dia integer NOT NULL DEFAULT 0 CHECK (emails_dia >= 0),
            avisou_fim boolean NOT NULL DEFAULT false,
            PRIMARY KEY (conta_id, mes)
        )
    """)
    op.execute("ALTER TABLE envios_uso ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE envios_uso FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY isolamento_conta ON envios_uso
            USING (conta_id = app_conta() OR app_sistema())
            WITH CHECK (conta_id = app_conta() OR app_sistema())
    """)

    op.execute(f"""
        CREATE TABLE denuncias (
            id bigserial PRIMARY KEY,
            conta_id bigint NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
            formulario_id bigint REFERENCES formularios(id) ON DELETE SET NULL,
            formulario_nome text CHECK (length(formulario_nome) <= 200),
            origem text NOT NULL CHECK (origem IN ('convite','link_publico')),
            motivo text NOT NULL CHECK (motivo IN ({_lista(MOTIVOS_DENUNCIA)})),
            detalhe text CHECK (length(detalhe) <= 1000),
            ip_hash text CHECK (length(ip_hash) <= 64),
            situacao text NOT NULL DEFAULT 'aberta' CHECK (situacao IN ('aberta','procedente','descartada')),
            criada_em timestamptz NOT NULL DEFAULT now(),
            resolvida_em timestamptz,
            nota_interna text CHECK (length(nota_interna) <= 2000)
        )
    """)
    op.execute("CREATE INDEX denuncias_conta_idx ON denuncias (conta_id, criada_em DESC)")
    op.execute("CREATE INDEX denuncias_criada_idx ON denuncias (criada_em DESC)")
    op.execute("ALTER TABLE denuncias ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE denuncias FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY so_sistema ON denuncias USING (app_sistema()) WITH CHECK (app_sistema())")

    _check_chave(CHAVE_NOVA, GRUPOS_ANTIGOS + ("gratis",))
    op.execute("DROP POLICY ler_limites ON parametros")
    op.execute("CREATE POLICY ler_limites ON parametros FOR SELECT "
               "USING (chave LIKE 'planos.%.contatos' OR chave = 'gratis.contatos')")
    op.execute(LIMITE_NOVO)
    op.execute(GATILHO_NOVO)

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON envios_uso, denuncias TO {papel};
                GRANT USAGE, SELECT ON SEQUENCE denuncias_id_seq TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute(GATILHO_ANTIGO)
    op.execute(LIMITE_ANTIGO)
    op.execute("DELETE FROM parametros WHERE chave LIKE 'gratis.%'")
    op.execute("DELETE FROM parametros WHERE chave IN ('ia.cota.gratis', 'ia.teto.gratis', 'whatsapp.franquia.gratis')")
    op.execute("DELETE FROM parametros_historico WHERE grupo = 'gratis'")
    _check_chave(CHAVE_ANTIGA, GRUPOS_ANTIGOS)
    op.execute("DROP POLICY ler_limites ON parametros")
    op.execute("CREATE POLICY ler_limites ON parametros FOR SELECT USING (chave LIKE 'planos.%.contatos')")
    op.execute("DROP TABLE denuncias")
    op.execute("DROP TABLE envios_uso")
    op.execute("DROP INDEX contas_gratis_idx")
    _check_situacao(SITUACOES_ANTIGAS + ("gratis",))
    op.execute("UPDATE contas SET situacao = CASE WHEN pago_ate IS NULL THEN 'teste_expirado' ELSE 'cancelada' END "
               "WHERE situacao = 'gratis'")
    _check_situacao(SITUACOES_ANTIGAS)
    op.execute("ALTER TABLE contas DROP CONSTRAINT contas_risco_liberado_check, "
               "DROP COLUMN risco_liberado_em, DROP COLUMN risco_liberado_pontos, DROP COLUMN risco_em, "
               "DROP COLUMN risco_pontos, DROP COLUMN gratis_motivo, DROP COLUMN gratis_desde")
