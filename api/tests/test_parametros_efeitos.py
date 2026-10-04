"""Etapa 5g: o efeito de cada parâmetro no que já está rodando — limite de contatos (banco e API, na hora), preço
(assinar e trocar com o preço atual; a assinatura antiga mantém o contratado, também na conferência; `preco_mudou`;
adoção só pelo preço atual), IA (cotas, análises por nível, modelo e esforço), teto e franquia abaixo do uso, teste
(dias e plano no cadastro, na Plataforma e no "+N dias"), modo da exclusão automática e as marcas da Ajuda."""
import json
import logging
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import text
from util import (
    API,
    DADOS_COBRANCA,
    FUSO,
    assinar,
    conectar_whatsapp,
    conta_pronta,
    criar_contato,
    criar_empresa,
    definir_plano,
    emails_para,
    encher_contatos,
    evento,
    fixar_relogio,
    form_padrao,
    gerar_chave,
    gerar_ia,
    gravar_parametro,
    grupo_parametros,
    inserir_resposta,
    ligar_envios,
    perguntar,
    registrar_resposta,
    salvar_parametros,
    sem_passos,
    sql,
    superadmin,
    trocar_plano,
    usar_cota,
)

from toqqi import tarefas
from toqqi.core import ia_texto, parametros, relogio
from toqqi.core.config import config
from toqqi.core.db import em_conta
from toqqi.modelos import Conta
from toqqi.modulos.ajuda import servico as ajuda
from toqqi.modulos.assinatura import conferencia
from toqqi.modulos.ia import cota


@pytest.fixture
def root(client):
    return superadmin(client)


