import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError

from toqqi.core.validacao import Telefone, Texto


def _padrao(regex: str, mensagem: str):
    def conferir(v: str) -> str:
        if not re.fullmatch(regex, v):
            raise PydanticCustomError("toqqi_whatsapp", mensagem)
        return v
    return AfterValidator(conferir)


IdMeta = Annotated[Texto, _padrao(r"[0-9]{5,30}",
                                  "Use só os números do identificador, como aparece no painel da Meta.")]


class ConectarIn(BaseModel):
    phone_number_id: IdMeta
    waba_id: IdMeta
    token: Annotated[Texto, Field(min_length=20, max_length=1000)]
    modelo_nome: Annotated[Texto, _padrao(r"[a-z0-9_]{1,512}",
                                          "Use o nome do modelo como está no WhatsApp Manager (minúsculas e _).")]
    modelo_idioma: Annotated[Texto, _padrao(r"[a-z]{2,3}(_[A-Z]{2})?", "Use o código do idioma, como pt_BR.")] = "pt_BR"


class AlterarIn(BaseModel):
    ativo: bool | None = None
    excedente_ativo: bool | None = None


def _obrigatorio(v: str | None) -> str:
    if not v:
        raise PydanticCustomError("toqqi_telefone", "Informe o telefone com DDD.")
    return v


class TesteIn(BaseModel):
    telefone: Annotated[Telefone, AfterValidator(_obrigatorio)]


class RegistrarIn(BaseModel):
    """Registro do número na Meta: o PIN de 6 dígitos da verificação em duas etapas (não é guardado)."""
    pin: Annotated[Texto, _padrao(r"[0-9]{6}", "O PIN tem 6 números.")]
