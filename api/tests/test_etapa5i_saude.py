"""Etapa 5i, saúde da conta (docs/api-etapa-5i.md §3, versão enxuta): os exemplos do contrato (regras puras), a lista
de Empresas com a saúde, o filtro e a ordem, a saúde de uma empresa, a carteira no Início e as renovações."""
from datetime import date, timedelta

import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, form_padrao, inserir_resposta, membro, perfil_id, sql

from toqqi.core import relogio
from toqqi.modulos.saude.regras import Sinais, calcular, faixa

D = date(2026, 10, 5)


def _pontos(r):
    return [c["pontos"] for c in r["criterios"]]


def test_exemplos_do_contrato():
    r = calcular(Sinais(nps_j=(4, 2, 0), nps_anterior=(2, 1, 1), convidados=4, convidados_responderam=3,
                        tem_decisor=True, decisor_j=("promotor", 9, date(2026, 8, 12)), respondeu_alguma_vez=True), D)
    assert (r["nota"], r["faixa"], _pontos(r)) == (89, "saudavel", [33, 10, 11, 15, 10, 10])
    assert "Decisor promotor (nota 9 em 12/08/2026)" in [c["texto"] for c in r["criterios"]]
    assert len(r["porques"]) == 2  # sem negativos: até 2 positivos

    r = calcular(Sinais(nps_j=(0, 1, 2), nps_anterior=(1, 1, 0), convidados=5, convidados_responderam=2,
                        tem_decisor=True, decisor_ultima=date(2026, 2, 1), pendente_desde=D - timedelta(days=40),
                        atrasados=2, respondeu_alguma_vez=True), D)
    assert (r["nota"], r["faixa"], _pontos(r)) == (22, "risco", [7, 0, 6, 3, 6, 0])
    textos = [p["texto"] for p in r["porques"]]
    assert textos[0] == "NPS −67 nos últimos 6 meses (3 respostas)" and len(textos) == 3
    assert "NPS caiu 117 pontos em relação aos 6 meses anteriores" in textos

    r = calcular(Sinais(nps_j=(1, 1, 0), pendente_desde=D - timedelta(days=100), abertos_detrator=1,
                        respondeu_alguma_vez=True), D)
    assert (r["nota"], r["faixa"], _pontos(r)) == (62, "atencao", [30, 6, 8, 7, 3, 8])

    assert calcular(Sinais(primeiro_convite=D - timedelta(days=10), pendente_desde=D - timedelta(days=10)), D)["faixa"] \
        == "sem_dados"
    r = calcular(Sinais(primeiro_convite=D - timedelta(days=100), pendente_desde=D - timedelta(days=100), convidados=1), D)
    assert (r["nota"], r["faixa"], _pontos(r)) == (46, "atencao", [20, 6, 0, 7, 3, 10])

    assert [faixa(n) for n in (70, 69, 45, 44, None)] == ["saudavel", "atencao", "atencao", "risco", "sem_dados"]
    r = calcular(Sinais(respondeu_alguma_vez=True, pendente_desde=D - timedelta(days=30)), D)
    assert next(c for c in r["criterios"] if c["criterio"] == "silencio")["pontos"] == 10


def test_renovacao_em_destaque():
    risco = Sinais(nps_j=(0, 0, 3), respondeu_alguma_vez=True, atrasados=2)
    assert calcular(risco, D, D + timedelta(days=12))["renovacao"] == {"em": D + timedelta(days=12), "dias": 12}
    assert calcular(risco, D, D + timedelta(days=12))["destaque"] is True
    assert calcular(risco, D, D + timedelta(days=61))["renovacao"] is None


