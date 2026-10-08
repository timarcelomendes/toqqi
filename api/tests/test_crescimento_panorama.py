"""Panorama do Crescimento (docs/api-crescimento-panorama.md): a receita do período e do anterior (a mesma conta da
"Receita gerada pelo Toqqi"), a trilha do promotor ao cliente, as ofertas (e quantas empresas estão prontas para uma
agora), quem mais indica e o depoimento em destaque."""
from datetime import date, timedelta

import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, form_padrao, inserir_resposta, membro, sql

from toqqi.core import relogio

pytestmark = pytest.mark.usefixtures("relogio_estavel")


@pytest.fixture
def conta(client, dono, relogio_estavel):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h, conta_id, hoje = a["h"], a["conta"]["id"], relogio_estavel
    nps, csat = form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"]
    azul = criar_empresa(client, h, "Mercado Azul", valor_mensal="300.00")
    sol = criar_empresa(client, h, "Padaria Sol", valor_mensal="200.00")
    ana = criar_contato(client, h, nome="Ana Lima", email="ana@azul.com.br", empresa_id=azul["id"])
    bia = criar_contato(client, h, nome="Bia Souza", email="bia@sol.com.br", empresa_id=sol["id"])

    def resposta(contato, nota, dias, tipo="nps", comentario="", arquivada=False):
        return inserir_resposta(dono, conta_id, nps if tipo == "nps" else csat, contato, nota,
                                hoje - timedelta(days=dias), tipo=tipo, comentario=comentario, arquivada=arquivada)

    def indicacao(dias, situacao=None, valor=None, empresa=None, nome=None):
        corpo = {"nome": nome or f"Pessoa {dias}", "email": f"p{dias}-{situacao}@x.com.br",
                 **({"indicador_empresa_id": empresa["id"]} if empresa else {})}
        i = client.post(f"{API}/crescimento/indicacoes", headers=h, json=corpo)
        assert i.status_code == 201, i.text
        i = i.json()
        if situacao:
            mudanca = {"situacao": situacao, **({"valor_mensal": valor} if valor is not None else {})}
            r = client.patch(f"{API}/crescimento/indicacoes/{i['id']}", headers=h, json=mudanca)
            assert r.status_code == 200, r.text
        sql(dono, "update indicacoes set criada_em = :q where id = :i", q=relogio.agora() - timedelta(days=dias),
            i=i["id"])
        return i

    def oferta(empresa, dias, resultado=None, valor=None):
        o = client.post(f"{API}/crescimento/ofertas", headers=h,
                        json={"empresa_id": empresa["id"], "lista": "promotores", "texto": "Oi"})
        assert o.status_code == 201, o.text
        o = o.json()
        if resultado:
            client.patch(f"{API}/crescimento/ofertas/{o['id']}", headers=h, json={"resultado": resultado, "valor": valor})
        sql(dono, "update ofertas set criada_em = :q where id = :o", q=relogio.agora() - timedelta(days=dias),
            o=o["id"])
        return o

    return {"h": h, "conta_id": conta_id, "hoje": hoje, "azul": azul, "sol": sol, "ana": ana, "bia": bia,
            "resposta": resposta, "indicacao": indicacao, "oferta": oferta}


