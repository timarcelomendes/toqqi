"""Etapa 4a: painel (todos os blocos com um conjunto pequeno calculado à mão), filtros, exportação e desempenho."""
import csv
import io
import time as relogio_real
from datetime import date, datetime, time, timedelta

import pytest
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_form,
    criar_responsavel,
    definir_plano,
    form_padrao,
    ligar_envios,
    link_pesquisa,
    lista_respostas,
    membro,
    perfil_id,
    registrar_resposta,
    sql,
)

from toqqi.core import relogio
from toqqi.modulos.formularios.validacao import grupo_da_nota
from toqqi.modulos.respostas.registro import temas_da_resposta

pytestmark = pytest.mark.usefixtures("relogio_estavel")
MARCO = {"de": "2026-03-01", "ate": "2026-03-31"}


def _dia(d: date | str) -> datetime:
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return datetime.combine(d, time(12), tzinfo=FUSO)


class Dados:
    """Insere direto no banco (como o dono, em modo sistema) para controlar datas e situações."""

    def __init__(self, dono, conta_id: int, nps_id: int, csat_id: int):
        self.dono, self.conta, self.nps, self.csat = dono, conta_id, nps_id, csat_id

    def resposta(self, contato: dict | None, nota: int, quando: str, tipo: str = "nps", comentario: str = "",
                 arquivada: bool = False) -> int:
        empresa = contato["empresa"]["id"] if contato and contato["empresa"] else None
        (rid,), = sql(self.dono, """
            insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota,
                                   grupo, comentario, comentario_cliente, temas, respondida_em, arquivada)
            values (:conta, :f, :c, :e, 'manual', 'manual', :n, :t, :g, :com, :com, :temas, :quando, :arq)
            returning id
        """, conta=self.conta, f=self.nps if tipo == "nps" else self.csat, c=contato["id"] if contato else None,
            e=empresa, n=nota, t=tipo, g=grupo_da_nota(tipo, nota), com=comentario,
            temas=temas_da_resposta(comentario), quando=_dia(quando), arq=arquivada)
        return rid

    def convite(self, contato: dict, quando: str, situacao: str | None, canal: str = "email") -> None:
        (cid,), = sql(self.dono, """
            insert into convites (conta_id, token_hash, formulario_id, contato_id, canal, criado_em)
            values (:conta, md5(random()::text), :f, :c, :canal, :quando) returning id
        """, conta=self.conta, f=self.nps, c=contato["id"], canal=canal, quando=_dia(quando))
        if situacao:
            sql(self.dono, """
                insert into envios (conta_id, contato_id, convite_id, canal, tipo, origem, situacao, para, criado_em)
                values (:conta, :c, :cid, :canal, 'convite', 'manual', :s, 'x', :quando)
            """, conta=self.conta, c=contato["id"], cid=cid, canal="whatsapp" if canal == "whatsapp" else "email",
                s=situacao, quando=_dia(quando))

    def acao(self, titulo: str, empresa: dict | None, situacao: str = "a_fazer", prazo: date | None = None,
             criada: datetime | None = None, prioridade: str = "media") -> int:
        (aid,), = sql(self.dono, """
            insert into acoes (conta_id, empresa_id, titulo, prioridade, prazo, situacao, origem, criada_em)
            values (:conta, :e, :t, :p, :prazo, :s, 'manual', :criada) returning id
        """, conta=self.conta, e=empresa["id"] if empresa else None, t=titulo, p=prioridade, prazo=prazo, s=situacao,
            criada=criada or relogio.agora())
        return aid


