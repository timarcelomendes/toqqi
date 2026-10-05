"""Etapa 5h §1 (docs/api-etapa-5h.md): sua marca nas pesquisas. `GET /conta/marca` ({cor, tem_logo}, para quem vê o
Início), `PUT /conta/marca` (configuracoes.gerenciar: grava `config_envios.email_cor` e troca a cor dos formulários que
ainda estão na cor dos modelos), formulário novo nascendo com a cor da marca, auditoria e isolamento entre contas."""
import pytest
from util import API, conta_pronta, criar_form, formularios, membro, png, sql

from toqqi.modulos.conta.esquemas import MSG_COR

PERGUNTA = [{"tipo": "nps", "titulo": "De 0 a 10?", "obrigatoria": True}]


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _marca(client, h) -> dict:
    r = client.get(f"{API}/conta/marca", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _salvar(client, h, cor):
    return client.put(f"{API}/conta/marca", headers=h, json={"cor": cor})


def _cores(client, h) -> dict:
    return {nome: f["tema"]["cor"] for nome, f in formularios(client, h).items()}


def _eventos(dono, conta_id: int) -> list:
    return [x[0] for x in sql(dono, "select detalhe from auditoria where conta_id = :c and evento = 'marca_alterada' "
                                    "order by id", c=conta_id)]


def test_conta_nova_sem_cor_nem_logo_e_logo_enviado(client, admin):
    h = admin["h"]
    assert _marca(client, h) == {"cor": None, "tem_logo": False}
    r = client.put(f"{API}/conta/logo", headers=h, files={"arquivo": ("logo.png", png(7), "image/png")})
    assert r.status_code == 200, r.text
    assert _marca(client, h) == {"cor": None, "tem_logo": True}
    assert client.delete(f"{API}/conta/logo", headers=h).status_code == 204
    assert _marca(client, h)["tem_logo"] is False


def test_cor_troca_so_os_formularios_na_cor_dos_modelos(client, admin, dono):
    h, conta = admin["h"], admin["conta"]["id"]
    # a conta nasce com "Pesquisa NPS" e "Satisfação pós-entrega" na cor dos modelos (#1f6feb)
    assert set(_cores(client, h).values()) == {"#1f6feb"}
    propria = criar_form(client, h, PERGUNTA, nome="Cor própria", tema={"cor": "#123456"})
    maiusculas = criar_form(client, h, PERGUNTA, nome="Maiúsculas")
    sql(dono, "update formularios set tema = tema || '{\"cor\": \"#1F6FEB\"}'::jsonb where id = :f", f=maiusculas["id"])
    arquivado = criar_form(client, h, PERGUNTA, nome="Arquivado")
    sql(dono, "update formularios set arquivado = true where id = :f", f=arquivado["id"])

    r = _salvar(client, h, " #d63a18 ")
    assert r.status_code == 200, r.text
    assert r.json() == {"cor": "#D63A18", "formularios_atualizados": 3}  # os 2 da conta nova e o de maiúsculas
    assert _cores(client, h) == {"Pesquisa NPS": "#d63a18", "Satisfação pós-entrega": "#d63a18",
                                 "Maiúsculas": "#d63a18", "Cor própria": "#123456"}
    assert propria["id"] != arquivado["id"]
    assert sql(dono, "select tema->>'cor' from formularios where id = :f", f=arquivado["id"]) == [("#1f6feb",)]
    # o resto do tema fica como estava
    nps = next(f for f in formularios(client, h).values() if f["padrao_nps"])
    assert nps["tema"]["titulo_abertura"] == "Olá, {nome}!" and nps["tema"]["modo"] == "uma_por_vez"
    # a cor dos e-mails (Configurações › Envios) é a da marca
    assert sql(dono, "select email_cor from config_envios where conta_id = :c", c=conta) == [("#D63A18",)]
    assert client.get(f"{API}/envios/configuracao", headers=h).json()["email_cor"] == "#D63A18"
    assert _marca(client, h) == {"cor": "#D63A18", "tem_logo": False}
    assert _eventos(dono, conta) == [{"cor": "#D63A18", "formularios_atualizados": 3}]
    # a mesma cor de novo: nada muda e não vai outra auditoria
    assert _salvar(client, h, "#D63A18").json() == {"cor": "#D63A18", "formularios_atualizados": 0}
    assert len(_eventos(dono, conta)) == 1
    # outra cor: os formulários que já estão na cor da marca não são mais "da cor dos modelos"
    assert _salvar(client, h, "#047857").json() == {"cor": "#047857", "formularios_atualizados": 0}
    assert set(_cores(client, h).values()) == {"#d63a18", "#123456"}
    assert _eventos(dono, conta)[-1] == {"cor": "#047857", "formularios_atualizados": 0}
    ev = next(i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"] if i["evento"] == "marca_alterada")
    assert (ev["rotulo"], ev["grupo"]) == ("Cor da marca nas pesquisas alterada", "configuracoes")


def test_formulario_novo_nasce_com_a_cor_da_marca(client, admin):
    h = admin["h"]
    antes = client.post(f"{API}/formularios", headers=h, json={"nome": "Antes", "modelo": "nps_simples"}).json()
    assert antes["tema"]["cor"] == "#1f6feb"  # sem marca, a cor dos modelos
    assert _salvar(client, h, "#7C3AED").status_code == 200
    novo = client.post(f"{API}/formularios", headers=h, json={"nome": "Do modelo", "modelo": "pos_entrega"})
    assert novo.status_code == 201 and novo.json()["tema"]["cor"] == "#7c3aed"
    assert novo.json()["tema"]["titulo_abertura"] == "Olá, {nome}!"  # o resto do tema do modelo
    assert criar_form(client, h, PERGUNTA, nome="Sem modelo")["tema"]["cor"] == "#7c3aed"
    # cor pedida vale mais que a da marca (mesmo a dos modelos)
    assert criar_form(client, h, PERGUNTA, nome="Azul", tema={"cor": "#1F6FEB"})["tema"]["cor"] == "#1f6feb"
    assert criar_form(client, h, PERGUNTA, nome="Vinho", tema={"cor": "#7f1d1d"})["tema"]["cor"] == "#7f1d1d"
    # a cópia fica com a cor do original
    copia = client.post(f"{API}/formularios/{antes['id']}/duplicar", headers=h).json()
    assert copia["tema"]["cor"] == "#7c3aed"  # o "Antes" estava na cor dos modelos: passou para a da marca
    azul = next(f for f in formularios(client, h).values() if f["nome"] == "Azul")
    assert client.post(f"{API}/formularios/{azul['id']}/duplicar", headers=h).json()["tema"]["cor"] == "#1f6feb"
    # a prévia dos modelos mostra a cor que o formulário vai ter
    assert {m["tema"]["cor"] for m in client.get(f"{API}/formularios/modelos", headers=h).json()} == {"#7c3aed"}


def test_permissoes(client, admin):
    h = admin["h"]
    for perfil in ("gestor", "consulta"):
        m = membro(client, h, f"{perfil}@alfa.com.br", perfil)
        assert _marca(client, m["h"]) == {"cor": None, "tem_logo": False}  # quem vê o Início lê
        assert _salvar(client, m["h"], "#000000").status_code == 403
    assert client.get(f"{API}/conta/marca").status_code == 401
    assert _marca(client, h)["cor"] is None


@pytest.mark.parametrize("cor", ["D63A18", "#D63A1", "#GGGGGG", "#D63A18AA", "", "   ", None, 123, "azul",
                                 "rgb(1,2,3)"])
def test_cor_invalida(client, admin, dono, cor):
    h = admin["h"]
    r = _salvar(client, h, cor)
    assert r.status_code == 422, r.text
    assert r.json()["erro"]["campos"] == {"cor": MSG_COR}
    assert sql(dono, "select count(*) from config_envios where email_cor is not null")[0][0] == 0
    assert set(_cores(client, h).values()) == {"#1f6feb"}


def test_sem_cor_no_corpo(client, admin):
    r = client.put(f"{API}/conta/marca", headers=admin["h"], json={})
    assert r.status_code == 422 and "cor" in r.json()["erro"]["campos"]


def test_uma_conta_nao_mexe_na_outra(client, admin, dono):
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert _salvar(client, admin["h"], "#0E7490").json()["formularios_atualizados"] == 2
    assert set(_cores(client, b["h"]).values()) == {"#1f6feb"}
    assert _marca(client, b["h"]) == {"cor": None, "tem_logo": False}
    assert _salvar(client, b["h"], "#BE185D").json() == {"cor": "#BE185D", "formularios_atualizados": 2}
    assert set(_cores(client, admin["h"]).values()) == {"#0e7490"}
    assert _marca(client, admin["h"])["cor"] == "#0E7490"
    cores = dict(sql(dono, "select conta_id, email_cor from config_envios"))
    assert cores == {admin["conta"]["id"]: "#0E7490", b["conta"]["id"]: "#BE185D"}
