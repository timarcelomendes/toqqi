"""Etapa 4b: relatórios — números de cada aba conferidos contra um conjunto pequeno calculado à mão (março/2026),
filtros, ordens, CSV, permissões e desempenho."""
import csv
import io
import json
import time as relogio_real
from datetime import date, datetime, time, timedelta

import pytest
from util import (
    API,
    FUSO,
    conta_pronta,
    criar_contato,
    criar_empresa,
    criar_responsavel,
    definir_plano,
    form_padrao,
    membro,
    perfil_id,
    sql,
)

from toqqi.core import relogio
from toqqi.modulos.formularios.validacao import grupo_da_nota

pytestmark = pytest.mark.usefixtures("relogio_estavel")
MARCO = {"de": "2026-03-01", "ate": "2026-03-31"}


def _dia(d: str, hora: int = 12, minuto: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(d), time(hora, minuto), tzinfo=FUSO)


class Dados:
    def __init__(self, dono, conta_id: int, nps_id: int, csat_id: int):
        self.dono, self.conta, self.nps, self.csat = dono, conta_id, nps_id, csat_id

    def resposta(self, contato: dict, nota: int, quando: str, temas: list[str] | None = None, tipo: str = "nps",
                 comentario: str = "", contexto: dict | None = None, ia: tuple | None = None) -> int:
        """`ia` = (sentimento geral, [(tema, sentimento)], resumo): resposta analisada pela IA."""
        empresa = (contato.get("empresa") or {}).get("id")
        (rid,), = sql(self.dono, """
            insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota,
                                   grupo, comentario, comentario_cliente, temas, respondida_em, contexto, ia_situacao,
                                   ia_sentimento, ia_temas, ia_resumo)
            values (:conta, :f, :c, :e, 'email', 'pesquisa', :n, :t, :g, :com, :com, :temas, :quando,
                    cast(:ctx as jsonb), :sit, :sent, cast(:ia_temas as jsonb), :resumo) returning id
        """, conta=self.conta, f=self.nps if tipo == "nps" else self.csat, c=contato["id"], e=empresa, n=nota, t=tipo,
            g=grupo_da_nota(tipo, nota), com=comentario, temas=temas or [], quando=_dia(quando),
            ctx=json.dumps(contexto or {}), sit="analisada" if ia else None, sent=ia[0] if ia else None,
            ia_temas=json.dumps([{"tema": t, "sentimento": s} for t, s in ia[1]]) if ia else None,
            resumo=ia[2] if ia else None)
        return rid

    def convite(self, contato: dict, quando: str, situacao: str, canal: str = "email") -> None:
        (cid,), = sql(self.dono, """
            insert into convites (conta_id, token_hash, formulario_id, contato_id, canal, criado_em)
            values (:conta, md5(random()::text), :f, :c, :canal, :quando) returning id
        """, conta=self.conta, f=self.nps, c=contato["id"], canal=canal, quando=_dia(quando))
        sql(self.dono, """
            insert into envios (conta_id, contato_id, convite_id, canal, tipo, origem, situacao, para, criado_em)
            values (:conta, :c, :cid, :canal, 'convite', 'manual', :s, 'x', :quando)
        """, conta=self.conta, c=contato["id"], cid=cid, canal=canal, s=situacao, quando=_dia(quando))

    def acao(self, empresa: dict | None, prazo: date | None = None, situacao: str = "a_fazer",
             criada: datetime | None = None, concluida: datetime | None = None, resposta_id: int | None = None) -> int:
        (aid,), = sql(self.dono, """
            insert into acoes (conta_id, empresa_id, resposta_id, titulo, prioridade, prazo, situacao, origem,
                               criada_em, concluida_em)
            values (:conta, :e, :r, 'Ação', 'media', :prazo, :s, 'manual', :criada, :concluida) returning id
        """, conta=self.conta, e=empresa["id"] if empresa else None, r=resposta_id, prazo=prazo, s=situacao,
            criada=criada or relogio.agora(), concluida=concluida)
        return aid


