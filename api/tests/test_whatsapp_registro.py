"""Situação do número na Meta e o registro na Cloud API pelo Toqqi (docs/api-whatsapp-registro.md): o número
"Pendente" no WhatsApp Manager é registrado com o token salvo e um PIN de 6 dígitos que nunca fica guardado; as
recusas da Meta viram texto simples e há um limite de tentativas em 72 horas."""
import logging

import pytest
from util import API, PNID, conectar_whatsapp, conta_pronta, membro, sql

from toqqi.modulos.whatsapp import graph

PIN = "482915"
PENDENTE = {"status": "PENDING", "platform_type": "NOT_APPLICABLE", "code_verification_status": "VERIFIED",
            "name_status": "APPROVED"}


@pytest.fixture
def admin(client, dono, meta):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    assert conectar_whatsapp(client, a["h"]).status_code == 200
    return a


def _numero(client, h):
    return client.get(f"{API}/integracoes/whatsapp/numero", headers=h)


def _registrar(client, h, pin=PIN):
    return client.post(f"{API}/integracoes/whatsapp/registrar", headers=h, json={"pin": pin})


@pytest.mark.parametrize("dados,situacao", [
    ({"status": "CONNECTED", "platform_type": "CLOUD_API"}, "registrado"),
    ({"status": "PENDING", "platform_type": "NOT_APPLICABLE"}, "falta_registrar"),
    ({"status": "UNVERIFIED", "platform_type": "NOT_APPLICABLE"}, "falta_registrar"),
    ({"status": "CONNECTED", "platform_type": "ON_PREMISE"}, "falta_registrar"),
    ({"status": "PENDING"}, "falta_registrar"),
    ({"status": "CONNECTED"}, "registrado"),
    ({"status": "FLAGGED", "platform_type": "CLOUD_API"}, "atencao"),
    ({"status": "RESTRICTED", "platform_type": "CLOUD_API"}, "atencao"),
    ({"status": "BANNED", "platform_type": "CLOUD_API"}, "problema"),
    ({"status": "DELETED", "platform_type": "NOT_APPLICABLE"}, "problema"),
    ({}, "desconhecida"),
])
def test_situacao(dados, situacao):
    assert graph.situacao(dados) == situacao


def test_situacao_do_numero_lida_na_hora(client, admin, meta):
    h = admin["h"]
    assert _numero(client, h).json() == {"situacao": "registrado", "status": "CONNECTED", "codigo_confirmado": True}
    pedido = meta.pedidos[-1]
    assert pedido.url.path.endswith(f"/{PNID}") and "platform_type" in pedido.url.params["fields"]
    meta.numero = {**PENDENTE, "code_verification_status": "EXPIRED"}
    assert _numero(client, h).json() == {"situacao": "falta_registrar", "status": "PENDING",
                                         "codigo_confirmado": False}
    meta.numero = {}
    assert _numero(client, h).json() == {"situacao": "desconhecida", "status": None, "codigo_confirmado": None}
    # a Meta recusou o token: o texto de sempre
    meta.erro_numero = (401, {"code": 190, "message": "Invalid OAuth access token."})
    r = _numero(client, h)
    assert r.status_code == 409 and r.json()["erro"] == {"codigo": "falha_meta", "mensagem": graph.MSG_TOKEN,
                                                          "campos": {}}


def test_registra_com_o_token_salvo_e_nao_guarda_o_pin(client, admin, meta, dono, caplog):
    h = admin["h"]
    meta.numero = dict(PENDENTE)
    sql(dono, "update whatsapp_contas set ultimo_erro = :e", e=graph.MSG_CONTA)
    caplog.set_level(logging.DEBUG)
    r = _registrar(client, h)
    assert r.status_code == 200, r.text
    assert r.json() == {"mensagem": "Pronto! O número foi registrado na Meta. Em alguns minutos ele aparece como "
                                    "Conectado no WhatsApp Manager.",
                        "numero": {"situacao": "registrado", "status": None, "codigo_confirmado": True}}
    assert meta.registros == [{"messaging_product": "whatsapp", "pin": PIN}]
    pedido = meta.pedidos[-1]
    assert pedido.url.path.endswith(f"/{PNID}/register") and pedido.headers["authorization"].startswith("Bearer EAAG")
    assert _numero(client, h).json()["situacao"] == "registrado"
    # o erro "sem número registrado" do último envio sai; o PIN não fica em lugar nenhum
    assert sql(dono, "select ultimo_erro from whatsapp_contas") == [(None,)]
    eventos = client.get(f"{API}/auditoria", headers=h).json()["itens"]
    registro = next(e for e in eventos if e["evento"] == "whatsapp_numero_registrado")
    assert registro["detalhe"] == {"numero": "+55 11 4000-1234"}
    assert sql(dono, "select count(*) from auditoria where detalhe::text like :p", p=f"%{PIN}%")[0][0] == 0
    assert PIN not in caplog.text


