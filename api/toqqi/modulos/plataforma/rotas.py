from fastapi import APIRouter, Depends

from toqqi.core.deps import Contexto, requer_superadmin
from toqqi.modulos.plataforma import servico
from toqqi.modulos.plataforma.esquemas import EstenderTesteIn, NovaContaIn

router = APIRouter(prefix="/plataforma", tags=["plataforma"])


@router.get("/contas")
def listar(ctx: Contexto = Depends(requer_superadmin)):
    return servico.listar()


@router.post("/contas", status_code=201)
def criar(dados: NovaContaIn, ctx: Contexto = Depends(requer_superadmin)):
    return servico.criar_conta(ctx, dados)


@router.post("/contas/{conta_id}/estender-teste")
def estender_teste(conta_id: int, dados: EstenderTesteIn | None = None, ctx: Contexto = Depends(requer_superadmin)):
    return servico.estender_teste(ctx, conta_id, (dados or EstenderTesteIn()).dias)


@router.post("/contas/{conta_id}/cortesia")
def cortesia(conta_id: int, ctx: Contexto = Depends(requer_superadmin)):
    return servico.cortesia(ctx, conta_id)
