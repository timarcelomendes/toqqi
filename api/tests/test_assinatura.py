"""Etapa 5a: rotas da assinatura (com o Asaas falso atrás do adaptador) — planos, estado, assinar no teste e depois
dele, 409/422/503, cliente guardado depois de falha, tempo esgotado ao criar o cliente ou a assinatura (reaproveita ou
adota o que o Asaas chegou a criar; nunca duas vivas), trocar de plano (valor e limite; plano menor com contatos
demais; tempo esgotado com o valor já mudado lá), dados de cobrança (telefone do Brasil; celular ↔ fixo), CNPJ
alfanumérico, cancelar (no teste → volta ao teste e ao plano do teste; pago → até `pago_ate`), assinar de novo,
permissões e os avisos em /eu e no login."""
import json
from datetime import date, datetime, time

import httpx
import pytest
from util import (
    API,
    DADOS_COBRANCA,
    FUSO,
    assinar,
    conta_pronta,
    criar_contato,
    encher_contatos,
    entrar,
    fixar_relogio,
    membro,
    situacao_conta,
    sql,
    trocar_plano,
)

from toqqi import tarefas
from toqqi.core.config import config


def momento(dia: str, hora: int = 10, minuto: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(dia), time(hora, minuto), tzinfo=FUSO)


@pytest.fixture
def admin(client, dono, monkeypatch):
    """Conta em teste até 15/10/2026 14:30 (São Paulo); hoje é 10/10/2026, 10:00."""
    fixar_relogio(monkeypatch, momento("2026-10-10"))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    sql(dono, "update contas set teste_ate = :t where id = :c", t=momento("2026-10-15", 14, 30), c=a["conta"]["id"])
    return a


