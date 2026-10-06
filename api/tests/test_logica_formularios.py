"""Etapa 5l: o motor da lógica dos formulários (`formularios/logica.py`) com os casos compartilhados com o site
(`docs/casos-logica-5l.json`: caminho, finais e legado) e as peças do motor (norm, número de texto, grupos, sem
resposta).
As citações (`citacoes` do JSON) são do navegador: a API não troca os tokens."""
import json
from pathlib import Path

import pytest

from toqqi.modulos.formularios import logica

CASOS = json.loads((Path(__file__).resolve().parents[2] / "docs" / "casos-logica-5l.json").read_text(encoding="utf-8"))


def _ids(grupo: str) -> list[str]:
    return [c["nome"] for c in CASOS[grupo]]


def test_o_arquivo_tem_os_tres_grupos_de_casos():
    assert CASOS["versao"] == 1
    assert len(CASOS["caminho"]) >= 20 and len(CASOS["finais"]) >= 5 and len(CASOS["legado"]) >= 3


@pytest.mark.parametrize("caso", CASOS["caminho"], ids=_ids("caminho"))
def test_caminho(caso):
    assert logica.caminho(caso["itens"], caso["respostas"]) == caso["caminho"]


@pytest.mark.parametrize("caso", CASOS["finais"], ids=_ids("finais"))
def test_final(caso):
    assert logica.escolher_final(caso["finais"], caso["itens"], caso["respostas"]) == caso["final"]


@pytest.mark.parametrize("caso", CASOS["legado"], ids=_ids("legado"))
def test_legado(caso):
    assert logica.converter_condicao_legada(caso["condicao"], caso["principal"]) == caso["mostrar_se"]


# ---- peças do motor ----------------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperado", [
    ("  SÃO   Paulo ", "sao paulo"), ("Preço\talto\n", "preco alto"), ("ÇÉÍ", "cei"), ("", ""),
])
def test_norm(texto, esperado):
    assert logica.norm(texto) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("1.250,5", 1250.5), ("12.5", 12.5), ("12,5", 12.5), (" 7 ", 7.0), ("-3", -3.0), ("1.250", 1.25),
    ("abc", None), ("", None), ("1e3", None), ("nan", None), ("1_000", None), (10, 10.0), (True, None),
])
def test_numero_do_texto(texto, esperado):
    assert logica.numero_do_texto(texto) == esperado


def test_grupos_das_notas():
    assert [logica.grupo_da_nota("nps", n) for n in (0, 6, 7, 8, 9, 10)] == [
        "detrator", "detrator", "neutro", "neutro", "promotor", "promotor"]
    assert [logica.grupo_da_nota("csat", n) for n in (1, 2, 3, 4, 5)] == [
        "insatisfeito", "insatisfeito", "neutro", "satisfeito", "satisfeito"]
    assert logica.grupo_da_nota("estrelas", 3) == "neutro"
    assert logica.grupo_da_nota("escala", 3) is None and logica.grupo_da_nota("nps", None) is None


def _mostra(itens, respostas) -> list[str]:
    return logica.caminho(itens, respostas)


def test_valor_invalido_conta_como_sem_resposta():
    itens = [{"id": "p1", "tipo": "nps"}, {"id": "p2", "tipo": "escolha_unica", "opcoes": ["A", "B"]},
             {"id": "p3", "tipo": "comentario", "logica": {"mostrar_se": {"juncao": "qualquer", "condicoes": [
                 {"fonte": "p1", "op": "nao_respondida"}, {"fonte": "p2", "op": "nao_respondida"}]}}},
             {"id": "p4", "tipo": "comentario", "logica": {"mostrar_se": {"juncao": "todas", "condicoes": [
                 {"fonte": "p1", "op": "diferente", "valor": 5}]}}}]
    assert _mostra(itens, {"p1": 11, "p2": "A"}) == ["p1", "p2", "p3"]  # nota fora da faixa
    assert _mostra(itens, {"p1": True, "p2": "A"}) == ["p1", "p2", "p3"]  # bool não é nota
    assert _mostra(itens, {"p1": 9, "p2": "C"}) == ["p1", "p2", "p3", "p4"]  # opção que não existe
    assert _mostra(itens, {"p1": 9, "p2": "B"}) == ["p1", "p2", "p4"]


