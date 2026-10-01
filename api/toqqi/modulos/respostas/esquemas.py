from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field
from pydantic_core import PydanticCustomError

from toqqi.core.filtros import DataFiltro
from toqqi.core.validacao import TextoAte
from toqqi.modulos.respostas.temas import CHAVES

CANAIS = ("email", "whatsapp", "link", "qr", "widget", "api", "importacao", "manual", "telefone", "reuniao")
CANAIS_MANUAIS = ("manual", "whatsapp", "telefone", "email", "reuniao")
CATEGORIAS = ("detrator", "neutro", "promotor", "insatisfeito", "satisfeito")
ORIGENS = ("pesquisa", "manual", "importacao")

Tema = Literal[CHAVES]  # type: ignore[valid-type]


def _vazio_none(v):
    return None if v == "" else v


Opcional = BeforeValidator(_vazio_none)
Busca = Annotated[Annotated[str, Field(max_length=100)] | None, Opcional]
Id = Annotated[int | None, Opcional]


class FiltrosRespostas(BaseModel):
    busca: Busca = None
    categoria: Annotated[Literal[CATEGORIAS] | None, Opcional] = None  # type: ignore[valid-type]
    tipo_nota: Annotated[Literal["nps", "csat"] | None, Opcional] = None
    grupo_id: Id = None
    empresa_id: Id = None
    contato_id: Id = None
    tema: Annotated[Tema | None, Opcional] = None
    perfil_id: Id = None
    canal: Annotated[Literal[CANAIS] | None, Opcional] = None  # type: ignore[valid-type]
    origem: Annotated[Literal[ORIGENS] | None, Opcional] = None  # type: ignore[valid-type]
    formulario_id: Id = None
    de: DataFiltro = None
    ate: DataFiltro = None
    data_por: Annotated[Literal["resposta", "entrada"] | None, Opcional] = None  # vazio = resposta
    arquivadas: Annotated[Literal["false", "true", "todas"] | None, Opcional] = None  # vazio = false
    # como no painel: tira respostas de empresas inativas (respostas sem empresa sempre contam)
    so_ativos: Annotated[bool | None, Opcional] = None  # vazio = false


def _nota_nps(v: int) -> int:
    if not 0 <= v <= 10:
        raise PydanticCustomError("toqqi_nota", "A nota precisa ser de 0 a 10.")
    return v


class RespostaManualIn(BaseModel):
    contato_id: int
    nota: Annotated[int, AfterValidator(_nota_nps)]
    canal: Literal[CANAIS_MANUAIS] = "manual"  # type: ignore[valid-type]
    comentario: TextoAte(4000) = None
    data: date | None = None


class AnaliseIn(BaseModel):
    """Corpo parcial: só os campos enviados mudam. `temas` enviado vira escolha manual."""
    nota: int | None = None
    comentario: TextoAte(4000) = None
    o_que_faltou: TextoAte(2000) = None
    o_que_combinamos: TextoAte(2000) = None
    temas: Annotated[list[Tema], Field(max_length=20)] | None = None
