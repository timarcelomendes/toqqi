from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import Texto
from toqqi.modulos.formularios.modelos import MODELOS

ChaveModelo = Literal[tuple(MODELOS)]  # type: ignore[valid-type]
Nome = Annotated[Texto, Field(min_length=1, max_length=120)]
Descricao = Annotated[Texto, Field(max_length=500)]


class FormularioIn(BaseModel):
    nome: Nome
    descricao: Descricao | None = None
    modelo: ChaveModelo | None = None
    perguntas: list[Any] | None = None
    tema: dict[str, Any] | None = None


class FormularioAlterarIn(BaseModel):
    nome: Nome | None = None
    descricao: Descricao | None = None
    perguntas: list[Any] | None = None
    tema: dict[str, Any] | None = None
    ativo: bool | None = None
    publico: bool | None = None


class PadraoIn(BaseModel):
    uso: Literal["nps", "csat"]
