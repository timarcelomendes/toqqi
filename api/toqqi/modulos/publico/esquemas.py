from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from toqqi.core.validacao import TextoAte


class ResponderIn(BaseModel):
    respostas: Annotated[dict[str, Any], Field(max_length=200)]


class ResponderLinkIn(ResponderIn):
    canal: Literal["link", "qr", "widget"] = "link"
    referencia: TextoAte(120) = None
    contexto: Annotated[dict[str, Any], Field(max_length=20)] | None = None


class ErroSiteIn(BaseModel):
    """POST /publico/erros (etapa 5h): um erro do site. O corpo inteiro vai até 4 KB (`main.LIMITES_DE_CORPO`); a API
    limpa e corta cada texto (`core.erros`) antes de gravar."""
    tipo: Annotated[str, Field(min_length=1, max_length=200)]
    mensagem: Annotated[str, Field(max_length=2000)] = ""
    local: Annotated[str, Field(max_length=1000)] = ""
    pilha: Annotated[str, Field(max_length=4000)] = ""
    versao: Annotated[str, Field(max_length=40, pattern=r"^[0-9A-Za-z._-]*$")] = ""
