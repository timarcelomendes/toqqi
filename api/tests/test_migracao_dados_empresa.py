"""Migração 0006 (dados da empresa e imagens): restrições do banco; descer para a 0005 e subir de novo."""
import hashlib

import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import API, conta_pronta, form_padrao, png, sql

from alembic import command
from toqqi.core.db import RAIZ_API

COLUNAS = {"razao_social", "documento", "telefone", "email_contato", "site", "cep", "logradouro", "numero",
           "complemento", "bairro", "cidade", "uf", "dados_atualizados_em"}


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono, tabela: str) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = :t", t=tabela)}


@pytest.mark.parametrize("coluna,valor", [
    ("documento", "123"), ("documento", "1122233300018a"), ("telefone", "123"), ("telefone", "55119876543210"),
    ("cep", "0131010"), ("uf", "XX"), ("site", "ftp://alfa.com.br"), ("site", "https://" + "x" * 200),
    ("razao_social", ""), ("email_contato", "x" * 255), ("numero", "x" * 21),
])
def test_restricoes_de_contas(client, dono, coluna, valor):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    with pytest.raises(IntegrityError):
        sql(dono, f"update contas set {coluna} = :v where id = :c", v=valor, c=a["conta"]["id"])


def test_restricoes_de_imagens(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    f = form_padrao(client, a["h"])
    dados = png()

    def inserir(**campos):
        v = {"conta_id": a["conta"]["id"], "uso": "logo_conta", "formulario_id": None, "chave": "c" * 43,
             "tipo": "image/png", "dados": dados, "tamanho": len(dados),
             "sha256": hashlib.sha256(dados).hexdigest(), **campos}
        sql(dono, "insert into imagens (conta_id, uso, formulario_id, chave, tipo, dados, tamanho, sha256) "
                  "values (:conta_id, :uso, :formulario_id, :chave, :tipo, :dados, :tamanho, :sha256)", **v)

    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (300 * 1024 - 7)
    for campos in ({"formulario_id": f["id"]},                       # logo da conta não aponta para formulário
                   {"uso": "logo_formulario"},                       # logo de formulário sem formulário
                   {"uso": "fundo"}, {"tipo": "image/gif"}, {"tipo": "image/svg+xml"},
                   {"chave": "curta"}, {"chave": "c" * 42 + "/"},
                   {"tamanho": 1},                                    # tamanho diferente dos bytes
                   {"dados": grande, "tamanho": len(grande)},         # acima de 300 KB
                   {"sha256": "x" * 64}):
        with pytest.raises(IntegrityError):
            inserir(**campos)
    inserir()
    inserir(chave="d" * 43, uso="logo_formulario", formulario_id=f["id"])
    with pytest.raises(IntegrityError):  # um logo por conta
        inserir(chave="e" * 43)
    with pytest.raises(IntegrityError):  # um logo por formulário
        inserir(chave="f" * 43, uso="logo_formulario", formulario_id=f["id"])
    with pytest.raises(IntegrityError):  # chave única
        inserir(chave="d" * 43, uso="logo_formulario", formulario_id=form_padrao(client, a["h"], "csat")["id"])
    assert sql(dono, "select count(*) from imagens")[0][0] == 2


def test_descer_e_subir_a_0006(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h = a["h"]
    r = client.put(f"{API}/conta/dados", headers=h, json={"nome": "Alfa Nova", "cidade": "Recife"})
    assert r.status_code == 200
    arquivo = {"arquivo": ("logo.png", png(), "image/png")}
    assert client.put(f"{API}/conta/logo", headers=h, files=arquivo).status_code == 200
    cfg = _alembic()
    command.downgrade(cfg, "0005_respostas_acoes")
    try:
        assert sql(dono, "select to_regclass('imagens')")[0][0] is None
        assert not COLUNAS & _colunas(dono, "contas")
        assert sql(dono, "select nome from contas where id = :c", c=a["conta"]["id"])[0][0] == "Alfa Nova"
    finally:
        command.upgrade(cfg, "head")
    assert COLUNAS <= _colunas(dono, "contas")
    d = client.get(f"{API}/conta/dados", headers=h).json()
    assert d["nome"] == "Alfa Nova" and d["cidade"] is None and d["logo_url"] is None and d["atualizado_em"] is None
    r = client.put(f"{API}/conta/logo", headers=h, files=arquivo)  # o papel da aplicação volta a ter acesso
    assert r.status_code == 200 and r.json()["logo_url"]
