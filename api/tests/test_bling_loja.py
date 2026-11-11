"""Instalação do Toqqi pela loja do Bling (Central de Extensões): a volta sem o `state` do Toqqi troca o código na hora,
guarda a instalação (24 h, só o hash) e leva a /conectar/bling; quem entra como administrador liga à conta, uma vez só.
Também: a mesma empresa do Bling não liga em duas contas, o Plano Grátis fica de fora, a limpeza apaga as vencidas."""
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from test_etapa5j_bling import admin, falso  # noqa: F401 - fixtures
from util import API, conta_pronta, fixar_relogio, membro, sql

from toqqi import tarefas
from toqqi.core import relogio
from toqqi.modulos.conectores import bling


def _da_loja(client, **params):
    r = client.get(f"{API}/publico/conectores/bling/retorno", params=params, follow_redirects=False)
    assert r.status_code == 303
    url = urlparse(r.headers["location"])
    return url.path, parse_qs(url.query)


def test_volta_da_loja_guarda_a_instalacao_e_liga_a_conta(client, dono, admin, falso):  # noqa: F811
    caminho, q = _da_loja(client, code="c1")  # sem state: começou no Bling
    assert caminho == "/conectar/bling" and len(q["instalacao"][0]) >= 40
    codigo = q["instalacao"][0]
    (hash_, cifrado, empresa), = sql(dono, "select codigo_hash, tokens_cifrado, empresa_bling from bling_instalacoes")
    assert codigo not in hash_ and "a1" not in cifrado and empresa == "emp-123"
    h = admin["h"]
    gestor = membro(client, h, "gil@alfa.com.br", perfil="gestor")
    url = f"{API}/integracoes/conectores/bling/instalacao"
    assert client.post(url, headers=gestor["h"], json={"instalacao": codigo}).status_code == 403
    r = client.post(url, headers=h, json={"instalacao": codigo})
    assert r.status_code == 200, r.text
    assert r.json()["conectado"] and r.json()["pesquisar_ao_faturar"]
    assert sql(dono, "select opcoes->>'empresa_bling' from conectores where provedor = 'bling'") == [("emp-123",)]
    assert sql(dono, "select count(*) from bling_instalacoes")[0][0] == 0
    assert sql(dono, "select detalhe->>'origem' from auditoria where evento = 'conector_ligado'") == [("loja",)]
    r = client.post(url, headers=h, json={"instalacao": codigo})  # uma vez só
    assert r.status_code == 404 and r.json()["erro"]["codigo"] == "instalacao_vencida"


def test_negou_ou_falhou_na_loja(client, dono, falso, monkeypatch):  # noqa: F811
    assert _da_loja(client) == ("/conectar/bling", {"resultado": ["negado"]})

    def falha(codigo):
        raise bling.ErroBling("O Bling recusou a autorização. Conecte de novo.")

    monkeypatch.setattr(bling, "trocar_codigo", falha)
    assert _da_loja(client, code="c1", state="qualquer") == ("/conectar/bling", {"resultado": ["erro"]})
    assert sql(dono, "select count(*) from bling_instalacoes")[0][0] == 0


def test_a_mesma_empresa_do_bling_passa_para_a_conta_que_autorizou(client, dono, admin, falso):  # noqa: F811
    _, q = _da_loja(client, code="c1")
    assert client.post(f"{API}/integracoes/conectores/bling/instalacao", headers=admin["h"],
                       json={"instalacao": q["instalacao"][0]}).json()["movido"] is False
    beto = conta_pronta(client, "beto@beta.com.br", empresa="Beta")
    _, q = _da_loja(client, code="c2")
    r = client.post(f"{API}/integracoes/conectores/bling/instalacao", headers=beto["h"],
                    json={"instalacao": q["instalacao"][0]})
    assert r.status_code == 200 and r.json()["conectado"] and r.json()["movido"] is True
    assert sql(dono, "select conta_id from conectores where provedor = 'bling'") == [(beto["conta"]["id"],)]
    (motivo,), = sql(dono, "select detalhe->>'motivo' from auditoria where evento = 'conector_desligado' "
                           "and conta_id = :c", c=admin["conta"]["id"])
    assert motivo == "A empresa do Bling foi conectada a outra conta do Toqqi."
    assert client.get(f"{API}/integracoes/conectores", headers=admin["h"]).json()["bling"]["conectado"] is False
    # pelo Toqqi (com state): volta com resultado=movido e a conexão vai para a conta que autorizou
    url = client.post(f"{API}/integracoes/conectores/bling/autorizar", headers=admin["h"]).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    caminho, q = _da_loja(client, code="c3", state=state)
    assert caminho == "/integracoes" and q["resultado"] == ["movido"]
    assert sql(dono, "select conta_id from conectores where provedor = 'bling'") == [(admin["conta"]["id"],)]
    # de novo na mesma conta: só "ok"
    url = client.post(f"{API}/integracoes/conectores/bling/autorizar", headers=admin["h"]).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    assert _da_loja(client, code="c4", state=state)[1]["resultado"] == ["ok"]


def test_plano_gratis_nao_liga(client, dono, admin, falso):  # noqa: F811
    _, q = _da_loja(client, code="c1")
    sql(dono, "update contas set situacao = 'gratis', gratis_desde = now(), gratis_motivo = 'teste' where id = :c",
        c=admin["conta"]["id"])
    r = client.post(f"{API}/integracoes/conectores/bling/instalacao", headers=admin["h"],
                    json={"instalacao": q["instalacao"][0]})
    assert r.status_code == 403 and r.json()["erro"]["codigo"] == "recurso_do_plano"


