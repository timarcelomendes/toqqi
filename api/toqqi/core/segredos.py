"""Segredos guardados no banco (token do WhatsApp, segredos de webhooks), cifrados com Fernet.

A chave é sha256(SEGREDOS_KEY) em base64 url-safe. Fora de produção, sem SEGREDOS_KEY, usa o JWT_SECRET.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from toqqi.core.config import config
from toqqi.core.errors import AppError


def _fernet() -> Fernet:
    cfg = config()
    segredo = cfg.SEGREDOS_KEY or (cfg.JWT_SECRET if cfg.AMBIENTE != "producao" else "")
    if not segredo:
        raise AppError(409, "segredos_indisponivel",
                       "O armazenamento seguro de credenciais ainda não foi configurado na plataforma.")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(segredo.encode()).digest()))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(cifrado: str) -> str | None:
    """None se a chave mudou (o segredo precisa ser cadastrado de novo)."""
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken:
        return None
