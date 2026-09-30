from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from toqqi.core.deps import Contexto, requer
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.empresas import servico
from toqqi.modulos.empresas.esquemas import EmpresaAlterarIn, EmpresaIn

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("")
def listar(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    grupo_id: int | None = None,
    segmento_id: int | None = None,
    responsavel_id: int | None = None,
    ativa: Literal["true", "false", "todas"] = "todas",
    pg: Pagina = Depends(pagina),
    ctx: Contexto = Depends(requer("contatos.ver")),
):
    return servico.listar(ctx, pg, (busca or "").strip() or None, grupo_id, segmento_id, responsavel_id, ativa)


@router.post("", status_code=201)
def criar(dados: EmpresaIn, ctx: Contexto = Depends(requer("contatos.editar"))):
    return servico.criar(ctx, dados)


@router.get("/{empresa_id}")
def obter(empresa_id: int, ctx: Contexto = Depends(requer("contatos.ver"))):
    return servico.obter(ctx, empresa_id)


@router.patch("/{empresa_id}")
def alterar(empresa_id: int, dados: EmpresaAlterarIn, ctx: Contexto = Depends(requer("contatos.editar"))):
    return servico.alterar(ctx, empresa_id, dados)


@router.delete("/{empresa_id}", status_code=204)
def excluir(empresa_id: int, ctx: Contexto = Depends(requer("contatos.excluir"))):
    servico.excluir(ctx, empresa_id)
    return Response(status_code=204)
