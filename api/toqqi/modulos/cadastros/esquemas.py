from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError

from toqqi.core.rede import EnderecoProibido, conferir_url_https
from toqqi.core.validacao import EmailOpcional, Texto, TextoAte


def _webhook(v: str | None) -> str | None:
    if v is None:
        return None
    try:
        return conferir_url_https(v)
    except EnderecoProibido as e:
        raise PydanticCustomError("toqqi_webhook", f"{e} Use o endereço gerado pelo Teams (https://...).")


def _https(v: str | None) -> str | None:
    if v is not None and not v.startswith("https://"):
        raise PydanticCustomError("toqqi_url", "Use um endereço https://.")
    return v


class ItemIn(BaseModel):
    nome: Annotated[Texto, Field(min_length=1, max_length=80)]


class ResponsavelIn(BaseModel):
    nome: Annotated[Texto, Field(min_length=2, max_length=120)]
    funcao: TextoAte(80) = None
    email: EmailOpcional = None
    foto_url: Annotated[TextoAte(500), AfterValidator(_https)] = None
    teams_webhook: Annotated[TextoAte(1000), AfterValidator(_webhook)] = None


class ResponsavelAlterarIn(BaseModel):
    nome: Annotated[Texto, Field(min_length=2, max_length=120)] | None = None
    funcao: TextoAte(80) = None
    email: EmailOpcional = None
    foto_url: Annotated[TextoAte(500), AfterValidator(_https)] = None
    teams_webhook: Annotated[TextoAte(1000), AfterValidator(_webhook)] = None
