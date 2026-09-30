"""Empresas e contatos: validações, unicidade, limite do plano, situação e permissões."""
import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_empresa,
    definir_plano,
    encher_contatos,
    form_padrao,
    link_pesquisa,
    membro,
)

CNPJ_OK = "11.222.333/0001-81"
CPF_OK = "529.982.247-25"


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


# ---- empresas ---------------------------------------------------------------

def test_empresa_documento_validado_e_so_digitos(client, admin):
    h = admin["h"]
    e = criar_empresa(client, h, "Atacado Norte", documento=CNPJ_OK, valor_mensal=1250.5,
                      cliente_desde="2024-03-01", codigo_externo="ERP-77")
    assert e["documento"] == "11222333000181"
    assert e["valor_mensal"] == 1250.5 and e["cliente_desde"] == "2024-03-01"
    assert e["ativa"] is True and e["contatos"] == 0
    assert criar_empresa(client, h, "Pessoa Física", documento=CPF_OK)["documento"] == "52998224725"
    for doc in ["11.222.333/0001-80", "111.111.111-11", "123"]:
        r = client.post(f"{API}/empresas", headers=h, json={"nome": f"X {doc}", "documento": doc})
        assert r.status_code == 422 and "documento" in r.json()["erro"]["campos"], doc


def test_empresa_nome_unico_e_filtros(client, admin):
    h = admin["h"]
    criar_empresa(client, h, "Atacado Norte")
    r = client.post(f"{API}/empresas", headers=h, json={"nome": "ATACADO NORTE"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "nome_em_uso"
    criar_empresa(client, h, "Mercearia Sul", ativa=False)
    lista = client.get(f"{API}/empresas?busca=norte", headers=h).json()
    assert lista["total"] == 1 and lista["itens"][0]["nome"] == "Atacado Norte"
    assert client.get(f"{API}/empresas?ativa=false", headers=h).json()["total"] == 1
    assert client.get(f"{API}/empresas?ativa=todas&por_pagina=1", headers=h).json()["por_pagina"] == 1


def test_empresa_referencia_inexistente(client, admin):
    r = client.post(f"{API}/empresas", headers=admin["h"], json={"nome": "X", "grupo_id": 9999})
    assert r.status_code == 422 and "grupo_id" in r.json()["erro"]["campos"]


def test_excluir_empresa_exige_admin_e_contatos_ficam_sem_empresa(client, admin):
    h = admin["h"]
    e = criar_empresa(client, h, "Atacado Norte")
    c = criar_contato(client, h, empresa_id=e["id"])
    assert client.get(f"{API}/empresas/{e['id']}", headers=h).json()["contatos"] == 1
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    r = client.delete(f"{API}/empresas/{e['id']}", headers=gestor["h"])
    assert r.status_code == 403
    assert client.delete(f"{API}/empresas/{e['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["empresa"] is None
    eventos = [i["evento"] for i in client.get(f"{API}/auditoria", headers=h).json()["itens"]]
    assert "empresa_excluida" in eventos


# ---- contatos ---------------------------------------------------------------

def test_criar_contato_formato(client, admin):
    h = admin["h"]
    e = criar_empresa(client, h, "Atacado Norte")
    perfil = client.get(f"{API}/cadastros/perfis", headers=h).json()[0]
    c = criar_contato(client, h, nome="Carla Dias", email="Carla@Cliente.com.br", telefone="(11) 98765-4321",
                      empresa_id=e["id"], perfil_id=perfil["id"], codigo_externo="C-1")
    assert c["email"] == "carla@cliente.com.br"
    assert c["telefone"] == "5511987654321"
    assert len(c["codigo"]) == 9 and c["codigo"].isdigit()
    assert c["empresa"] == {"id": e["id"], "nome": "Atacado Norte"}
    assert c["perfil"]["nome"] == "Decisor"
    assert c["situacao"] == "nunca_enviado" and c["ultima_nota"] is None
    assert c["ultimo_envio"] is None and c["proximo_envio"] is None


@pytest.mark.parametrize("entrada,esperado", [
    ("1133334444", "551133334444"),
    ("+55 (11) 3333-4444", "551133334444"),
    ("11 91234-5678", "5511912345678"),
    ("5511912345678", "5511912345678"),
])
def test_telefone_normalizado(client, admin, entrada, esperado):
    c = criar_contato(client, admin["h"], telefone=entrada)
    assert c["telefone"] == esperado


@pytest.mark.parametrize("tel", ["1234", "0113333444", "12345678901234"])
def test_telefone_invalido(client, admin, tel):
    r = client.post(f"{API}/contatos", headers=admin["h"], json={"nome": "X", "telefone": tel})
    assert r.status_code == 422 and "telefone" in r.json()["erro"]["campos"]


def test_email_ou_telefone_obrigatorio(client, admin):
    r = client.post(f"{API}/contatos", headers=admin["h"], json={"nome": "Sem canal"})
    assert r.status_code == 422
    c = criar_contato(client, admin["h"], telefone="11987654321")
    r = client.patch(f"{API}/contatos/{c['id']}", headers=admin["h"], json={"telefone": None})
    assert r.status_code == 422


def test_email_unico_na_conta_mas_livre_entre_contas(client, admin):
    criar_contato(client, admin["h"], email="joao@cliente.com.br")
    r = client.post(f"{API}/contatos", headers=admin["h"], json={"nome": "Outro", "email": "JOAO@cliente.com.br"})
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "email_em_uso"
    outra = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    criar_contato(client, outra["h"], email="joao@cliente.com.br")


def test_limite_do_plano_via_api(client, admin, dono):
    h = admin["h"]
    conta_id = admin["conta"]["id"]
    definir_plano(dono, conta_id, "essencial")
    encher_contatos(dono, conta_id, 299)
    ultimo = criar_contato(client, h)  # 300º cabe
    r = client.post(f"{API}/contatos", headers=h, json={"nome": "Excedente", "email": "x@y.com.br"})
    assert r.status_code == 402
    assert r.json()["erro"] == {"codigo": "limite_do_plano",
                                "mensagem": "Seu plano permite até 300 contatos ativos.", "campos": {}}
    # contato inativo não conta
    assert client.post(f"{API}/contatos", headers=h,
                       json={"nome": "Inativo", "email": "i@y.com.br", "ativo": False}).status_code == 201
    # editar contato já ativo continua permitido
    r = client.patch(f"{API}/contatos/{ultimo['id']}", headers=h, json={"nome": "Nome Novo", "ativo": True})
    assert r.status_code == 200
    # desativar libera vaga, e reativar volta a esbarrar no limite
    client.patch(f"{API}/contatos/{ultimo['id']}", headers=h, json={"ativo": False})
    assert client.post(f"{API}/contatos", headers=h, json={"nome": "Cabe", "email": "c@y.com.br"}).status_code == 201
    r = client.patch(f"{API}/contatos/{ultimo['id']}", headers=h, json={"ativo": True})
    assert r.status_code == 402
    # plano empresa e cortesia: ilimitado
    definir_plano(dono, conta_id, "empresa")
    assert client.patch(f"{API}/contatos/{ultimo['id']}", headers=h, json={"ativo": True}).status_code == 200
    definir_plano(dono, conta_id, "essencial", "cortesia")
    assert client.post(f"{API}/contatos", headers=h, json={"nome": "Z", "email": "z@y.com.br"}).status_code == 201


def test_limite_garantido_no_banco(client, admin, dono):
    import sqlalchemy

    conta_id = admin["conta"]["id"]
    definir_plano(dono, conta_id, "essencial")
    encher_contatos(dono, conta_id, 300)
    with pytest.raises(sqlalchemy.exc.DatabaseError, match="Seu plano permite até 300"):
        encher_contatos(dono, conta_id, 1)


def test_situacao_historico_e_exclusao(client, admin):
    h = admin["h"]
    c = criar_contato(client, h, nome="Paula Lima")
    token = link_pesquisa(client, h, c["id"])
    nps = form_padrao(client, h, "nps")
    r = client.post(f"{API}/publico/convites/{token}/responder",
                    json={"respostas": {nps["perguntas"][0]["id"]: 9}})
    assert r.status_code == 201, r.text
    d = client.get(f"{API}/contatos/{c['id']}", headers=h).json()
    assert d["situacao"] == "respondeu" and d["ultima_nota"] == 9
    assert d["historico"][0]["tipo"] == "resposta" and d["historico"][0]["grupo"] == "promotor"
    assert d["historico"][0]["formulario"]["nome"] == "Pesquisa NPS"
    client.patch(f"{API}/contatos/{c['id']}", headers=h, json={"ativo": False})
    assert client.get(f"{API}/contatos/{c['id']}", headers=h).json()["situacao"] == "inativo"
    # excluir apaga as respostas dele
    assert client.delete(f"{API}/contatos/{c['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/formularios/{nps['id']}/respostas", headers=h).json()["total"] == 0


def test_filtros_da_lista(client, admin):
    h = admin["h"]
    g = client.post(f"{API}/cadastros/grupos", headers=h, json={"nome": "Rede"}).json()
    e = criar_empresa(client, h, "Atacado Norte", grupo_id=g["id"])
    criar_contato(client, h, nome="Ana Norte", empresa_id=e["id"])
    criar_contato(client, h, nome="Bruno Sul", telefone="11955554444", email=None)
    criar_contato(client, h, nome="Célia", ativo=False)
    assert client.get(f"{API}/contatos", headers=h).json()["total"] == 3
    assert client.get(f"{API}/contatos?ativo=true", headers=h).json()["total"] == 2
    assert client.get(f"{API}/contatos?grupo_id={g['id']}", headers=h).json()["itens"][0]["nome"] == "Ana Norte"
    assert client.get(f"{API}/contatos?busca=atacado", headers=h).json()["total"] == 1
    assert client.get(f"{API}/contatos?busca=5555-4444", headers=h).json()["itens"][0]["nome"] == "Bruno Sul"


def test_link_pesquisa(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    r = client.post(f"{API}/contatos/{c['id']}/link-pesquisa", headers=h,
                    json={"contexto": {"pedido": "123", "rota": "Sul"}, "assunto": "a entrega de ontem"})
    assert r.status_code == 201
    d = r.json()
    assert d["link"] == f"http://app.teste/r/{d['token']}" and d["expira_em"] is None
    aberto = client.get(f"{API}/publico/convites/{d['token']}").json()
    assert aberto["variaveis"]["assunto"] == "a entrega de ontem"
    csat = form_padrao(client, h, "csat")
    r = client.post(f"{API}/contatos/{c['id']}/link-pesquisa", headers=h, json={"formulario_id": csat["id"]})
    assert r.status_code == 201
    r = client.post(f"{API}/contatos/{c['id']}/link-pesquisa", headers=h, json={"formulario_id": 99999})
    assert r.status_code == 422


def test_permissoes_contatos(client, admin):
    h = admin["h"]
    c = criar_contato(client, h)
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    assert client.get(f"{API}/contatos", headers=consulta["h"]).status_code == 200
    assert client.patch(f"{API}/contatos/{c['id']}", headers=consulta["h"], json={"nome": "X"}).status_code == 403
    assert client.delete(f"{API}/contatos/{c['id']}", headers=consulta["h"]).status_code == 403
    assert client.post(f"{API}/contatos/{c['id']}/link-pesquisa", headers=consulta["h"], json={}).status_code == 403
    assert client.post(f"{API}/empresas", headers=consulta["h"], json={"nome": "X"}).status_code == 403
    assert client.patch(f"{API}/contatos/{c['id']}", headers=gestor["h"], json={"nome": "Y"}).status_code == 200
    assert client.post(f"{API}/empresas", headers=gestor["h"], json={"nome": "X"}).status_code == 201
