"""Etapa 5b: ferramentas do assistente — números iguais aos do painel (e do relatório de empresas) com os mesmos
filtros, períodos padrão e inválidos, empresa por parte do nome sem acento, empresa inativa, permissões, e o padrão
por palavras do provedor `memoria` (o do teste integrado)."""
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.exc import DataError, OperationalError
from util import (
    AJUDA_EXEMPLO,
    API,
    FUSO,
    conta_pronta,
    contexto_de,
    criar_contato,
    criar_empresa,
    fixar_relogio,
    form_padrao,
    inserir_resposta,
    membro,
    perguntar,
)

from toqqi.core import ia_conversa
from toqqi.core.deps import Contexto
from toqqi.modulos.ajuda import servico as ajuda
from toqqi.modulos.assistente import ferramentas
from toqqi.modulos.respostas.temas import ROTULOS

pytestmark = pytest.mark.usefixtures("relogio_estavel")
mem = ia_conversa.memoria
SEM_ACESSO = {"erro": "Seu perfil não tem acesso a estes dados."}


@pytest.fixture(autouse=True)
def ajuda_exemplo(monkeypatch):
    monkeypatch.setattr(ajuda, "CAMINHO", AJUDA_EXEMPLO)
    ajuda.limpar_cache()


@pytest.fixture
def cenario(client, dono, relogio_estavel):
    """Respostas nos últimos 30 dias, no período anterior e mais antigas; uma empresa inativa e uma arquivada."""
    hoje = relogio_estavel
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")
    h, conta = a["h"], a["conta"]["id"]
    e = {nome: criar_empresa(client, h, nome, **extra) for nome, extra in (
        ("Água Viva Distribuidora", {}), ("Mercado Joãozinho", {}), ("Padaria São João", {"ativa": False}),
        ("Alfa", {}), ("Comercial Alfa", {}))}
    c = {n: criar_contato(client, h, nome=f"Contato {n}", empresa_id=e[nome]["id"] if nome else None)
         for n, nome in ((1, "Água Viva Distribuidora"), (2, "Água Viva Distribuidora"), (3, "Mercado Joãozinho"),
                         (4, "Padaria São João"), (5, "Alfa"), (6, None), (7, "Comercial Alfa"))}
    nps, csat = form_padrao(client, h)["id"], form_padrao(client, h, "csat")["id"]

    def r(n, nota, dias, comentario="", tipo="nps", arquivada=False):
        inserir_resposta(dono, conta, nps if tipo == "nps" else csat, c[n], nota, hoje - timedelta(days=dias),
                         tipo=tipo, comentario=comentario, arquivada=arquivada)

    # últimos 30 dias
    r(1, 3, 1, "Entrega atrasou e o frete é caro")
    r(1, 10, 2, "Atendimento excelente")
    r(1, 9, 3)
    r(2, 8, 4, "Entrega ok, mas o preço subiu")
    r(2, 0, 5, "Produto quebrado")
    r(3, 6, 6, "Atrasou de novo")
    r(3, 2, 7)
    r(3, 9, 8, "Vendedor atencioso")
    r(4, 10, 9, "Entrega rápida")  # empresa inativa
    r(4, 10, 10)
    r(4, 1, 11, "Péssimo atendimento")
    r(5, 9, 12)
    r(5, 7, 13, "Site lento")
    r(5, 10, 14)
    r(5, 4, 15, "Demorou demais")
    r(6, 9, 16)  # sem empresa: sempre conta
    r(7, 5, 17, "Caro")
    r(1, 0, 2, "Arquivada", arquivada=True)  # fora de tudo
    r(1, 5, 1, "Ótimo", tipo="csat")
    r(2, 2, 3, "Ruim", tipo="csat")
    r(4, 4, 4, tipo="csat")  # empresa inativa
    # período anterior (de 30 a 59 dias atrás) e mais antigas
    r(1, 10, 35)
    r(3, 3, 40, "Atrasou")
    r(5, 9, 45)
    r(5, 8, 50)
    r(1, 7, 100)
    r(2, 2, 130, "Muito antigo")
    return {**a, "hoje": hoje, "empresas": e, "ctx": contexto_de(a)}


