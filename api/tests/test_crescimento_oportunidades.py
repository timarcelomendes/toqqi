"""Etapa 5c: oportunidades — "Pode crescer" bate com o quadrante da matriz de Relatórios › Empresas (últimos 90 dias) e
"Promotores recentes" com as respostas dos últimos 30 dias; a regra de ouro (inativa, detrator em 90 dias, ação aberta,
contato inativo ou descadastrado); contato sugerido, última resposta e última oferta (com o valor); filtros, paginação e
CSV; ofertas (a regra de ouro conferida na hora) e resultados (o valor que fica); resumo; configuração (padrões,
partes, permissões)."""
import csv
import io
from datetime import timedelta

import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    form_padrao,
    inserir_resposta,
    membro,
    sql,
)

from toqqi.core import relogio

pytestmark = pytest.mark.usefixtures("relogio_estavel")


@pytest.fixture
def cenario(client, dono, relogio_estavel):
    """Empresas A–P (valor mensal, grupo, responsável) e respostas em dias contados para trás a partir de hoje.

    Matriz dos últimos 90 dias (ativas, com NPS e valor): A 1000 (NPS 100), B 600 (50), C 500 (0), D 60000 (100),
    E 15000 (50), F 2000 (−100), G 800 (100), H 900 (33), L 3000 (100), M 550 (100) → mediana 950 → "Pode crescer" =
    B, C, G, H e M; G tem ação aberta e H um detrator → sobram M (100, 550), B (50, 600) e C (0, 500), nessa ordem.
    Promotores em 30 dias: G (−1, ação aberta), I (−1, inativa), D (−2), H (−3, detrator), O (−3, arquivada), A (−5),
    N (−7; o detrator dela tem 95 dias), E (−10), J (−15), L (−25) → D, A, N, E, J, L.
    """
    hoje = relogio_estavel
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h, conta = a["h"], a["conta"]["id"]
    leste = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Leste"}).json()
    rita = criar_responsavel(client, h, "Rita Gomes")
    nps, csat = form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"]
    e, c = {}, {}

    def empresa(chave, nome, valor, **campos):
        e[chave] = criar_empresa(client, h, nome, valor_mensal=valor, **campos)

    def contato(chave, emp, **campos):
        campos.setdefault("email", f"{chave.lower()}@cliente.com.br")
        c[chave] = criar_contato(client, h, nome=f"Contato {chave}", empresa_id=e[emp]["id"], **campos)

    def resp(chave, nota, dias, tipo="nps", arquivada=False):
        inserir_resposta(dono, conta, nps if tipo == "nps" else csat, c[chave], nota, hoje - timedelta(days=dias),
                         tipo=tipo, arquivada=arquivada)

    empresa("A", "Atacado Norte", "1000.00")
    empresa("B", "Bazar Sul", "600.00", responsavel_id=rita["id"])
    empresa("C", "Casa Leste", "500.00", grupo_id=leste["id"])
    empresa("D", "Doces Oeste", "60000.00", responsavel_id=rita["id"])
    empresa("E", "Empório Centro", "15000.00")
    empresa("F", "Feira Norte", "2000.00")
    empresa("G", "Granja Sul", "800.00")
    empresa("H", "Horti Leste", "900.00")
    empresa("I", "Inativa Ltda", "100.00", ativa=False)
    empresa("J", "Jota sem Valor", None)
    empresa("K", "Antiga Ltda", "700.00")
    empresa("L", "Mercearia Alta", "3000.00")
    empresa("M", "Mini Box", "550.00", grupo_id=leste["id"])
    empresa("N", "Nova Era", None)
    empresa("O", "Ofuscada", None)
    empresa("P", "Pura CSAT", None)

    contato("A1", "A", ativo=False)
    contato("A2", "A")
    contato("B1", "B", email=None, telefone="11999990000")  # descadastrado pelo telefone (WhatsApp)
    contato("B2", "B", telefone="11988887777")
    contato("C1", "C")
    contato("D1", "D")  # descadastrado pelo e-mail
    contato("D2", "D", telefone="21977776666")
    for chave in ("E1", "F1", "G1", "H1", "I1", "J1", "K1", "L1", "M1", "N1", "O1", "P1"):
        contato(chave, chave[0])
    sql(dono, "insert into descadastros (conta_id, telefone, origem) values (:c, '5511999990000', 'whatsapp')",
        c=conta)
    sql(dono, "insert into descadastros (conta_id, email, origem) values (:c, 'd1@cliente.com.br', 'link')", c=conta)

    resp("A1", 10, 5), resp("A2", 9, 40)
    resp("B1", 10, 50), resp("B2", 8, 60)
    resp("C1", 8, 30), resp("C1", 7, 10)
    resp("D1", 10, 2), resp("D2", 9, 20)
    resp("E1", 9, 10), resp("E1", 7, 60)
    resp("F1", 3, 15)
    resp("G1", 10, 1)
    resp("H1", 10, 3), resp("H1", 10, 20), resp("H1", 5, 70)
    resp("I1", 10, 1)
    resp("J1", 10, 15)
    resp("K1", 10, 100)
    resp("L1", 10, 25), resp("L1", 10, 80)
    resp("M1", 9, 45)
    resp("N1", 2, 95), resp("N1", 10, 7)
    resp("O1", 10, 3, arquivada=True)
    resp("P1", 5, 3, tipo="csat")
    (acao,), = sql(dono, "insert into acoes (conta_id, empresa_id, titulo, prioridade, situacao, origem) "
                         "values (:c, :e, 'Ligar', 'media', 'em_andamento', 'manual') returning id",
                   c=conta, e=e["G"]["id"])
    return {"h": h, "a": a, "hoje": hoje, "e": e, "c": c, "leste": leste, "rita": rita, "acao": acao,
            "ids": {k: v["id"] for k, v in e.items()}}