@pytest.fixture
def cenario(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h, cid = a["h"], a["conta"]["id"]
    f = form_padrao(client, h)["id"]
    hoje = relogio.hoje()
    boa = criar_empresa(client, h, nome="Boa", valor_mensal="1000.00")
    ruim = criar_empresa(client, h, nome="Ruim", valor_mensal="5000.00",
                         renovacao_em=(hoje + timedelta(days=20)).isoformat())
    nova = criar_empresa(client, h, nome="Nova", valor_mensal="300.00")
    decisor = perfil_id(client, h, "Decisor")
    c_boa = criar_contato(client, h, empresa_id=boa["id"], perfil_id=decisor)
    c_ruim = criar_contato(client, h, empresa_id=ruim["id"], perfil_id=decisor)
    for n in (10, 9, 10):
        inserir_resposta(dono, cid, f, c_boa, n, hoje - timedelta(days=10))
    for n in (2, 3, 1):
        inserir_resposta(dono, cid, f, c_ruim, n, hoje - timedelta(days=10))
    inserir_resposta(dono, cid, f, c_ruim, 10, hoje - timedelta(days=250))
    inserir_resposta(dono, cid, f, c_ruim, 9, hoje - timedelta(days=250))
    return {**a, "boa": boa, "ruim": ruim, "nova": nova}


def test_lista_filtro_ordem_e_detalhe(client, cenario):
    h = cenario["h"]
    r = client.get(f"{API}/empresas", headers=h)
    assert r.status_code == 200, r.text
    itens = r.json()["itens"]
    saude = {e["nome"]: e["saude"] for e in itens}
    assert saude["Boa"]["faixa"] == "saudavel" and saude["Ruim"]["faixa"] == "risco"
    assert saude["Nova"]["faixa"] == "sem_dados" and saude["Nova"]["nota"] is None
    assert saude["Ruim"]["destaque"] is True

    r = client.get(f"{API}/empresas", headers=h, params={"saude": "risco"}).json()
    assert [e["nome"] for e in r["itens"]] == ["Ruim"] and r["total"] == 1
    r = client.get(f"{API}/empresas", headers=h, params={"ordem": "saude"}).json()
    assert [e["nome"] for e in r["itens"]] == ["Ruim", "Boa", "Nova"]
    r = client.get(f"{API}/empresas", headers=h, params={"ordem": "renovacao"}).json()
    assert r["itens"][0]["nome"] == "Ruim"

    d = client.get(f"{API}/empresas/{cenario['ruim']['id']}/saude", headers=h).json()
    assert d["saude"]["faixa"] == "risco" and len(d["saude"]["criterios"]) == 6
    assert any("caiu" in p["texto"] for p in d["saude"]["porques"])
    assert client.get(f"{API}/empresas/999999/saude", headers=h).status_code == 404


def test_carteira_e_renovacoes(client, cenario):
    h = cenario["h"]
    c = client.get(f"{API}/painel/saude", headers=h).json()
    assert c["faixas"]["saudavel"]["empresas"] == 1 and c["faixas"]["risco"]["receita"] == 5000.0
    assert c["faixas"]["sem_dados"]["empresas"] == 1 and c["empresas"] == 3 and c["receita"] == 6300.0
    assert c["renovacoes_em_risco"]["empresas"] == 1
    assert c["renovacoes_em_risco"]["primeira"]["empresa"]["nome"] == "Ruim"

    r = client.get(f"{API}/relatorios/renovacoes", headers=h).json()
    assert [i["empresa"]["nome"] for i in r["itens"]] == ["Ruim"]
    assert r["itens"][0]["dias"] == 20 and r["itens"][0]["destaque"] is True


def test_perdida_sem_saude_e_permissao(client, dono, cenario):
    h = cenario["h"]
    sql(dono, "update empresa_historico set data = '2025-01-01' where empresa_id = :e", e=cenario["boa"]["id"])
    assert client.post(f"{API}/empresas/{cenario['boa']['id']}/perda", headers=h,
                       json={"motivo_perda": "preco"}).status_code == 200
    assert client.get(f"{API}/empresas/{cenario['boa']['id']}/saude", headers=h).json()["saude"] is None
    itens = client.get(f"{API}/empresas", headers=h, params={"ativa": "todas"}).json()["itens"]
    assert next(e for e in itens if e["nome"] == "Boa")["saude"] is None

    sem = membro(client, h, "leo@alfa.com.br", perfil="consulta")
    sql(dono, "delete from perfil_permissoes where conta_id = :c and perfil = 'consulta' "
              "and permissao in ('painel.ver', 'relatorios.ver')", c=cenario["conta"]["id"])
    r = client.get(f"{API}/empresas", headers=sem["h"])
    if r.status_code == 200:  # quem vê contatos sem os números: a lista vem sem saúde
        assert all(e["saude"] is None for e in r.json()["itens"])
        assert client.get(f"{API}/empresas", headers=sem["h"], params={"saude": "risco"}).status_code == 403