def _ferramenta(ctx, ferramenta: str, /, **argumentos) -> dict:
    return ferramentas.executar(ctx, ferramenta, argumentos)


def _painel(client, h, de: date, ate: date, **extra) -> dict:
    r = client.get(f"{API}/painel", headers=h, params={"de": de.isoformat(), "ate": ate.isoformat(), **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _relatorio(client, h, de: date, ate: date, nome: str, **extra) -> dict:
    r = client.get(f"{API}/relatorios/empresas", headers=h,
                   params={"de": de.isoformat(), "ate": ate.isoformat(), "busca": nome, **extra})
    assert r.status_code == 200, r.text
    return next(x for x in r.json()["itens"] if x["empresa"]["nome"] == nome)


NPS = ("valor", "total", "promotores", "neutros", "detratores")


# ---- números iguais aos do painel ---------------------------------------------------------------

def test_indicadores_iguais_ao_painel(client, cenario):
    hoje, ctx, h = cenario["hoje"], cenario["ctx"], cenario["h"]
    de = hoje - timedelta(days=29)
    r = _ferramenta(ctx, "indicadores", empresa_id=None, de=None, ate=None)  # padrão: últimos 30 dias
    p = _painel(client, h, de, hoje)
    assert r["periodo"] == {"de": de.isoformat(), "ate": hoje.isoformat()} and r["empresa"] is None
    assert r["nps"] == {k: p["nps"][k] for k in NPS}
    assert r["csat"] == {k: p["csat"][k] for k in ("percentual", "media", "total")}
    assert r["anterior"] == {"periodo": p["periodo"]["anterior"],
                             "nps": {"valor": p["variacao"]["anterior"], "total": 4}}
    assert r["variacao"] == p["variacao"]["valor"]
    # conferido à mão: 14 respostas NPS (sem a inativa e a arquivada): 6 promotores, 2 neutros, 6 detratores
    assert (r["nps"]["total"], r["nps"]["promotores"], r["nps"]["neutros"], r["nps"]["detratores"]) == (14, 6, 2, 6)
    assert r["nps"]["valor"] == 0 and r["amostra_pequena"] is True
    assert r["csat"] == {"percentual": 50, "media": 3.5, "total": 2}
    # mesmo período em datas explícitas
    assert _ferramenta(ctx, "indicadores", empresa_id=None, de=de.isoformat(), ate=hoje.isoformat()) == r


def test_indicadores_da_empresa_iguais_ao_relatorio(client, cenario):
    hoje, ctx, h, e = cenario["hoje"], cenario["ctx"], cenario["h"], cenario["empresas"]
    de = hoje - timedelta(days=89)
    for nome in ("Água Viva Distribuidora", "Alfa", "Mercado Joãozinho"):
        r = _ferramenta(ctx, "indicadores", empresa_id=e[nome]["id"], de=de.isoformat(), ate=None)
        assert r["empresa"] == {"id": e[nome]["id"], "nome": nome}
        assert r["nps"] == {k: _relatorio(client, h, de, hoje, nome)["nps"][k] for k in NPS}
    alfa = _ferramenta(ctx, "indicadores", empresa_id=e["Alfa"]["id"], de=None, ate=None)
    assert alfa["nps"] == {"valor": 25, "total": 4, "promotores": 2, "neutros": 1, "detratores": 1}
    assert alfa["anterior"]["nps"] == {"valor": 50, "total": 2} and alfa["variacao"] == -25


def test_empresa_inativa_conta_as_respostas_dela(client, cenario):
    hoje, ctx, h, e = cenario["hoje"], cenario["ctx"], cenario["h"], cenario["empresas"]
    padaria = e["Padaria São João"]
    r = _ferramenta(ctx, "indicadores", empresa_id=padaria["id"], de=None, ate=None)
    assert r["nps"] == {"valor": 33, "total": 3, "promotores": 2, "neutros": 0, "detratores": 1}
    assert r["csat"]["total"] == 1
    de = hoje - timedelta(days=29)
    assert r["nps"] == {k: _relatorio(client, h, de, hoje, "Padaria São João", so_ativos="false")["nps"][k]
                        for k in NPS}
    # no total da conta ela fica de fora (so_ativos), como no painel
    assert _ferramenta(ctx, "indicadores", empresa_id=None, de=None, ate=None)["nps"]["total"] == 14
    comentarios = _ferramenta(ctx, "comentarios", empresa_id=padaria["id"], grupo="todos", de=None, ate=None,
                              limite=None)["comentarios"]
    assert [x["texto"] for x in comentarios] == ["Entrega rápida", "Péssimo atendimento"]


def test_temas_ranking_comentarios_e_evolucao_iguais_ao_painel(client, cenario):
    hoje, ctx, h = cenario["hoje"], cenario["ctx"], cenario["h"]
    de = hoje - timedelta(days=29)
    p = _painel(client, h, de, hoje)
    temas = _ferramenta(ctx, "temas", empresa_id=None, de=None, ate=None)["temas"]
    assert temas[:5] == [{"tema": ROTULOS[t["chave"]], "mencoes": t["mencoes"], "reclamacoes": t["reclamacoes"],
                          "nota_media": t["nota_media"]} for t in p["temas"]]
    assert len(temas) <= 6
    menor = _ferramenta(ctx, "ranking_empresas", ordem="menor", de=None, ate=None, limite=10)
    maior = _ferramenta(ctx, "ranking_empresas", ordem="maior", de=None, ate=None, limite=None)
    assert menor["minimo_respostas"] == 3
    assert [x["id"] for x in menor["empresas"][:len(p["empresas"]["menor"])]] == [
        x["empresa"]["id"] for x in p["empresas"]["menor"]]
    assert [x["id"] for x in maior["empresas"][:len(p["empresas"]["maior"])]] == [
        x["empresa"]["id"] for x in p["empresas"]["maior"]]
    assert [(x["nome"], x["nps"], x["respostas"]) for x in menor["empresas"]] == [
        ("Mercado Joãozinho", -33, 3), ("Água Viva Distribuidora", 0, 5), ("Alfa", 25, 4)]  # a inativa fica fora
    assert len(_ferramenta(ctx, "ranking_empresas", ordem="menor", de=None, ate=None, limite=1)["empresas"]) == 1
    # comentários: os mais recentes com texto do cliente (NPS e CSAT), como o painel
    todos = _ferramenta(ctx, "comentarios", empresa_id=None, grupo="todos", de=None, ate=None, limite=6)
    assert [(x["texto"], x["nota"], x["tipo_nota"], x["grupo"]) for x in todos["comentarios"]] == [
        (x["comentario"], x["nota"], x["tipo_nota"], x["grupo"]) for x in p["comentarios"]]
    assert todos["comentarios"][0]["texto"] == "Ótimo"  # mesmo dia e hora: a gravada por último primeiro
    assert todos["comentarios"][1] == {"data": (hoje - timedelta(days=1)).isoformat(), "nota": 3, "tipo_nota": "nps",
                                       "grupo": "detrator", "empresa": "Água Viva Distribuidora",
                                       "contato": "Contato 1", "texto": "Entrega atrasou e o frete é caro"}
    detratores = _ferramenta(ctx, "comentarios", empresa_id=None, grupo="detratores", de=None, ate=None, limite=10)
    assert [x["texto"] for x in detratores["comentarios"]] == [
        "Entrega atrasou e o frete é caro", "Produto quebrado", "Atrasou de novo", "Demorou demais", "Caro"]
    assert _ferramenta(ctx, "comentarios", empresa_id=None, grupo="promotores", de=None, ate=None,
                       limite=2)["comentarios"][0]["texto"] == "Atendimento excelente"
    # evolução: os meses do calendário até o atual, inclusive os sem respostas
    evolucao = _ferramenta(ctx, "evolucao_mensal", empresa_id=None, meses=6)["meses"]
    assert len(evolucao) == 6 and evolucao[-1]["mes"] == hoje.strftime("%Y-%m")
    inicio = date.fromisoformat(evolucao[0]["mes"] + "-01")
    assert [x for x in evolucao if x["total"]] == _painel(client, h, inicio, hoje)["evolucao"]
    assert all(x["nps"] is None for x in evolucao if not x["total"])
    assert [x["mes"] for x in _ferramenta(ctx, "evolucao_mensal", empresa_id=None, meses=1)["meses"]] == [
        hoje.strftime("%Y-%m")]


def test_textos_dos_comentarios_cortados(client, cenario, dono):
    ctx, hoje = cenario["ctx"], cenario["hoje"]
    contato = criar_contato(client, cenario["h"], nome="Longo")
    inserir_resposta(dono, cenario["conta"]["id"], form_padrao(client, cenario["h"])["id"], contato, 1, hoje,
                     comentario="muito\nruim " * 100)
    texto = _ferramenta(ctx, "comentarios", empresa_id=None, grupo="detratores", de=None, ate=None,
                        limite=1)["comentarios"][0]["texto"]
    assert len(texto) <= 500 and texto.endswith("…") and "\n" not in texto


# ---- períodos ------------------------------------------------------------------------------------------

def test_periodos_padrao_e_invalidos(monkeypatch):
    fixar_relogio(monkeypatch, datetime(2026, 10, 2, 12, tzinfo=FUSO))
    d = date.fromisoformat
    assert ferramentas.periodo(None, None) == (d("2026-09-03"), d("2026-10-02"))
    assert ferramentas.periodo("2026-09-01", None) == (d("2026-09-01"), d("2026-10-02"))
    assert ferramentas.periodo(None, "2026-09-15") == (d("2026-08-17"), d("2026-09-15"))
    assert ferramentas.periodo("2025-10-01", "2026-10-01") == (d("2025-10-01"), d("2026-10-01"))  # 366 dias
    assert ferramentas.periodo("2026-10-02", "2026-10-02") == (d("2026-10-02"), d("2026-10-02"))
    for de, ate, trecho in (
        ("2026-09-10", "2026-09-01", "anterior à final"),
        ("2026-10-03", None, "anterior à final"),
        (None, "2026-10-03", "depois de hoje (2026-10-02)"),
        ("2025-09-30", "2026-10-01", "12 meses"),
        ("02/10/2026", None, "AAAA-MM-DD"),
        (None, 20260901, "AAAA-MM-DD"),
        ("2026-02-30", None, "não existe"),
        ("1999-12-31", None, "entre 2000 e 2100"),
    ):
        with pytest.raises(ferramentas.Uso, match=re.escape(trecho)):
            ferramentas.periodo(de, ate)


def test_problemas_de_uso_viram_erro_para_o_modelo(client, cenario):
    ctx, e = cenario["ctx"], cenario["empresas"]
    amanha = (cenario["hoje"] + timedelta(days=1)).isoformat()
    casos = [
        ("indicadores", {"empresa_id": None, "de": None, "ate": amanha}, "depois de hoje"),
        ("indicadores", {"empresa_id": 999999, "de": None, "ate": None}, "Empresa não encontrada."),
        ("indicadores", {"empresa_id": "abc", "de": None, "ate": None}, "empresa_id"),
        ("indicadores", {"empresa_id": True, "de": None, "ate": None}, "empresa_id"),
        ("ranking_empresas", {"ordem": "pior", "de": None, "ate": None, "limite": None}, "ordem"),
        ("ranking_empresas", {"ordem": "menor", "de": None, "ate": None, "limite": 11}, "de 1 a 10"),
        ("ranking_empresas", {"ordem": "menor", "de": None, "ate": None, "limite": 0}, "de 1 a 10"),
        ("comentarios", {"empresa_id": None, "grupo": "raivosos", "de": None, "ate": None, "limite": None}, "grupo"),
        ("evolucao_mensal", {"empresa_id": None, "meses": 13}, "de 1 a 12"),
        ("temas", {"empresa_id": e["Alfa"]["id"], "de": "2026-13-01", "ate": None}, "não existe"),
        ("buscar_empresas", {"nome": "  "}, "parte do nome"),
        ("buscar_ajuda", {"termo": ""}, "assunto"),
        ("apagar_tudo", {}, "Ferramenta desconhecida."),
    ]
    for nome, argumentos, trecho in casos:
        r = ferramentas.executar(ctx, nome, argumentos)
        assert set(r) == {"erro"} and trecho in r["erro"], (nome, r)


def test_argumentos_que_o_banco_recusaria_nao_chegam_a_ele(client, cenario):
    """Os argumentos vêm do modelo: empresa_id fora do bigint, NUL e surrogates soltos não chegam ao banco (antes
    viravam DataError ou UnicodeEncodeError e a pergunta dava 500), nem um grupo que não é texto (TypeError)."""
    ctx = cenario["ctx"]
    periodo = {"de": None, "ate": None}
    com_empresa = {"indicadores": periodo, "temas": periodo, "evolucao_mensal": {"meses": None},
                   "comentarios": {"grupo": "todos", "limite": None, **periodo}}
    for empresa_id in (2**63, 2**64 + 1, 10**40, 0, -1, -(2**63), -(2**63) - 1, 2**63 - 1):
        for nome, argumentos in com_empresa.items():
            r = ferramentas.executar(ctx, nome, {"empresa_id": empresa_id, **argumentos})
            assert r == {"erro": "Empresa não encontrada."}, (nome, empresa_id, r)
    for nome in ("alfa\x00", "\x00ALFA", "al\ud800fa", "\udfffalfa\x1b"):  # limpo antes do SQL
        r = _ferramenta(ctx, "buscar_empresas", nome=nome)
        assert [(x["nome"], x["ativa"]) for x in r["empresas"]] == [("Alfa", True), ("Comercial Alfa", True)], nome
    for nome in ("\x00", "\ud800", " \x07\udc00 "):  # nada sobra depois de limpar
        assert _ferramenta(ctx, "buscar_empresas", nome=nome) == {"erro": "Informe parte do nome da empresa."}
    for grupo in (["detratores"], {"grupo": "todos"}, 3):
        r = _ferramenta(ctx, "comentarios", empresa_id=None, grupo=grupo, de=None, ate=None, limite=None)
        assert r["erro"].startswith("Use grupo"), grupo


def test_pergunta_com_argumentos_estranhos_responde(client, cenario):
    e = cenario["empresas"]
    mem.programar([ia_conversa.chamada("buscar_empresas", nome="Alfa\x00"),
                   ia_conversa.chamada("indicadores", empresa_id=2**63, de=None, ate=None),
                   ia_conversa.chamada("buscar_empresas", nome="\ud800")], ia_conversa.final("Pronto."))
    r = perguntar(client, cenario["h"], "Qual o NPS da Alfa?")
    assert r.status_code == 200 and r.json()["resposta"] == "Pronto."
    saidas = [json.loads(i["output"]) for i in mem.corpos[1]["input"] if i.get("type") == "function_call_output"]
    assert saidas == [{"empresas": [{"id": e[n]["id"], "nome": n, "ativa": True} for n in ("Alfa", "Comercial Alfa")],
                       "total": 2},
                      {"erro": "Empresa não encontrada."}, {"erro": "Informe parte do nome da empresa."}]


def _contexto_qualquer() -> Contexto:
    return Contexto(usuario_id=1, conta_id=1, sessao_id=uuid.uuid4(), email="ana@alfa.com.br", perfil="admin",
                    superadmin=False, permissoes=[])


@pytest.mark.parametrize("erro", [
    DataError("select …", {}, Exception("DADO-SIGILOSO")),
    OperationalError("select …", {}, Exception("DADO-SIGILOSO")),
    ValueError("DADO-SIGILOSO"),
    UnicodeEncodeError("utf-8", "DADO-SIGILOSO\ud800", 13, 14, "surrogates not allowed"),
])
def test_erro_do_banco_ou_de_valor_vira_erro_sem_detalhes(monkeypatch, caplog, erro):
    """Erro do banco ou de valor que escape das conferências: {"erro": "Não consegui consultar esses dados."} para o
    modelo, sem detalhes técnicos; o log leva só a ferramenta e a classe do erro."""
    def quebrada(ctx, a):
        raise erro

    monkeypatch.setitem(ferramentas.FERRAMENTAS, "temas", quebrada)
    with caplog.at_level(logging.WARNING, logger="toqqi.assistente"):
        r = ferramentas.executar(_contexto_qualquer(), "temas", {})
    assert r == {"erro": "Não consegui consultar esses dados."}
    assert "Assistente: a consulta temas falhou na conta 1 (" in caplog.text and "SIGILOSO" not in caplog.text


def test_outros_erros_da_ferramenta_sobem(monkeypatch):
    """Bug (outra exceção) não vira resposta para o modelo: sobe, e a pergunta devolve a análise (test_assistente)."""
    def quebrada(ctx, a):
        raise RuntimeError("bug")

    monkeypatch.setitem(ferramentas.FERRAMENTAS, "temas", quebrada)
    with pytest.raises(RuntimeError):
        ferramentas.executar(_contexto_qualquer(), "temas", {})


# ---- empresas por parte do nome ------------------------------------------------------------------------

def test_buscar_empresas_sem_acento_e_por_parte_do_nome(client, cenario):
    ctx, e = cenario["ctx"], cenario["empresas"]

    def nomes(termo):
        r = _ferramenta(ctx, "buscar_empresas", nome=termo)
        return [(x["nome"], x["ativa"]) for x in r["empresas"]], r["total"]

    assert nomes("joao") == ([("Mercado Joãozinho", True), ("Padaria São João", False)], 2)
    assert nomes("ÁGUA viva") == ([("Água Viva Distribuidora", True)], 1)
    assert nomes("alfa") == ([("Alfa", True), ("Comercial Alfa", True)], 2)  # as que começam com o termo primeiro
    assert nomes("ALF") == ([("Alfa", True), ("Comercial Alfa", True)], 2)
    assert nomes("%") == ([], 0) and nomes("_") == ([], 0) and nomes("xyz") == ([], 0)
    assert _ferramenta(ctx, "buscar_empresas", nome="padaria")["empresas"] == [
        {"id": e["Padaria São João"]["id"], "nome": "Padaria São João", "ativa": False}]
    for n in range(10):
        criar_empresa(client, cenario["h"], f"Loja {n:02d}")
    r = _ferramenta(ctx, "buscar_empresas", nome="loja")
    assert r["total"] == 10 and [x["nome"] for x in r["empresas"]] == [f"Loja {n:02d}" for n in range(8)]
    # empresas de outra conta não aparecem
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    criar_empresa(client, outra["h"], "Alfa Beta")
    assert nomes("alfa")[1] == 2


# ---- permissões ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("permissoes,podem", [
    (["contatos.ver"], {"buscar_empresas", "buscar_ajuda"}),
    (["respostas.ver"], {"buscar_empresas", "comentarios", "buscar_ajuda"}),
    (["painel.ver"], {"buscar_empresas", "indicadores", "ranking_empresas", "temas", "evolucao_mensal",
                      "buscar_ajuda"}),
    (["relatorios.ver"], {"buscar_empresas", "indicadores", "ranking_empresas", "temas", "evolucao_mensal",
                          "buscar_ajuda"}),
    ([], {"buscar_ajuda"}),
])
def test_permissoes_das_ferramentas(cenario, permissoes, podem):
    ctx = contexto_de(cenario, permissoes)
    argumentos = {
        "buscar_empresas": {"nome": "alfa"}, "indicadores": {"empresa_id": None, "de": None, "ate": None},
        "ranking_empresas": {"ordem": "menor", "de": None, "ate": None, "limite": None},
        "comentarios": {"empresa_id": None, "grupo": "todos", "de": None, "ate": None, "limite": None},
        "temas": {"empresa_id": None, "de": None, "ate": None}, "evolucao_mensal": {"empresa_id": None, "meses": 3},
        "buscar_ajuda": {"termo": "planilha"}}
    for nome, args in argumentos.items():
        r = ferramentas.executar(ctx, nome, args)
        assert (r != SEM_ACESSO) == (nome in podem), (nome, r)


