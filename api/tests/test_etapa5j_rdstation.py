"""Etapa 5j, conector do RD Station CRM (o RD é falso: as funções de `conectores.rdstation` são trocadas). Conectar
(token conferido e cifrado, aviso cadastrado), sincronizar (cria empresas e contatos, não duplica, respeita o limite
do plano), o aviso de negócio ganho (manda a pesquisa uma vez por negociação e contato; segredo errado e negócio não
ganho não fazem nada) e desconectar."""
import pytest
from util import API, conta_pronta, definir_plano, encher_contatos, form_padrao, ligar_envios, membro, sql

from toqqi.core.email import caixa_memoria
from toqqi.modulos.conectores import rdstation

TOKEN = "tok_rd_0123456789abcdef"
ORGS = [{"id": "o1", "name": "Mercado Azul"}, {"_id": "o2", "name": "Padaria Sol"}]
PESSOAS = [
    {"id": "p1", "name": "Ana Azul", "emails": [{"email": "Ana@Azul.com.br"}], "organization_id": "o1"},
    {"id": "p2", "name": "Beto Sol", "phones": [{"phone": "(11) 98765-4321"}], "organization_id": "o2"},
    {"id": "p3", "name": "Sem Contato"},
]


@pytest.fixture
def rd(monkeypatch):
    estado = {"webhooks": [], "removidos": [], "token_ok": True}

    def conferir(token):
        if not estado["token_ok"]:
            raise rdstation.ErroRd("O RD Station CRM recusou o token.")

    def criar(token, url):
        estado["webhooks"].append(url)
        return f"wh{len(estado['webhooks'])}"

    monkeypatch.setattr(rdstation, "conferir_token", conferir)
    monkeypatch.setattr(rdstation, "criar_webhook", criar)
    monkeypatch.setattr(rdstation, "remover_webhook", lambda token, wid: estado["removidos"].append(wid))
    monkeypatch.setattr(rdstation, "empresas", lambda token, maximo: iter(ORGS))
    monkeypatch.setattr(rdstation, "contatos", lambda token, maximo: iter(PESSOAS))
    monkeypatch.setattr(rdstation, "negociacao", lambda token, deal_id: {
        "id": deal_id, "name": "Contrato anual", "win": True, "organization": {"id": "o1", "name": "Mercado Azul"},
        "contacts": [{"name": "Ana Azul", "emails": [{"email": "ana@azul.com.br"}]}]})
    return estado


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _conectar(client, h, **corpo):
    return client.put(f"{API}/integracoes/conectores/rdstation-crm", headers=h,
                      json={"token": TOKEN, "pesquisar_ao_ganhar": True, **corpo})


def _segredo(rd) -> str:
    return rd["webhooks"][-1].rsplit("/", 1)[-1]


def test_conectar_guarda_cifrado_e_cadastra_o_aviso(client, dono, admin, rd):
    h = admin["h"]
    assert client.get(f"{API}/integracoes/conectores", headers=h).json() == {"rdstation_crm": {"conectado": False}}
    r = _conectar(client, h)
    assert r.status_code == 200, r.text
    assert r.json()["conectado"] and r.json()["aviso_cadastrado"] and r.json()["pesquisar_ao_ganhar"]
    assert "/api/v1/publico/conectores/rdstation-crm/" in rd["webhooks"][0]
    (cifrado, hash_), = sql(dono, "select token_cifrado, segredo_hash from conectores")
    assert TOKEN not in cifrado and _segredo(rd) not in hash_
    # desligar a pesquisa remove o aviso no RD
    r = client.patch(f"{API}/integracoes/conectores/rdstation-crm", headers=h, json={"pesquisar_ao_ganhar": False})
    assert r.json()["aviso_cadastrado"] is False and rd["removidos"] == ["wh1"]
    rd["token_ok"] = False
    r = _conectar(client, h)
    assert r.status_code == 502 and r.json()["erro"]["codigo"] == "conector_falhou"


