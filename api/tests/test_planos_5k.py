"""Etapa 5k (docs/api-etapa-5k.md): Pix com desconto, anual, plano Personalizado e os padrões novos — preço e descrição
de cada contrato, assinar (corpo no Asaas, plano e limites na conta), `pago_ate` do anual, troca no anual (409), troca
para e do Personalizado, limite de contatos pelo gatilho, cota e teto do Personalizado, cota do teste, adoção de uma
assinatura anual pela conferência e a rota de preço."""
import json
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from util import API, FUSO, assinar, conta_pronta, encher_contatos, fixar_relogio, sql, trocar_plano

from toqqi.core import planos
from toqqi.core.db import em_conta
from toqqi.core.planos import Contrato
from toqqi.modelos import Conta
from toqqi.modulos.ia import cota, regras


def momento(dia: str, hora: int = 10) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora), tzinfo=FUSO)


@pytest.fixture
def admin(client, dono, monkeypatch):
    """Conta em teste até 15/10/2026 14:30 (São Paulo); hoje é 10/10/2026, 10:00."""
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set teste_ate = :t where id = :c", t=momento("2026-10-15", 14).replace(minute=30),
        c=a["conta"]["id"])
    return a


def _corpo(pedido) -> dict:
    return json.loads(pedido.content)


def _criacao(asaas_falso) -> dict:
    return next(_corpo(p) for p in asaas_falso.pedidos if p.method == "POST" and p.url.path == "/v3/subscriptions")


# ---- preço e descrição -------------------------------------------------------------------------------------

@pytest.mark.parametrize("contrato,valor,descricao", [
    (Contrato("essencial"), "149.00", "Toqqi – plano Essencial"),
    (Contrato("essencial", forma="pix"), "144.53", "Toqqi – plano Essencial · Pix"),
    (Contrato("profissional", "anual"), "3769.20", "Toqqi – plano Profissional · anual"),
    (Contrato("empresa", forma="pix"), "775.03", "Toqqi – plano Empresa · Pix"),
    (Contrato("personalizado", contatos=1500, cota_ia=500), "399.00",
     "Toqqi – plano Personalizado (1.500 contatos, 500 perguntas)"),
    (Contrato("personalizado", contatos=5000, cota_ia=2000), "874.00",
     "Toqqi – plano Personalizado (5.000 contatos, 2.000 perguntas)"),
    (Contrato("personalizado", contatos=10000, cota_ia=2000), "1424.00",
     "Toqqi – plano Personalizado (10.000 contatos, 2.000 perguntas)"),
    (Contrato("personalizado", contatos=12000, cota_ia=5000), "1674.00",
     "Toqqi – plano Personalizado (12.000 contatos, 5.000 perguntas)"),
    (Contrato("personalizado", contatos=100, cota_ia=100), "117.00",
     "Toqqi – plano Personalizado (100 contatos, 100 perguntas)"),
    (Contrato("personalizado", "anual", contatos=1500, cota_ia=500), "4309.20",
     "Toqqi – plano Personalizado (1.500 contatos, 500 perguntas) · anual"),
])
def test_valor_e_descricao(client, contrato, valor, descricao):
    assert planos.valor_contrato(contrato) == Decimal(valor)
    assert planos.descricao(contrato) == descricao
    assert planos.contrato_da_descricao(descricao) == contrato


@pytest.mark.parametrize("texto", [
    "Toqqi – plano Ouro", "Toqqi – plano Personalizado", "Toqqi – plano Essencial (300 contatos, 100 perguntas)",
    "Toqqi – plano Personalizado (150 contatos, 100 perguntas)", "Toqqi – plano Personalizado (1.000 contatos, 7 perguntas)",
    "Toqqi – plano Essencial · mensal", None, 12])
def test_descricao_desconhecida(client, texto):
    assert planos.contrato_da_descricao(texto) is None


