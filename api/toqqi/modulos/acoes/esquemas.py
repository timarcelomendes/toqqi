from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator
from pydantic_core import PydanticCustomError

from toqqi.core.filtros import DataFiltro
from toqqi.core.validacao import TextoAte
from toqqi.modulos.respostas.esquemas import CATEGORIAS, Busca, Id, Opcional

Prioridade = Literal["alta", "media", "baixa"]
Situacao = Literal["a_fazer", "em_andamento", "concluida"]


def _titulo(v):
    if not isinstance(v, str):
        return v
    v = v.strip()
    if not v:
        raise PydanticCustomError("toqqi_titulo", "Escreva o título da ação.")
    if len(v) > 200:
        raise PydanticCustomError("toqqi_titulo", "Use no máximo 200 caracteres.")
    return v


def _prazo_dias(v: int) -> int:
    if not 1 <= v <= 90:
        raise PydanticCustomError("toqqi_prazo", "Use um prazo de 1 a 90 dias.")
    return v


Titulo = Annotated[str, BeforeValidator(_titulo)]
PrazoDias = Annotated[int, AfterValidator(_prazo_dias)]


class AcaoIn(BaseModel):
    titulo: Titulo
    descricao: TextoAte(4000) = None
    empresa_id: int | None = None
    contato_id: int | None = None
    resposta_id: int | None = None
    responsavel_id: int | None = None
    prioridade: Prioridade = "media"
    prazo: date | None = None


class AcaoAlterarIn(BaseModel):
    """Corpo parcial; null limpa os campos opcionais (descrição, resolução, responsável, prazo, empresa)."""
    titulo: Titulo | None = None
    descricao: TextoAte(4000) = None
    resolucao: TextoAte(4000) = None
    responsavel_id: int | None = None
    prioridade: Prioridade | None = None
    prazo: date | None = None
    situacao: Situacao | None = None
    empresa_id: int | None = None


class FiltrosAcoes(BaseModel):
    busca: Busca = None
    categoria: Annotated[Literal[CATEGORIAS] | None, Opcional] = None  # type: ignore[valid-type]
    tipo_nota: Annotated[Literal["nps", "csat"] | None, Opcional] = None
    responsavel_id: Id = None  # 0 = sem responsável
    empresa_id: Id = None
    grupo_id: Id = None
    de: DataFiltro = None
    ate: DataFiltro = None
    so_vencidas: Annotated[bool | None, Opcional] = None


class FiltrosListaAcoes(FiltrosAcoes):
    situacao: Annotated[Situacao | None, Opcional] = None


class ConfigAcoesIn(BaseModel):
    """Corpo parcial: só os campos enviados mudam."""
    prazo_detrator: PrazoDias | None = None
    prazo_neutro: PrazoDias | None = None
    prazo_promotor: PrazoDias | None = None
    acao_promotor: bool | None = None

