"""Cliente da API v3 do Bling (OAuth 2 do aplicativo do Toqqi). O cliente autoriza o Toqqi no Bling; o Toqqi guarda o
access token (curto) e o refresh token (até 30 dias, renovado a cada uso) e chama a API com `Authorization: Bearer`.
Os avisos (webhooks) são do aplicativo: chegam todos ao mesmo endereço, com o `companyId` da empresa no Bling e a
assinatura `X-Bling-Signature-256` (HMAC-SHA256 do corpo com o client secret do aplicativo)."""
import base64
import hashlib
import hmac
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from toqqi.core.config import config

TEMPO = httpx.Timeout(20.0, connect=10.0)
POR_PAGINA = 100
PAUSA = 0.35  # o Bling aceita 3 pedidos por segundo


class ErroBling(Exception):
    """Falha ao falar com o Bling (mensagem pronta para a tela)."""


def disponivel() -> bool:
    cfg = config()
    return bool(cfg.BLING_CLIENT_ID and cfg.BLING_CLIENT_SECRET)


def url_autorizar(state: str) -> str:
    cfg = config()
    return str(httpx.URL(cfg.BLING_AUTORIZAR_URL, params={"response_type": "code", "client_id": cfg.BLING_CLIENT_ID,
                                                           "state": state}))


def _basic() -> str:
    cfg = config()
    return "Basic " + base64.b64encode(f"{cfg.BLING_CLIENT_ID}:{cfg.BLING_CLIENT_SECRET}".encode()).decode()


def _tokens(corpo: dict) -> dict:
    try:
        r = httpx.post(f"{config().BLING_API_URL}/oauth/token", data=corpo, timeout=TEMPO,
                       headers={"Authorization": _basic(), "Accept": "1.0"})
    except httpx.HTTPError:
        raise ErroBling("Não conseguimos falar com o Bling. Tente de novo em instantes.")
    if r.status_code >= 400:
        raise ErroBling("O Bling recusou a autorização. Conecte de novo.")
    d = r.json()
    expira = datetime.now(timezone.utc) + timedelta(seconds=int(d.get("expires_in") or 3600) - 60)
    return {"access": d["access_token"], "refresh": d.get("refresh_token"), "expira": expira.isoformat()}


def trocar_codigo(codigo: str) -> dict:
    return _tokens({"grant_type": "authorization_code", "code": codigo})


def renovar(refresh: str) -> dict:
    return _tokens({"grant_type": "refresh_token", "refresh_token": refresh})


def vencido(tokens: dict) -> bool:
    try:
        return datetime.fromisoformat(tokens["expira"]) <= datetime.now(timezone.utc)
    except (KeyError, ValueError, TypeError):
        return True


def pedir(tokens: dict, caminho: str, params: dict | None = None) -> dict:
    """GET na API v3 com o access token (quem chama renova antes, se `vencido`)."""
    try:
        r = httpx.get(f"{config().BLING_API_URL}{caminho}", params=params, timeout=TEMPO,
                      headers={"Authorization": f"Bearer {tokens['access']}"})
    except httpx.HTTPError:
        raise ErroBling("Não conseguimos falar com o Bling. Tente de novo em instantes.")
    if r.status_code == 401:
        raise ErroBling("O Bling recusou o acesso. Conecte de novo.")
    if r.status_code == 429:
        time.sleep(1)
        return pedir(tokens, caminho, params)
    if r.status_code == 404:
        return {}
    if r.status_code >= 400:
        raise ErroBling(f"O Bling respondeu com erro ({r.status_code}).")
    return r.json() if r.content else {}


def empresa(tokens: dict) -> str | None:
    d = pedir(tokens, "/empresas/me/dados-basicos").get("data") or {}
    return str(d.get("id")) if d.get("id") else None


def contatos(tokens: dict, maximo: int):
    pagina, total = 1, 0
    while total < maximo:
        itens = pedir(tokens, "/contatos", {"pagina": pagina, "limite": POR_PAGINA}).get("data") or []
        for item in itens:
            yield item
            total += 1
            if total >= maximo:
                return
        if len(itens) < POR_PAGINA:
            return
        pagina += 1
        time.sleep(PAUSA)


def contato(tokens: dict, contato_id: str) -> dict:
    time.sleep(PAUSA)
    return pedir(tokens, f"/contatos/{contato_id}").get("data") or {}


def assinatura_valida(corpo: bytes, assinatura: str | None) -> bool:
    if not assinatura or not config().BLING_CLIENT_SECRET:
        return False
    esperado = "sha256=" + hmac.new(config().BLING_CLIENT_SECRET.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, assinatura.strip())


# ---- leitura dos campos ---------------------------------------------------------------------

def ativo(c: dict) -> bool:
    return str(c.get("situacao") or "A").upper() == "A"


def documento(c: dict) -> str | None:
    d = re.sub(r"[^0-9A-Za-z]", "", str(c.get("numeroDocumento") or "")).upper()
    return d if len(d) in (11, 14) else None


def email(c: dict) -> str | None:
    for campo in ("email", "emailNotaFiscal"):
        v = str(c.get(campo) or "").strip().lower()
        if "@" in v:
            return v.split(";")[0].split(",")[0].strip()
    return None


def telefone(c: dict) -> str | None:
    for campo in ("celular", "telefone"):
        v = re.sub(r"\D", "", str(c.get(campo) or ""))
        if len(v) >= 10:
            return v
    return None


def contato_do_aviso(dados: dict) -> str | None:
    c = dados.get("contato") if isinstance(dados.get("contato"), dict) else {}
    v = c.get("id") or dados.get("idContato")
    return str(v) if v else None


EVENTOS_PESQUISA = ("invoice.created", "consumer_invoice.created")
