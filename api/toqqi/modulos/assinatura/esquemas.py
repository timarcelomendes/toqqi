"""Entradas da assinatura. Dados de cobrança validados como em Dados da empresa (CPF/CNPJ pelos dígitos
verificadores, inclusive o CNPJ alfanumérico; e-mail; telefone com DDD), mas todos obrigatórios. O telefone segue a
regra brasileira, mais estrita que a dos Dados da empresa (o Asaas pede DDD + número, sem o 55): DDD de 11 a 99 e
celular com 9 dígitos começando com 9 ou fixo com 8 dígitos começando com 2 a 5."""
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator
from pydantic_core import PydanticCustomError

from toqqi.core.texto import normalizar_documento
from toqqi.core.validacao import _validar_email, telefone_br

Plano = Literal["essencial", "profissional", "empresa"]
MAX_RAZAO_SOCIAL = 200


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
        return telefone_br(v)  # a regra brasileira de sempre (core.validacao)
    except ValueError as e:
        raise _erro("telefone", str(e))


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