@pytest.fixture
def cenario(client, dono, relogio_estavel):
    """Conjunto calculado à mão (comentários nos asserts de cada bloco)."""
    hoje = relogio_estavel
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h = a["h"]
    g1 = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Leste"}).json()
    g2 = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Oeste"}).json()
    rita = criar_responsavel(client, h, "Rita Gomes")
    e1 = criar_empresa(client, h, "Atacado Norte", grupo_id=g1["id"], valor_mensal="1000.00",
                       responsavel_id=rita["id"])
    e2 = criar_empresa(client, h, "Mercado Sul", grupo_id=g1["id"])
    e3 = criar_empresa(client, h, "Padaria Leste", grupo_id=g2["id"], valor_mensal="500.00", ativa=False)
    e4 = criar_empresa(client, h, "Loja Oeste", grupo_id=g2["id"], valor_mensal="300.00")
    decisor = perfil_id(client, h, "Decisor")
    c1 = criar_contato(client, h, nome="Carla Um", empresa_id=e1["id"], perfil_id=decisor)
    c2 = criar_contato(client, h, nome="Caio Dois", empresa_id=e1["id"])
    c3 = criar_contato(client, h, nome="Cris Três", empresa_id=e2["id"], perfil_id=decisor)
    c4 = criar_contato(client, h, nome="Cid Quatro", empresa_id=e3["id"])
    c5 = criar_contato(client, h, nome="Cléo Cinco", empresa_id=e4["id"])
    c6 = criar_contato(client, h, nome="Ciro Seis")
    c7 = criar_contato(client, h, nome="Célia Sete", empresa_id=e4["id"])
    c8 = criar_contato(client, h, nome="Cadu Oito", empresa_id=e1["id"], ativo=False)
    c9 = criar_contato(client, h, nome="Cora Nove", empresa_id=e1["id"])
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])

    # NPS no período (março/2026)
    d.resposta(c1, 3, "2026-03-05", comentario="Entrega atrasou e o frete é caro")
    d.resposta(c1, 10, "2026-03-06", comentario="Atendimento excelente")
    d.resposta(c2, 8, "2026-03-08", comentario="Entrega ok, mas o preço subiu")
    d.resposta(c3, 0, "2026-03-10", comentario="Produto quebrado")
    d.resposta(c3, 6, "2026-03-11", comentario="Atrasou de novo")
    d.resposta(c3, 2, "2026-03-12")
    for dia in ("2026-03-13", "2026-03-14", "2026-03-15"):  # empresa inativa
        d.resposta(c4, 10, dia, comentario="Entrega rápida")
    d.resposta(c5, 9, "2026-03-16", comentario="Vendedor atencioso")
    d.resposta(c5, 7, "2026-03-17", comentario="Site lento")
    d.resposta(c6, 9, "2026-03-18")
    d.resposta(c1, 0, "2026-03-25", comentario="Péssimo", arquivada=True)  # arquivada: fora de tudo
    # CSAT no período
    d.resposta(c1, 5, "2026-03-20", tipo="csat")
    d.resposta(c2, 4, "2026-03-21", tipo="csat")
    d.resposta(c5, 2, "2026-03-22", tipo="csat", comentario="Motorista grosseiro")
    d.resposta(c6, 3, "2026-03-23", tipo="csat")
    d.resposta(c4, 1, "2026-03-24", tipo="csat")  # empresa inativa
    # período anterior (29/01 a 28/02) e antes
    d.resposta(c2, 9, "2026-02-11")
    d.resposta(c5, 3, "2026-02-12", comentario="Demorou")
    d.resposta(c3, 10, "2026-02-13")
    d.resposta(c6, 2, "2025-11-01")

    # convites
    d.convite(c1, "2026-03-01", "enviado")
    d.convite(c2, "2026-03-02", "aberto_no_whatsapp", canal="whatsapp")
    d.convite(c3, "2026-03-03", "erro")
    d.convite(c5, "2026-02-01", "enviado")
    d.convite(c6, "2026-03-04", "entregue", canal="whatsapp")
    d.convite(c4, "2026-03-05", "enviado")
    d.convite(c7, "2026-03-06", "enviado")
    d.convite(c8, "2026-03-07", "enviado")
    d.convite(c9, "2026-03-08", None, canal="link_manual")

    # ações
    a1 = d.acao("A1", e1, prazo=hoje - timedelta(days=3), prioridade="alta", criada=_dia("2026-03-01"))
    a2 = d.acao("A2", e1, situacao="em_andamento", prazo=hoje + timedelta(days=5), criada=_dia("2026-03-02"))
    a3 = d.acao("A3", e2, criada=_dia("2026-02-01"))
    d.acao("A4", e3, prazo=hoje - timedelta(days=1), criada=_dia("2026-01-01"))
    d.acao("A5", e4, situacao="concluida", criada=_dia("2025-01-01"))
    d.acao("A6", None, prazo=hoje - timedelta(days=10))
    a7 = d.acao("A7", e4, prazo=hoje + timedelta(days=1))
    return {"h": h, "a": a, "g1": g1, "g2": g2, "rita": rita, "e": [None, e1, e2, e3, e4],
            "c": [None, c1, c2, c3, c4, c5, c6, c7, c8, c9], "acoes": {"a1": a1, "a2": a2, "a3": a3, "a7": a7},
            "hoje": hoje, "dados": d}


def _painel(client, h, **filtros) -> dict:
    r = client.get(f"{API}/painel", headers=h, params=filtros)
    assert r.status_code == 200, r.text
    return r.json()


