"""Etapa 5a: adaptador do Asaas (httpx.MockTransport) — cabeçalhos, endereço e ambiente pela chave, corpos do cliente
(celular ou fixo, o outro campo vazio; CNPJ alfanumérico como está) e da assinatura, updatePendingPayments, paginação,
listas pela referência (só as exatas), leitura da cobrança e erros (400 com campos, 401/403, 404, 5xx, tempo esgotado,
rede), sem a chave nem o CPF/CNPJ no log."""
import json
import logging
from datetime import date
from decimal import Decimal

import httpx
import pytest

from toqqi.core import asaas
from toqqi.core.config import config

CHAVE = "$aact_hmlg_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjAwMDAwMDAwMDA6OiRhYWNoX2NoYXZl"
CHAVE_PRODUCAO = "$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjAwMDAwMDAwMDA6OiRhYWNoX3Byb2Q="
CLIENTE = asaas.Cliente(nome="Alfa Distribuidora Ltda", documento="11222333000181", email="fin@alfa.com.br",
                        telefone="5511987654321", referencia="toqqi-conta-7")


@pytest.fixture
def falso(monkeypatch):
    """Asaas de mentira: `respostas` (fila do que responder; exceção = levantar) e `pedidos` (o que chegou)."""
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE)

    class Falso:
        def __init__(self):
            self.pedidos: list[httpx.Request] = []
            self.respostas: list = []

        def __call__(self, request: httpx.Request) -> httpx.Response:
            self.pedidos.append(request)
            r = self.respostas.pop(0) if self.respostas else httpx.Response(200, json={"id": "x_1"})
            if isinstance(r, Exception):
                raise r
            return r

    f = Falso()
    monkeypatch.setattr(asaas, "transporte", httpx.MockTransport(f))
    return f


def _corpo(pedido: httpx.Request) -> dict:
    return json.loads(pedido.content)


def test_cabecalhos_endereco_e_corpo_do_cliente(falso):
    falso.respostas.append(httpx.Response(200, json={"object": "customer", "id": "cus_000005219613"}))
    assert asaas.criar_cliente(CLIENTE) == "cus_000005219613"
    pedido, = falso.pedidos
    assert pedido.method == "POST" and str(pedido.url) == "https://api-sandbox.asaas.com/v3/customers"
    assert pedido.headers["access_token"] == CHAVE
    assert pedido.headers["user-agent"] == "Toqqi/1.0" and pedido.headers["content-type"] == "application/json"
    assert _corpo(pedido) == {"name": "Alfa Distribuidora Ltda", "cpfCnpj": "11222333000181",
                              "email": "fin@alfa.com.br", "mobilePhone": "11987654321", "phone": "",
                              "externalReference": "toqqi-conta-7"}
    asaas.atualizar_cliente("cus_000005219613", CLIENTE)
    pedido = falso.pedidos[-1]
    assert pedido.method == "PUT" and pedido.url.path == "/v3/customers/cus_000005219613"
    assert _corpo(pedido)["cpfCnpj"] == "11222333000181"


def test_telefone_fixo_vai_em_phone_e_o_outro_campo_vazio(falso):
    """O campo que não é usado vai vazio: trocar de celular para fixo (ou o contrário) apaga o número antigo."""
    fixo = asaas.Cliente(nome="Beta", documento="52998224725", email="b@b.com.br", telefone="551140001234",
                         referencia="toqqi-conta-8")
    asaas.atualizar_cliente("cus_1", fixo)
    corpo = _corpo(falso.pedidos[0])
    assert (corpo["phone"], corpo["mobilePhone"]) == ("1140001234", "")
    asaas.atualizar_cliente("cus_1", CLIENTE)
    corpo = _corpo(falso.pedidos[1])
    assert (corpo["phone"], corpo["mobilePhone"]) == ("", "11987654321")


def test_cnpj_alfanumerico_vai_como_esta(falso):
    alfa = asaas.Cliente(nome="Gama", documento="12ABC34501DE35", email="g@g.com.br", telefone="5511987654321",
                         referencia="toqqi-conta-9")
    asaas.criar_cliente(alfa)
    assert _corpo(falso.pedidos[0])["cpfCnpj"] == "12ABC34501DE35"


def test_ambiente_pela_chave(falso, monkeypatch):
    assert asaas.ambiente() == "sandbox"
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_PRODUCAO)
    assert asaas.ambiente() == "producao"
    monkeypatch.setattr(config(), "ASAAS_API_KEY", "$aact_YTU5YTE0M2M2N2I4MTliNzk0YTI5N2U5MzdjNWZmNDQ")
    assert asaas.ambiente() == "sandbox"  # formato desconhecido: nunca produção
    monkeypatch.setattr(config(), "ASAAS_API_KEY", "")
    assert asaas.ambiente() is None


