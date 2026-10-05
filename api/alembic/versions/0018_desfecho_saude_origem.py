"""Etapa 5i: desfecho das empresas (perda, retorno e histórico), saúde da conta e origem do cadastro.

- `empresas`: `renovacao_em` (renovação ou fim do contrato), `perdida_em`, `motivo_perda` e `motivo_detalhe` (≤ 300).
  Perdida = `perdida_em` preenchida, com motivo e `ativa` false (`empresas_perda_check`). Índices parciais das
  renovações (só não perdidas) e das perdidas.
- `empresa_historico` (padrão da 0013: conta_id DEFAULT app_conta() com CASCADE, RLS com FORCE e a política de sempre,
  chave composta da empresa com CASCADE e do usuário com SET NULL): `entrada`, `valor`, `perdida` e `reativada`, com o
  dia que vale para os cálculos, valor antes e depois, motivo, os contatos desativados na perda, a origem (`tela`,
  `importacao`, `api`, `migracao`, `sistema`) e o usuário. Papel da aplicação: SELECT, INSERT e UPDATE (a edição da
  perda, feita pelo gatilho); sem DELETE nem TRUNCATE (as linhas saem em cascata com a empresa ou a conta).
- Gatilho `empresas_historico` (AFTER INSERT OR UPDATE OF valor_mensal, perdida_em, motivo_perda, motivo_detalhe):
  grava o histórico venha a mudança de onde vier. Lê da transação `app.hoje` (AAAA-MM-DD; sem ele, o dia do banco em
  São Paulo), `app.empresa_origem` (sem ele, `sistema`), `app.usuario_id` (sem ele, ou de outra conta, nulo) e, na
  perda, `app.contatos_desativados` (ids separados por vírgula, chaves opcionais; sem ele, lista vazia).
- Gatilho `contatos_empresa_perdida` (BEFORE INSERT OR UPDATE OF ativo, empresa_id ON contatos): contato ativo em
  empresa perdida → SQLSTATE `TQ409` (`core.errors` responde 409 `empresa_perdida`). Roda antes do limite do plano
  (`contatos_limite_plano`, ordem alfabética).
- `webhooks.eventos` aceita `empresa.perdida` e `empresa.reativada`; `config_envios.ocultar_mencao_toqqi`;
  `contas.origem` (utm_source, utm_medium e utm_campaign, cada um `^[a-z0-9._-]{1,60}$`); índice dos convites por
  empresa e data (saúde).
- Semente: uma `entrada` por empresa **ativa** (dia da criação em São Paulo, valor de hoje, origem `migracao`).

O downgrade apaga os gatilhos, as funções e a tabela, tira os eventos novos dos webhooks (os que só tinham eles somem,
com as entregas desses eventos), volta o CHECK, apaga o índice e as colunas novas. As perdidas ficam inativas.

Revision ID: 0018_desfecho_saude_origem
Revises: 0017_erros
Create Date: 2026-10-05
"""
import os
import re

from alembic import op

revision = "0018_desfecho_saude_origem"
down_revision = "0017_erros"
branch_labels = None
depends_on = None

CONTA = "conta_id bigint NOT NULL DEFAULT app_conta() REFERENCES contas(id) ON DELETE CASCADE"
MOTIVOS = "'preco','concorrente','atendimento','produto','encerrou','outro'"
TIPOS = "'entrada','valor','perdida','reativada'"
ORIGENS = "'tela','importacao','api','migracao','sistema'"
EVENTOS_ANTES = "'resposta.criada','contato.descadastrado','indicacao.criada','indicacao.atualizada'"
EVENTOS_NOVOS = "'empresa.perdida','empresa.reativada'"
# objeto não vazio, só as três chaves, cada valor um texto limpo (minúsculas, dígitos, ponto, sublinhado e hífen)
ORIGEM_VALIDA = (
    "jsonb_typeof(origem) = 'object' AND origem <> '{}'::jsonb AND NOT jsonb_path_exists(origem, "
    "'$.keyvalue() ? (!(@.key == \"utm_source\" || @.key == \"utm_medium\" || @.key == \"utm_campaign\") "
    "|| @.value.type() != \"string\" || !(@.value like_regex \"^[a-z0-9._-]{1,60}$\"))')"
)

