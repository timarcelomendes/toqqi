"""Etapa 5h (B), §3: a régua de notas do e-mail cabe no celular.

A régua cabe em 320 px de tela sem rolagem lateral e continua boa nos 600 px do cartão e no Outlook: tabela com 100% da
largura do conteúdo, uma célula de largura percentual por nota (NPS 11, CSAT 5), nenhuma largura fixa em px, o link em
bloco com 40 px de altura e fonte de 15 px, a cor no `bgcolor` da célula (Outlook) e no fundo do link, os rótulos
embaixo. O CSAT fica em até 320 px, no meio. A versão em texto não muda.
(Conferido no Chromium a 320, 360 e 600 px: `scrollWidth` igual à largura da tela.)"""
import re
from html.parser import HTMLParser

import pytest
from util import (
    API,
    conta_pronta,
    criar_contato,
    criar_form,
    disparar,
    emails_para,
    form_padrao,
    ligar_envios,
    token_do_convite,
)

from toqqi.core.email import caixa_memoria
from toqqi.modulos.envios import mensagens
from toqqi.modulos.envios.descadastro import link_descadastro

LINK = "https://app.teste/r/AbC123"
VERMELHO, AMARELO, VERDE = "#dc2626", "#d97706", "#16a34a"
NPS = [{"id": "a", "tipo": "nps", "titulo": "Recomendaria a {empresa}?", "obrigatoria": True,
        "rotulo_min": "Nada provável", "rotulo_max": "Muito provável"}]
CSAT = [{"id": "a", "tipo": "csat", "titulo": "Como foi a entrega?", "obrigatoria": True}]
# Conteúdo do cartão numa tela de 320 px: 12 px de fundo cinza e 28 px de margem de cada lado
CONTEUDO_EM_320 = 320 - 2 * 12 - 2 * mensagens.MARGEM


# ---- árvore mínima do HTML ------------------------------------------------------------------

class _Arvore(HTMLParser):
    VAZIAS = {"br", "img", "meta", "hr", "input", "link"}

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.raiz = {"tag": "#doc", "attrs": {}, "filhos": [], "texto": "", "pai": None}
        self._pilha = [self.raiz]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        no = {"tag": tag, "attrs": dict(attrs), "filhos": [], "texto": "", "pai": self._pilha[-1]}
        self._pilha[-1]["filhos"].append(no)
        if tag not in self.VAZIAS:
            self._pilha.append(no)

    def handle_endtag(self, tag):
        for i in range(len(self._pilha) - 1, 0, -1):
            if self._pilha[i]["tag"] == tag:
                del self._pilha[i:]
                return

    def handle_data(self, data):
        self._pilha[-1]["filhos"].append({"tag": "#texto", "texto": data, "filhos": [], "attrs": {}})


def _todos(no, tag=None):
    for f in no["filhos"]:
        if tag is None or f["tag"] == tag:
            yield f
        yield from _todos(f, tag)


def _texto(no) -> str:
    return no["texto"] if no["tag"] == "#texto" else "".join(_texto(f) for f in no["filhos"])


def _estilo(no) -> dict:
    return {k.strip(): v.strip() for k, v in
            (p.split(":", 1) for p in (no["attrs"].get("style") or "").split(";") if ":" in p)}


def _acima(no, tag):
    while no is not None and no["tag"] != tag:
        no = no["pai"]
    return no


def _irmao_seguinte(no):
    irmaos = [f for f in no["pai"]["filhos"] if f["tag"] != "#texto"]
    i = irmaos.index(no) + 1
    return irmaos[i] if i < len(irmaos) else None


def _regua(html: str) -> dict:
    """A régua do e-mail: links das notas, células, a tabela delas e a tabela dos rótulos."""
    raiz = _Arvore(html).raiz
    links = [a for a in _todos(raiz, "a") if "nota=" in a["attrs"].get("href", "")]
    assert links, "o e-mail não tem a régua"
    celulas = [_acima(a, "td") for a in links]
    tabela = _acima(celulas[0], "table")
    assert all(_acima(c, "table") is tabela for c in celulas), "as notas ficam numa tabela só"
    assert len({id(_acima(c, "tr")) for c in celulas}) == 1, "as notas ficam numa linha só"
    rotulos = _irmao_seguinte(tabela)
    assert rotulos is not None and rotulos["tag"] == "table", "os rótulos vêm numa tabela logo depois da régua"
    return {"links": links, "celulas": celulas, "tabela": tabela, "rotulos": rotulos}


def _email(perguntas, link=LINK, **visual) -> str:
    v = mensagens.variaveis("Alfa & Cia", "Maria Souza", None, link)
    return mensagens.email_pesquisa(conta_id=1, para="maria@cliente.com.br", empresa="Alfa & Cia", assunto="Oi",
                                    texto="Olá, {nome}!", perguntas=perguntas, link=link, v=v, remetente_nome=None,
                                    responder_para=None, visual=mensagens.Visual(**visual))


