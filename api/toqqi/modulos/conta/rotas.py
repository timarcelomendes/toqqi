from fastapi import APIRouter, Depends

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.conta import servico
from toqqi.modulos.conta.esquemas import SegurancaIn

router = APIRouter(prefix="/conta", tags=["conta"])
GERENCIAR = requer("configuracoes.gerenciar")


@router.get("/seguranca")
def obter(ctx: Contexto = Depends(GERENCIAR)):
    return servico.obter(ctx)


@router.put("/seguranca")
def salvar(dados: SegurancaIn, ctx: Contexto = Depends(GERENCIAR)):
    return servico.salvar(ctx, dados)
