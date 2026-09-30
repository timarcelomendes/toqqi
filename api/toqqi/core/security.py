"""Senhas (argon2id), tokens de acesso (JWT HS256) e tokens de uso único."""
import hashlib
import secrets
import uuid
from datetime import datetime

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from toqqi.core.config import config

SENHA_MIN = 8
SENHA_MAX = 70

_hasher = PasswordHasher()  # argon2id com os parâmetros recomendados pela biblioteca
# Hash de uma senha aleatória: usado para gastar o mesmo tempo quando o e-mail não existe.
_HASH_FICTICIO = _hasher.hash(secrets.token_urlsafe(16))


def problemas_senha(senha: str) -> list[str]:
    """Lista, em português, o que falta na senha. Vazia = senha aceita."""
    faltas = []
    if len(senha) < SENHA_MIN:
        faltas.append(f"pelo menos {SENHA_MIN} caracteres")
    if len(senha) > SENHA_MAX:
        faltas.append(f"no máximo {SENHA_MAX} caracteres")
    if not any(c.isupper() for c in senha):
        faltas.append("uma letra maiúscula")
    if not any(c.isdigit() for c in senha):
        faltas.append("um número")
    if all(c.isalnum() for c in senha):
        faltas.append("um símbolo (ex.: ! @ # $)")
    return faltas


def mensagem_senha_fraca(faltas: list[str]) -> str:
    if len(faltas) == 1:
        lista = faltas[0]
    else:
        lista = ", ".join(faltas[:-1]) + " e " + faltas[-1]
    return f"A senha precisa ter {lista}."


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def conferir_senha(hash_: str | None, senha: str) -> bool:
    if not hash_:
        gastar_tempo(senha)
        return False
    try:
        return _hasher.verify(hash_, senha)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def gastar_tempo(senha: str) -> None:
    """Executa uma verificação argon2 descartável (iguala o tempo de resposta)."""
    try:
        _hasher.verify(_HASH_FICTICIO, senha)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass


def precisa_rehash(hash_: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hash_)
    except InvalidHashError:
        return True


# ---- tokens de acesso -------------------------------------------------------

def criar_token_acesso(usuario_id: int, conta_id: int, sessao_id: uuid.UUID, expira_em: datetime) -> str:
    payload = {
        "sub": str(usuario_id),
        "cid": conta_id,
        "sid": str(sessao_id),
        "exp": int(expira_em.timestamp()),
    }
    return jwt.encode(payload, config().JWT_SECRET, algorithm="HS256")


def ler_token_acesso(token: str) -> dict | None:
    """Devolve {usuario_id, conta_id, sessao_id} ou None se inválido/expirado."""
    try:
        p = jwt.decode(token, config().JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        return {"usuario_id": int(p["sub"]), "conta_id": int(p["cid"]), "sessao_id": uuid.UUID(p["sid"])}
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


# ---- tokens de uso único (links de e-mail) ----------------------------------

def novo_token_uso_unico() -> tuple[str, str]:
    """Devolve (token para o link, hash sha256 para guardar no banco)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- descrição amigável do aparelho -----------------------------------------

def descrever_aparelho(agente: str | None) -> str:
    ua = (agente or "").lower()
    if not ua:
        return "Aparelho desconhecido"
    if "edg/" in ua:
        nav = "Edge"
    elif "opr/" in ua or "opera" in ua:
        nav = "Opera"
    elif "firefox/" in ua:
        nav = "Firefox"
    elif "chrome/" in ua or "crios/" in ua:
        nav = "Chrome"
    elif "safari/" in ua:
        nav = "Safari"
    else:
        nav = "Navegador"
    if "iphone" in ua:
        so = "iPhone"
    elif "ipad" in ua:
        so = "iPad"
    elif "android" in ua:
        so = "Android"
    elif "windows" in ua:
        so = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        so = "Mac"
    elif "linux" in ua:
        so = "Linux"
    else:
        so = None
    return f"{nav} no {so}" if so else nav
