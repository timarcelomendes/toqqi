from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from toqqi.core.deps import Contexto, requer
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.contatos import servico
from toqqi.modulos.contatos.esquemas import ContatoAlterarIn, ContatoIn, LinkPesquisaIn
from toqqi.modulos.envios import servico as envios
from toqqi.modulos.envios.esquemas import WhatsappIn

router = APIRouter(prefix="/contatos", tags=["contatos"])


@router.get("")
def listar(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    empresa_id: int | None = None,
    grupo_id: int | None = None,
    responsavel_id: int | None = None,
    perfil_id: int | None = None,
    ativo: Literal["true", "false", "todos"] = "todos",
    pg: Pagina = Depends(pagina),
    ctx: Contexto = Depends(requer("contatos.ver")),
):
    return servico.listar(ctx, pg, (busca or "").strip() or None, empresa_id, grupo_id, responsavel_id,
                          perfil_id, ativo)


@router.post("", status_code=201)
def criar(dados: ContatoIn, ctx: Contexto = Depends(requer("contatos.editar"))):
    return servico.criar(ctx, dados)


@router.get("/{contato_id}")
def obter(contato_id: int, ctx: Contexto = Depends(requer("contatos.ver"))):
    return servico.obter(ctx, contato_id)


@router.patch("/{contato_id}")
def alterar(contato_id: int, dados: ContatoAlterarIn, ctx: Contexto = Depends(requer("contatos.editar"))):
    return servico.alterar(ctx, contato_id, dados)


@router.delete("/{contato_id}", status_code=204)
def excluir(contato_id: int, ctx: Contexto = Depends(requer("contatos.excluir"))):
    servico.excluir(ctx, contato_id)
    return Response(status_code=204)


@router.post("/{contato_id}/link-pesquisa", status_code=201)
def link_pesquisa(contato_id: int, dados: LinkPesquisaIn, ctx: Contexto = Depends(requer("envios.disparar"))):
    return servico.link_pesquisa(ctx, contato_id, dados)


@router.post("/{contato_id}/whatsapp", status_code=201)
def whatsapp(contato_id: int, dados: WhatsappIn | None = None, ctx: Contexto = Depends(requer("envios.disparar"))):
    return envios.whatsapp(ctx, contato_id, dados or WhatsappIn())
