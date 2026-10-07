from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import Texto
from toqqi.modulos.formularios.modelos import MODELOS

ChaveModelo = Literal[tuple(MODELOS)]  # type: ignore[valid-type]
Nome = Annotated[Texto, Field(min_length=1, max_length=120)]
Descricao = Annotated[Texto, Field(max_length=500)]


Rev = Annotated[int, Field(ge=0, le=2**31 - 1)]


class FormularioIn(BaseModel):
    nome: Nome
    descricao: Descricao | None = None
    modelo: ChaveModelo | None = None
    perguntas: list[Any] | None = None
    tema: dict[str, Any] | None = None
    finais: list[Any] | None = None


class FormularioAlterarIn(BaseModel):
    nome: Nome | None = None
    descricao: Descricao | None = None
    perguntas: list[Any] | None = None
    tema: dict[str, Any] | None = None
    finais: list[Any] | None = None
    ativo: bool | None = None
    publico: bool | None = None
    permite_editar: bool | None = None  # o cliente pode mudar a resposta (docs/api-editar-resposta.md)


class RascunhoIn(BaseModel):
    """PUT /formularios/{id}/rascunho (etapa 5l): `rev` que o editor conhece e o documento em edição (o que faltar
    vem do rascunho atual, ou do publicado)."""
    rev: Rev
    perguntas: list[Any] | None = None
    tema: dict[str, Any] | None = None
    finais: list[Any] | None = None


class PublicarIn(BaseModel):
    rev: Rev


class PadraoIn(BaseModel):
    uso: Literal["nps", "csat"]