def test_painel_marco(client, cenario):
    p = _painel(client, cenario["h"], **MARCO)
    e1, e2, e3, e4 = cenario["e"][1:]
    c = cenario["c"]
    assert p["periodo"] == {"de": "2026-03-01", "ate": "2026-03-31",
                            "anterior": {"de": "2026-01-29", "ate": "2026-02-28"}}
    # NPS (só ativos): E1 3,10,8 · E2 0,6,2 · E4 9,7 · sem empresa 9 → 3 P, 2 N, 4 D em 9 → −11,1 → −11
    assert p["nps"] == {
        "valor": -11, "faixa": "critico", "promotores": 3, "neutros": 2, "detratores": 4, "total": 9,
        "pct": {"promotores": 33.3, "neutros": 22.2, "detratores": 44.4},
        "decisores": {"valor": -60, "total": 5},  # Carla 3,10 e Cris 0,6,2 → (1 − 4) / 5
    }
    # anterior (29/01–28/02): Caio 9, Cléo 3, Cris 10 → 33; −11 − 33 = −44
    assert p["variacao"] == {"valor": -44, "anterior": 33}
    # CSAT: 5, 4, 2, 3 (a da empresa inativa fica fora) → 2 de 4 = 50%, média 3,5
    assert p["csat"] == {"percentual": 50, "media": 3.5, "total": 4, "satisfeitos": 2}
    # convidados: Carla (enviado), Caio (WhatsApp aberto), Ciro (entregue), Célia (enviado, não respondeu);
    # fora: Cris (erro), Cléo (convite de fevereiro), Cid (empresa inativa), Cadu (inativo), Cora (só link)
    assert p["taxa_resposta"] == {"percentual": 75, "responderam": 3, "convidados": 4, "amostra_pequena": False}
    # movimentação: Carla 3→10 e Ciro 2 (2025)→9 resgatados; Caio 9 (fev)→8 e Cléo 9→7 deixaram de ser promotores
    mov = p["movimentacao"]
    assert (mov["resgatados"], mov["deixaram_de_ser_promotores"]) == (2, 2)
    assert [(x["tipo"], x["contato"]["id"], x["nota_anterior"], x["nota_atual"]) for x in mov["itens"]] == [
        ("resgatado", c[6]["id"], 2, 9), ("deixou_de_ser_promotor", c[5]["id"], 9, 7),
        ("deixou_de_ser_promotor", c[2]["id"], 9, 8), ("resgatado", c[1]["id"], 3, 10)]
    ciro = mov["itens"][0]
    assert ciro["empresa"] is None and ciro["contato"]["nome"] == "Ciro Seis"
    assert datetime.fromisoformat(ciro["data_anterior"]) == _dia("2025-11-01")
    assert datetime.fromisoformat(ciro["data_atual"]) == _dia("2026-03-18")
    assert mov["itens"][2]["empresa"] == {"id": e1["id"], "nome": "Atacado Norte"}

    # atenção (sem período): abertas A1, A2, A3, A6, A7; vencidas A1 e A6 (A4 é de empresa inativa)
    at = p["atencao"]
    assert (at["acoes_abertas"], at["acoes_vencidas"], at["tudo_em_dia"]) == (5, 2, False)
    assert [x["empresa"]["nome"] for x in at["empresas"]] == ["Atacado Norte", "Mercado Sul", "Loja Oeste"]
    norte, sul, oeste = at["empresas"]
    assert (norte["nps"], norte["acoes_abertas"], norte["acoes_vencidas"], norte["acao_id"]) == (
        0, 2, 1, cenario["acoes"]["a1"])
    assert norte["responsavel"] == {"id": cenario["rita"]["id"], "nome": "Rita Gomes"}
    assert norte["ultimo_comentario_detrator"] == "Entrega atrasou e o frete é caro"  # a arquivada não conta
    assert datetime.fromisoformat(norte["desde"]) == _dia("2026-03-01")
    assert (sul["nps"], sul["acoes_vencidas"], sul["acao_id"], sul["responsavel"]) == (
        -100, 0, cenario["acoes"]["a3"], None)
    assert sul["ultimo_comentario_detrator"] == "Atrasou de novo"
    assert (oeste["nps"], oeste["acao_id"], oeste["ultimo_comentario_detrator"]) == (
        50, cenario["acoes"]["a7"], "Demorou")  # o comentário pode ser de qualquer data
    # receita em risco: empresas com detrator em março: Atacado Norte (R$ 1.000) e Mercado Sul (sem valor)
    assert at["receita_em_risco"] == {"valor": 1000.0, "empresas": 2, "sem_valor": 1}

    # temas (só NPS): prazo 3 (3, 8, 6 → 5,7); atendimento 2 (9,5); preço 2 (5,5); produto 1; sistema 1
    assert p["temas"] == [
        {"chave": "prazo_entrega", "rotulo": "Prazo e entrega", "mencoes": 3, "nota_media": 5.7},
        {"chave": "atendimento", "rotulo": "Atendimento", "mencoes": 2, "nota_media": 9.5},
        {"chave": "preco_condicoes", "rotulo": "Preço e condições", "mencoes": 2, "nota_media": 5.5},
        {"chave": "produto_avarias", "rotulo": "Produto e avarias", "mencoes": 1, "nota_media": 0.0},
        {"chave": "sistema_pedidos", "rotulo": "Sistema e pedidos", "mencoes": 1, "nota_media": 7.0},
    ]
    assert [x["comentario"] for x in p["comentarios"]] == [
        "Motorista grosseiro", "Site lento", "Vendedor atencioso", "Atrasou de novo", "Produto quebrado",
        "Entrega ok, mas o preço subiu"]
    primeiro = p["comentarios"][0]
    assert (primeiro["tipo_nota"], primeiro["nota"], primeiro["grupo"]) == ("csat", 2, "insatisfeito")
    assert primeiro["contato"] == {"id": c[5]["id"], "nome": "Cléo Cinco"}
    assert primeiro["empresa"] == {"id": e4["id"], "nome": "Loja Oeste"}
    assert p["evolucao"] == [{"mes": "2026-03", "nps": -11, "total": 9}]
    # empresas com 3+ respostas NPS: Mercado Sul (−100) e Atacado Norte (0); Loja Oeste só tem 2
    assert p["empresas"] == {
        "menor": [{"empresa": {"id": e2["id"], "nome": "Mercado Sul"}, "nps": -100, "respostas": 3}],
        "maior": [{"empresa": {"id": e1["id"], "nome": "Atacado Norte"}, "nps": 0, "respostas": 3}],
    }
    assert p["palavras"] == [
        {"palavra": "atrasou", "total": 2}, {"palavra": "entrega", "total": 2},
        {"palavra": "atencioso", "total": 1}, {"palavra": "atendimento", "total": 1},
        {"palavra": "caro", "total": 1}, {"palavra": "excelente", "total": 1}, {"palavra": "frete", "total": 1},
        {"palavra": "grosseiro", "total": 1}, {"palavra": "lento", "total": 1}, {"palavra": "motorista", "total": 1},
        {"palavra": "novo", "total": 1}, {"palavra": "preço", "total": 1}]
    assert p["primeiros_passos"] == {"contatos": True, "envios_ligados": False, "primeiro_envio": True,
                                     "primeira_resposta": True}
    assert e3["id"] not in [x["empresa"]["id"] for x in p["empresas"]["menor"] + p["empresas"]["maior"]]


