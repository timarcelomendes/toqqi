"""Painel v2 (docs/painel-v2.md §1): evolução de 12 meses, tom dos comentários, carteira e valor mensal no ranking.
Usa o cenário de `test_painel.py` (março/2026 calculado à mão)."""
from datetime import date

import pytest
import test_painel
from test_painel import MARCO, Dados, _painel
from util import API, conta_pronta, criar_contato, criar_empresa, form_padrao, sql

cenario = test_painel.cenario  # a mesma fixture do painel
pytestmark = pytest.mark.usefixtures("relogio_estavel")


def _meses_ate(fim: date) -> list[str]:
    a, m = fim.year, fim.month
    meses = []
    for _ in range(12):
        meses.insert(0, f"{a:04d}-{m:02d}")
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    return meses


def _por_mes(p: dict) -> dict:
    return {x["mes"]: x for x in p["evolucao_12m"]}


def _sentimentos(dono, conta: int) -> None:
    """IA no cenário: sentimento por comentário; "Atrasou de novo" ficou pendente; uma sem comentário analisada."""
    for texto, sentimento in [
        ("Entrega atrasou e o frete é caro", "negativo"), ("Atendimento excelente", "positivo"),
        ("Entrega ok, mas o preço subiu", "misto"), ("Produto quebrado", "negativo"),
        ("Vendedor atencioso", "positivo"), ("Site lento", "neutro"), ("Motorista grosseiro", "negativo"),
        ("Demorou", "negativo"), ("Entrega rápida", "positivo"), ("Péssimo", "negativo"),
    ]:
        sql(dono, "update respostas set ia_situacao = 'analisada', ia_sentimento = :s "
                  "where conta_id = :c and comentario_cliente = :t", s=sentimento, c=conta, t=texto)
    sql(dono, "update respostas set ia_situacao = 'pendente' where conta_id = :c and comentario_cliente = :t",
        c=conta, t="Atrasou de novo")
    sql(dono, "update respostas set ia_situacao = 'analisada', ia_sentimento = 'negativo' "
              "where conta_id = :c and comentario_cliente = '' and nota = 2 and tipo_nota = 'nps'", c=conta)


# ---- evolução de 12 meses -----------------------------------------------------

def test_evolucao_12m_com_periodo(client, cenario):
    p = _painel(client, cenario["h"], **MARCO)
    ev = p["evolucao_12m"]
    assert [x["mes"] for x in ev] == _meses_ate(date(2026, 3, 1))  # 2025-04 a 2026-03
    # não aplica o período: novembro e fevereiro aparecem; meses vazios com nps null e total 0
    assert {x["mes"]: (x["nps"], x["total"]) for x in ev if x["total"]} == {
        "2025-11": (-100, 1), "2026-02": (33, 3), "2026-03": (-11, 9)}
    assert all(x["nps"] is None for x in ev if not x["total"])
    assert [x["mes"] for x in ev if x["no_periodo"]] == ["2026-03"]
    # o bloco antigo continua igual
    assert p["evolucao"] == [{"mes": "2026-03", "nps": -11, "total": 9}]


def test_evolucao_12m_periodo_entre_meses_e_pontas_abertas(client, cenario, relogio_estavel):
    h = cenario["h"]
    ev = _painel(client, h, de="2026-02-15", ate="2026-03-10")["evolucao_12m"]
    assert ev[-1]["mes"] == "2026-03" and [x["mes"] for x in ev if x["no_periodo"]] == ["2026-02", "2026-03"]
    # só `ate`: termina no mês de `ate` e todos os meses cruzam o período
    ev = _painel(client, h, ate="2026-02-28")["evolucao_12m"]
    assert [x["mes"] for x in ev] == _meses_ate(date(2026, 2, 1)) and all(x["no_periodo"] for x in ev)
    # só `de`: termina hoje; do mês de `de` em diante está no período
    ev = _painel(client, h, de="2026-03-17")["evolucao_12m"]
    assert [x["mes"] for x in ev] == _meses_ate(relogio_estavel)
    assert [x["mes"] for x in ev if x["no_periodo"]] == [m for m in _meses_ate(relogio_estavel) if m >= "2026-03"]
    # `de` no futuro: a janela vai até o mês de `de`
    futuro = date(relogio_estavel.year + 1, relogio_estavel.month, 1)
    ev = _painel(client, h, de=futuro.isoformat())["evolucao_12m"]
    assert ev[-1]["mes"] == futuro.strftime("%Y-%m") and [x["no_periodo"] for x in ev].count(True) == 1