def oportunidades(client, h, **filtros) -> dict:
    r = client.get(f"{API}/crescimento/oportunidades", headers=h, params={"por_pagina": 200, **filtros})
    assert r.status_code == 200, r.text
    return r.json()


def _empresas(r: dict) -> list[int]:
    return [x["empresa"]["id"] for x in r["itens"]]


def _relatorio_crescer(client, h, hoje) -> set[int]:
    r = client.get(f"{API}/relatorios/empresas", headers=h, params={
        "de": (hoje - timedelta(days=89)).isoformat(), "ate": hoje.isoformat(), "quadrante": "crescer",
        "por_pagina": 200})
    assert r.status_code == 200, r.text
    return {x["empresa"]["id"] for x in r.json()["itens"]}


def test_pode_crescer_bate_com_o_relatorio(client, cenario):
    h, ids, hoje = cenario["h"], cenario["ids"], cenario["hoje"]
    relatorio = _relatorio_crescer(client, h, hoje)
    assert relatorio == {ids[k] for k in "BCGHM"}
    r = oportunidades(client, h, lista="pode_crescer")
    assert _empresas(r) == [ids["M"], ids["B"], ids["C"]]  # maior NPS, depois menor valor
    assert set(_empresas(r)) == relatorio - {ids["G"], ids["H"]}  # regra de ouro: ação aberta e detrator
    assert r["total"] == 3 and (r["pagina"], r["por_pagina"]) == (1, 200)
    assert _empresas(oportunidades(client, h)) == _empresas(r)  # sem `lista`: pode_crescer

    m, b, c = r["itens"]
    c_ = cenario["c"]
    assert m == {
        "empresa": {"id": ids["M"], "nome": "Mini Box", "valor_mensal": 550.0},
        "grupo": {"id": cenario["leste"]["id"], "nome": "Rede Leste"}, "responsavel": None,
        "nps": {"valor": 100, "total": 1},
        "contato": {"id": c_["M1"]["id"], "nome": "Contato M1", "telefone": None, "email": "m1@cliente.com.br"},
        "ultima_resposta": {"data": m["ultima_resposta"]["data"], "nota": 9, "tipo_nota": "nps"},
        "ultima_oferta": None,
    }
    assert m["ultima_resposta"]["data"].startswith((hoje - timedelta(days=45)).isoformat())
    # B: a resposta mais recente é do contato descadastrado pelo telefone → sugere o outro
    assert b["nps"] == {"valor": 50, "total": 2}
    assert b["responsavel"] == {"id": cenario["rita"]["id"], "nome": "Rita Gomes"}
    assert b["contato"] == {"id": c_["B2"]["id"], "nome": "Contato B2", "telefone": "5511988887777",
                            "email": "b2@cliente.com.br"}
    assert (b["ultima_resposta"]["nota"], b["ultima_resposta"]["data"][:10]) == \
        (10, (hoje - timedelta(days=50)).isoformat())
    assert c["nps"] == {"valor": 0, "total": 2} and c["contato"]["id"] == c_["C1"]["id"]
    assert c["ultima_resposta"]["nota"] == 7