@pytest.fixture
def cenario(client, dono, relogio_estavel):
    hoje = relogio_estavel
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h = a["h"]
    g1 = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Leste"}).json()
    g2 = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede Oeste"}).json()
    s1 = client.post(f"{API}/cadastros/segmentos", headers=h, json={"nome": "Atacado"}).json()
    s2 = client.post(f"{API}/cadastros/segmentos", headers=h, json={"nome": "Varejo"}).json()
    rita = criar_responsavel(client, h, "Rita Gomes", foto_url="https://x.com/rita.png")
    beto = criar_responsavel(client, h, "Beto Lima")

    def empresa(nome, dias, **campos):
        desde = None if dias is None else (hoje - timedelta(days=dias)).isoformat()
        return criar_empresa(client, h, nome, cliente_desde=desde, **campos)

    e1 = empresa("Atacado Norte", 400, grupo_id=g1["id"], segmento_id=s1["id"], responsavel_id=rita["id"],
                 valor_mensal="1000.00")
    e2 = empresa("Mercado Sul", 100, grupo_id=g1["id"], segmento_id=s2["id"], responsavel_id=rita["id"],
                 valor_mensal="3000.00")
    e3 = empresa("Padaria Leste", 30, grupo_id=g2["id"], segmento_id=s2["id"], valor_mensal="500.00", ativa=False)
    e4 = empresa("Loja Oeste", -10, grupo_id=g2["id"], responsavel_id=beto["id"], valor_mensal="60000.00")
    e5 = empresa("Distribuidora Centro", None, segmento_id=s1["id"], responsavel_id=beto["id"])
    e6 = empresa("Empório Novo", 200, grupo_id=g1["id"], segmento_id=s1["id"], valor_mensal="15000.00")
    decisor = perfil_id(client, h, "Decisor")
    cargo = client.post(f"{API}/cadastros/cargos", headers=h, json={"nome": "Comprador"}).json()

    def contato(nome, empresa_, **campos):
        return criar_contato(client, h, nome=nome, empresa_id=empresa_["id"] if empresa_ else None, **campos)

    c1 = contato("Carla Um", e1, perfil_id=decisor, cargo_id=cargo["id"])
    c2 = contato("Caio Dois", e1)
    contato("Cadu Inativo", e1, ativo=False)
    c4 = contato("Cris Quatro", e2)
    c5 = contato("Cid Cinco", e3)
    c6 = contato("Cléo Seis", e4)
    c7 = contato("Célia Sete", e4)
    c8 = contato("Ciro Oito", e5)
    c9 = contato("Cora Nove", None)
    c10 = contato("Clara Dez", e6)
    d = Dados(dono, a["conta"]["id"], form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"])

    # março/2026 (NPS, salvo indicação)
    d.resposta(c9, 9, "2026-03-01", comentario="Tudo ótimo", ia=("positivo", [], "Elogia o serviço"))
    d.resposta(c1, 10, "2026-03-02", contexto={"motorista": "João Silva"})
    r_c1_3 = d.resposta(c1, 3, "2026-03-05", ["prazo_entrega"], comentario="Entrega atrasou",
                        contexto={"motorista": "João Silva"},
                        ia=("negativo", [("prazo_entrega", "negativo")], "Reclama do atraso na entrega"))
    d.resposta(c2, 8, "2026-03-08", ["preco_condicoes"], comentario="Preço subiu",
               contexto={"motorista": "  joão silva "})
    d.resposta(c4, 0, "2026-03-10", ["produto_avarias"], comentario="Produto quebrado", contexto={"motorista": "Ana"})
    d.resposta(c4, 6, "2026-03-11", ["prazo_entrega"], comentario="Atrasou de novo", contexto={"motorista": "ana"},
               ia=("misto", [("prazo_entrega", "negativo")], "Reclama de novo atraso"))
    for dia in ("2026-03-13", "2026-03-14"):  # empresa inativa
        d.resposta(c5, 10, dia, ["prazo_entrega"], comentario="Entrega rápida", contexto={"motorista": "Ana"})
    d.resposta(c6, 9, "2026-03-16", ["atendimento"], comentario="Vendedor atencioso", contexto={"rota": "Sul"},
               ia=("positivo", [("atendimento", "positivo")], "Elogia o vendedor"))
    d.resposta(c7, 7, "2026-03-17", ["atendimento"], comentario="Atendimento ok")
    d.resposta(c8, 2, "2026-03-18", ["sistema_pedidos"], comentario="Site fora do ar")
    d.resposta(c1, 5, "2026-03-24", ["prazo_entrega"], tipo="csat", comentario="Entrega no prazo",
               contexto={"motorista": "Ana"})
    d.resposta(c4, 1, "2026-03-25", ["prazo_entrega"], tipo="csat", comentario="Atraso", contexto={"motorista": "Ana"})
    # fora do período
    d.resposta(c1, 0, "2026-02-10", ["prazo_entrega"])
    d.resposta(c6, 10, "2026-04-10")

    # convites (operação): Clara foi convidada e não respondeu; o do Cris deu erro
    d.convite(c1, "2026-03-01", "enviado")
    d.convite(c2, "2026-03-02", "aberto_no_whatsapp", canal="whatsapp")
    d.convite(c4, "2026-03-03", "erro")
    d.convite(c6, "2026-03-04", "enviado")
    d.convite(c8, "2026-03-04", "entregue", canal="whatsapp")
    d.convite(c10, "2026-03-05", "enviado")
    # ações: abertas (agora) e concluídas em março
    d.acao(e1, prazo=hoje - timedelta(days=2), resposta_id=r_c1_3)
    d.acao(e1, prazo=hoje + timedelta(days=3))
    d.acao(e2)
    d.acao(e1, situacao="concluida", prazo=date(2026, 3, 5), criada=_dia("2026-03-01"),
           concluida=_dia("2026-03-04"))
    d.acao(e2, situacao="concluida", prazo=date(2026, 3, 11), criada=_dia("2026-03-10"),
           concluida=_dia("2026-03-12", 0, 0))  # concluída à meia-noite do dia seguinte ao prazo: atrasada
    d.acao(None, situacao="concluida", criada=_dia("2026-03-20"), concluida=_dia("2026-03-21"))
    d.acao(e4, situacao="concluida", criada=_dia("2026-04-01"), concluida=_dia("2026-04-02"))
    # sem resposta depois do último convite: Clara (100 dias, atrasada) e Célia (10 dias)
    for c, dias in ((c10, 100), (c7, 10), (c5, 5)):
        sql(dono, "update contatos set ultimo_envio = :q where id = :c",
            q=datetime.combine(hoje - timedelta(days=dias), time(10), tzinfo=FUSO), c=c["id"])
    sql(dono, "update contatos set ultimo_envio = :q where id = :c", q=_dia("2026-03-01", 9), c=c1["id"])
    return {"h": h, "a": a, "e": [None, e1, e2, e3, e4, e5, e6], "c": [None, c1, c2, None, c4, c5, c6, c7, c8, c9,
                                                                          c10],
            "g": [None, g1, g2], "s": [None, s1, s2], "rita": rita, "beto": beto, "hoje": hoje, "dados": d,
            "cargo": cargo, "r_c1_3": r_c1_3}


def _get(client, h, url, **params):
    r = client.get(f"{API}{url}", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _csv(client, h, url, **params) -> list[list[str]]:
    r = client.get(f"{API}{url}", headers=h, params=params)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf") and r.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))


def _nps(valor, faixa, p, n, d) -> dict:
    return {"valor": valor, "faixa": faixa, "promotores": p, "neutros": n, "detratores": d, "total": p + n + d}


# ---- empresas -------------------------------------------------------------------------

def test_empresas_resumo_matriz_e_itens(client, cenario):
    h, e = cenario["h"], cenario["e"]
    r = _get(client, h, "/relatorios/empresas", **MARCO)
    # só ativas: Atacado Norte, Mercado Sul, Loja Oeste, Distribuidora Centro, Empório Novo (a Padaria é inativa)
    assert r["resumo"] == {
        "empresas": 5, "com_respostas": 4,
        "cobertura": {"contatos_ativos": 7, "responderam": 6, "percentual": 86},  # Clara (Empório) não respondeu
        "receita": {"total": 79000.0, "em_risco": 4000.0, "empresas_em_risco": 3, "sem_valor": 1, "percentual": 5},
        "por_faixa": {"excelente": 0, "muito_bom": 1, "pode_melhorar": 1, "critico": 2, "sem_respostas": 1},
    }
    # matriz: Atacado (1.000, NPS 0), Mercado (3.000, −100), Loja (60.000, 50) → mediana 3.000 (ímpar)
    m = r["matriz"]
    assert m["mediana_valor"] == 3000.0 and m["sem_valor"] == 1  # Distribuidora tem NPS e não tem valor
    assert m["quadrantes"] == {"proteger": 1, "manter": 1, "corrigir": 0, "crescer": 1}
    assert m["pontos"] == [
        {"empresa": {"id": e[4]["id"], "nome": "Loja Oeste"}, "nps": 50, "valor_mensal": 60000.0, "respostas": 2,
         "quadrante": "manter"},
        {"empresa": {"id": e[2]["id"], "nome": "Mercado Sul"}, "nps": -100, "valor_mensal": 3000.0, "respostas": 2,
         "quadrante": "proteger"},
        {"empresa": {"id": e[1]["id"], "nome": "Atacado Norte"}, "nps": 0, "valor_mensal": 1000.0, "respostas": 3,
         "quadrante": "crescer"},
    ]
    # ordem padrão (prioridade): em risco primeiro (maior valor primeiro, sem valor no fim), depois as outras
    assert [x["empresa"]["nome"] for x in r["itens"]] == [
        "Mercado Sul", "Atacado Norte", "Distribuidora Centro", "Loja Oeste", "Empório Novo"]
    assert (r["total"], r["pagina"], r["por_pagina"]) == (5, 1, 50)
    atacado = r["itens"][1]
    assert atacado == {
        "empresa": {"id": e[1]["id"], "nome": "Atacado Norte", "ativa": True},
        "grupo": {"id": cenario["g"][1]["id"], "nome": "Rede Leste"},
        "segmento": {"id": cenario["s"][1]["id"], "nome": "Atacado"},
        "responsavel": {"id": cenario["rita"]["id"], "nome": "Rita Gomes"}, "valor_mensal": 1000.0,
        "cliente_desde": (cenario["hoje"] - timedelta(days=400)).isoformat(),
        "nps": _nps(0, "pode_melhorar", 1, 1, 1),
        "cobertura": {"contatos_ativos": 2, "responderam": 2, "percentual": 100},
        "ultima_resposta": {"data": atacado["ultima_resposta"]["data"], "nota": 5, "tipo_nota": "csat"},
        "em_risco": True, "quadrante": "crescer", "acoes_abertas": 2,
    }
    assert datetime.fromisoformat(atacado["ultima_resposta"]["data"]) == _dia("2026-03-24")
    loja = r["itens"][3]
    # última resposta de qualquer data (abril), mesmo fora do período
    assert datetime.fromisoformat(loja["ultima_resposta"]["data"]) == _dia("2026-04-10")
    emporio = r["itens"][4]
    assert emporio["nps"] == _nps(None, None, 0, 0, 0) and emporio["quadrante"] is None
    assert emporio["cobertura"] == {"contatos_ativos": 1, "responderam": 0, "percentual": 0}
    assert r["itens"][2]["responsavel"] == {"id": cenario["beto"]["id"], "nome": "Beto Lima"}


def test_empresas_mediana_par_e_so_ativos_desligado(client, cenario):
    r = _get(client, cenario["h"], "/relatorios/empresas", so_ativos="false", **MARCO)
    # + Padaria (500, NPS 100): 500, 1.000, 3.000, 60.000 → mediana (1.000 + 3.000) ÷ 2 = 2.000
    m = r["matriz"]
    assert m["mediana_valor"] == 2000.0
    assert {x["empresa"]["nome"]: x["quadrante"] for x in m["pontos"]} == {
        "Loja Oeste": "manter", "Mercado Sul": "proteger", "Atacado Norte": "crescer", "Padaria Leste": "crescer"}
    assert r["resumo"]["empresas"] == 6 and r["resumo"]["receita"]["total"] == 79500.0


@pytest.mark.parametrize("ordem,nomes", [
    ("nps", ["Distribuidora Centro", "Mercado Sul", "Atacado Norte", "Loja Oeste", "Empório Novo"]),
    ("valor", ["Loja Oeste", "Empório Novo", "Mercado Sul", "Atacado Norte", "Distribuidora Centro"]),
    ("cobertura", ["Empório Novo", "Atacado Norte", "Distribuidora Centro", "Loja Oeste", "Mercado Sul"]),
    ("respostas", ["Atacado Norte", "Loja Oeste", "Mercado Sul", "Distribuidora Centro", "Empório Novo"]),
    ("nome", ["Atacado Norte", "Distribuidora Centro", "Empório Novo", "Loja Oeste", "Mercado Sul"]),
])
def test_empresas_ordens(client, cenario, ordem, nomes):
    r = _get(client, cenario["h"], "/relatorios/empresas", ordem=ordem, **MARCO)
    assert [x["empresa"]["nome"] for x in r["itens"]] == nomes


def test_empresas_filtros(client, cenario):
    h, s, g = cenario["h"], cenario["s"], cenario["g"]

    def nomes(**f):
        return sorted(x["empresa"]["nome"] for x in _get(client, h, "/relatorios/empresas", **MARCO, **f)["itens"])

    assert nomes(segmento_id=s[1]["id"]) == ["Atacado Norte", "Distribuidora Centro", "Empório Novo"]
    assert nomes(segmento_id=0) == ["Loja Oeste"]
    assert nomes(responsavel_id=cenario["rita"]["id"]) == ["Atacado Norte", "Mercado Sul"]
    assert nomes(responsavel_id=0) == ["Empório Novo"]
    assert nomes(grupo_id=g[2]["id"]) == ["Loja Oeste"]
    assert nomes(faixa_valor="sem_valor") == ["Distribuidora Centro"]
    assert nomes(faixa_valor="acima_50k") == ["Loja Oeste"] and nomes(faixa_valor="10k_50k") == ["Empório Novo"]
    assert nomes(faixa_valor="ate_2k") == ["Atacado Norte"] and nomes(faixa_valor="2k_10k") == ["Mercado Sul"]
    assert nomes(tempo_cliente="ate_3m") == ["Loja Oeste"]  # data futura conta como até 3 meses
    assert nomes(tempo_cliente="3_6m") == ["Mercado Sul"] and nomes(tempo_cliente="6_12m") == ["Empório Novo"]
    assert nomes(tempo_cliente="mais_1a") == ["Atacado Norte"] and nomes(tempo_cliente="sem_data") == [
        "Distribuidora Centro"]
    assert nomes(busca="MERC") == ["Mercado Sul"] and nomes(busca="emporio") == ["Empório Novo"]
    assert nomes(respostas="sem") == ["Empório Novo"]
    assert nomes(quadrante="proteger") == ["Mercado Sul"]
    # filtros só da tabela não mudam o resumo nem a matriz
    r = _get(client, h, "/relatorios/empresas", busca="merc", **MARCO)
    assert r["resumo"]["empresas"] == 5 and r["total"] == 1 and len(r["matriz"]["pontos"]) == 3
    # filtros de empresa mudam
    r = _get(client, h, "/relatorios/empresas", responsavel_id=cenario["rita"]["id"], **MARCO)
    assert r["resumo"]["empresas"] == 2 and r["matriz"]["mediana_valor"] == 2000.0
    # paginação
    r = _get(client, h, "/relatorios/empresas", por_pagina=2, pagina=2, **MARCO)
    assert [x["empresa"]["nome"] for x in r["itens"]] == ["Distribuidora Centro", "Loja Oeste"] and r["total"] == 5


@pytest.mark.parametrize("params,campo", [
    ({"de": "2026-03-31", "ate": "2026-03-01"}, "de"), ({"ate": "9999-12-31"}, "ate"),
    ({"faixa_valor": "muito"}, "faixa_valor"), ({"tempo_cliente": "5a"}, "tempo_cliente"),
    ({"quadrante": "x"}, "quadrante"), ({"ordem": "data"}, "ordem"), ({"respostas": "talvez"}, "respostas"),
    ({"por_pagina": 201}, "por_pagina"),
])
def test_empresas_validacao(client, cenario, params, campo):
    r = client.get(f"{API}/relatorios/empresas", headers=cenario["h"], params=params)
    assert r.status_code == 422 and campo in r.json()["erro"]["campos"], r.text


def test_empresas_csv(client, cenario):
    linhas = _csv(client, cenario["h"], "/relatorios/empresas.csv", **MARCO)
    assert linhas[0] == ["Empresa", "Ativa", "Grupo", "Segmento", "Responsável", "Valor mensal", "Cliente desde",
                         "NPS", "Faixa", "Respostas", "Promotores", "Neutros", "Detratores", "Contatos ativos",
                         "Responderam", "Cobertura (%)", "Última resposta", "Em risco", "Quadrante", "Ações abertas"]
    assert len(linhas) == 6 and linhas[1][0] == "Mercado Sul"
    desde = (cenario["hoje"] - timedelta(days=400)).strftime("%d/%m/%Y")
    assert linhas[2] == ["Atacado Norte", "Sim", "Rede Leste", "Atacado", "Rita Gomes", "1000,00", desde, "0",
                         "Pode melhorar", "3", "1", "1", "1", "2", "2", "100", "24/03/2026", "Sim", "Pode crescer", "2"]
    assert linhas[2 + 1][7] == "-100"  # NPS negativo sai como número (sem a proteção contra fórmula)
    assert linhas[5][7:10] == ["", "", "0"]


# ---- grupos de clientes ------------------------------------------------------------------

def test_grupos(client, cenario):
    s, g = cenario["s"], cenario["g"]
    r = _get(client, cenario["h"], "/relatorios/grupos", **MARCO)
    # Atacado: Atacado Norte (P1 N1 D1) + Distribuidora (D1) → −25; Varejo: Mercado (D2) → −100; sem: Loja → 50
    assert r["segmentos"] == [
        {"segmento": {"id": s[2]["id"], "nome": "Varejo"}, "empresas": 1, "nps": _nps(-100, "critico", 0, 0, 2)},
        {"segmento": {"id": s[1]["id"], "nome": "Atacado"}, "empresas": 2, "nps": _nps(-25, "critico", 1, 1, 2)},
        {"segmento": None, "empresas": 1, "nps": _nps(50, "muito_bom", 1, 1, 0)},
    ]
    assert r["grupos"] == [
        {"grupo": {"id": g[1]["id"], "nome": "Rede Leste"}, "empresas": 2, "nps": _nps(-40, "critico", 1, 1, 3)},
        {"grupo": {"id": g[2]["id"], "nome": "Rede Oeste"}, "empresas": 1, "nps": _nps(50, "muito_bom", 1, 1, 0)},
        {"grupo": None, "empresas": 1, "nps": _nps(-100, "critico", 0, 0, 1)},
    ]
    vazio = _nps(None, None, 0, 0, 0)
    assert r["tempo_cliente"] == [
        {"faixa": "ate_3m", "rotulo": "Até 3 meses", "empresas": 1, "nps": _nps(50, "muito_bom", 1, 1, 0)},
        {"faixa": "3_6m", "rotulo": "3 a 6 meses", "empresas": 1, "nps": _nps(-100, "critico", 0, 0, 2)},
        {"faixa": "6_12m", "rotulo": "6 a 12 meses", "empresas": 0, "nps": vazio},
        {"faixa": "mais_1a", "rotulo": "Mais de 1 ano", "empresas": 1, "nps": _nps(0, "pode_melhorar", 1, 1, 1)},
        {"faixa": "sem_data", "rotulo": "Sem data de início", "empresas": 1, "nps": _nps(-100, "critico", 0, 0, 1)},
    ]
    assert r["valor"] == [
        {"faixa": "ate_2k", "rotulo": "Menos de R$ 2 mil", "empresas": 1, "nps": _nps(0, "pode_melhorar", 1, 1, 1)},
        {"faixa": "2k_10k", "rotulo": "R$ 2 mil a 10 mil", "empresas": 1, "nps": _nps(-100, "critico", 0, 0, 2)},
        {"faixa": "10k_50k", "rotulo": "R$ 10 mil a 50 mil", "empresas": 0, "nps": vazio},
        {"faixa": "acima_50k", "rotulo": "R$ 50 mil ou mais", "empresas": 1, "nps": _nps(50, "muito_bom", 1, 1, 0)},
        {"faixa": "sem_valor", "rotulo": "Sem valor", "empresas": 1, "nps": _nps(-100, "critico", 0, 0, 1)},
    ]
    # temas com 2+ respostas: prazo (3 e 6 → 4,5; 2 × 5,5 = 11) antes de atendimento (9 e 7 → 8; 2 × 2 = 4)
    assert r["prioridades"] == [
        {"tema": "prazo_entrega", "rotulo": "Prazo e entrega", "mencoes": 2, "nota_media": 4.5, "reclamacoes": 2},
        {"tema": "atendimento", "rotulo": "Atendimento", "mencoes": 2, "nota_media": 8.0, "reclamacoes": 0},
    ]
    # filtros de empresa
    r = _get(client, cenario["h"], "/relatorios/grupos", segmento_id=s[1]["id"], **MARCO)
    assert [x["segmento"]["nome"] for x in r["segmentos"]] == ["Atacado"]
    r = _get(client, cenario["h"], "/relatorios/grupos", faixa_valor="acima_50k", **MARCO)
    assert [x["grupo"]["nome"] for x in r["grupos"]] == ["Rede Oeste"]
    assert [x["tema"] for x in r["prioridades"]] == ["atendimento"]  # só a Loja Oeste (9 e 7)
    r = _get(client, cenario["h"], "/relatorios/grupos", tempo_cliente="6_12m", **MARCO)
    assert r["segmentos"] == r["grupos"] == r["prioridades"] == []  # só o Empório Novo, que não tem respostas
    assert [x["empresas"] for x in r["valor"]] == [0, 0, 0, 0, 0]
    r = _get(client, cenario["h"], "/relatorios/grupos", segmento_id=0, **MARCO)
    assert [x["grupo"]["nome"] for x in r["grupos"]] == ["Rede Oeste"] and r["segmentos"][0]["segmento"] is None


# ---- temas ----------------------------------------------------------------------------

def test_temas(client, cenario):
    r = _get(client, cenario["h"], "/relatorios/temas", **MARCO)
    assert r["ia"] == {"ativa": True, "analisadas": 4, "com_comentario": 10}
    assert r["sentimento"] == {"positivo": 2, "neutro": 0, "negativo": 1, "misto": 1, "sem_analise": 6}
    vazio = {"positivo": 0, "neutro": 0, "negativo": 0, "sem_analise": 0}
    assert r["temas"] == [
        # prazo: Carla 3 (IA negativo), Cris 6 (IA negativo), CSAT 5 (satisfeito: elogio), CSAT 1 (insatisfeito)
        {"tema": "prazo_entrega", "rotulo": "Prazo e entrega", "mencoes": 4, "reclamacoes": 3, "elogios": 1,
         "nota_media": 4.5, "variacao": 3, "sentimento": {**vazio, "negativo": 2, "sem_analise": 2}},
        {"tema": "produto_avarias", "rotulo": "Produto e avarias", "mencoes": 1, "reclamacoes": 1, "elogios": 0,
         "nota_media": 0.0, "variacao": 1, "sentimento": {**vazio, "sem_analise": 1}},
        {"tema": "atendimento", "rotulo": "Atendimento", "mencoes": 2, "reclamacoes": 0, "elogios": 1,
         "nota_media": 8.0, "variacao": 2, "sentimento": {**vazio, "positivo": 1, "sem_analise": 1}},
        {"tema": "preco_condicoes", "rotulo": "Preço e condições", "mencoes": 1, "reclamacoes": 0, "elogios": 0,
         "nota_media": 8.0, "variacao": 1, "sentimento": {**vazio, "sem_analise": 1}},
        {"tema": "comunicacao", "rotulo": "Comunicação", "mencoes": 0, "reclamacoes": 0, "elogios": 0,
         "nota_media": None, "variacao": 0, "sentimento": vazio},
        {"tema": "sistema_pedidos", "rotulo": "Sistema e pedidos", "mencoes": 1, "reclamacoes": 1, "elogios": 0,
         "nota_media": 2.0, "variacao": 1, "sentimento": {**vazio, "sem_analise": 1}},
    ]
    zero = {"mencoes": 0, "reclamacoes": 0}

    def semana(inicio, respostas, **temas):
        ini = date.fromisoformat(inicio)
        todos = {t: zero for t in ("prazo_entrega", "produto_avarias", "atendimento", "preco_condicoes",
                                   "comunicacao", "sistema_pedidos")}
        todos.update({t: {"mencoes": m, "reclamacoes": rec} for t, (m, rec) in temas.items()})
        return {"inicio": inicio, "fim": (ini + timedelta(days=6)).isoformat(), "respostas": respostas, "temas": todos}

    assert r["semanas"] == [
        semana("2026-02-23", 1),  # só domingo, 1º de março, dentro do período
        semana("2026-03-02", 3, prazo_entrega=(1, 1), preco_condicoes=(1, 0)),
        semana("2026-03-09", 2, prazo_entrega=(1, 1), produto_avarias=(1, 1)),
        semana("2026-03-16", 3, atendimento=(2, 0), sistema_pedidos=(1, 1)),
        semana("2026-03-23", 2, prazo_entrega=(2, 1)),
        semana("2026-03-30", 0),
    ]
    assert r["picos"] == []
    # sem período: 12 semanas até a atual, sem variação
    r = _get(client, cenario["h"], "/relatorios/temas")
    hoje = cenario["hoje"]
    atual = hoje - timedelta(days=hoje.weekday())
    assert len(r["semanas"]) == 12 and r["semanas"][-1]["inicio"] == atual.isoformat()
    assert all(x["variacao"] is None for x in r["temas"])
    # período longo: as 26 semanas mais recentes
    r = _get(client, cenario["h"], "/relatorios/temas", de="2025-01-01", ate="2026-03-31")
    assert len(r["semanas"]) == 26 and r["semanas"][-1]["inicio"] == "2026-03-30"


def test_temas_so_com_de_ou_so_com_ate(client, cenario):
    h, hoje = cenario["h"], cenario["hoje"]
    atual = hoje - timedelta(days=hoje.weekday())
    # só `de`, numa semana futura: a semana de `de` (antes dava erro 500)
    futura = atual + timedelta(weeks=2, days=3)
    r = _get(client, h, "/relatorios/temas", de=futura.isoformat())
    assert [x["inicio"] for x in r["semanas"]] == [(atual + timedelta(weeks=2)).isoformat()]
    assert len(_get(client, h, "/relatorios/temas", de="2100-12-31")["semanas"]) == 1
    # só `de`, no passado: daquela semana até a atual
    r = _get(client, h, "/relatorios/temas", de=(atual - timedelta(weeks=3)).isoformat())
    assert len(r["semanas"]) == 4 and r["semanas"][-1]["inicio"] == atual.isoformat()
    # só `ate`: as 26 semanas que terminam na semana de `ate` (12 só sem `de` e sem `ate`)
    r = _get(client, h, "/relatorios/temas", ate="2026-03-31")
    assert len(r["semanas"]) == 26 and r["semanas"][-1]["inicio"] == "2026-03-30"
    assert r["semanas"][0]["inicio"] == "2025-10-06"


# ---- entregas -----------------------------------------------------------------------------

def test_entregas(client, cenario):
    h = cenario["h"]
    r = _get(client, h, "/relatorios/entregas", **MARCO)
    assert r["dimensao"] == "motorista" and r["sem_valor"] == 4 and r["total"] == 2
    ana, joao = r["itens"]
    assert ana == {"valor": "Ana", "respostas": 4, "nps": _nps(-100, "critico", 0, 0, 2),
                   "csat": {"percentual": 50, "media": 3.0, "total": 2}, "reclamacoes": 3,
                   "temas": [{"tema": "prazo_entrega", "rotulo": "Prazo e entrega", "mencoes": 3},
                             {"tema": "produto_avarias", "rotulo": "Produto e avarias", "mencoes": 1}],
                   "ultima_resposta": ana["ultima_resposta"], "amostra_pequena": True}
    assert datetime.fromisoformat(ana["ultima_resposta"]) == _dia("2026-03-25")
    # "João Silva", "  joão silva " e "João Silva": um grupo só, com a forma mais frequente
    assert (joao["valor"], joao["respostas"], joao["nps"]["valor"], joao["reclamacoes"]) == ("João Silva", 3, 0, 1)
    assert joao["csat"] == {"percentual": None, "media": None, "total": 0}
    assert [t["tema"] for t in joao["temas"]] == ["prazo_entrega", "preco_condicoes"]
    assert [x["valor"] for x in _get(client, h, "/relatorios/entregas", ordem="valor", **MARCO)["itens"]] == [
        "Ana", "João Silva"]
    assert [x["valor"] for x in _get(client, h, "/relatorios/entregas", ordem="nps", **MARCO)["itens"]] == [
        "Ana", "João Silva"]
    assert [x["valor"] for x in _get(client, h, "/relatorios/entregas", ordem="csat", **MARCO)["itens"]] == [
        "Ana", "João Silva"]
    assert [x["valor"] for x in _get(client, h, "/relatorios/entregas", busca="JOÃO", **MARCO)["itens"]] == [
        "João Silva"]
    rota = _get(client, h, "/relatorios/entregas", dimensao="rota", **MARCO)
    assert [(x["valor"], x["respostas"]) for x in rota["itens"]] == [("Sul", 1)] and rota["sem_valor"] == 10
    assert _get(client, h, "/relatorios/entregas", dimensao="filial", **MARCO)["itens"] == []
    assert client.get(f"{API}/relatorios/entregas", headers=h, params={"dimensao": "placa"}).status_code == 422
    linhas = _csv(client, h, "/relatorios/entregas.csv", **MARCO)
    assert linhas == [
        ["Motorista", "Respostas", "NPS", "Promotores", "Neutros", "Detratores", "CSAT (%)", "CSAT média",
         "Reclamações", "Última resposta"],
        ["Ana", "4", "-100", "0", "0", "2", "50", "3,00", "3", "25/03/2026"],
        ["João Silva", "3", "0", "1", "1", "1", "", "", "1", "08/03/2026"],
    ]
    assert _csv(client, h, "/relatorios/entregas.csv", dimensao="rota", **MARCO)[0][0] == "Rota"


# ---- responsáveis ----------------------------------------------------------------------------

def test_responsaveis(client, cenario):
    h, e = cenario["h"], cenario["e"]
    rita, beto = cenario["rita"], cenario["beto"]
    r = _get(client, h, "/relatorios/responsaveis", **MARCO)
    assert r["itens"] == [
        {"responsavel": {"id": rita["id"], "nome": "Rita Gomes", "foto_url": "https://x.com/rita.png"},
         "empresas": 2, "empresas_com_respostas": 2, "nps": _nps(-40, "critico", 1, 1, 3), "receita": 4000.0,
         "receita_em_risco": 4000.0, "acoes_abertas": 3, "acoes_vencidas": 1},
        {"responsavel": {"id": beto["id"], "nome": "Beto Lima", "foto_url": None}, "empresas": 2,
         "empresas_com_respostas": 2, "nps": _nps(0, "pode_melhorar", 1, 1, 1), "receita": 60000.0,
         "receita_em_risco": 0, "acoes_abertas": 0, "acoes_vencidas": 0},
        {"responsavel": None, "empresas": 1, "empresas_com_respostas": 0, "nps": _nps(None, None, 0, 0, 0),
         "receita": 15000.0, "receita_em_risco": 0, "acoes_abertas": 0, "acoes_vencidas": 0},
    ]
    empresas = _get(client, h, f"/relatorios/responsaveis/{rita['id']}/empresas", **MARCO)
    assert [(x["empresa"]["nome"], x["nps"]["valor"], x["nota_media"], x["valor_mensal"], x["acoes_abertas"])
            for x in empresas] == [("Mercado Sul", -100, 3.0, 3000.0, 1), ("Atacado Norte", 0, 7.0, 1000.0, 2)]
    assert empresas[1]["ultima_resposta"]["nota"] == 5
    sem = _get(client, h, "/relatorios/responsaveis/0/empresas", **MARCO)
    assert sem == [{"empresa": {"id": e[6]["id"], "nome": "Empório Novo"}, "nps": _nps(None, None, 0, 0, 0),
                    "nota_media": None, "valor_mensal": 15000.0, "ultima_resposta": None, "acoes_abertas": 0}]
    assert client.get(f"{API}/relatorios/responsaveis/999999/empresas", headers=h).status_code == 404
    linhas = _csv(client, h, "/relatorios/responsaveis.csv", **MARCO)
    assert linhas[0] == ["Responsável", "Empresas", "Com respostas", "NPS", "Promotores", "Neutros", "Detratores",
                         "Respostas", "Receita", "Receita em risco", "Ações abertas", "Ações vencidas"]
    assert linhas[1] == ["Rita Gomes", "2", "2", "-40", "1", "1", "3", "5", "4000,00", "4000,00", "3", "1"]
    assert linhas[3][:4] == ["Sem responsável", "1", "0", ""]


# ---- operação ------------------------------------------------------------------------------

def test_operacao(client, cenario):
    h, c = cenario["h"], cenario["c"]
    r = _get(client, h, "/relatorios/operacao", **MARCO)
    # convidados (saiu): Carla, Caio, Cléo, Ciro e Clara (o do Cris deu erro); responderam 4 de 5
    assert r["taxa_resposta"] == {"percentual": 80, "responderam": 4, "convidados": 5, "amostra_pequena": False}
    assert r["canais"] == [{"canal": "email", "convidados": 3, "responderam": 2, "percentual": 67},
                           {"canal": "whatsapp", "convidados": 2, "responderam": 2, "percentual": 100}]
    # concluídas em março: 3 dias (no prazo), 1,5 dia (atrasada: meia-noite depois do prazo), 1 dia (sem prazo)
    assert r["acoes"] == {"concluidas": 3, "tempo_medio_dias": 1.8, "no_prazo_percentual": 50, "abertas": 3,
                          "vencidas": 1}
    sem = r["sem_resposta"]
    assert (sem["total"], sem["atrasados"], sem["intervalo_dias"]) == (2, 1, 90)
    assert [(x["contato"]["nome"], x["dias"], x["atrasado"]) for x in sem["itens"]] == [
        ("Clara Dez", 100, True), ("Célia Sete", 10, False)]
    assert sem["itens"][0]["contato"] == {"id": c[10]["id"], "nome": "Clara Dez", "email": c[10]["email"]}
    assert sem["itens"][0]["empresa"] == {"id": cenario["e"][6]["id"], "nome": "Empório Novo"}
    # sem o período: a lista é a mesma; com grupo_id, só os contatos das empresas do grupo
    r2 = _get(client, h, "/relatorios/operacao", grupo_id=cenario["g"][1]["id"])
    assert [x["contato"]["nome"] for x in r2["sem_resposta"]["itens"]] == ["Clara Dez"]
    linhas = _csv(client, h, "/relatorios/operacao/sem-resposta.csv")
    assert linhas[0] == ["Contato", "E-mail", "Empresa", "Último envio", "Dias", "Atrasado"]
    assert linhas[1][0] == "Clara Dez" and linhas[1][2:] == [
        "Empório Novo", (cenario["hoje"] - timedelta(days=100)).strftime("%d/%m/%Y"), "100", "Sim"]
    assert len(linhas) == 3


# ---- histórico de uma empresa ------------------------------------------------------------------

def test_historico(client, cenario):
    h, e, c = cenario["h"], cenario["e"], cenario["c"]
    r = _get(client, h, f"/relatorios/historico/{e[1]['id']}", **MARCO)
    assert r["empresa"] == {"id": e[1]["id"], "nome": "Atacado Norte", "ativa": True,
                            "grupo": {"id": cenario["g"][1]["id"], "nome": "Rede Leste"},
                            "segmento": {"id": cenario["s"][1]["id"], "nome": "Atacado"},
                            "responsavel": {"id": cenario["rita"]["id"], "nome": "Rita Gomes"},
                            "valor_mensal": 1000.0,
                            "cliente_desde": (cenario["hoje"] - timedelta(days=400)).isoformat()}
    assert r["nps"] == _nps(0, "pode_melhorar", 1, 1, 1)
    assert r["csat"] == {"percentual": 100, "media": 5.0, "total": 1}
    assert r["cobertura"] == {"contatos_ativos": 2, "responderam": 2, "percentual": 100}
    assert r["acoes"] == {"abertas": 2, "vencidas": 1, "concluidas": 1}
    assert r["evolucao"] == [{"mes": "2026-03", "nps": 0, "total": 3}]
    assert r["total"] == 4 and [x["nota"] for x in r["linha_do_tempo"]] == [5, 8, 3, 10]
    item = r["linha_do_tempo"][2]
    assert item == {
        "resposta_id": cenario["r_c1_3"], "data": item["data"], "nota": 3, "tipo_nota": "nps", "grupo": "detrator",
        "contato": {"id": c[1]["id"], "nome": "Carla Um", "cargo": "Comprador", "perfil": "Decisor"},
        "canal": "email", "origem": "pesquisa", "comentario": "Entrega atrasou", "temas": ["prazo_entrega"],
        "ia": {"sentimento": "negativo", "resumo": "Reclama do atraso na entrega"},
        "acao": {"id": item["acao"]["id"], "situacao": "a_fazer"},
    }
    assert r["linha_do_tempo"][1]["ia"] is None and r["linha_do_tempo"][1]["acao"] is None
    tudo = _get(client, h, f"/relatorios/historico/{e[1]['id']}")
    assert tudo["evolucao"] == [{"mes": "2026-02", "nps": -100, "total": 1}, {"mes": "2026-03", "nps": 0, "total": 3}]
    assert tudo["total"] == 5 and tudo["acoes"]["concluidas"] == 1
    sem_csat = _get(client, h, f"/relatorios/historico/{e[4]['id']}", **MARCO)
    assert sem_csat["csat"] is None and sem_csat["empresa"]["segmento"] is None
    assert client.get(f"{API}/relatorios/historico/999999", headers=h).status_code == 404
    linhas = _csv(client, h, f"/relatorios/historico/{e[1]['id']}.csv", **MARCO)
    assert linhas[0] == ["Data", "Nota", "Tipo", "Categoria", "Contato", "Cargo", "Canal", "Comentário", "Temas",
                         "Sentimento", "Resumo da IA"]
    assert linhas[3] == ["05/03/2026 12:00", "3", "NPS", "Detrator", "Carla Um", "Comprador", "E-mail",
                         "Entrega atrasou", "Prazo e entrega", "Negativo", "Reclama do atraso na entrega"]
    assert len(linhas) == 5
    assert client.get(f"{API}/relatorios/historico/999999.csv", headers=h).status_code == 404


# ---- permissões -------------------------------------------------------------------------------

ROTAS = ["/relatorios/empresas", "/relatorios/grupos", "/relatorios/temas", "/relatorios/entregas",
         "/relatorios/responsaveis", "/relatorios/responsaveis/0/empresas", "/relatorios/operacao"]
CSVS = ["/relatorios/empresas.csv", "/relatorios/entregas.csv", "/relatorios/responsaveis.csv",
        "/relatorios/operacao/sem-resposta.csv"]


def test_permissoes(client, cenario, dono):
    h, e = cenario["h"], cenario["e"]
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")  # relatorios.ver sem painel.exportar
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    for url in ROTAS + [f"/relatorios/historico/{e[1]['id']}"]:
        assert client.get(f"{API}{url}", headers=consulta["h"]).status_code == 200, url
    for url in CSVS + [f"/relatorios/historico/{e[1]['id']}.csv"]:
        assert client.get(f"{API}{url}", headers=consulta["h"]).status_code == 403, url
        assert client.get(f"{API}{url}", headers=gestor["h"]).status_code == 200, url
    sql(dono, "delete from perfil_permissoes where perfil = 'consulta' and permissao = 'relatorios.ver'")
    for url in ROTAS:
        assert client.get(f"{API}{url}", headers=consulta["h"]).status_code == 403, url
    assert client.get(f"{API}/relatorios/empresas").status_code == 401


# ---- desempenho --------------------------------------------------------------------------------

def test_desempenho_5000_contatos_1000_empresas_50000_respostas(client, dono):
    a = conta_pronta(client, "perf@alfa.com.br", empresa="Alfa Grande")
    h = a["h"]
    conta = a["conta"]["id"]
    definir_plano(dono, conta, "empresa")
    nps_id, csat_id = form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"]
    g = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede"}).json()
    seg = client.post(f"{API}/cadastros/segmentos", headers=h, json={"nome": "Atacado"}).json()
    resp = criar_responsavel(client, h, "Rita")
    sql(dono, """
        insert into empresas (conta_id, nome, grupo_id, segmento_id, responsavel_id, ativa, valor_mensal, cliente_desde)
        select :c, 'Empresa ' || n, case when n % 3 = 0 then :g end, case when n % 2 = 0 then :s end,
               case when n % 4 = 0 then :r end, n % 10 <> 0, case when n % 5 <> 0 then (n * 37 % 90000)::numeric end,
               case when n % 7 <> 0 then current_date - (n % 900) end
          from generate_series(1, 1000) n
    """, c=conta, g=g["id"], s=seg["id"], r=resp["id"])
    (e0,), = sql(dono, "select min(id) from empresas where conta_id = :c", c=conta)
    sql(dono, """
        insert into contatos (conta_id, codigo, nome, email, empresa_id, ativo, ultimo_envio)
        select :c, (300000000 + n)::text, 'Contato ' || n, 'p' || n || '@cliente.com.br',
               case when n % 50 <> 0 then :e0 + n % 1000 end, n % 40 <> 0,
               case when n % 3 = 0 then now() - (n % 200) * interval '1 day' end
          from generate_series(1, 5000) n
    """, c=conta, e0=e0)
    (c0,), = sql(dono, "select min(id) from contatos where conta_id = :c", c=conta)
    sql(dono, """
        insert into respostas (conta_id, formulario_id, contato_id, empresa_id, canal, origem, nota, tipo_nota, grupo,
                               comentario, comentario_cliente, temas, contexto, criada_em, arquivada, ia_situacao,
                               ia_temas, ia_sentimento)
        select :c, case when csat then :csat else :nps end, :c0 + k, case when k % 50 <> 0 then :e0 + k % 1000 end,
               'link', 'pesquisa', nota, case when csat then 'csat' else 'nps' end,
               case when csat then (case when nota <= 2 then 'insatisfeito' when nota = 3 then 'neutro'
                                         else 'satisfeito' end)
                    else (case when nota <= 6 then 'detrator' when nota <= 8 then 'neutro' else 'promotor' end) end,
               texto, texto,
               case n % 4 when 0 then array['prazo_entrega','atendimento'] when 1 then array['produto_avarias']
                          when 2 then array['atendimento'] else '{}'::text[] end,
               case when n % 3 = 0 then jsonb_build_object('motorista', 'Motorista ' || (n % 300),
                                                           'rota', 'Rota ' || (n % 40)) else '{}'::jsonb end,
               now() - (n % 730) * interval '1 day' - (n % 1440) * interval '1 minute', n % 97 = 0,
               case when n % 5 = 0 then 'analisada' end,
               case when n % 5 = 0 then '[{"tema": "atendimento", "sentimento": "negativo"}]'::jsonb end,
               case when n % 5 = 0 then 'negativo' end
          from (select n, (n * 7919) % 5000 as k, n % 10 = 0 as csat,
                       case when n % 10 = 0 then 1 + n % 5 else (n * 13) % 11 end as nota,
                       case n % 4 when 0 then 'Entrega atrasou e o atendimento demorou'
                                  when 1 then 'Produto chegou quebrado' when 2 then 'Ótimo vendedor' else '' end
                         as texto
                  from generate_series(1, 50000) n) x
    """, c=conta, nps=nps_id, csat=csat_id, c0=c0, e0=e0)
    sql(dono, """
        with cv as (
            insert into convites (conta_id, token_hash, formulario_id, contato_id, canal, criado_em)
            select :c, md5('perf4b' || n), :nps, :c0 + n % 5000, case when n % 4 = 0 then 'whatsapp' else 'email' end,
                   now() - (n % 365) * interval '1 day'
              from generate_series(1, 8000) n
            returning id, contato_id, canal, criado_em)
        insert into envios (conta_id, contato_id, convite_id, canal, tipo, origem, situacao, para, criado_em)
        select :c, contato_id, id, canal, 'convite', 'automatico',
               case when id % 9 = 0 then 'erro' else 'enviado' end, 'x', criado_em from cv
    """, c=conta, nps=nps_id, c0=c0)
    sql(dono, """
        insert into acoes (conta_id, empresa_id, titulo, prioridade, prazo, situacao, origem, criada_em, concluida_em)
        select :c, :e0 + n % 1000, 'Ação ' || n, 'media', current_date + (n % 30 - 15),
               (array['a_fazer','em_andamento','concluida'])[1 + n % 3], 'manual', now() - (n % 200) * interval '1 day',
               case when n % 3 = 2 then now() - (n % 100) * interval '1 day' end
          from generate_series(1, 3000) n
    """, c=conta, e0=e0)
    sql(dono, "analyze")
    assert sql(dono, "select count(*) from respostas where conta_id = :c", c=conta)[0][0] == 50000

    hoje = relogio.hoje()
    noventa = {"de": (hoje - timedelta(days=89)).isoformat(), "ate": hoje.isoformat()}
    rotas = [("empresas", "/relatorios/empresas", {}), ("empresas 90d", "/relatorios/empresas", noventa),
             ("empresas.csv", "/relatorios/empresas.csv", noventa), ("grupos", "/relatorios/grupos", noventa),
             ("temas", "/relatorios/temas", noventa), ("temas tudo", "/relatorios/temas", {}),
             ("entregas", "/relatorios/entregas", noventa), ("responsaveis", "/relatorios/responsaveis", noventa),
             ("responsavel/empresas", f"/relatorios/responsaveis/{resp['id']}/empresas", noventa),
             ("operacao", "/relatorios/operacao", noventa), ("historico", f"/relatorios/historico/{e0 + 7}", {}),
             ("painel", "/painel", noventa)]
    client.get(f"{API}/relatorios/empresas", headers=h)  # aquece conexões
    tempos = {}
    for nome, url, params in rotas:
        inicio = relogio_real.perf_counter()
        r = client.get(f"{API}{url}", headers=h, params=params)
        tempos[nome] = relogio_real.perf_counter() - inicio
        assert r.status_code == 200, (url, r.text)
    print("\nRelatórios com 5.000 contatos, 1.000 empresas e 50.000 respostas: " +
          ", ".join(f"{k} {v * 1000:.0f} ms" for k, v in tempos.items()))
    assert max(tempos.values()) < 1.0, tempos
