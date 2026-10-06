"""Dados da empresa e imagens (logo): validação, permissões, logo da conta e do formulário, imagem pública, logo
nas pesquisas e nos e-mails, nome novo da empresa em todo lugar."""
import json

import pytest
from util import (
    API,
    caminho_imagem,
    conta_pronta,
    criar_contato,
    criar_form,
    disparar,
    emails_para,
    entrar,
    fixar_relogio,
    form_padrao,
    ligar_envios,
    link_pesquisa,
    membro,
    png,
    segunda,
    sql,
    token_do_convite,
)

from toqqi import tarefas
from toqqi.core.config import config
from toqqi.core.rate_limit import limiter

MSG_ARQUIVO = "Use uma imagem PNG ou JPG de até 300 KB."
MSG_TEMA = "Use um endereço https:// (até 500 caracteres)."
VAZIO = {"razao_social": None, "documento": None, "telefone": None, "email_contato": None, "site": None,
         "cep": None, "logradouro": None, "numero": None, "complemento": None, "bairro": None, "cidade": None,
         "uf": None}


JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64 + b"\xff\xd9"


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def _dados(client, h) -> dict:
    r = client.get(f"{API}/conta/dados", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _salvar(client, h, **campos):
    return client.put(f"{API}/conta/dados", headers=h, json={"nome": "Alfa Distribuidora", **campos})


def _enviar_logo(client, h, conteudo: bytes, nome: str = "logo.png", tipo: str = "image/png"):
    return client.put(f"{API}/conta/logo", headers=h, files={"arquivo": (nome, conteudo, tipo)})


def _logo_form(client, h, form_id: int, conteudo: bytes, nome: str = "logo.png"):
    return client.post(f"{API}/formularios/{form_id}/logo", headers=h, files={"arquivo": (nome, conteudo, "image/png")})


def _eventos(client, h, evento: str) -> list[dict]:
    return [i for i in client.get(f"{API}/auditoria", headers=h).json()["itens"] if i["evento"] == evento]


# ---- dados da empresa ---------------------------------------------------------

def test_dados_iniciais_e_salvar_com_mascaras(client, admin):
    h = admin["h"]
    assert _dados(client, h) == {"nome": "Alfa Distribuidora", **VAZIO, "logo_url": None, "atualizado_em": None}
    r = client.put(f"{API}/conta/dados", headers=h, json={
        "nome": "  Alfa Distribuidora Ltda  ", "razao_social": "Alfa Comércio de Alimentos Ltda",
        "documento": "11.222.333/0001-81", "telefone": "(11) 98765-4321", "email_contato": "Contato@Alfa.com.br",
        "site": "www.Alfa.com.br", "cep": "01310-100", "logradouro": "Avenida Paulista", "numero": "1000",
        "complemento": "", "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "sp"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d == {
        "nome": "Alfa Distribuidora Ltda", "razao_social": "Alfa Comércio de Alimentos Ltda",
        "documento": "11222333000181", "telefone": "5511987654321", "email_contato": "contato@alfa.com.br",
        "site": "https://www.alfa.com.br", "cep": "01310100", "logradouro": "Avenida Paulista", "numero": "1000",
        "complemento": None, "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "SP", "logo_url": None,
        "atualizado_em": d["atualizado_em"]}
    assert d["atualizado_em"] is not None
    assert _dados(client, h) == d
    # o nome novo vale na hora (topo do app)
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["nome"] == "Alfa Distribuidora Ltda"
    # auditoria: só os nomes dos campos que mudaram, sem os valores
    ev, = _eventos(client, h, "dados_empresa_alterados")
    assert ev["rotulo"] == "Dados da empresa alterados"
    assert ev["detalhe"] == {"campos": ["nome", "razao_social", "documento", "telefone", "email_contato", "site",
                                        "cep", "logradouro", "numero", "bairro", "cidade", "uf"]}
    assert "11222333000181" not in json.dumps(ev) and "Paulista" not in json.dumps(ev)

    # salvar igual: nada muda, nada é auditado
    corpo = {k: v for k, v in d.items() if k not in ("logo_url", "atualizado_em")}
    assert client.put(f"{API}/conta/dados", headers=h, json=corpo).json() == d
    assert len(_eventos(client, h, "dados_empresa_alterados")) == 1
    # PUT leva todos os campos: o que vem nulo (ou falta) fica sem valor
    r = client.put(f"{API}/conta/dados", headers=h, json={**corpo, "site": None, "numero": "", "cep": None,
                                                          "uf": None, "complemento": "Conjunto 12"})
    assert r.status_code == 200
    assert (r.json()["site"], r.json()["numero"], r.json()["complemento"]) == (None, None, "Conjunto 12")
    assert _eventos(client, h, "dados_empresa_alterados")[0]["detalhe"] == {
        "campos": ["site", "cep", "numero", "complemento", "uf"]}
    r = client.put(f"{API}/conta/dados", headers=h, json={"nome": "Alfa Distribuidora Ltda"})
    assert r.status_code == 200 and {k: r.json()[k] for k in VAZIO} == VAZIO


@pytest.mark.parametrize("campo,valor,mensagem", [
    ("nome", "", "Informe o nome da empresa."),
    ("nome", "A", "Informe o nome da empresa."),
    ("nome", None, "Informe o nome da empresa."),
    ("nome", "x" * 121, "Use no máximo 120 caracteres."),
    ("documento", "11.222.333/0001-80", "CNPJ ou CPF inválido. Confira os números."),
    ("documento", "123.456.789-00", "CNPJ ou CPF inválido. Confira os números."),
    ("documento", "1234", "CNPJ ou CPF inválido. Confira os números."),
    ("telefone", "9876-5432", "Informe o telefone com DDD (10 a 13 dígitos)."),
    ("telefone", "(011) 9876-5432", "Informe o telefone com DDD, sem o zero da operadora."),
    ("email_contato", "contato@", "Informe um e-mail válido, como nome@empresa.com.br."),
    ("site", "alfa", "Informe um site válido, como www.suaempresa.com.br."),
    ("site", "ftp://alfa.com.br", "Informe um site válido, como www.suaempresa.com.br."),
    ("site", "javascript:alert(1)", "Informe um site válido, como www.suaempresa.com.br."),
    ("site", "www.alfa .com.br", "Informe um site válido, como www.suaempresa.com.br."),
    ("site", "https://ana:segredo@alfa.com.br", "Informe um site válido, como www.suaempresa.com.br."),
    ("site", "localhost:8000", "Informe um site válido, como www.suaempresa.com.br."),
    ("site", "www.alfa.com.br/" + "x" * 190, "Informe um site válido, como www.suaempresa.com.br."),
    ("cep", "1310-100", "Informe o CEP com 8 números, como 01310-100."),
    ("cep", "01310-1000", "Informe o CEP com 8 números, como 01310-100."),
    ("cep", "abcde-fgh", "Informe o CEP com 8 números, como 01310-100."),
    ("uf", "XX", "Escolha um estado (UF) da lista."),
    ("uf", "São Paulo", "Escolha um estado (UF) da lista."),
    ("razao_social", "x" * 201, "Está longo demais."),
    ("logradouro", "x" * 151, "Está longo demais."),
    ("numero", "x" * 21, "Está longo demais."),
    ("complemento", "x" * 81, "Está longo demais."),
    ("bairro", "x" * 81, "Está longo demais."),
    ("cidade", "x" * 81, "Está longo demais."),
])
def test_validacao_por_campo(client, admin, campo, valor, mensagem):
    r = client.put(f"{API}/conta/dados", headers=admin["h"], json={"nome": "Alfa", campo: valor})
    assert r.status_code == 422, r.text
    assert r.json()["erro"]["campos"] == {campo: mensagem}
    assert _dados(client, admin["h"])["nome"] == "Alfa Distribuidora"  # nada foi gravado


def test_nome_obrigatorio_mesmo_sem_o_campo(client, admin):
    r = client.put(f"{API}/conta/dados", headers=admin["h"], json={"cidade": "Campinas"})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"nome": "Informe o nome da empresa."}


@pytest.mark.parametrize("campo,valor,gravado", [
    ("documento", "529.982.247-25", "52998224725"),          # CPF também vale
    ("documento", "11222333000181", "11222333000181"),
    ("telefone", "11 3333-4444", "551133334444"),
    ("telefone", "+55 (11) 98765-4321", "5511987654321"),
    ("site", "alfa.com.br", "https://alfa.com.br"),
    ("site", "http://www.alfa.com.br/contato?x=1", "http://www.alfa.com.br/contato?x=1"),
    ("site", "HTTPS://WWW.ALFA.COM.BR/Loja", "https://www.alfa.com.br/Loja"),
    ("site", "açaí.com.br", "https://açaí.com.br"),
    ("cep", "01310100", "01310100"),
    ("cep", "01.310-100", "01310100"),
    ("uf", " rj ", "RJ"),
    ("email_contato", "  ", None),
    ("nome", "AB", None),
])
def test_normalizacao(client, admin, campo, valor, gravado):
    r = client.put(f"{API}/conta/dados", headers=admin["h"], json={"nome": "Alfa", campo: valor})
    assert r.status_code == 200, r.text
    assert r.json()[campo] == (gravado if campo != "nome" else valor)


def test_permissoes(client, admin):
    h = admin["h"]
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    for quem in (gestor, consulta):
        assert client.get(f"{API}/conta/dados", headers=quem["h"]).status_code == 403
        assert client.put(f"{API}/conta/dados", headers=quem["h"], json={"nome": "Outra"}).status_code == 403
        assert _enviar_logo(client, quem["h"], png()).status_code == 403
        assert client.delete(f"{API}/conta/logo", headers=quem["h"]).status_code == 403
        # todos veem o logo da conta em /eu (o editor de formulário mostra o logo da empresa)
        assert client.get(f"{API}/eu", headers=quem["h"]).json()["conta"]["logo_url"] is None
    assert _dados(client, h)["nome"] == "Alfa Distribuidora"
    assert client.get(f"{API}/conta/dados").status_code == 401


# ---- logo da conta e imagem pública -------------------------------------------

def test_logo_da_conta_trocar_e_remover(client, admin, dono):
    h = admin["h"]
    r = _enviar_logo(client, h, png(10))
    assert r.status_code == 200, r.text
    d = r.json()
    url = d["logo_url"]
    chave = url.rsplit("/", 1)[1]
    assert url == f"{config().API_PUBLIC_URL}/api/v1/publico/imagens/{chave}" and len(chave) >= 32
    assert d["nome"] == "Alfa Distribuidora" and d["atualizado_em"] is not None
    assert _dados(client, h)["logo_url"] == url
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["logo_url"] == url
    img = client.get(caminho_imagem(url))
    assert img.status_code == 200 and img.content == png(10)
    assert img.headers["content-type"] == "image/png"

    # trocar: chave nova (a URL muda) e a anterior deixa de existir
    r = _enviar_logo(client, h, JPEG, nome="logo.txt", tipo="text/plain")  # vale o conteúdo, não o nome
    assert r.status_code == 200, r.text
    nova = r.json()["logo_url"]
    assert nova != url and client.get(caminho_imagem(url)).status_code == 404
    img = client.get(caminho_imagem(nova))
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content == JPEG
    assert sql(dono, "select count(*) from imagens where uso = 'logo_conta'")[0][0] == 1
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["logo_url"] == nova
    # o login também devolve o logo (o site não precisa de outra chamada)
    sessao = entrar(client, "ana@alfa.com.br").json()
    assert sessao["conta"]["logo_url"] == nova

    # remover
    r = client.delete(f"{API}/conta/logo", headers=h)
    assert r.status_code == 204
    assert _dados(client, h)["logo_url"] is None and client.get(caminho_imagem(nova)).status_code == 404
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["logo_url"] is None
    assert client.delete(f"{API}/conta/logo", headers=h).status_code == 204  # sem logo: nada a fazer
    assert sql(dono, "select count(*) from imagens")[0][0] == 0

    alterados, removidos = _eventos(client, h, "logo_alterado"), _eventos(client, h, "logo_removido")
    assert len(alterados) == 2 and len(removidos) == 1
    assert alterados[0]["rotulo"] == "Logo da empresa alterado" and removidos[0]["rotulo"] == "Logo da empresa removido"
    assert alterados[0]["detalhe"] == {"tipo": "image/jpeg", "tamanho": len(JPEG)}
    assert _eventos(client, h, "dados_empresa_alterados") == []  # o logo não mexe nos dados


@pytest.mark.parametrize("nome,conteudo", [
    ("logo.png", b"isto e um texto, nao uma imagem"),                  # .png que é texto
    ("logo.png", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'),  # SVG não
    ("logo.gif", b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"),
    ("logo.webp", b"RIFF\x1a\x00\x00\x00WEBPVP8 "),
    ("logo.png", b""),
    ("logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * (300 * 1024 - 7)),  # 1 byte acima de 300 KB
])
def test_arquivo_recusado(client, admin, dono, nome, conteudo):
    h = admin["h"]
    r = _enviar_logo(client, h, conteudo, nome=nome)
    assert r.status_code == 422, r.text
    assert r.json()["erro"]["campos"] == {"arquivo": MSG_ARQUIVO}
    f = form_padrao(client, h)
    r = _logo_form(client, h, f["id"], conteudo, nome=nome)
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"arquivo": MSG_ARQUIVO}
    assert sql(dono, "select count(*) from imagens")[0][0] == 0
    assert _eventos(client, h, "logo_alterado") == []


def test_limite_exato_de_300_kb(client, admin):
    conteudo = b"\x89PNG\r\n\x1a\n" + b"\x00" * (300 * 1024 - 8)
    r = _enviar_logo(client, admin["h"], conteudo)
    assert r.status_code == 200, r.text
    assert client.get(caminho_imagem(r.json()["logo_url"])).content == conteudo


def test_imagem_publica_cabecalhos_e_304(client, admin):
    import hashlib

    url = _enviar_logo(client, admin["h"], png(7)).json()["logo_url"]
    caminho = caminho_imagem(url)
    sha = hashlib.sha256(png(7)).hexdigest()
    r = client.get(caminho)  # sem login
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert r.headers["etag"] == f'"{sha}"'
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-length"] == str(len(png(7)))
    for etag in (f'"{sha}"', f'W/"{sha}"', f'"outra", "{sha}"', sha, "*"):
        r = client.get(caminho, headers={"If-None-Match": etag})
        assert r.status_code == 304 and r.content == b"", etag
        assert r.headers["etag"] == f'"{sha}"' and r.headers["cache-control"].endswith("immutable")
    r = client.get(caminho, headers={"If-None-Match": '"versao-antiga"'})
    assert r.status_code == 200 and r.content == png(7)
    for chave in ("x" * 43, "curta", "a" * 31, "%2e%2e%2f" + "a" * 40):
        r = client.get(f"{API}/publico/imagens/{chave}")
        assert r.status_code == 404 and r.json()["erro"]["codigo"] == "nao_encontrado", chave


def test_imagem_publica_limite_por_ip(client, admin):
    caminho = caminho_imagem(_enviar_logo(client, admin["h"], png()).json()["logo_url"])
    limiter.enabled = True
    limiter.reset()
    try:
        for _ in range(600):
            assert client.get(caminho, headers={"If-None-Match": "*"}).status_code == 304
        r = client.get(caminho)
        assert r.status_code == 429 and r.json()["erro"]["codigo"] == "muitas_tentativas"
    finally:
        limiter.enabled = False
        limiter.reset()


# ---- logo do formulário -------------------------------------------------------

def test_logo_do_formulario_e_salvar_o_formulario(client, admin, dono):
    """Regressão: o editor guardava a imagem como data: e salvar o formulário dava 422. Agora envia o arquivo,
    recebe a URL da plataforma e salva o tema com ela."""
    h = admin["h"]
    gestor = membro(client, h, "gil@alfa.com.br", "gestor")
    f = form_padrao(client, h)
    r = _logo_form(client, gestor["h"], f["id"], png(1))  # formularios.editar
    assert r.status_code == 200, r.text
    url = r.json()["logo_url"]
    assert list(r.json()) == ["logo_url"] and client.get(caminho_imagem(url)).content == png(1)
    # o tema só muda quando o formulário é salvo
    assert client.get(f"{API}/formularios/{f['id']}", headers=h).json()["tema"]["logo_url"] is None
    r = client.patch(f"{API}/formularios/{f['id']}", headers=gestor["h"], json={"tema": {"logo_url": url}})
    assert r.status_code == 200, r.text
    assert r.json()["tema"]["logo_url"] == url
    # também ao criar um formulário com o tema pronto
    r = client.post(f"{API}/formularios", headers=h, json={"nome": "Com logo", "modelo": "nps_simples",
                                                          "tema": {"logo_url": url}})
    assert r.status_code == 201 and r.json()["tema"]["logo_url"] == url
    # trocar (etapa 5l): chave nova, e o logo publicado continua no ar até a troca ser publicada
    nova = _logo_form(client, gestor["h"], f["id"], png(2)).json()["logo_url"]
    assert nova != url and client.get(caminho_imagem(url)).status_code == 200
    assert sql(dono, "select count(*) from imagens where formulario_id = :f", f=f["id"])[0][0] == 2
    assert client.patch(f"{API}/formularios/{f['id']}", headers=gestor["h"],
                        json={"tema": {"logo_url": nova}}).status_code == 200
    # publicou: o anterior ainda está no tema do formulário "Com logo", então fica
    assert client.get(caminho_imagem(url)).status_code == 200
    com_logo = next(x for x in client.get(f"{API}/formularios", headers=h).json() if x["nome"] == "Com logo")
    assert client.delete(f"{API}/formularios/{com_logo['id']}", headers=h).status_code == 204
    assert client.patch(f"{API}/formularios/{f['id']}", headers=gestor["h"],
                        json={"tema": {"logo_url": nova}}).status_code == 200
    assert client.get(caminho_imagem(url)).status_code == 404  # ninguém mais cita: saiu ao publicar
    assert sql(dono, "select count(*) from imagens where formulario_id = :f", f=f["id"])[0][0] == 1
    consulta = membro(client, h, "caio@alfa.com.br", "consulta")
    assert _logo_form(client, consulta["h"], f["id"], png()).status_code == 403
    assert _logo_form(client, h, 999999, png()).status_code == 404
    # excluir o formulário leva o logo junto
    outro = criar_form(client, h, [{"tipo": "nps", "titulo": "Nota", "obrigatoria": True}], nome="Descartável")
    url_outro = _logo_form(client, h, outro["id"], png(3)).json()["logo_url"]
    assert client.delete(f"{API}/formularios/{outro['id']}", headers=h).status_code == 204
    assert client.get(caminho_imagem(url_outro)).status_code == 404
    # nada disso entra na auditoria do logo da empresa
    assert _eventos(client, h, "logo_alterado") == []


def test_copiar_formulario_copia_o_logo(client, admin, dono):
    """A cópia ganha a própria imagem: trocar o logo de um formulário não deixa o outro sem logo."""
    h = admin["h"]
    f = form_padrao(client, h)
    url = _logo_form(client, h, f["id"], png(4)).json()["logo_url"]
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"tema": {"logo_url": url}})
    copia = client.post(f"{API}/formularios/{f['id']}/duplicar", headers=h).json()
    url_copia = copia["tema"]["logo_url"]
    assert url_copia != url and client.get(caminho_imagem(url_copia)).content == png(4)
    assert client.get(f"{API}/formularios/{copia['id']}", headers=h).json()["tema"]["logo_url"] == url_copia
    _logo_form(client, h, f["id"], png(5))  # troca o do original
    assert client.get(caminho_imagem(url_copia)).status_code == 200
    # etapa 5l: o logo publicado do original fica até a troca ser publicada (2 no original + 1 na cópia)
    assert sql(dono, "select count(*) from imagens where uso = 'logo_formulario'")[0][0] == 3
    # endereço de fora é copiado como está
    externo = "https://cdn.alfa.com.br/logo.png"
    client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"tema": {"logo_url": externo}})
    assert client.post(f"{API}/formularios/{f['id']}/duplicar", headers=h).json()["tema"]["logo_url"] == externo


