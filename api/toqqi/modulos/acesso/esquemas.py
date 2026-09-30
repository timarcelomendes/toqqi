from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError

from toqqi.core.validacao import Email, SenhaForte, Texto, normalizar_email


def _aceite_obrigatorio(v: bool) -> bool:
    if v is not True:
        raise PydanticCustomError("toqqi_termos", "Para criar a conta, é preciso aceitar os termos de uso.")
    return v


class CadastroIn(BaseModel):
    empresa: Annotated[Texto, Field(min_length=2, max_length=120)]
    nome: Annotated[Texto, Field(min_length=2, max_length=120)]
    email: Email
    senha: SenhaForte
    telefone: Annotated[Texto, Field(max_length=30)] | None = None
    aceite_termos: Annotated[bool, AfterValidator(_aceite_obrigatorio)]


class EntrarIn(BaseModel):
    email: Annotated[str, AfterValidator(normalizar_email), Field(min_length=1, max_length=254)]
    senha: Annotated[str, Field(min_length=1, max_length=200)]
    lembrar: bool = False


class TokenIn(BaseModel):
    token: Annotated[str, Field(min_length=1, max_length=200)]


class EmailIn(BaseModel):
    email: Email


class RedefinirIn(BaseModel):
    token: Annotated[str, Field(min_length=1, max_length=200)]
    senha: SenhaForte


class PedirAcessoIn(BaseModel):
    nome: Annotated[Texto, Field(min_length=2, max_length=120)]
    email: Email
    senha: SenhaForte


class EuAlterarIn(BaseModel):
    nome: Annotated[Texto, Field(min_length=2, max_length=120)] | None = None
    cargo: Annotated[Texto, Field(max_length=80)] | None = None


class TrocarSenhaIn(BaseModel):
    senha_atual: Annotated[str, Field(min_length=1, max_length=200)]
    senha_nova: SenhaForte


class Mensagem(BaseModel):
    mensagem: str
