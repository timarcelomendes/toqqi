"""Tipos Pydantic reutilizáveis com mensagens em português."""
import re
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BeforeValidator
from pydantic_core import PydanticCustomError

from toqqi.core.security import mensagem_senha_fraca, problemas_senha

DOMINIOS_GRATUITOS = frozenset({
    "gmail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "yahoo.com.br",
    "icloud.com", "bol.com.br", "uol.com.br", "terra.com.br", "ig.com.br", "protonmail.com",
})

_RE_DOMINIO = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def normalizar_email(v: str) -> str:
    return v.strip().lower()


def _validar_email(v: str) -> str:
    v = normalizar_email(v)
    try:
        validate_email(v, check_deliverability=False)
    except EmailNotValidError:
        raise PydanticCustomError("toqqi_email", "Informe um e-mail válido, como nome@empresa.com.br.")
    if len(v) > 254:
        raise PydanticCustomError("toqqi_email", "Este e-mail é longo demais.")
    return v


def _validar_senha(v: str) -> str:
    faltas = problemas_senha(v)
    if faltas:
        raise PydanticCustomError("toqqi_senha", mensagem_senha_fraca(faltas))
    return v


def _texto_limpo(v):
    return v.strip() if isinstance(v, str) else v


def dominio_valido(d: str) -> bool:
    return bool(_RE_DOMINIO.match(d))


def normalizar_dominio(d: str) -> str:
    d = d.strip().lower()
    if d.startswith("@"):
        d = d[1:]
    return d


def dominio_do_email(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


Email = Annotated[str, AfterValidator(_validar_email)]
SenhaForte = Annotated[str, AfterValidator(_validar_senha)]
Texto = Annotated[str, BeforeValidator(_texto_limpo)]


def _validar_telefone(v):
    from toqqi.core.texto import normalizar_telefone

    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return normalizar_telefone(str(v))
    except ValueError as e:
        raise PydanticCustomError("toqqi_telefone", str(e))


def _validar_documento(v):
    from toqqi.core.texto import normalizar_documento

    if v is None:
        return None
    try:
        return normalizar_documento(str(v))
    except ValueError as e:
        raise PydanticCustomError("toqqi_documento", str(e))


def _email_opcional(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return _validar_email(v)


def _vazio_para_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


Telefone = Annotated[str | None, BeforeValidator(_validar_telefone)]
Documento = Annotated[str | None, BeforeValidator(_validar_documento)]
EmailOpcional = Annotated[str | None, BeforeValidator(_email_opcional)]
TextoOpcional = Annotated[str | None, BeforeValidator(_vazio_para_none)]
