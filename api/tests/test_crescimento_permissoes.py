"""Etapa 5c: permissões por perfil em todas as rotas do Crescimento (padrão: gestor com ver e tratar, consulta só com
ver; alterar pede ver e tratar; CSV pede também `painel.exportar`; a configuração é lida com `crescimento.ver` ou
`configuracoes.gerenciar` e alterada só com `configuracoes.gerenciar`) e o catálogo de permissões."""
import pytest
from util import API, conta_pronta, criar_contato, criar_empresa, membro, sql

from toqqi.core.permissoes import PADRAO, catalogo_json


@pytest.fixture
def perfis(client):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    h = a["h"]
    e = criar_empresa(client, h, "Mercado")
    c = criar_contato(client, h, nome="Bruno", email="bruno@mercado.com.br", empresa_id=e["id"])
    return {"admin": a, "gestor": membro(client, h, "gil@alfa.com.br", "gestor"),
            "consulta": membro(client, h, "caio@alfa.com.br", "consulta"), "empresa": e, "contato": c}


def _rotas(client, perfis) -> list[tuple]:
    """(método, caminho, corpo, status com permissão) — itens novos a cada chamada (a exclusão consome um)."""
    h = perfis["admin"]["h"]
    i = client.post(f"{API}/crescimento/indicacoes", headers=h, json={"nome": "João", "email": "joao@x.com.br"}).json()
    o = client.post(f"{API}/crescimento/ofertas", headers=h, json={"empresa_id": perfis["empresa"]["id"],
                                                                     "lista": "promotores", "texto": "Oi"}).json()
    return [
        ("get", "/crescimento/indicacoes", None, 200),
        ("get", "/crescimento/indicacoes.csv", None, 200),
        ("post", "/crescimento/indicacoes", {"nome": "Maria", "email": "maria@x.com.br"}, 201),
        ("patch", f"/crescimento/indicacoes/{i['id']}", {"situacao": "em_contato"}, 200),
        ("delete", f"/crescimento/indicacoes/{i['id']}", None, 204),
        ("get", "/crescimento/oportunidades", None, 200),
        ("get", "/crescimento/oportunidades.csv", None, 200),
        ("post", "/crescimento/ofertas", {"empresa_id": perfis["empresa"]["id"], "lista": "promotores",
                                          "texto": "Oi"}, 201),
        ("patch", f"/crescimento/ofertas/{o['id']}", {"resultado": "recusou"}, 200),
        ("get", "/crescimento/resumo", None, 200),
        ("get", "/crescimento/configuracao", None, 200),
        ("put", "/crescimento/configuracao", {"indicacoes_ativas": True}, 200),
    ]


# rotas que cada perfil padrão NÃO pode usar
PROIBIDAS = {
    "admin": set(),
    "gestor": {("put", "/crescimento/configuracao")},
    "consulta": {("get", "/crescimento/indicacoes.csv"), ("post", "/crescimento/indicacoes"),
                 ("patch", "/crescimento/indicacoes/"), ("delete", "/crescimento/indicacoes/"),
                 ("get", "/crescimento/oportunidades.csv"), ("post", "/crescimento/ofertas"),
                 ("patch", "/crescimento/ofertas/"), ("put", "/crescimento/configuracao")},
}


def _proibida(perfil: str, metodo: str, caminho: str) -> bool:
    base = caminho.rstrip("0123456789")
    return (metodo, base) in PROIBIDAS[perfil]


@pytest.mark.parametrize("perfil", ["admin", "gestor", "consulta"])
def test_permissoes_por_perfil_em_todas_as_rotas(client, perfis, perfil):
    h = perfis[perfil]["h"]
    for metodo, caminho, corpo, esperado in _rotas(client, perfis):
        kw = {"json": corpo} if corpo is not None else {}
        r = getattr(client, metodo)(f"{API}{caminho}", headers=h, **kw)
        if _proibida(perfil, metodo, caminho):
            assert r.status_code == 403, (perfil, metodo, caminho, r.text)
            assert r.json()["erro"]["codigo"] == "sem_permissao"
        else:
            assert r.status_code == esperado, (perfil, metodo, caminho, r.text)


def test_sem_login_e_sem_ver(client, perfis, dono):
    for metodo, caminho, corpo, _ in _rotas(client, perfis):
        kw = {"json": corpo} if corpo is not None else {}
        assert getattr(client, metodo)(f"{API}{caminho}", **kw).status_code == 401, (metodo, caminho)
    # consulta sem "ver" (tirado pelo administrador): nada do Crescimento, nem a configuração
    sql(dono, "delete from perfil_permissoes where perfil = 'consulta' and permissao = 'crescimento.ver'")
    h = perfis["consulta"]["h"]
    for caminho in ("indicacoes", "oportunidades", "resumo", "configuracao"):
        assert client.get(f"{API}/crescimento/{caminho}", headers=h).status_code == 403, caminho
    # gestor com "tratar" e sem "ver": nem lista nem trata (as rotas que alteram devolvem o registro inteiro, e
    # "tratar" sozinho leria tudo percorrendo os ids)
    sql(dono, "delete from perfil_permissoes where perfil = 'gestor' and permissao = 'crescimento.ver'")
    g = perfis["gestor"]["h"]
    for metodo, caminho, corpo, _ in _rotas(client, perfis):
        kw = {"json": corpo} if corpo is not None else {}
        r = getattr(client, metodo)(f"{API}{caminho}", headers=g, **kw)
        assert r.status_code == 403 and r.json()["erro"]["codigo"] == "sem_permissao", (metodo, caminho, r.text)
    # só ficou o que `_rotas` criou como administrador (uma indicação e uma oferta a cada chamada), sem mudanças
    assert sql(dono, "select nome, situacao from indicacoes") == [("João", "nova")] * 2
    assert sql(dono, "select resultado from ofertas") == [(None,)] * 2


def test_catalogo_e_padroes(client, perfis):
    grupo = [x for x in catalogo_json() if x["grupo"] == "Crescimento"]
    assert grupo == [
        {"chave": "crescimento.ver", "rotulo": "Ver indicações e oportunidades", "grupo": "Crescimento",
         "somente_admin": False},
        {"chave": "crescimento.tratar", "rotulo": "Tratar indicações e registrar ofertas", "grupo": "Crescimento",
         "somente_admin": False},
    ]
    assert {"crescimento.ver", "crescimento.tratar"} <= set(PADRAO["gestor"])
    assert "crescimento.ver" in PADRAO["consulta"] and "crescimento.tratar" not in PADRAO["consulta"]
    r = client.get(f"{API}/equipe/permissoes", headers=perfis["admin"]["h"]).json()
    assert [x["chave"] for x in r["catalogo"] if x["grupo"] == "Crescimento"] == ["crescimento.ver",
                                                                                  "crescimento.tratar"]
    assert {"crescimento.ver", "crescimento.tratar"} <= set(perfis["gestor"]["permissoes"])  # no login
    assert "crescimento.tratar" not in perfis["consulta"]["permissoes"]
