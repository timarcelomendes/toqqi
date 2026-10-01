"""Migração 0005 (respostas e planos de ação): volta para a 0004 e sobe de novo, preenchendo origem e temas das
respostas que já existiam."""
from datetime import datetime

import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from util import FUSO, conta_pronta, criar_contato, criar_form, link_pesquisa, registrar_resposta, sql

from alembic import command
from toqqi.core.db import RAIZ_API

API = "/api/v1"
pytestmark = pytest.mark.usefixtures("relogio_estavel")


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono, tabela: str) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = :t", t=tabela)}


def test_descer_e_subir_a_0005(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h = a["h"]
    c = criar_contato(client, h, nome="Paula")
    manual = registrar_resposta(client, h, c["id"], 3, canal="telefone", comentario="O frete atrasou",
                                data="2025-01-10").json()
    f = criar_form(client, h, [{"tipo": "nps", "titulo": "Nota", "obrigatoria": True},
                               {"tipo": "comentario", "titulo": "Fale do atendimento"},
                               {"tipo": "comentario", "titulo": "Algo sobre o frete?"}])
    p = [x["id"] for x in f["perguntas"]]
    token = link_pesquisa(client, h, c["id"], formulario_id=f["id"])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {p[0]: 9, p[1]: "Ótimo",
                                                                                  p[2]: "Nada a dizer"}})
    (pesquisa, comentario), = sql(dono, "select id, comentario from respostas where formulario_id = :f", f=f["id"])
    g = criar_form(client, h, [{"tipo": "nps", "titulo": "Nota", "obrigatoria": True},
                               {"tipo": "escolha_multipla", "titulo": "O que pesou?",
                                "opcoes": ["Prazo de entrega", "Mix de produtos"]},
                               {"tipo": "comentario", "titulo": "Conte mais"},
                               {"tipo": "texto_curto", "titulo": "Seu e-mail", "formato": "email"}], nome="Outra")
    q = [x["id"] for x in g["perguntas"]]
    token = link_pesquisa(client, h, c["id"], formulario_id=g["id"])
    client.post(f"{API}/publico/convites/{token}/responder",
                json={"respostas": {q[0]: 4, q[1]: ["Prazo de entrega"], q[2]: "Bom | mas caro", q[3]: "p@x.com.br"}})
    (outra,), = sql(dono, "select id from respostas where formulario_id = :f", f=g["id"])
    assert comentario == "Fale do atendimento: Ótimo | Algo sobre o frete? Nada a dizer"
    assert sql(dono, "select temas from respostas where id = :r", r=pesquisa)[0][0] == []  # títulos não contam
    (importada,), = sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, canal, origem, nota, tipo_nota, grupo, comentario,
                               respondida_em)
        values (:c, :f, :k, 'importacao', 'importacao', 10, 'nps', 'promotor', 'Vendedor muito educado',
                '2024-06-01 12:00-03') returning id
    """, c=a["conta"]["id"], f=f["id"], k=c["id"])
    client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": ("r.csv", b"email;data;nota\r\nx;1;1\r\n")},
                data={"tipo": "respostas"})
    assert sql(dono, "select count(*) from acoes")[0][0] == 2  # as das notas 3 e 4

    cfg = _alembic()
    command.downgrade(cfg, "0004_integracoes")
    try:
        assert sql(dono, "select to_regclass('acoes'), to_regclass('config_acoes')")[0] == (None, None)
        assert not {"origem", "temas", "data_resposta", "respondida_em"} & _colunas(dono, "respostas")
        assert "tipo" not in _colunas(dono, "importacoes")
        assert sql(dono, "select count(*) from importacoes")[0][0] == 0  # análise de respostas sai
        canal, criada = sql(dono, "select canal, criada_em from respostas where id = :r", r=manual["id"])[0]
        assert canal == "manual" and criada == datetime(2025, 1, 10, 12, tzinfo=FUSO)  # a data informada fica
        assert sql(dono, "select canal from respostas where id = :r", r=importada)[0][0] == "importacao"
        # dado antigo, como se viesse da etapa 3: depois da subida ganha origem e temas
        sql(dono, "update respostas set comentario = 'Liguei: o boleto veio errado' where id = :r", r=manual["id"])
    finally:
        command.upgrade(cfg, "head")
    linhas = {r: (origem, temas, respondida, data) for r, origem, temas, respondida, data in sql(
        dono, "select id, origem, temas, respondida_em, data_resposta from respostas")}
    assert linhas[manual["id"]][:3] == ("manual", ["preco_condicoes"], None)
    assert linhas[manual["id"]][3] == datetime(2025, 1, 10, 12, tzinfo=FUSO)
    assert linhas[importada][:2] == ("importacao", ["atendimento"])
    assert linhas[pesquisa][:2] == ("pesquisa", [])
    # comentário do cliente: nas de pesquisa, só as perguntas de comentário (lidas das respostas, com " | " no
    # texto); nas outras, o comentário. Temas: esse texto e as opções marcadas (o "Seu e-mail" não conta)
    assert linhas[outra][:2] == ("pesquisa", ["prazo_entrega", "preco_condicoes"])
    clientes = dict(sql(dono, "select id, comentario_cliente from respostas"))
    assert clientes == {manual["id"]: "Liguei: o boleto veio errado", pesquisa: "Ótimo · Nada a dizer",
                        outra: "Bom | mas caro", importada: "Vendedor muito educado"}
    r = client.get(f"{API}/respostas", headers=h, params={"origem": "manual"}).json()
    assert r["total"] == 1 and r["itens"][0]["canal"] == "manual"
    assert client.get(f"{API}/acoes/configuracao", headers=h).status_code == 200
