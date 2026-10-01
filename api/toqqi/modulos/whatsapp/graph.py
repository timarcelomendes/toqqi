"""Chamadas à Graph API da Meta (WhatsApp Cloud API).

Endereço e versão vêm da configuração (WHATSAPP_GRAPH_URL, WHATSAPP_GRAPH_VERSION). Sem redirecionamento,
timeout de 10 s. Os testes trocam `transporte` por um httpx.MockTransport (nada sai para a rede).
O token nunca vai para o log.
"""
import logging

import httpx

from toqqi.core.config import config

log = logging.getLogger("toqqi.whatsapp")

transporte: httpx.BaseTransport | None = None

MSG_TOKEN = "A Meta recusou o token do WhatsApp. Reconecte o WhatsApp em Integrações."
MSG_MODELO = "A Meta recusou o modelo de mensagem. Confira o modelo em Integrações."
MSG_CONTA = "A conta do WhatsApp está bloqueada, restrita ou sem número registrado na Meta."
MSG_NUMERO = "O número não tem WhatsApp ou não pode receber a mensagem."
MSG_LIMITE = "Limite de envio do WhatsApp atingido; tentaremos de novo."
MSG_FORA_DO_AR = "O WhatsApp está fora do ar; tentaremos de novo."
MSG_RECUSOU = "O WhatsApp recusou a mensagem."

_CODIGOS_TOKEN = {190, 10, 200}
_CODIGOS_CONTA = {368, 131031, 133010}
_CODIGOS_NUMERO = {100, 131021, 131026, 131030, 131049, 131050, 131051}
_CODIGOS_LIMITE = {4, 80007, 130429, 131048, 131056}


class FalhaGraph(Exception):
    def __init__(self, status: int | None, codigo: int | None, detalhe: str):
        super().__init__(detalhe)
        self.status = status
        self.codigo = codigo


def traduzir(status: int | None, codigo: int | None) -> tuple[str, bool]:
    """(texto simples, é problema da conexão da conta e não do destinatário)."""
    if status == 401 or codigo in _CODIGOS_TOKEN:
        return MSG_TOKEN, True
    if codigo is not None and 132000 <= codigo < 133000:
        return MSG_MODELO, True
    if codigo in _CODIGOS_CONTA:
        return MSG_CONTA, True
    if codigo in _CODIGOS_LIMITE or status == 429:
        return MSG_LIMITE, False
    if codigo in _CODIGOS_NUMERO:
        return MSG_NUMERO, False
    if status is None or status >= 500:
        return MSG_FORA_DO_AR, False
    return MSG_RECUSOU, False


def chamar(token: str, metodo: str, caminho: str, **kw) -> dict:
    cfg = config()
    base = f"{cfg.WHATSAPP_GRAPH_URL.rstrip('/')}/{cfg.WHATSAPP_GRAPH_VERSION}"
    try:
        with httpx.Client(base_url=base, timeout=10, follow_redirects=False, transport=transporte,
                          headers={"Authorization": f"Bearer {token}"}) as c:
            r = c.request(metodo, caminho, **kw)
    except httpx.HTTPError as e:
        log.warning("Falha de rede na Graph API (%s %s): %r", metodo, caminho, e)
        raise FalhaGraph(None, None, repr(e)) from e
    try:
        dados = r.json()
    except ValueError:
        dados = {}
    if r.status_code >= 400 or not isinstance(dados, dict) or "error" in dados:
        erro = dados.get("error") if isinstance(dados, dict) else None
        erro = erro if isinstance(erro, dict) else {}
        codigo = erro.get("code") if isinstance(erro.get("code"), int) else None
        detalhe = str(erro.get("message") or r.text[:300])
        log.warning("Graph API recusou %s %s (HTTP %s, código %s): %s", metodo, caminho, r.status_code, codigo, detalhe)
        raise FalhaGraph(r.status_code, codigo, detalhe)
    return dados


def dados_do_numero(token: str, phone_number_id: str) -> dict:
    return chamar(token, "GET", f"/{phone_number_id}", params={"fields": "display_phone_number,verified_name"})


def modelos(token: str, waba_id: str, nome: str) -> list[dict]:
    dados = chamar(token, "GET", f"/{waba_id}/message_templates",
                   params={"name": nome, "fields": "name,language,status,category,components", "limit": 50})
    return [m for m in dados.get("data") or [] if isinstance(m, dict)]


def enviar_mensagem(token: str, phone_number_id: str, corpo: dict) -> str:
    """Envia e devolve o wamid."""
    dados = chamar(token, "POST", f"/{phone_number_id}/messages", json=corpo)
    try:
        return str(dados["messages"][0]["id"])
    except (KeyError, IndexError, TypeError):
        raise FalhaGraph(200, None, "Resposta sem o id da mensagem.")