def estado(client, h) -> dict:
    r = client.get(f"{API}/assinatura", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def pedidos(falso, metodo: str, trecho: str) -> list:
    return [p for p in falso.pedidos if p.method == metodo and trecho in p.url.path]


def pagar_tudo(falso, forma: str = "PIX") -> None:
    for p in falso.cobrancas():
        if p["status"] in ("PENDING", "OVERDUE"):
            falso.simular("pagar", p["id"], forma=forma)


# ---- planos, estado e permissões ------------------------------------------------------

def test_planos_para_qualquer_logado(client, admin):
    consulta = membro(client, admin["h"], "caio@alfa.com.br", "consulta")
    r = client.get(f"{API}/assinatura/planos", headers=consulta["h"])
    assert r.status_code == 200
    comuns = {"whatsapp": None}  # 5k: sem franquia
    assert r.json() == [
        {"chave": "essencial", "nome": "Essencial", "preco": 149.0, "contatos": 300, "ia_cota": 100, "ia_teto": 1000, **comuns},
        {"chave": "profissional", "nome": "Profissional", "preco": 349.0, "contatos": 1500, "ia_cota": 500, "ia_teto": 5000,
         **comuns},
        {"chave": "empresa", "nome": "Empresa", "preco": 799.0, "contatos": 5000, "ia_cota": 2000, "ia_teto": 15000,
         **comuns}]
    assert client.get(f"{API}/assinatura/planos").status_code == 401


def test_so_admin_gerencia(client, admin, asaas_falso):
    for perfil in ("gestor", "consulta"):
        m = membro(client, admin["h"], f"{perfil}@alfa.com.br", perfil)
        for metodo, rota, corpo in (("get", "", None), ("post", "", {"plano": "essencial", **DADOS_COBRANCA}),
                                    ("put", "/plano", {"plano": "empresa"}), ("put", "/dados", DADOS_COBRANCA),
                                    ("post", "/cancelar", None)):
            r = client.request(metodo.upper(), f"{API}/assinatura{rota}", headers=m["h"], json=corpo)
            assert r.status_code == 403 and r.json()["erro"]["codigo"] == "sem_permissao", (perfil, rota)
        assert "assinatura.gerenciar" not in client.get(f"{API}/eu", headers=m["h"]).json()["permissoes"]
    # o gestor não ganha a permissão nem pela matriz da equipe
    r = client.put(f"{API}/equipe/permissoes", headers=admin["h"],
                   json={"gestor": ["assinatura.gerenciar"], "consulta": []})
    assert r.status_code == 422
    assert asaas_falso.pedidos == []


def test_estado_inicial_e_dados_sugeridos(client, admin, dono, asaas_falso):
    h = admin["h"]
    sql(dono, "update contas set razao_social = 'Alfa Distribuidora Ltda', documento = '11222333000181', "
              "telefone = '551140001234' where id = :c", c=admin["conta"]["id"])
    criar_contato(client, h)
    criar_contato(client, h, ativo=False)
    d = estado(client, h)
    assert d["conta"] == {"situacao": "teste", "plano": "profissional", "teste_ate": "2026-10-15T17:30:00+00:00",
                          "pago_ate": None, "atrasada_desde": None, "liberada": True,
                          "pausa_em": "2026-10-15T17:30:00+00:00", "contatos_personalizado": None,
                          "cota_ia_personalizada": None}
    assert d["descontos"] == {"pix": 3, "anual": 10} and d["personalizado"]["base"] == 99.0
    assert d["contatos_ativos"] == 1 and d["disponivel"] is True and len(d["planos"]) == 3
    assert d["dados_sugeridos"] == {"razao_social": "Alfa Distribuidora Ltda", "documento": "11222333000181",
                                    "email_cobranca": "ana@alfa.com.br", "telefone": "551140001234"}
    assert (d["assinatura"], d["fatura_aberta"], d["cobrancas"]) == (None, None, [])
    # sem dados da empresa: o nome da conta e o telefone do cadastro do admin (se for válido)
    sql(dono, "update contas set razao_social = null, documento = null, telefone = null where id = :c",
        c=admin["conta"]["id"])
    sql(dono, "update usuarios set telefone = '(11) 98888-7777' where email = 'ana@alfa.com.br'")
    assert estado(client, h)["dados_sugeridos"] == {"razao_social": "Alfa Distribuidora", "documento": None,
                                                    "email_cobranca": "ana@alfa.com.br", "telefone": "5511988887777"}
    sql(dono, "update usuarios set telefone = '123' where email = 'ana@alfa.com.br'")
    assert estado(client, h)["dados_sugeridos"]["telefone"] is None


def test_sem_asaas_configurado(client, admin, dono):
    h = admin["h"]
    d = estado(client, h)
    assert d["disponivel"] is False and d["assinatura"] is None
    r = assinar(client, h)
    assert r.status_code == 503 and r.json()["erro"] == {
        "codigo": "cobranca_indisponivel",
        "mensagem": "A cobrança online ainda não está disponível. Fale com a equipe Toqqi.", "campos": {}}
    assert sql(dono, "select count(*) from assinaturas")[0][0] == 0
    assert trocar_plano(client, h, "empresa").json()["erro"]["codigo"] == \
        "sem_assinatura"


# ---- assinar ----------------------------------------------------------------------------------

def test_assinar_durante_o_teste(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    r = assinar(client, h, "essencial")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["assinatura"] == {
        "plano": "essencial", "nome": "Essencial", "valor": 149.0, "ciclo": "mensal", "forma": "qualquer",
        "contatos": None, "cota_ia": None, "situacao": "ativa", "criada_em": "2026-10-10T13:00:00+00:00",
        "cancelada_em": None, "primeiro_vencimento": "2026-10-15",
        "dados": {"razao_social": "Alfa Distribuidora Ltda", "documento": "11222333000181",
                  "email_cobranca": "financeiro@alfa.com.br", "telefone": "5511987654321"}}
    assert d["fatura_aberta"] == {"valor": 149.0, "vencimento": "2026-10-15", "situacao": "pendente",
                                  "link": d["cobrancas"][0]["link"]}
    assert d["cobrancas"] == [{"valor": 149.0, "vencimento": "2026-10-15", "situacao": "pendente", "forma": None,
                               "pago_em": None, "link": d["fatura_aberta"]["link"]}]
    # o teste continua (e, sem pagamento, vai até o fim da carência da primeira fatura: 7 dias depois do vencimento)
    assert d["conta"]["situacao"] == "teste" and d["conta"]["plano"] == "essencial"
    assert d["conta"]["liberada"] is True and d["conta"]["pausa_em"] == "2026-10-23T03:00:00+00:00"
    corpo = json.loads(pedidos(asaas_falso, "POST", "/subscriptions")[0].content)
    assert corpo == {"customer": asaas_falso.assinatura()["customer"], "billingType": "UNDEFINED", "value": 149.0,
                     "nextDueDate": "2026-10-15", "cycle": "MONTHLY", "description": "Toqqi – plano Essencial",
                     "externalReference": f"toqqi-conta-{conta}"}
    assert situacao_conta(dono, conta) == ("teste", None, None, date(2026, 10, 15))
    assert sql(dono, "select evento, detalhe from auditoria where conta_id = :c and evento = 'assinatura_criada'",
               c=conta) == [("assinatura_criada", {"plano": "essencial", "valor": "149.00"})]
    # o limite de contatos já é o do plano novo
    encher_contatos(dono, conta, 300)
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Excedente", "email": "x@y.com.br"})
    assert r.status_code == 402 and r.json()["erro"]["campos"] == {"limite": "300"}


def test_assinar_depois_do_teste_vence_amanha_e_libera_so_com_pagamento(client, admin, dono, asaas_falso, monkeypatch):
    h, conta = admin["h"], admin["conta"]["id"]
    fixar_relogio(monkeypatch, momento("2026-10-20", 16))
    sql(dono, "update contas set situacao = 'teste_expirado' where id = :c", c=conta)
    d = assinar(client, h).json()
    assert d["assinatura"]["primeiro_vencimento"] == "2026-10-21"
    assert (d["conta"]["situacao"], d["conta"]["liberada"]) == ("teste_expirado", False)
    eu = client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]
    # já assinou: o aviso é o da primeira fatura (os envios voltam quando ela for paga), não o de teste encerrado
    assert eu["aviso"] == {"tipo": "aguardando_pagamento", "data": "2026-10-21", "dias": 1}
    assert eu["liberada"] is False and eu["assinada"] is True
    r = client.get(f"{API}/envios/pre-condicoes", headers=h).json()["itens"][0]
    assert r["mensagem"] == "Os envios voltam quando a fatura da assinatura for paga."
    # venceu sem pagar: não ganha a carência de atraso (não estava coberto quando a fatura venceu)
    fixar_relogio(monkeypatch, momento("2026-10-22", 9))
    asaas_falso.simular("vencer", asaas_falso.cobrancas()[0]["id"])
    assert situacao_conta(dono, conta) == ("teste_expirado", None, date(2026, 10, 21), date(2026, 10, 21))
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]["liberada"] is False
    # pagou: ativa
    pagar_tudo(asaas_falso)
    assert situacao_conta(dono, conta) == ("ativa", date(2026, 11, 20), None, date(2026, 10, 21))
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]["liberada"] is True