def test_listas_pela_referencia_so_as_exatas(falso):
    """Se o filtro do Asaas fosse ignorado, a lista traria as de outras contas: só as da referência exata ficam."""
    falso.respostas += [
        httpx.Response(200, json={"object": "list", "hasMore": False, "data": [
            {"id": "sub_1", "externalReference": "toqqi-conta-7", "status": "ACTIVE"},
            {"id": "sub_2", "externalReference": "toqqi-conta-77"},
            {"id": "sub_3", "externalReference": None}, {"externalReference": "toqqi-conta-7"}]}),
        httpx.Response(200, json={"object": "list", "hasMore": False, "data": [
            {"id": "cus_1", "externalReference": "toqqi-conta-7"},
            {"id": "cus_2", "externalReference": "toqqi-conta-7", "deleted": True},
            {"id": "cus_3", "externalReference": "toqqi-conta-8"}]}),
        httpx.Response(200, json={"object": "customer", "id": "cus_1", "name": "Alfa"}),
    ]
    assert [a["id"] for a in asaas.listar_assinaturas("toqqi-conta-7")] == ["sub_1"]
    assert falso.pedidos[0].url.path == "/v3/subscriptions"
    assert falso.pedidos[0].url.params["externalReference"] == "toqqi-conta-7"
    assert [c["id"] for c in asaas.buscar_clientes("toqqi-conta-7")] == ["cus_1"]  # sem a removida
    assert (falso.pedidos[1].url.path, falso.pedidos[1].url.params["externalReference"]) == (
        "/v3/customers", "toqqi-conta-7")
    assert asaas.obter_cliente("cus_1")["name"] == "Alfa"
    assert (falso.pedidos[2].method, falso.pedidos[2].url.path) == ("GET", "/v3/customers/cus_1")


@pytest.mark.parametrize("assinatura,viva", [
    ({"status": "ACTIVE", "deleted": False}, True), ({}, True), ({"status": "INACTIVE"}, False),
    ({"status": "EXPIRED"}, False), ({"status": "ACTIVE", "deleted": True}, False),
])
def test_assinatura_viva(assinatura, viva):
    assert asaas.assinatura_viva(assinatura) is viva


def test_endereco_segue_a_chave(falso, monkeypatch):
    assert asaas.endereco() == "https://api-sandbox.asaas.com/v3"
    monkeypatch.setattr(config(), "ASAAS_API_KEY", CHAVE_PRODUCAO)
    assert asaas.endereco() == "https://api.asaas.com/v3"
    asaas.obter_cobranca("pay_1")
    assert str(falso.pedidos[-1].url) == "https://api.asaas.com/v3/payments/pay_1"
    # chave de formato desconhecido nunca vai para a produção
    monkeypatch.setattr(config(), "ASAAS_API_KEY", "$aact_YTU5YTE0M2M2N2I4MTliNzk0YTI5N2U5MzdjNWZmNDQ")
    assert asaas.endereco() == "https://api-sandbox.asaas.com/v3"
    # ASAAS_URL sobrepõe (Asaas falso local)
    monkeypatch.setattr(config(), "ASAAS_URL", "http://localhost:8010/v3/")
    asaas.obter_cobranca("pay/../1")
    assert str(falso.pedidos[-1].url) == "http://localhost:8010/v3/payments/pay%2F..%2F1"  # id sempre escapado


def test_disponivel_e_sem_chave_nao_chama(falso, monkeypatch):
    assert asaas.disponivel() is True
    monkeypatch.setattr(config(), "ASAAS_API_KEY", "  ")
    assert asaas.disponivel() is False
    with pytest.raises(asaas.FalhaAsaas) as e:
        asaas.obter_cobranca("pay_1")
    assert e.value.tipo == "configuracao" and falso.pedidos == []


