"""Etapa 5j, conector do Omie (o Omie é falso: as funções de `conectores.omie` são trocadas). Conectar (chaves
conferidas e cifradas, endereço do aviso estável ao reconectar), sincronizar (cliente → empresa + contato, inativo e
sem contato ficam de fora, sem duplicar) e o aviso de pedido faturado (pesquisa uma vez por pedido; aviso de outro
aplicativo, tópico fora da lista e segredo errado não fazem nada; cliente ainda não sincronizado é consultado)."""
import pytest
from util import API, conta_pronta, form_padrao, ligar_envios, membro, sql

from toqqi.core.email import caixa_memoria
from toqqi.modulos.conectores import omie

CHAVES = {"app_key": "1234567890123", "app_secret": "segredo-do-app-omie-abc"}
CLIENTES = [
    {"codigo_cliente_omie": 101, "razao_social": "Mercado Azul Ltda", "nome_fantasia": "Mercado Azul",
     "cnpj_cpf": "11.222.333/0001-81", "email": "compras@azul.com.br; outro@azul.com.br", "contato": "Ana Azul",
     "inativo": "N"},
    {"codigo_cliente_omie": 102, "razao_social": "Padaria Sol", "telefone1_ddd": "11", "telefone1_numero": "98765-4321",
     "inativo": "N"},
    {"codigo_cliente_omie": 103, "razao_social": "Antiga SA", "email": "x@antiga.com.br", "inativo": "S"},
    {"codigo_cliente_omie": 104, "razao_social": "Sem Contato Ltda", "inativo": "N"},
]


@pytest.fixture
def falso(monkeypatch):
    estado = {"ok": True, "consultas": []}

    def conferir(chaves):
        if not estado["ok"]:
            raise omie.ErroOmie("O Omie recusou as chaves.")

    def cliente(chaves, codigo):
        estado["consultas"].append(codigo)
        return {"codigo_cliente_omie": int(codigo), "nome_fantasia": "Cliente Novo", "email": "novo@cliente.com.br"}

    monkeypatch.setattr(omie, "conferir", conferir)
    monkeypatch.setattr(omie, "clientes", lambda chaves, maximo: iter(CLIENTES))
    monkeypatch.setattr(omie, "cliente", cliente)
    return estado


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _conectar(client, h, **corpo):
    return client.put(f"{API}/integracoes/conectores/omie", headers=h, json={**CHAVES, **corpo})


def test_conectar_e_endereco_estavel(client, dono, admin, falso):
    h = admin["h"]
    r = _conectar(client, h)
    assert r.status_code == 200, r.text
    url = r.json()["url_aviso"]
    assert "/api/v1/publico/conectores/omie/" in url and "VendaProduto.Faturada" in r.json()["eventos"]
    (cifrado,), = sql(dono, "select token_cifrado from conectores where provedor = 'omie'")
    assert CHAVES["app_secret"] not in cifrado
    assert _conectar(client, h).json()["url_aviso"] == url  # reconectar não troca o endereço já cadastrado no Omie
    falso["ok"] = False
    assert _conectar(client, h).status_code == 502
    gestor = membro(client, h, "gil@alfa.com.br", perfil="gestor")
    assert _conectar(client, gestor["h"]).status_code == 403


def test_sincronizar(client, dono, admin, falso):
    h = admin["h"]
    _conectar(client, h)
    r = client.post(f"{API}/integracoes/conectores/omie/sincronizar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"empresas_novas": 3, "empresas_existentes": 0, "contatos_novos": 2, "contatos_existentes": 0,
                        "sem_email_ou_telefone": 1, "inativos": 1, "limite_do_plano": False, "cortado": False}
    linhas = sql(dono, "select c.nome, c.email, c.telefone, e.nome, e.documento from contatos c "
                       "join empresas e on e.id = c.empresa_id order by c.nome")
    assert [tuple(x)[:2] + (tuple(x)[3], tuple(x)[4]) for x in linhas] == [
        ("Ana Azul", "compras@azul.com.br", "Mercado Azul", "11222333000181"),
        ("Padaria Sol", None, "Padaria Sol", None)]
    r = client.post(f"{API}/integracoes/conectores/omie/sincronizar", headers=h).json()
    assert (r["empresas_novas"], r["contatos_novos"], r["contatos_existentes"]) == (0, 0, 2)


def test_pedido_faturado(client, dono, admin, falso):
    h = admin["h"]
    form_padrao(client, h)
    ligar_envios(client, h)
    url = _conectar(client, h).json()["url_aviso"]
    caminho = "/api/v1" + url.split("/api/v1", 1)[1]
    client.post(f"{API}/integracoes/conectores/omie/sincronizar", headers=h)
    aviso = {"topic": "VendaProduto.Faturada", "appKey": CHAVES["app_key"], "messageId": "m1",
             "event": {"idPedido": 555, "idCliente": 101}}
    antes = len(caixa_memoria)
    assert client.post(caminho, json=aviso).status_code == 200
    assert [m.para for m in caixa_memoria[antes:]] == ["compras@azul.com.br"]
    assert client.post(caminho, json=aviso).status_code == 200  # repetido: não manda de novo
    for outro in ({**aviso, "appKey": "outro"}, {**aviso, "topic": "Produto.Alterado"}, {"topic": "x"}):
        client.post(caminho, json=outro)
    client.post(f"{API}/publico/conectores/omie/errado", json=aviso)
    assert len(caixa_memoria) == antes + 1
    (ref,), = sql(dono, "select referencia from convites")
    assert ref == "Pedido 555"
    # cliente ainda não sincronizado: consulta no Omie e cria o contato
    novo = {**aviso, "event": {"idPedido": 556, "idCliente": 900}}
    client.post(caminho, json=novo)
    assert falso["consultas"] == ["900"] and caixa_memoria[-1].para == "novo@cliente.com.br"
    # desligado: nada
    client.patch(f"{API}/integracoes/conectores/omie", headers=h, json={"pesquisar_ao_faturar": False})
    client.post(caminho, json={**aviso, "event": {"idPedido": 557, "idCliente": 101}})
    assert caixa_memoria[-1].para == "novo@cliente.com.br" and len(caixa_memoria) == antes + 2


def test_desconectar(client, dono, admin, falso):
    h = admin["h"]
    _conectar(client, h)
    assert client.delete(f"{API}/integracoes/conectores/omie", headers=h).status_code == 204
    assert sql(dono, "select count(*) from conectores")[0][0] == 0
    assert client.get(f"{API}/integracoes/conectores", headers=h).json()["omie"] == {"conectado": False}