def _sem_largura_fixa(r: dict):
    """Nenhum elemento da régua nem dos rótulos tem largura fixa em px (só %), e o teto (CSAT) cabe em 320 px."""
    for tabela in (r["tabela"], r["rotulos"]):
        for no in [tabela, *_todos(tabela)]:
            if no["tag"] == "#texto":
                continue
            largura = no["attrs"].get("width")
            assert largura is None or largura.endswith("%"), (no["tag"], largura)
            estilo = _estilo(no)
            assert not estilo.get("width", "%").endswith("px"), (no["tag"], estilo)
            if "max-width" in estilo:
                assert int(estilo["max-width"].removesuffix("px")) <= 320


# ---- NPS ------------------------------------------------------------------------------------

def test_regua_nps_onze_notas_em_largura_percentual():
    r = _regua(_email(NPS).html)
    assert [a["attrs"]["href"] for a in r["links"]] == [f"{LINK}?nota={n}" for n in range(11)]
    assert [_texto(a) for a in r["links"]] == [str(n) for n in range(11)]
    # tabela com 100% da largura do conteúdo, que não cresce com o conteúdo
    t = r["tabela"]
    assert t["attrs"]["width"] == "100%" and t["attrs"]["cellspacing"] == str(mensagens.ESPACO_NOTAS)
    assert _estilo(t)["width"] == "100%" and _estilo(t)["table-layout"] == "fixed"
    assert "max-width" not in _estilo(t)  # o NPS ocupa a largura toda do cartão (até 544 px)
    for c in r["celulas"]:
        assert c["attrs"]["width"] == "9%" and _estilo(c)["width"] == "9.09%"
        assert c["attrs"]["height"] == "40" and _estilo(c)["height"] == "40px"
    assert sum(float(_estilo(c)["width"][:-1]) for c in r["celulas"]) == pytest.approx(100, abs=0.1)
    _sem_largura_fixa(r)


def test_link_em_bloco_de_40px_com_fonte_15px():
    for a in _regua(_email(NPS).html)["links"]:
        e = _estilo(a)
        assert e["display"] == "block" and e["height"] == "40px" and e["line-height"] == "40px"
        assert e["font-size"] == "15px" and e["font-weight"] == "bold" and e["color"] == "#ffffff"
        assert e["text-decoration"] == "none" and e["text-align"] == "center"
        assert "width" not in e  # a largura é a da célula
        assert a["attrs"]["target"] == "_blank"


def test_cores_no_bgcolor_da_celula_e_no_fundo_do_link():
    r = _regua(_email(NPS, cor="#7C3AED").html)  # a cor de destaque da conta não muda a régua
    esperadas = [VERMELHO] * 7 + [AMARELO] * 2 + [VERDE] * 2
    assert [c["attrs"]["bgcolor"] for c in r["celulas"]] == esperadas  # Outlook
    assert [_estilo(c)["background"] for c in r["celulas"]] == esperadas
    assert [_estilo(a)["background"] for a in r["links"]] == esperadas


def test_cabe_em_320px():
    """A régua não tem largura mínima maior que o conteúdo do cartão numa tela de 320 px (240 px): cada nota precisa só
    do número ("10" em Arial negrito de 15 px ≈ 17 px) mais o espaço entre elas."""
    r = _regua(_email(NPS).html)
    digito = 0.556 * int(_estilo(r["links"][0])["font-size"][:-2])  # largura de um algarismo no Arial (em)
    minimo = len(r["links"]) * (2 * digito + mensagens.ESPACO_NOTAS) + mensagens.ESPACO_NOTAS
    assert minimo <= CONTEUDO_EM_320, minimo
    # e o resto do cartão também não tem largura fixa que estoure: o cartão é width:100% com teto de 600 px
    assert 'width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px' in _email(NPS).html


def test_rotulos_embaixo_nas_pontas_e_escapados():
    perguntas = [{**NPS[0], "rotulo_min": "Nunca <b>mesmo</b>", "rotulo_max": "Com certeza & já"}]
    html = _email(perguntas).html
    r = _regua(html)
    esquerda, direita = [td for td in _todos(r["rotulos"], "td")]
    assert (esquerda["attrs"]["align"], _texto(esquerda)) == ("left", "Nunca <b>mesmo</b>")
    assert (direita["attrs"]["align"], _texto(direita)) == ("right", "Com certeza & já")
    assert esquerda["attrs"]["width"] == direita["attrs"]["width"] == "50%"
    assert "Nunca &lt;b&gt;mesmo&lt;/b&gt;" in html and "<b>" not in html
    # padrões do NPS quando a pergunta não tem rótulos
    sem = _regua(_email([{k: v for k, v in NPS[0].items() if not k.startswith("rotulo")}]).html)
    assert [_texto(td) for td in _todos(sem["rotulos"], "td")] == ["Nada provável", "Muito provável"]


