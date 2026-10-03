"""Decisão de 03/10 (docs/api-etapa-5d.md §0): o nível "Mais detalhado" (gpt-5, umas 5 vezes o custo do Equilibrado
para a Toqqi) gasta 2 análises da cota do plano por geração ou pergunta; o "Rápido" (era "Rápido e econômico") e o
"Equilibrado", 1. Reserva de N análises (atômica no limite, nunca parcial, pedidos ao mesmo tempo), devolução das N,
`custo` nos GET e nas respostas, `cota_insuficiente` (restam menos que o custo) ao lado do `cota_esgotada` (nenhuma
restante), o nível lido uma vez por pedido e `analises` nos níveis de GET /conta/ia."""
import threading
from dataclasses import replace
from datetime import datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from util import (
    API,
    conta_pronta,
    contexto_de,
    cota_do_mes,
    criar_contato,
    criar_empresa,
    definir_plano,
    estado_ia,
    fixar_relogio,
    form_padrao,
    gerar_ia,
    inserir_resposta,
    perguntar,
    sql,
    teto_do_mes,
    usar_cota,
)

from toqqi.core import ia_conversa, ia_texto, relogio
from toqqi.core.config import config
from toqqi.core.db import em_conta
from toqqi.core.errors import AppError
from toqqi.modelos import Conta
from toqqi.modulos.assistente import servico as assistente
from toqqi.modulos.assistente.limite import MAX_SIMULTANEAS
from toqqi.modulos.ia import cota, pareceres

pytestmark = pytest.mark.usefixtures("relogio_estavel")
mem = ia_texto.memoria
ESGOTADA = {"codigo": "cota_esgotada", "campos": {},
            "mensagem": "O limite mensal de análises de IA do seu plano foi atingido. Ele renova no dia 1º."}
INSUFICIENTE = {"codigo": "cota_insuficiente", "campos": {},
                "mensagem": "Resta 1 análise e o nível Mais detalhado gasta 2. Troque para o Equilibrado em "
                            "Configurações › IA ou aguarde o próximo mês."}


def mes_iso() -> str:
    return relogio.hoje().strftime("%Y-%m")


def cota_json(usadas: int, limite: int = 500) -> dict:
    return {"usadas": usadas, "limite": limite, "restantes": max(0, limite - usadas), "mes": mes_iso()}


def nivel(dono, conta_id: int, valor: str) -> None:
    """Troca o nível de modelo da conta direto no banco (como alguém em Configurações › IA)."""
    sql(dono, "update contas set ia_modelo = :n where id = :c", n=valor, c=conta_id)


def reservar(conta_id: int, quantidade: int) -> cota.Reserva | None:
    with em_conta(conta_id) as s:
        return cota.reservar(s, s.get(Conta, conta_id), quantidade)


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


@pytest.fixture
def com_respostas(client, admin, dono):
    """A conta com uma resposta NPS de hoje (o resumo e o parecer têm o que analisar)."""
    h, c = admin["h"], admin["conta"]["id"]
    empresa = criar_empresa(client, h, "Atacado Norte")
    contato = criar_contato(client, h, nome="Paula Lima", empresa_id=empresa["id"])
    inserir_resposta(dono, c, form_padrao(client, h)["id"], contato, 9, relogio.hoje(), comentario="Entrega rápida")
    return admin


# ---- níveis -------------------------------------------------------------------------------------------------

def test_niveis_com_rotulo_descricao_e_custo():
    assert [(o.valor, o.rotulo, o.descricao, o.analises) for o in ia_texto.MODELOS] == [
        ("rapido", "Rápido", "Respostas curtas e rápidas. Gasta 1 análise da cota.", 1),
        ("equilibrado", "Equilibrado", "O padrão: bom para o dia a dia. Gasta 1 análise da cota.", 1),
        ("detalhado", "Mais detalhado", "Análises mais cuidadosas; pode demorar mais. Gasta 2 análises da cota.", 2)]
    assert [ia_texto.analises_do_nivel(n) for n in ("rapido", "equilibrado", "detalhado", None, "turbo")] == [
        1, 1, 2, 1, 1]  # desconhecido vale como equilibrado
    assert ia_texto.rotulo_do_nivel("rapido") == "Rápido"
    assert all(not hasattr(o, "analises") for o in ia_texto.ESTILOS)