def test_assinatura_criar_atualizar_e_remover(falso):
    falso.respostas.append(httpx.Response(200, json={"object": "subscription", "id": "sub_VXJBYgP2u0eO"}))
    sid = asaas.criar_assinatura("cus_1", Decimal("349.00"), date(2026, 10, 15), "Toqqi – plano Profissional",
                                 "toqqi-conta-7")
    assert sid == "sub_VXJBYgP2u0eO"
    pedido = falso.pedidos[-1]
    assert pedido.method == "POST" and pedido.url.path == "/v3/subscriptions"
    assert _corpo(pedido) == {"customer": "cus_1", "billingType": "UNDEFINED", "value": 349.0,
                              "nextDueDate": "2026-10-15", "cycle": "MONTHLY",
                              "description": "Toqqi – plano Profissional", "externalReference": "toqqi-conta-7"}
    asaas.atualizar_assinatura(sid, Decimal("799"), "Toqqi – plano Empresa")
    pedido = falso.pedidos[-1]
    assert pedido.method == "PUT" and pedido.url.path == f"/v3/subscriptions/{sid}"
    assert _corpo(pedido) == {"value": 799.0, "description": "Toqqi – plano Empresa", "updatePendingPayments": True}
    falso.respostas.append(httpx.Response(200, json={"object": "subscription", "id": sid, "deleted": False}))
    assert asaas.obter_assinatura(sid)["deleted"] is False
    assert (falso.pedidos[-1].method, falso.pedidos[-1].url.path) == ("GET", f"/v3/subscriptions/{sid}")
    falso.respostas.append(httpx.Response(200, json={"deleted": True, "id": sid}))
    asaas.remover_assinatura(sid)
    pedido = falso.pedidos[-1]
    assert (pedido.method, pedido.url.path, pedido.content) == ("DELETE", f"/v3/subscriptions/{sid}", b"")


def test_cobrancas_da_assinatura_paginadas(falso):
    pagina1 = [{"id": f"pay_{i}"} for i in range(100)]
    falso.respostas += [httpx.Response(200, json={"object": "list", "hasMore": True, "data": pagina1}),
                        httpx.Response(200, json={"object": "list", "hasMore": False, "data": [{"id": "pay_100"}, 7]})]
    itens = asaas.cobrancas_da_assinatura("sub_1")
    assert [p["id"] for p in itens] == [f"pay_{i}" for i in range(101)]  # o que não é objeto fica de fora
    p1, p2 = falso.pedidos
    assert p1.url.path == "/v3/subscriptions/sub_1/payments"
    assert (p1.url.params["offset"], p1.url.params["limit"]) == ("0", "100")
    assert (p2.url.params["offset"], p2.url.params["limit"]) == ("100", "100")


@pytest.mark.parametrize("status,esperado", [
    ("PENDING", "pendente"), ("AWAITING_RISK_ANALYSIS", "pendente"), ("CONFIRMED", "paga"), ("RECEIVED", "paga"),
    ("RECEIVED_IN_CASH", "paga"), ("DUNNING_RECEIVED", "paga"), ("OVERDUE", "vencida"),
    ("DUNNING_REQUESTED", "vencida"), ("REFUNDED", "estornada"), ("REFUND_REQUESTED", "estornada"),
    ("REFUND_IN_PROGRESS", "estornada"), ("CHARGEBACK_REQUESTED", "estornada"), ("CHARGEBACK_DISPUTE", "estornada"),
    ("AWAITING_CHARGEBACK_REVERSAL", "estornada"), ("ALGO_NOVO", None), (None, None),
])
def test_situacao_da_cobranca(status, esperado):
    assert asaas.situacao({"status": status}) == esperado
    assert asaas.situacao({"status": status, "deleted": True}) == "removida"


def test_leitura_da_cobranca():
    p = {"billingType": "PIX", "paymentDate": "2026-10-12", "clientPaymentDate": "2026-10-11", "dueDate": "2026-10-15",
         "value": 349, "netValue": 347.01, "invoiceUrl": "https://sandbox.asaas.com/i/080225913252"}
    assert (asaas.forma(p), asaas.data_do_pagamento(p), asaas.vencimento(p)) == (
        "pix", date(2026, 10, 11), date(2026, 10, 15))
    assert (asaas.valor(p["value"]), asaas.valor(p["netValue"])) == (Decimal("349.00"), Decimal("347.01"))
    assert asaas.link(p) == "https://sandbox.asaas.com/i/080225913252"
    assert [asaas.forma({"billingType": b}) for b in ("BOLETO", "CREDIT_CARD", "DEBIT_CARD", "UNDEFINED")] == [
        "boleto", "cartao", "cartao", None]
    assert asaas.data_do_pagamento({"paymentDate": "2026-10-12"}) == date(2026, 10, 12)
    assert asaas.data_do_pagamento({"paymentDate": None, "clientPaymentDate": "x"}) is None
    assert [asaas.valor(v) for v in ("abc", True, None, float("inf"), "1e30")] == [None] * 5
    assert asaas.link({"invoiceUrl": "javascript:alert(1)"}) is None and asaas.link({}) is None


