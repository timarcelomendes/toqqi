"""Etapa 5e: banco de imagens da conta (GET/POST /imagens, DELETE /imagens/{id}): tipos pelos bytes, 1 MB, 30 por
conta, dimensões, nome do arquivo, em uso, permissões, isolamento entre contas e auditoria."""
import struct
import zlib

import pytest
from sqlalchemy import text
from util import API, caminho_imagem, conta_pronta, membro, png, sql

from toqqi.modulos.imagens import servico

MSG_ARQUIVO = "Use uma imagem PNG ou JPG de até 1 MB."
MSG_LIMITE = "O banco de imagens tem até 30 imagens. Exclua uma para enviar outra."
MSG_EM_USO = "Esta imagem está no visual dos e-mails. Troque a imagem de topo antes de excluir."
CAMPOS = {"id", "url", "nome", "tipo", "tamanho", "largura", "altura", "criada_em", "em_uso"}


def png_de(largura: int, altura: int) -> bytes:
    """Só o cabeçalho de um PNG (assinatura + IHDR + IEND): basta para o tipo e as dimensões."""
    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))

    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0))
            + bloco(b"IEND", b""))


def jpeg_de(largura: int, altura: int, sof: int = 0xC0) -> bytes:
    """SOI + APP0 (JFIF) + DQT de mentira + SOFn com as dimensões + EOI."""
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    dqt = b"\xff\xdb" + struct.pack(">H", 4) + b"\x00\x01"
    sofn = bytes([0xFF, sof]) + struct.pack(">HBHHB", 11, 8, altura, largura, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + dqt + sofn + b"\xff\xd9"


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa")


def _enviar(client, h, conteudo: bytes, nome: str = "topo.png", tipo: str = "image/png"):
    return client.post(f"{API}/imagens", headers=h, files={"arquivo": (nome, conteudo, tipo)})


def _lista(client, h) -> dict:
    r = client.get(f"{API}/imagens", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _eventos(client, h, evento: str) -> list[dict]:
    return [e for e in client.get(f"{API}/auditoria", headers=h).json()["itens"] if e["evento"] == evento]


def test_enviar_listar_servir_e_excluir(client, admin):
    h = admin["h"]
    assert _lista(client, h) == {"itens": [], "limite": 30}
    r = _enviar(client, h, png_de(1200, 400), nome="fotos/Topo de Natal.png")
    assert r.status_code == 201, r.text
    a = r.json()
    assert set(a) == CAMPOS
    assert (a["nome"], a["tipo"], a["tamanho"], a["largura"], a["altura"], a["em_uso"]) == (
        "Topo de Natal.png", "image/png", len(png_de(1200, 400)), 1200, 400, False)
    assert a["criada_em"] and a["url"].startswith("http")
    b = _enviar(client, h, jpeg_de(640, 480), nome="foto.jpg", tipo="image/jpeg").json()
    assert (b["tipo"], b["largura"], b["altura"]) == ("image/jpeg", 640, 480)
    # mais novas primeiro
    assert [i["id"] for i in _lista(client, h)["itens"]] == [b["id"], a["id"]]
    assert _lista(client, h)["itens"][1] == a
    # sai sem login pela URL pública de sempre
    r = client.get(caminho_imagem(a["url"]))
    assert r.status_code == 200 and r.content == png_de(1200, 400) and r.headers["content-type"] == "image/png"
    # auditoria com o nome
    [enviada] = [e for e in _eventos(client, h, "imagem_enviada") if e["detalhe"]["nome"] == "Topo de Natal.png"]
    assert enviada["rotulo"] == "Imagem enviada ao banco de imagens"
    assert enviada["detalhe"] == {"nome": "Topo de Natal.png", "tipo": "image/png", "tamanho": a["tamanho"]}
    assert client.delete(f"{API}/imagens/{a['id']}", headers=h).status_code == 204
    assert [i["id"] for i in _lista(client, h)["itens"]] == [b["id"]]
    assert client.get(caminho_imagem(a["url"])).status_code == 404
    [excluida] = _eventos(client, h, "imagem_excluida")
    assert excluida["detalhe"] == {"nome": "Topo de Natal.png"}
    assert excluida["rotulo"] == "Imagem excluída do banco de imagens"
    assert client.delete(f"{API}/imagens/{a['id']}", headers=h).status_code == 404


@pytest.mark.parametrize("conteudo,nome,tipo", [
    (b"GIF89a" + b"\x00" * 20, "a.gif", "image/gif"),
    (b"<svg xmlns='x'></svg>", "a.png", "image/png"),  # a extensão não conta: valem os bytes
    (b"", "vazio.png", "image/png"),
    (png() + b"\x00" * (1024 * 1024 + 1 - len(png())), "grande.png", "image/png"),  # 1 MB + 1 byte
])
def test_tipo_e_tamanho(client, admin, conteudo, nome, tipo):
    r = _enviar(client, admin["h"], conteudo, nome=nome, tipo=tipo)
    assert r.status_code == 422, r.text
    assert r.json()["erro"]["campos"] == {"arquivo": MSG_ARQUIVO} and r.json()["erro"]["mensagem"] == MSG_ARQUIVO


def test_ate_1_mb_e_dimensoes_desconhecidas(client, admin):
    h = admin["h"]
    um_mb = png() + b"\x00" * (1024 * 1024 - len(png()))
    r = _enviar(client, h, um_mb)
    assert r.status_code == 201 and r.json()["tamanho"] == 1024 * 1024
    # JPEG sem SOF (dimensões que não dá para ler): entra, com largura e altura nulas
    r = _enviar(client, h, b"\xff\xd8\xff\xe0" + b"\x00" * 30, nome="x.jpg", tipo="image/jpeg")
    assert r.status_code == 201 and (r.json()["largura"], r.json()["altura"]) == (None, None)
    # os logos continuam com 300 KB
    grande = png() + b"\x00" * (300 * 1024 + 1 - len(png()))
    assert client.put(f"{API}/conta/logo", headers=h, files={"arquivo": ("l.png", grande, "image/png")}
                      ).status_code == 422


def test_limite_de_30(client, admin, dono):
    h = admin["h"]
    sql(dono, """
        insert into imagens (conta_id, uso, chave, tipo, dados, tamanho, sha256)
        select :c, 'banco', 'chave' || g || repeat('x', 40), 'image/png', decode('00', 'hex'), 1, repeat('0', 64)
          from generate_series(1, 29) g
    """, c=admin["conta"]["id"])
    assert _enviar(client, h, png(1)).status_code == 201  # a 30ª
    r = _enviar(client, h, png(2))
    assert r.status_code == 409 and r.json()["erro"] == {"codigo": "limite_imagens", "mensagem": MSG_LIMITE,
                                                         "campos": {}}
    assert len(_lista(client, h)["itens"]) == 30
    # o logo da conta não conta (nem aparece no banco)
    assert client.put(f"{API}/conta/logo", headers=h, files={"arquivo": ("l.png", png(3), "image/png")}
                      ).status_code == 200
    assert len(_lista(client, h)["itens"]) == 30
    # outra conta tem o seu próprio limite
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert _enviar(client, b["h"], png(4)).status_code == 201


def test_imagem_em_uso_nao_sai(client, admin, dono):
    h = admin["h"]
    img = _enviar(client, h, png(1)).json()
    outra = _enviar(client, h, png(2)).json()
    assert client.put(f"{API}/envios/configuracao", headers=h, json={"email_imagem_topo_id": img["id"]}
                      ).status_code == 200
    assert {i["id"]: i["em_uso"] for i in _lista(client, h)["itens"]} == {img["id"]: True, outra["id"]: False}
    r = client.delete(f"{API}/imagens/{img['id']}", headers=h)
    assert r.status_code == 409 and r.json()["erro"]["codigo"] == "imagem_em_uso"
    assert r.json()["erro"]["mensagem"] == MSG_EM_USO
    assert _eventos(client, h, "imagem_excluida") == []
    # trocando a imagem de topo, a antiga pode sair
    assert client.put(f"{API}/envios/configuracao", headers=h, json={"email_imagem_topo_id": outra["id"]}
                      ).status_code == 200
    assert client.delete(f"{API}/imagens/{img['id']}", headers=h).status_code == 204
    # se a imagem some por fora (ex.: exclusão da conta pela plataforma), a configuração fica sem imagem
    sql(dono, "delete from imagens where id = :i", i=outra["id"])
    assert sql(dono, "select email_imagem_topo_id from config_envios") == [(None,)]
    assert client.get(f"{API}/envios/configuracao", headers=h).json()["email_imagem_topo"] is None


def test_permissoes_e_outra_conta(client, admin, dono, app_engine):
    h = admin["h"]
    img = _enviar(client, h, png(1)).json()
    g = membro(client, h, "gil@alfa.com.br", "gestor")
    assert client.get(f"{API}/imagens", headers=g["h"]).status_code == 403
    assert _enviar(client, g["h"], png(2)).status_code == 403
    assert client.delete(f"{API}/imagens/{img['id']}", headers=g["h"]).status_code == 403
    assert client.get(f"{API}/imagens").status_code == 401
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    assert _lista(client, b["h"])["itens"] == []
    assert client.delete(f"{API}/imagens/{img['id']}", headers=b["h"]).status_code == 404
    assert client.delete(f"{API}/imagens/999999", headers=h).status_code == 404
    assert client.delete(f"{API}/imagens/0", headers=h).status_code == 422
    # um logo não é imagem do banco: 404
    client.put(f"{API}/conta/logo", headers=h, files={"arquivo": ("l.png", png(3), "image/png")})
    logo_id = sql(dono, "select id from imagens where uso = 'logo_conta'")[0][0]
    assert client.delete(f"{API}/imagens/{logo_id}", headers=h).status_code == 404
    assert [i["id"] for i in _lista(client, h)["itens"]] == [img["id"]]
    # SQL direto com a conta de B não vê nem apaga as imagens de A
    with app_engine.begin() as c:
        c.execute(text("select set_config('app.conta_id', :c, true)"), {"c": str(b["conta"]["id"])})
        assert c.execute(text("select count(*) from imagens")).scalar() == 0
        assert c.execute(text("delete from imagens")).rowcount == 0
    assert sql(dono, "select count(*) from imagens where uso = 'banco'")[0][0] == 1


def test_formulario_copiado_nao_copia_imagem_do_banco(client, admin, dono):
    """Uma imagem do banco no tema de um formulário (até 1 MB) não vira logo do formulário copiado (logos: 300 KB)."""
    h = admin["h"]
    img = _enviar(client, h, png(1)).json()
    f = client.get(f"{API}/formularios", headers=h).json()[0]
    sql(dono, "update formularios set tema = tema || jsonb_build_object('logo_url', cast(:u as text)) where id = :f",
        u=img["url"], f=f["id"])
    r = client.post(f"{API}/formularios/{f['id']}/duplicar", headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["tema"]["logo_url"] == img["url"]  # fica como está
    assert sql(dono, "select count(*) from imagens where uso = 'logo_formulario'")[0][0] == 0


# ---- unidades ----------------------------------------------------------------------------------

def test_dimensoes_pelo_cabecalho():
    assert servico.dimensoes(png(), "image/png") == (1, 1)
    assert servico.dimensoes(png_de(1200, 400), "image/png") == (1200, 400)
    assert servico.dimensoes(jpeg_de(1200, 400), "image/jpeg") == (1200, 400)
    assert servico.dimensoes(jpeg_de(800, 600, sof=0xC2), "image/jpeg") == (800, 600)  # progressivo
    assert servico.dimensoes(jpeg_de(0, 600), "image/jpeg") == (None, None)
    assert servico.dimensoes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4, "image/png") == (None, None)
    assert servico.dimensoes(b"\xff\xd8\xff\xda\x00\x02", "image/jpeg") == (None, None)  # dados sem SOF antes
    assert servico.dimensoes(b"\xff\xd8\xff\xe0\x00\x01", "image/jpeg") == (None, None)  # tamanho inválido


def test_nome_do_arquivo():
    assert servico.nome_do_arquivo("C:\\fakepath\\Banner\u202e  Topo\x07.PNG") == "Banner Topo .PNG"
    assert servico.nome_do_arquivo("pasta/sub/foto.jpg") == "foto.jpg"
    assert servico.nome_do_arquivo("   ") is None and servico.nome_do_arquivo(None) is None
    assert servico.nome_do_arquivo("a" * 200 + ".png") == "a" * 120


def test_envio_enorme_para_antes_do_login(client, admin, dono):
    """O FastAPI lê o multipart antes de conferir o login: o envio enorme para no limite do corpo (413), sem token e
    com token; um pouco acima de 1 MB ainda chega à rota e recebe a mensagem de sempre."""
    grande = b"\x89PNG\r\n\x1a\n" + b"\0" * (2 * 1024 * 1024)
    for h in ({}, admin["h"]):
        r = client.post(f"{API}/imagens", headers=h, files={"arquivo": ("x.png", grande, "image/png")})
        assert r.status_code == 413 and r.json()["erro"]["codigo"] == "pedido_grande_demais"
    um_pouco_acima = png() + b"\0" * (1024 * 1024)
    r = client.post(f"{API}/imagens", headers=admin["h"], files={"arquivo": ("x.png", um_pouco_acima, "image/png")})
    assert r.status_code == 422 and set(r.json()["erro"]["campos"]) == {"arquivo"}
    for metodo, caminho in (("put", "/conta/logo"), ("post", "/formularios/1/logo"), ("post", "/importacao/analisar")):
        r = getattr(client, metodo)(f"{API}{caminho}", files={"arquivo": ("x.png", grande * 3, "image/png")})
        assert r.status_code == 413, caminho
    assert sql(dono, "select count(*) from imagens")[0][0] == 0