# ---- padrão do provedor de memória (teste integrado) --------------------------------------------------------------

def test_padrao_nps_da_empresa_nos_ultimos_90_dias(client, cenario):
    h, e, hoje = cenario["h"], cenario["empresas"], cenario["hoje"]
    de = hoje - timedelta(days=89)
    r = perguntar(client, h, "Qual o NPS da Alfa nos últimos 90 dias?")
    assert r.status_code == 200, r.text
    feitas = [[(i["name"], i["arguments"]) for i in c["input"] if i.get("type") == "function_call"][-1:]
              for c in mem.corpos[1:]]
    assert [f[0][0] for f in feitas] == ["buscar_empresas", "indicadores"]
    esperado = _ferramenta(cenario["ctx"], "indicadores", empresa_id=e["Alfa"]["id"], de=de.isoformat(),
                           ate=hoje.isoformat())
    relatorio = _relatorio(client, h, de, hoje, "Alfa")["nps"]
    assert esperado["nps"] == {k: relatorio[k] for k in NPS}
    nps = esperado["nps"]
    resposta = r.json()["resposta"]
    assert resposta.startswith(f"O NPS da Alfa de {de.strftime('%d/%m/%Y')} a {hoje.strftime('%d/%m/%Y')} foi "
                               f"{nps['valor']}, com {nps['total']} respostas: {nps['promotores']} promotores, "
                               f"{nps['neutros']} neutros e {nps['detratores']} detratores.")
    assert "Amostra pequena" in resposta and r.json()["atalhos"][0]["chave"] == "relatorios"


