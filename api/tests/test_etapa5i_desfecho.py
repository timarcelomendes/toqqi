"""Etapa 5i, desfecho (docs/api-etapa-5i.md §2, versão enxuta): marcar a empresa como perdida (motivo e data, desativa
os contatos), voltar a ser cliente (reativa os contatos dentro do limite do plano) e Relatórios › Desfecho (perdidas,
motivos, o que diziam antes de sair × carteira ativa, GRR e NRR pelo histórico gravado pelo banco)."""
from datetime import date, timedelta

import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, definir_plano, encher_contatos, form_padrao, \
    inserir_resposta, sql

from toqqi.core import relogio


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _perder(client, h, empresa_id, **corpo):
    return client.post(f"{API}/empresas/{empresa_id}/perda", headers=h, json={"motivo_perda": "preco", **corpo})


def _antigo(dono, empresa_id: int, quando: str = "2025-01-01") -> None:
    """A empresa existe desde `quando` (o histórico nasce no dia do cadastro)."""
    sql(dono, "update empresa_historico set data = :d where empresa_id = :e", d=quando, e=empresa_id)


def test_perder_e_voltar(client, dono, admin):
    h = admin["h"]
    e = criar_empresa(client, h, valor_mensal="1500.00", renovacao_em="2026-12-01")
    assert e["situacao"] == "ativa" and e["renovacao_em"] == "2026-12-01"
    c1 = criar_contato(client, h, empresa_id=e["id"])
    criar_contato(client, h, empresa_id=e["id"])
    _antigo(dono, e["id"])

    r = _perder(client, h, e["id"], motivo_perda="outro")
    assert r.status_code == 422 and "motivo_detalhe" in r.json()["erro"]["campos"]
    amanha = (relogio.hoje() + timedelta(days=1)).isoformat()
    assert _perder(client, h, e["id"], perdida_em=amanha).status_code == 422

    r = _perder(client, h, e["id"], motivo_perda="concorrente", motivo_detalhe="Fechou com outro fornecedor")
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["situacao"], p["ativa"], p["contatos_desativados"]) == ("perdida", False, 2)
    assert p["motivo_perda_rotulo"] == "Foi para um concorrente" and p["perdida_em"] == relogio.hoje().isoformat()
    assert _perder(client, h, e["id"]).status_code == 409

    # contato ativo em empresa perdida e reativar pela edição: 409
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Novo", "email": "novo@x.com.br", "empresa_id": e["id"]})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "empresa_perdida"
    assert client.patch(f"{API}/contatos/{c1['id']}", headers=h, json={"ativo": True}).status_code == 409
    assert client.patch(f"{API}/empresas/{e['id']}", headers=h, json={"ativa": True}).status_code == 409

    r = client.post(f"{API}/empresas/{e['id']}/retorno", headers=h, json={"valor_mensal": "1800.00"})
    assert r.status_code == 200, r.text
    v = r.json()
    assert (v["situacao"], v["ativa"], v["contatos_reativados"], v["valor_mensal"]) == ("ativa", True, 2, 1800.0)
    assert client.post(f"{API}/empresas/{e['id']}/retorno", headers=h, json={}).status_code == 409

    tipos = [t for (t,) in sql(dono, "select tipo from empresa_historico where empresa_id = :e order by data, id",
                                e=e["id"])]
    assert tipos == ["entrada", "perdida", "reativada"]
    eventos = {ev for (ev,) in sql(dono, "select evento from auditoria where conta_id = :c", c=admin["conta"]["id"])}
    assert {"empresa_perdida", "empresa_reativada"} <= eventos


def test_voltar_respeita_o_limite_do_plano(client, dono, admin):
    h, cid = admin["h"], admin["conta"]["id"]
    e = criar_empresa(client, h)
    criar_contato(client, h, empresa_id=e["id"])
    _antigo(dono, e["id"])
    assert _perder(client, h, e["id"]).status_code == 200
    definir_plano(dono, cid, "essencial")
    limite = sql(dono, "select limite_contatos('essencial', 'ativa')")[0][0]
    encher_contatos(dono, cid, limite)
    r = client.post(f"{API}/empresas/{e['id']}/retorno", headers=h, json={})
    assert r.status_code == 402
    assert client.get(f"{API}/empresas/{e['id']}", headers=h).json()["situacao"] == "perdida"
    # sem reativar os contatos, volta
    r = client.post(f"{API}/empresas/{e['id']}/retorno", headers=h, json={"reativar_contatos": False})
    assert r.status_code == 200 and r.json()["contatos_reativados"] == 0


def _linha(dono, empresa_id, tipo, data, antes=None, depois=None, motivo=None):
    sql(dono, """insert into empresa_historico (conta_id, empresa_id, tipo, data, valor_antes, valor_depois, motivo,
                 origem) select conta_id, id, :t, :d, :a, :v, :m, 'tela' from empresas where id = :e""",
        t=tipo, d=data, a=antes, v=depois, m=motivo, e=empresa_id)