def test_rota_de_preco(client, admin):
    h = admin["h"]
    r = client.get(f"{API}/assinatura/preco", headers=h,
                   params={"plano": "personalizado", "ciclo": "anual", "contatos": 5000, "cota_ia": 2000})
    assert r.status_code == 200 and r.json() == {"valor": 9439.2, "por_mes": 874.0, "descricao":
                                                 "Toqqi – plano Personalizado (5.000 contatos, 2.000 perguntas) · anual"}
    for params, campo in (({"plano": "personalizado", "contatos": 150, "cota_ia": 100}, "contatos"),
                          ({"plano": "personalizado", "contatos": 200, "cota_ia": 7}, "cota_ia"),
                          ({"plano": "essencial", "contatos": 200}, "plano"),
                          ({"plano": "essencial", "ciclo": "anual", "forma": "pix"}, "forma"),
                          ({"plano": "ouro"}, "plano")):
        r = client.get(f"{API}/assinatura/preco", headers=h, params=params)
        assert r.status_code == 422 and campo in r.json()["erro"]["campos"], (params, r.text)


def test_descontos_e_tabela_seguem_os_parametros(client, admin):
    from util import salvar_parametros, superadmin
    root = superadmin(client)
    assert salvar_parametros(client, root["h"], "planos", {"planos.desconto.pix": 5, "planos.desconto.anual": 20,
                                                           "planos.personalizado.base": "109.00"}).status_code == 200
    assert planos.valor_contrato(Contrato("essencial", forma="pix")) == Decimal("141.55")
    assert planos.valor_contrato(Contrato("essencial", "anual")) == Decimal("1430.40")
    assert planos.preco_mensal(Contrato("personalizado", contatos=1500, cota_ia=500)) == Decimal("409.00")


# ---- assinar ----------------------------------------------------------------------------------------------

def test_assinar_mensal_com_pix(client, admin, dono, asaas_falso):
    r = assinar(client, admin["h"], "essencial", forma="pix", preco="144.53")
    assert r.status_code == 201, r.text
    a = r.json()["assinatura"]
    assert (a["valor"], a["ciclo"], a["forma"], a["nome"]) == (144.53, "mensal", "pix", "Essencial")
    corpo = _criacao(asaas_falso)
    assert (corpo["billingType"], corpo["cycle"], corpo["value"], corpo["description"]) == (
        "PIX", "MONTHLY", 144.53, "Toqqi – plano Essencial · Pix")


def test_preco_do_pix_conferido(client, admin, asaas_falso):
    r = assinar(client, admin["h"], "essencial", forma="pix")  # mandou o preço cheio (149.00)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "preco_mudou"
    assert "R$ 144,53" in r.json()["erro"]["mensagem"] and asaas_falso.pedidos == []