FUNCAO_HISTORICO = """
    CREATE FUNCTION empresas_registrar_historico() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        v_hoje date := coalesce(nullif(current_setting('app.hoje', true), '')::date,
                                (now() AT TIME ZONE 'America/Sao_Paulo')::date);
        v_origem text := coalesce(nullif(current_setting('app.empresa_origem', true), ''), 'sistema');
        v_usuario bigint := nullif(current_setting('app.usuario_id', true), '')::bigint;
        v_lista text := btrim(coalesce(current_setting('app.contatos_desativados', true), ''), '{} ');
        v_contatos bigint[] := CASE WHEN v_lista = '' THEN '{}'::bigint[]
                                    ELSE string_to_array(v_lista, ',')::bigint[] END;
        v_evento text;
        v_data date;
    BEGIN
        -- usuário de outra conta (equipe Toqqi pela Plataforma) ou que não existe: sem usuário
        IF v_usuario IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM usuarios u WHERE u.id = v_usuario AND u.conta_id = NEW.conta_id
        ) THEN
            v_usuario := NULL;
        END IF;

        IF TG_OP = 'INSERT' THEN
            -- já nasce perdida (só pela API): a entrada não fica depois da perda
            v_data := CASE WHEN NEW.perdida_em IS NULL THEN v_hoje ELSE least(v_hoje, NEW.perdida_em) END;
            INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_depois, origem, usuario_id)
                VALUES (NEW.conta_id, NEW.id, 'entrada', v_data, NEW.valor_mensal, v_origem, v_usuario);
            IF NEW.perdida_em IS NOT NULL THEN
                INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_antes, motivo, motivo_detalhe,
                                               contatos, origem, usuario_id)
                    VALUES (NEW.conta_id, NEW.id, 'perdida', NEW.perdida_em, NEW.valor_mensal, NEW.motivo_perda,
                            NEW.motivo_detalhe, v_contatos, v_origem, v_usuario);
            END IF;
            RETURN NULL;
        END IF;

        IF OLD.perdida_em IS NULL AND NEW.perdida_em IS NOT NULL THEN
            v_evento := 'perdida';
            v_data := NEW.perdida_em;
        ELSIF OLD.perdida_em IS NOT NULL AND NEW.perdida_em IS NULL THEN
            v_evento := 'reativada';
            v_data := v_hoje;
        ELSIF NEW.perdida_em IS NOT NULL THEN
            -- perdida antes e depois: só a edição da perda; valor mudado enquanto perdida vai na linha do retorno
            IF (OLD.perdida_em, OLD.motivo_perda, OLD.motivo_detalhe)
                    IS DISTINCT FROM (NEW.perdida_em, NEW.motivo_perda, NEW.motivo_detalhe) THEN
                v_evento := 'edicao';
                v_data := NEW.perdida_em;
            END IF;
        ELSIF OLD.valor_mensal IS DISTINCT FROM NEW.valor_mensal THEN
            v_evento := 'valor';
            v_data := v_hoje;
        END IF;
        IF v_evento IS NULL THEN
            RETURN NULL;
        END IF;

        -- empresa sem histórico (pausada de antes da 0018): a entrada vem antes do evento
        IF NOT EXISTS (SELECT 1 FROM empresa_historico h
                        WHERE h.conta_id = NEW.conta_id AND h.empresa_id = NEW.id) THEN
            INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_depois, origem, usuario_id)
                VALUES (NEW.conta_id, NEW.id, 'entrada', least(v_hoje, v_data), OLD.valor_mensal, v_origem,
                        v_usuario);
        END IF;

        IF v_evento = 'perdida' THEN
            INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_antes, motivo, motivo_detalhe,
                                           contatos, origem, usuario_id)
                VALUES (NEW.conta_id, NEW.id, 'perdida', NEW.perdida_em, OLD.valor_mensal, NEW.motivo_perda,
                        NEW.motivo_detalhe, v_contatos, v_origem, v_usuario);
        ELSIF v_evento = 'reativada' THEN
            INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_antes, valor_depois, origem,
                                           usuario_id)
                VALUES (NEW.conta_id, NEW.id, 'reativada', v_hoje, OLD.valor_mensal, NEW.valor_mensal, v_origem,
                        v_usuario);
        ELSIF v_evento = 'edicao' THEN
            UPDATE empresa_historico h
               SET data = NEW.perdida_em, motivo = NEW.motivo_perda, motivo_detalhe = NEW.motivo_detalhe
             WHERE h.id = (SELECT max(u.id) FROM empresa_historico u
                            WHERE u.conta_id = NEW.conta_id AND u.empresa_id = NEW.id AND u.tipo = 'perdida');
            IF NOT FOUND THEN  -- perdida sem linha (não acontece pela aplicação): registra agora
                INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_antes, motivo,
                                               motivo_detalhe, contatos, origem, usuario_id)
                    VALUES (NEW.conta_id, NEW.id, 'perdida', NEW.perdida_em, OLD.valor_mensal, NEW.motivo_perda,
                            NEW.motivo_detalhe, '{}', v_origem, v_usuario);
            END IF;
        ELSE
            INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_antes, valor_depois, origem,
                                           usuario_id)
                VALUES (NEW.conta_id, NEW.id, 'valor', v_hoje, OLD.valor_mensal, NEW.valor_mensal, v_origem,
                        v_usuario);
        END IF;
        RETURN NULL;
    END $$
"""

