from typing import Annotated

from pydantic import BaseModel, Field


class SegurancaIn(BaseModel):
    sessao_minutos: Annotated[int, Field(ge=30, le=1440)]
    dominios: list[Annotated[str, Field(max_length=253)]] = Field(default_factory=list, max_length=50)