def test_padrao_nps_da_conta_ranking_e_detratores(client, cenario):
    h, hoje = cenario["h"], cenario["hoje"]
    r = perguntar(client, h, "Qual é o NPS dos últimos 30 dias?").json()
    assert r["resposta"].startswith(f"O NPS de {(hoje - timedelta(days=29)).strftime('%d/%m/%Y')} a "
                                    f"{hoje.strftime('%d/%m/%Y')} foi 0, com 14 respostas")
    r = perguntar(client, h, "Quais clientes têm o NPS mais baixo nos últimos 90 dias?").json()
    assert r["resposta"].splitlines()[1] == "- Mercado Joãozinho: NPS -50 (4 respostas)"
    r = perguntar(client, h, "O que os detratores disseram nos últimos 10 dias?").json()
    assert r["resposta"].splitlines()[:4] == [
        f"Comentários mais recentes de {(hoje - timedelta(days=9)).strftime('%d/%m/%Y')} a "
        f"{hoje.strftime('%d/%m/%Y')}:",
        f"- {(hoje - timedelta(days=1)).strftime('%d/%m/%Y')}, nota 3 (Água Viva Distribuidora): Entrega atrasou e o "
        "frete é caro",
        f"- {(hoje - timedelta(days=5)).strftime('%d/%m/%Y')}, nota 0 (Água Viva Distribuidora): Produto quebrado",
        f"- {(hoje - timedelta(days=6)).strftime('%d/%m/%Y')}, nota 6 (Mercado Joãozinho): Atrasou de novo"]
    mem.limpar()
    perguntar(client, h, "O que os detratores disseram este mês?")
    consulta, = [json.loads(i["arguments"]) for i in mem.corpos[-1]["input"] if i.get("type") == "function_call"]
    assert consulta == {"empresa_id": None, "grupo": "detratores", "de": hoje.replace(day=1).isoformat(),
                        "ate": hoje.isoformat(), "limite": 5}
    r = perguntar(client, h, "Qual o NPS do cliente Inexistente?").json()
    assert r["resposta"] == "Não encontrei nenhuma empresa com \"Inexistente\" no nome."
    r = perguntar(client, h, "Qual o NPS da joao?").json()  # duas parecidas: pergunta qual
    assert r["resposta"].startswith("Encontrei mais de uma empresa parecida: Mercado Joãozinho, Padaria São João.")


def test_padrao_duvida_de_uso_responde_com_a_ajuda_e_o_atalho(client, cenario):
    h = cenario["h"]
    r = perguntar(client, h, "Como importo meus contatos?").json()
    assert r["resposta"].startswith("Importar uma planilha (Contatos):\nTraga muitos contatos")
    assert [a["chave"] for a in r["atalhos"]] == ["importar_contatos", "ajuda"]
    assert mem.corpos[0]["tool_choice"] == "auto"
    # quem não pode importar não recebe o atalho da tela de importação
    consulta = membro(client, h, "consulta@alfa.com.br", "consulta")
    r = perguntar(client, consulta["h"], "Como importo meus contatos?").json()
    assert [a["chave"] for a in r["atalhos"]] == ["ajuda"]
