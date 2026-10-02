"""Migração 0013 (IA sob demanda): colunas novas de `contas` e `acoes` com os padrões e as restrições, a tabela
`ia_pareceres` (restrições, único por recorte, índices), descer para a 0012 (tudo desfeito) e subir de novo."""
import json

import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import API, acao, conta_pronta, criar_contato, form_padrao, gerar_ia, inserir_resposta, sql

from alembic import command
from toqqi.core import relogio
from toqqi.core.db import RAIZ_API

pytestmark = pytest.mark.usefixtures("relogio_estavel")
COLUNAS_CONTAS = {"ia_modelo", "ia_estilo", "ia_passos_acoes"}
COLUNAS_ACOES = {"ia_passos", "ia_passos_situacao", "ia_passos_em", "ia_passos_tentativas", "ia_passos_reservada_em"}
PARECER = ("insert into ia_pareceres (conta_id, tipo, chave, filtros, conteudo, modelo, estilo) "
           "values (:c, :tipo, :chave, cast(:filtros as jsonb), cast(:conteudo as jsonb), :modelo, :estilo)")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono, tabela: str) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = :t", t=tabela)}


def _objeto(dono, nome: str):
    return sql(dono, "select to_regclass(:n)", n=nome)[0][0]


@pytest.fixture
def conta(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


@pytest.fixture
def acao_id(dono, conta) -> int:
    return sql(dono, "insert into acoes (conta_id, titulo, prioridade) values (:c, 'Ação', 'alta') returning id",
               c=conta["conta"]["id"])[0][0]


def test_padroes_das_colunas_novas(conta, acao_id, dono):
    c = conta["conta"]["id"]
    assert sql(dono, "select ia_modelo, ia_estilo, ia_passos_acoes from contas where id = :c", c=c) == [
        ("equilibrado", "equilibrada", True)]
    assert sql(dono, "select ia_passos, ia_passos_situacao, ia_passos_em, ia_passos_tentativas, "
                     "ia_passos_reservada_em from acoes where id = :a", a=acao_id) == [(None, None, None, 0, None)]
    assert _objeto(dono, "acoes_ia_passos_fila_idx") is not None
    assert _objeto(dono, "ia_pareceres_recentes_idx") is not None


@pytest.mark.parametrize("coluna,valor", [("ia_modelo", "turbo"), ("ia_modelo", None), ("ia_estilo", "formal"),
                                          ("ia_passos_acoes", None)])
def test_restricoes_de_contas(conta, dono, coluna, valor):
    with pytest.raises(IntegrityError):
        sql(dono, f"update contas set {coluna} = :v where id = :c", v=valor, c=conta["conta"]["id"])


@pytest.mark.parametrize("passos,situacao", [
    ([], "pronta"),  # 1 a 3
    (["a", "b", "c", "d"], "pronta"),
    ([""], "pronta"),  # texto vazio
    (["x" * 201], "pronta"),  # até 200 caracteres
    ([1], "pronta"),  # só textos
    ({"passo": "a"}, "pronta"),  # lista
    (["Ligue para o cliente."], "pendente"),  # passos só com 'pronta'
    (None, "pronta"),  # 'pronta' sempre com os passos
    (None, "processando"),
])
def test_restricoes_dos_passos(acao_id, dono, passos, situacao):
    with pytest.raises(IntegrityError):
        sql(dono, "update acoes set ia_passos = cast(:p as jsonb), ia_passos_situacao = :s where id = :a",
            p=None if passos is None else json.dumps(passos), s=situacao, a=acao_id)


def test_passos_validos_no_banco(acao_id, dono):
    for passos in (["Ligue."], ["a", "b", "c"], ["x" * 200], ["é" * 200]):
        sql(dono, "update acoes set ia_passos = cast(:p as jsonb), ia_passos_situacao = 'pronta' where id = :a",
            p=json.dumps(passos), a=acao_id)
    for situacao in ("pendente", "falhou", "limite", None):
        sql(dono, "update acoes set ia_passos = null, ia_passos_situacao = :s where id = :a", s=situacao, a=acao_id)
    for tentativas in (-1, 101):
        with pytest.raises(IntegrityError):
            sql(dono, "update acoes set ia_passos_tentativas = :t where id = :a", t=tentativas, a=acao_id)


@pytest.mark.parametrize("campos", [
    {"tipo": "assistente"}, {"chave": ""}, {"chave": "x" * 201}, {"filtros": "[]"}, {"conteudo": '"texto"'},
    {"modelo": "turbo"}, {"estilo": "formal"}, {"modelo": None}, {"filtros": None},
])
def test_restricoes_dos_pareceres(conta, dono, campos):
    valores = {"tipo": "painel", "chave": "de=|ate=|grupo=|ativos=1", "filtros": "{}", "conteudo": "{}",
               "modelo": "rapido", "estilo": "objetiva", **campos}
    with pytest.raises(IntegrityError):
        sql(dono, PARECER, c=conta["conta"]["id"], **valores)


def test_um_parecer_por_recorte(conta, dono):
    c = conta["conta"]["id"]
    valores = {"tipo": "painel", "chave": "de=|ate=|grupo=|ativos=1", "filtros": "{}", "conteudo": "{}",
               "modelo": "rapido", "estilo": "objetiva"}
    sql(dono, PARECER, c=c, **valores)
    sql(dono, PARECER, c=c, **{**valores, "tipo": "relatorios"})  # outro tipo, mesma chave: pode
    with pytest.raises(IntegrityError):
        sql(dono, PARECER, c=c, **valores)
    assert sql(dono, "select gerado_por, gerado_em is not null from ia_pareceres where tipo = 'painel'") == [
        (None, True)]


def test_descer_e_subir_a_0013(client, conta, dono):
    h, c = conta["h"], conta["conta"]["id"]
    inserir_resposta(dono, c, form_padrao(client, h)["id"], None, 9, relogio.hoje(), comentario="Tudo certo")
    assert gerar_ia(client, h).status_code == 200
    assert client.put(f"{API}/conta/ia", headers=h, json={"modelo": "detalhado", "estilo": "criativa",
                                                          "passos_acoes": False}).status_code == 200
    contato = criar_contato(client, h, nome="Paula")
    sql(dono, "update contas set ia_passos_acoes = true where id = :c", c=c)
    assert client.post(f"{API}/respostas", headers=h, json={"contato_id": contato["id"], "nota": 2,
                                                            "comentario": "Atrasou"}).status_code == 201
    assert sql(dono, "select ia_passos_situacao from acoes") == [("pronta",)]
    cfg = _alembic()
    command.downgrade(cfg, "0012_crescimento")
    try:
        assert _objeto(dono, "ia_pareceres") is None and _objeto(dono, "acoes_ia_passos_fila_idx") is None
        assert not COLUNAS_CONTAS & _colunas(dono, "contas")
        assert not COLUNAS_ACOES & _colunas(dono, "acoes")
        assert sql(dono, "select count(*) from acoes")[0][0] == 1  # a ação fica, sem os passos
    finally:
        command.upgrade(cfg, "head")
    assert COLUNAS_CONTAS <= _colunas(dono, "contas") and COLUNAS_ACOES <= _colunas(dono, "acoes")
    # os padrões voltam (a escolha da conta se perde com a coluna)
    assert sql(dono, "select ia_modelo, ia_estilo, ia_passos_acoes from contas where id = :c", c=c) == [
        ("equilibrado", "equilibrada", True)]
    assert sql(dono, "select ia_passos, ia_passos_situacao, ia_passos_tentativas from acoes") == [(None, None, 0)]
    # e a aplicação volta a usar tudo (permissões do papel da aplicação na tabela nova)
    assert client.get(f"{API}/painel/resumo-ia", headers=h).json()["item"] is None
    assert gerar_ia(client, h).status_code == 200
    r = client.post(f"{API}/respostas", headers=h, json={"contato_id": contato["id"], "nota": 1,
                                                         "comentario": "Produto quebrado"})
    assert r.status_code == 201
    novas = sql(dono, "select id from acoes where ia_passos_situacao = 'pronta'")
    assert len(novas) == 1 and len(acao(client, h, novas[0][0])["ia_passos"]) == 3