def test_evolucao_12m_sem_periodo(client, cenario, relogio_estavel):
    ev = _painel(client, cenario["h"])["evolucao_12m"]
    meses = _meses_ate(relogio_estavel)
    assert [x["mes"] for x in ev] == meses and not any(x["no_periodo"] for x in ev)
    esperado = {"2025-11": (-100, 1), "2026-02": (33, 3), "2026-03": (-11, 9)}
    assert {x["mes"]: (x["nps"], x["total"]) for x in ev if x["total"]} == {
        m: v for m, v in esperado.items() if m in meses}


def test_evolucao_12m_filtros_de_empresa(client, cenario):
    h = cenario["h"]
    # Rede Leste (Atacado Norte e Mercado Sul): fev Caio 9, Cris 10; mar 1 P, 1 N, 4 D; Ciro (sem empresa) sai
    meses = _por_mes(_painel(client, h, grupo_id=cenario["g1"]["id"], **MARCO))
    assert (meses["2026-02"]["nps"], meses["2026-02"]["total"]) == (100, 2)
    assert (meses["2026-03"]["nps"], meses["2026-03"]["total"]) == (-50, 6)
    assert (meses["2025-11"]["nps"], meses["2025-11"]["total"]) == (None, 0)
    # todas as empresas: entram os 3 promotores da Padaria Leste (inativa) → 6 P, 2 N, 4 D em 12 → 17
    meses = _por_mes(_painel(client, h, so_ativos="false", **MARCO))
    assert (meses["2026-03"]["nps"], meses["2026-03"]["total"]) == (17, 12)


def test_evolucao_12m_mes_de_sao_paulo_e_bordas(client, dono):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])
    c = criar_contato(client, h)
    vazio = _painel(client, h, de="2026-04-01", ate="2026-04-30")["evolucao_12m"]
    assert len(vazio) == 12 and all(x["nps"] is None and x["total"] == 0 for x in vazio)
    horarios = {"2025-04-30 23:30-03": 0, "2025-05-01 00:30-03": 10,  # antes da janela / primeiro mês
                "2026-04-30 23:30-03": 10, "2026-05-01 00:30-03": 0}  # último mês / depois da janela
    for quando, nota in horarios.items():
        r = d.resposta(c, nota, "2026-01-01")
        sql(dono, "update respostas set respondida_em = :q where id = :r", q=quando, r=r)
    d.resposta(c, 5, "2025-12-10", tipo="csat")  # CSAT não entra na evolução
    ev = _painel(client, h, de="2026-04-01", ate="2026-04-30")["evolucao_12m"]
    assert [x["mes"] for x in ev] == _meses_ate(date(2026, 4, 1))
    assert {x["mes"]: (x["nps"], x["total"]) for x in ev if x["total"]} == {"2025-05": (100, 1),
                                                                          "2026-04": (100, 1)}


# ---- tom dos comentários --------------------------------------------------------

def test_tom_com_periodo_e_anterior(client, cenario, dono):
    _sentimentos(dono, cenario["a"]["conta"]["id"])
    t = _painel(client, cenario["h"], **MARCO)["tom"]
    # base do painel (só ativas, não arquivadas): 9 NPS + 4 CSAT; 8 com comentário (7 NPS + "Motorista grosseiro");
    # analisados: os 8 com comentário menos o pendente ("Atrasou de novo") → 7; a sem comentário não conta
    assert t == {"analisados": 7, "com_comentario": 8, "total_respostas": 13, "pendentes": 1, "negativo": 3, "misto": 1,
                 "neutro": 1, "positivo": 1 + 1, "anterior": {"analisados": 1, "negativo": 1},  # "Demorou"
                 "ia_ligada": True, "sem_analise": 0}  # etapa 5h: todos os comentários analisados ou na fila