def test_409_ja_assinada_e_cortesia(client, admin, dono, asaas_falso):
    h = admin["h"]
    assert assinar(client, h).status_code == 201
    r = assinar(client, h, "empresa")
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "ja_assinada"
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=outra["conta"]["id"])
    r = assinar(client, outra["h"])
    assert r.status_code == 409 and r.json()["erro"] == {
        "codigo": "cortesia", "mensagem": "Sua conta é cortesia: não precisa assinar.", "campos": {}}
    assert len(asaas_falso.dados["assinaturas"]) == 1


def test_422_limite_do_plano_ao_assinar(client, admin, dono, asaas_falso):
    encher_contatos(dono, admin["conta"]["id"], 301)
    r = assinar(client, admin["h"], "essencial")
    assert r.status_code == 422 and r.json()["erro"] == {
        "codigo": "limite_do_plano",
        "mensagem": "Você tem 301 contatos ativos; o plano Essencial permite até 300. Desative contatos antes de "
                    "assinar.", "campos": {"limite": "300"}}
    assert asaas_falso.pedidos == []
    assert assinar(client, admin["h"], "profissional").status_code == 201


@pytest.mark.parametrize("campo,valor,mensagem", [
    ("documento", "11.222.333/0001-80", "CNPJ ou CPF inválido. Confira os números."),
    ("documento", "", "Informe o CPF ou o CNPJ."),
    ("email_cobranca", "financeiro@", "Informe um e-mail válido, como nome@empresa.com.br."),
    ("email_cobranca", None, "Informe o e-mail que recebe as faturas."),
    ("telefone", "98765-4321", "Informe o telefone com DDD (10 a 13 dígitos)."),
    ("telefone", "+44 20 7946 09581", "Informe um telefone do Brasil com DDD."),
    ("telefone", "+1 415 555 0100", "Informe um telefone do Brasil com DDD."),  # 11 dígitos, mas não é do Brasil
    ("telefone", "(10) 98765-4321", "Informe um telefone do Brasil com DDD."),  # DDD 10
    ("telefone", "(11) 1234-5678", "Informe um telefone do Brasil com DDD."),  # fixo começando com 1
    ("telefone", "(11) 88765-4321", "Informe um telefone do Brasil com DDD."),  # celular sem o 9 na frente
    ("telefone", "+55 (11) 08765-4321", "Informe um telefone do Brasil com DDD."),
    ("documento", "12.ABC.345/01DE-34", "CNPJ ou CPF inválido. Confira os números."),  # DV errado
    ("documento", "12.ABC.345/01DE-3A", "CNPJ ou CPF inválido. Confira os números."),  # letra no DV
    ("razao_social", "  ", "Informe a razão social (ou o nome completo, para CPF)."),
    ("razao_social", "x" * 201, "Use no máximo 200 caracteres."),
    ("plano", "ouro", "Opção inválida."),
])
def test_422_validacao_dos_dados(client, admin, asaas_falso, campo, valor, mensagem):
    r = assinar(client, admin["h"], **{campo: valor})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {campo: mensagem}
    assert asaas_falso.pedidos == []


def test_cpf_e_telefone_fixo(client, admin, asaas_falso):
    r = assinar(client, admin["h"], documento="529.982.247-25", razao_social="Ana   Souza", telefone="1140001234")
    assert r.status_code == 201, r.text
    assert r.json()["assinatura"]["dados"] | {"email_cobranca": None} == {
        "razao_social": "Ana Souza", "documento": "52998224725", "email_cobranca": None, "telefone": "551140001234"}
    cliente = json.loads(pedidos(asaas_falso, "POST", "/customers")[0].content)
    assert (cliente["cpfCnpj"], cliente["phone"], cliente["mobilePhone"]) == ("52998224725", "1140001234", "")


def test_asaas_recusa_os_dados(client, admin, dono, asaas_falso):
    h = admin["h"]
    asaas_falso.falhar(httpx.Response(400, json={"errors": [
        {"code": "invalid_cpfCnpj", "description": "O CPF/CNPJ informado é inválido."},
        {"code": "invalid_mobilePhone", "description": "O celular informado é inválido."}]}), "POST", "/customers")
    r = assinar(client, h)
    assert r.status_code == 422 and r.json()["erro"] == {
        "codigo": "cobranca_recusada", "mensagem": "Confira os campos destacados.",
        "campos": {"documento": "O Asaas recusou este CPF/CNPJ. Confira os números.",
                   "telefone": "O Asaas recusou este telefone. Informe um número com DDD."}}
    asaas_falso.falhar(httpx.Response(400, json={"errors": [
        {"code": "invalid_object", "description": "Não é permitido criar cobranças para este cliente."}]}),
        "POST", "/subscriptions")
    r = assinar(client, h)
    assert r.status_code == 422 and r.json()["erro"] == {
        "codigo": "cobranca_recusada", "mensagem": "Não é permitido criar cobranças para este cliente.", "campos": {}}
    assert sql(dono, "select count(*) from assinaturas")[0][0] == 0


