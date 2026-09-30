from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ConferirIn(BaseModel):
    mapeamento: Annotated[dict[str, str | None], Field(max_length=200)]
    chave: Literal["email", "codigo_externo", "telefone"] = "email"
    atualizar_existentes: bool = False
    grupo_id: int | None = None


class ImportarIn(ConferirIn):
    ignorar_com_problema: bool = False