@pytest.mark.parametrize("valor,aceito", [
    ("https://cdn.alfa.com.br/logo.png", True),
    ("plataforma", True),
    ("", True),
    ("data:image/png;base64,iVBORw0KGgo=", False),
    ("http://cdn.alfa.com.br/logo.png", False),
    ("http://localhost:8000/api/v1/publico/imagens/curta", False),
    ("http://localhost:8000/api/v1/publico/imagens/" + "a" * 43 + "?x=1", False),
    ("https://cdn.alfa.com.br/" + "x" * 480, False),
])
def test_tema_logo_url(client, admin, valor, aceito):
    h = admin["h"]
    f = form_padrao(client, h)
    if valor == "plataforma":
        valor = _logo_form(client, h, f["id"], png()).json()["logo_url"]
        assert valor.startswith("http://localhost:8000/")  # http:// fora de produção
    r = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"tema": {"logo_url": valor}})
    if aceito:
        assert r.status_code == 200, r.text
        assert r.json()["tema"]["logo_url"] == (valor or None)
    else:
        assert r.status_code == 422 and r.json()["erro"]["campos"] == {"tema.logo_url": MSG_TEMA}


def test_tema_logo_url_em_producao(client, admin, monkeypatch):
    h = admin["h"]
    f = form_padrao(client, h)
    url_http = _logo_form(client, h, f["id"], png()).json()["logo_url"]
    monkeypatch.setattr(config(), "AMBIENTE", "producao")
    r = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"tema": {"logo_url": url_http}})
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"tema.logo_url": MSG_TEMA}
    monkeypatch.setattr(config(), "API_PUBLIC_URL", "https://api.toqqi.com.br")
    url = _logo_form(client, h, f["id"], png()).json()["logo_url"]
    assert url.startswith("https://api.toqqi.com.br/api/v1/publico/imagens/")
    r = client.patch(f"{API}/formularios/{f['id']}", headers=h, json={"tema": {"logo_url": url}})
    assert r.status_code == 200 and r.json()["tema"]["logo_url"] == url