def test_so_ativos_desligado(client, cenario):
    p = _painel(client, cenario["h"], so_ativos="false", **MARCO)
    # + Padaria Leste (inativa): 10, 10, 10 → 6 P, 2 N, 4 D em 12 → 16,7 → 17
    assert (p["nps"]["valor"], p["nps"]["total"]) == (17, 12)
    assert p["csat"] == {"percentual": 40, "media": 3.0, "total": 5, "satisfeitos": 2}
    assert p["taxa_resposta"] == {"percentual": 80, "responderam": 4, "convidados": 5, "amostra_pequena": False}
    assert (p["atencao"]["acoes_abertas"], p["atencao"]["acoes_vencidas"]) == (6, 3)
    assert [x["empresa"]["nome"] for x in p["atencao"]["empresas"]] == [
        "Padaria Leste", "Atacado Norte", "Mercado Sul", "Loja Oeste"]
    assert p["temas"][0] == {"chave": "prazo_entrega", "rotulo": "Prazo e entrega", "mencoes": 6, "nota_media": 7.8}
    # 3 empresas: as 2 piores em "menor", a melhor em "maior", sem repetir
    assert [x["empresa"]["nome"] for x in p["empresas"]["menor"]] == ["Mercado Sul", "Atacado Norte"]
    assert [(x["empresa"]["nome"], x["nps"]) for x in p["empresas"]["maior"]] == [("Padaria Leste", 100)]


def test_filtro_grupo_de_empresas(client, cenario):
    p = _painel(client, cenario["h"], grupo_id=cenario["g1"]["id"], **MARCO)
    # Atacado Norte + Mercado Sul: 1 P, 1 N, 4 D em 6 → −50; sem empresa e outras redes ficam fora
    assert (p["nps"]["valor"], p["nps"]["total"]) == (-50, 6)
    assert p["variacao"] == {"valor": -150, "anterior": 100}  # anterior: Caio 9 e Cris 10
    assert p["csat"]["total"] == 2
    assert p["taxa_resposta"]["convidados"] == 2 and p["taxa_resposta"]["percentual"] == 100
    assert (p["atencao"]["acoes_abertas"], p["atencao"]["acoes_vencidas"]) == (3, 1)  # A6 (sem empresa) sai
    assert [x["tipo"] for x in p["movimentacao"]["itens"]] == ["deixou_de_ser_promotor", "resgatado"]
    assert p["atencao"]["receita_em_risco"] == {"valor": 1000.0, "empresas": 2, "sem_valor": 1}


def test_sem_periodo(client, cenario):
    p = _painel(client, cenario["h"])
    assert p["periodo"] == {"de": None, "ate": None, "anterior": None}
    assert p["variacao"] is None  # sem período, não há variação
    # todo o histórico (só ativos): março (9) + fevereiro (3) + novembro (1) = 13
    assert p["nps"]["total"] == 13
    assert p["evolucao"] == [{"mes": "2025-11", "nps": -100, "total": 1}, {"mes": "2026-02", "nps": 33, "total": 3},
                             {"mes": "2026-03", "nps": -11, "total": 9}]
    assert (p["atencao"]["acoes_abertas"], p["atencao"]["acoes_vencidas"]) == (5, 2)  # igual: ignora período
    # Cléo: a última de todas (7, março) contra a anterior (9) continua "deixou de ser promotor"
    assert p["movimentacao"]["deixaram_de_ser_promotores"] == 2
    so_inicio = _painel(client, cenario["h"], de="2026-03-17")
    assert so_inicio["variacao"] is None and so_inicio["periodo"]["anterior"] is None
    assert so_inicio["nps"]["total"] == 2  # Cléo 7 e Ciro 9


def test_variacao_some_sem_respostas_no_anterior(client, cenario):
    p = _painel(client, cenario["h"], de="2026-03-16", ate="2026-03-31")  # 16 dias: anterior 28/02 a 15/03
    assert p["periodo"]["anterior"] == {"de": "2026-02-28", "ate": "2026-03-15"}
    # Cléo 9, 7 e Ciro 9 (1 N, 2 P → 67) contra Carla 3, 10 · Caio 8 · Cris 0, 6, 2 (1 P, 1 N, 4 D → −50)
    assert p["variacao"] == {"valor": 117, "anterior": -50}
    p = _painel(client, cenario["h"], de="2025-12-01", ate="2025-12-31")
    assert p["nps"]["valor"] is None and p["variacao"] is None and p["nps"]["faixa"] is None
    assert p["nps"]["pct"] == {"promotores": 0.0, "neutros": 0.0, "detratores": 0.0}
    assert p["csat"] == {"percentual": None, "media": None, "total": 0, "satisfeitos": 0}
    assert p["evolucao"] == [] and p["comentarios"] == [] and p["temas"] == [] and p["palavras"] == []