def test_tom_filtros_de_empresa_e_sem_periodo(client, cenario, dono):
    _sentimentos(dono, cenario["a"]["conta"]["id"])
    h = cenario["h"]
    # todas: + 3 "Entrega rápida" (positivo) e o CSAT sem comentário da Padaria Leste
    t = _painel(client, h, so_ativos="false", **MARCO)["tom"]
    assert (t["analisados"], t["positivo"], t["com_comentario"], t["total_respostas"]) == (10, 5, 11, 17)
    # Rede Leste: Carla, Caio e Cris (6 NPS + 2 CSAT); no anterior, sem comentários
    t = _painel(client, h, grupo_id=cenario["g1"]["id"], **MARCO)["tom"]
    assert t == {"analisados": 4, "com_comentario": 5, "total_respostas": 8, "pendentes": 1, "negativo": 2, "misto": 1,
                 "neutro": 0, "positivo": 1, "anterior": {"analisados": 0, "negativo": 0}, "ia_ligada": True,
                 "sem_analise": 0}
    # sem período: todo o histórico ("Demorou" entra) e sem anterior; só `de` também não tem anterior
    t = _painel(client, h)["tom"]
    assert (t["analisados"], t["negativo"], t["com_comentario"], t["total_respostas"], t["pendentes"], t["anterior"]) == (
        8, 4, 9, 17, 1, None)
    assert _painel(client, h, de="2026-03-17")["tom"]["anterior"] is None


def test_tom_sem_ia_e_periodo_vazio(client, cenario):
    t = _painel(client, cenario["h"], **MARCO)["tom"]
    # etapa 5h: os 8 comentários (todos com 3+ letras) estão sem análise e fora da fila; a IA está ligada na conta
    assert t == {"analisados": 0, "com_comentario": 8, "total_respostas": 13, "pendentes": 0, "negativo": 0, "misto": 0,
                 "neutro": 0, "positivo": 0, "anterior": {"analisados": 0, "negativo": 0}, "ia_ligada": True,
                 "sem_analise": 8}
    t = _painel(client, cenario["h"], de="2025-12-01", ate="2025-12-31")["tom"]
    assert t == {"analisados": 0, "com_comentario": 0, "total_respostas": 0, "pendentes": 0, "negativo": 0, "misto": 0,
                 "neutro": 0, "positivo": 0, "anterior": {"analisados": 0, "negativo": 0}, "ia_ligada": True,
                 "sem_analise": 0}


# ---- carteira e valor mensal no ranking -------------------------------------------

def test_carteira_por_filtro(client, cenario):
    h, g1, g2 = cenario["h"], cenario["g1"]["id"], cenario["g2"]["id"]

    def carteira(**f):
        return _painel(client, h, **f)["atencao"]["receita_em_risco"]["carteira"]
    # Atacado Norte 1.000 · Mercado Sul sem valor · Padaria Leste 500 (inativa) · Loja Oeste 300
    assert carteira(**MARCO) == 1300.0 and carteira() == 1300.0  # não depende do período
    assert carteira(so_ativos="false", **MARCO) == 1800.0
    assert carteira(grupo_id=g1, **MARCO) == 1000.0
    assert carteira(grupo_id=g2) == 300.0 and carteira(grupo_id=g2, so_ativos="false") == 800.0
    sem_valor = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Sem valor"}).json()
    criar_empresa(client, h, "Só Nome", grupo_id=sem_valor["id"])
    assert carteira(grupo_id=sem_valor["id"]) is None


def test_valor_mensal_no_ranking(client, cenario):
    p = _painel(client, cenario["h"], so_ativos="false", **MARCO)
    valores = {x["empresa"]["nome"]: x["valor_mensal"] for x in p["empresas"]["menor"] + p["empresas"]["maior"]}
    assert valores == {"Mercado Sul": None, "Atacado Norte": 1000.0, "Padaria Leste": 500.0}


# ---- isolamento entre contas -------------------------------------------------------