def test_promotores_recentes_batem_com_as_respostas(client, cenario, dono):
    h, ids, c_ = cenario["h"], cenario["ids"], cenario["c"]
    r = oportunidades(client, h, lista="promotores")
    assert _empresas(r) == [ids[k] for k in "DANEJL"]  # promotor mais recente primeiro
    # as respostas: empresas ativas com promotor nos últimos 30 dias, menos as da regra de ouro
    (de,), = sql(dono, "select (now() at time zone 'America/Sao_Paulo')::date - 29")
    com_promotor = {x for (x,) in sql(dono, """
        select distinct r.empresa_id from respostas r join empresas e on e.id = r.empresa_id
         where r.grupo = 'promotor' and not r.arquivada and e.ativa
           and (r.data_resposta at time zone 'America/Sao_Paulo')::date >= :de""", de=de)}
    assert set(_empresas(r)) == com_promotor - {ids["G"], ids["H"]}
    d, a, n, e = r["itens"][:4]
    # D: o promotor mais recente saiu da lista (e-mail) → sugere o outro promotor; a última resposta é a dele
    assert d["contato"]["id"] == c_["D2"]["id"] and d["ultima_resposta"]["nota"] == 10
    assert d["nps"] == {"valor": 100, "total": 2}
    # A: o único promotor dos 30 dias é um contato inativo → sem contato
    assert a["contato"] is None and a["ultima_resposta"]["nota"] == 10 and a["nps"] == {"valor": 100, "total": 1}
    assert n["contato"]["id"] == c_["N1"]["id"] and n["empresa"]["valor_mensal"] is None
    # E: NPS dos 30 dias (o neutro de 60 dias não entra)
    assert e["nps"] == {"valor": 100, "total": 1} and e["ultima_resposta"]["nota"] == 9


def test_regra_de_ouro_e_filtros(client, cenario, dono):
    h, ids = cenario["h"], cenario["ids"]
    # ação concluída: a empresa volta para as duas listas
    sql(dono, "update acoes set situacao = 'concluida', concluida_em = now() where id = :a", a=cenario["acao"])
    assert _empresas(oportunidades(client, h)) == [ids[k] for k in "MGBC"]
    assert _empresas(oportunidades(client, h, lista="promotores"))[0] == ids["G"]
    # ação nova (a fazer) tira de novo; empresa desativada também sai
    sql(dono, "update acoes set situacao = 'a_fazer' where id = :a", a=cenario["acao"])
    assert ids["G"] not in _empresas(oportunidades(client, h))
    client.patch(f"{API}/empresas/{ids['M']}", headers=h, json={"ativa": False})
    assert ids["M"] not in _empresas(oportunidades(client, h))
    client.patch(f"{API}/empresas/{ids['M']}", headers=h, json={"ativa": True})
    # filtros: grupo e responsável (0 = sem responsável) só filtram a lista
    assert _empresas(oportunidades(client, h, grupo_id=cenario["leste"]["id"])) == [ids["M"], ids["C"]]
    assert _empresas(oportunidades(client, h, responsavel_id=cenario["rita"]["id"])) == [ids["B"]]
    assert _empresas(oportunidades(client, h, lista="promotores", responsavel_id=cenario["rita"]["id"])) == [ids["D"]]
    assert _empresas(oportunidades(client, h, responsavel_id=0)) == [ids["M"], ids["C"]]
    # paginação
    r = client.get(f"{API}/crescimento/oportunidades", headers=h, params={"por_pagina": 2}).json()
    assert _empresas(r) == [ids["M"], ids["B"]] and r["total"] == 3
    r = client.get(f"{API}/crescimento/oportunidades", headers=h, params={"por_pagina": 2, "pagina": 2}).json()
    assert _empresas(r) == [ids["C"]]
    assert client.get(f"{API}/crescimento/oportunidades", headers=h, params={"lista": "todas"}).status_code == 422


