from typing import Annotated, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import Email, SenhaForte, Texto


class NovaContaIn(BaseModel):
    empresa: Annotated[Texto, Field(min_length=2, max_length=120)]
    admin_nome: Annotated[Texto, Field(min_length=2, max_length=120)]
    admin_email: Email
    admin_senha: SenhaForte
    situacao: Literal["teste", "cortesia"] = "teste"


class EstenderTesteIn(BaseModel):
    dias: Annotated[int, Field(ge=1, le=365)] = 14