@pytest.mark.parametrize("status,tipo", [
    (400, "recusado"), (409, "recusado"), (422, "recusado"), (401, "configuracao"), (403, "configuracao"),
    (404, "nao_encontrado"), (408, "indisponivel"), (429, "indisponivel"), (500, "indisponivel"),
    (502, "indisponivel"), (503, "indisponivel"),
])
def test_erros_http(falso, status, tipo):
    falso.respostas.append(httpx.Response(status, json={"errors": [{"code": "x", "description": "y"}]}))
    with pytest.raises(asaas.FalhaAsaas) as e:
        asaas.obter_cobranca("pay_1")
    assert e.value.tipo == tipo and str(status) in e.value.detalhe


def test_400_traz_os_erros_do_asaas(falso):
    falso.respostas.append(httpx.Response(400, json={"errors": [
        {"code": "invalid_cpfCnpj", "description": "O CPF/CNPJ informado é inválido."},
        {"code": "invalid_email", "description": "O email informado é inválido."}, "lixo"]}))
    with pytest.raises(asaas.FalhaAsaas) as e:
        asaas.criar_cliente(CLIENTE)
    assert e.value.tipo == "recusado"
    assert e.value.erros == [("invalid_cpfCnpj", "O CPF/CNPJ informado é inválido."),
                             ("invalid_email", "O email informado é inválido.")]
    assert e.value.detalhe == "HTTP 400 (invalid_cpfCnpj, invalid_email)"
    falso.respostas.append(httpx.Response(400, text="<html>erro</html>"))
    with pytest.raises(asaas.FalhaAsaas) as e:
        asaas.criar_cliente(CLIENTE)
    assert (e.value.tipo, e.value.erros, e.value.detalhe) == ("recusado", [], "HTTP 400 (sem código)")


@pytest.mark.parametrize("resposta,detalhe", [
    (httpx.ReadTimeout("lento"), "tempo esgotado"),
    (httpx.ConnectTimeout("lento"), "tempo esgotado"),
    (httpx.ConnectError("recusada"), "falha de rede (ConnectError)"),
    (httpx.RemoteProtocolError("caiu"), "falha de rede (RemoteProtocolError)"),
    (httpx.Response(200, text="não é json"), "resposta que não é um objeto JSON"),
    (httpx.Response(200, json=[1, 2]), "resposta que não é um objeto JSON"),
    (httpx.Response(200, json={"object": "customer"}), "resposta sem id"),
])
def test_indisponivel(falso, resposta, detalhe):
    falso.respostas.append(resposta)
    with pytest.raises(asaas.FalhaAsaas) as e:
        asaas.criar_cliente(CLIENTE)
    assert (e.value.tipo, e.value.detalhe) == ("indisponivel", detalhe)


def test_tempo_limite_e_sem_redirecionamento(falso, monkeypatch):
    usados = {}
    original = httpx.Client.__init__

    def espiar(self, *a, **k):
        usados.update(k)
        original(self, *a, **k)

    monkeypatch.setattr(httpx.Client, "__init__", espiar)
    falso.respostas.append(httpx.Response(302, headers={"location": "https://outro.site/"}))
    with pytest.raises(asaas.FalhaAsaas):
        asaas.obter_cobranca("pay_1")
    assert usados["timeout"] == 20 and usados["follow_redirects"] is False
    assert len(falso.pedidos) == 1  # não seguiu o redirecionamento


def test_chave_e_documento_fora_do_log(falso, caplog):
    caplog.set_level(logging.DEBUG)
    descricao = "O CPF/CNPJ 112.223.330/0018-1 (11222333000181) informado é inválido."
    falso.respostas += [
        httpx.Response(400, json={"errors": [{"code": "invalid_cpfCnpj", "description": descricao}]}),
        httpx.Response(401, json={"errors": [{"code": "invalid_access_token", "description": f"chave {CHAVE}"}]}),
        httpx.Response(500, text=f"erro interno com {CHAVE} e 11222333000181"),
        httpx.ReadTimeout(f"tempo esgotado {CHAVE}"),
        httpx.ConnectError(f"falhou 11222333000181 {CHAVE}"),
    ]
    for _ in range(5):
        with pytest.raises(asaas.FalhaAsaas):
            asaas.criar_cliente(CLIENTE)
    texto = "\n".join(r.getMessage() for r in caplog.records)  # todos os registros, inclusive os do httpx
    for proibido in (CHAVE, "11222333000181", "112.223.330", "fin@alfa.com.br", "987654321", "Alfa Distribuidora"):
        assert proibido not in texto, proibido
    nossos = [r for r in caplog.records if r.name == "toqqi.asaas"]
    assert len(nossos) == 5 and "invalid_cpfCnpj" in texto and "HTTP 401" in texto
    assert [r.levelno for r in nossos].count(logging.ERROR) == 1  # a chave recusada é erro de configuração
