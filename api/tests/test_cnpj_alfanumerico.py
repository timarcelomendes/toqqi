"""CNPJ alfanumérico (Receita Federal, desde 31/07/2026): 12 caracteres [0-9A-Z] + 2 dígitos verificadores (cada
caractere vale o código ASCII − 48; pesos 5,4,3,2,9,8,7,6,5,4,3,2 e 6,5,4,3,2,9,8,7,6,5,4,3,2; resto < 2 → 0, senão
11 − resto). Aceito com máscara e minúsculas e guardado em maiúsculas sem pontuação em todo lugar que recebe documento:
empresas (e a busca), dados da empresa, integrações, importação de empresas e assinatura (esta em test_assinatura).
O CPF segue só com dígitos; as mensagens de erro não mudam."""
import io

import pytest
from util import API, conta_pronta, criar_empresa, evento, gerar_chave, ligar_envios, sql

from toqqi.core.texto import normalizar_documento

OFICIAL = "12.ABC.345/01DE-35"  # o exemplo da Receita Federal
GUARDADO = "12ABC34501DE35"
MSG = "CNPJ ou CPF inválido. Confira os números."


@pytest.mark.parametrize("entrada,saida", [
    (OFICIAL, GUARDADO), ("12.abc.345/01de-35", GUARDADO), ("12abc34501de35", GUARDADO),
    (" 12 ABC 345 01DE 35 ", GUARDADO),
    ("11.222.333/0001-81", "11222333000181"), ("CNPJ 11.222.333/0001-81", "11222333000181"),  # o numérico de sempre
    ("529.982.247-25", "52998224725"), ("", None), ("  ", None), (None, None),
])
def test_normalizar_documento(entrada, saida):
    assert normalizar_documento(entrada) == saida


@pytest.mark.parametrize("ruim", [
    "12.ABC.345/01DE-34",  # 2º dígito verificador errado
    "12.ABC.345/01DE-45",  # 1º errado
    "12.ABC.345/01DE-3A",  # letra no dígito verificador
    "12.ABC.345/01DE-AB",
    "12ABC34501D35",  # 13 caracteres
    "12ABC34501DE355",  # 15 caracteres
    "12ABC34501DÉ35",  # acento não é [0-9A-Z]
    "11.222.333/0001-80", "529.982.247-24", "00000000000000", "123",
])
def test_documento_invalido(ruim):
    with pytest.raises(ValueError, match=MSG):
        normalizar_documento(ruim)


@pytest.fixture
def admin(client, dono):
    a = conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=a["conta"]["id"])
    return a


def test_empresas_cadastro_e_busca(client, admin):
    h = admin["h"]
    assert criar_empresa(client, h, "Gama", documento="12.abc.345/01de-35")["documento"] == GUARDADO
    criar_empresa(client, h, "Delta", documento="11.222.333/0001-81")
    for busca in ("12.ABC.345", "12abc345", "01DE-35", GUARDADO, "12.abc.345/01de-35"):
        itens = client.get(f"{API}/empresas", headers=h, params={"busca": busca}).json()["itens"]
        assert [e["nome"] for e in itens] == ["Gama"], busca
    for ruim in ("12.ABC.345/01DE-34", "12.ABC.345/01DE-3A", "12ABC34501D35"):
        r = client.post(f"{API}/empresas", headers=h, json={"nome": f"X {ruim}", "documento": ruim})
        assert r.status_code == 422 and r.json()["erro"]["campos"] == {"documento": MSG}, ruim


def test_dados_da_empresa(client, admin):
    r = client.put(f"{API}/conta/dados", headers=admin["h"], json={"nome": "Alfa", "documento": "12.abc.345/01de-35"})
    assert r.status_code == 200, r.text
    assert r.json()["documento"] == GUARDADO
    r = client.put(f"{API}/conta/dados", headers=admin["h"], json={"nome": "Alfa", "documento": "12.ABC.345/01DE-3A"})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"documento": MSG}


def test_integracao_cria_e_acha_a_empresa_pelo_cnpj_alfanumerico(client, admin, dono):
    h = admin["h"]
    ligar_envios(client, h)
    chave = gerar_chave(client, h)
    r = evento(client, chave, email="joao@cliente.com.br", enviar=False,
               empresa={"nome": "Gama", "documento": "12.abc.345/01de-35"})
    assert r.status_code == 201, r.text
    assert sql(dono, "select nome, documento from empresas") == [("Gama", GUARDADO)]
    r = evento(client, chave, email="maria@cliente.com.br", enviar=False, empresa={"documento": OFICIAL})
    assert r.status_code == 201, r.text
    assert client.get(f"{API}/contatos/{r.json()['contato_id']}", headers=h).json()["empresa"]["nome"] == "Gama"
    assert sql(dono, "select count(*) from empresas")[0][0] == 1
    r = evento(client, chave, email="rui@cliente.com.br", enviar=False, empresa={"documento": "12.ABC.345/01DE-34"})
    assert r.status_code == 422 and "empresa.documento" in r.json()["erro"]["campos"]


def test_importacao_de_empresas(client, admin):
    h = admin["h"]
    conteudo = "\r\n".join(";".join(x) for x in [
        ["nome", "email", "empresa", "documento_empresa"],
        ["Paula Lima", "paula@gama.com.br", "Gama", "12.abc.345/01de-35"],
        ["Rui Sá", "rui@delta.com.br", "Delta", "12.ABC.345/01DE-34"],
    ]).encode("utf-8-sig")
    r = client.post(f"{API}/importacao/analisar", headers=h, files={"arquivo": ("contatos.csv", io.BytesIO(conteudo))})
    assert r.status_code == 200, r.text
    d = r.json()
    corpo = {"mapeamento": d["mapeamento_sugerido"], "chave": "email", "ignorar_com_problema": True}
    c = client.post(f"{API}/importacao/{d['id']}/conferir", headers=h, json=corpo).json()
    assert (c["prontas"], c["com_problema"]) == (1, 1)
    assert "CNPJ/CPF inválido" in c["problemas"][0]["motivo"] and c["problemas"][0]["linha"] == 3
    r = client.post(f"{API}/importacao/{d['id']}/importar", headers=h, json=corpo)
    assert r.status_code == 200 and r.json()["novos"] == 1
    empresas = client.get(f"{API}/empresas", headers=h).json()["itens"]
    assert [(e["nome"], e["documento"]) for e in empresas] == [("Gama", GUARDADO)]
