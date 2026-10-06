"""Migração 0026 (etapa 5l, docs/api-etapa-5l.md §4.7): colunas novas de `formularios` (CHECKs e FKs de usuário),
`respostas.formulario_versao`, `imagens` com `conteudo_formulario` (até 1 MB, sempre com formulário) e mais de um logo
por formulário; a `condicao` antiga vira `logica.mostrar_se` (publicado e rascunho); descer para a 0025 (lógica simples
volta a ser `condicao`, o resto sai) e subir de novo."""
import hashlib
import json

import pytest
from alembic.config import Config as AlembicConfig
from conftest import OWNER_URL
from sqlalchemy.exc import IntegrityError
from util import API, conta_pronta, form_padrao, png, sql

from alembic import command
from toqqi.core.db import RAIZ_API

COLUNAS = {"finais", "rascunho", "rascunho_rev", "rascunho_em", "rascunho_por", "versao", "publicado_em",
           "publicado_por"}


def _alembic() -> AlembicConfig:
    cfg = AlembicConfig(str(RAIZ_API / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_API / "alembic"))
    cfg.attributes["url"] = OWNER_URL
    return cfg


def _colunas(dono, tabela: str) -> set[str]:
    return {c for (c,) in sql(dono, "select column_name from information_schema.columns "
                                    "where table_schema = 'public' and table_name = :t", t=tabela)}


def _perguntas(dono, fid: int) -> list:
    return sql(dono, "select perguntas from formularios where id = :f", f=fid)[0][0]


def _imagem(dono, conta_id: int, uso: str, formulario_id: int | None, chave: str, dados: bytes = None) -> None:
    dados = png() if dados is None else dados
    sql(dono, "insert into imagens (conta_id, uso, formulario_id, chave, tipo, dados, tamanho, sha256) "
              "values (:c, :u, :f, :k, 'image/png', :d, :t, :h)", c=conta_id, u=uso, f=formulario_id, k=chave,
        d=dados, t=len(dados), h=hashlib.sha256(dados).hexdigest())


