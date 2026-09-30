from typing import Literal

from fastapi import APIRouter, Depends, Response

from toqqi.core.deps import Contexto, requer
from toqqi.modulos.cadastros import servico
from toqqi.modulos.cadastros.esquemas import ItemIn, ResponsavelAlterarIn, ResponsavelIn

router = APIRouter(tags=["cadastros"])
VER = requer("contatos.ver")
EDITAR = requer("contatos.editar")
EXCLUIR = requer("contatos.excluir")
Tipo = Literal["grupos", "segmentos", "perfis", "cargos"]


@router.get("/cadastros/{tipo}")
def listar(tipo: Tipo, ctx: Contexto = Depends(VER)):
    return servico.listar(ctx, tipo)


@router.post("/cadastros/{tipo}", status_code=201)
def criar(tipo: Tipo, dados: ItemIn, ctx: Contexto = Depends(EDITAR)):
    return servico.criar(ctx, tipo, dados.nome)


@router.patch("/cadastros/{tipo}/{item_id}")
def alterar(tipo: Tipo, item_id: int, dados: ItemIn, ctx: Contexto = Depends(EDITAR)):
    return servico.alterar(ctx, tipo, item_id, dados.nome)


@router.delete("/cadastros/{tipo}/{item_id}", status_code=204)
def excluir(tipo: Tipo, item_id: int, ctx: Contexto = Depends(EXCLUIR)):
    servico.excluir(ctx, tipo, item_id)
    return Response(status_code=204)


@router.get("/responsaveis")
def listar_responsaveis(ctx: Contexto = Depends(VER)):
    return servico.listar_responsaveis(ctx)


@router.post("/responsaveis", status_code=201)
def criar_responsavel(dados: ResponsavelIn, ctx: Contexto = Depends(EDITAR)):
    return servico.criar_responsavel(ctx, dados)


@router.patch("/responsaveis/{rid}")
def alterar_responsavel(rid: int, dados: ResponsavelAlterarIn, ctx: Contexto = Depends(EDITAR)):
    return servico.alterar_responsavel(ctx, rid, dados)


@router.delete("/responsaveis/{rid}", status_code=204)
def excluir_responsavel(rid: int, ctx: Contexto = Depends(EXCLUIR)):
    servico.excluir_responsavel(ctx, rid)
    return Response(status_code=204)


@router.post("/responsaveis/{rid}/testar-teams")
def testar_teams(rid: int, ctx: Contexto = Depends(EDITAR)):
    return {"mensagem": servico.testar_teams(ctx, rid)}