def test_get_e_put_conta_ia_com_analises_nos_niveis(client, admin):
    h = admin["h"]
    for r in (client.get(f"{API}/conta/ia", headers=h), client.put(f"{API}/conta/ia", headers=h,
                                                                    json={"modelo": "detalhado"})):
        assert r.status_code == 200, r.text
        assert [(m["valor"], m["rotulo"], m["analises"]) for m in r.json()["modelos"]] == [
            ("rapido", "Rápido", 1), ("equilibrado", "Equilibrado", 1), ("detalhado", "Mais detalhado", 2)]
        assert all(set(e) == {"valor", "rotulo", "descricao"} for e in r.json()["estilos"])


# ---- reserva e devolução de N análises ------------------------------------------------------------------------

def test_reservar_quantidade_no_limite_e_nunca_parcial(client, admin, dono, monkeypatch):
    c = admin["conta"]["id"]
    definir_plano(dono, c, "essencial")  # 100 por mês
    r = reservar(c, 2)  # sem a linha do mês: entra já com 2
    assert (r.usadas, r.limite, r.quantidade) == (2, 100, 2) and cota_do_mes(dono, c)[0] == 2
    usar_cota(dono, c, 98)
    r = reservar(c, 2)  # fecha exatamente no limite
    assert (r.usadas, r.quantidade) == (100, 2) and cota_do_mes(dono, c)[0] == 100
    assert reservar(c, 1) is None
    usar_cota(dono, c, 99)  # resta 1: as 2 não cabem e nada é gasto (nunca só uma parte)
    assert reservar(c, 2) is None and cota_do_mes(dono, c)[0] == 99
    assert reservar(c, 1).usadas == 100
    # mais que o limite inteiro (cortesia com 1): nem cria a linha do mês
    monkeypatch.setattr(config(), "IA_COTA_CORTESIA", 1)
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")["conta"]["id"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=outra)
    assert reservar(outra, 2) is None and cota_do_mes(dono, outra) == (0, 0, 0)
    with pytest.raises(ValueError):
        reservar(c, 0)


