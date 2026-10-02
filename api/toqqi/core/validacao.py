"""Tipos Pydantic reutilizáveis com mensagens em português."""
import re
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BeforeValidator, Field
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

# ids são bigint: fora de 1..2^63−1 o banco recusaria a consulta (DataError). `IdBanco` para ids no corpo; nas rotas,
# Path(ge=1, le=MAX_ID).
MAX_ID = 2**63 - 1
IdBanco = Annotated[int, Field(ge=1, le=MAX_ID)]


def _validar_telefone(v):
    from toqqi.core.texto import normalizar_telefone

    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return normalizar_telefone(str(v))
    except ValueError as e:
        raise PydanticCustomError("toqqi_telefone", str(e))


# Telefone do Brasil (a regra da cobrança e das indicações): DDD de 11 a 99 e celular com 9 dígitos começando com 9 ou
# fixo com 8 dígitos começando com 2 a 5; guardado só com dígitos, com 55 (celular sempre com o nono dígito).
RE_TELEFONE_BR = re.compile(r"55([1-9][0-9])(9[0-9]{8}|[2-5][0-9]{7})")  # 55 + DDD + celular ou fixo
MSG_TELEFONE_BR = "Informe um telefone do Brasil com DDD."


def telefone_br(v) -> str:
    """Telefone do Brasil (celular ou fixo) → só dígitos, com 55. Levanta ValueError com o texto para a tela."""
    from toqqi.core.texto import normalizar_telefone, telefone_canonico

    d = telefone_canonico(normalizar_telefone(str(v)))
    m = RE_TELEFONE_BR.fullmatch(d)
    if m is None or not 11 <= int(m.group(1)) <= 99:
        raise ValueError(MSG_TELEFONE_BR)
    return d


def _telefone_br_opcional(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if not isinstance(v, (str, int)) or isinstance(v, bool):
        raise PydanticCustomError("toqqi_telefone", MSG_TELEFONE_BR)
    try:
        return telefone_br(v)
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
    if not isinstance(v, str):  # número, lista, objeto: 422 no campo (e não AttributeError no .strip())
        raise PydanticCustomError("toqqi_email", "Informe um e-mail válido, como nome@empresa.com.br.")
    return _validar_email(v)


def _vazio_para_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


Telefone = Annotated[str | None, BeforeValidator(_validar_telefone)]
TelefoneBr = Annotated[str | None, BeforeValidator(_telefone_br_opcional)]  # opcional; vazio = None
Documento = Annotated[str | None, BeforeValidator(_validar_documento)]
EmailOpcional = Annotated[str | None, BeforeValidator(_email_opcional)]
TextoOpcional = Annotated[str | None, BeforeValidator(_vazio_para_none)]


def TextoAte(maximo: int):  # noqa: N802 - usado como tipo
    """Texto opcional com tamanho máximo; vazio ou nulo vira None (o limite só vale para texto)."""
    return Annotated[Annotated[str, Field(max_length=maximo)] | None, BeforeValidator(_vazio_para_none)]
