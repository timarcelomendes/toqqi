"""Etapa 5j, conector do Bling (o Bling é falso: as funções de `conectores.bling` que falam com a rede são trocadas).
Indisponível sem as credenciais do aplicativo; autorizar → volta com o código (state assinado, de 15 min) → tokens
cifrados e o id da empresa no Bling; sincronização em segundo plano (pula quem já existe sem consultar o detalhe,
inativo e sem contato ficam de fora); aviso assinado de nota emitida → pesquisa uma vez por evento (assinatura errada,
outra empresa e outro evento não fazem nada); token vencido é renovado."""
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

import pytest
from util import API, conta_pronta, form_padrao, ligar_envios, membro, sql

from toqqi.core.config import config
from toqqi.core.email import caixa_memoria
from toqqi.modulos.conectores import bling

SEGREDO_APP = "segredo-do-app-bling"
LISTA = [{"id": 1, "nome": "Mercado Azul", "situacao": "A"}, {"id": 2, "nome": "Padaria Sol", "situacao": "A"},
         {"id": 3, "nome": "Antiga SA", "situacao": "I"}, {"id": 4, "nome": "Sem Contato", "situacao": "A"}]
DETALHES = {"1": {"email": "compras@azul.com.br", "numeroDocumento": "11.222.333/0001-81"},
            "2": {"celular": "(11) 98765-4321"}, "4": {}, "9": {"nome": "Cliente Novo", "email": "novo@cliente.com.br"}}


@pytest.fixture
def falso(monkeypatch):
    monkeypatch.setattr(config(), "BLING_CLIENT_ID", "cliente-toqqi")
    monkeypatch.setattr(config(), "BLING_CLIENT_SECRET", SEGREDO_APP)
    estado = {"detalhes": [], "renovou": 0}
    monkeypatch.setattr(bling, "trocar_codigo", lambda codigo: {"access": "a1", "refresh": "r1",
                                                               "expira": "2099-01-01T00:00:00+00:00"})

    def renovar(refresh):
        estado["renovou"] += 1
        return {"access": "a2", "refresh": "r2", "expira": "2099-01-01T00:00:00+00:00"}

    def contato(tokens, cid):
        estado["detalhes"].append(cid)
        return DETALHES.get(str(cid), {})

    monkeypatch.setattr(bling, "renovar", renovar)
    monkeypatch.setattr(bling, "empresa", lambda tokens: "emp-123")
    monkeypatch.setattr(bling, "contatos", lambda tokens, maximo: iter(LISTA))
    monkeypatch.setattr(bling, "contato", contato)
    monkeypatch.setattr(bling, "PAUSA", 0)
    return estado


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _conectar(client, h) -> None:
    url = client.post(f"{API}/integracoes/conectores/bling/autorizar", headers=h).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    r = client.get(f"{API}/publico/conectores/bling/retorno", params={"code": "c1", "state": state},
                   follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("resultado=ok"), r.headers.get("location")


def _assinado(corpo: dict) -> tuple[bytes, dict]:
    bruto = json.dumps(corpo).encode()
    sig = "sha256=" + hmac.new(SEGREDO_APP.encode(), bruto, hashlib.sha256).hexdigest()
    return bruto, {"X-Bling-Signature-256": sig, "content-type": "application/json"}


def test_indisponivel_sem_credenciais(client, admin):
    r = client.post(f"{API}/integracoes/conectores/bling/autorizar", headers=admin["h"])
    assert r.status_code == 503
    assert client.get(f"{API}/integracoes/conectores", headers=admin["h"]).json()["bling"]["disponivel"] is False


def test_autorizar_e_voltar(client, dono, admin, falso):
    h = admin["h"]
    _conectar(client, h)
    b = client.get(f"{API}/integracoes/conectores", headers=h).json()["bling"]
    assert b["conectado"] and b["pesquisar_ao_faturar"] and b["disponivel"]
    (cifrado, opcoes), = sql(dono, "select token_cifrado, opcoes from conectores where provedor = 'bling'")
    assert "r1" not in cifrado and opcoes["empresa_bling"] == "emp-123"
    r = client.get(f"{API}/publico/conectores/bling/retorno", params={"code": "c1", "state": "falso"},
                   follow_redirects=False)
    assert r.headers["location"].endswith("resultado=erro")
    gestor = membro(client, h, "gil@alfa.com.br", perfil="gestor")
    assert client.post(f"{API}/integracoes/conectores/bling/autorizar", headers=gestor["h"]).status_code == 403


def test_sincronizar_em_segundo_plano(client, dono, admin, falso):
    h = admin["h"]
    _conectar(client, h)
    r = client.post(f"{API}/integracoes/conectores/bling/sincronizar", headers=h)
    assert r.status_code == 202  # o TestClient roda a tarefa ao fim da resposta
    b = client.get(f"{API}/integracoes/conectores", headers=h).json()["bling"]
    assert b["sincronizando"] is False
    assert b["resumo"] == {"empresas_novas": 3, "empresas_existentes": 0, "contatos_novos": 2, "contatos_existentes": 0,
                           "sem_email_ou_telefone": 1, "inativos": 1, "limite_do_plano": False, "cortado": False}
    assert falso["detalhes"] == ["1", "2", "4"]
    client.post(f"{API}/integracoes/conectores/bling/sincronizar", headers=h)
    b = client.get(f"{API}/integracoes/conectores", headers=h).json()["bling"]
    assert b["resumo"]["contatos_existentes"] == 2
    assert falso["detalhes"] == ["1", "2", "4", "4"]  # quem já existe não é consultado de novo


def test_nota_emitida_manda_a_pesquisa(client, dono, admin, falso):
    h = admin["h"]
    form_padrao(client, h)
    ligar_envios(client, h)
    _conectar(client, h)
    aviso = {"eventId": "ev1", "event": "invoice.created", "companyId": "emp-123",
             "data": {"id": 77, "numero": "1001", "contato": {"id": 9}}}
    bruto, cab = _assinado(aviso)
    antes = len(caixa_memoria)
    assert client.post(f"{API}/publico/conectores/bling/aviso", content=bruto, headers=cab).status_code == 200
    assert [m.para for m in caixa_memoria[antes:]] == ["novo@cliente.com.br"]
    client.post(f"{API}/publico/conectores/bling/aviso", content=bruto, headers=cab)  # repetido
    for outro in ({**aviso, "companyId": "outra"}, {**aviso, "event": "order.created", "eventId": "ev2"}):
        client.post(f"{API}/publico/conectores/bling/aviso", content=_assinado(outro)[0], headers=_assinado(outro)[1])
    client.post(f"{API}/publico/conectores/bling/aviso", content=bruto,
                headers={"X-Bling-Signature-256": "sha256=errada", "content-type": "application/json"})
    assert len(caixa_memoria) == antes + 1
    (ref,), = sql(dono, "select referencia from convites")
    assert ref == "Nota 1001"


def test_token_vencido_e_renovado(client, dono, admin, falso, monkeypatch):
    h = admin["h"]
    monkeypatch.setattr(bling, "trocar_codigo", lambda codigo: {"access": "a1", "refresh": "r1",
                                                               "expira": "2000-01-01T00:00:00+00:00"})
    _conectar(client, h)
    client.post(f"{API}/integracoes/conectores/bling/sincronizar", headers=h)
    assert falso["renovou"] == 1
    assert client.delete(f"{API}/integracoes/conectores/bling", headers=h).status_code == 204
    assert sql(dono, "select count(*) from conectores")[0][0] == 0
