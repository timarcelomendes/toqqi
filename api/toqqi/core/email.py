"""Envio de e-mail com provedores trocáveis por EMAIL_PROVIDER.

- console: imprime no terminal (desenvolvimento);
- memory: guarda em `caixa_memoria` (testes);
- zeptomail / resend: envio real via HTTP.

Falha no envio é registrada em log e não derruba a requisição.
"""
import html as html_lib
import logging
from dataclasses import dataclass
from email.utils import parseaddr

import httpx

from toqqi.core.config import config

log = logging.getLogger("toqqi.email")


@dataclass
class Mensagem:
    para: str
    assunto: str
    texto: str
    html: str


caixa_memoria: list[Mensagem] = []


class Provedor:
    def enviar(self, m: Mensagem) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class Console(Provedor):
    def enviar(self, m: Mensagem) -> None:
        print(f"\n--- e-mail para {m.para} ---\nAssunto: {m.assunto}\n\n{m.texto}\n--- fim ---\n", flush=True)


class Memoria(Provedor):
    def enviar(self, m: Mensagem) -> None:
        caixa_memoria.append(m)


class ZeptoMail(Provedor):
    URL = "https://api.zeptomail.com/v1.1/email"

    def enviar(self, m: Mensagem) -> None:
        nome, endereco = parseaddr(config().EMAIL_FROM)
        corpo = {
            "from": {"address": endereco, "name": nome or "Toqqi"},
            "to": [{"email_address": {"address": m.para}}],
            "subject": m.assunto,
            "htmlbody": m.html,
            "textbody": m.texto,
        }
        token = config().ZEPTOMAIL_TOKEN
        if not token.lower().startswith("zoho-enczapikey"):
            token = f"Zoho-enczapikey {token}"
        r = httpx.post(self.URL, json=corpo, headers={"Authorization": token}, timeout=10)
        r.raise_for_status()


class Resend(Provedor):
    URL = "https://api.resend.com/emails"

    def enviar(self, m: Mensagem) -> None:
        corpo = {"from": config().EMAIL_FROM, "to": [m.para], "subject": m.assunto, "html": m.html, "text": m.texto}
        r = httpx.post(
            self.URL, json=corpo, headers={"Authorization": f"Bearer {config().RESEND_API_KEY}"}, timeout=10
        )
        r.raise_for_status()


_PROVEDORES = {"console": Console, "memory": Memoria, "zeptomail": ZeptoMail, "resend": Resend}


def provedor() -> Provedor:
    return _PROVEDORES[config().EMAIL_PROVIDER]()


def _html(paragrafos: list[str], botao: tuple[str, str] | None) -> str:
    partes = [f"<p>{html_lib.escape(p)}</p>" for p in paragrafos]
    if botao:
        rotulo, link = botao
        partes.append(
            f'<p><a href="{html_lib.escape(link)}" style="background:#1f6feb;color:#fff;'
            f'padding:10px 16px;border-radius:6px;text-decoration:none">{html_lib.escape(rotulo)}</a></p>'
            f'<p style="color:#666;font-size:13px">Se o botão não funcionar, copie este endereço: '
            f"{html_lib.escape(link)}</p>"
        )
    return '<div style="font-family:Arial,sans-serif;font-size:15px;color:#222">' + "".join(partes) + "</div>"


def enviar(para: str, assunto: str, paragrafos: list[str], botao: tuple[str, str] | None = None) -> None:
    texto = "\n\n".join(paragrafos)
    if botao:
        texto += f"\n\n{botao[0]}: {botao[1]}"
    texto += "\n\nEquipe Toqqi"
    m = Mensagem(para=para, assunto=assunto, texto=texto, html=_html(paragrafos, botao))
    try:
        provedor().enviar(m)
    except Exception:  # noqa: BLE001 - e-mail não pode derrubar o fluxo
        log.exception("Falha ao enviar e-mail '%s' para %s", assunto, para)