def test_objetos_e_restricoes(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    f = form_padrao(client, a["h"])
    assert COLUNAS <= _colunas(dono, "formularios") and "formulario_versao" in _colunas(dono, "respostas")
    assert sql(dono, "select to_regclass('imagens_formulario_idx'), to_regclass('imagens_logo_formulario_key')") == [
        ("imagens_formulario_idx", None)]
    fks = {n for (n,) in sql(dono, "select conname from pg_constraint where conrelid = 'formularios'::regclass "
                                   "and contype = 'f'")}
    assert {"formularios_rascunho_por_fkey", "formularios_publicado_por_fkey"} <= fks
    for campo, valor in (("versao", "0"), ("rascunho_rev", "-1"), ("finais", "'{}'::jsonb"),
                         ("rascunho", "'[]'::jsonb"), ("publicado_por", "999999")):
        with pytest.raises(IntegrityError):
            sql(dono, f"update formularios set {campo} = {valor} where id = :f", f=f["id"])
    conta = a["conta"]["id"]
    with pytest.raises(IntegrityError):  # imagem de conteúdo sempre aponta para o formulário
        _imagem(dono, conta, "conteudo_formulario", None, "a" * 43)
    with pytest.raises(IntegrityError):  # logo da conta nunca
        _imagem(dono, conta, "logo_conta", f["id"], "a" * 43)
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (1024 * 1024 - 8)
    _imagem(dono, conta, "conteudo_formulario", f["id"], "b" * 43, grande)  # até 1 MB
    with pytest.raises(IntegrityError):  # logo continua até 300 KB
        _imagem(dono, conta, "logo_formulario", f["id"], "c" * 43, grande)
    _imagem(dono, conta, "logo_formulario", f["id"], "d" * 43)
    _imagem(dono, conta, "logo_formulario", f["id"], "e" * 43)  # mais de um logo (o do rascunho)
    with pytest.raises(IntegrityError):
        sql(dono, "insert into respostas (conta_id, formulario_id, canal, formulario_versao) "
                  "values (:c, :f, 'link', 0)", c=conta, f=f["id"])
    # a FK do usuário zera quando o usuário sai
    sql(dono, "update formularios set rascunho_por = :u, publicado_por = :u where id = :f",
        u=a["usuario"]["id"], f=f["id"])
    assert sql(dono, "select rascunho_por, publicado_por from formularios where id = :f", f=f["id"]) == [
        (a["usuario"]["id"], a["usuario"]["id"])]


def test_converte_a_condicao_antiga_e_desce_e_sobe(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h, conta = a["h"], a["conta"]["id"]
    csat = form_padrao(client, h, "csat")
    nota = csat["perguntas"][0]["id"]
    # um formulário com o que a 0025 não conhece: pular, conteúdo, finais, rascunho e imagens de conteúdo
    novo = client.post(f"{API}/formularios", headers=h, json={"nome": "Novo", "perguntas": [
        {"id": "p_n", "tipo": "nps", "titulo": "N", "obrigatoria": True,
         "logica": {"pular": [{"se": {"juncao": "todas", "condicoes": [{"fonte": "p_n", "op": "menor", "valor": 3}]},
                               "para": "fim"}]}},
        {"id": "c_1", "tipo": "conteudo", "html": "<p>Bloco</p>"},
        {"id": "p_a", "tipo": "comentario", "titulo": "A", "logica": {"mostrar_se": {"juncao": "todas", "condicoes": [
            {"fonte": "p_n", "op": "maior_igual", "valor": 9}]}}},
        {"id": "p_b", "tipo": "comentario", "titulo": "B", "logica": {"mostrar_se": {
            "juncao": "qualquer",
            "condicoes": [{"fonte": "p_n", "op": "igual", "valor": 1}, {"fonte": "p_n", "op": "igual", "valor": 2}]}}},
    ], "finais": [{"nome": "F", "titulo": "T"}]}).json()
    client.put(f"{API}/formularios/{novo['id']}/rascunho", headers=h,
               json={"rev": 0, "perguntas": novo["perguntas"][:1]})
    _imagem(dono, conta, "conteudo_formulario", novo["id"], "f" * 43)
    _imagem(dono, conta, "logo_formulario", novo["id"], "g" * 43)
    _imagem(dono, conta, "logo_formulario", novo["id"], "h" * 43)
    cfg = _alembic()
    command.downgrade(cfg, "0025_planos_5k")
    try:
        assert not COLUNAS & _colunas(dono, "formularios")
        assert "formulario_versao" not in _colunas(dono, "respostas")
        entrega = _perguntas(dono, csat["id"])
        assert entrega[2]["condicao"] == {"tipo": "grupo", "grupos": ["insatisfeito", "neutro"]}
        assert all("logica" not in p for p in entrega)
        volta = _perguntas(dono, novo["id"])
        assert [p["id"] for p in volta] == ["p_n", "p_a", "p_b"]  # o bloco de conteúdo sai
        assert "logica" not in volta[0] and "condicao" not in volta[0]  # pular sai
        assert volta[1]["condicao"] == {"tipo": "nota", "operador": ">=", "valor": 9}
        assert "condicao" not in volta[2] and "logica" not in volta[2]  # lógica que a 0025 não representa sai
        assert sql(dono, "select uso, chave from imagens where formulario_id = :f", f=novo["id"]) == [
            ("logo_formulario", "h" * 43)]  # um logo por formulário (o mais novo); conteúdo sai
        # dado antigo para a subida converter (publicado com `condicao`)
        antigo = [{"id": "p_x", "tipo": "texto_curto", "titulo": "Nome", "condicao": {"tipo": "grupo",
                                                                                     "grupos": ["detrator"]}},
                  {"id": "p_1", "tipo": "nps", "titulo": "N", "obrigatoria": True},
                  {"id": "p_2", "tipo": "comentario", "titulo": "C", "condicao": {"tipo": "nota", "operador": "<=",
                                                                                 "valor": 6}},
                  {"id": "p_3", "tipo": "comentario", "titulo": "D", "condicao": {"tipo": "grupo",
                                                                                 "grupos": ["promotor"]}}]
        sql(dono, "update formularios set perguntas = cast(:p as jsonb), atualizado_em = '2026-01-02 10:00-03' "
                  "where id = :f", p=json.dumps(antigo), f=novo["id"])
    finally:
        command.upgrade(cfg, "head")
    convertido = _perguntas(dono, novo["id"])
    assert all("condicao" not in p for p in convertido)
    assert "logica" not in convertido[0]  # condição antes da nota principal (que nunca valeu) sai
    assert convertido[2]["logica"] == {"pular": [], "mostrar_se": {"juncao": "todas", "condicoes": [
        {"fonte": "p_1", "op": "menor_igual", "valor": 6}]}}
    assert convertido[3]["logica"]["mostrar_se"]["condicoes"][0] == {"fonte": "p_1", "op": "grupo_e",
                                                                     "valor": ["promotor"]}
    linha = sql(dono, "select versao, rascunho, rascunho_rev, finais, publicado_em = atualizado_em "
                      "from formularios where id = :f", f=novo["id"])
    assert linha == [(1, None, 0, [], True)]
    # a aplicação usa tudo de novo (o papel da aplicação tem acesso às colunas novas)
    g = client.get(f"{API}/formularios/{novo['id']}", headers=h)
    assert g.status_code == 200 and g.json()["versao"] == 1 and g.json()["perguntas"][2]["logica"]
    r = client.put(f"{API}/formularios/{novo['id']}/rascunho", headers=h, json={"rev": 0, "perguntas": convertido})
    assert r.status_code == 200 and r.json()["rev"] == 1 and r.json()["problemas"] == {}
    assert client.get(f"{API}/formularios/{csat['id']}", headers=h).json()["perguntas"][2]["logica"]["mostrar_se"] == {
        "juncao": "todas", "condicoes": [{"fonte": nota, "op": "grupo_e", "valor": ["insatisfeito", "neutro"]}]}