def test_asaas_fora_do_ar_guarda_o_cliente_para_a_proxima(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    asaas_falso.falhar(httpx.Response(503), "POST", "/customers")
    r = assinar(client, h)
    assert r.status_code == 503 and r.json()["erro"] == {
        "codigo": "cobranca_indisponivel",
        "mensagem": "A cobrança está temporariamente indisponível. Tente de novo em alguns minutos.", "campos": {}}
    assert sql(dono, "select asaas_cliente_id from contas where id = :c", c=conta) == [(None,)]
    # o cliente foi criado, mas a assinatura não: o id do cliente fica guardado
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "POST", "/subscriptions")
    assert assinar(client, h).status_code == 503
    (cliente,), = sql(dono, "select asaas_cliente_id from contas where id = :c", c=conta)
    assert cliente in asaas_falso.dados["clientes"] and len(asaas_falso.dados["clientes"]) == 1
    assert sql(dono, "select count(*) from assinaturas")[0][0] == 0
    # na próxima tentativa, o mesmo cliente (atualizado), sem criar outro
    assert assinar(client, h, telefone="11977776666").status_code == 201
    assert len(asaas_falso.dados["clientes"]) == 1 and asaas_falso.assinatura()["customer"] == cliente
    assert asaas_falso.dados["clientes"][cliente]["mobilePhone"] == "11977776666"
    assert len(pedidos(asaas_falso, "PUT", f"/customers/{cliente}")) == 1


def test_cliente_apagado_no_asaas_ganha_outro(client, admin, dono, asaas_falso):
    sql(dono, "update contas set asaas_cliente_id = 'cus_sumiu', asaas_ambiente = 'sandbox' where id = :c",
        c=admin["conta"]["id"])
    assert assinar(client, admin["h"]).status_code == 201
    novo = asaas_falso.assinatura()["customer"]
    assert novo != "cus_sumiu"
    assert sql(dono, "select asaas_cliente_id from contas where id = :c", c=admin["conta"]["id"]) == [(novo,)]


def test_sem_a_primeira_fatura_a_assinatura_fica_e_o_webhook_completa(client, admin, dono, asaas_falso):
    asaas_falso.falhar(httpx.Response(500), "GET", "/payments")
    r = assinar(client, admin["h"])
    assert r.status_code == 201 and r.json()["fatura_aberta"] is None and r.json()["assinatura"] is not None
    # o webhook de cobrança criada traz a fatura
    from util import aviso_asaas
    p = asaas_falso.cobrancas()[0]
    assert aviso_asaas(client, {"id": "evt_criada", "event": "PAYMENT_CREATED", "payment": p}).status_code == 200
    assert estado(client, admin["h"])["fatura_aberta"]["vencimento"] == "2026-10-15"


def test_gravacao_falha_depois_de_criar_no_asaas_remove_la(client, admin, dono, asaas_falso, monkeypatch):
    from toqqi.modulos.assinatura import servico

    def quebrar(*_a, **_k):
        raise RuntimeError("banco caiu")

    monkeypatch.setattr(servico, "recalcular", quebrar)
    with pytest.raises(RuntimeError):  # o TestClient repassa o erro (a API responde 500)
        assinar(client, admin["h"])
    sub, = asaas_falso.dados["assinaturas"].values()
    assert sub["deleted"] is True  # sem a assinatura gravada aqui, o Asaas não pode seguir cobrando
    assert sql(dono, "select count(*) from assinaturas")[0][0] == 0


# ---- trocar de plano e dados ---------------------------------------------------------------------

def test_trocar_de_plano(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    r = trocar_plano(client, h, "essencial")
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "sem_assinatura"
    assinar(client, h, "profissional")
    sid = asaas_falso.assinatura()["id"]
    # o mesmo plano: nada muda (nem chama o Asaas)
    antes = len(asaas_falso.pedidos)
    assert trocar_plano(client, h, "profissional").status_code == 200
    assert len(asaas_falso.pedidos) == antes
    # plano menor com contatos demais: recusado antes de chamar o Asaas
    encher_contatos(dono, conta, 301)
    r = trocar_plano(client, h, "essencial")
    assert r.status_code == 422 and r.json()["erro"] == {
        "codigo": "limite_do_plano",
        "mensagem": "Você tem 301 contatos ativos; o plano Essencial permite até 300. Desative contatos antes de "
                    "trocar.", "campos": {"limite": "300"}}
    assert len(asaas_falso.pedidos) == antes
    # maior: muda o valor também da fatura em aberto, o plano da conta e o limite na hora
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["assinatura"]["plano"], d["assinatura"]["valor"], d["conta"]["plano"]) == ("empresa", 799.0, "empresa")
    assert d["fatura_aberta"]["valor"] == 799.0
    put, = pedidos(asaas_falso, "PUT", f"/subscriptions/{sid}")
    assert json.loads(put.content) == {"value": 799.0, "description": "Toqqi – plano Empresa",
                                       "updatePendingPayments": True}
    encher_contatos(dono, conta, 0)
    assert client.post(f"{API}/contatos", headers=h, json={"nome": "Cabe", "email": "c@y.com.br"}).status_code == 201
    assert sql(dono, "select detalhe from auditoria where evento = 'plano_alterado'") == [
        ({"de": "profissional", "para": "empresa"},)]
    # menor e cabe: o limite vale na hora
    sql(dono, "update contatos set ativo = false where conta_id = :c", c=conta)
    encher_contatos(dono, conta, 0)
    assert trocar_plano(client, h, "essencial").status_code == 200
    assert sql(dono, "select limite_contatos(plano, situacao) from contas where id = :c", c=conta) == [(300,)]


def test_trocar_de_plano_com_asaas_fora_nao_muda_nada(client, admin, dono, asaas_falso):
    h = admin["h"]
    assinar(client, h, "profissional")
    asaas_falso.falhar(httpx.Response(502), "PUT", "/subscriptions")
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 503
    assert sql(dono, "select a.plano, a.valor, c.plano from assinaturas a join contas c on c.id = a.conta_id") == [
        ("profissional", 349, "profissional")]


