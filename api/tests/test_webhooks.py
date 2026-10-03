"""Etapa 3b: webhooks de saída (cadastro, entrega assinada, novas tentativas, desativação, teste, entregas)."""
import hashlib
import hmac
import json
from datetime import timedelta

import httpx
import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    emails_para,
    fixar_relogio,
    form_padrao,
    link_pesquisa,
    membro,
    segunda,
    sql,
)

from toqqi import tarefas
from toqqi.core import rede

URL = "https://erp.cliente.com.br/toqqi"


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def criar(client, h, url=URL, eventos=("resposta.criada", "contato.descadastrado")):
    return client.post(f"{API}/integracoes/webhooks", headers=h, json={"url": url, "eventos": list(eventos)})


def responder(client, h, contato_id: int, **convite):
    nps = form_padrao(client, h)
    token = link_pesquisa(client, h, contato_id, **convite)
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 9}})
    assert r.status_code == 201, r.text


def entregas(client, h, webhook_id):
    r = client.get(f"{API}/integracoes/webhooks/{webhook_id}/entregas", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def conferir_assinatura(recebido: dict, segredo: str) -> None:
    t, v1 = (p.split("=", 1)[1] for p in recebido["cabecalhos"]["X-Toqqi-Assinatura"].split(","))
    esperado = hmac.new(segredo.encode(), f"{t}.".encode() + recebido["corpo"], hashlib.sha256).hexdigest()
    assert hmac.compare_digest(v1, esperado)


# ---- cadastro ---------------------------------------------------------------

@pytest.mark.parametrize("url", ["http://erp.cliente.com.br/x", "https://localhost/x", "https://10.0.0.1/x",
                                 "https://192.168.0.10/x", "https://erp.local/x", "https://user:senha@erp.com.br/x",
                                 "https://erp.cliente.com.br:8443/x", "ftp://erp.com.br"])
def test_url_precisa_ser_https_publica(client, admin, url):
    r = criar(client, admin["h"], url=url)
    assert r.status_code == 422 and "url" in r.json()["erro"]["campos"], url


def test_cadastro_segredo_e_limite(client, admin, dono):
    h = admin["h"]
    r = criar(client, h, eventos=["resposta.criada"])
    assert r.status_code == 201, r.text
    w = r.json()
    assert w["segredo"].startswith("whsec_") and w["segredo_prefixo"] == w["segredo"][:10] + "…"
    assert (w["url"], w["eventos"], w["ativo"], w["ultima_entrega"], w["falhas_seguidas"]) == \
        (URL, ["resposta.criada"], True, None, 0)
    (cifrado,), = sql(dono, "select segredo_cifrado from webhooks")
    assert w["segredo"] not in cifrado
    lista = client.get(f"{API}/integracoes/webhooks", headers=h).json()
    assert len(lista) == 1 and "segredo" not in lista[0]

    novo = client.post(f"{API}/integracoes/webhooks/{w['id']}/novo-segredo", headers=h).json()["segredo"]
    assert novo != w["segredo"]
    assert client.get(f"{API}/integracoes/webhooks", headers=h).json()[0]["segredo_prefixo"] == novo[:10] + "…"

    r = client.patch(f"{API}/integracoes/webhooks/{w['id']}", headers=h,
                     json={"eventos": ["contato.descadastrado"], "ativo": False})
    assert r.status_code == 200 and (r.json()["eventos"], r.json()["ativo"]) == (["contato.descadastrado"], False)
    assert client.patch(f"{API}/integracoes/webhooks/{w['id']}", headers=h,
                        json={"url": "http://x.com.br"}).status_code == 422
    for eventos in ([], ["resposta.apagada"], ["resposta.criada", "resposta.criada"]):
        assert criar(client, h, eventos=eventos).status_code == 422, eventos

    for _ in range(4):
        assert criar(client, h).status_code == 201
    r = criar(client, h)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "limite_webhooks"

    assert client.delete(f"{API}/integracoes/webhooks/{w['id']}", headers=h).status_code == 204
    assert client.delete(f"{API}/integracoes/webhooks/{w['id']}", headers=h).status_code == 404


def test_so_admin_e_so_da_conta(client, admin):
    w = criar(client, admin["h"]).json()
    gestor = membro(client, admin["h"], "gil@alfa.com.br", perfil="gestor")
    assert client.get(f"{API}/integracoes/webhooks", headers=gestor["h"]).status_code == 403
    assert criar(client, gestor["h"]).status_code == 403
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert client.get(f"{API}/integracoes/webhooks", headers=b["h"]).json() == []
    for metodo, caminho in [("patch", ""), ("delete", ""), ("post", "/testar"), ("post", "/novo-segredo"),
                            ("get", "/entregas")]:
        kw = {"json": {"ativo": False}} if metodo == "patch" else {}
        r = getattr(client, metodo)(f"{API}/integracoes/webhooks/{w['id']}{caminho}", headers=b["h"], **kw)
        assert r.status_code == 404, (metodo, caminho)


# ---- entrega ----------------------------------------------------------------

def test_resposta_criada_assinada(client, admin, destino):
    h = admin["h"]
    w = criar(client, h, eventos=["resposta.criada"]).json()
    c = criar_contato(client, h, nome="João Lima", email="joao@cliente.com.br")
    responder(client, h, c["id"], referencia="1234", contexto={"motorista": "Zé"})

    assert len(destino.recebidos) == 1
    rec = destino.recebidos[0]
    assert (rec["url"], rec["ip"], rec["host"]) == (URL, "52.96.1.10", "erp.cliente.com.br")
    conferir_assinatura(rec, w["segredo"])
    corpo = json.loads(rec["corpo"])
    assert rec["cabecalhos"]["X-Toqqi-Evento"] == "resposta.criada"
    assert rec["cabecalhos"]["X-Toqqi-Entrega"] == corpo["id"]
    assert corpo["evento"] == "resposta.criada"
    assert corpo["conta"] == {"id": admin["conta"]["id"], "nome": "Alfa Distribuidora"}
    dados = corpo["dados"]
    assert dados["nota"] == 9 and dados["grupo"] == "promotor" and dados["canal"] == "link"
    assert dados["contato"] == {"id": c["id"], "nome": "João Lima", "email": "joao@cliente.com.br"}
    assert dados["contexto"] == {"motorista": "Zé"} and dados["referencia"] == "1234"
    assert dados["convite"] == {"evento": None, "referencia": "1234"}

    e, = entregas(client, h, w["id"])
    assert (e["id"], e["evento"], e["tentativas"], e["status_http"], e["ok"], e["erro"]) == \
        (corpo["id"], "resposta.criada", 1, 200, True, None)
    ultima = client.get(f"{API}/integracoes/webhooks", headers=h).json()[0]["ultima_entrega"]
    assert ultima["ok"] is True and ultima["status_http"] == 200

    # webhook só do outro evento, ou desligado: nada sai
    client.patch(f"{API}/integracoes/webhooks/{w['id']}", headers=h, json={"ativo": False})
    responder(client, h, c["id"])
    assert len(destino.recebidos) == 1


def test_contato_descadastrado(client, admin, destino):
    h = admin["h"]
    criar(client, h, eventos=["contato.descadastrado"])
    c = criar_contato(client, h, email="maria@cliente.com.br")
    client.post(f"{API}/envios/descadastros", headers=h, json={"email": "maria@cliente.com.br", "motivo": "pediu"})
    corpo = json.loads(destino.recebidos[0]["corpo"])
    assert corpo["evento"] == "contato.descadastrado"
    assert corpo["dados"] == {"email_mascarado": "ma***@cliente.com.br", "contato_id": c["id"], "origem": "manual"}
    # repetir o descadastro não gera outro evento
    client.post(f"{API}/envios/descadastros", headers=h, json={"email": "maria@cliente.com.br"})
    assert len(destino.recebidos) == 1


def test_novas_tentativas_e_desativacao(client, admin, destino, monkeypatch, dono):
    h = admin["h"]
    w = criar(client, h, eventos=["resposta.criada"]).json()
    c = criar_contato(client, h)
    inicio = segunda(9)
    fixar_relogio(monkeypatch, inicio)
    destino.status = 500
    responder(client, h, c["id"])
    e, = entregas(client, h, w["id"])
    assert (e["tentativas"], e["status_http"], e["ok"]) == (1, 500, False)
    assert e["erro"] == "O endereço respondeu com erro (HTTP 500)."

    def rodar(minutos: float) -> dict:
        fixar_relogio(monkeypatch, inicio + timedelta(minutes=minutos))
        return tarefas.executar("webhooks")["webhooks"]

    # 1 min, 5 min, 30 min, 2 h e 6 h depois de cada falha
    assert rodar(0.5) == {"entregues": 0, "falharam": 0}
    assert rodar(1) == {"entregues": 0, "falharam": 1}
    assert rodar(5.5) == {"entregues": 0, "falharam": 0}
    assert rodar(6) == {"entregues": 0, "falharam": 1}
    assert rodar(36) == {"entregues": 0, "falharam": 1}
    assert rodar(156) == {"entregues": 0, "falharam": 1}
    assert rodar(516) == {"entregues": 0, "falharam": 1}
    assert entregas(client, h, w["id"])[0]["tentativas"] == 6
    assert rodar(10000) == {"entregues": 0, "falharam": 0}         # 5 novas tentativas no total: acabou
    assert sql(dono, "select status from webhook_entregas")[0][0] == "falhou"
    assert client.get(f"{API}/integracoes/webhooks", headers=h).json()[0]["falhas_seguidas"] == 6

    # 10 falhas seguidas desativam o webhook e avisam os admins
    fixar_relogio(monkeypatch, inicio + timedelta(days=1))
    for _ in range(3):
        responder(client, h, c["id"])
    assert client.get(f"{API}/integracoes/webhooks", headers=h).json()[0]["ativo"] is True
    responder(client, h, c["id"])  # a 10ª falha
    responder(client, h, c["id"])  # webhook desligado: não entra na fila
    w2 = client.get(f"{API}/integracoes/webhooks", headers=h).json()[0]
    assert (w2["ativo"], w2["falhas_seguidas"]) == (False, 10)
    assert len(entregas(client, h, w["id"])) == 5
    assert sql(dono, "select count(*) from webhook_entregas where status = 'pendente'")[0][0] == 0
    aviso, = emails_para("ana@alfa.com.br")[-1:]
    assert aviso.assunto == "Um webhook da Toqqi foi desativado" and URL in aviso.texto
    # etapa 5e: entra no registro de e-mails enviados da conta, como aviso aos administradores
    assert sql(dono, "select tipo, destinatario, assunto, situacao from emails_enviados where tipo = 'aviso'") == [
        ("aviso", "ana@alfa.com.br", aviso.assunto, "enviado")]
    assert any(a["evento"] == "webhook_desativado"
               for a in client.get(f"{API}/auditoria", headers=h).json()["itens"])

    # religar zera as falhas; um sucesso também
    r = client.patch(f"{API}/integracoes/webhooks/{w['id']}", headers=h, json={"ativo": True})
    assert r.json()["falhas_seguidas"] == 0
    destino.status = 204
    fixar_relogio(monkeypatch, inicio + timedelta(days=1, minutes=1))
    responder(client, h, c["id"])
    assert entregas(client, h, w["id"])[0]["ok"] is True


def test_entrega_recusa_ip_interno_e_falha_de_rede(client, admin, destino, monkeypatch):
    h = admin["h"]
    w = criar(client, h, eventos=["resposta.criada"]).json()
    c = criar_contato(client, h)
    monkeypatch.setattr(rede, "resolver", lambda host: ["10.0.0.5"])  # DNS aponta para dentro
    responder(client, h, c["id"])
    assert destino.recebidos == []
    assert entregas(client, h, w["id"])[0]["erro"] == "O endereço precisa ser público."

    monkeypatch.setattr(rede, "resolver", lambda host: ["52.96.1.10"])

    def estoura(*a):
        raise httpx.ReadTimeout("lento")

    monkeypatch.setattr(rede, "enviar_post", estoura)
    responder(client, h, c["id"])
    assert entregas(client, h, w["id"])[0]["erro"] == "O endereço demorou mais de 10 segundos para responder."


def test_testar(client, admin, destino):
    h = admin["h"]
    w = criar(client, h).json()
    r = client.post(f"{API}/integracoes/webhooks/{w['id']}/testar", headers=h)
    assert r.json() == {"ok": True, "status_http": 200, "mensagem": "O endereço recebeu o teste (HTTP 200)."}
    corpo = json.loads(destino.recebidos[0]["corpo"])
    assert corpo["evento"] == "teste" and corpo["dados"] == {"mensagem": "Teste de webhook da Toqqi."}
    conferir_assinatura(destino.recebidos[0], w["segredo"])
    destino.status = 404
    r = client.post(f"{API}/integracoes/webhooks/{w['id']}/testar", headers=h)
    assert r.json() == {"ok": False, "status_http": 404, "mensagem": "O endereço respondeu com erro (HTTP 404)."}
    destino.status = 302
    r = client.post(f"{API}/integracoes/webhooks/{w['id']}/testar", headers=h)
    assert "redirecionamento" in r.json()["mensagem"]
    # o teste não entra na fila nem conta como falha
    assert entregas(client, h, w["id"]) == []
    assert client.get(f"{API}/integracoes/webhooks", headers=h).json()[0]["falhas_seguidas"] == 0


def test_entregas_dos_ultimos_30_dias(client, admin, destino, monkeypatch, dono):
    h = admin["h"]
    w = criar(client, h, eventos=["resposta.criada"]).json()
    c = criar_contato(client, h)
    responder(client, h, c["id"])
    sql(dono, "update webhook_entregas set criado_em = now() - interval '31 days'")
    responder(client, h, c["id"])
    assert len(entregas(client, h, w["id"])) == 1
    assert client.get(f"{API}/integracoes/webhooks/{w['id']}/entregas?pagina=2", headers=h).json() == []


def test_tarefas_inclui_webhooks(client, admin, monkeypatch):
    from toqqi.core.config import config

    monkeypatch.setattr(config(), "TAREFAS_TOKEN", "t" * 20)
    r = client.post(f"{API}/interno/tarefas", headers={"X-Tarefas-Token": "t" * 20})
    assert r.status_code == 200 and r.json()["webhooks"] == {"entregues": 0, "falharam": 0}