def test_amostra_pequena(client, cenario):
    # 06/03: só a Célia foi convidada (e não respondeu) → 0% → amostra pequena
    p = _painel(client, cenario["h"], de="2026-03-06", ate="2026-03-06")
    assert p["taxa_resposta"] == {"percentual": 0, "responderam": 0, "convidados": 1, "amostra_pequena": True}
    p = _painel(client, cenario["h"], de="2026-03-09", ate="2026-03-09")
    assert p["taxa_resposta"] == {"percentual": None, "responderam": 0, "convidados": 0, "amostra_pequena": False}


def test_nps_arredondado_no_painel(client, dono):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])
    c = criar_contato(client, h)
    for nota in (10, 9, 9, 8, 7, 7, 3, 0):  # (3 − 2) / 8 = 12,5 → 13
        d.resposta(c, nota, "2026-04-10")
    for nota in (10, 10, 8, 8, 8, 6, 6, 6):  # (2 − 3) / 8 = −12,5 → −13
        d.resposta(c, nota, "2026-05-10")
    for nota in (5, 1, 1, 1, 1, 1, 1, 1):  # CSAT 1 de 8 = 12,5% → 13
        d.resposta(c, nota, "2026-04-10", tipo="csat")
    abril = _painel(client, h, de="2026-04-01", ate="2026-04-30")
    assert abril["nps"]["valor"] == 13 and abril["nps"]["faixa"] == "pode_melhorar"
    assert abril["nps"]["pct"] == {"promotores": 37.5, "neutros": 37.5, "detratores": 25.0}
    assert abril["csat"]["percentual"] == 13 and abril["csat"]["media"] == 1.5
    maio = _painel(client, h, de="2026-05-01", ate="2026-05-31")
    assert maio["nps"]["valor"] == -13 and maio["variacao"] == {"valor": -26, "anterior": 13}
    assert [x["nps"] for x in _painel(client, h)["evolucao"]] == [13, -13]


def test_evolucao_6_meses_sem_periodo_e_24_com_periodo(client, dono):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])
    c = criar_contato(client, h)
    meses = [date(2023, 1, 15) + timedelta(days=31 * i) for i in range(30)]  # 30 meses seguidos
    for m in meses:
        d.resposta(c, 10, m.isoformat())
    sem = _painel(client, h)["evolucao"]
    assert [x["mes"] for x in sem] == [m.strftime("%Y-%m") for m in meses[-6:]]
    com = _painel(client, h, de="2023-01-01", ate="2025-12-31")["evolucao"]
    assert len(com) == 24 and com[-1]["mes"] == meses[-1].strftime("%Y-%m") and com[0]["mes"] < com[-1]["mes"]
    curto = _painel(client, h, de="2023-01-01", ate="2023-03-31")["evolucao"]
    assert [x["mes"] for x in curto] == ["2023-01", "2023-02", "2023-03"]


def test_empresas_menor_e_maior_sem_repetir(client, dono):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])
    notas = {}
    for i in range(14):  # 14 empresas, NPS de −100 a 100 (passo de ~15)
        e = criar_empresa(client, h, f"Empresa {i:02d}")
        c = criar_contato(client, h, empresa_id=e["id"])
        promotores = min(i, 13) * 3 // 13
        lote = [10] * promotores + [0] * (3 - promotores)
        for nota in lote:
            d.resposta(c, nota, "2026-04-10")
        notas[e["nome"]] = lote
    p = _painel(client, h)
    menor, maior = p["empresas"]["menor"], p["empresas"]["maior"]
    assert len(menor) == 6 and len(maior) == 6
    assert not {x["empresa"]["id"] for x in menor} & {x["empresa"]["id"] for x in maior}
    assert [x["nps"] for x in menor] == sorted(x["nps"] for x in menor)
    assert [x["nps"] for x in maior] == sorted((x["nps"] for x in maior), reverse=True)
    assert max(x["nps"] for x in menor) <= min(x["nps"] for x in maior)


def test_primeiros_passos_conta_nova(client, dono):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    p = _painel(client, h)
    assert p["primeiros_passos"] == {"contatos": False, "envios_ligados": False, "primeiro_envio": False,
                                     "primeira_resposta": False}
    assert p["atencao"] == {"acoes_abertas": 0, "acoes_vencidas": 0, "tudo_em_dia": True, "empresas": [],
                            "receita_em_risco": {"valor": 0, "empresas": 0, "sem_valor": 0}}
    assert p["nps"]["decisores"] == {"valor": None, "total": 0}
    assert p["movimentacao"] == {"resgatados": 0, "deixaram_de_ser_promotores": 0, "itens": []}
    criar_contato(client, h)
    ligar_envios(client, h)
    p = _painel(client, h)["primeiros_passos"]
    assert p == {"contatos": True, "envios_ligados": True, "primeiro_envio": False, "primeira_resposta": False}