def test_trocar_de_plano_falha_ao_gravar_volta_o_valor_no_asaas(client, admin, asaas_falso, monkeypatch):
    from toqqi.modulos.assinatura import servico

    assinar(client, admin["h"], "profissional")
    def quebrar(*_a, **_k):
        raise RuntimeError("banco caiu")

    monkeypatch.setattr(servico, "recalcular", quebrar)
    with pytest.raises(RuntimeError):  # o TestClient repassa o erro (a API responde 500)
        trocar_plano(client, admin["h"], "empresa")
    assert asaas_falso.assinatura()["value"] == 349.0
    assert asaas_falso.assinatura()["description"] == "Toqqi – plano Profissional"


def test_dados_de_cobranca(client, admin, dono, asaas_falso):
    h = admin["h"]
    r = client.put(f"{API}/assinatura/dados", headers=h, json=DADOS_COBRANCA)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "sem_assinatura"
    assinar(client, h)
    cliente = asaas_falso.assinatura()["customer"]
    antes = len(asaas_falso.pedidos)
    # sem mudança (o e-mail não diferencia maiúsculas): não chama o Asaas nem audita
    assert client.put(f"{API}/assinatura/dados", headers=h,
                      json={**DADOS_COBRANCA, "email_cobranca": "FINANCEIRO@alfa.com.br"}).status_code == 200
    assert len(asaas_falso.pedidos) == antes
    novos = {**DADOS_COBRANCA, "documento": "529.982.247-25", "email_cobranca": "contas@alfa.com.br"}
    r = client.put(f"{API}/assinatura/dados", headers=h, json=novos)
    assert r.status_code == 200, r.text
    assert r.json()["assinatura"]["dados"] == {"razao_social": "Alfa Distribuidora Ltda", "documento": "52998224725",
                                               "email_cobranca": "contas@alfa.com.br", "telefone": "5511987654321"}
    assert (asaas_falso.dados["clientes"][cliente]["cpfCnpj"],
            asaas_falso.dados["clientes"][cliente]["email"]) == ("52998224725", "contas@alfa.com.br")
    assert sql(dono, "select detalhe from auditoria where evento = 'dados_cobranca_alterados'") == [
        ({"campos": ["documento", "email_cobranca"]},)]  # só os nomes dos campos
    # o Asaas recusa: 422 no campo e nada muda aqui
    asaas_falso.falhar(httpx.Response(400, json={"errors": [{"code": "invalid_email", "description": "x"}]}),
                       "PUT", "/customers")
    r = client.put(f"{API}/assinatura/dados", headers=h, json={**novos, "email_cobranca": "outro@alfa.com.br"})
    assert r.status_code == 422 and list(r.json()["erro"]["campos"]) == ["email_cobranca"]
    assert sql(dono, "select email_cobranca from assinaturas") == [("contas@alfa.com.br",)]


# ---- cancelar e assinar de novo -------------------------------------------------------------------

def test_cancelar_no_teste_volta_ao_teste(client, admin, dono, asaas_falso, monkeypatch):
    h, conta = admin["h"], admin["conta"]["id"]
    assert client.post(f"{API}/assinatura/cancelar", headers=h).json()["erro"]["codigo"] == "sem_assinatura"
    assinar(client, h)
    sid, pid = asaas_falso.assinatura()["id"], asaas_falso.cobrancas()[0]["id"]
    r = client.post(f"{API}/assinatura/cancelar", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["assinatura"] is None and d["fatura_aberta"] is None
    assert (d["conta"]["situacao"], d["conta"]["liberada"]) == ("teste", True)
    assert d["conta"]["pausa_em"] == "2026-10-15T17:30:00+00:00"  # volta ao fim do teste (sem o dia do vencimento)
    assert d["cobrancas"][0]["situacao"] == "removida"
    assert asaas_falso.dados["assinaturas"][sid]["deleted"] and asaas_falso.dados["cobrancas"][pid]["deleted"]
    assert sql(dono, "select situacao, cancelada_por is not null, cancelada_em is not null from assinaturas") == [
        ("cancelada", True, True)]
    assert situacao_conta(dono, conta) == ("teste", None, None, None)
    assert sql(dono, "select gravidade, detalhe from auditoria where evento = 'assinatura_cancelada'") == [
        ("atencao", {"plano": "profissional"})]
    # o teste acaba: a tarefa marca teste_expirado
    fixar_relogio(monkeypatch, momento("2026-10-15", 15))
    assert tarefas.executar("assinaturas")["assinaturas"]["testes_expirados"] == 1
    assert situacao_conta(dono, conta)[0] == "teste_expirado"


def test_cancelar_pago_usa_ate_o_fim_do_periodo(client, admin, dono, asaas_falso, monkeypatch):
    h, conta = admin["h"], admin["conta"]["id"]
    assinar(client, h)
    pagar_tudo(asaas_falso, "CREDIT_CARD")  # cartão: CONFIRMED já vale
    fixar_relogio(monkeypatch, momento("2026-10-20"))
    assert situacao_conta(dono, conta)[:2] == ("ativa", date(2026, 11, 14))
    d = client.post(f"{API}/assinatura/cancelar", headers=h).json()
    assert (d["conta"]["situacao"], d["conta"]["liberada"], d["conta"]["pausa_em"]) == (
        "cancelada", True, "2026-11-15T03:00:00+00:00")
    assert d["cobrancas"][0]["situacao"] == "paga" and d["cobrancas"][0]["forma"] == "cartao"
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]["aviso"] == {
        "tipo": "cancelada", "data": "2026-11-14", "dias": 25}
    fixar_relogio(monkeypatch, momento("2026-11-15", 0))
    cobranca = client.get(f"{API}/eu", headers=h).json()["conta"]["cobranca"]
    assert (cobranca["liberada"], cobranca["aviso"]) == (
        False, {"tipo": "cancelada_encerrada", "data": "2026-11-14", "dias": None})
    assert client.get(f"{API}/envios/pre-condicoes", headers=h).json()["itens"][0]["mensagem"] == (
        "A assinatura foi cancelada e o período pago terminou. Assine um plano para voltar a enviar.")


