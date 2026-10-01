from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import TextoAte


class ResponderIn(BaseModel):
    respostas: Annotated[dict[str, Any], Field(max_length=200)]


class ResponderLinkIn(ResponderIn):
    canal: Literal["link", "qr", "widget"] = "link"
    referencia: TextoAte(120) = None
    contexto: Annotated[dict[str, Any], Field(max_length=20)] | None = None
