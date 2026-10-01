from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from toqqi.core.deps import Contexto, requer
from toqqi.core.filtros import DataFiltro
from toqqi.modulos.painel import servico
from toqqi.modulos.respostas.esquemas import Id, Opcional
from toqqi.modulos.respostas.rotas import csv_resposta
from toqqi.modulos.respostas.servico import nome_csv

router = APIRouter(prefix="/painel", tags=["painel"])


class FiltrosPainel(BaseModel):
    de: DataFiltro = None
    ate: DataFiltro = None
    grupo_id: Id = None
    so_ativos: Annotated[bool | None, Opcional] = None  # vazio = true

    def args(self) -> tuple:
        return self.de, self.ate, self.grupo_id, self.so_ativos is not False


@router.get("")
def painel(filtros: Annotated[FiltrosPainel, Query()], ctx: Contexto = Depends(requer("painel.ver"))):
    return servico.painel(ctx, *filtros.args())


@router.get("/exportar.csv")
def exportar(filtros: Annotated[FiltrosPainel, Query()], ctx: Contexto = Depends(requer("painel.exportar"))):
    return csv_resposta(servico.exportar_csv(ctx, *filtros.args()), nome_csv())