FUNCAO_CONTATOS = """
    CREATE FUNCTION contatos_checar_empresa_perdida() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.ativo AND NEW.empresa_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM empresas e
             WHERE e.id = NEW.empresa_id AND e.conta_id = NEW.conta_id AND e.perdida_em IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'Esta empresa foi marcada como perdida.' USING ERRCODE = 'TQ409';
        END IF;
        RETURN NEW;
    END $$
"""


def _papel_app() -> str:
    papel = os.environ.get("APP_DB_ROLE", "toqqi_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", papel):
        raise ValueError("APP_DB_ROLE inválido")
    return papel


def _check_eventos(eventos: str) -> None:
    op.execute(f"""
        ALTER TABLE webhooks DROP CONSTRAINT IF EXISTS webhooks_eventos_check,
            ADD CONSTRAINT webhooks_eventos_check CHECK (cardinality(eventos) >= 1 AND eventos <@ ARRAY[{eventos}])
    """)


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE empresas
            ADD COLUMN renovacao_em date,
            ADD COLUMN perdida_em date,
            ADD COLUMN motivo_perda text CHECK (motivo_perda IN ({MOTIVOS})),
            ADD COLUMN motivo_detalhe text CHECK (length(motivo_detalhe) <= 300),
            ADD CONSTRAINT empresas_perda_check CHECK (
                (perdida_em IS NULL AND motivo_perda IS NULL AND motivo_detalhe IS NULL)
                OR (perdida_em IS NOT NULL AND motivo_perda IS NOT NULL AND NOT ativa))
    """)
    op.execute("CREATE INDEX empresas_renovacao_idx ON empresas (conta_id, renovacao_em) "
               "WHERE renovacao_em IS NOT NULL AND perdida_em IS NULL")
    op.execute("CREATE INDEX empresas_perdidas_idx ON empresas (conta_id, perdida_em) WHERE perdida_em IS NOT NULL")

    op.execute(f"""
        CREATE TABLE empresa_historico (
            id bigserial PRIMARY KEY,
            {CONTA},
            empresa_id bigint NOT NULL,
            tipo text NOT NULL CHECK (tipo IN ({TIPOS})),
            data date NOT NULL,
            valor_antes numeric(12,2),
            valor_depois numeric(12,2),
            motivo text CHECK (motivo IN ({MOTIVOS})),
            motivo_detalhe text CHECK (length(motivo_detalhe) <= 300),
            contatos bigint[],
            origem text NOT NULL CHECK (origem IN ({ORIGENS})),
            usuario_id bigint,
            criado_em timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT empresa_historico_motivo_so_perdida CHECK ((tipo = 'perdida') = (motivo IS NOT NULL)),
            CONSTRAINT empresa_historico_contatos_so_perdida CHECK (contatos IS NULL OR tipo = 'perdida'),
            CONSTRAINT empresa_historico_valor_mudou CHECK (tipo <> 'valor' OR valor_antes IS DISTINCT FROM valor_depois),
            FOREIGN KEY (empresa_id, conta_id) REFERENCES empresas(id, conta_id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id, conta_id) REFERENCES usuarios(id, conta_id) ON DELETE SET NULL (usuario_id)
        )
    """)
    op.execute("CREATE INDEX empresa_historico_empresa_idx ON empresa_historico (conta_id, empresa_id, data, id)")
    op.execute("CREATE INDEX empresa_historico_perdas_idx ON empresa_historico (conta_id, data) "
               "WHERE tipo = 'perdida'")
    # o SET NULL quando o usuário sai da equipe
    op.execute("CREATE INDEX empresa_historico_usuario_idx ON empresa_historico (usuario_id) "
               "WHERE usuario_id IS NOT NULL")
    op.execute("ALTER TABLE empresa_historico ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE empresa_historico FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY isolamento_conta ON empresa_historico
            USING (conta_id = app_conta() OR app_sistema())
            WITH CHECK (conta_id = app_conta() OR app_sistema())
    """)

    op.execute(FUNCAO_HISTORICO)
    op.execute("""
        CREATE TRIGGER empresas_historico
            AFTER INSERT OR UPDATE OF valor_mensal, perdida_em, motivo_perda, motivo_detalhe ON empresas
            FOR EACH ROW EXECUTE FUNCTION empresas_registrar_historico()
    """)
    op.execute(FUNCAO_CONTATOS)
    op.execute("""
        CREATE TRIGGER contatos_empresa_perdida
            BEFORE INSERT OR UPDATE OF ativo, empresa_id ON contatos
            FOR EACH ROW EXECUTE FUNCTION contatos_checar_empresa_perdida()
    """)

    _check_eventos(f"{EVENTOS_ANTES},{EVENTOS_NOVOS}")
    op.execute("ALTER TABLE config_envios ADD COLUMN ocultar_mencao_toqqi boolean NOT NULL DEFAULT false")
    op.execute(f"ALTER TABLE contas ADD COLUMN origem jsonb CONSTRAINT contas_origem_check CHECK ({ORIGEM_VALIDA})")
    # saúde: os convites de cada empresa, dos mais novos para os mais antigos (o `convites_empresa_idx` da 0015, só
    # por empresa_id, fica para o SET NULL da exclusão)
    op.execute("CREATE INDEX convites_empresa_recentes_idx ON convites (conta_id, empresa_id, criado_em DESC) "
               "WHERE empresa_id IS NOT NULL")

    # semente: a carteira de hoje das ativas, no dia em que cada uma foi criada
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute("""
        INSERT INTO empresa_historico (conta_id, empresa_id, tipo, data, valor_depois, origem)
        SELECT conta_id, id, 'entrada', (criada_em AT TIME ZONE 'America/Sao_Paulo')::date, valor_mensal, 'migracao'
          FROM empresas WHERE ativa
         ORDER BY conta_id, id
    """)
    op.execute("SELECT set_config('app.sistema', '', true)")

    papel = _papel_app()
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{papel}') THEN
                GRANT SELECT, INSERT, UPDATE ON empresa_historico TO {papel};
                REVOKE DELETE, TRUNCATE ON empresa_historico FROM {papel};
                GRANT USAGE, SELECT ON SEQUENCE empresa_historico_id_seq TO {papel};
            ELSE
                RAISE WARNING 'Papel % não existe: permissões não concedidas', '{papel}';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("SELECT set_config('app.sistema', 'on', true)")
    op.execute("DROP TRIGGER IF EXISTS contatos_empresa_perdida ON contatos")
    op.execute("DROP TRIGGER IF EXISTS empresas_historico ON empresas")
    op.execute("DROP FUNCTION IF EXISTS contatos_checar_empresa_perdida()")
    op.execute("DROP FUNCTION IF EXISTS empresas_registrar_historico()")
    op.execute("DROP TABLE IF EXISTS empresa_historico CASCADE")

    op.execute(f"DELETE FROM webhook_entregas WHERE evento IN ({EVENTOS_NOVOS})")
    op.execute(f"DELETE FROM webhooks WHERE eventos <@ ARRAY[{EVENTOS_NOVOS}]")  # só tinham os eventos novos
    op.execute("UPDATE webhooks SET eventos = array_remove(array_remove(eventos, 'empresa.perdida'), "
               f"'empresa.reativada') WHERE eventos && ARRAY[{EVENTOS_NOVOS}]")
    _check_eventos(EVENTOS_ANTES)

    op.execute("DROP INDEX IF EXISTS convites_empresa_recentes_idx")
    op.execute("ALTER TABLE contas DROP COLUMN IF EXISTS origem")
    op.execute("ALTER TABLE config_envios DROP COLUMN IF EXISTS ocultar_mencao_toqqi")
    op.execute("DROP INDEX IF EXISTS empresas_perdidas_idx")
    op.execute("DROP INDEX IF EXISTS empresas_renovacao_idx")
    # as perdidas já estão inativas (o CHECK garante) e ficam assim
    op.execute("""
        ALTER TABLE empresas
            DROP CONSTRAINT IF EXISTS empresas_perda_check,
            DROP COLUMN IF EXISTS renovacao_em,
            DROP COLUMN IF EXISTS perdida_em,
            DROP COLUMN IF EXISTS motivo_perda,
            DROP COLUMN IF EXISTS motivo_detalhe
    """)
