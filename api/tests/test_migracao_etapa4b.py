"""Migração 0007 (IA por resposta, relatórios, picos e resumo semanal): restrições do banco, colunas geradas de
reclamação/elogio; descer para a 0006 e subir de novo."""
import json

import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import DBAPIError, IntegrityError
from util import API, conta_pronta, criar_contato, registrar_resposta, sql

from alembic import command
from toqqi.core.db import RAIZ_API

COLUNAS_RESPOSTAS = {"ia_situacao", "ia_temas", "ia_sentimento", "ia_resumo", "ia_modelo", "ia_em", "ia_tentativas",
                     "ia_reservada_em", "ia_texto_hash", "temas_reclamacao", "temas_elogio"}
TABELAS = ("ia_uso_mensal", "alertas_pico", "resumos_semanais")
FUNCOES = ("classe_tema", "temas_reclamacao", "temas_elogio")
pytestmark = pytest.mark.usefixtures("relogio_estavel")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono, tabela: str) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = :t", t=tabela)}


def _funcoes(dono) -> set[str]:
    return {f for (f,) in sql(dono, "select proname from pg_proc where proname = any(:f)", f=list(FUNCOES))}


@pytest.fixture
def resposta(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    c = criar_contato(client, a["h"], nome="Paula")
    r = registrar_resposta(client, a["h"], c["id"], 3, comentario="Atrasou e o preço subiu")
    assert r.status_code == 201, r.text
    return {**a, "contato": c, "resposta": r.json()["id"]}


@pytest.mark.parametrize("coluna,valor", [
    ("ia_situacao", "processando"), ("ia_sentimento", "bravo"), ("ia_resumo", "x" * 161), ("ia_modelo", "x" * 101),
    ("ia_tentativas", -1), ("ia_tentativas", 101), ("ia_texto_hash", "abc"), ("ia_texto_hash", "A" * 64),
])
def test_restricoes_das_colunas_da_ia(resposta, dono, coluna, valor):
    with pytest.raises(IntegrityError):
        sql(dono, f"update respostas set {coluna} = :v where id = :r", v=valor, r=resposta["resposta"])


def test_restricoes_das_tabelas_novas(resposta, dono):
    conta = resposta["conta"]["id"]
    with pytest.raises(IntegrityError):  # ia_temas é sempre uma lista
        sql(dono, "update respostas set ia_temas = cast(:v as jsonb) where id = :r",
            v=json.dumps({"tema": "prazo_entrega"}), r=resposta["resposta"])
    with pytest.raises(DBAPIError, match="generated"):  # coluna gerada não se grava
        sql(dono, "update respostas set temas_reclamacao = '{}' where id = :r", r=resposta["resposta"])
    for comando in (
        "insert into ia_uso_mensal (conta_id, mes) values (:c, '2026-03-02')",               # mês começa no dia 1
        "insert into ia_uso_mensal (conta_id, mes, analises) values (:c, '2026-03-01', -1)",
        "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior) values (:c, 'frete', 3, 0)",
        "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior) values (:c, 'atendimento', 3, -1)",
        "insert into resumos_semanais (conta_id, semana) values (:c, '2026-03-03')",          # terça
    ):
        with pytest.raises(IntegrityError):
            sql(dono, comando, c=conta)
    sql(dono, "insert into resumos_semanais (conta_id, semana) values (:c, '2026-03-02')", c=conta)
    with pytest.raises(IntegrityError):  # um resumo por conta e semana
        sql(dono, "insert into resumos_semanais (conta_id, semana) values (:c, '2026-03-02')", c=conta)


def test_colunas_geradas_de_reclamacao_e_elogio(resposta, dono):
    r = resposta["resposta"]
    # o provedor de testes analisou (sentimento pela nota): os dois temas como reclamação
    assert sql(dono, "select ia_situacao, temas, temas_reclamacao, temas_elogio from respostas where id = :r",
               r=r) == [("analisada", ["prazo_entrega", "preco_condicoes"], ["prazo_entrega", "preco_condicoes"], [])]
    # a IA diz que o preço foi elogiado: só o prazo é reclamação
    sql(dono, "update respostas set ia_temas = cast(:t as jsonb) where id = :r", r=r, t=json.dumps(
        [{"tema": "prazo_entrega", "sentimento": "negativo"}, {"tema": "preco_condicoes", "sentimento": "positivo"}]))
    assert sql(dono, "select temas_reclamacao, temas_elogio from respostas where id = :r", r=r) == [
        (["prazo_entrega"], ["preco_condicoes"])]
    # sem análise vale a nota: detrator reclama de tudo; promotor elogia tudo; neutro nem um nem outro
    sql(dono, "update respostas set ia_situacao = null where id = :r", r=r)
    assert sql(dono, "select temas_reclamacao, temas_elogio from respostas where id = :r", r=r) == [
        (["prazo_entrega", "preco_condicoes"], [])]
    for nota, grupo, esperado in ((9, "promotor", ([], ["prazo_entrega", "preco_condicoes"])), (7, "neutro", ([], []))):
        sql(dono, "update respostas set nota = :n, grupo = :g where id = :r", n=nota, g=grupo, r=r)
        assert sql(dono, "select temas_reclamacao, temas_elogio from respostas where id = :r", r=r) == [esperado]


def test_descer_e_subir_a_0007(client, resposta, dono):
    h, conta, r = resposta["h"], resposta["conta"]["id"], resposta["resposta"]
    assert sql(dono, "select analises from ia_uso_mensal where conta_id = :c", c=conta) == [(1,)]
    sql(dono, "insert into alertas_pico (conta_id, tema, reclamacoes, media_anterior) values (:c, 'atendimento', 3, 0)",
        c=conta)
    sql(dono, "insert into resumos_semanais (conta_id, semana) values (:c, '2026-03-02')", c=conta)
    sql(dono, "update contas set ia_analise_respostas = false where id = :c", c=conta)
    cfg = _alembic()
    command.downgrade(cfg, "0006_dados_empresa")
    try:
        assert sql(dono, "select to_regclass('ia_uso_mensal'), to_regclass('alertas_pico'), "
                         "to_regclass('resumos_semanais')")[0] == (None, None, None)
        assert not COLUNAS_RESPOSTAS & _colunas(dono, "respostas")
        assert "ia_analise_respostas" not in _colunas(dono, "contas")
        assert not {"recebe_resumo_semanal", "recebe_alertas"} & _colunas(dono, "usuarios")
        assert _funcoes(dono) == set()
        assert sql(dono, "select to_regclass('respostas_ia_fila_idx'), to_regclass('respostas_empresa_data_idx')")[
            0] == (None, None)
        # a resposta fica, com nota, comentário e temas
        assert sql(dono, "select nota, comentario, temas from respostas where id = :r", r=r) == [
            (3, "Atrasou e o preço subiu", ["prazo_entrega", "preco_condicoes"])]
        # dado antigo, como se viesse da 0006: depois da subida a reclamação sai da nota
        sql(dono, "update respostas set temas = '{atendimento}' where id = :r", r=r)
    finally:
        command.upgrade(cfg, "head")
    assert COLUNAS_RESPOSTAS <= _colunas(dono, "respostas")
    assert _funcoes(dono) == set(FUNCOES)
    assert sql(dono, "select ia_situacao, ia_tentativas, temas_reclamacao, temas_elogio from respostas where id = :r",
               r=r) == [(None, 0, ["atendimento"], [])]
    assert sql(dono, "select ia_analise_respostas from contas where id = :c", c=conta) == [(True,)]  # padrão
    assert sql(dono, "select recebe_resumo_semanal, recebe_alertas from usuarios where conta_id = :c", c=conta) == [
        (True, True)]
    for t in TABELAS:
        assert sql(dono, f"select count(*) from {t}")[0][0] == 0, t
    # o papel da aplicação volta a ter acesso às tabelas novas (a análise grava o uso do mês)
    assert client.get(f"{API}/conta/ia", headers=h).json()["analises"] == 0
    nova = registrar_resposta(client, h, resposta["contato"]["id"], 2, comentario="Produto veio quebrado")
    assert nova.status_code == 201, nova.text
    assert client.get(f"{API}/respostas/{nova.json()['id']}", headers=h).json()["ia"]["situacao"] == "analisada"
    assert client.get(f"{API}/conta/ia", headers=h).json()["analises"] == 1
    assert client.get(f"{API}/relatorios/temas", headers=h).status_code == 200