# ---- onde o logo aparece ------------------------------------------------------

def test_pagina_da_pesquisa_usa_o_logo_do_formulario_ou_o_da_conta(client, admin, dono):
    h = admin["h"]
    nps = form_padrao(client, h)
    c = criar_contato(client, h, nome="Paula Lima", email="paula@cliente.com.br")
    token = link_pesquisa(client, h, c["id"])

    def logos() -> tuple:
        convite = client.get(f"{API}/publico/convites/{token}").json()["formulario"]["tema"]["logo_url"]
        link = client.get(f"{API}/publico/formularios/{nps['codigo_publico']}").json()["formulario"]["tema"]
        return convite, link["logo_url"]

    assert logos() == (None, None)  # nenhum logo
    da_conta = _enviar_logo(client, h, png(1)).json()["logo_url"]
    assert logos() == (da_conta, da_conta)  # sem logo próprio: o da conta
    externo = "https://cdn.alfa.com.br/logo.png"
    client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"tema": {"logo_url": externo}})
    assert logos() == (externo, externo)
    do_form = _logo_form(client, h, nps["id"], png(2)).json()["logo_url"]
    client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"tema": {"logo_url": do_form}})
    assert logos() == (do_form, do_form)
    # etapa 5l: trocou o logo no editor sem publicar: o publicado continua no ar
    _logo_form(client, h, nps["id"], png(3))
    assert logos() == (do_form, do_form)
    # a URL salva aponta para uma imagem que não existe mais → o da conta, não uma imagem quebrada
    sql(dono, "delete from imagens where chave = :k", k=do_form.rsplit("/", 1)[1])
    assert logos() == (da_conta, da_conta)
    # o formulário guardado não muda
    assert client.get(f"{API}/formularios/{nps['id']}", headers=h).json()["tema"]["logo_url"] == do_form