def test_cancelar_com_asaas_fora_nao_muda_nada(client, admin, dono, asaas_falso):
    assinar(client, admin["h"])
    asaas_falso.falhar(httpx.Response(500), "DELETE", "/subscriptions")
    r = client.post(f"{API}/assinatura/cancelar", headers=admin["h"])
    assert r.status_code == 503 and r.json()["erro"]["codigo"] == "cobranca_indisponivel"
    assert sql(dono, "select situacao from assinaturas") == [("ativa",)]
    assert asaas_falso.assinatura()["deleted"] is False
    # já removida no Asaas (404): cancela aqui também
    asaas_falso.falhar(httpx.Response(404), "DELETE", "/subscriptions")
    assert client.post(f"{API}/assinatura/cancelar", headers=admin["h"]).status_code == 200
    assert sql(dono, "select situacao from assinaturas") == [("cancelada",)]


def test_assinar_de_novo_depois_do_periodo_pago(client, admin, dono, asaas_falso, monkeypatch):
    h, conta = admin["h"], admin["conta"]["id"]
    assinar(client, h)
    pagar_tudo(asaas_falso)
    client.post(f"{API}/assinatura/cancelar", headers=h)
    fixar_relogio(monkeypatch, momento("2026-12-01"))  # o período pago acabou em 14/11
    r = assinar(client, h, "essencial")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["assinatura"]["primeiro_vencimento"] == "2026-12-02"  # amanhã
    assert (d["conta"]["situacao"], d["conta"]["liberada"]) == ("cancelada", False)  # volta quando pagar
    assert [c["situacao"] for c in d["cobrancas"]] == ["pendente", "paga"]
    pagar_tudo(asaas_falso, "BOLETO")
    assert situacao_conta(dono, conta) == ("ativa", date(2027, 1, 1), None, date(2026, 12, 2))
    assert sql(dono, "select situacao from assinaturas order by id") == [("cancelada",), ("ativa",)]


# ---- avisos em /eu e no login -----------------------------------------------------------------------

@pytest.mark.parametrize("situacao,campos,aviso,liberada", [
    ("teste", {"teste_ate": "2026-10-15 14:30-03"}, {"tipo": "teste_acabando", "data": "2026-10-15", "dias": 5},
     True),
    ("teste", {"teste_ate": "2026-10-25 14:30-03"}, None, True),
    ("teste", {"teste_ate": "2026-10-09 14:30-03"}, {"tipo": "teste_expirado", "data": "2026-10-09", "dias": None},
     False),
    ("teste_expirado", {"teste_ate": "2026-10-09 14:30-03"},
     {"tipo": "teste_expirado", "data": "2026-10-09", "dias": None}, False),
    ("atrasada", {"atrasada_desde": "2026-10-05"}, {"tipo": "atrasada", "data": "2026-10-13", "dias": 3}, True),
    ("atrasada", {"atrasada_desde": "2026-10-02"}, {"tipo": "pausada", "data": "2026-10-02", "dias": None}, False),
    ("cancelada", {"pago_ate": "2026-10-14", "teste_ate": "2026-09-01 10:00-03"},
     {"tipo": "cancelada", "data": "2026-10-14", "dias": 4}, True),
    ("cancelada", {"pago_ate": "2026-10-09", "teste_ate": "2026-09-01 10:00-03"},
     {"tipo": "cancelada_encerrada", "data": "2026-10-09", "dias": None}, False),
    ("cancelada", {"pago_ate": "2026-10-09"},  # o teste vai além do período pago: liberada até o fim dele
     {"tipo": "teste_acabando", "data": "2026-10-15", "dias": 5}, True),
    ("ativa", {"pago_ate": "2026-10-09"}, None, True),
    ("cortesia", {}, None, True),
])
def test_avisos_no_eu_e_no_login(client, admin, dono, situacao, campos, aviso, liberada):
    sets = ", ".join(f"{k} = :{k}" for k in campos)
    sql(dono, f"update contas set situacao = :s{', ' + sets if sets else ''} where id = :c", s=situacao,
        c=admin["conta"]["id"], **campos)
    cobranca = client.get(f"{API}/eu", headers=admin["h"]).json()["conta"]["cobranca"]
    assert (cobranca["aviso"], cobranca["liberada"]) == (aviso, liberada)
    assert set(cobranca) == {"liberada", "assinada", "pago_ate", "atrasada_desde", "pausa_em", "aviso", "exclusao_em"}
    assert entrar(client, "ana@alfa.com.br").json()["conta"]["cobranca"] == cobranca


def test_login_traz_a_cobranca(client, admin):
    assert entrar(client, "ana@alfa.com.br").json()["conta"]["cobranca"] == {
        "liberada": True, "assinada": False, "pago_ate": None, "atrasada_desde": None, "pausa_em": "2026-10-15T17:30:00+00:00",
        "aviso": {"tipo": "teste_acabando", "data": "2026-10-15", "dias": 5}, "exclusao_em": None}


def test_conta_sem_chave_continua_funcionando(client, admin, monkeypatch):
    monkeypatch.setattr(config(), "ASAAS_API_KEY", "")
    assert client.get(f"{API}/eu", headers=admin["h"]).status_code == 200
    assert estado(client, admin["h"])["disponivel"] is False