@pytest.fixture
def ana(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _salvar(client, root, grupo: str, mudancas: dict) -> dict:
    r = salvar_parametros(client, root["h"], grupo, mudancas)
    assert r.status_code == 200, r.text
    return r.json()


# ---- limite de contatos ------------------------------------------------------------------------------------

CSV = "Nome;E-mail\r\nPaula Lima;paula@norte.com.br\r\n".encode("utf-8-sig")


def test_limite_de_contatos_na_hora(client, root, ana, dono):
    h, c = ana["h"], ana["conta"]["id"]
    definir_plano(dono, c, "essencial")
    _salvar(client, root, "planos", {"planos.essencial.contatos": 2, "planos.profissional.contatos": 3,
                                     "planos.empresa.contatos": 5})
    primeiro = criar_contato(client, h)
    criar_contato(client, h)
    erro = {"codigo": "limite_do_plano", "mensagem": "Seu plano permite até 2 contatos ativos.",
            "campos": {"limite": "2"}}
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Terceiro", "email": "t@y.com.br"})
    assert r.status_code == 402 and r.json()["erro"] == erro
    # importar
    d = client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": ("c.csv", CSV)}).json()
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email"}
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 402 and r.json()["erro"]["codigo"] == "limite_do_plano"
    # reativar
    client.patch(f"{API}/contatos/{primeiro['id']}", headers=h, json={"ativo": False})
    criar_contato(client, h)
    r = client.patch(f"{API}/contatos/{primeiro['id']}", headers=h, json={"ativo": True})
    assert r.status_code == 402 and r.json()["erro"] == erro
    # no banco, em conta (o gatilho lê a linha pela política `ler_limites`)
    with em_conta(c) as s:
        assert s.scalar(text("select limite_contatos(plano, situacao) from contas")) == 2
    # Empresa com 5: vale; sem limite: libera
    definir_plano(dono, c, "empresa")
    encher_contatos(dono, c, 3)
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Sexto", "email": "s@y.com.br"})
    assert r.status_code == 402 and r.json()["erro"]["campos"] == {"limite": "5"}
    _salvar(client, root, "planos", {"planos.empresa.contatos": None})
    assert client.post(f"{API}/contatos", headers=h, json={"nome": "Sexto", "email": "s@y.com.br"}).status_code == 201
    # cortesia nunca tem limite
    definir_plano(dono, c, "essencial", "cortesia")
    assert client.post(f"{API}/contatos", headers=h, json={"nome": "Z", "email": "z@y.com.br"}).status_code == 201
    # GET /assinatura/planos acompanha
    planos = client.get(f"{API}/assinatura/planos", headers=h).json()
    assert [p["contatos"] for p in planos] == [2, 3, None]


def test_troca_de_plano_usa_o_limite_novo(client, root, ana, dono, asaas_falso, relogio_estavel):
    h, c = ana["h"], ana["conta"]["id"]
    assert assinar(client, h, "empresa").status_code == 201
    encher_contatos(dono, c, 3)
    _salvar(client, root, "planos", {"planos.essencial.contatos": 2})
    r = trocar_plano(client, h, "essencial")
    assert r.status_code == 422 and r.json()["erro"]["mensagem"] == (
        "Você tem 3 contatos ativos; o plano Essencial permite até 2. Desative contatos antes de trocar.")


# ---- preço -------------------------------------------------------------------------------------------------

def _assinatura_da(asaas_falso, conta_id: int) -> dict:
    vivas = [a for a in asaas_falso.dados["assinaturas"].values()
             if a["externalReference"] == f"toqqi-conta-{conta_id}" and not a["deleted"]]
    assert len(vivas) == 1, vivas
    return vivas[0]


def _valores_no_asaas(asaas_falso) -> list[float]:
    return [json.loads(p.content)["value"] for p in asaas_falso.pedidos
            if p.method in ("POST", "PUT") and "/subscriptions" in p.url.path and p.content]


def test_preco_novo_so_para_assinar_e_trocar(client, root, ana, dono, asaas_falso, relogio_estavel):
    h = ana["h"]
    antiga = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert assinar(client, antiga["h"], "profissional").status_code == 201  # antes do reajuste: 349
    _salvar(client, root, "planos", {"planos.profissional.preco": "399.00"})
    assert [p["preco"] for p in client.get(f"{API}/assinatura/planos", headers=h).json()] == [149.0, 399.0, 799.0]
    assert client.get(f"{API}/publico/planos").json()["planos"][1]["preco"] == 399.0
    assert [p["preco"] for p in client.get(f"{API}/assinatura", headers=h).json()["planos"]] == [149.0, 399.0, 799.0]
    # a tela mostrou o preço antigo: 409 antes de chamar o Asaas
    asaas_falso.pedidos.clear()
    r = assinar(client, h, "profissional", preco="349.00")
    assert r.status_code == 409 and r.json()["erro"] == {
        "codigo": "preco_mudou", "campos": {},
        "mensagem": "O preço do plano Profissional mudou para R$ 399,00. Confira e confirme de novo."}
    assert asaas_falso.pedidos == []
    r = assinar(client, h, "profissional", preco=399)
    assert r.status_code == 201 and r.json()["assinatura"]["valor"] == 399.0
    assert _assinatura_da(asaas_falso, ana["conta"]["id"])["value"] == 399.0
    # trocar: o preço atual do plano novo
    _salvar(client, root, "planos", {"planos.empresa.preco": "899.00"})
    asaas_falso.pedidos.clear()
    r = client.put(f"{API}/assinatura/plano", headers=h, json={"plano": "empresa", "preco": "799.00"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "preco_mudou" and asaas_falso.pedidos == []
    r = client.put(f"{API}/assinatura/plano", headers=h, json={"plano": "empresa", "preco": "899.00"})
    assert r.status_code == 200 and r.json()["assinatura"]["valor"] == 899.0
    assert _valores_no_asaas(asaas_falso) == [899.0]
    # a assinatura antiga mantém o contratado (e as faturas); trocar para o mesmo plano não muda nada
    b = antiga["conta"]["id"]
    assert sql(dono, "select valor from assinaturas where conta_id = :c", c=b) == [(349,)]
    assert {v for (v,) in sql(dono, "select valor from cobrancas where conta_id = :c", c=b)} == {349}
    asaas_falso.pedidos.clear()
    r = trocar_plano(client, antiga["h"], "profissional")
    assert r.status_code == 200 and r.json()["assinatura"]["valor"] == 349.0 and asaas_falso.pedidos == []


def test_conferencia_volta_ao_contratado_e_nunca_ao_preco_atual(client, root, ana, dono, asaas_falso,
                                                                relogio_estavel):
    c = ana["conta"]["id"]
    assert assinar(client, ana["h"], "profissional").status_code == 201
    _salvar(client, root, "planos", {"planos.profissional.preco": "399.00"})
    asaas_falso.pedidos.clear()
    assert conferencia.conferir_conta(c) == "ok"
    assert _valores_no_asaas(asaas_falso) == []  # no contratado: nada a corrigir
    sid = _assinatura_da(asaas_falso, c)["id"]
    asaas_falso.dados["assinaturas"][sid]["value"] = 399.0  # alguém pôs o preço novo no painel do Asaas
    assert conferencia.conferir_conta(c) == "ok"
    assert _assinatura_da(asaas_falso, c)["value"] == 349.0
    assert sql(dono, "select detalhe from auditoria where evento = 'valor_realinhado'") == [
        ({"plano": "profissional", "de": "399.00", "para": "349.00"},)]
    assert sql(dono, "select valor from assinaturas") == [(349,)]


def test_adocao_so_pelo_preco_atual(client, root, ana, dono, asaas_falso, relogio_estavel):
    c = ana["conta"]["id"]
    _salvar(client, root, "planos", {"planos.profissional.preco": "399.00"})
    velha = asaas_falso.criar_direto(c, valor=349.0)  # preço antigo: não é adotada
    sql(dono, "update contas set asaas_cliente_id = :k, asaas_ambiente = 'sandbox' where id = :i",
        k=velha["customer"], i=c)
    assert conferencia.conferir_conta(c) == "ok"
    assert sql(dono, "select count(*) from assinaturas") == [(0,)]
    assert asaas_falso.dados["assinaturas"][velha["id"]]["deleted"] is True
    assert sql(dono, "select detalhe->>'motivo' from auditoria where evento = 'assinatura_removida_no_asaas'") == [
        ("nao_adotada",)]
    nova = asaas_falso.criar_direto(c, valor=399.0, descricao="Toqqi – plano Profissional")
    assert conferencia.conferir_conta(c) == "ok"
    assert sql(dono, "select asaas_id, plano, valor from assinaturas") == [(nova["id"], "profissional", 399)]


def test_adocao_pelo_valor_e_pela_descricao_do_plano(client, root, ana, dono, asaas_falso, relogio_estavel):
    """Entre mudanças de preço, o valor de um plano pode virar o de outro: a assinatura viva no Asaas só é adotada
    quando o valor (preço atual) e a descrição são do mesmo plano; senão sai como `nao_adotada`."""
    c = ana["conta"]["id"]
    velha = asaas_falso.criar_direto(c, valor=149.0)  # "Toqqi – plano Essencial", criada antes da mudança
    sql(dono, "update contas set asaas_cliente_id = :k, asaas_ambiente = 'sandbox' where id = :i",
        k=velha["customer"], i=c)
    _salvar(client, root, "planos", {"planos.essencial.preco": "99.00", "planos.profissional.preco": "149.00"})
    assert conferencia.conferir_conta(c) == "ok"
    assert sql(dono, "select count(*) from assinaturas") == [(0,)]  # não virou uma do Profissional
    assert asaas_falso.dados["assinaturas"][velha["id"]]["deleted"] is True
    assert sql(dono, "select detalhe->>'motivo' from auditoria where evento = 'assinatura_removida_no_asaas'") == [
        ("nao_adotada",)]
    nova = asaas_falso.criar_direto(c, valor=149.0, descricao="Toqqi – plano Profissional")
    assert conferencia.conferir_conta(c) == "ok"
    assert sql(dono, "select asaas_id, plano, valor from assinaturas") == [(nova["id"], "profissional", 149)]


def test_assinar_nao_adota_a_de_outro_plano_com_o_mesmo_valor(client, root, ana, asaas_falso, relogio_estavel):
    """Ao assinar, a desconhecida só é adotada com o valor e a descrição do plano pedido; a do Essencial com o valor
    que hoje é o do Profissional sai (duplicada) e a nova é criada."""
    h, c = ana["h"], ana["conta"]["id"]
    orfa = asaas_falso.criar_direto(c, valor=149.0)  # do Essencial, de um pedido que esgotou o tempo
    _salvar(client, root, "planos", {"planos.essencial.preco": "99.00", "planos.profissional.preco": "149.00"})
    r = assinar(client, h, "profissional")
    assert r.status_code == 201, r.text
    assert asaas_falso.dados["assinaturas"][orfa["id"]]["deleted"] is True
    nova = _assinatura_da(asaas_falso, c)
    assert nova["id"] != orfa["id"] and (nova["value"], nova["description"]) == (149.0, "Toqqi – plano Profissional")
    assert r.json()["assinatura"]["plano"] == "profissional"


def test_preco_e_obrigatorio_ao_assinar_e_ao_trocar(client, ana, dono, asaas_falso, relogio_estavel):
    """Sem `preco` (ou com null), 422 no campo antes de chamar o Asaas: quem não manda o preço que viu escaparia do
    `preco_mudou`."""
    h = ana["h"]
    erro = {"codigo": "dados_invalidos", "mensagem": "Confira os campos destacados.",
            "campos": {"preco": "Recarregue a página para ver o preço atual do plano."}}
    for extra in ({}, {"preco": None}):
        r = client.post(f"{API}/assinatura", headers=h, json={"plano": "profissional", **DADOS_COBRANCA, **extra})
        assert r.status_code == 422 and r.json()["erro"] == erro, r.text
    assert asaas_falso.pedidos == [] and sql(dono, "select count(*) from assinaturas") == [(0,)]
    assert assinar(client, h, "profissional").status_code == 201  # com o preço que a tela mostrou
    asaas_falso.pedidos.clear()
    for extra in ({}, {"preco": None}):
        r = client.put(f"{API}/assinatura/plano", headers=h, json={"plano": "empresa", **extra})
        assert r.status_code == 422 and r.json()["erro"] == erro, r.text
    assert asaas_falso.pedidos == []
    r = trocar_plano(client, h, "empresa")
    assert r.status_code == 200 and r.json()["assinatura"]["plano"] == "empresa"


# ---- IA ----------------------------------------------------------------------------------------------------

def test_cotas_e_analises_por_nivel(client, root, ana, dono):
    h, c = ana["h"], ana["conta"]["id"]
    definir_plano(dono, c, "essencial")
    _salvar(client, root, "ia", {"ia.cota.essencial": 7, "ia.analises.detalhado": 3})
    d = client.get(f"{API}/conta/ia", headers=h).json()
    assert d["cota"]["limite"] == 7
    assert [(m["valor"], m["analises"], m["descricao"]) for m in d["modelos"]] == [
        ("rapido", 1, "Respostas curtas e rápidas. Gasta 1 análise da cota."),
        ("equilibrado", 1, "O padrão: bom para o dia a dia. Gasta 1 análise da cota."),
        ("detalhado", 3, "Análises mais cuidadosas; pode demorar mais. Gasta 3 análises da cota.")]
    sql(dono, "update contas set ia_modelo = 'detalhado' where id = :c", c=c)
    r = perguntar(client, h)
    assert r.status_code == 200 and r.json()["custo"] == 3
    usar_cota(dono, c, 5)  # restam 2: menos que o nível gasta
    r = perguntar(client, h)
    assert r.status_code == 409 and r.json()["erro"]["mensagem"].startswith(
        "Restam 2 análises e o nível Mais detalhado gasta 3.")
    # cortesia: a cota da cortesia
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=c)
    _salvar(client, root, "ia", {"ia.cota.cortesia": 9})
    assert client.get(f"{API}/conta/ia", headers=h).json()["cota"]["limite"] == 9


def test_devolucao_e_o_reservado_mesmo_depois_da_mudanca(client, root, ana, dono):
    c = ana["conta"]["id"]
    with em_conta(c) as s:
        reserva = cota.reservar(s, s.get(Conta, c), ia_texto.analises_do_nivel("detalhado"))
    assert reserva.quantidade == 2
    _salvar(client, root, "ia", {"ia.analises.detalhado": 1})
    assert ia_texto.analises_do_nivel("detalhado") == 1
    cota.devolver(reserva)
    assert sql(dono, "select cota_usada from ia_uso_mensal where conta_id = :c", c=c) == [(0,)]


def test_cota_abaixo_do_uso_fica_sem_saldo_ate_subir(client, root, ana, dono):
    h, c = ana["h"], ana["conta"]["id"]
    usar_cota(dono, c, 300)  # profissional (teste): 500
    _salvar(client, root, "ia", {"ia.cota.profissional": 200})
    r = perguntar(client, h)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "cota_esgotada"
    assert client.get(f"{API}/conta/ia", headers=h).json()["cota"]["restantes"] == 0
    _salvar(client, root, "ia", {"ia.cota.profissional": 302})
    assert perguntar(client, h).status_code == 200


def test_modelo_e_esforco_na_proxima_chamada(client, root, ana, dono):
    h, c = ana["h"], ana["conta"]["id"]
    empresa = criar_empresa(client, h, "Atacado Norte")
    contato = criar_contato(client, h, nome="Paula Lima", empresa_id=empresa["id"])
    inserir_resposta(dono, c, form_padrao(client, h)["id"], contato, 9, relogio.hoje(), comentario="Entrega rápida")
    _salvar(client, root, "ia", {"ia.modelo.equilibrado": "gpt-4.1-mini", "ia.esforco.equilibrado": ""})
    assert gerar_ia(client, h).status_code == 200
    corpo = ia_texto.memoria.corpos[-1]
    assert corpo["model"] == "gpt-4.1-mini" and "reasoning" not in corpo
    _salvar(client, root, "ia", {"ia.esforco.equilibrado": "high"})
    assert gerar_ia(client, h, tipo="relatorios").status_code == 200
    assert ia_texto.memoria.corpos[-1]["reasoning"] == {"effort": "high"}


def test_teto_abaixo_do_uso_fica_sem_saldo(client, root, ana, dono):
    h, c = ana["h"], ana["conta"]["id"]
    sem_passos(dono, c)
    definir_plano(dono, c, "essencial")
    contato = criar_contato(client, h)
    sql(dono, "insert into ia_uso_mensal (conta_id, mes, analises) values (:c, :m, 50)", c=c,
        m=relogio.hoje().replace(day=1))
    _salvar(client, root, "ia", {"ia.teto.essencial": 40})
    rid = registrar_resposta(client, h, contato["id"], 3, comentario="Frete caro").json()["id"]
    assert sql(dono, "select ia_situacao from respostas where id = :r", r=rid) == [("limite",)]
    assert client.get(f"{API}/conta/ia", headers=h).json()["limite"] == 40
    _salvar(client, root, "ia", {"ia.teto.essencial": 60})
    rid = registrar_resposta(client, h, contato["id"], 3, comentario="O vendedor sumiu").json()["id"]
    assert sql(dono, "select ia_situacao from respostas where id = :r", r=rid) == [("analisada",)]


def test_franquia_abaixo_do_uso_avisa_uma_vez(client, root, dono, meta, relogio_estavel):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h, c = a["h"], a["conta"]["id"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=c)
    assert conectar_whatsapp(client, h).status_code == 200
    ligar_envios(client, h, canal="whatsapp")
    chave = gerar_chave(client, h)
    sql(dono, "insert into whatsapp_uso (conta_id, mes, usadas, avisou_80) values (:c, :m, 150, true)", c=c,
        m=relogio.agora().strftime("%Y-%m"))
    _salvar(client, root, "whatsapp", {"whatsapp.franquia.cortesia": 100})
    assert client.get(f"{API}/integracoes/whatsapp", headers=h).json()["franquia"]["limite"] == 100
    r = evento(client, chave, telefone="11900000001", email="c1@cliente.com.br")
    assert r.json()["canal"] == "email"
    assunto = "A franquia de WhatsApp do mês acabou"
    assert [m.assunto for m in emails_para("ana@alfa.com.br")].count(assunto) == 1
    assert evento(client, chave, telefone="11900000002", email="c2@cliente.com.br").json()["canal"] == "email"
    assert [m.assunto for m in emails_para("ana@alfa.com.br")].count(assunto) == 1  # uma vez só
    _salvar(client, root, "whatsapp", {"whatsapp.franquia.cortesia": 200})  # subir libera na hora
    assert evento(client, chave, telefone="11900000003").json()["canal"] == "whatsapp"


# ---- teste e cortesia ------------------------------------------------------------------------------------------

def _data(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def test_conta_nova_com_os_dias_e_o_plano_do_teste(client, root, dono, monkeypatch):
    agora = datetime.combine(date(2026, 10, 3), time(14, 30), tzinfo=FUSO)
    fixar_relogio(monkeypatch, agora)
    andamento = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")  # teste em andamento: fica como está
    assert sql(dono, "select plano from contas where id = :c", c=andamento["conta"]["id"]) == [("profissional",)]
    _salvar(client, root, "teste", {"teste.dias": 7, "teste.plano": "essencial"})
    nova = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert sql(dono, "select plano, teste_ate from contas where id = :c", c=nova["conta"]["id"]) == [
        ("essencial", agora + timedelta(days=7))]
    assert sql(dono, "select plano, teste_ate from contas where id = :c", c=andamento["conta"]["id"]) == [
        ("profissional", agora + timedelta(days=14))]
    for situacao in ("teste", "cortesia"):
        r = client.post(f"{API}/plataforma/contas", headers=root["h"], json={
            "empresa": f"Gama {situacao}", "admin_nome": "Gui", "admin_email": f"gui@{situacao}.com.br",
            "admin_senha": "Senha@123", "situacao": situacao})
        assert r.status_code == 201 and r.json()["plano"] == "essencial"
        assert _data(r.json()["teste_ate"]) == (agora + timedelta(days=7) if situacao == "teste" else None)
    # "+N dias" sem `dias` no teste em andamento (criado antes da mudança): soma os dias do teste de hoje e o plano
    # continua o dele (o "+N" recalcula a conta)
    a = andamento["conta"]["id"]
    r = client.post(f"{API}/plataforma/contas/{a}/estender-teste", headers=root["h"])
    assert r.status_code == 200, r.text
    assert (r.json()["plano"], _data(r.json()["teste_ate"])) == ("profissional", agora + timedelta(days=14 + 7))
    r = client.post(f"{API}/plataforma/contas/{a}/estender-teste", headers=root["h"], json={"dias": 3})
    assert (r.json()["plano"], _data(r.json()["teste_ate"])) == ("profissional", agora + timedelta(days=24))
    assert sql(dono, "select plano, situacao from contas where id = :c", c=a) == [("profissional", "teste")]


def test_conferencia_e_virada_do_teste_nao_mudam_o_plano_do_teste_em_andamento(client, root, ana, dono, asaas_falso,
                                                                                relogio_estavel):
    """A conferência diária e a virada do teste recalculam a conta: o teste em andamento (e o que acabou) fica no
    plano com que começou, mesmo depois de mudar `teste.plano`."""
    c = ana["conta"]["id"]
    _salvar(client, root, "teste", {"teste.plano": "essencial"})
    assert conferencia.conferir_conta(c) == "ok"
    assert sql(dono, "select plano, situacao from contas where id = :c", c=c) == [("profissional", "teste")]
    sql(dono, "update contas set teste_ate = :t where id = :c", t=relogio.agora() - timedelta(hours=1), c=c)
    assert conferencia.recalcular_pelas_datas() == 1
    assert sql(dono, "select plano, situacao from contas where id = :c", c=c) == [("profissional", "teste_expirado")]


def test_quem_cancela_sem_nunca_pagar_volta_ao_plano_do_teste_atual(client, root, ana, dono, asaas_falso,
                                                                     relogio_estavel):
    h, c = ana["h"], ana["conta"]["id"]
    assert assinar(client, h, "empresa").status_code == 201
    _salvar(client, root, "teste", {"teste.plano": "essencial"})
    assert client.post(f"{API}/assinatura/cancelar", headers=h).status_code == 200
    assert sql(dono, "select plano, situacao from contas where id = :c", c=c) == [("essencial", "teste")]
    # de volta ao teste, é um teste em andamento: a mudança seguinte do plano do teste não o atinge
    _salvar(client, root, "teste", {"teste.plano": "empresa"})
    assert conferencia.conferir_conta(c) == "ok"
    assert sql(dono, "select plano from contas where id = :c", c=c) == [("essencial",)]


def test_assinatura_removida_no_asaas_sem_pagar_volta_ao_plano_do_teste_atual(client, root, ana, dono, asaas_falso,
                                                                               relogio_estavel):
    """A regra da 5a para quem perde a assinatura sem nunca ter pago (aqui, removida no painel do Asaas e achada pela
    conferência): volta ao plano do teste, o de hoje."""
    h, c = ana["h"], ana["conta"]["id"]
    assert assinar(client, h, "empresa").status_code == 201
    _salvar(client, root, "teste", {"teste.plano": "essencial"})
    asaas_falso.assinatura()["deleted"] = True
    assert conferencia.conferir_conta(c) == "ok"
    assert sql(dono, "select situacao from assinaturas") == [("cancelada",)]
    assert sql(dono, "select plano, situacao from contas where id = :c", c=c) == [("essencial", "teste")]


# ---- exclusão automática ----------------------------------------------------------------------------------

def _rodada(client, dono, monkeypatch) -> dict:
    hoje = date(2026, 10, 3)
    fixar_relogio(monkeypatch, datetime.combine(hoje, time(10), tzinfo=FUSO))
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    sql(dono, "update contas set situacao = 'teste_expirado', teste_ate = :t, criada_em = now() - interval '200 days' "
              "where id = :c", t=datetime.combine(hoje - timedelta(days=90), time(12), tzinfo=FUSO),
        c=a["conta"]["id"])
    return tarefas.limpeza()["encerradas"]


def test_exclusao_ligada_no_banco_vence_a_variavel(client, dono, monkeypatch):
    monkeypatch.setattr(config(), "EXCLUSAO_AUTOMATICA", "simular")
    gravar_parametro(dono, "teste.exclusao_automatica", "ligada")
    resumo = _rodada(client, dono, monkeypatch)
    assert (resumo["modo"], resumo["avisadas"]) == ("ligada", 1)
    assert sql(dono, "select exclusao_avisada_para from contas") == [(date(2026, 10, 10),)]


def test_exclusao_simular_no_banco_vence_a_variavel(client, dono, monkeypatch, caplog):
    monkeypatch.setattr(config(), "EXCLUSAO_AUTOMATICA", "ligada")
    gravar_parametro(dono, "teste.exclusao_automatica", "simular")
    resumo = _rodada(client, dono, monkeypatch)
    assert (resumo["modo"], resumo["avisadas"]) == ("simular", 1)
    assert sql(dono, "select exclusao_avisada_para from contas") == [(None,)]
    # valor estranho na variável: o aviso no log só sem linha no banco
    monkeypatch.setattr(config(), "EXCLUSAO_AUTOMATICA", "desligada")
    sql(dono, "delete from auditoria where conta_id is null")
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        assert tarefas.limpeza()["encerradas"]["modo"] == "simular"
    assert "desligada" not in caplog.text
    sql(dono, "delete from parametros")
    sql(dono, "delete from auditoria where conta_id is null")
    parametros.invalidar()
    with caplog.at_level(logging.WARNING, logger="toqqi"):
        assert tarefas.limpeza()["encerradas"]["modo"] == "simular"
    assert "desligada" in caplog.text


# ---- Ajuda --------------------------------------------------------------------------------------------------

def _textos(dados) -> list[str]:
    if isinstance(dados, str):
        return [dados]
    if isinstance(dados, dict):
        return [t for v in dados.values() for t in _textos(v)]
    if isinstance(dados, list):
        return [t for v in dados for t in _textos(v)]
    return []


def test_ajuda_com_os_valores_de_hoje(client, root, ana):
    bruto = json.dumps(ajuda.carregar(), ensure_ascii=False)
    assert "{{teste.dias}}" in bruto and "{{planos.essencial.preco}}" in bruto
    assert ajuda.validar(ajuda.carregar()) == []
    r = client.get(f"{API}/ajuda", headers=ana["h"])
    assert r.status_code == 200 and r.headers["cache-control"] == "private, max-age=60"
    textos = _textos(r.json())
    assert not [t for t in textos if "{{" in t or "}}" in t]
    tudo = " ".join(textos)
    for trecho in ("Começar 14 dias grátis", "Essencial: R$ 149,00 por mês. Contatos ativos: 300.",
                   "Empresa: R$ 799,00 por mês. Contatos ativos: sem limite.", "Profissional 1.500 e Empresa sem limite",
                   "Essencial 40, Profissional 90 e Empresa 200", "Rápido 1, Equilibrado 1 e Mais detalhado 2",
                   "como “120 de 500”", "2.000 no Empresa", "o Profissional."):
        assert trecho in tudo, trecho
    # sem nível fixo na sugestão de quando restam menos análises do que o nível gasta
    assert "“Equilibrado” em Configurações › IA" not in tudo and "troque para o “Equilibrado”" not in tudo
    assert tudo.count("o nível mais econômico que cabe no que resta") == 3
    _salvar(client, root, "planos", {"planos.essencial.preco": "159.90", "planos.empresa.contatos": 9000})
    _salvar(client, root, "teste", {"teste.dias": 7})
    _salvar(client, root, "ia", {"ia.analises.detalhado": 3})
    tudo = " ".join(_textos(client.get(f"{API}/ajuda", headers=ana["h"]).json()))
    for trecho in ("Começar 7 dias grátis", "Essencial: R$ 159,90 por mês.", "Contatos ativos: 9.000.",
                   "Mais detalhado 3"):
        assert trecho in tudo, trecho
    # a busca do assistente também
    achadas = ajuda.buscar("quanto custa o plano essencial")
    assert any("R$ 159,90" in a["texto"] for a in achadas) and not any("{{" in a["texto"] for a in achadas)


def test_validar_recusa_marca_desconhecida_ou_incompleta():
    dados = json.loads(json.dumps(ajuda.carregar()))
    secao = dados["topicos"][0]["secoes"][0]
    secao["blocos"].append({"tipo": "paragrafo", "texto": "O teste dura {{teste.semanas}} semanas."})
    secao["blocos"].append({"tipo": "paragrafo", "texto": "O teste dura {{teste.dias dias."})
    erros = ajuda.validar(dados)
    assert any("marca desconhecida {{teste.semanas}}" in e for e in erros), erros
    assert any("marca incompleta" in e for e in erros), erros


def test_a_tela_le_o_banco_direto(client, root, dono, monkeypatch):
    """A tela lê o banco direto (não o cache): uma linha gravada por outro processo aparece na hora."""
    monkeypatch.setattr(parametros, "monotonico", lambda: 5000.0)  # o cache não vence
    assert parametros.valor("teste.dias") == 14
    gravar_parametro(dono, "teste.dias", 8, limpar_cache=False)  # outro processo
    assert grupo_parametros(client, root["h"], "teste")["valores"]["teste.dias"] == 8
    assert parametros.valor("teste.dias") == 14  # o cache, até vencer