def test_contato_descadastrado_depois_some_da_sugestao(client, cenario, dono):
    h, ids, c_ = cenario["h"], cenario["ids"], cenario["c"]
    sql(dono, "insert into descadastros (conta_id, email, origem) values (:c, 'm1@cliente.com.br', 'manual')",
        c=cenario["a"]["conta"]["id"])
    m = next(x for x in oportunidades(client, h)["itens"] if x["empresa"]["id"] == ids["M"])
    assert m["contato"] is None  # a empresa continua; só não há a quem oferecer
    client.patch(f"{API}/contatos/{c_['C1']['id']}", headers=h, json={"ativo": False})
    c = next(x for x in oportunidades(client, h)["itens"] if x["empresa"]["id"] == ids["C"])
    assert c["contato"] is None


def test_oportunidades_de_outra_conta_nao_aparecem(client, cenario):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    for lista in ("pode_crescer", "promotores"):
        assert oportunidades(client, b["h"], lista=lista) == {"itens": [], "total": 0, "pagina": 1, "por_pagina": 200}


def test_csv_das_oportunidades(client, cenario):
    h, hoje = cenario["h"], cenario["hoje"]
    oferta = client.post(f"{API}/crescimento/ofertas", headers=h, json={
        "empresa_id": cenario["ids"]["M"], "contato_id": cenario["c"]["M1"]["id"], "lista": "pode_crescer",
        "texto": "Olá!"}).json()
    client.patch(f"{API}/crescimento/ofertas/{oferta['id']}", headers=h, json={"resultado": "aceitou", "valor": 300})
    r = client.get(f"{API}/crescimento/oportunidades.csv", headers=h)
    assert r.status_code == 200
    assert r.headers["content-disposition"] == \
        f'attachment; filename="oportunidades-pode-crescer-{hoje.isoformat()}.csv"'
    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8").lstrip("﻿")), delimiter=";"))
    assert linhas[0] == ["Empresa", "Grupo", "Responsável", "Valor mensal", "NPS", "Respostas", "Contato", "Telefone",
                         "E-mail", "Última resposta", "Última oferta"]
    dia = lambda d: (hoje - timedelta(days=d)).strftime("%d/%m/%Y")  # noqa: E731
    assert linhas[1:] == [
        ["Mini Box", "Rede Leste", "", "550,00", "100", "1", "Contato M1", "", "m1@cliente.com.br", dia(45),
         f"{hoje.strftime('%d/%m/%Y')} (Aceitou)"],
        ["Bazar Sul", "", "Rita Gomes", "600,00", "50", "2", "Contato B2", "(11) 98888-7777", "b2@cliente.com.br",
         dia(50), ""],
        ["Casa Leste", "Rede Leste", "", "500,00", "0", "2", "Contato C1", "", "c1@cliente.com.br", dia(10), ""],
    ]
    r = client.get(f"{API}/crescimento/oportunidades.csv", headers=h, params={"lista": "promotores"})
    assert r.headers["content-disposition"].endswith(f'oportunidades-promotores-{hoje.isoformat()}.csv"')
    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8").lstrip("﻿")), delimiter=";"))
    assert [x[0] for x in linhas[1:]] == ["Doces Oeste", "Atacado Norte", "Nova Era", "Empório Centro",
                                          "Jota sem Valor", "Mercearia Alta"]
    assert linhas[2][6:9] == ["", "", ""]  # Atacado Norte: sem contato sugerido


# ---- ofertas ---------------------------------------------------------------------------------------