def _panorama(client, h, **params):
    r = client.get(f"{API}/crescimento/panorama", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_conta_sem_nada(client, conta):
    hoje = conta["hoje"]
    p = _panorama(client, conta["h"])
    assert p["periodo"] == {"de": (hoje - timedelta(days=89)).isoformat(), "ate": hoje.isoformat()}
    assert p["anterior"] == {"de": (hoje - timedelta(days=179)).isoformat(),
                             "ate": (hoje - timedelta(days=90)).isoformat()}
    assert p["receita"] == {"total": 0, "indicacoes": 0, "ofertas": 0, "anterior": 0}
    assert p["indicacoes"] == {"promotores": 0, "recebidas": 0, "novas": 0, "em_contato": 0, "clientes": 0,
                               "nao_avancou": 0, "abordadas": 0, "esperando_contato": 0}
    assert p["ofertas"] == {"feitas": 0, "aceitas": 0, "recusadas": 0, "sem_resposta": 0, "aguardando": 0,
                            "prontas": 0, "sem_oferta": 0}
    assert p["fas"] == [] and p["depoimentos"] == {"aprovados": 0, "pendentes": 0, "destaque": None}
    assert p["tem_historico"] is False
    assert len(p["meses"]) == 12 and p["meses"][-1] == {"mes": hoje.strftime("%Y-%m"), "indicacoes": 0, "ofertas": 0,
                                                        "total": 0}
    primeiro = date(hoje.year - (1 if hoje.month < 12 else 0), (hoje.month % 12) + 1, 1)  # 11 meses antes
    assert p["meses"][0]["mes"] == primeiro.strftime("%Y-%m")


def test_tem_historico_de_qualquer_data(client, conta, dono):
    """Um promotor de 2 anos atrás já conta (o período escolhido não importa); um 8 ou uma nota máxima arquivada, não."""
    h = conta["h"]
    conta["resposta"](conta["ana"], 8, 3)
    conta["resposta"](conta["bia"], 10, 3, arquivada=True)
    assert _panorama(client, h)["tem_historico"] is False
    conta["resposta"](conta["ana"], 5, 730, tipo="csat")
    p = _panorama(client, h)
    assert p["tem_historico"] is True and p["indicacoes"]["promotores"] == 0
    sql(dono, "delete from respostas")
    conta["oferta"](conta["sol"], 400)
    assert _panorama(client, h)["tem_historico"] is True


def test_receita_trilhas_e_comparacao(client, conta, dono):
    h, azul, sol = conta["h"], conta["azul"], conta["sol"]
    resposta, indicacao, oferta = conta["resposta"], conta["indicacao"], conta["oferta"]
    # promotores no período: NPS 9 e 10 e CSAT 5; fora: 8, CSAT 4, arquivada e de 100 dias
    resposta(conta["ana"], 10, 5), resposta(conta["ana"], 9, 40), resposta(conta["bia"], 5, 10, tipo="csat")
    resposta(conta["bia"], 8, 3), resposta(conta["bia"], 4, 3, tipo="csat"), resposta(conta["ana"], 10, 2, arquivada=True)
    resposta(conta["ana"], 10, 100)
    indicacao(10, "cliente", "1000.00", empresa=azul), indicacao(20, empresa=azul), indicacao(25, "em_contato", empresa=sol)
    indicacao(30, "nao_avancou"), indicacao(100, "cliente", "500.00", empresa=sol), indicacao(150)  # nova, de 150 dias
    oferta(azul, 5, "aceitou", "300.00"), oferta(sol, 30, "recusou"), oferta(sol, 40), oferta(azul, 95, "aceitou", "999.00")
    p = _panorama(client, h)
    assert p["receita"] == {"total": 1300.0, "indicacoes": 1000.0, "ofertas": 300.0, "anterior": 1499.0}
    # esperando contato: as "nova" de qualquer data (a de 20 dias e a de 150)
    assert p["indicacoes"] == {"promotores": 3, "recebidas": 4, "novas": 1, "em_contato": 1, "clientes": 1,
                               "nao_avancou": 1, "abordadas": 3, "esperando_contato": 2}
    assert {k: p["ofertas"][k] for k in ("feitas", "aceitas", "recusadas", "sem_resposta", "aguardando")} == {
        "feitas": 3, "aceitas": 1, "recusadas": 1, "sem_resposta": 0, "aguardando": 1}
    # quem mais indicou no período: o Mercado Azul (2, 1 cliente) antes da Padaria Sol (1); a de 100 dias não conta
    assert p["fas"] == [
        {"empresa": {"id": azul["id"], "nome": "Mercado Azul"}, "indicacoes": 2, "clientes": 1, "receita_mensal": 1000.0},
        {"empresa": {"id": sol["id"], "nome": "Padaria Sol"}, "indicacoes": 1, "clientes": 0, "receita_mensal": 0},
    ]
    # mês a mês (12 meses, não depende do período): a soma das indicações que viraram cliente e das ofertas aceitas
    esperado = {}
    for dias, valor in ((10, 1000), (100, 500), (5, 300), (95, 999)):
        mes = (conta["hoje"] - timedelta(days=dias)).strftime("%Y-%m")
        esperado[mes] = esperado.get(mes, 0) + valor
    assert {m["mes"]: m["total"] for m in p["meses"] if m["total"]} == esperado
    assert all(m["total"] == m["indicacoes"] + m["ofertas"] for m in p["meses"])
    assert sum(m["ofertas"] for m in p["meses"]) == 1299
    # outro período: 120 dias (o anterior também tem 120)
    hoje = conta["hoje"]
    de = (hoje - timedelta(days=119)).isoformat()
    p = _panorama(client, h, de=de, ate=hoje.isoformat())
    assert p["anterior"] == {"de": (hoje - timedelta(days=239)).isoformat(),
                             "ate": (hoje - timedelta(days=120)).isoformat()}
    assert p["receita"]["total"] == 1000.0 + 500.0 + 300.0 + 999.0 and p["receita"]["anterior"] == 0
    assert p["fas"][0]["empresa"]["nome"] == "Mercado Azul" and p["fas"][1]["indicacoes"] == 2
    # só o fim do período: sem começo, sem anterior
    assert _panorama(client, h, ate=hoje.isoformat())["anterior"] is None
    r = client.get(f"{API}/crescimento/panorama", headers=h, params={"de": hoje.isoformat(), "ate": de})
    assert r.status_code == 422


def test_quem_mais_indica_ate_cinco(client, conta):
    h, indicacao = conta["h"], conta["indicacao"]
    empresas = [criar_empresa(client, h, f"Empresa {n}") for n in "ABCDEF"]
    for posicao, empresa in enumerate(empresas):
        for dia in range(6 - posicao):  # A indica 6 vezes, B 5... F 1
            indicacao(dia + 1, empresa=empresa, nome=f"{empresa['nome']} {dia}")
    fas = _panorama(client, h)["fas"]
    assert [f["empresa"]["nome"] for f in fas] == ["Empresa A", "Empresa B", "Empresa C", "Empresa D", "Empresa E"]
    assert [f["indicacoes"] for f in fas] == [6, 5, 4, 3, 2]


def test_prontas_para_oferta_e_sem_oferta(client, conta):
    h, resposta, oferta = conta["h"], conta["resposta"], conta["oferta"]
    # duas empresas com promotor nos últimos 30 dias: as duas estão em "Promotores recentes"
    resposta(conta["ana"], 10, 3), resposta(conta["bia"], 9, 6)
    p = _panorama(client, h)["ofertas"]
    assert (p["prontas"], p["sem_oferta"]) == (2, 2)
    oferta(conta["sol"], 10)  # oferta há 10 dias: a Padaria Sol já recebeu
    p = _panorama(client, h)["ofertas"]
    assert (p["prontas"], p["sem_oferta"]) == (2, 1)


def test_depoimento_em_destaque(client, conta, dono):
    h, resposta = conta["h"], conta["resposta"]
    antiga = resposta(conta["ana"], 10, 20, comentario="Muito bom, recomendo.")
    nova = resposta(conta["bia"], 9, 5, comentario="  Entrega   rápida e equipe atenciosa.  ")
    pendente = resposta(conta["ana"], 10, 2, comentario="Ótimo!")
    oculto = resposta(conta["bia"], 10, 1, comentario="Não publicar")
    agora = relogio.agora()
    for rid, situacao, horas in ((antiga, "aprovado", 30), (nova, "aprovado", 3), (pendente, "pendente", 2),
                                 (oculto, "oculto", 1)):
        sql(dono, "update respostas set depoimento_em = :q, depoimento_situacao = :s where id = :r",
            q=agora - timedelta(hours=horas), s=situacao, r=rid)
    d = _panorama(client, h)["depoimentos"]
    assert (d["aprovados"], d["pendentes"]) == (2, 1)
    assert d["destaque"] == {"resposta_id": nova, "comentario": "Entrega rápida e equipe atenciosa.",
                             "assinatura": "Bia, Padaria Sol", "nota": 9, "tipo_nota": "nps",
                             "data_resposta": d["destaque"]["data_resposta"]}
    # arquivada sai do destaque
    sql(dono, "update respostas set arquivada = true where id = :r", r=nova)
    assert _panorama(client, h)["depoimentos"]["destaque"]["resposta_id"] == antiga


def test_permissao_e_outra_conta(client, conta):
    h = conta["h"]
    conta["indicacao"](3, "cliente", "100.00", empresa=conta["azul"])
    consulta = membro(client, h, "caio@alfa.com.br", perfil="consulta")["h"]
    assert client.get(f"{API}/crescimento/panorama", headers=consulta).status_code == 200  # consulta vê o Crescimento
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    p = _panorama(client, outra["h"])
    assert p["receita"]["total"] == 0 and p["fas"] == [] and p["indicacoes"]["recebidas"] == 0
    assert p["tem_historico"] is False