def _sem_logo(m) -> bool:
    return "<img" not in m.html


def _com_logo(m, url: str, alt: str = "Alfa Distribuidora") -> bool:
    return f'<img src="{url}" alt="{alt}" height="48" style="display:block;height:48px;max-height:48px;' in m.html


def test_emails_de_pesquisa_com_e_sem_logo(client, admin, dono, monkeypatch):
    h = admin["h"]
    sql(dono, "update contas set situacao = 'cortesia' where id = :c", c=admin["conta"]["id"])
    ligar_envios(client, h)
    nps = form_padrao(client, h)
    # sem logo nenhum: o e-mail fica como sempre foi
    client.post(f"{API}/envios/configuracao/teste", headers=h)
    teste = emails_para("ana@alfa.com.br")[-1]
    assert _sem_logo(teste)
    a = criar_contato(client, h, nome="Paula", email="paula@cliente.com.br")
    disparar(client, h, [a["id"]])
    convite = emails_para("paula@cliente.com.br")[-1]
    assert _sem_logo(convite)
    token = token_do_convite(convite)
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 10}})
    agradecimento = emails_para("paula@cliente.com.br")[-1]
    assert agradecimento.assunto == "Alfa Distribuidora agradece a sua resposta" and _sem_logo(agradecimento)

    # logo da conta: convite, lembrete, agradecimento e teste ganham o cabeçalho (URL absoluta, alt = nome)
    da_conta = _enviar_logo(client, h, png(1)).json()["logo_url"]
    assert da_conta.startswith("http")
    client.post(f"{API}/envios/configuracao/teste", headers=h)
    assert _com_logo(emails_para("ana@alfa.com.br")[-1], da_conta)
    b = criar_contato(client, h, nome="Bruno", email="bruno@cliente.com.br")
    fixar_relogio(monkeypatch, segunda(9))
    disparar(client, h, [b["id"]])
    convite_b = emails_para("bruno@cliente.com.br")[-1]
    assert _com_logo(convite_b, da_conta)
    assert da_conta not in convite_b.texto  # o texto puro não muda
    fixar_relogio(monkeypatch, segunda(10, mais_dias=3))
    assert tarefas.executar("lembretes")["lembretes"]["enviados"] == 1
    lembrete = emails_para("bruno@cliente.com.br")[-1]
    assert lembrete.assunto.startswith("Lembrete:") and _com_logo(lembrete, da_conta)
    client.post(f"{API}/publico/convites/{token_do_convite(convite_b)}/responder",
                json={"respostas": {nps["perguntas"][0]["id"]: 3}})
    assert _com_logo(emails_para("bruno@cliente.com.br")[-1], da_conta)

    # logo do formulário vence o da conta
    do_form = _logo_form(client, h, nps["id"], png(2)).json()["logo_url"]
    client.patch(f"{API}/formularios/{nps['id']}", headers=h, json={"tema": {"logo_url": do_form}})
    client.post(f"{API}/envios/configuracao/teste", headers=h)
    assert _com_logo(emails_para("ana@alfa.com.br")[-1], do_form)
    c = criar_contato(client, h, nome="Carla", email="carla@cliente.com.br")
    disparar(client, h, [c["id"]])
    convite_c = emails_para("carla@cliente.com.br")[-1]
    assert _com_logo(convite_c, do_form) and da_conta not in convite_c.html
    client.post(f"{API}/publico/convites/{token_do_convite(convite_c)}/responder",
                json={"respostas": {nps["perguntas"][0]["id"]: 8}})
    assert _com_logo(emails_para("carla@cliente.com.br")[-1], do_form)