def test_permissoes_validacao_e_exportacao(client, cenario):
    h = cenario["h"]
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    assert client.get(f"{API}/painel", headers=consulta["h"]).status_code == 200
    assert client.get(f"{API}/painel/exportar.csv", headers=consulta["h"]).status_code == 403
    r = client.get(f"{API}/painel", headers=h, params={"de": "2026-03-31", "ate": "2026-03-01"})
    assert r.status_code == 422 and "de" in r.json()["erro"]["campos"]
    assert client.get(f"{API}/painel", headers=h, params={"de": "01/03/2026"}).status_code == 422
    assert client.get(f"{API}/painel", headers=h, params={"so_ativos": "talvez"}).status_code == 422
    assert client.get(f"{API}/painel", headers=h, params={"de": "", "ate": "", "grupo_id": ""}).status_code == 200
    r = client.get(f"{API}/painel/exportar.csv", headers=h, params=MARCO)
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")
    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert linhas[0][0] == "Data" and linhas[0][-1] == "Arquivada"
    assert len(linhas) == 1 + 9 + 4  # NPS e CSAT de março, só ativos, sem a arquivada
    assert all(x[-1] == "Não" for x in linhas[1:]) and "Padaria Leste" not in r.content.decode("utf-8-sig")
    todas = client.get(f"{API}/painel/exportar.csv", headers=h, params={**MARCO, "so_ativos": "false"})
    assert todas.content.decode("utf-8-sig").count("Padaria Leste") == 4


# ---- rodada de revisão --------------------------------------------------------

def _responder(client, h, form: dict, contato: dict, *valores) -> None:
    """Responde pelo link do contato; `valores` na ordem das perguntas do formulário (None = sem resposta)."""
    token = link_pesquisa(client, h, contato["id"], formulario_id=form["id"])
    respostas = {p["id"]: v for p, v in zip(form["perguntas"], valores) if v is not None}
    r = client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": respostas})
    assert r.status_code == 201, r.text


def test_comentarios_so_com_o_texto_do_cliente(client, dono):
    """Modelos prontos: comentários, último comentário de detrator e palavras usam só o que o cliente escreveu
    (mesmo com " | " no texto), sem nome, e-mail, opções marcadas ou a nota de outras perguntas; os temas usam
    também as opções marcadas. Editado na análise, vale o texto como ficou."""
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    norte, sul = criar_empresa(client, h, "Atacado Norte"), criar_empresa(client, h, "Mercado Sul")
    carla = criar_contato(client, h, nome="Carla Um", empresa_id=norte["id"])
    caio = criar_contato(client, h, nome="Caio Dois", empresa_id=sul["id"])
    ciro = criar_contato(client, h, nome="Ciro Seis")
    rapida = criar_form(client, h, None, nome="Rápida", modelo="pesquisa_rapida")
    distribuidora = criar_form(client, h, None, nome="Distribuidora", modelo="nps_distribuidora")
    atendimento = criar_form(client, h, None, nome="Atendimento", modelo="pos_atendimento")
    entrega = form_padrao(client, h, "csat")  # modelo pos_entrega
    _responder(client, h, rapida, carla, 3, "Entrega atrasou | frete caro demais", "Joana Prado",
               "joana@cliente.com.br")
    _responder(client, h, distribuidora, caio, 5, ["Disponibilidade de produtos", "Trocas e pós-venda"],
               "Faltou mix | e variedade")
    _responder(client, h, entrega, ciro, 1, ["Atrasou"], "Motorista sem educação")
    _responder(client, h, atendimento, ciro, 5, 6)  # o comentário só aparece com nota até 3
    _responder(client, h, distribuidora, carla, 10, ["Atendimento do vendedor"], None, "Preço justo")
    _responder(client, h, form_padrao(client, h), caio, 9)  # sem comentário
    p = _painel(client, h)
    assert [x["comentario"] for x in p["comentarios"]] == [
        "Preço justo", "Motorista sem educação", "Faltou mix | e variedade", "Entrega atrasou | frete caro demais"]
    assert {x["empresa"]["nome"]: x["ultimo_comentario_detrator"] for x in p["atencao"]["empresas"]} == {
        "Atacado Norte": "Entrega atrasou | frete caro demais", "Mercado Sul": "Faltou mix | e variedade"}
    # temas (NPS): as opções contam ("Trocas e pós-venda", "Atendimento do vendedor"); "Seu e-mail" não
    assert [(t["chave"], t["mencoes"], t["nota_media"]) for t in p["temas"]] == [
        ("atendimento", 2, 7.5), ("preco_condicoes", 2, 6.5), ("prazo_entrega", 1, 3.0), ("produto_avarias", 1, 5.0)]
    assert [x["palavra"] for x in p["palavras"]] == [
        "atrasou", "caro", "demais", "educação", "entrega", "faltou", "frete", "justo", "mix", "motorista", "preço",
        "variedade"]

    # a lista de respostas continua com o resumo (etapa 2); o painel não
    joana = lista_respostas(client, h, formulario_id=rapida["id"])["itens"][0]
    assert "Seu nome: Joana Prado" in joana["comentario"]
    # salvar a análise com o comentário igual (a tela manda tudo) ou só a nota não troca o texto do cliente
    r = client.patch(f"{API}/respostas/{joana['id']}", headers=h,
                     json={"comentario": joana["comentario"], "o_que_faltou": "Pontualidade", "nota": 2})
    assert r.status_code == 200 and r.json()["temas"] == ["prazo_entrega", "preco_condicoes"]
    assert _painel(client, h)["comentarios"][-1]["comentario"] == "Entrega atrasou | frete caro demais"
    # editado na análise: vale o texto como ficou (painel, temas e palavras)
    r = client.patch(f"{API}/respostas/{joana['id']}", headers=h, json={"comentario": "Atrasou duas vezes | sem aviso"})
    assert r.status_code == 200 and r.json()["temas"] == ["prazo_entrega", "comunicacao"]
    # à mão: o comentário como foi digitado
    registrar_resposta(client, h, caio["id"], 4, comentario="Ruim | demorou")
    p = _painel(client, h)
    assert [x["comentario"] for x in p["comentarios"]][:1] + [x["comentario"] for x in p["comentarios"]][-1:] == [
        "Ruim | demorou", "Atrasou duas vezes | sem aviso"]
    assert {x["empresa"]["nome"]: x["ultimo_comentario_detrator"] for x in p["atencao"]["empresas"]} == {
        "Atacado Norte": "Atrasou duas vezes | sem aviso", "Mercado Sul": "Ruim | demorou"}
    assert {"aviso", "ruim", "demorou"} <= {x["palavra"] for x in p["palavras"]}
    assert not {"joana", "prado", "seu", "nome", "e-mail", "motivo"} & {x["palavra"] for x in p["palavras"]}