def test_so_administrador(client, admin, rd):
    gestor = membro(client, admin["h"], "gil@alfa.com.br", perfil="gestor")
    assert _conectar(client, gestor["h"]).status_code == 403


def test_sincronizar_cria_sem_duplicar(client, dono, admin, rd):
    h = admin["h"]
    _conectar(client, h)
    r = client.post(f"{API}/integracoes/conectores/rdstation-crm/sincronizar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() | {} == {"empresas_novas": 2, "empresas_existentes": 0, "contatos_novos": 2,
                             "contatos_existentes": 0, "sem_email_ou_telefone": 1, "limite_do_plano": False,
                             "cortado": False}
    linhas = sql(dono, "select c.nome, c.email, c.codigo_externo, e.nome from contatos c "
                       "left join empresas e on e.id = c.empresa_id order by c.nome")
    assert [tuple(x) for x in linhas] == [("Ana Azul", "ana@azul.com.br", "rd:p1", "Mercado Azul"),
                                         ("Beto Sol", None, "rd:p2", "Padaria Sol")]
    r = client.post(f"{API}/integracoes/conectores/rdstation-crm/sincronizar", headers=h).json()
    assert (r["empresas_novas"], r["contatos_novos"], r["contatos_existentes"]) == (0, 0, 2)
    ver = client.get(f"{API}/integracoes/conectores", headers=h).json()["rdstation_crm"]
    assert ver["sincronizado_em"] and ver["resumo"]["contatos_existentes"] == 2


def test_sincronizar_para_no_limite_do_plano(client, dono, admin, rd):
    h, cid = admin["h"], admin["conta"]["id"]
    _conectar(client, h)
    definir_plano(dono, cid, "essencial")
    limite = sql(dono, "select limite_contatos('essencial', 'ativa')")[0][0]
    encher_contatos(dono, cid, limite - 1)
    r = client.post(f"{API}/integracoes/conectores/rdstation-crm/sincronizar", headers=h).json()
    assert r["contatos_novos"] == 1 and r["limite_do_plano"] is True


def test_negocio_ganho_manda_a_pesquisa_uma_vez(client, dono, admin, rd):
    h = admin["h"]
    form_padrao(client, h)
    ligar_envios(client, h)
    _conectar(client, h)
    url = f"{API}/publico/conectores/rdstation-crm/{_segredo(rd)}"
    aviso = {"event_name": "crm_deal_updated", "document": {"id": "d9", "name": "Contrato anual", "win": True}}
    antes = len(caixa_memoria)
    assert client.post(url, json=aviso).status_code == 200
    para = [m.para for m in caixa_memoria[antes:]]
    assert para == ["ana@azul.com.br"]
    assert client.post(url, json=aviso).status_code == 200  # o RD repetiu: não manda de novo
    assert len(caixa_memoria) == antes + 1
    (evento, referencia), = sql(dono, "select evento, referencia from convites")
    assert (evento, referencia) == ("negocio_ganho", "Contrato anual")
    # não ganho, segredo errado e corpo estranho: nada
    assert client.post(url, json={"document": {"id": "d10", "win": False}}).status_code == 200
    assert client.post(f"{API}/publico/conectores/rdstation-crm/errado", json=aviso).status_code == 200
    assert client.post(url, content=b"nao-json", headers={"content-type": "application/json"}).status_code == 200
    assert len(caixa_memoria) == antes + 1


def test_desconectar(client, dono, admin, rd):
    h = admin["h"]
    _conectar(client, h)
    segredo = _segredo(rd)
    assert client.delete(f"{API}/integracoes/conectores/rdstation-crm", headers=h).status_code == 204
    assert rd["removidos"] == ["wh1"]
    assert sql(dono, "select count(*) from conectores")[0][0] == 0
    aviso = {"document": {"id": "d9", "win": True}}
    assert client.post(f"{API}/publico/conectores/rdstation-crm/{segredo}", json=aviso).status_code == 200
    eventos = {e for (e,) in sql(dono, "select evento from auditoria where conta_id = :c", c=admin["conta"]["id"])}
    assert {"conector_ligado", "conector_desligado"} <= eventos