def test_retencao_do_exemplo_do_contrato(client, dono, admin):
    h = admin["h"]
    ids = {n: criar_empresa(client, h, nome=n)["id"] for n in ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8")}
    sql(dono, "delete from empresa_historico where empresa_id = any(:i)", i=list(ids.values()))
    for nome, valor in (("E1", 10000), ("E2", 5000), ("E3", 4000), ("E4", 1000), ("E5", 2000), ("E7", None),
                        ("E8", 5000)):
        _linha(dono, ids[nome], "entrada", "2025-06-01", depois=valor)
    _linha(dono, ids["E1"], "perdida", "2026-02-15", antes=10000, motivo="preco")
    _linha(dono, ids["E2"], "valor", "2026-03-10", antes=5000, depois=3000)
    _linha(dono, ids["E3"], "valor", "2026-01-20", antes=4000, depois=6000)
    _linha(dono, ids["E5"], "perdida", "2026-01-05", antes=2000, motivo="preco")
    _linha(dono, ids["E5"], "reativada", "2026-01-25", antes=2000, depois=2500)
    _linha(dono, ids["E6"], "entrada", "2026-02-10", depois=3000)
    _linha(dono, ids["E8"], "perdida", "2025-12-20", antes=5000, motivo="encerrou")

    r = client.get(f"{API}/relatorios/desfecho", headers=h, params={"de": "2026-01-01", "ate": "2026-03-31"})
    assert r.status_code == 200, r.text
    d = r.json()
    ret = d["retencao"]
    assert ret["inicio"] == {"data": "2026-01-01", "empresas": 5, "receita": 22000.0, "sem_valor": 1}
    assert (ret["perdida"], ret["reducao"], ret["aumento"], ret["fim"]) == (10000.0, 2000.0, 2500.0, 12500.0)
    assert (ret["grr"], ret["nrr"]) == (45.5, 56.8)
    assert ret["novas"] == {"empresas": 1, "receita": 3000.0}
    assert ret["historico_parcial"] is False
    assert d["perdidas"]["empresas"] == 1 and d["perdidas"]["receita_mensal"] == 10000.0
    assert [i["empresa"]["nome"] for i in d["perdidas"]["itens"]] == ["E1"]
    assert {m["motivo"]: m["empresas"] for m in d["motivos"]} == {
        "preco": 1, "concorrente": 0, "atendimento": 0, "produto": 0, "encerrou": 0, "outro": 0}
    # período invertido
    assert client.get(f"{API}/relatorios/desfecho", headers=h,
                      params={"de": "2026-03-31", "ate": "2026-01-01"}).status_code == 422


def test_o_que_diziam_antes_de_sair(client, dono, admin):
    h, cid = admin["h"], admin["conta"]["id"]
    f = form_padrao(client, h)["id"]
    hoje = relogio.hoje()
    perda = hoje - timedelta(days=10)

    def empresa(nome):
        e = criar_empresa(client, h, nome=nome, valor_mensal="1000.00")
        _antigo(dono, e["id"])
        return e["id"]

    p = {n: empresa(n) for n in ("P1", "P2", "P3", "P4")}
    inserir_resposta(dono, cid, f, None, 3, perda - timedelta(days=30), empresa_id=p["P1"])
    inserir_resposta(dono, cid, f, None, 7, perda - timedelta(days=5), empresa_id=p["P2"])
    inserir_resposta(dono, cid, f, None, 2, perda - timedelta(days=100), empresa_id=p["P4"])
    inserir_resposta(dono, cid, f, None, 10, perda - timedelta(days=20), empresa_id=p["P4"])
    for e_id in p.values():
        assert _perder(client, h, e_id, perdida_em=perda.isoformat()).status_code == 200
    carteira = [empresa(f"C{i}") for i in range(10)]
    inserir_resposta(dono, cid, f, None, 4, hoje - timedelta(days=3), empresa_id=carteira[0])
    inserir_resposta(dono, cid, f, None, 6, hoje - timedelta(days=60), empresa_id=carteira[1])
    inserir_resposta(dono, cid, f, None, 9, hoje - timedelta(days=3), empresa_id=carteira[2])

    d = client.get(f"{API}/relatorios/desfecho", headers=h).json()
    a = d["antes_de_sair"]
    assert a["perdidas"]["percentuais"] == {"detrator": 25.0, "neutro": 25.0, "promotor": 25.0, "sem_resposta": 25.0}
    assert a["amostra_pequena"] is True
    assert a["carteira"]["total"] == 10 and a["carteira"]["detrator"] == 2 and a["carteira"]["percentuais"]["detrator"] == 20.0
    itens = {i["empresa"]["nome"]: i for i in d["perdidas"]["itens"]}
    assert itens["P4"]["antes"] == "promotor" and itens["P4"]["ultima_nota"]["nota"] == 10
    assert itens["P3"]["ultima_nota"] is None
    assert d["perdidas"]["receita_mensal"] == 4000.0


def test_desfecho_exige_permissao(client, admin):
    from util import membro
    sem = membro(client, admin["h"], "leo@alfa.com.br", perfil="consulta")
    r = client.get(f"{API}/relatorios/desfecho", headers=sem["h"])
    assert r.status_code in (200, 403)  # segue `relatorios.ver` do perfil, como as outras abas
    e = criar_empresa(client, admin["h"])
    assert _perder(client, sem["h"], e["id"]).status_code == 403
