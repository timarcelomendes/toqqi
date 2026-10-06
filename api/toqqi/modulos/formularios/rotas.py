from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from toqqi.core.deps import Contexto, requer
from toqqi.core.paginacao import Pagina, pagina
from toqqi.modulos.formularios import servico
from toqqi.modulos.formularios.esquemas import (
    FormularioAlterarIn,
    FormularioIn,
    PadraoIn,
    PublicarIn,
    RascunhoIn,
)
from toqqi.modulos.imagens.servico import LIMITE_BANCO, MSG_BANCO, ler_envio, nome_do_arquivo

router = APIRouter(prefix="/formularios", tags=["formularios"])
VER = requer("formularios.ver")
EDITAR = requer("formularios.editar")
Data = Annotated[str | None, Query(max_length=10)]


@router.get("")
def listar(ctx: Contexto = Depends(VER)):
    return servico.listar(ctx)


@router.get("/modelos")
def modelos(ctx: Contexto = Depends(VER)):
    return servico.modelos(ctx)


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


@router.put("/{formulario_id}/rascunho")
def salvar_rascunho(formulario_id: int, dados: RascunhoIn, ctx: Contexto = Depends(EDITAR)):
    """Grava o rascunho (etapa 5l): rev diferente → 409 `rascunho_desatualizado`; só o estrutural dá 422; os outros
    problemas voltam em `problemas`."""
    return servico.salvar_rascunho(ctx, formulario_id, dados)


@router.delete("/{formulario_id}/rascunho", status_code=204)
def descartar_rascunho(formulario_id: int, ctx: Contexto = Depends(EDITAR)):
    servico.descartar_rascunho(ctx, formulario_id)
    return Response(status_code=204)


@router.post("/{formulario_id}/publicar")
def publicar(formulario_id: int, dados: PublicarIn, ctx: Contexto = Depends(EDITAR)):
    return servico.publicar(ctx, formulario_id, dados)


@router.post("/{formulario_id}/imagens", status_code=201)
def enviar_imagem(formulario_id: int, arquivo: UploadFile = File(...), ctx: Contexto = Depends(EDITAR)):
    """Imagem de um bloco de conteúdo (etapa 5l): PNG ou JPG de até 1 MB, conferido pelos bytes → {url, largura,
    altura}."""
    conteudo, tipo = ler_envio(arquivo, LIMITE_BANCO, MSG_BANCO)
    return servico.enviar_imagem(ctx, formulario_id, conteudo, tipo, nome_do_arquivo(arquivo.filename))


@router.post("/{formulario_id}/duplicar", status_code=201)
def duplicar(formulario_id: int, ctx: Contexto = Depends(EDITAR)):
    return servico.duplicar(ctx, formulario_id)


@router.post("/{formulario_id}/padrao")
def padrao(formulario_id: int, dados: PadraoIn, ctx: Contexto = Depends(EDITAR)):
    return servico.definir_padrao(ctx, formulario_id, dados.uso)


@router.post("/{formulario_id}/logo")
def enviar_logo(formulario_id: int, arquivo: UploadFile = File(...), ctx: Contexto = Depends(EDITAR)):
    """Guarda um logo novo do formulário e devolve a URL; o tema só muda quando o rascunho (ou o PATCH) grava a URL.
    O logo publicado não é apagado (etapa 5l)."""
    conteudo, tipo = ler_envio(arquivo)
    return servico.enviar_logo(ctx, formulario_id, conteudo, tipo)


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