def test_oferta_e_resultado(client, cenario, dono):
    h, ids, c_ = cenario["h"], cenario["ids"], cenario["c"]
    r = client.post(f"{API}/crescimento/ofertas", headers=h, json={
        "empresa_id": ids["B"], "contato_id": c_["B2"]["id"], "lista": "pode_crescer",
        "texto": "Olá, B2! Aqui é Ana, da Alfa Distribuidora."})
    assert r.status_code == 201, r.text
    o = r.json()
    usuario = cenario["a"]["usuario"]
    assert o == {"id": o["id"], "empresa": {"id": ids["B"], "nome": "Bazar Sul"},
                 "contato": {"id": c_["B2"]["id"], "nome": "Contato B2"}, "lista": "pode_crescer", "canal": "whatsapp",
                 "texto": "Olá, B2! Aqui é Ana, da Alfa Distribuidora.",
                 "usuario": {"id": usuario["id"], "nome": usuario["nome"]}, "criada_em": o["criada_em"],
                 "resultado": None, "valor": None, "resultado_em": None}
    b = next(x for x in oportunidades(client, h)["itens"] if x["empresa"]["id"] == ids["B"])
    assert b["ultima_oferta"] == {"id": o["id"], "criada_em": o["criada_em"], "resultado": None, "valor": None}

    url = f"{API}/crescimento/ofertas/{o['id']}"
    r = client.patch(url, headers=h, json={"resultado": "aceitou", "valor": "1200.00"})
    assert r.status_code == 200 and (r.json()["resultado"], r.json()["valor"]) == ("aceitou", 1200.0)
    assert r.json()["resultado_em"] is not None
    primeira_vez = r.json()["resultado_em"]
    r = client.patch(url, headers=h, json={"valor": 1300})  # só o valor
    assert (r.json()["resultado"], r.json()["valor"], r.json()["resultado_em"]) == ("aceitou", 1300.0, primeira_vez)
    r = client.patch(url, headers=h, json={"resultado": "recusou"})  # outro resultado limpa o valor
    assert (r.json()["resultado"], r.json()["valor"]) == ("recusou", None)
    r = client.patch(url, headers=h, json={"valor": 50})
    assert r.json()["valor"] is None
    r = client.patch(url, headers=h, json={"resultado": "sem_resposta"})
    assert r.json()["resultado"] == "sem_resposta"
    r = client.patch(url, headers=h, json={"resultado": None})  # desfaz
    assert (r.json()["resultado"], r.json()["valor"], r.json()["resultado_em"]) == (None, None, None)
    for corpo in ({"resultado": "talvez"}, {"resultado": "aceitou", "valor": -1}):
        assert client.patch(url, headers=h, json=corpo).status_code == 422
    assert client.patch(f"{API}/crescimento/ofertas/999999", headers=h, json={}).status_code == 404
    # a mais recente aparece como última oferta (e-mail, sem contato)
    r = client.post(f"{API}/crescimento/ofertas", headers=h, json={
        "empresa_id": ids["B"], "lista": "promotores", "texto": "Oi", "canal": "email"})
    assert r.status_code == 201 and (r.json()["canal"], r.json()["contato"]) == ("email", None)
    b = next(x for x in oportunidades(client, h)["itens"] if x["empresa"]["id"] == ids["B"])
    assert b["ultima_oferta"]["id"] == r.json()["id"]
    # some com a empresa
    sql(dono, "delete from empresas where id = :e", e=ids["B"])
    assert sql(dono, "select count(*) from ofertas")[0][0] == 0