def test_outro_erro_do_ultimo_envio_fica(client, admin, meta, dono):
    meta.numero = dict(PENDENTE)
    sql(dono, "update whatsapp_contas set ultimo_erro = :e", e=graph.MSG_MODELO)
    assert _registrar(client, admin["h"]).status_code == 200
    assert sql(dono, "select ultimo_erro from whatsapp_contas") == [(graph.MSG_MODELO,)]


@pytest.mark.parametrize("pin", ["12345", "1234567", "abcdef", "12 456", "", "１２３４５６"])
def test_pin_de_6_numeros(client, admin, meta, pin):
    r = _registrar(client, admin["h"], pin)
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"pin": "O PIN tem 6 números."}
    assert meta.registros == []


@pytest.mark.parametrize("status,erro,mensagem", [
    (400, {"code": 133005, "message": "Two step verification PIN Mismatch"}, graph.MSG_REGISTRO[133005]),
    (400, {"code": 133016, "message": "Account register deregister rate limit exceeded"},
     graph.MSG_REGISTRO[133016]),
    (400, {"code": 133006, "message": "Phone number re-verification needed"}, graph.MSG_REGISTRO[133006]),
    (401, {"code": 190, "message": "Invalid OAuth access token."}, graph.MSG_TOKEN),
    (403, {"code": 200, "message": "Permissions error"}, graph.MSG_REGISTRO_PERMISSAO),
    (503, {"code": 133004, "message": "Server temporarily unavailable"}, graph.MSG_REGISTRO_FORA_DO_AR),
    (400, {"code": 131999, "message": "Something else"},
     "A Meta recusou o registro do número (código 131999). Confira o número no WhatsApp Manager."),
])
def test_recusas_da_meta_em_texto_simples(client, admin, meta, dono, status, erro, mensagem):
    meta.numero = dict(PENDENTE)
    meta.erro_registro = (status, erro)
    r = _registrar(client, admin["h"])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "registro_recusado"
    assert r.json()["erro"]["mensagem"] == mensagem
    assert sql(dono, "select detalhe->>'codigo' from auditoria where evento = 'whatsapp_registro_recusado'") == [
        (str(erro["code"]),)]


def test_limite_de_tentativas_em_72_horas(client, admin, meta, dono):
    conta = admin["conta"]["id"]
    for horas in (1, 2, 3, 4, 5, 6, 7, 80):  # 7 nas últimas 72 horas, uma mais antiga
        sql(dono, "insert into auditoria (conta_id, evento, gravidade, detalhe, criado_em) values "
                  "(:c, 'whatsapp_registro_recusado', 'atencao', '{}', now() - make_interval(hours => :h))",
            c=conta, h=horas)
    meta.numero = dict(PENDENTE)
    meta.erro_registro = (400, {"code": 133005, "message": "PIN Mismatch"})
    assert _registrar(client, admin["h"]).json()["erro"]["codigo"] == "registro_recusado"  # a 8ª passa
    r = _registrar(client, admin["h"])
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "muitas_tentativas_registro"
    assert r.json()["erro"]["mensagem"].startswith("Já foram 8 tentativas de registro nos últimos 3 dias.")
    assert len(meta.registros) == 1  # a 9ª nem chega à Meta


def test_sem_whatsapp_e_permissoes(client, meta, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    for r in (_numero(client, a["h"]), _registrar(client, a["h"])):
        assert r.status_code == 409 and r.json()["erro"]["codigo"] == "whatsapp_nao_conectado"
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    conectar_whatsapp(client, a["h"])
    gestor = membro(client, a["h"], "gil@alfa.com.br", perfil="gestor")["h"]
    for r in (_numero(client, gestor), _registrar(client, gestor)):
        assert r.status_code == 403
    assert meta.registros == []
