"""Migração 0014 (e-mails): colunas do visual em `config_envios` (padrões e restrições, chave composta com SET NULL),
`imagens` com o uso 'banco' (1 MB; logos continuam com 300 KB), a tabela `emails_enviados` (restrições, índices, RLS
forçado), descer para a 0013 (tudo desfeito, imagens do banco apagadas, logos mantidos) e subir de novo."""
import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import API, conta_pronta, png, sql

from alembic import command
from toqqi.core.db import RAIZ_API
from toqqi.core.email import TIPOS

COLUNAS_CONFIG = {"email_cor", "email_mostrar_logo", "email_imagem_topo_id", "email_assinatura", "email_rodape"}
COLUNAS_IMAGENS = {"nome", "largura", "altura"}
IMAGEM = ("insert into imagens (conta_id, uso, chave, tipo, dados, tamanho, sha256, nome, largura, altura) "
          "values (:c, :uso, :chave, 'image/png', decode(repeat('00', :n), 'hex'), :n, repeat('0', 64), :nome, :l, :a) "
          "returning id")
EMAIL = ("insert into emails_enviados (conta_id, tipo, destinatario, assunto, situacao, erro) "
         "values (:c, :tipo, :para, :assunto, :situacao, :erro)")


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


def _imagem(dono, conta_id: int, uso: str = "banco", n: int = 10, chave: str = "c" * 40, nome: str | None = "a.png",
            largura: int | None = 1, altura: int | None = 1) -> int:
    return sql(dono, IMAGEM, c=conta_id, uso=uso, chave=chave, n=n, nome=nome, l=largura, a=altura)[0][0]