def test_valor_da_oferta_aceita_e_ultima_oferta(client, cenario):
    """`ultima_oferta` traz o valor. No PATCH, com 'aceitou', valor ausente ou null mantém o valor (a tela reabre o
    resultado com o campo vazio); um número troca; outro resultado limpa; voltar a 'aceitou' sem valor fica sem."""
    h, ids, c_ = cenario["h"], cenario["ids"], cenario["c"]
    o = client.post(f"{API}/crescimento/ofertas", headers=h, json={
        "empresa_id": ids["B"], "contato_id": c_["B2"]["id"], "lista": "pode_crescer", "texto": "Oi"}).json()
    url = f"{API}/crescimento/ofertas/{o['id']}"

    def valor(corpo):
        r = client.patch(url, headers=h, json=corpo)
        assert r.status_code == 200, r.text
        return r.json()["valor"]

    def ultima() -> dict:
        return next(x for x in oportunidades(client, h)["itens"] if x["empresa"]["id"] == ids["B"])["ultima_oferta"]

    assert valor({"resultado": "aceitou", "valor": "1200.00"}) == 1200.0
    assert ultima() == {"id": o["id"], "criada_em": o["criada_em"], "resultado": "aceitou", "valor": 1200.0}
    assert valor({"resultado": "aceitou", "valor": None}) == 1200.0  # o que a tela manda com o campo vazio
    assert valor({"resultado": "aceitou"}) == 1200.0
    assert valor({"valor": None}) == 1200.0 and valor({}) == 1200.0
    assert valor({"resultado": "aceitou", "valor": 0}) == 0  # um número troca (zero também)
    assert valor({"valor": "350.50"}) == 350.5 and ultima()["valor"] == 350.5
    assert valor({"resultado": "recusou", "valor": 99}) is None  # outro resultado limpa
    assert valor({"resultado": "aceitou", "valor": None}) is None  # voltou a 'aceitou' sem valor
    assert ultima() == {"id": o["id"], "criada_em": o["criada_em"], "resultado": "aceitou", "valor": None}


def test_oferta_confere_a_regra_de_ouro_na_hora(client, cenario, dono):
    """A lista da tela pode estar velha: a oferta confere na hora a regra de ouro (empresa inativa, com plano de ação
    aberto ou detrator nos últimos 90 dias) e o contato (da empresa, ativo, não descadastrado): 422 com o motivo na
    mensagem e no campo (a tela mostra o do campo)."""
    h, ids, c_ = cenario["h"], cenario["ids"], cenario["c"]

    def ofertar(empresa, contato=None):
        corpo = {"empresa_id": ids[empresa], "lista": "promotores", "texto": "Olá!"}
        if contato:
            corpo["contato_id"] = c_[contato]["id"]
        return client.post(f"{API}/crescimento/ofertas", headers=h, json=corpo)

    saiu = "Esta empresa saiu das oportunidades: "
    for empresa, contato, campo, motivo in (
        ("I", "I1", "empresa_id", saiu + "ela está inativa."),
        ("G", "G1", "empresa_id", saiu + "ela tem um plano de ação aberto."),
        ("G", None, "empresa_id", saiu + "ela tem um plano de ação aberto."),  # sem contato (e-mail) também
        ("H", "H1", "empresa_id", saiu + "ela deu uma nota de detrator (0 a 6) nos últimos 90 dias."),
        ("A", "B2", "contato_id", "Este contato não é desta empresa."),
        ("A", "A1", "contato_id", "Este contato está inativo e não recebe ofertas."),
        ("D", "D1", "contato_id", "Este contato saiu da lista e não recebe ofertas."),
    ):
        r = ofertar(empresa, contato)
        assert r.status_code == 422, (empresa, contato, r.text)
        assert r.json()["erro"] == {"codigo": "dados_invalidos", "mensagem": motivo, "campos": {campo: motivo}}
    assert sql(dono, "select count(*) from ofertas")[0][0] == 0
    # o detrator de 95 dias (N) já não conta; com a ação concluída, G volta a receber oferta
    assert ofertar("N", "N1").status_code == 201
    sql(dono, "update acoes set situacao = 'concluida', concluida_em = now() where id = :a", a=cenario["acao"])
    assert ofertar("G", "G1").status_code == 201