@pytest.mark.parametrize("usadas", [None, 95])
def test_reservas_de_2_ao_mesmo_tempo_nao_passam_do_limite(client, admin, dono, monkeypatch, usadas):
    """6 reservas de 2 ao mesmo tempo: só cabem 2; a análise que sobra não é gasta pela metade. Sem a linha do mês
    (cortesia com 5), todas tentam inserir juntas; com 95 de 100, todas caem na atualização condicional."""
    c = admin["conta"]["id"]
    if usadas is None:
        monkeypatch.setattr(config(), "IA_COTA_CORTESIA", 5)
        sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=c)
    else:
        definir_plano(dono, c, "essencial")
        usar_cota(dono, c, usadas)
    barreira = threading.Barrier(6)
    reservas: list = []

    def tentar():
        barreira.wait()
        reservas.append(reservar(c, 2))

    threads = [threading.Thread(target=tentar) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    feitas = [r for r in reservas if r is not None]
    assert len(reservas) == 6 and len(feitas) == 2 and {r.quantidade for r in feitas} == {2}
    assert sorted(r.usadas for r in feitas) == ([2, 4] if usadas is None else [97, 99])
    assert cota_do_mes(dono, c)[0] == (4 if usadas is None else 99)


def test_devolver_volta_a_quantidade_reservada_no_mes_da_reserva(client, admin, dono, monkeypatch):
    c = admin["conta"]["id"]
    usar_cota(dono, c, 10)
    reserva = reservar(c, 2)
    assert cota_do_mes(dono, c)[0] == 12
    cota.devolver(reserva)
    assert cota_do_mes(dono, c)[0] == 10
    cota.devolver(cota.Reserva(c, relogio.hoje().replace(day=1)))  # sem a quantidade: 1, como antes
    assert cota_do_mes(dono, c)[0] == 9
    usar_cota(dono, c, 1)  # nunca abaixo de zero
    cota.devolver(reserva)
    assert cota_do_mes(dono, c)[0] == 0
    # o mês virou entre a reserva e a devolução: as 2 voltam no mês da reserva
    usar_cota(dono, c, 7)
    reserva = reservar(c, 2)
    mes = relogio.hoje().replace(day=1)
    proximo = (mes + timedelta(days=32)).replace(day=1)
    fixar_relogio(monkeypatch, datetime.combine(proximo, time(0, 5), tzinfo=relogio.FUSO))
    usar_cota(dono, c, 3, proximo)
    cota.devolver(reserva)
    assert cota_do_mes(dono, c, mes)[0] == 7 and cota_do_mes(dono, c, proximo)[0] == 3


# ---- resumo, parecer e ToqqiAI no Mais detalhado --------------------------------------------------------------

@pytest.mark.parametrize("tipo", ["painel", "relatorios"])
def test_resumo_e_parecer_no_mais_detalhado_gastam_2_e_devolvem_2(client, com_respostas, dono, monkeypatch, tipo):
    h, c = com_respostas["h"], com_respostas["conta"]["id"]
    nivel(dono, c, "detalhado")
    usar_cota(dono, c, 10)
    r = estado_ia(client, h, tipo).json()
    assert (r["disponivel"], r["motivo"], r["cota"], r["custo"]) == (True, None, cota_json(10), 2)
    mem.programar("transitoria")
    assert gerar_ia(client, h, tipo).status_code == 503
    assert cota_do_mes(dono, c)[0] == 10  # devolveu as 2
    r = gerar_ia(client, h, tipo)  # a falha não conta para os 30 s
    assert r.status_code == 200, r.text
    assert (r.json()["custo"], r.json()["cota"], r.json()["item"]["modelo"], r.json()["item"]["modelo_rotulo"]) == (
        2, cota_json(12), "detalhado", "Mais detalhado")
    assert (mem.corpos[-1]["model"], mem.corpos[-1]["reasoning"]) == ("gpt-5", {"effort": "low"})
    assert cota_do_mes(dono, c)[0] == 12 and teto_do_mes(dono, c)[0] == 0  # o teto da análise por resposta não muda
    # erro inesperado depois de reservar (o banco recusa a gravação): também devolve as 2
    fixar_relogio(monkeypatch, relogio.agora() + timedelta(seconds=31))

    def salvar_quebrado(*_args):
        raise OperationalError("insert into ia_pareceres …", {}, Exception("banco fora"))

    monkeypatch.setattr(pareceres, "_salvar", salvar_quebrado)
    r = gerar_ia(TestClient(client.app, raise_server_exceptions=False), h, tipo)
    assert r.status_code == 503 and cota_do_mes(dono, c)[0] == 12


def test_pergunta_no_mais_detalhado_gasta_2_e_devolve_2(client, admin, dono):
    h, c = admin["h"], admin["conta"]["id"]
    nivel(dono, c, "detalhado")
    e = client.get(f"{API}/assistente", headers=h).json()
    assert (e["disponivel"], e["cota"], e["custo"]) == (True, cota_json(0), 2)
    r = perguntar(client, h)
    assert r.status_code == 200, r.text
    assert (r.json()["custo"], r.json()["cota"]) == (2, cota_json(2))
    assert {x["model"] for x in ia_conversa.memoria.corpos} == {"gpt-5"}
    ia_conversa.memoria.programar("transitoria")
    assert perguntar(client, h).status_code == 503 and cota_do_mes(dono, c)[0] == 2  # devolveu as 2
    ia_conversa.memoria.programar(RuntimeError("bug no meio da conversa"))
    assert perguntar(TestClient(client.app, raise_server_exceptions=False), h).status_code == 500
    assert cota_do_mes(dono, c)[0] == 2
    # no Equilibrado volta a gastar 1
    nivel(dono, c, "equilibrado")
    r = perguntar(client, h)
    assert (r.json()["custo"], r.json()["cota"]) == (1, cota_json(3))


# ---- cota insuficiente e cota esgotada --------------------------------------------------------------------------

def test_resta_1_no_mais_detalhado_e_cota_insuficiente_e_com_0_continua_esgotada(client, com_respostas, dono):
    h, c = com_respostas["h"], com_respostas["conta"]["id"]
    nivel(dono, c, "detalhado")
    usar_cota(dono, c, 499)  # resta 1 e o Mais detalhado gasta 2
    for tipo in ("painel", "relatorios"):
        r = estado_ia(client, h, tipo).json()
        assert (r["disponivel"], r["motivo"], r["cota"], r["custo"]) == (False, "cota_insuficiente", cota_json(499), 2)
        r = gerar_ia(client, h, tipo)
        assert r.status_code == 409 and r.json()["erro"] == INSUFICIENTE
    assert client.get(f"{API}/assistente", headers=h).json() == {
        "disponivel": False, "motivo": "cota_insuficiente", "cota": cota_json(499), "custo": 2, "sugestoes": []}
    r = perguntar(client, h)
    assert r.status_code == 409 and r.json()["erro"] == INSUFICIENTE
    # nada foi gasto nem chegou à IA
    assert cota_do_mes(dono, c)[0] == 499 and mem.corpos == [] and ia_conversa.memoria.corpos == []
    # no Equilibrado, a última análise serve
    nivel(dono, c, "equilibrado")
    assert estado_ia(client, h).json()["disponivel"] is True
    r = gerar_ia(client, h)
    assert r.status_code == 200 and (r.json()["custo"], r.json()["cota"]) == (1, cota_json(500))
    # nenhuma restante: cota_esgotada, como antes, em qualquer nível
    for n in ("equilibrado", "detalhado"):
        nivel(dono, c, n)
        r = estado_ia(client, h, "relatorios").json()
        assert (r["disponivel"], r["motivo"], r["custo"]) == (False, "cota_esgotada", ia_texto.analises_do_nivel(n))
        assert client.get(f"{API}/assistente", headers=h).json()["motivo"] == "cota_esgotada"
        r = gerar_ia(client, h, "relatorios")
        assert r.status_code == 409 and r.json()["erro"] == ESGOTADA
        r = perguntar(client, h)
        assert r.status_code == 409 and r.json()["erro"] == ESGOTADA
    # conta pausada vem antes da cota
    sql(dono, "update contas set situacao = 'teste_expirado' where id = :c", c=c)
    usar_cota(dono, c, 499)
    assert client.get(f"{API}/assistente", headers=h).json()["motivo"] == "conta_pausada"
    assert gerar_ia(client, h, "relatorios").json()["erro"]["codigo"] == "conta_pausada"


def test_mensagem_de_cota_insuficiente_no_plural(client, admin, dono, monkeypatch):
    """Com um nível que gastasse 3, restar 2 também é insuficiente: a mensagem vai no plural."""
    h, c = admin["h"], admin["conta"]["id"]
    caro = tuple(replace(o, analises=3) if o.valor == "detalhado" else o for o in ia_texto.MODELOS)
    monkeypatch.setattr(ia_texto, "MODELOS", caro)
    assert cota.mensagem_insuficiente(2, "detalhado") == (
        "Restam 2 análises e o nível Mais detalhado gasta 3. Troque para o Equilibrado em Configurações › IA ou "
        "aguarde o próximo mês.")
    assert [cota.motivo_sem_saldo({"restantes": n}, 3) for n in (0, 1, 2, 3, 4)] == [
        "cota_esgotada", "cota_insuficiente", "cota_insuficiente", None, None]
    nivel(dono, c, "detalhado")
    usar_cota(dono, c, 498)
    assert client.get(f"{API}/assistente", headers=h).json()["motivo"] == "cota_insuficiente"
    r = perguntar(client, h)
    assert r.status_code == 409 and r.json()["erro"]["mensagem"].startswith(
        "Restam 2 análises e o nível Mais detalhado gasta 3.")
    assert cota_do_mes(dono, c)[0] == 498


def test_perguntas_ao_mesmo_tempo_no_mais_detalhado(client, admin, dono):
    """Restam 5 e cada pergunta gasta 2: passam 2; as outras recebem `cota_insuficiente` (resta 1) e a última
    análise não é gasta."""
    c = admin["conta"]["id"]
    definir_plano(dono, c, "essencial")
    usar_cota(dono, c, 95)
    nivel(dono, c, "detalhado")
    ctx = contexto_de(admin)
    n = MAX_SIMULTANEAS  # cada uma de um usuário: cabem todas nas vagas do processo
    barreira = threading.Barrier(n)
    resultados: list[str] = []

    def tentar(usuario_id):
        barreira.wait()
        try:
            assistente.perguntar(replace(ctx, usuario_id=usuario_id), "Como importo meus contatos?", [])
            resultados.append("ok")
        except AppError as erro:
            resultados.append(erro.codigo)

    threads = [threading.Thread(target=tentar, args=(2000 + i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(resultados) == ["cota_insuficiente"] * (n - 2) + ["ok"] * 2
    assert cota_do_mes(dono, c)[0] == 99


# ---- o nível é lido uma vez por pedido --------------------------------------------------------------------------

@pytest.mark.parametrize("antes,depois", [("equilibrado", "detalhado"), ("detalhado", "rapido")])
def test_nivel_lido_uma_vez_por_pedido(client, com_respostas, dono, monkeypatch, antes, depois):
    """Alguém troca o nível logo depois da reserva: o pedido segue com o nível lido no começo (nunca cobra 1 e roda o
    Mais detalhado, nem o contrário), e a falha devolve exatamente o que foi reservado."""
    h, c = com_respostas["h"], com_respostas["conta"]["id"]
    custo, modelo = ia_texto.analises_do_nivel(antes), ia_texto.modelo_do_nivel(antes)[0]
    original = cota.reservar

    def reservar_e_trocar(s, conta, quantidade=1):
        reserva = original(s, conta, quantidade)
        nivel(dono, c, depois)
        return reserva

    monkeypatch.setattr(cota, "reservar", reservar_e_trocar)
    nivel(dono, c, antes)
    r = gerar_ia(client, h)
    assert r.status_code == 200, r.text
    assert (r.json()["custo"], r.json()["item"]["modelo"], mem.corpos[-1]["model"]) == (custo, antes, modelo)
    assert cota_do_mes(dono, c)[0] == custo
    nivel(dono, c, antes)
    r = perguntar(client, h)
    assert r.status_code == 200 and r.json()["custo"] == custo
    assert {x["model"] for x in ia_conversa.memoria.corpos} == {modelo}
    assert cota_do_mes(dono, c)[0] == 2 * custo
    # falhou com o nível já trocado: devolve o que reservou, não o custo do nível novo
    nivel(dono, c, antes)
    mem.programar("transitoria")
    assert gerar_ia(client, h, "relatorios").status_code == 503
    assert mem.corpos[-1]["model"] == modelo
    nivel(dono, c, antes)
    ia_conversa.memoria.programar("transitoria")
    assert perguntar(client, h).status_code == 503
    assert cota_do_mes(dono, c)[0] == 2 * custo
