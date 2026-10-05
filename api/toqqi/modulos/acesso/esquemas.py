from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, StrictBool
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
    origem: Any = None  # etapa 5i: {utm_source, utm_medium, utm_campaign}; limpo no cadastro, nunca dá 422


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
    recebe_resumo_semanal: bool | None = None
    recebe_alertas: bool | None = None


class TrocarSenhaIn(BaseModel):
    senha_atual: Annotated[str, Field(min_length=1, max_length=200)]
    senha_nova: SenhaForte


class AceiteIn(BaseModel):
    versao: Annotated[int, Field(ge=1, le=1_000_000)]


def _confirmar_obrigatorio(v: bool | None) -> bool:
    if v is not True:
        raise PydanticCustomError("toqqi_confirmar", "Confirme que quer retirar o aceite.")
    return v


class RevogarAceiteIn(BaseModel):
    # StrictBool: só `true` de verdade (não "yes", "true" nem 1); ausente cai na mesma mensagem.
    confirmar: Annotated[StrictBool | None, AfterValidator(_confirmar_obrigatorio)] = Field(default=None,
                                                                                            validate_default=True)


class Mensagem(BaseModel):
    mensagem: str
