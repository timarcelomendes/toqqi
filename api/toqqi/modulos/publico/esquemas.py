from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import TextoOpcional


class ResponderIn(BaseModel):
    respostas: Annotated[dict[str, Any], Field(max_length=200)]


class ResponderLinkIn(ResponderIn):
    canal: Literal["link", "qr", "widget"] = "link"
    referencia: Annotated[TextoOpcional, Field(max_length=120)] = None
    contexto: Annotated[dict[str, Any], Field(max_length=20)] | None = None