# ---- correções da revisão: tempo esgotado, conciliação, CNPJ alfanumérico, telefone --------------------------------

@pytest.mark.parametrize("telefone,guardado,campos", [
    ("(11) 4000-1234", "551140001234", ("", "1140001234")),  # fixo de 2 a 5
    ("(21) 5432-1098", "552154321098", ("", "2154321098")),
    ("+55 99 99876-5432", "5599998765432", ("99998765432", "")),
    ("(11) 8765-4321", "5511987654321", ("11987654321", "")),  # celular antigo, sem o 9: ganha o 9
])
def test_telefones_do_brasil_aceitos(client, admin, asaas_falso, telefone, guardado, campos):
    r = assinar(client, admin["h"], telefone=telefone)
    assert r.status_code == 201, r.text
    assert r.json()["assinatura"]["dados"]["telefone"] == guardado
    cliente = json.loads(pedidos(asaas_falso, "POST", "/customers")[0].content)
    assert (cliente["mobilePhone"], cliente["phone"]) == campos


def test_trocar_celular_por_fixo_apaga_o_celular_no_asaas(client, admin, asaas_falso):
    h = admin["h"]
    assinar(client, h)
    cliente = asaas_falso.assinatura()["customer"]
    assert asaas_falso.dados["clientes"][cliente]["mobilePhone"] == "11987654321"
    r = client.put(f"{API}/assinatura/dados", headers=h, json={**DADOS_COBRANCA, "telefone": "(11) 4000-1234"})
    assert r.status_code == 200, r.text
    put = json.loads(pedidos(asaas_falso, "PUT", f"/customers/{cliente}")[-1].content)
    assert (put["mobilePhone"], put["phone"]) == ("", "1140001234")
    assert (asaas_falso.dados["clientes"][cliente]["mobilePhone"],
            asaas_falso.dados["clientes"][cliente]["phone"]) == ("", "1140001234")
    r = client.put(f"{API}/assinatura/dados", headers=h, json=DADOS_COBRANCA)  # e de volta
    put = json.loads(pedidos(asaas_falso, "PUT", f"/customers/{cliente}")[-1].content)
    assert (put["mobilePhone"], put["phone"]) == ("11987654321", "")


def test_cnpj_alfanumerico_na_assinatura(client, admin, asaas_falso):
    r = assinar(client, admin["h"], documento="12.abc.345/01de-35")
    assert r.status_code == 201, r.text
    assert r.json()["assinatura"]["dados"]["documento"] == "12ABC34501DE35"
    assert asaas_falso.dados["clientes"][asaas_falso.assinatura()["customer"]]["cpfCnpj"] == "12ABC34501DE35"


def test_tempo_esgotado_ao_criar_o_cliente_reaproveita_o_que_o_asaas_criou(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "POST", "/customers", depois=True)
    r = assinar(client, h)
    assert r.status_code == 201, r.text
    cliente, = asaas_falso.dados["clientes"]  # um só: achado de novo pela referência da conta
    assert asaas_falso.assinatura()["customer"] == cliente
    assert sql(dono, "select asaas_cliente_id, asaas_ambiente from contas where id = :c", c=conta) == [
        (cliente, "sandbox")]


def test_cliente_da_conta_ja_no_asaas_e_reaproveitado(client, admin, dono, asaas_falso):
    """O id do cliente se perdeu (a gravação da 1ª fase falhou, por exemplo): a busca pela referência acha o cliente
    e o atualiza, sem criar outro."""
    conta = admin["conta"]["id"]
    existente = asaas_falso.http.post("/v3/customers", headers={"access_token": "x"}, json={
        "name": "Nome antigo", "cpfCnpj": "52998224725", "email": "velho@alfa.com.br", "mobilePhone": "11911112222",
        "phone": "", "externalReference": f"toqqi-conta-{conta}"}).json()["id"]
    assert assinar(client, admin["h"]).status_code == 201
    assert pedidos(asaas_falso, "POST", "/customers") == []
    assert list(asaas_falso.dados["clientes"]) == [existente]
    assert asaas_falso.dados["clientes"][existente]["name"] == "Alfa Distribuidora Ltda"
    assert asaas_falso.assinatura()["customer"] == existente


def test_tempo_esgotado_ao_criar_a_assinatura_adota_a_que_o_asaas_criou(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "POST", "/subscriptions", depois=True)
    r = assinar(client, h, "essencial")
    assert r.status_code == 201, r.text
    sub, = asaas_falso.vivas()  # nunca duas
    assert sql(dono, "select asaas_id, ambiente, plano, situacao from assinaturas") == [
        (sub["id"], "sandbox", "essencial", "ativa")]
    d = r.json()
    assert d["assinatura"]["primeiro_vencimento"] == "2026-10-15" and d["fatura_aberta"]["vencimento"] == "2026-10-15"
    assert situacao_conta(dono, conta) == ("teste", None, None, date(2026, 10, 15))
    assert len(pedidos(asaas_falso, "POST", "/subscriptions")) == 1


