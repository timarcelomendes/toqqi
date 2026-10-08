"""Panorama dos Planos de ação (docs/api-acoes-panorama.md): os prazos das abertas, a carga por responsável e as
concluídas nos últimos 30 dias (mediana de dias e retorno ao cliente), com os filtros do quadro."""
from datetime import timedelta

import pytest
from util import API, conta_pronta, criar_empresa, criar_responsavel, membro, sql

from toqqi.core import relogio

pytestmark = pytest.mark.usefixtures("relogio_estavel")


@pytest.fixture
def conta(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h = a["h"]
    rita = criar_responsavel(client, h, "Rita Gomes")
    bruno = criar_responsavel(client, h, "Bruno Dias")
    grupo = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Varejo"}).json()
    norte = criar_empresa(client, h, "Atacado Norte", grupo_id=grupo["id"])
    sul = criar_empresa(client, h, "Mercado Sul")
    return {"h": h, "conta_id": a["conta"]["id"], "rita": rita, "bruno": bruno, "grupo": grupo, "norte": norte,
            "sul": sul}


def _criar(client, h, **campos) -> dict:
    r = client.post(f"{API}/acoes", headers=h, json={"titulo": "Ação", **campos})
    assert r.status_code == 201, r.text
    return r.json()


def _panorama(client, h, **filtros) -> dict:
    r = client.get(f"{API}/acoes/panorama", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()


def _d(n: int) -> str:
    return (relogio.hoje() + timedelta(days=n)).isoformat()


def test_conta_sem_acoes(client, conta):
    p = _panorama(client, conta["h"])
    assert p["prazos"] == {"abertas": 0, "vencidas": 0, "hoje": 0, "proximos_7_dias": 0, "depois": 0, "sem_prazo": 0}
    assert p["responsaveis"] == []
    hoje = relogio.hoje()
    assert p["concluidas"] == {
        "de": (hoje - timedelta(days=29)).isoformat(), "ate": hoje.isoformat(), "total": 0, "mediana_dias": None,
        "com_retorno": 0, "anterior": {"de": (hoje - timedelta(days=59)).isoformat(),
                                       "ate": (hoje - timedelta(days=30)).isoformat(), "total": 0,
                                       "mediana_dias": None, "com_retorno": 0}}


def test_prazos_e_responsaveis(client, conta):
    h, rita, bruno = conta["h"], conta["rita"], conta["bruno"]
    _criar(client, h, prazo=_d(-3), responsavel_id=rita["id"])
    _criar(client, h, prazo=_d(-1), responsavel_id=rita["id"])
    _criar(client, h, prazo=_d(0), responsavel_id=bruno["id"])
    _criar(client, h, prazo=_d(7), responsavel_id=bruno["id"])
    _criar(client, h, prazo=_d(8), responsavel_id=bruno["id"])
    andamento = _criar(client, h, prazo=_d(2))  # sem responsável, em andamento
    client.patch(f"{API}/acoes/{andamento['id']}", headers=h, json={"situacao": "em_andamento"})
    _criar(client, h)  # sem prazo, sem responsável
    feita = _criar(client, h, prazo=_d(-10), responsavel_id=bruno["id"])  # concluída: não conta nos prazos
    client.patch(f"{API}/acoes/{feita['id']}", headers=h, json={"situacao": "concluida", "resolucao": "Feito"})
    p = _panorama(client, h)
    assert p["prazos"] == {"abertas": 7, "vencidas": 2, "hoje": 1, "proximos_7_dias": 2, "depois": 1, "sem_prazo": 1}
    # quem tem mais vencidas primeiro; depois mais abertas; sem responsável no fim do empate
    assert p["responsaveis"] == [
        {"responsavel": {"id": rita["id"], "nome": "Rita Gomes"}, "abertas": 2, "vencidas": 2},
        {"responsavel": {"id": bruno["id"], "nome": "Bruno Dias"}, "abertas": 3, "vencidas": 0},
        {"responsavel": None, "abertas": 2, "vencidas": 0},
    ]
    # "Só vencidas" não recorta o panorama; o filtro de responsável recorta os prazos, mas não a lista de pessoas
    assert _panorama(client, h, so_vencidas="true")["prazos"]["abertas"] == 7
    p = _panorama(client, h, responsavel_id=rita["id"])
    assert p["prazos"]["abertas"] == 2 and p["prazos"]["vencidas"] == 2 and len(p["responsaveis"]) == 3
    assert _panorama(client, h, responsavel_id=0)["prazos"]["abertas"] == 2  # sem responsável


def test_filtros_do_quadro_valem(client, conta):
    h = conta["h"]
    _criar(client, h, empresa_id=conta["norte"]["id"], prazo=_d(-1))
    _criar(client, h, empresa_id=conta["sul"]["id"], prazo=_d(1))
    assert _panorama(client, h, grupo_id=conta["grupo"]["id"])["prazos"] == {
        "abertas": 1, "vencidas": 1, "hoje": 0, "proximos_7_dias": 0, "depois": 0, "sem_prazo": 0}
    assert _panorama(client, h, busca="Mercado")["prazos"]["abertas"] == 1
    assert _panorama(client, h, empresa_id=conta["sul"]["id"])["prazos"]["proximos_7_dias"] == 1


def test_concluidas_mediana_e_retorno(client, conta, dono):
    h, rita = conta["h"], conta["rita"]
    ids = []
    for _ in range(4):
        a = _criar(client, h, responsavel_id=rita["id"])
        r = client.patch(f"{API}/acoes/{a['id']}", headers=h, json={"situacao": "concluida", "resolucao": "Feito"})
        assert r.status_code == 200, r.text
        ids.append(a["id"])
    agora = relogio.agora()
    # 2, 4 e 10 dias da criação à conclusão nos últimos 30 dias (mediana 4); uma de 40 dias atrás (período anterior)
    for i, (criada, concluida) in zip(ids, ((12, 10), (9, 5), (15, 5), (45, 40)), strict=True):
        sql(dono, "update acoes set criada_em = :c, concluida_em = :f where id = :i",
            c=agora - timedelta(days=criada), f=agora - timedelta(days=concluida), i=i)
    sql(dono, "update acoes set retorno_em = now(), retorno_texto = 'Trocamos o produto.' where id = :i", i=ids[0])
    c = _panorama(client, h)["concluidas"]
    assert (c["total"], c["mediana_dias"], c["com_retorno"]) == (3, 4.0, 1)
    assert (c["anterior"]["total"], c["anterior"]["mediana_dias"], c["anterior"]["com_retorno"]) == (1, 5.0, 0)


def test_permissao_e_outra_conta(client, conta):
    h = conta["h"]
    _criar(client, h, prazo=_d(-1))
    consulta = membro(client, h, "caio@alfa.com.br", perfil="consulta")["h"]
    assert client.get(f"{API}/acoes/panorama", headers=consulta).status_code == 200
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert _panorama(client, outra["h"])["prazos"]["abertas"] == 0