def test_nome_novo_da_empresa_nas_pesquisas_e_nos_emails(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    r = _salvar(client, h, razao_social="Alfa Nova Comércio Ltda")
    assert r.status_code == 200
    r = client.put(f"{API}/conta/dados", headers=h, json={"nome": "Alfa Nova"})
    assert r.status_code == 200 and r.json()["nome"] == "Alfa Nova"
    assert client.get(f"{API}/eu", headers=h).json()["conta"]["nome"] == "Alfa Nova"
    c = criar_contato(client, h, nome="Paula Lima", email="paula@cliente.com.br")
    token = link_pesquisa(client, h, c["id"])
    pagina = client.get(f"{API}/publico/convites/{token}").json()
    assert pagina["variaveis"]["empresa"] == "Alfa Nova"
    assert "recomendaria a Alfa Nova a um colega" in pagina["formulario"]["perguntas"][0]["titulo"]
    nps = form_padrao(client, h)
    link = client.get(f"{API}/publico/formularios/{nps['codigo_publico']}").json()
    assert link["variaveis"]["empresa"] == "Alfa Nova"
    disparar(client, h, [c["id"]])
    m = emails_para("paula@cliente.com.br")[-1]
    assert m.assunto == "Alfa Nova quer saber a sua opinião"
    assert m.remetente_nome == "Alfa Nova"  # sem remetente_nome configurado, vai o nome da empresa
    assert "Você recebeu esta pesquisa porque é cliente de Alfa Nova." in m.html
    _enviar_logo(client, h, png())
    disparar(client, h, [criar_contato(client, h, email="rui@cliente.com.br")["id"]])
    assert 'alt="Alfa Nova"' in emails_para("rui@cliente.com.br")[-1].html
    # WhatsApp (link manual): {empresa} também com o nome novo
    w = criar_contato(client, h, nome="Carlos Souza", email=None, telefone="(11) 98765-4321")
    zap = client.post(f"{API}/contatos/{w['id']}/whatsapp", headers=h, json={}).json()
    assert zap["mensagem"].startswith("Olá, Carlos! Aqui é da Alfa Nova.")