@pytest.mark.parametrize("filtros", [
    {}, MARCO, {**MARCO, "so_ativos": "false"}, {"so_ativos": "false"}, {**MARCO, "grupo_id": "g1"},
    {**MARCO, "grupo_id": "g2", "so_ativos": "false"}, {"de": "2026-02-01", "ate": "2026-03-10"},
])
def test_painel_e_lista_de_respostas_contam_igual(client, cenario, filtros):
    """Mesmo período, grupo e "só ativos": o NPS e o CSAT do painel batem com as métricas de /respostas."""
    h = cenario["h"]
    filtros = {"so_ativos": "true", **filtros}  # o padrão do painel (na lista, o padrão é todas)
    if "grupo_id" in filtros:
        filtros["grupo_id"] = cenario[filtros["grupo_id"]]["id"]
    p = _painel(client, h, **filtros)
    nps = lista_respostas(client, h, tipo_nota="nps", **filtros)["metricas"]["nps"]
    assert nps == {k: p["nps"][k] for k in ("valor", "faixa", "promotores", "neutros", "detratores", "total")}
    csat = lista_respostas(client, h, tipo_nota="csat", **filtros)["metricas"]["csat"]
    assert csat == ({k: p["csat"][k] for k in ("percentual", "media", "total")} if p["csat"]["total"] else None)


def test_dia_e_mes_de_sao_paulo_no_painel(client, dono):
    """23:30 de 30/04 em Brasília (02:30 de 01/05 em UTC) conta em abril; 00:30 de 01/05, em maio."""
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])
    c = criar_contato(client, h)
    abril, maio = d.resposta(c, 10, "2026-04-30"), d.resposta(c, 0, "2026-05-01")
    sql(dono, "update respostas set respondida_em = '2026-04-30 23:30-03' where id = :r", r=abril)
    sql(dono, "update respostas set respondida_em = '2026-05-01 00:30-03' where id = :r", r=maio)
    p = _painel(client, h, de="2026-04-30", ate="2026-04-30")
    assert (p["nps"]["total"], p["nps"]["valor"]) == (1, 100)
    p = _painel(client, h, de="2026-05-01", ate="2026-05-01")
    assert (p["nps"]["total"], p["nps"]["valor"]) == (1, -100)
    assert _painel(client, h)["evolucao"] == [{"mes": "2026-04", "nps": 100, "total": 1},
                                             {"mes": "2026-05", "nps": -100, "total": 1}]
    texto = client.get(f"{API}/painel/exportar.csv", headers=h,
                       params={"de": "2026-04-30", "ate": "2026-04-30"}).content.decode("utf-8-sig")
    assert texto.count("\r\n") == 2 and "30/04/2026 23:30" in texto


def test_decisores_sem_diferenciar_maiusculas(client, dono):
    a = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    h = a["h"]
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])
    decisor = perfil_id(client, h, "Decisor")
    r = client.patch(f"{API}/cadastros/perfis/{decisor}", headers=h, json={"nome": "DECISOR"})
    assert r.status_code == 200 and r.json()["nome"] == "DECISOR"
    quase = client.post(f"{API}/cadastros/perfis", headers=h, json={"nome": "Decisores regionais"}).json()
    chefe = criar_contato(client, h, perfil_id=decisor)
    for nota in (10, 0, 9):
        d.resposta(chefe, nota, "2026-04-10")
    d.resposta(criar_contato(client, h, perfil_id=perfil_id(client, h, "Influenciador")), 0, "2026-04-10")
    d.resposta(criar_contato(client, h, perfil_id=quase["id"]), 0, "2026-04-10")
    d.resposta(criar_contato(client, h), 0, "2026-04-10")
    p = _painel(client, h)
    assert p["nps"]["total"] == 6 and p["nps"]["decisores"] == {"valor": 33, "total": 3}  # (2 − 1) / 3


# ---- desempenho -------------------------------------------------------------

