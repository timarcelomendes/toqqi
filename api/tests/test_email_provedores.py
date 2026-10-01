"""Provedores de e-mail: cabeçalhos extras, responder-para, nome do remetente e tradução de falhas."""
import httpx
import pytest

from toqqi.core import email
from toqqi.core.config import config


@pytest.fixture
def capturar(monkeypatch):
    chamadas = []

    def post(url, json, headers, timeout):
        chamadas.append({"url": url, "json": json, "headers": headers})
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(email.httpx, "post", post)
    monkeypatch.setattr(config(), "EMAIL_FROM", "Toqqi <pesquisa@toqqi.com>")
    return chamadas


def _mensagem() -> email.Mensagem:
    return email.Mensagem(para="p@c.com.br", assunto="A", texto="t", html="<p>t</p>",
                          remetente_nome='Alfa "Distribuidora" <x>', responder_para="sac@alfa.com.br",
                          cabecalhos={"List-Unsubscribe": "<https://api/x>",
                                      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})


def test_zeptomail(capturar, monkeypatch):
    monkeypatch.setattr(config(), "ZEPTOMAIL_TOKEN", "abc")
    email.ZeptoMail().enviar(_mensagem())
    [c] = capturar
    assert c["json"]["from"] == {"address": "pesquisa@toqqi.com", "name": "Alfa Distribuidora x via Toqqi"}
    assert c["json"]["reply_to"] == [{"address": "sac@alfa.com.br"}]
    assert c["json"]["mime_headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert c["headers"]["Authorization"] == "Zoho-enczapikey abc"


def test_resend(capturar, monkeypatch):
    monkeypatch.setattr(config(), "RESEND_API_KEY", "re_x")
    email.Resend().enviar(_mensagem())
    [c] = capturar
    assert c["json"]["from"] == '"Alfa Distribuidora x via Toqqi" <pesquisa@toqqi.com>'
    assert c["json"]["reply_to"] == ["sac@alfa.com.br"]
    assert c["json"]["headers"]["List-Unsubscribe"] == "<https://api/x>"


def test_email_do_sistema_sem_extras(capturar, monkeypatch):
    monkeypatch.setattr(config(), "RESEND_API_KEY", "re_x")
    email.Resend().enviar(email.Mensagem(para="p@c.com.br", assunto="A", texto="t", html="h"))
    [c] = capturar
    assert c["json"]["from"] == '"Toqqi" <pesquisa@toqqi.com>'
    assert "headers" not in c["json"] and "reply_to" not in c["json"]


def test_falhas_traduzidas_e_sistema_nao_quebra(monkeypatch):
    def falha(self, m):
        raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://p"), response=httpx.Response(401))

    monkeypatch.setattr(email.Memoria, "enviar", falha)
    with pytest.raises(email.FalhaEnvio) as e:
        email.enviar_mensagem(_mensagem())
    assert e.value.mensagem == email.MSG_CONFIGURACAO
    email.enviar("p@c.com.br", "Assunto", ["texto"])  # e-mail do sistema: só registra no log
