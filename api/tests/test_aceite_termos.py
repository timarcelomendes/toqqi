"""Aceite dos Termos de uso e da Política de privacidade (LGPD): /eu, POST /eu/aceite, cadastro, versão nova, RLS e
limite por usuário."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from util import API, auth, conta_pronta, entrar, membro, sql

from toqqi.core.rate_limit import limiter
from toqqi.modulos.acesso import termos

UA = "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0 Safari/537.36"
V = termos.VERSAO_DOCUMENTOS  # a versão atual (a seguinte, V + 1, faz o papel de "versão nova")


def _aceite(client, h) -> dict:
    r = client.get(f"{API}/eu", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["usuario"]["aceite"]


def _aceitar(client, h, versao: int = V, ua: str | None = UA):
    headers = {**h, "User-Agent": ua} if ua else h
    return client.post(f"{API}/eu/aceite", headers=headers, json={"versao": versao})


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


@pytest.fixture
def gestor(client, admin):
    """Membro criado pelo admin: não passou pelo cadastro, então ainda não aceitou."""
    return membro(client, admin["h"], "gil@alfa.com.br", "gestor")


VERSAO_TS = Path(__file__).resolve().parents[2] / "web" / "src" / "modulos" / "geral" / "legal" / "versao.ts"


def test_versao_igual_a_do_site():
    achou = re.search(r"VERSAO_DOCUMENTOS = (\d+)", VERSAO_TS.read_text(encoding="utf-8"))
    assert achou, f"VERSAO_DOCUMENTOS não encontrada em {VERSAO_TS}"
    assert int(achou.group(1)) == termos.VERSAO_DOCUMENTOS


def test_eu_sem_aceite_fica_pendente(client, gestor):
    assert _aceite(client, gestor["h"]) == {"versao_atual": V, "versao_aceita": None, "aceito_em": None,
                                            "pendente": True, "revogado_em": None}
    assert gestor["usuario"]["aceite"]["pendente"] is True  # a resposta de entrar já traz o aceite


def test_aceitar_grava_e_tira_a_pendencia(client, gestor, dono):
    r = _aceitar(client, gestor["h"])
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["versao_atual"] == V and corpo["versao_aceita"] == V and corpo["pendente"] is False
    assert corpo["aceito_em"]
    assert _aceite(client, gestor["h"]) == corpo
    (linha,) = sql(dono, "select usuario_id, usuario_email, usuario_nome, conta_id, versao, ip, agente, origem "
                         "from aceites_termos where usuario_id = :u", u=gestor["usuario"]["id"])
    assert linha.versao == V and linha.origem == "tela" and linha.conta_id == gestor["conta"]["id"]
    assert (linha.usuario_email, linha.usuario_nome) == ("gil@alfa.com.br", "Membro gestor")
    assert linha.ip == "testclient" and linha.agente == UA
    (aud,) = sql(dono, "select detalhe, usuario_id from auditoria where evento = 'termos_aceitos' and usuario_id = :u",
                 u=gestor["usuario"]["id"])
    assert aud.detalhe == {"versao": V}
    # entrar de novo: a resposta já vem sem pendência
    assert entrar(client, "gil@alfa.com.br").json()["usuario"]["aceite"]["pendente"] is False


def test_aceitar_de_novo_e_idempotente(client, gestor, dono):
    primeiro = _aceitar(client, gestor["h"]).json()
    segundo = _aceitar(client, gestor["h"], ua="Outro navegador").json()
    assert segundo == primeiro
    u = gestor["usuario"]["id"]
    assert sql(dono, "select count(*), max(agente) from aceites_termos where usuario_id = :u", u=u)[0] == (1, UA)
    assert sql(dono, "select count(*) from auditoria where evento = 'termos_aceitos' and usuario_id = :u",
               u=u)[0][0] == 1


def test_agente_longo_e_cortado_em_400(client, gestor, dono):
    assert _aceitar(client, gestor["h"], ua="x" * 1000).status_code == 200
    assert sql(dono, "select length(agente) from aceites_termos where usuario_id = :u",
               u=gestor["usuario"]["id"])[0][0] == 400


def test_versao_errada_da_409(client, gestor, dono):
    r = _aceitar(client, gestor["h"], versao=V + 1)
    assert r.status_code == 409
    assert r.json()["erro"]["codigo"] == "versao_desatualizada"
    assert r.json()["erro"]["mensagem"] == "Os termos foram atualizados. Recarregue a página para ver a versão nova."
    for invalida in (0, -1):  # versão 0 ou negativa: validação (422), não 409
        r = _aceitar(client, gestor["h"], versao=invalida)
        assert r.status_code == 422 and r.json()["erro"]["campos"].keys() >= {"versao"}, r.text
    assert sql(dono, "select count(*) from aceites_termos where usuario_id = :u", u=gestor["usuario"]["id"])[0][0] == 0
    assert _aceite(client, gestor["h"])["pendente"] is True


def test_cadastro_grava_o_aceite(client, admin, dono):
    assert admin["usuario"]["aceite"]["pendente"] is False  # entrar
    a = _aceite(client, admin["h"])
    assert a["versao_aceita"] == V and a["pendente"] is False and a["aceito_em"]
    (linha,) = sql(dono, "select conta_id, versao, ip, origem from aceites_termos where usuario_id = :u",
                   u=admin["usuario"]["id"])
    assert (linha.conta_id, linha.versao, linha.origem) == (admin["conta"]["id"], V, "cadastro") and linha.ip
    (aud,) = sql(dono, "select detalhe, conta_id from auditoria where evento = 'termos_aceitos'")
    assert aud.detalhe == {"versao": V, "origem": "cadastro"} and aud.conta_id == admin["conta"]["id"]
    # aceitar pela tela depois do cadastro não grava de novo
    assert _aceitar(client, admin["h"]).json() == a
    assert sql(dono, "select count(*) from aceites_termos")[0][0] == 1


def test_versao_nova_volta_a_pedir_o_aceite(client, admin, dono, monkeypatch):
    monkeypatch.setattr(termos, "VERSAO_DOCUMENTOS", V + 1)
    a = _aceite(client, admin["h"])
    assert (a["versao_atual"], a["versao_aceita"], a["pendente"]) == (V + 1, V, True)
    assert _aceitar(client, admin["h"], versao=V).status_code == 409
    r = _aceitar(client, admin["h"], versao=V + 1)
    assert r.status_code == 200 and r.json()["versao_aceita"] == V + 1 and r.json()["pendente"] is False
    versoes = sql(dono, "select versao, origem from aceites_termos where usuario_id = :u order by versao",
                  u=admin["usuario"]["id"])
    assert [tuple(x) for x in versoes] == [(V, "cadastro"), (V + 1, "tela")]  # o histórico fica


def test_superadmin_aceita_como_qualquer_usuario(client):
    root = conta_pronta(client, "root@toqqi.com", empresa="Toqqi")
    assert root["usuario"]["superadmin"] is True
    assert _aceitar(client, root["h"]).json()["pendente"] is False


def test_rls_outra_conta_nao_ve(client, admin, gestor, app_engine):
    _aceitar(client, gestor["h"])
    bia = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    ida, idb = admin["conta"]["id"], bia["conta"]["id"]
    with app_engine.connect() as c:  # sem contexto: nada
        assert c.execute(text("select count(*) from aceites_termos")).scalar() == 0
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(idb)})
        assert c.execute(text("select count(*) from aceites_termos")).scalar() == 1  # só o da Bia
        assert c.execute(text("select count(*) from aceites_termos where conta_id = :a"), {"a": ida}).scalar() == 0
        assert c.execute(text("delete from aceites_termos where conta_id = :a"), {"a": ida}).rowcount == 0
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(ida)})
        assert c.execute(text("select count(*) from aceites_termos")).scalar() == 2
    # gravar em nome de um usuário de outra conta: a chave composta (usuario_id, conta_id) recusa
    with pytest.raises(IntegrityError), app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(idb)})
        c.execute(text("insert into aceites_termos (usuario_id, usuario_email, usuario_nome, versao, origem) "
                       "values (:u, 'gil@alfa.com.br', 'Gil', 5, 'tela')"),
                  {"u": gestor["usuario"]["id"]})


def test_tabela_tem_rls_forcado(dono):
    (linha,) = sql(dono, """
        select c.relrowsecurity, c.relforcerowsecurity, array_agg(p.polname)
          from pg_class c join pg_policy p on p.polrelid = c.oid
         where c.relname = 'aceites_termos' group by 1, 2
    """)
    assert tuple(linha) == (True, True, ["isolamento_conta"])


def test_sem_login_401(client):
    r = client.post(f"{API}/eu/aceite", json={"versao": 1})
    assert r.status_code == 401 and r.json()["erro"]["codigo"] == "sessao_invalida"
    assert client.post(f"{API}/eu/aceite", headers=auth("lixo"), json={"versao": 1}).status_code == 401


def test_limite_20_por_minuto_por_usuario(client, admin, gestor):
    limiter.enabled = True
    limiter.reset()
    try:
        codigos = [_aceitar(client, gestor["h"]).status_code for _ in range(21)]
        assert codigos == [200] * 20 + [429]
        assert _aceitar(client, gestor["h"]).json()["erro"]["codigo"] == "muitas_tentativas"
        assert _aceitar(client, admin["h"]).status_code == 200  # cada usuário tem o seu limite (mesmo IP)
    finally:
        limiter.enabled = False
        limiter.reset()


def test_limite_nao_conta_token_forjado_com_id_de_outro(client, admin, gestor):
    """Assinatura inválida com o id do gestor: a chave do limite é o IP, não o usuário, e o gestor não é bloqueado."""
    limiter.enabled = True
    limiter.reset()
    try:
        forjado = jwt.encode({"sub": str(gestor["usuario"]["id"]), "cid": gestor["conta"]["id"],
                              "sid": "00000000-0000-0000-0000-000000000000",
                              "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())},
                             "outro-segredo-qualquer-com-tamanho-suficiente", algorithm="HS256")
        for _ in range(25):
            client.post(f"{API}/eu/aceite", headers=auth(forjado), json={"versao": 1})
        assert _aceitar(client, gestor["h"]).status_code == 200
    finally:
        limiter.enabled = False
        limiter.reset()


def test_patch_eu_devolve_o_aceite(client, admin):
    r = client.patch(f"{API}/eu", headers=admin["h"], json={"cargo": "Diretora"})
    assert r.status_code == 200, r.text
    assert r.json()["cargo"] == "Diretora"
    assert r.json()["aceite"] == _aceite(client, admin["h"])
    assert r.json()["aceite"]["pendente"] is False


def test_remover_membro_mantem_a_prova_do_aceite(client, admin, gestor, dono):
    assert _aceitar(client, gestor["h"]).status_code == 200
    gid = gestor["usuario"]["id"]
    assert client.delete(f"{API}/equipe/{gid}", headers=admin["h"]).status_code == 204
    assert sql(dono, "select count(*) from usuarios where id = :u", u=gid)[0][0] == 0
    (linha,) = sql(dono, "select usuario_id, usuario_email, usuario_nome, versao, origem, conta_id "
                         "from aceites_termos where usuario_email = 'gil@alfa.com.br'")
    assert linha.usuario_id is None and linha.usuario_nome == "Membro gestor"
    assert (linha.versao, linha.origem, linha.conta_id) == (V, "tela", admin["conta"]["id"])
    # o aceite do admin (cadastro) não é afetado
    assert _aceite(client, admin["h"])["pendente"] is False