@pytest.mark.parametrize("corpo,erros", [
    ({"empresa_id": 999999}, {"empresa_id"}),
    ({"contato_id": 999999}, {"contato_id"}),
    ({"empresa_id": 2**63}, {"empresa_id"}),  # fora do bigint: 422, não erro do banco
    ({"contato_id": 2**63}, {"contato_id"}),
    ({"empresa_id": 0}, {"empresa_id"}),
    ({"lista": "todas"}, {"lista"}),
    ({"texto": ""}, {"texto"}),
    ({"texto": "x" * 2001}, {"texto"}),
    ({"canal": "sms"}, {"canal"}),
])
def test_oferta_validacoes(client, cenario, corpo, erros):
    base = {"empresa_id": cenario["ids"]["M"], "contato_id": cenario["c"]["M1"]["id"], "lista": "pode_crescer",
            "texto": "Olá!"}
    r = client.post(f"{API}/crescimento/ofertas", headers=cenario["h"], json={**base, **corpo})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == erros, r.text


def test_oferta_para_contato_descadastrado_e_outra_conta(client, cenario):
    h, ids, c_ = cenario["h"], cenario["ids"], cenario["c"]
    r = client.post(f"{API}/crescimento/ofertas", headers=h, json={
        "empresa_id": ids["D"], "contato_id": c_["D1"]["id"], "lista": "promotores", "texto": "Olá!"})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {
        "contato_id": "Este contato saiu da lista e não recebe ofertas."}
    o = client.post(f"{API}/crescimento/ofertas", headers=h, json={
        "empresa_id": ids["D"], "contato_id": c_["D2"]["id"], "lista": "promotores", "texto": "Olá!"}).json()
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert client.patch(f"{API}/crescimento/ofertas/{o['id']}", headers=b["h"],
                        json={"resultado": "aceitou"}).status_code == 404
    r = client.post(f"{API}/crescimento/ofertas", headers=b["h"], json={
        "empresa_id": ids["D"], "lista": "promotores", "texto": "Olá!"})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"empresa_id"}


# ---- resumo ----------------------------------------------------------------------------------------

def test_resumo(client, dono, relogio_estavel):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h, hoje = a["h"], relogio_estavel
    vazio = client.get(f"{API}/crescimento/resumo", headers=h).json()
    assert vazio == {"periodo": {"de": (hoje - timedelta(days=89)).isoformat(), "ate": hoje.isoformat()},
                     "indicacoes": {"recebidas": 0, "clientes": 0, "taxa": None, "receita_mensal": 0},
                     "ofertas": {"feitas": 0, "aceitas": 0, "taxa": None, "receita": 0}}
    empresa = criar_empresa(client, h, "Mercado Bom Preço")

    def indicacao(dias, situacao=None, valor=None):
        i = client.post(f"{API}/crescimento/indicacoes", headers=h,
                        json={"nome": f"Pessoa {dias}", "email": f"p{dias}@x.com.br"}).json()
        if situacao:
            corpo = {"situacao": situacao, **({"valor_mensal": valor} if valor is not None else {})}
            assert client.patch(f"{API}/crescimento/indicacoes/{i['id']}", headers=h, json=corpo).status_code == 200
        sql(dono, "update indicacoes set criada_em = :q where id = :i", q=relogio.agora() - timedelta(days=dias),
            i=i["id"])

    def oferta(dias, resultado=None, valor=None):
        o = client.post(f"{API}/crescimento/ofertas", headers=h,
                        json={"empresa_id": empresa["id"], "lista": "promotores", "texto": "Oi"}).json()
        if resultado:
            client.patch(f"{API}/crescimento/ofertas/{o['id']}", headers=h,
                         json={"resultado": resultado, "valor": valor})
        sql(dono, "update ofertas set criada_em = :q where id = :o", q=relogio.agora() - timedelta(days=dias),
            o=o["id"])

    indicacao(10, "cliente", "1000.00"), indicacao(20), indicacao(30, "nao_avancou"), indicacao(100, "cliente", 500)
    oferta(5, "aceitou", 300), oferta(30, "recusou"), oferta(95, "aceitou", 999)
    r = client.get(f"{API}/crescimento/resumo", headers=h).json()
    assert r["indicacoes"] == {"recebidas": 3, "clientes": 1, "taxa": 33, "receita_mensal": 1000.0}
    assert r["ofertas"] == {"feitas": 2, "aceitas": 1, "taxa": 50, "receita": 300.0}
    de = (hoje - timedelta(days=120)).isoformat()
    r = client.get(f"{API}/crescimento/resumo", headers=h, params={"de": de, "ate": hoje.isoformat()}).json()
    assert r["periodo"] == {"de": de, "ate": hoje.isoformat()}
    assert r["indicacoes"] == {"recebidas": 4, "clientes": 2, "taxa": 50, "receita_mensal": 1500.0}
    assert r["ofertas"] == {"feitas": 3, "aceitas": 2, "taxa": 67, "receita": 1299.0}
    r = client.get(f"{API}/crescimento/resumo", headers=h, params={"de": de}).json()  # só o começo: até hoje
    assert r["periodo"] == {"de": de, "ate": None} and r["indicacoes"]["recebidas"] == 4
    assert client.get(f"{API}/crescimento/resumo", headers=h,
                      params={"de": hoje.isoformat(), "ate": de}).status_code == 422