def test_tempo_esgotado_sem_conseguir_listar_e_adotada_no_proximo_assinar(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "POST", "/subscriptions", depois=True)
    asaas_falso.falhar(httpx.Response(503), "GET", "/subscriptions", pular=1)  # a lista depois do tempo esgotado
    r = assinar(client, h)
    assert r.status_code == 503 and r.json()["erro"]["codigo"] == "cobranca_indisponivel"
    orfa, = asaas_falso.vivas()  # criada lá, desconhecida aqui
    assert sql(dono, "select count(*) from assinaturas")[0][0] == 0
    # a conta fica marcada para a conferência conciliar (se ninguém tentar de novo)
    assert sql(dono, "select asaas_conferida_em from contas where id = :c", c=conta) == [(None,)]
    # tentou de novo, o mesmo plano: adota a que já existe (sem criar outra)
    r = assinar(client, h)
    assert r.status_code == 201, r.text
    assert [a["id"] for a in asaas_falso.vivas()] == [orfa["id"]]
    assert len(pedidos(asaas_falso, "POST", "/subscriptions")) == 1
    assert sql(dono, "select asaas_id, plano from assinaturas") == [(orfa["id"], "profissional")]


def test_tempo_esgotado_sem_criar_responde_503(client, admin, dono, asaas_falso):
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "POST", "/subscriptions")  # não chegou ao Asaas
    r = assinar(client, admin["h"])
    assert r.status_code == 503
    assert asaas_falso.vivas() == [] and sql(dono, "select count(*) from assinaturas")[0][0] == 0
    assert assinar(client, admin["h"]).status_code == 201
    assert len(asaas_falso.vivas()) == 1


def test_assinar_com_outro_plano_remove_a_que_sobrou_de_antes(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "POST", "/subscriptions", depois=True)
    asaas_falso.falhar(httpx.Response(503), "GET", "/subscriptions", pular=1)
    assert assinar(client, h, "essencial").status_code == 503
    orfa, = asaas_falso.vivas()
    r = assinar(client, h, "empresa")  # outro valor: a de antes sai, uma nova entra
    assert r.status_code == 201, r.text
    nova, = asaas_falso.vivas()
    assert nova["id"] != orfa["id"] and nova["value"] == 799.0
    assert asaas_falso.dados["assinaturas"][orfa["id"]]["deleted"] is True
    assert sql(dono, "select asaas_id, plano from assinaturas") == [(nova["id"], "empresa")]
    assert sql(dono, "select detalhe from auditoria where conta_id = :c and evento = 'assinatura_removida_no_asaas'",
               c=conta) == [({"motivo": "duplicada", "valor": "149.00"},)]


def test_remover_a_que_sobrou_falha_responde_503_e_fica_para_a_tarefa(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "POST", "/subscriptions", depois=True)
    asaas_falso.falhar(httpx.Response(503), "GET", "/subscriptions", pular=1)
    assert assinar(client, h, "essencial").status_code == 503
    orfa, = asaas_falso.vivas()
    asaas_falso.falhar(httpx.Response(503), "DELETE", "/subscriptions")
    assert assinar(client, h, "empresa").status_code == 503  # sem remover a que sobrou, não cria outra
    assert [a["id"] for a in asaas_falso.vivas()] == [orfa["id"]]
    assert sql(dono, "select asaas_id, conta_id, motivo from asaas_remocoes") == [(orfa["id"], conta, "duplicada")]


def test_gravacao_falha_e_a_remocao_tambem_fica_para_a_tarefa(client, admin, dono, asaas_falso, monkeypatch):
    from toqqi.modulos.assinatura import servico

    def quebrar(*_a, **_k):
        raise RuntimeError("banco caiu")

    monkeypatch.setattr(servico, "recalcular", quebrar)
    asaas_falso.falhar(httpx.Response(502), "DELETE", "/subscriptions")
    with pytest.raises(RuntimeError):
        assinar(client, admin["h"])
    sub, = asaas_falso.vivas()
    assert sql(dono, "select asaas_id, motivo, removida_em is null from asaas_remocoes") == [
        (sub["id"], "gravacao_falhou", True)]


def test_trocar_de_plano_com_tempo_esgotado_e_o_valor_ja_mudado_la(client, admin, dono, asaas_falso):
    h = admin["h"]
    assinar(client, h, "profissional")
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "PUT", "/subscriptions", depois=True)
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 200, r.text  # o GET mostrou o valor novo: conclui aqui
    assert (r.json()["assinatura"]["plano"], r.json()["conta"]["plano"]) == ("empresa", "empresa")
    assert asaas_falso.assinatura()["value"] == 799.0
    assert sql(dono, "select detalhe from auditoria where evento = 'plano_alterado'") == [
        ({"de": "profissional", "para": "empresa"},)]


def test_trocar_de_plano_com_tempo_esgotado_sem_mudar_la_responde_503(client, admin, dono, asaas_falso):
    h = admin["h"]
    assinar(client, h, "profissional")
    asaas_falso.falhar(httpx.ReadTimeout("lento"), "PUT", "/subscriptions")
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 503
    assert asaas_falso.assinatura()["value"] == 349.0
    assert sql(dono, "select a.plano, c.plano from assinaturas a join contas c on c.id = a.conta_id") == [
        ("profissional", "profissional")]


def test_cancelar_no_teste_sem_pagar_volta_ao_plano_do_teste(client, admin, dono, asaas_falso):
    h, conta = admin["h"], admin["conta"]["id"]
    assinar(client, h, "essencial")
    assert sql(dono, "select plano from contas where id = :c", c=conta) == [("essencial",)]
    d = client.post(f"{API}/assinatura/cancelar", headers=h).json()
    assert (d["conta"]["situacao"], d["conta"]["plano"]) == ("teste", "profissional")
    # quem já pagou fica com o plano que pagou
    assinar(client, h, "empresa")
    pagar_tudo(asaas_falso)
    d = client.post(f"{API}/assinatura/cancelar", headers=h).json()
    assert (d["conta"]["situacao"], d["conta"]["plano"]) == ("cancelada", "empresa")
