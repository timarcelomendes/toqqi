from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from toqqi.core.deps import Contexto, requer
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.formularios import servico
from toqqi.modulos.formularios.esquemas import FormularioAlterarIn, FormularioIn, PadraoIn

router = APIRouter(prefix="/formularios", tags=["formularios"])
VER = requer("formularios.ver")
EDITAR = requer("formularios.editar")
Data = Annotated[str | None, Query(max_length=10)]


@router.get("")
def listar(ctx: Contexto = Depends(VER)):
    return servico.listar(ctx)


@router.get("/modelos")
def modelos(ctx: Contexto = Depends(VER)):
    return servico.modelos()


@router.post("", status_code=201)
def criar(dados: FormularioIn, ctx: Contexto = Depends(EDITAR)):
    return servico.criar(ctx, dados)


@router.get("/{formulario_id}")
def obter(formulario_id: int, ctx: Contexto = Depends(VER)):
    return servico.obter(ctx, formulario_id)


@router.patch("/{formulario_id}")
def alterar(formulario_id: int, dados: FormularioAlterarIn, ctx: Contexto = Depends(EDITAR)):
    return servico.alterar(ctx, formulario_id, dados)


@router.delete("/{formulario_id}", status_code=204)
def excluir(formulario_id: int, ctx: Contexto = Depends(EDITAR)):
    servico.excluir(ctx, formulario_id)
    return Response(status_code=204)


@router.post("/{formulario_id}/duplicar", status_code=201)
def duplicar(formulario_id: int, ctx: Contexto = Depends(EDITAR)):
    return servico.duplicar(ctx, formulario_id)


@router.post("/{formulario_id}/padrao")
def padrao(formulario_id: int, dados: PadraoIn, ctx: Contexto = Depends(EDITAR)):
    return servico.definir_padrao(ctx, formulario_id, dados.uso)


@router.post("/{formulario_id}/novo-codigo")
def novo_codigo(formulario_id: int, ctx: Contexto = Depends(EDITAR)):
    return servico.novo_codigo(ctx, formulario_id)


@router.get("/{formulario_id}/resultados")
def resultados(formulario_id: int, de: Data = None, ate: Data = None, ctx: Contexto = Depends(VER)):
    return servico.resultados(ctx, formulario_id, de, ate)


@router.get("/{formulario_id}/respostas")
def respostas(formulario_id: int, de: Data = None, ate: Data = None, pg: Pagina = Depends(pagina),
              ctx: Contexto = Depends(VER)):
    return servico.listar_respostas(ctx, formulario_id, de, ate, pg)


@router.get("/{formulario_id}/respostas.csv")
def respostas_csv(formulario_id: int, de: Data = None, ate: Data = None, ctx: Contexto = Depends(VER)):
    conteudo, nome = servico.respostas_csv(ctx, formulario_id, de, ate)
    return Response(conteudo.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
