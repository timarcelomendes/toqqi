from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from toqqi.core.deps import Contexto, requer
from toqqi.core.filtros import DataFiltro
from toqqi.modulos.ia import pareceres
from toqqi.modulos.painel import servico
from toqqi.modulos.painel.resumo_ia import TIPO as RESUMO_IA
from toqqi.modulos.respostas.esquemas import Id, Opcional
from toqqi.modulos.respostas.rotas import csv_resposta
from toqqi.modulos.respostas.servico import nome_csv

router = APIRouter(prefix="/painel", tags=["painel"])
VER = requer("painel.ver")


class FiltrosPainel(BaseModel):
    de: DataFiltro = None
    ate: DataFiltro = None
    grupo_id: Id = None
    so_ativos: Annotated[bool | None, Opcional] = None  # vazio = true

    def args(self) -> tuple:
        return self.de, self.ate, self.grupo_id, self.so_ativos is not False


@router.get("")
def painel(filtros: Annotated[FiltrosPainel, Query()], ctx: Contexto = Depends(VER)):
    return servico.painel(ctx, *filtros.args())


# ---- resumo da IA (etapa 5d) ----------------------------------------------------------

@router.get("/resumo-ia")
def resumo_ia(filtros: Annotated[FiltrosPainel, Query()], ctx: Contexto = Depends(VER)):
    return pareceres.estado(ctx, RESUMO_IA, pareceres.Recorte.dos_filtros(filtros))


@router.post("/resumo-ia")
def gerar_resumo_ia(dados: FiltrosPainel | None = None, ctx: Contexto = Depends(VER)):
    # síncrona: segura uma thread da API por até 45 s; as vagas do assistente limitam quantas ao mesmo tempo
    return pareceres.gerar(ctx, RESUMO_IA, pareceres.Recorte.dos_filtros(dados or FiltrosPainel()))


@router.get("/exportar.csv")
def exportar(filtros: Annotated[FiltrosPainel, Query()], ctx: Contexto = Depends(requer("painel.exportar"))):
    return csv_resposta(servico.exportar_csv(ctx, *filtros.args()), nome_csv())