def test_fonte_desconhecida_e_grupo_vazio():
    itens = [{"id": "p1", "tipo": "comentario", "logica": {"mostrar_se": {"juncao": "todas", "condicoes": [
        {"fonte": "nao_existe", "op": "nao_respondida"}]}}},
        {"id": "p2", "tipo": "comentario", "logica": {"mostrar_se": {"juncao": "qualquer", "condicoes": []}}},
        {"id": "p3", "tipo": "comentario", "logica": {"mostrar_se": {"juncao": "todas", "condicoes": [
            {"fonte": "nao_existe", "op": "igual", "valor": "x"}]}}}]
    assert _mostra(itens, {}) == ["p1", "p2"]


def test_pular_para_tras_ou_para_id_desconhecido_e_ignorado():
    regra = {"id": "r1", "se": {"juncao": "todas", "condicoes": [{"fonte": "p2", "op": "respondida"}]}}
    itens = [{"id": "p1", "tipo": "comentario"},
             {"id": "p2", "tipo": "comentario", "logica": {"pular": [{**regra, "para": "p1"}, {**regra, "para": "x"}]}},
             {"id": "p3", "tipo": "comentario"}]
    assert _mostra(itens, {"p2": "a"}) == ["p1", "p2", "p3"]


def test_finais_e_valores_do_caminho():
    itens = [{"id": "p1", "tipo": "sim_nao", "logica": {"pular": [
        {"id": "r1", "se": {"juncao": "todas", "condicoes": [{"fonte": "p1", "op": "igual", "valor": False}]},
         "para": "p3"}]}}, {"id": "p2", "tipo": "nps"}, {"id": "c1", "tipo": "conteudo"}, {"id": "p3", "tipo": "data"}]
    assert logica.valores_do_caminho(itens, {"p1": False, "p2": 10, "c1": "x", "p3": "2026-01-02"}) == {
        "p1": False, "p3": "2026-01-02"}
    finais = [{"id": "f_sem",
               "mostrar_se": {"juncao": "todas", "condicoes": [{"fonte": "p2", "op": "nao_respondida"}]}}]
    assert logica.escolher_final(finais, itens, {"p1": False, "p2": 10}) == "f_sem"
    assert logica.escolher_final(finais, itens, {"p1": True, "p2": 10}) is None
    assert logica.escolher_final([], itens, {}) is None


def test_operadores_por_tipo():
    assert "grupo_e" in logica.operadores({"tipo": "nps"}) and "grupo_e" not in logica.operadores({"tipo": "escala"})
    assert "contem" in logica.operadores({"tipo": "texto_curto", "formato": "email"})
    assert "contem" not in logica.operadores({"tipo": "texto_curto", "formato": "numero"})
    assert logica.operadores({"tipo": "sim_nao"}) == ("igual", "respondida", "nao_respondida")
    assert logica.operadores({"tipo": "conteudo"}) == ("respondida", "nao_respondida")


def test_legado_invalido_e_sem_citacoes_e_descricao():
    assert logica.converter_condicao_legada({"tipo": "nota", "operador": "<"}, "p1") is None
    assert logica.converter_condicao_legada({"tipo": "grupo", "grupos": ["detrator"]}, None) is None
    assert logica.sem_citacoes("Por que {{p_abc123}}? {{ x }}") == "Por que …? {{ x }}"
    assert logica.sem_citacoes("Nota {{p1}}", "") == "Nota "
    itens = [{"id": "p1", "tipo": "nps", "titulo": "Recomendaria?"},
             {"id": "p2", "tipo": "sim_nao", "titulo": "É cliente?"}]
    grupo = {"juncao": "qualquer", "condicoes": [{"fonte": "p1", "op": "grupo_e", "valor": ["detrator", "neutro"]},
                                                 {"fonte": "p2", "op": "igual", "valor": False}]}
    assert logica.descrever_grupo(grupo, itens) == "NPS é detrator ou neutro ou “É cliente?” é Não"
    assert logica.descrever_grupo(None, itens) == "Sempre"
