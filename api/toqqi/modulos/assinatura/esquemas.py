"""Entradas da assinatura. Dados de cobrança validados como em Dados da empresa (CPF/CNPJ pelos dígitos
verificadores, inclusive o CNPJ alfanumérico; e-mail; telefone com DDD), mas todos obrigatórios. O telefone segue a
regra brasileira, mais estrita que a dos Dados da empresa (o Asaas pede DDD + número, sem o 55): DDD de 11 a 99 e
celular com 9 dígitos começando com 9 ou fixo com 8 dígitos começando com 2 a 5."""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator
from pydantic_core import PydanticCustomError

from toqqi.core.texto import normalizar_documento, normalizar_telefone, telefone_canonico
from toqqi.core.validacao import _validar_email

Plano = Literal["essencial", "profissional", "empresa"]
MAX_RAZAO_SOCIAL = 200
RE_TELEFONE_BR = re.compile(r"55([1-9][0-9])(9[0-9]{8}|[2-5][0-9]{7})")  # 55 + DDD + celular ou fixo
MSG_TELEFONE_BR = "Informe um telefone do Brasil com DDD."


def _erro(tipo: str, msg: str) -> PydanticCustomError:
    return PydanticCustomError(f"toqqi_{tipo}", msg)


def _vazio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _razao_social(v):
    if _vazio(v) or not isinstance(v, str):
        raise _erro("razao_social", "Informe a razão social (ou o nome completo, para CPF).")
    v = " ".join(v.split())
    if len(v) > MAX_RAZAO_SOCIAL:
        raise _erro("razao_social", f"Use no máximo {MAX_RAZAO_SOCIAL} caracteres.")
    return v


def _documento(v):
    if _vazio(v) or not isinstance(v, str):
        raise _erro("documento", "Informe o CPF ou o CNPJ.")
    try:
        return normalizar_documento(v)
    except ValueError as e:
        raise _erro("documento", str(e))


def _email(v):
    if _vazio(v) or not isinstance(v, str):
        raise _erro("email", "Informe o e-mail que recebe as faturas.")
    return _validar_email(v)


def _telefone(v):
    if _vazio(v) or not isinstance(v, (str, int)):
        raise _erro("telefone", "Informe o telefone com DDD.")
    try:
        d = telefone_canonico(normalizar_telefone(str(v)))
    except ValueError as e:
        raise _erro("telefone", str(e))
    m = RE_TELEFONE_BR.fullmatch(d)
    if m is None or not 11 <= int(m.group(1)) <= 99:
        raise _erro("telefone", MSG_TELEFONE_BR)
    return d


class DadosCobrancaIn(BaseModel):
    """PUT /assinatura/dados (e a parte de cobrança de POST /assinatura)."""
    razao_social: Annotated[str, BeforeValidator(_razao_social)]
    documento: Annotated[str, BeforeValidator(_documento)]
    email_cobranca: Annotated[str, BeforeValidator(_email)]
    telefone: Annotated[str, BeforeValidator(_telefone)]


class AssinarIn(DadosCobrancaIn):
    plano: Plano


class PlanoIn(BaseModel):
    plano: Plano