def test_anual_pago_cobre_um_ano_e_nao_troca_de_plano(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    r = assinar(client, h, "profissional", ciclo="anual", preco="3769.20")
    assert r.status_code == 201, r.text
    corpo = _criacao(asaas_falso)
    assert (corpo["billingType"], corpo["cycle"], corpo["value"]) == ("UNDEFINED", "YEARLY", 3769.2)
    for p in asaas_falso.cobrancas():
        asaas_falso.simular("pagar", p["id"], forma="PIX")
    assert sql(dono, "select situacao, pago_ate from contas where id = :c", c=conta) == [
        ("ativa", date(2027, 10, 14))]  # vence no último dia do teste (15/10) e cobre até a véspera de 15/10/2027
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "troca_no_anual"
    # o mesmo plano não muda nada (nem no anual)
    assert client.put(f"{API}/assinatura/plano", headers=h,
                      json={"plano": "profissional", "preco": "3769.20"}).status_code == 200


def test_anual_com_pix_recusado(client, admin, asaas_falso):
    r = assinar(client, admin["h"], "profissional", ciclo="anual", forma="pix", preco="3769.20")
    assert r.status_code == 422 and "forma" in r.json()["erro"]["campos"] and asaas_falso.pedidos == []


def test_personalizado_assinar_limites_cota_e_teto(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    r = assinar(client, h, "personalizado", contatos=2000, cota_ia=500, preco="454.00")
    assert r.status_code == 201, r.text
    a = r.json()["assinatura"]
    assert (a["plano"], a["contatos"], a["cota_ia"], a["nome"]) == (
        "personalizado", 2000, 500, "Personalizado (2.000 contatos, 500 perguntas)")
    assert _criacao(asaas_falso)["description"] == "Toqqi – plano Personalizado (2.000 contatos, 500 perguntas)"
    assert sql(dono, "select plano, contatos_personalizado, cota_ia_personalizada from contas where id = :c",
               c=conta) == [("personalizado", 2000, 500)]
    # assinou no teste: a cota já é a contratada (não a do teste); o teto segue o do teste até pagar
    with em_conta(conta) as s:
        c = s.get(Conta, conta)
        assert cota.limite(c) == 500 and regras.teto_mensal(c) == 500
    for p in asaas_falso.cobrancas():
        asaas_falso.simular("pagar", p["id"], forma="PIX")
    with em_conta(conta) as s:
        c = s.get(Conta, conta)
        assert c.situacao == "ativa" and cota.limite(c) == 500 and regras.teto_mensal(c) == 6000
    # o gatilho usa o limite contratado
    encher_contatos(dono, conta, 2000)
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Um a mais", "email": "mais@cliente.com.br"})
    assert r.status_code == 402 and "2000" in r.json()["erro"]["mensagem"]
    # trocar para menos contatos que os ativos: 422; para mais: muda o valor e o limite
    r = trocar_plano(client, h, "personalizado", contatos=1000, cota_ia=500, preco="309.00")
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "limite_do_plano"
    r = trocar_plano(client, h, "personalizado", contatos=3000, cota_ia=2000, preco="654.00")
    assert r.status_code == 200, r.text
    assert sql(dono, "select contatos_personalizado, cota_ia_personalizada from contas where id = :c",
               c=conta) == [(3000, 2000)]
    assert asaas_falso.assinatura()["description"] == "Toqqi – plano Personalizado (3.000 contatos, 2.000 perguntas)"
    assert client.post(f"{API}/contatos", headers=h,
                       json={"nome": "Agora cabe", "email": "cabe@cliente.com.br"}).status_code == 201
    # e para um plano padrão: os limites do Personalizado saem da conta
    sql(dono, "update contatos set ativo = false where conta_id = :c and id in (select id from contatos where "
              "conta_id = :c order by id limit 1800)", c=conta)
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 200, r.text
    assert sql(dono, "select plano, contatos_personalizado, cota_ia_personalizada from contas where id = :c",
               c=conta) == [("empresa", None, None)]


def test_personalizado_fora_da_tabela(client, admin, asaas_falso):
    for extra in ({"contatos": 250, "cota_ia": 100}, {"contatos": 200}, {"contatos": 200, "cota_ia": 300}):
        r = assinar(client, admin["h"], "personalizado", preco="135.00", **extra)
        assert r.status_code == 422, r.text
    r = assinar(client, admin["h"], "essencial", contatos=300)
    assert r.status_code == 422 and "plano" in r.json()["erro"]["campos"]
    assert asaas_falso.pedidos == []


def test_cota_do_teste_e_padroes_novos(client, admin, dono):
    conta = admin["conta"]["id"]
    with em_conta(conta) as s:
        c = s.get(Conta, conta)
        assert (c.situacao, cota.limite(c), regras.teto_mensal(c)) == ("teste", 50, 500)
    assert sql(dono, "select limite_contatos('empresa', 'ativa'), limite_contatos('empresa', 'cortesia')") == [
        (5000, None)]
    r = client.get(f"{API}/conta/ia", headers=admin["h"])
    assert r.status_code == 200 and r.json()["cota"]["limite"] == 50


# ---- conferência: adoção ------------------------------------------------------------------------------------

def test_conferencia_adota_assinatura_anual_e_personalizada(client, admin, dono, asaas_falso):
    from toqqi.modulos.assinatura import conferencia
    conta = admin["conta"]["id"]
    sql(dono, "update contas set asaas_cliente_id = 'cus_x', asaas_ambiente = 'sandbox' where id = :c", c=conta)
    sub = {"id": "sub_1", "value": 4309.2, "cycle": "YEARLY", "customer": "cus_x",
           "description": "Toqqi – plano Personalizado (1.500 contatos, 500 perguntas) · anual"}
    assert conferencia.servico.contrato_do_asaas(sub) == Contrato("personalizado", "anual", "qualquer", 1500, 500)
    assert conferencia.servico.contrato_do_asaas({**sub, "cycle": "MONTHLY"}) is None
    assert conferencia.servico.contrato_do_asaas({**sub, "value": 4000}) is None
    assert conferencia.servico.plano_da_assinatura({"value": 144.53, "description": "Toqqi – plano Essencial · Pix",
                                                    "cycle": "MONTHLY"}) == "essencial"
