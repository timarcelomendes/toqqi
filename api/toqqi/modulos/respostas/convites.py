"""Convites individuais para responder uma pesquisa (link com token de uso único).

No banco fica só o sha256 do token. Convites por e-mail/WhatsApp guardam também uma semente aleatória:
o token é HMAC(JWT_SECRET, semente), para o lembrete reenviar o mesmo link. Só com o banco não dá para
montar o link.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from toqqi.core.config import config
from toqqi.core.security import hash_token, novo_token_uso_unico
from toqqi.modelos import Contato, Convite

CANAIS_CONVITE = ("email", "whatsapp", "link_manual")
# canal do convite → canal gravado na resposta
CANAL_RESPOSTA = {"email": "email", "whatsapp": "whatsapp", "link_manual": "link"}
CHAVES_CONTEXTO = ("pedido", "nota_fiscal", "rota", "motorista", "filial", "transportadora")
MAX_CONTEXTO = 120


def limpar_contexto(contexto: dict | None) -> dict:
    """Só as chaves conhecidas, como texto de até 120 caracteres; vazias são descartadas."""
    saida = {}
    for k in CHAVES_CONTEXTO:
        v = (contexto or {}).get(k)
        if v is None or isinstance(v, (dict, list)):
            continue
        v = str(v).strip()[:MAX_CONTEXTO]
        if v:
            saida[k] = v
    return saida


def link_do_convite(token: str) -> str:
    return f"{config().FRONTEND_URL.rstrip('/')}/r/{token}"


def token_do_convite(semente: str) -> str:
    """Token do link de um convite com semente (e-mail/WhatsApp)."""
    mac = hmac.new(config().JWT_SECRET.encode(), f"convite|{semente}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def novo_convite(
    s: Session,
    formulario_id: int,
    contato_id: int | None = None,
    canal: str = "link_manual",
    assunto: str | None = None,
    referencia: str | None = None,
    contexto: dict | None = None,
    empresa_id: int | None = None,
    criado_em: datetime | None = None,
) -> tuple[Convite, str]:
    """Cria o convite na conta da transação e devolve (convite, token)."""
    assert canal in CANAIS_CONVITE
    if contato_id is not None and empresa_id is None:
        c = s.get(Contato, contato_id)
        empresa_id = c.empresa_id if c else None
    semente = None
    if canal in ("email", "whatsapp"):
        semente = secrets.token_urlsafe(16)
        token = token_do_convite(semente)
        h = hash_token(token)
    else:
        token, h = novo_token_uso_unico()
    extras = {"criado_em": criado_em} if criado_em else {}
    convite = Convite(token_hash=h, token_semente=semente, formulario_id=formulario_id, contato_id=contato_id,
                      empresa_id=empresa_id, canal=canal, assunto=(assunto or None), referencia=(referencia or None),
                      contexto=limpar_contexto(contexto), **extras)
    s.add(convite)
    s.flush()
    return convite, token


def criar_convite(s: Session, formulario_id: int, **campos) -> str:
    """Como `novo_convite`, devolvendo só o token (mostrado só agora)."""
    return novo_convite(s, formulario_id, **campos)[1]