def test_vence_em_24_horas_e_a_limpeza_apaga(client, dono, admin, falso, monkeypatch):  # noqa: F811
    _, q = _da_loja(client, code="c1")
    depois = relogio.agora() + timedelta(hours=24, minutes=1)
    fixar_relogio(monkeypatch, depois)
    r = client.post(f"{API}/integracoes/conectores/bling/instalacao", headers=admin["h"],
                    json={"instalacao": q["instalacao"][0]})
    assert r.status_code == 404
    assert tarefas.limpeza()["bling_instalacoes_apagadas"] == 1
    assert sql(dono, "select count(*) from bling_instalacoes")[0][0] == 0


@pytest.mark.parametrize("codigo", ["curto", "x" * 101])
def test_codigo_invalido(client, admin, codigo):  # noqa: F811
    assert client.post(f"{API}/integracoes/conectores/bling/instalacao", headers=admin["h"],
                       json={"instalacao": codigo}).status_code == 422


# ---- teste de homologação (Plataforma, superadmin) ------------------------------------------------------------------

class _Resp:
    def __init__(self, status, corpo=None, hash_=None):
        import json as _json
        self.status_code, self._corpo = status, corpo
        self.content = _json.dumps(corpo).encode() if corpo is not None else b""
        self.headers = {"x-bling-homologacao": hash_} if hash_ else {}

    def json(self):
        return self._corpo


def test_homologacao_roda_os_5_passos_com_o_hash_e_renova_o_token(client, dono, falso, monkeypatch):  # noqa: F811
    from test_etapa5j_bling import _conectar
    from toqqi.core.config import config

    monkeypatch.setattr(config(), "SUPERADMIN_EMAILS", "marcelo@toqqi.com")
    m = conta_pronta(client, "marcelo@toqqi.com", empresa="Toqqi")
    rota = f"{API}/plataforma/bling/homologacao"
    r = client.post(rota, headers=m["h"])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "bling_desconectado"
    _conectar(client, m["h"])
    pedidos = []
    respostas = iter([
        _Resp(200, {"data": {"nome": "Copo do Bling", "codigo": "COD"}}, "h1"),
        _Resp(201, {"data": {"id": 555}}, "h2"),
        _Resp(401, {"error": {"type": "invalid_token"}}),  # o Bling invalida o token no PUT
        _Resp(200, {"data": {}}, "h3"),
        _Resp(204, None, "h4"),
        _Resp(204, None, "h5"),
    ])

    def pedir(metodo, url, json=None, headers=None, timeout=None):
        pedidos.append((metodo, url.split("/Api/v3")[-1], json, headers.get("x-bling-homologacao"),
                        headers["Authorization"]))
        return next(respostas)

    import httpx
    monkeypatch.setattr(httpx, "request", pedir)
    r = client.post(rota, headers=m["h"])
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["ok"] is True and corpo["erro"] is None
    assert [p["metodo"] for p in corpo["passos"]] == ["GET", "POST", "PUT", "PATCH", "DELETE"]
    assert [p["renovou"] for p in corpo["passos"]] == [False, False, True, False, False]
    assert [(p[0], p[1], p[3]) for p in pedidos] == [
        ("GET", "/homologacao/produtos", None), ("POST", "/homologacao/produtos", "h1"),
        ("PUT", "/homologacao/produtos/555", "h2"), ("PUT", "/homologacao/produtos/555", "h2"),
        ("PATCH", "/homologacao/produtos/555/situacoes", "h3"), ("DELETE", "/homologacao/produtos/555", "h4")]
    assert pedidos[1][2] == {"nome": "Copo do Bling", "codigo": "COD"}  # o POST leva o que o GET devolveu
    assert pedidos[2][2]["nome"] == "Copo" and pedidos[4][2] == {"situacao": "I"}
    assert pedidos[2][4] == "Bearer a1" and pedidos[3][4] == "Bearer a2"  # repetiu com o token renovado
    assert falso["renovou"] == 1
    assert sql(dono, "select count(*) from auditoria where evento = 'bling_homologacao'")[0][0] == 1


def test_homologacao_para_no_erro_e_so_superadmin(client, admin, falso, monkeypatch):  # noqa: F811
    from test_etapa5j_bling import _conectar
    from toqqi.core.config import config

    assert client.post(f"{API}/plataforma/bling/homologacao", headers=admin["h"]).status_code == 403
    monkeypatch.setattr(config(), "SUPERADMIN_EMAILS", "ana@alfa.com.br")
    _conectar(client, admin["h"])
    import httpx
    respostas = iter([_Resp(200, {"data": {"nome": "X"}}, "h1"),
                      _Resp(400, {"error": {"description": "Fora do tempo"}}, "h2")])
    monkeypatch.setattr(httpx, "request", lambda *a, **k: next(respostas))
    corpo = client.post(f"{API}/plataforma/bling/homologacao", headers=admin["h"]).json()
    assert corpo["ok"] is False and [p["status"] for p in corpo["passos"]] == [200, 400]
    assert corpo["erro"] == "2. Criar o produto: o Bling respondeu 400. Fora do tempo"