@pytest.fixture
def conta(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    assert client.get(f"{API}/envios/configuracao", headers=a["h"]).status_code == 200  # cria a config_envios
    return a


def test_padroes_e_objetos(conta, dono):
    c = conta["conta"]["id"]
    assert sql(dono, "select email_cor, email_mostrar_logo, email_imagem_topo_id, email_assinatura, email_rodape "
                     "from config_envios where conta_id = :c", c=c) == [(None, True, None, None, None)]
    for nome in ("imagens_banco_idx", "config_envios_imagem_topo_idx", "emails_enviados_recentes_idx",
                 "emails_enviados_situacao_idx"):
        assert _objeto(dono, nome) is not None, nome
    linhas = sql(dono, """
        select c.relrowsecurity, c.relforcerowsecurity, array_agg(p.polname)
          from pg_class c join pg_policy p on p.polrelid = c.oid where c.relname = 'emails_enviados' group by 1, 2
    """)
    assert linhas == [(True, True, ["isolamento_conta"])]
    # os tipos do CHECK são os de core.email.TIPOS
    definicao = sql(dono, "select pg_get_constraintdef(oid) from pg_constraint "
                          "where conrelid = 'emails_enviados'::regclass and conname = 'emails_enviados_tipo_check'")[0][0]
    assert all(f"'{t}'" in definicao for t in TIPOS)


@pytest.mark.parametrize("coluna,valor", [
    ("email_cor", "#d63a18"),  # guardada em maiúsculas
    ("email_cor", "D63A18"),
    ("email_cor", "#D63A1"),
    ("email_assinatura", ""),
    ("email_assinatura", "x" * 301),
    ("email_rodape", "x" * 501),
    ("email_mostrar_logo", None),
    ("email_imagem_topo_id", 999999),  # imagem que não existe
])
def test_restricoes_do_visual(conta, dono, coluna, valor):
    with pytest.raises(IntegrityError):
        sql(dono, f"update config_envios set {coluna} = :v where conta_id = :c", v=valor, c=conta["conta"]["id"])


def test_imagem_de_topo_so_da_propria_conta_e_set_null(client, conta, dono):
    c = conta["conta"]["id"]
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    da_b = _imagem(dono, b["conta"]["id"], chave="b" * 40)
    with pytest.raises(IntegrityError):  # chave composta: a imagem precisa ser da mesma conta
        sql(dono, "update config_envios set email_imagem_topo_id = :i where conta_id = :c", i=da_b, c=c)
    minha = _imagem(dono, c)
    sql(dono, "update config_envios set email_imagem_topo_id = :i, email_cor = '#D63A18' where conta_id = :c",
        i=minha, c=c)
    sql(dono, "delete from imagens where id = :i", i=minha)
    assert sql(dono, "select email_imagem_topo_id, email_cor from config_envios where conta_id = :c", c=c) == [
        (None, "#D63A18")]  # só a imagem vira nula


@pytest.mark.parametrize("campos", [
    {"uso": "banner"},
    {"uso": "banco", "n": 1024 * 1024 + 1},
    {"uso": "logo_conta", "n": 300 * 1024 + 1},  # logos continuam com 300 KB
    {"nome": ""},
    {"nome": "x" * 121},
    {"largura": 0},
    {"altura": -1},
])
def test_restricoes_das_imagens(conta, dono, campos):
    with pytest.raises(IntegrityError):
        _imagem(dono, conta["conta"]["id"], **campos)


def test_imagens_validas(conta, dono):
    c = conta["conta"]["id"]
    _imagem(dono, c, n=1024 * 1024, chave="a" * 40)
    _imagem(dono, c, n=10, chave="d" * 40, nome=None, largura=None, altura=None)
    assert sql(dono, "select count(*) from imagens where uso = 'banco'")[0][0] == 2


@pytest.mark.parametrize("campos", [
    {"tipo": "newsletter"},
    {"situacao": "entregue"},
    {"situacao": "falhou", "erro": None},  # falhou sempre com o erro
    {"situacao": "enviado", "erro": "x"},  # e o erro só com falhou
    {"situacao": "falhou", "erro": ""},
    {"assunto": "x" * 301},
    {"assunto": None},
    {"para": ""},
])
def test_restricoes_dos_emails_enviados(conta, dono, campos):
    valores = {"tipo": "convite", "para": "a@b.com", "assunto": "Oi", "situacao": "enviado", "erro": None, **campos}
    with pytest.raises(IntegrityError):
        sql(dono, EMAIL, c=conta["conta"]["id"], **valores)


def test_exclusao_da_conta_leva_os_emails(conta, dono):
    c = conta["conta"]["id"]
    assert sql(dono, "select count(*) from emails_enviados where conta_id = :c", c=c)[0][0] == 1  # a confirmação
    sql(dono, "delete from contas where id = :c", c=c)
    assert sql(dono, "select count(*) from emails_enviados")[0][0] == 0


def test_descer_e_subir_a_0014(client, conta, dono):
    h, c = conta["h"], conta["conta"]["id"]
    logo = client.put(f"{API}/conta/logo", headers=h, files={"arquivo": ("l.png", png(9), "image/png")})
    assert logo.status_code == 200
    img = client.post(f"{API}/imagens", headers=h, files={"arquivo": ("t.png", png(1), "image/png")}).json()
    assert client.put(f"{API}/envios/configuracao", headers=h, json={
        "email_imagem_topo_id": img["id"], "email_cor": "#047857", "email_assinatura": "Time Alfa"}).status_code == 200
    cfg = _alembic()
    command.downgrade(cfg, "0013_ia_sob_demanda")
    try:
        assert _objeto(dono, "emails_enviados") is None and _objeto(dono, "imagens_banco_idx") is None
        assert not COLUNAS_CONFIG & _colunas(dono, "config_envios")
        assert not COLUNAS_IMAGENS & _colunas(dono, "imagens")
        assert sql(dono, "select uso from imagens") == [("logo_conta",)]  # o banco some; o logo fica
        with pytest.raises(IntegrityError):  # 'banco' não vale mais
            sql(dono, "insert into imagens (conta_id, uso, chave, tipo, dados, tamanho, sha256) values "
                      "(:c, 'banco', :k, 'image/png', decode('00', 'hex'), 1, repeat('0', 64))", c=c, k="e" * 40)
    finally:
        command.upgrade(cfg, "head")
    assert COLUNAS_CONFIG <= _colunas(dono, "config_envios") and COLUNAS_IMAGENS <= _colunas(dono, "imagens")
    # os padrões voltam e a aplicação volta a usar tudo (permissões do papel da aplicação na tabela nova)
    d = client.get(f"{API}/envios/configuracao", headers=h).json()
    assert (d["email_cor"], d["email_mostrar_logo"], d["email_imagem_topo"], d["email_assinatura"]) == (
        None, True, None, None)
    assert client.get(f"{API}/imagens", headers=h).json()["itens"] == []
    assert client.post(f"{API}/envios/configuracao/teste", headers=h).status_code == 200
    assert [i["tipo"] for i in client.get(f"{API}/auditoria/emails", headers=h).json()["itens"]] == ["teste"]
    assert client.post(f"{API}/imagens", headers=h, files={"arquivo": ("t.png", png(2), "image/png")}
                       ).status_code == 201
