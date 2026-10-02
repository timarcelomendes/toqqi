import unicodedata
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator
from pydantic_core import PydanticCustomError

MAX_PERGUNTA = 1000
MAX_TEXTO_HISTORICO = 4000
MAX_HISTORICO = 8


def limpar(v):
    """Sem caracteres de controle (menos a quebra de linha; tab vira espaço) e sem espaços nas pontas."""
    if not isinstance(v, str):
        return v
    v = v.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    return "".join(ch for ch in v if ch == "\n" or unicodedata.category(ch) not in ("Cc", "Cs")).strip()


def _tamanho(maximo: int, vazio: str, longo: str):
    def conferir(v: str) -> str:
        if not v:
            raise PydanticCustomError("toqqi_texto", vazio)
        if len(v) > maximo:
            raise PydanticCustomError("toqqi_texto", longo)
        return v
    return conferir


Pergunta = Annotated[str, BeforeValidator(limpar), AfterValidator(_tamanho(
    MAX_PERGUNTA, "Escreva a sua pergunta.", "A pergunta pode ter até 1.000 caracteres."))]
TextoHistorico = Annotated[str, BeforeValidator(limpar), AfterValidator(_tamanho(
    MAX_TEXTO_HISTORICO, "Mensagem vazia no histórico.", "Cada mensagem do histórico pode ter até 4.000 caracteres."))]


class MensagemIn(BaseModel):
    papel: Literal["usuario", "assistente"]
    texto: TextoHistorico


def _ate_8(v):
    """Antes de validar cada item: mais de 8 mensagens já é erro."""
    if isinstance(v, list) and len(v) > MAX_HISTORICO:
        raise PydanticCustomError("toqqi_historico", "Envie até 8 mensagens do histórico.")
    return v


class PerguntaIn(BaseModel):
    pergunta: Pergunta
    historico: Annotated[list[MensagemIn] | None, BeforeValidator(_ate_8)] = None  # null = sem histórico
