"""Etapa 5e: visual guiado dos e-mails de pesquisa (PUT/GET da configuração e montagem), a variável {motivo} do
agradecimento e os e-mails do sistema no coral da marca."""
import re

import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_form,
    disparar,
    emails_para,
    fixar_relogio,
    form_padrao,
    ligar_envios,
    membro,
    png,
    segunda,
    sql,
    token_do_convite,
)

from toqqi.core.email import caixa_memoria
from toqqi.modulos.envios import mensagens
from toqqi.modulos.envios.processamento import motivo

CAMPOS_VISUAL = ("email_cor", "email_mostrar_logo", "email_imagem_topo", "email_assinatura", "email_rodape")


@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa & Cia")


def _config(client, h) -> dict:
    r = client.get(f"{API}/envios/configuracao", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _put(client, h, **corpo):
    return client.put(f"{API}/envios/configuracao", headers=h, json=corpo)


def _imagem(client, h, conteudo: bytes | None = None, nome: str = "topo.png") -> dict:
    r = client.post(f"{API}/imagens", headers=h, files={"arquivo": (nome, conteudo or png(5), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()


def _logo(client, h) -> str:
    r = client.put(f"{API}/conta/logo", headers=h, files={"arquivo": ("logo.png", png(9), "image/png")})
    assert r.status_code == 200, r.text
    return r.json()["logo_url"]


def _teste(client, h):
    """Manda o e-mail de teste e devolve a mensagem que saiu."""
    antes = len(caixa_memoria)
    r = client.post(f"{API}/envios/configuracao/teste", headers=h)
    assert r.status_code == 200, r.text
    assert len(caixa_memoria) == antes + 1
    return caixa_memoria[-1]


def _botao(html: str) -> tuple[str, str]:
    """(fundo, cor do texto) do botão "Responder pesquisa"."""
    achou = re.search(r'bgcolor="(#[0-9A-F]{6})" style="border-radius:6px;background:\1">'
                      r'<a [^>]*;color:(#[0-9a-f]{6});[^>]*>Responder pesquisa</a>', html)
    assert achou, html
    return achou.group(1), achou.group(2)


def _faixa(html: str) -> str:
    return re.search(r'<td height="4" bgcolor="(#[0-9A-F]{6})"', html).group(1)


# ---- configuração ---------------------------------------------------------------------------

def test_padroes_e_salvar_o_visual(client, admin, dono):
    h = admin["h"]
    cfg = _config(client, h)
    assert {c: cfg[c] for c in CAMPOS_VISUAL} == {"email_cor": None, "email_mostrar_logo": True,
                                                  "email_imagem_topo": None, "email_assinatura": None,
                                                  "email_rodape": None}
    assert "email_imagem_topo_id" not in cfg
    r = _put(client, h, email_cor=" #d63a1f ", email_mostrar_logo=False,
             email_assinatura="  Equipe Alfa\r\nAtendimento\t24h ‮ ", email_rodape="Rua A, 10\nSão Paulo")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["email_cor"] == "#D63A1F"  # guardada #RRGGBB em maiúsculas
    assert d["email_mostrar_logo"] is False
    assert d["email_assinatura"] == "Equipe Alfa\nAtendimento 24h"  # CRLF vira LF, tab vira espaço, sem BIDI
    assert d["email_rodape"] == "Rua A, 10\nSão Paulo"
    assert {c: d[c] for c in CAMPOS_VISUAL} == {c: _config(client, h)[c] for c in CAMPOS_VISUAL}
    assert sql(dono, "select email_cor from config_envios") == [("#D63A1F",)]
    evento = client.get(f"{API}/auditoria", headers=h).json()["itens"][0]
    assert evento["evento"] == "config_envios"
    assert set(evento["detalhe"]["campos"]) == {"email_cor", "email_mostrar_logo", "email_assinatura", "email_rodape"}
    # vazio e nulo limpam; um PUT sem os campos não mexe neles
    d = _put(client, h, email_cor="", email_assinatura="   ", email_rodape=None).json()
    assert (d["email_cor"], d["email_assinatura"], d["email_rodape"], d["email_mostrar_logo"]) == (None, None, None,
                                                                                                    False)
    assert _put(client, h, lembretes=2).json()["email_mostrar_logo"] is False
    # gestor não grava
    g = membro(client, h, "gil@alfa.com.br", "gestor")
    assert _put(client, g["h"], email_cor="#000000").status_code == 403


@pytest.mark.parametrize("corpo,campo", [
    ({"email_cor": "D63A18"}, "email_cor"),
    ({"email_cor": "#D63A1"}, "email_cor"),
    ({"email_cor": "#GGGGGG"}, "email_cor"),
    ({"email_cor": "#D63A18AA"}, "email_cor"),
    ({"email_cor": 123}, "email_cor"),
    ({"email_mostrar_logo": "talvez"}, "email_mostrar_logo"),
    ({"email_assinatura": "x" * 301}, "email_assinatura"),
    ({"email_rodape": "x" * 501}, "email_rodape"),
    ({"email_rodape": ["linha"]}, "email_rodape"),
    ({"email_imagem_topo_id": 0}, "email_imagem_topo_id"),
    ({"email_imagem_topo_id": "abc"}, "email_imagem_topo_id"),
    ({"email_imagem_topo_id": 99999}, "email_imagem_topo_id"),
])
def test_validacao_do_visual(client, admin, corpo, campo):
    r = _put(client, admin["h"], **corpo)
    assert r.status_code == 422, r.text
    assert campo in r.json()["erro"]["campos"], r.json()


def test_limites_contam_depois_da_limpeza(client, admin):
    h = admin["h"]
    d = _put(client, h, email_assinatura="a" * 300, email_rodape=" " * 10 + "r" * 500 + "\t").json()
    assert len(d["email_assinatura"]) == 300 and d["email_rodape"] == "r" * 500
    r = _put(client, h, email_assinatura="a" * 1300)  # muito maior que o limite: recusado antes de limpar
    assert r.status_code == 422 and r.json()["erro"]["campos"]["email_assinatura"] == "Use no máximo 300 caracteres."


def test_imagem_de_topo(client, admin, dono):
    h = admin["h"]
    img = _imagem(client, h)
    d = _put(client, h, email_imagem_topo_id=img["id"]).json()
    assert d["email_imagem_topo"] == {"id": img["id"], "url": img["url"], "largura": 1, "altura": 1}
    assert _config(client, h)["email_imagem_topo"] == d["email_imagem_topo"]
    # imagem de outra conta, logo da própria conta ou inexistente: 422 no campo, nada muda
    b = conta_pronta(client, "bia@beta.com.br", empresa="Beta")
    outra = _imagem(client, b["h"])
    _logo(client, h)
    logo_id = sql(dono, "select id from imagens where uso = 'logo_conta'")[0][0]
    for invalida in (outra["id"], logo_id):
        r = _put(client, h, email_imagem_topo_id=invalida)
        assert r.status_code == 422 and r.json()["erro"]["campos"] == {
            "email_imagem_topo_id": "Escolha uma imagem do banco de imagens da conta."}
    assert _config(client, h)["email_imagem_topo"]["id"] == img["id"]
    # nulo remove
    assert _put(client, h, email_imagem_topo_id=None).json()["email_imagem_topo"] is None
    assert sql(dono, "select email_imagem_topo_id from config_envios") == [(None,)]


# ---- montagem -------------------------------------------------------------------------------

def test_ordem_do_cartao_escapes_e_texto_puro(client, admin):
    h = admin["h"]
    logo = _logo(client, h)
    img = _imagem(client, h, nome="banner.png")
    assert _put(client, h, email_cor="#0E7490", email_imagem_topo_id=img["id"],
                email_assinatura="Abraços,\nTime <b>Alfa</b>\n\nSuporte & Vendas",
                email_rodape='Alfa Ltda <script>alert("x")</script>\nCNPJ 00.000.000/0001-00').status_code == 200
    m = _teste(client, h)
    html = m.html
    marcas = [
        '<td height="4" bgcolor="#0E7490"',  # 1. faixa de 4 px na cor de destaque
        f'<img src="{logo}" alt="Alfa &amp; Cia" height="48"',  # 2. logo da conta (o formulário não tem)
        f'<img src="{img["url"]}" alt="" width="544" height="544"',  # 3. imagem de topo (1×1 → 544 de altura)
        "Olá, Pessoa!",  # 4. textos
        "nota=10",  # 5. bloco da nota
        "Abraços,<br>Time &lt;b&gt;Alfa&lt;/b&gt;",  # 6. assinatura (escapada, quebras viram <br>)
        "Suporte &amp; Vendas",
        "Alfa Ltda &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;<br>CNPJ 00.000.000/0001-00",  # 7. rodapé da conta
        "Você recebeu esta pesquisa porque é cliente de Alfa &amp; Cia.",  # e as duas linhas fixas
        "Não quero mais receber pesquisas</a>",
    ]
    posicoes = [html.find(x) for x in marcas]
    assert -1 not in posicoes, [x for x, p in zip(marcas, posicoes) if p == -1]
    assert posicoes == sorted(posicoes)
    assert "<b>" not in html and "<script>" not in html
    assert 'color:#4b5563">Abraços,' in html  # assinatura em cinza
    assert re.search(r'<img src="[^"]+" alt="" width="544"[^>]*style="display:block;max-width:100%;height:auto', html)
    assert f'href="{img["url"]}"' not in html  # a imagem de topo não é link
    # texto puro: assinatura e rodapé antes das linhas fixas
    texto = m.texto
    ordem = ["Responda aqui: ", "Abraços,\nTime <b>Alfa</b>", "Suporte & Vendas", 'Alfa Ltda <script>alert("x")',
             "Você recebeu esta pesquisa porque é cliente de Alfa & Cia.", "Não quero mais receber pesquisas: "]
    posicoes = [texto.find(x) for x in ordem]
    assert -1 not in posicoes and posicoes == sorted(posicoes), texto


def test_sem_visual_fica_como_antes(client, admin):
    """Sem visual: faixa na cor do formulário (o azul padrão do tema), sem logo, imagem, assinatura nem rodapé."""
    m = _teste(client, admin["h"])
    assert _faixa(m.html) == "#1F6FEB"
    assert "<img" not in m.html and "#4b5563" not in m.html
    partes = m.texto.split("\n\n")
    assert partes[-4].startswith("Responda aqui: ")
    assert partes[-3] == "Você recebeu esta pesquisa porque é cliente de Alfa & Cia."
    assert partes[-2].startswith("Não quero mais receber pesquisas: ")
    assert partes[-1].startswith("Pesquisa feita com Toqqi: ")  # etapa 5i


def test_mostrar_logo(client, admin):
    h = admin["h"]
    _logo(client, h)
    assert 'height="48"' in _teste(client, h).html
    _put(client, h, email_mostrar_logo=False)
    assert 'height="48"' not in _teste(client, h).html


def test_cor_de_destaque_e_contraste_do_botao(client, admin, dono):
    h = admin["h"]
    livre = criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Sugestão"}], nome="Livre")
    assert _put(client, h, formulario_id=livre["id"]).status_code == 200

    def tema(cor):
        sql(dono, "update formularios set tema = tema || jsonb_build_object('cor', cast(:c as text)) where id = :f",
            c=cor, f=livre["id"])

    # sem cor da conta: a do formulário (escura → texto branco)
    tema("#1f6feb")
    m = _teste(client, h)
    assert _botao(m.html) == ("#1F6FEB", "#ffffff") and _faixa(m.html) == "#1F6FEB"
    # formulário claro → texto escuro
    tema("#fde047")
    assert _botao(_teste(client, h).html) == ("#FDE047", "#111827")
    # a cor da conta vale mais que a do formulário
    _put(client, h, email_cor="#d63a18")
    m = _teste(client, h)
    assert _botao(m.html) == ("#D63A18", "#ffffff") and _faixa(m.html) == "#D63A18"
    _put(client, h, email_cor="#FFFFFF")
    assert _botao(_teste(client, h).html) == ("#FFFFFF", "#111827")
    # nenhuma cor válida: o coral da marca
    _put(client, h, email_cor=None)
    tema("azul")
    assert _botao(_teste(client, h).html) == ("#D63A18", "#ffffff")
    # os botões de nota continuam vermelho, amarelo e verde, com qualquer cor de destaque
    _put(client, h, email_cor="#7C3AED", formulario_id=form_padrao(client, h)["id"])
    m = _teste(client, h)
    assert _faixa(m.html) == "#7C3AED"
    cores = set(re.findall(r'nota=\d+"[^>]*background:(#[0-9a-f]{6})', m.html))
    assert cores == {"#dc2626", "#d97706", "#16a34a"}


def test_regras_de_cor():
    assert mensagens.cor_de_destaque("#abcdef", "#123456") == "#ABCDEF"
    assert mensagens.cor_de_destaque(None, "#123456") == "#123456"
    assert mensagens.cor_de_destaque("x", "#12345") == "#D63A18"
    assert mensagens.cor_de_destaque(None, None) == "#D63A18"
    # contraste de 4,5:1 com o branco é o limite (#767676 passa, #777777 não)
    assert mensagens.cor_do_texto("#767676") == "#ffffff"
    assert mensagens.cor_do_texto("#777777") == "#111827"
    assert mensagens.cor_do_texto("#D63A18") == "#ffffff" and mensagens.cor_do_texto("#FDE047") == "#111827"
    assert round(mensagens.contraste("#000000", "#FFFFFF"), 2) == 21.0


def test_convite_e_lembrete_com_o_visual(client, admin, monkeypatch):
    """O convite e o lembrete que saem pela fila também usam o visual salvo (e a cor do formulário do envio)."""
    h = admin["h"]
    ligar_envios(client, h, email_assinatura="Time Alfa", email_rodape="Rodapé da Alfa")
    fixar_relogio(monkeypatch, segunda(9))
    c = criar_contato(client, h, nome="Maria Silva", email="maria@cliente.com.br")
    assert disparar(client, h, [c["id"]]).status_code == 202
    fixar_relogio(monkeypatch, segunda(10, mais_dias=3))
    assert client.post(f"{API}/envios/lembretes/executar", headers=h).json()["enviados"] == 1
    convite, lembrete = emails_para("maria@cliente.com.br")
    assert lembrete.assunto.startswith("Lembrete") and token_do_convite(lembrete) == token_do_convite(convite)
    for m in (convite, lembrete):
        assert _faixa(m.html) == "#1F6FEB" and "Time Alfa" in m.html and "Rodapé da Alfa" in m.html
        assert m.texto.index("Time Alfa") < m.texto.index("Rodapé da Alfa") < m.texto.index("Você recebeu")


def test_imagem_de_topo_com_proporcao_absurda():
    """No Outlook vale o height="…": com teto, uma imagem 1 × 20000 não vira um atributo de milhões de pixels."""
    assert mensagens.altura_imagem_topo(1200, 400) == 181
    assert mensagens.altura_imagem_topo(1, 20000) == 2 * mensagens.LARGURA_IMAGEM
    assert mensagens.altura_imagem_topo(20000, 1) == 1


# ---- agradecimento: {motivo} --------------------------------------------------------------------

def test_motivo_numa_linha_e_cortado():
    assert motivo(None) == "" and motivo("   ") == ""
    assert motivo("  Entrega\r\n\tatrasou   muito \x00 ") == "Entrega atrasou muito"
    longo = "palavra " * 40
    assert motivo(longo) == longo[:200].rstrip() and len(motivo("x" * 300)) == 200


def test_agradecimento_com_motivo(client, admin):
    h = admin["h"]
    ligar_envios(client, h, agradecimento={"promotor": "Valeu, {nome}! Você disse: “{motivo}”. Nota {nota}.",
                                           "neutro": "N {motivo}", "detrator": "D"},
                 email_assinatura="Time Alfa", email_cor="#047857")
    c = criar_contato(client, h, nome="Paula Lima", email="paula@c.com.br")
    disparar(client, h, [c["id"]])
    nps = form_padrao(client, h)
    token = token_do_convite(emails_para("paula@c.com.br")[0])
    comentario = "Gostei {nome} <b>muito</b>\n\nda entrega " + "e " * 150
    r = client.post(f"{API}/publico/convites/{token}/responder",
                    json={"respostas": {nps["perguntas"][0]["id"]: 10, nps["perguntas"][1]["id"]: comentario}})
    assert r.status_code == 201, r.text
    m = emails_para("paula@c.com.br")[-1]
    assert m.assunto == "Alfa & Cia agradece a sua resposta"
    esperado = motivo(comentario)
    assert len(esperado) <= 200 and esperado.startswith("Gostei {nome} <b>muito</b> da entrega e e")
    assert m.texto.startswith(f"Valeu, Paula! Você disse: “{esperado}”. Nota 10.")  # o comentário não é trocado
    assert "&lt;b&gt;muito&lt;/b&gt;" in m.html and "<b>" not in m.html
    assert _faixa(m.html) == "#047857" and "Time Alfa" in m.html and "Time Alfa" in m.texto


def test_agradecimento_sem_comentario(client, admin):
    h = admin["h"]
    ligar_envios(client, h, agradecimento={"promotor": "Obrigado! {motivo}", "neutro": "N", "detrator": "D"})
    c = criar_contato(client, h, nome="Rui", email="rui@c.com.br")
    disparar(client, h, [c["id"]])
    nps = form_padrao(client, h)
    token = token_do_convite(emails_para("rui@c.com.br")[0])
    client.post(f"{API}/publico/convites/{token}/responder", json={"respostas": {nps["perguntas"][0]["id"]: 9}})
    assert emails_para("rui@c.com.br")[-1].texto.startswith("Obrigado!\n\n")


# ---- e-mails do sistema ------------------------------------------------------------------------

def test_emails_do_sistema_no_coral_da_marca(client, admin):
    assert client.post(f"{API}/auth/esqueci-senha", json={"email": "ana@alfa.com.br"}).status_code == 200
    m = emails_para("ana@alfa.com.br")[-1]
    assert m.assunto == "Redefina sua senha do Toqqi"
    assert re.search(r'<a href="[^"]+/redefinir-senha\?token=[^"]+" style="background:#D63A18;color:#ffffff;', m.html)
    assert re.search(r'copie este endereço: <a href="[^"]+" style="color:#B02F13">', m.html)
    assert "1f6feb" not in m.html.lower()
    assert m.texto.rstrip().endswith("Equipe Toqqi")
