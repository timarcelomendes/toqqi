"""Registros de acesso (etapa 5f, Marco Civil art. 15): cada evento com o IP resolvido, o que não entra, ficam depois de
excluir o usuário e a conta, RLS (em conta não lê nem a própria linha, não grava com outra conta, UPDATE não muda nada)
e a limpeza de 184 dias."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from util import (
    API,
    SENHA,
    cadastrar,
    conta_pronta,
    criar_contato,
    entrar,
    form_padrao,
    link_pesquisa,
    membro,
    responder_link,
    sql,
    token_do_email,
)

from toqqi.core import acessos
from toqqi.core.db import em_conta


def _registros(dono) -> list[tuple]:
    return sql(dono, "select evento, conta_id, usuario_id, item_id, ip from registros_acesso order by id")


def _de(client, ip: str) -> TestClient:
    return TestClient(client.app, client=(ip, 41234))


def test_entradas_cadastro_e_tentativas(client, dono):
    with _de(client, "203.0.113.10") as c:
        cadastrar(c, "ana@alfa.com.br", empresa="Alfa")
        ((conta_id, usuario_id),) = sql(dono, "select conta_id, id from usuarios")
        assert _registros(dono) == [("cadastro", conta_id, usuario_id, None, "203.0.113.10")]
        # e-mail não confirmado: tentativa
        assert entrar(c, "ana@alfa.com.br").status_code == 403
        c.post(f"{API}/auth/confirmar-email", json={"token": token_do_email("ana@alfa.com.br", "confirmar-email")})
        assert entrar(c, "ana@alfa.com.br", senha="Errada@123").status_code == 401  # senha errada
        assert entrar(c, "ninguem@alfa.com.br").status_code == 401  # e-mail desconhecido: sem conta nem usuário
        assert entrar(c, "ana@alfa.com.br").status_code == 200
    assert _registros(dono)[1:] == [
        ("login_falhou", conta_id, usuario_id, None, "203.0.113.10"),
        ("login_falhou", conta_id, usuario_id, None, "203.0.113.10"),
        ("login_falhou", None, None, None, "203.0.113.10"),
        ("login", conta_id, usuario_id, None, "203.0.113.10"),
    ]
    # o e-mail digitado nunca vai para a tabela (nem há coluna para ele)
    assert "ninguem" not in str(sql(dono, "select * from registros_acesso"))


def test_bloqueado_pendente_pedido_e_senha_pelo_link(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    c = a["conta"]["id"]
    m = membro(client, a["h"], "caio@alfa.com.br")
    client.patch(f"{API}/equipe/{m['usuario']['id']}", headers=a["h"], json={"situacao": "bloqueado"})
    sql(dono, "delete from registros_acesso")
    assert entrar(client, "caio@alfa.com.br").status_code == 403
    assert _registros(dono) == [("login_falhou", c, m["usuario"]["id"], None, "testclient")]
    # pedido de acesso (domínio liberado) cria o usuário pendente
    assert client.put(f"{API}/conta/seguranca", headers=a["h"],
                      json={"sessao_minutos": 60, "dominios": ["alfa.com.br"]}).status_code == 200
    sql(dono, "delete from registros_acesso")
    with _de(client, "198.51.100.7") as outro:
        r = outro.post(f"{API}/auth/pedir-acesso", json={"nome": "Dora", "email": "dora@alfa.com.br", "senha": SENHA})
        assert r.status_code == 200, r.text
        dora = sql(dono, "select id from usuarios where email = 'dora@alfa.com.br'")[0][0]
        assert entrar(outro, "dora@alfa.com.br").status_code == 403  # não confirmado / pendente
        outro.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"})
        token = token_do_email("ana@alfa.com.br", "redefinir-senha")
        assert outro.post(f"{API}/auth/redefinir-senha", json={"token": token, "senha": "Nova@1234"}).status_code == 200
    assert _registros(dono) == [("pedido_acesso", c, dora, None, "198.51.100.7"),
                                ("login_falhou", c, dora, None, "198.51.100.7"),
                                ("senha_redefinida", c, a["usuario"]["id"], None, "198.51.100.7")]


def test_respostas_e_indicacao_publicas(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    c = a["conta"]["id"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=c)
    k = criar_contato(client, a["h"], nome="Carla", email="carla@um.com.br")
    f = form_padrao(client, a["h"])
    assert client.put(f"{API}/crescimento/configuracao", headers=a["h"],
                      json={"indicacoes_ativas": True}).status_code == 200
    sql(dono, "delete from registros_acesso")
    token = link_pesquisa(client, a["h"], k["id"], formulario_id=f["id"])
    with _de(client, "2001:db8::abcd") as outro:
        assert outro.get(f"{API}/publico/convites/{token}").status_code == 200  # abrir não entra
        r = outro.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {f["perguntas"][0]["id"]: 10}})
        assert r.status_code == 201, r.text
        r = outro.post(f"{API}/publico/convites/{token}/indicacoes",
                       json={"nome": "Fulano", "telefone": "11988887777", "pode_identificar": True,
                             "confirmo": True})
        assert r.status_code == 201, r.text
    resposta = sql(dono, "select id from respostas")[0][0]
    indicacao = sql(dono, "select id from indicacoes")[0][0]
    responder_link(client, f["codigo_publico"], {f["perguntas"][0]["id"]: 8}, ip="192.0.2.55")
    link = sql(dono, "select id from respostas where convite_id is null")[0][0]
    assert _registros(dono) == [("resposta", c, None, resposta, "2001:db8::abcd"),
                                ("indicacao", c, None, indicacao, "2001:db8::abcd"),
                                ("resposta", c, None, link, "192.0.2.55")]


def test_ficam_depois_de_excluir_usuario_e_conta(client, dono, monkeypatch):
    from toqqi.core.config import config

    monkeypatch.setattr(config(), "SUPERADMIN_EMAILS", "root@toqqi.com")
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    m = membro(client, a["h"], "caio@alfa.com.br")
    assert client.delete(f"{API}/equipe/{m['usuario']['id']}", headers=a["h"]).status_code == 204
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    antes = sql(dono, "select count(*) from registros_acesso where conta_id = :c", c=a["conta"]["id"])[0][0]
    assert antes >= 3
    r = client.request("DELETE", f"{API}/plataforma/contas/{a['conta']['id']}", headers=root["h"],
                       json={"confirmar_nome": "Alfa"})
    assert r.status_code == 204, r.text
    assert sql(dono, "select count(*) from contas where id = :c", c=a["conta"]["id"])[0][0] == 0
    assert sql(dono, "select count(*) from registros_acesso where conta_id = :c", c=a["conta"]["id"])[0][0] == antes
    assert sql(dono, "select count(*) from registros_acesso where usuario_id = :u", u=m["usuario"]["id"])[0][0] >= 1


def test_rls(client, dono, app_engine):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    c = a["conta"]["id"]
    with em_conta(c) as s:  # em conta, nem a própria linha aparece
        assert s.scalar(text("select count(*) from registros_acesso")) == 0
        acessos.registrar(s, "login", conta_id=c, usuario_id=a["usuario"]["id"])  # grava
    with pytest.raises(DBAPIError):  # com outra conta, não grava
        with em_conta(c) as s:
            acessos.registrar(s, "login", conta_id=b["conta"]["id"])
    with em_conta(c) as s:  # UPDATE e DELETE não mudam nada (sem privilégio de UPDATE; DELETE só em modo sistema)
        with pytest.raises(DBAPIError):
            with s.begin_nested():
                s.execute(text("update registros_acesso set ip = 'x'"))
        assert s.execute(text("delete from registros_acesso")).rowcount == 0
    assert sql(dono, "select count(*) from registros_acesso where ip = 'x'")[0][0] == 0
    assert sql(dono, "select count(*) from registros_acesso where conta_id = :c", c=c)[0][0] >= 3


def test_limpeza_de_184_dias(client, dono, monkeypatch):
    conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    sql(dono, "delete from registros_acesso")
    agora = datetime.now(timezone.utc)
    for dias in (185, 200, 400, 183):
        sql(dono, "insert into registros_acesso (evento, criado_em, ip) values ('login', :t, '203.0.113.1')",
            t=agora - timedelta(days=dias))
    monkeypatch.setattr(acessos, "LOTE_LIMPEZA", 2)  # vários lotes
    assert acessos.limpar() == 3
    assert sql(dono, "select count(*) from registros_acesso")[0][0] == 1
    assert acessos.limpar() == 0