# ---- configuração ----------------------------------------------------------------------------------

PADROES = {
    "indicacoes_ativas": False,
    "titulo_convite": "Que bom que você gostou!",
    "texto_convite": "Conhece outra empresa que ganharia com a {empresa}? Indique e a gente entra em contato com "
                     "cuidado.",
    "recompensa": None,
    "texto_oferta": "Olá, {nome}! Aqui é {representante}, da {empresa}. Obrigado pela ótima avaliação! Preparei uma "
                    "condição especial para a {empresa_cliente}. Posso te contar?",
    "depoimentos_ativos": False,  # melhoria 5
    "link_avaliacao": None,
}


def test_configuracao_padroes_partes_e_auditoria(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h = a["h"]
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    for quem in (a, consulta, gestor):
        r = client.get(f"{API}/crescimento/configuracao", headers=quem["h"])
        assert r.status_code == 200 and r.json() == PADROES
    assert sql(dono, "select count(*) from config_crescimento")[0][0] == 0  # ler não grava

    url = f"{API}/crescimento/configuracao"
    r = client.put(url, headers=h, json={"indicacoes_ativas": True, "recompensa": "  Ganhe 10% na {empresa}.  "})
    assert r.status_code == 200
    assert r.json() == {**PADROES, "indicacoes_ativas": True, "recompensa": "Ganhe 10% na {empresa}."}
    r = client.put(url, headers=h, json={"titulo_convite": None, "texto_oferta": "Oi, {nome}!\nTenho uma oferta."})
    assert r.json()["titulo_convite"] == PADROES["titulo_convite"]  # null não muda o obrigatório
    assert r.json()["texto_oferta"] == "Oi, {nome}!\nTenho uma oferta." and r.json()["recompensa"]
    assert client.put(url, headers=h, json={"recompensa": ""}).json()["recompensa"] is None  # vazia limpa
    assert client.get(url, headers=consulta["h"]).json()["indicacoes_ativas"] is True
    for corpo, campo in (({"titulo_convite": ""}, "titulo_convite"), ({"titulo_convite": "x" * 121}, "titulo_convite"),
                         ({"texto_convite": "x" * 501}, "texto_convite"), ({"recompensa": "x" * 301}, "recompensa"),
                         ({"texto_oferta": "x" * 1001}, "texto_oferta"), ({"texto_oferta": " "}, "texto_oferta"),
                         ({"indicacoes_ativas": "talvez"}, "indicacoes_ativas")):
        r = client.put(url, headers=h, json=corpo)
        assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {campo}, corpo
    campos = [d["campos"] for (d,) in sql(dono, "select detalhe from auditoria where evento = 'config_crescimento' "
                                                "order by id")]
    assert campos == [["indicacoes_ativas", "recompensa"], ["texto_oferta"], ["recompensa"]]
    client.put(url, headers=h, json={"indicacoes_ativas": True})  # nada mudou: sem auditoria
    assert sql(dono, "select count(*) from auditoria where evento = 'config_crescimento'")[0][0] == 3
    # só quem gerencia as configurações altera
    for quem in (consulta, gestor):
        assert client.put(url, headers=quem["h"], json={"indicacoes_ativas": False}).status_code == 403
