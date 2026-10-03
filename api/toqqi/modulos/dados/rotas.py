"""Configurações › Dados da conta (etapa 5f): exportar todos os dados e a zona de risco. Só o administrador."""
from fastapi import APIRouter, Depends, Request

from toqqi.core.deps import Contexto, requer, requer_admin
from toqqi.core.rate_limit import limite_por_usuario, limiter
from toqqi.modulos.dados import exportacao, zona
from toqqi.modulos.dados.esquemas import ZonaIn

router = APIRouter(prefix="/conta", tags=["dados"])
LIMITE_DADOS = "5/hour"  # exportação e zona de risco, por usuário
ZONA = requer("zona_risco.usar")


@router.get("/exportacao.zip")
@limiter.limit(LIMITE_DADOS, key_func=limite_por_usuario)
def exportar(request: Request, ctx: Contexto = Depends(requer_admin)):
    """Vale também com a conta encerrada (sem conferir se está liberada)."""
    return exportacao.resposta(ctx)


@router.get("/zona-de-risco")
def contagens(ctx: Contexto = Depends(ZONA)):
    return zona.obter(ctx)


@router.post("/zona-de-risco")
@limiter.limit(LIMITE_DADOS, key_func=limite_por_usuario)
def apagar(request: Request, dados: ZonaIn, ctx: Contexto = Depends(ZONA)):
    return zona.apagar(ctx, dados.opcao, dados.confirmacao)