def test_acrescimos_respeitam_rls(client, cenario, dono):
    _sentimentos(dono, cenario["a"]["conta"]["id"])
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    hb = b["h"]
    db = Dados(dono, b["conta"]["id"], form_padrao(client, hb)["id"], form_padrao(client, hb, "csat")["id"])
    eb = criar_empresa(client, hb, "Empresa B", valor_mensal="900.00")
    cb = criar_contato(client, hb, empresa_id=eb["id"])
    for _ in range(3):
        db.resposta(cb, 0, "2026-03-10", comentario="Péssimo")
    sql(dono, "update respostas set ia_situacao = 'analisada', ia_sentimento = 'negativo' where conta_id = :c",
        c=b["conta"]["id"])
    pa = _painel(client, cenario["h"], **MARCO)
    assert pa["atencao"]["receita_em_risco"]["carteira"] == 1300.0
    assert (pa["tom"]["analisados"], pa["tom"]["negativo"]) == (7, 3)
    assert _por_mes(pa)["2026-03"]["total"] == 9
    assert eb["id"] not in [x["empresa"]["id"] for x in pa["empresas"]["menor"] + pa["empresas"]["maior"]]
    pb = _painel(client, hb, **MARCO)
    assert pb["atencao"]["receita_em_risco"]["carteira"] == 900.0
    assert pb["tom"] == {"analisados": 3, "com_comentario": 3, "total_respostas": 3, "pendentes": 0, "negativo": 3, "misto": 0,
                         "neutro": 0, "positivo": 0, "anterior": {"analisados": 0, "negativo": 0}, "ia_ligada": True,
                         "sem_analise": 0}
    assert sum(x["total"] for x in pb["evolucao_12m"]) == 3
    assert pb["empresas"]["menor"] == [{"empresa": {"id": eb["id"], "nome": "Empresa B"}, "nps": -100,
                                        "respostas": 3, "valor_mensal": 900.0}]


def test_tom_pendentes(client, cenario, dono):
    """`pendentes` = com comentário e análise na fila; sem comentário ou de outra situação não conta."""
    conta, h = cenario["a"]["conta"]["id"], cenario["h"]
    sql(dono, "update respostas set ia_situacao = 'pendente' where conta_id = :c", c=conta)
    t = _painel(client, h, **MARCO)["tom"]
    assert (t["analisados"], t["pendentes"], t["com_comentario"]) == (0, 8, 8)
    sql(dono, "update respostas set ia_situacao = 'falhou' where conta_id = :c and comentario_cliente = :t",
        c=conta, t="Produto quebrado")
    assert _painel(client, h, **MARCO)["tom"]["pendentes"] == 7
    # desligar a IA tira as pendentes da fila (situação nula): nada pendente
    sql(dono, "update respostas set ia_situacao = null where conta_id = :c and ia_situacao = 'pendente'", c=conta)
    assert _painel(client, h, **MARCO)["tom"]["pendentes"] == 0


def test_consultas_juntadas_dao_o_mesmo(client, cenario, dono):
    """A carteira (subconsulta escalar) e o tom (dentro de `_nps_csat`) batem com as consultas separadas."""
    from sqlalchemy import func, select

    from toqqi.core.db import em_conta
    from toqqi.modelos import Empresa, Resposta
    from toqqi.modulos.painel import servico as sv

    _sentimentos(dono, cenario["a"]["conta"]["id"])
    conta = cenario["a"]["conta"]["id"]
    for filtro in ({}, {"so_ativos": False}, {"grupo_id": cenario["g1"]["id"]}, {"grupo_id": cenario["g2"]["id"]}):
        f = sv.Filtro(conta, date(2026, 3, 1), date(2026, 3, 31), filtro.get("grupo_id"), filtro.get("so_ativos", True))
        with em_conta(conta) as s:
            conds = f.respostas()
            _, _, contagens = sv._nps_csat(s, conds)
            separado = s.execute(sv._com_empresa(select(*sv._contagens_tom()).select_from(Resposta))
                                 .where(*conds)).one()
            assert tuple(contagens) == tuple(separado)
            carteira = s.scalar(select(func.sum(Empresa.valor_mensal))
                                .where(Empresa.conta_id == conta, *f.empresa(Empresa.id)))
            assert sv._atencao(s, f, conds, date(2026, 4, 1))["receita_em_risco"]["carteira"] == carteira