def test_desempenho_5000_contatos_50000_respostas(client, dono):
    a = conta_pronta(client, "perf@alfa.com.br", empresa="Alfa Grande")
    h = a["h"]
    conta = a["conta"]["id"]
    definir_plano(dono, conta, "empresa")  # sem limite de contatos ativos
    nps_id, csat_id = form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"]
    decisor = perfil_id(client, h, "Decisor")
    g = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede"}).json()
    sql(dono, """
        insert into empresas (conta_id, nome, grupo_id, ativa, valor_mensal)
        select :c, 'Empresa ' || n, case when n % 3 = 0 then :g end, n % 10 <> 0,
               case when n % 4 <> 0 then (n * 37 % 5000)::numeric end
          from generate_series(1, 500) n
    """, c=conta, g=g["id"])
    (e0,), = sql(dono, "select min(id) from empresas where conta_id = :c", c=conta)
    sql(dono, """
        insert into contatos (conta_id, codigo, nome, email, empresa_id, perfil_id, ativo)
        select :c, (200000000 + n)::text, 'Contato ' || n, 'p' || n || '@cliente.com.br',
               case when n % 50 <> 0 then :e0 + n % 500 end, case when n % 5 = 0 then :d end, n % 40 <> 0
          from generate_series(1, 5000) n
    """, c=conta, e0=e0, d=decisor)
    (c0,), = sql(dono, "select min(id) from contatos where conta_id = :c", c=conta)
    sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota, grupo,
                               comentario, comentario_cliente, temas, criada_em, arquivada)
        select :c, case when csat then :csat else :nps end, :c0 + k, case when k % 50 <> 0 then :e0 + k % 500 end,
               'link', 'pesquisa', nota, case when csat then 'csat' else 'nps' end,
               case when csat then (case when nota <= 2 then 'insatisfeito' when nota = 3 then 'neutro'
                                         else 'satisfeito' end)
                    else (case when nota <= 6 then 'detrator' when nota <= 8 then 'neutro' else 'promotor' end) end,
               case n % 4 when 0 then 'Entrega atrasou e o atendimento demorou'
                          when 1 then 'Preço bom, mas o produto chegou quebrado'
                          when 2 then 'Ótimo vendedor, recomendo' else '' end,
               case n % 4 when 0 then 'Entrega atrasou e o atendimento demorou'
                          when 1 then 'Preço bom, mas o produto chegou quebrado'
                          when 2 then 'Ótimo vendedor, recomendo' else '' end,
               case n % 4 when 0 then array['prazo_entrega','atendimento']
                          when 1 then array['produto_avarias','preco_condicoes']
                          when 2 then array['atendimento'] else '{}'::text[] end,
               now() - (n % 730) * interval '1 day' - (n % 1440) * interval '1 minute', n % 97 = 0
          from (select n, (n * 7919) % 5000 as k, n % 10 = 0 as csat,
                       case when n % 10 = 0 then 1 + n % 5 else (n * 13) % 11 end as nota
                  from generate_series(1, 50000) n) x
    """, c=conta, nps=nps_id, csat=csat_id, c0=c0, e0=e0)
    sql(dono, """
        with cv as (
            insert into convites (conta_id, token_hash, formulario_id, contato_id, empresa_id, canal, criado_em)
            select :c, md5('perf' || n), :nps, :c0 + n % 5000, :e0 + n % 500, 'email',
                   now() - (n % 365) * interval '1 day'
              from generate_series(1, 8000) n
            returning id, contato_id, criado_em)
        insert into envios (conta_id, contato_id, convite_id, canal, tipo, origem, situacao, para, criado_em)
        select :c, contato_id, id, 'email', 'convite', 'automatico',
               case when id % 9 = 0 then 'erro' else 'enviado' end, 'x', criado_em from cv
    """, c=conta, nps=nps_id, c0=c0, e0=e0)
    sql(dono, """
        insert into acoes (conta_id, empresa_id, titulo, prioridade, prazo, situacao, origem, criada_em)
        select :c, :e0 + n % 500, 'Ação ' || n, (array['alta','media','baixa'])[1 + n % 3],
               current_date + (n % 30 - 15), (array['a_fazer','em_andamento','concluida'])[1 + n % 3], 'manual',
               now() - (n % 200) * interval '1 day'
          from generate_series(1, 3000) n
    """, c=conta, e0=e0)
    sql(dono, "analyze")
    assert sql(dono, "select count(*) from respostas where conta_id = :c", c=conta)[0][0] == 50000

    _painel(client, h)  # aquece conexões e cache de planos
    tempos = {}
    hoje = relogio.hoje()
    for nome, filtros in (("90 dias", {"de": (hoje - timedelta(days=89)).isoformat(), "ate": hoje.isoformat()}),
                          ("tudo", {}),
                          ("12 meses + grupo", {"de": (hoje - timedelta(days=364)).isoformat(),
                                                "ate": hoje.isoformat(), "grupo_id": g["id"]})):
        inicio = relogio_real.perf_counter()
        p = _painel(client, h, **filtros)
        tempos[nome] = relogio_real.perf_counter() - inicio
        assert p["nps"]["total"] > 0 and len(p["palavras"]) == 12 and len(p["temas"]) == 4
    print("\nGET /painel com 5.000 contatos e 50.000 respostas: " +
          ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in tempos.items()))
    assert max(tempos.values()) < 1.5, tempos
    # a lista de respostas (com métricas) e o quadro também ficam rápidos com esse volume
    outros = {}
    for nome, url, params in (("respostas", "/respostas", {}), ("respostas por tema", "/respostas",
                                                                  {"tema": "atendimento", "pagina": 5}),
                              ("quadro", "/acoes/quadro", {})):
        inicio = relogio_real.perf_counter()
        r = client.get(f"{API}{url}", headers=h, params=params)
        outros[nome] = relogio_real.perf_counter() - inicio
        assert r.status_code == 200, r.text
    print("Outras telas: " + ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in outros.items()))
    assert max(outros.values()) < 1.5, outros