def test_link_que_ja_tem_parametros_ganha_nota_com_e_comercial():
    link = "http://app.teste/f/Xy12?canal=link"
    html = _email(NPS, link=link).html
    assert [a["attrs"]["href"] for a in _regua(html)["links"]] == [f"{link}&nota={n}" for n in range(11)]
    assert f'href="http://app.teste/f/Xy12?canal=link&amp;nota=10"' in html


# ---- CSAT e personalizado -------------------------------------------------------------------

def test_regua_csat_cinco_notas_ate_320px_no_meio():
    r = _regua(_email(CSAT).html)
    assert [a["attrs"]["href"] for a in r["links"]] == [f"{LINK}?nota={n}" for n in range(1, 6)]
    assert [c["attrs"]["width"] for c in r["celulas"]] == ["20%"] * 5
    assert [_estilo(c)["width"] for c in r["celulas"]] == ["20.00%"] * 5
    assert [c["attrs"]["bgcolor"] for c in r["celulas"]] == [VERMELHO, VERMELHO, AMARELO, VERDE, VERDE]
    for t in (r["tabela"], r["rotulos"]):
        assert t["attrs"]["width"] == "100%" and t["attrs"]["align"] == "center"
        assert _estilo(t)["width"] == "100%" and _estilo(t)["max-width"] == "320px"
    assert [_texto(td) for td in _todos(r["rotulos"], "td")] == ["Muito insatisfeito", "Muito satisfeito"]
    _sem_largura_fixa(r)


def test_estrelas_tambem_vai_de_1_a_5():
    perguntas = [{"id": "e", "tipo": "estrelas", "titulo": "Nota", "obrigatoria": True}]
    assert [_texto(a) for a in _regua(_email(perguntas).html)["links"]] == ["1", "2", "3", "4", "5"]


def test_personalizado_continua_com_o_botao():
    html = _email([{"id": "t", "tipo": "texto_curto", "titulo": "Sugestão", "obrigatoria": False}],
                  cor="#0E7490").html
    assert "nota=" not in html and "Responder pesquisa" in html
    assert 'bgcolor="#0E7490"' in html


def test_texto_puro_nao_muda():
    m = _email(NPS, assinatura="Abraços,\nTime Alfa", rodape="Alfa Ltda")
    sair = link_descadastro(1, "maria@cliente.com.br")
    assert m.texto == "\n\n".join([
        "Olá, Maria!", f"Responda aqui: {LINK}", "Abraços,\nTime Alfa", "Alfa Ltda",
        "Você recebeu esta pesquisa porque é cliente de Alfa & Cia.", f"Não quero mais receber pesquisas: {sair}",
    ])
    assert "nota=" not in m.texto


# ---- de ponta a ponta -----------------------------------------------------------------------

@pytest.fixture
def admin(client):
    return conta_pronta(client, "ana@alfa.com.br", empresa="Alfa Distribuidora")


def test_convite_enviado_leva_a_regua_nova(client, admin):
    h = admin["h"]
    ligar_envios(client, h)
    c = criar_contato(client, h, nome="Maria Silva", email="maria@cliente.com.br")
    assert disparar(client, h, [c["id"]]).status_code == 202
    [m] = emails_para("maria@cliente.com.br")
    token = token_do_convite(m)
    r = _regua(m.html)
    assert [a["attrs"]["href"] for a in r["links"]] == [f"http://app.teste/r/{token}?nota={n}" for n in range(11)]
    assert [c["attrs"]["bgcolor"] for c in r["celulas"]] == [VERMELHO] * 7 + [AMARELO] * 2 + [VERDE] * 2
    _sem_largura_fixa(r)
    # a nota do e-mail abre a pesquisa já com ela marcada (a página começa depois da nota)
    assert client.get(f"{API}/publico/convites/{token}").status_code == 200


def test_email_de_teste_com_formulario_csat(client, admin):
    h = admin["h"]
    csat = form_padrao(client, h, "csat")
    ligar_envios(client, h, formulario_id=csat["id"])
    antes = len(caixa_memoria)
    assert client.post(f"{API}/envios/configuracao/teste", headers=h).status_code == 200
    assert len(caixa_memoria) == antes + 1
    r = _regua(caixa_memoria[-1].html)
    assert [_texto(a) for a in r["links"]] == ["1", "2", "3", "4", "5"]
    assert all(re.search(rf"/f/{csat['codigo_publico']}\?canal=link&nota=\d$", a["attrs"]["href"]) for a in r["links"])
    assert [_texto(td) for td in _todos(r["rotulos"], "td")] == ["Muito ruim", "Excelente"]  # os do modelo
    livre = criar_form(client, h, [{"tipo": "texto_curto", "titulo": "Sugestão"}], nome="Livre")
    ligar_envios(client, h, formulario_id=livre["id"])
    client.post(f"{API}/envios/configuracao/teste", headers=h)
    assert "nota=" not in caixa_memoria[-1].html
