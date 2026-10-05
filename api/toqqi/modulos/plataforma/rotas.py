from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Response

from toqqi.core.deps import Contexto, requer_superadmin
from toqqi.core.errors import AppError
from toqqi.core.validacao import MAX_ID
from toqqi.modulos.plataforma import erros, servico, visao
from toqqi.modulos.plataforma.esquemas import EstenderTesteIn, ExcluirContaIn, NovaContaIn

router = APIRouter(prefix="/plataforma", tags=["plataforma"])

IdErro = Annotated[int, Path(ge=1, le=MAX_ID)]


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


@router.delete("/contas/{conta_id}", status_code=204)
def excluir(conta_id: int, dados: ExcluirContaIn, ctx: Contexto = Depends(requer_superadmin)):
    servico.excluir_conta(ctx, conta_id, dados.confirmar_nome)
    return Response(status_code=204)


# ---- etapa 5h: visão do negócio e erros ---------------------------------------------------------------------------

@router.get("/visao")
def ver_visao(ctx: Contexto = Depends(requer_superadmin)):
    """Visão geral do negócio (`visao.py`)."""
    return visao.visao()


@router.get("/erros")
def listar_erros(
    origem: Annotated[Literal["", "api", "site", "tarefa"] | None, Query()] = None,
    situacao: Annotated[Literal["abertos", "resolvidos", "todos"], Query()] = "abertos",
    dias: Annotated[int, Query()] = 7,
    ctx: Contexto = Depends(requer_superadmin),
):
    """Plataforma › Erros (`erros.py`): `dias` 7 ou 30 (outro → 422 no campo)."""
    if dias not in erros.DIAS:
        raise AppError(422, "dados_invalidos", "Confira os campos destacados.", {"dias": "Use 7 ou 30 dias."})
    return erros.listar(origem or None, situacao, dias)


@router.post("/erros/{erro_id}/resolver")
def resolver_erro(erro_id: IdErro, ctx: Contexto = Depends(requer_superadmin)):
    return erros.resolver(erro_id)


@router.post("/erros/{erro_id}/reabrir")
def reabrir_erro(erro_id: IdErro, ctx: Contexto = Depends(requer_superadmin)):
    return erros.reabrir(erro_id)
